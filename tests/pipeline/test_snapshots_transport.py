from __future__ import annotations

import hashlib
import io
import json
import ssl
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from museum_pipeline.adapters import get_adapter
from museum_pipeline.adapters.base import RequestSpec, ResponseContract
from museum_pipeline.canonical_json import canonical_json_bytes, write_canonical_json
from museum_pipeline.errors import PipelineError
from museum_pipeline.hashing import sha256_bytes
from museum_pipeline.paths import resolve_within, safe_relative_path
from museum_pipeline.snapshots import load_snapshot_manifest, snapshot_body_bytes, validate_snapshot, write_snapshot
from museum_pipeline.transport import HttpTransport, TransportPolicy, _parse_retry_after


class SequenceTransport(HttpTransport):
    def __init__(self, responses: list[ResponseContract], *, policy: TransportPolicy | None = None) -> None:
        self.delays: list[float] = []
        super().__init__(
            policy=policy or TransportPolicy(max_retries=3, total_timeout_seconds=60),
            sleeper=self.delays.append,
            random_value=lambda: 0,
            resolver=lambda *_args, **_kwargs: [(None, None, None, None, ("93.184.216.34", 443))],
        )
        self.responses = list(responses)
        self.calls = 0
        self.timeouts: list[float] = []

    def _one_request(self, request: RequestSpec, timeout: float) -> ResponseContract:
        self.calls += 1
        self.timeouts.append(timeout)
        if not self.responses:
            raise AssertionError("unexpected extra retry")
        return self.responses.pop(0)


def snapshot_fixture(raw_root: Path, *, body: bytes = b'{"line":"one\r\ntwo","text":"\xe8\x89\xba"}\r\n', at: datetime | None = None) -> Path:
    adapter = get_adapter("aic_api")
    request = adapter.build_request("27992")
    response = ResponseContract(200, {"content-type": "application/json", "etag": '"fixture"'}, body, request.url)
    return write_snapshot(
        adapter=adapter,
        request=request,
        response=response,
        source_object_ids=["27992"],
        run_id="pipeline-run:77777777-7777-5777-8777-777777777777",
        fetched_at=at or datetime(2026, 7, 12, 0, 0, 0, tzinfo=timezone.utc),
        raw_root=raw_root,
    )


class SnapshotTests(unittest.TestCase):
    def test_canonical_json_is_sorted_compact_utf8(self) -> None:
        self.assertEqual(b'{"a":"\xe8\x89\xba","b":2}', canonical_json_bytes({"b": 2, "a": "艺"}))

    def test_sha256_is_independent_of_host_path_and_platform(self) -> None:
        payload = b"line1\r\nline2\n"
        expected = "sha256:" + hashlib.sha256(payload).hexdigest()
        self.assertEqual(expected, sha256_bytes(payload))

    def test_raw_response_bytes_are_preserved_exactly(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            body = b"{\"unicode\":\"\xe8\x89\xba\",\"line\":\"a\\r\\nb\"}\r\n"
            snapshot = snapshot_fixture(Path(temporary) / "raw", body=body)
            self.assertEqual(body, (snapshot / "response.body").read_bytes())
            self.assertEqual(body, snapshot_body_bytes(snapshot, raw_root=Path(temporary) / "raw"))
            self.assertEqual([], validate_snapshot(snapshot))

    def test_snapshot_write_is_append_only(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "raw"
            snapshot_fixture(root)
            with self.assertRaises(PipelineError) as context:
                snapshot_fixture(root)
            self.assertEqual("snapshot_overwrite", context.exception.code)

    def test_identical_body_creates_reference_event_not_duplicate_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "raw"
            first = snapshot_fixture(root)
            second = snapshot_fixture(root, at=datetime(2026, 7, 12, 0, 0, 1, tzinfo=timezone.utc))
            manifest = load_snapshot_manifest(second)
            self.assertEqual("duplicate_content", manifest["event_type"])
            self.assertIsNone(manifest["response_body_path"])
            self.assertEqual(load_snapshot_manifest(first)["snapshot_id"], manifest["reused_body_snapshot_id"])
            self.assertFalse((second / "response.body").exists())
            self.assertEqual(snapshot_body_bytes(first, raw_root=root), snapshot_body_bytes(second, raw_root=root))
            self.assertEqual(snapshot_body_bytes(first), snapshot_body_bytes(second))

    def test_http_304_creates_new_check_event_referencing_prior_body(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "raw"
            previous = snapshot_fixture(root)
            adapter = get_adapter("aic_api")
            request = adapter.build_request("27992")
            response = ResponseContract(304, {"content-type": "application/json", "etag": '"fixture"'}, b"", request.url)
            check = write_snapshot(
                adapter=adapter, request=request, response=response, source_object_ids=["27992"],
                run_id="pipeline-run:77777777-7777-5777-8777-777777777777",
                fetched_at=datetime(2026, 7, 12, 0, 0, 2, tzinfo=timezone.utc), raw_root=root,
                previous_snapshot=previous,
            )
            manifest = load_snapshot_manifest(check)
            self.assertEqual("not_modified", manifest["event_type"])
            self.assertEqual(load_snapshot_manifest(previous)["body_sha256"], manifest["body_sha256"])
            self.assertTrue(manifest["snapshot_id"].endswith(manifest["body_sha256"][7:19]))
            self.assertEqual([], validate_snapshot(check, raw_root=root))

    def test_duplicate_reference_detects_later_body_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "raw"
            first = snapshot_fixture(root)
            second = snapshot_fixture(root, at=datetime(2026, 7, 12, 0, 0, 1, tzinfo=timezone.utc))
            (first / "response.body").write_bytes(b"tampered")
            issues = validate_snapshot(second, raw_root=root)
            self.assertIn("body_hash_mismatch", issues)
            self.assertIn("body_bytes_mismatch", issues)

    def test_corrupt_existing_body_is_not_reused_for_a_new_event(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "raw"
            first = snapshot_fixture(root)
            (first / "response.body").write_bytes(b"tampered")
            second = snapshot_fixture(root, at=datetime(2026, 7, 12, 0, 0, 1, tzinfo=timezone.utc))
            manifest = load_snapshot_manifest(second)
            self.assertEqual("acquired", manifest["event_type"])
            self.assertTrue((second / "response.body").exists())

    def test_body_hash_and_byte_tampering_are_detected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            snapshot = snapshot_fixture(Path(temporary) / "raw")
            (snapshot / "response.body").write_bytes(b"tampered")
            issues = validate_snapshot(snapshot)
            self.assertIn("body_hash_mismatch", issues)
            self.assertIn("body_bytes_mismatch", issues)

    def test_future_fetch_time_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            snapshot = snapshot_fixture(Path(temporary) / "raw")
            manifest = load_snapshot_manifest(snapshot)
            manifest["fetched_at"] = "2099-01-01T00:00:00Z"
            write_canonical_json(snapshot / "manifest.json", manifest)
            self.assertIn("future_fetched_at", validate_snapshot(snapshot))

    def test_parent_windows_and_absolute_paths_are_rejected(self) -> None:
        for value in ("../outside", "C:/outside", "C:\\outside", "/absolute", "a/../../b", "a//b", "a/./b", "CON/file.json", "name./file"):
            with self.subTest(value=value), self.assertRaises(PipelineError):
                safe_relative_path(value)

    def test_symlink_component_is_rejected_before_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "link").mkdir()
            original = Path.is_symlink
            with patch.object(Path, "is_symlink", lambda self: self.name == "link" or original(self)):
                with self.assertRaises(PipelineError) as context:
                    resolve_within(root, "link/file.json")
            self.assertEqual("symlink_escape", context.exception.code)

    def test_snapshot_manifest_has_no_cookie_or_secret_headers(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            snapshot = snapshot_fixture(Path(temporary) / "raw")
            manifest = load_snapshot_manifest(snapshot)
            text = json.dumps(manifest, ensure_ascii=False).lower()
            self.assertNotIn("cookie", text)
            self.assertNotIn("authorization", text)

    def test_snapshot_normalizes_allowlisted_response_header_names(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            adapter = get_adapter("aic_api")
            request = adapter.build_request("27992")
            snapshot = write_snapshot(
                adapter=adapter, request=request,
                response=ResponseContract(200, {"Content-Type": "application/json", "ETag": '"x"'}, b"{}", request.url),
                source_object_ids=["27992"], run_id="pipeline-run:77777777-7777-5777-8777-777777777777",
                fetched_at=datetime(2026, 7, 12, tzinfo=timezone.utc), raw_root=Path(temporary) / "raw",
            )
            self.assertEqual({"content-type", "etag"}, set(load_snapshot_manifest(snapshot)["response_headers"]))

    def test_tampered_snapshot_endpoint_is_rejected_against_adapter_allowlist(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            snapshot = snapshot_fixture(Path(temporary) / "raw")
            manifest = load_snapshot_manifest(snapshot)
            manifest["canonical_endpoint"] = "https://evil.example/object/1"
            write_canonical_json(snapshot / "manifest.json", manifest)
            self.assertIn("endpoint_not_allowed", validate_snapshot(snapshot))


class TransportTests(unittest.TestCase):
    def test_retry_after_seconds_is_honored(self) -> None:
        adapter = get_adapter("wikidata")
        request = adapter.build_request("Q42")
        transport = SequenceTransport([
            ResponseContract(429, {"retry-after": "2"}, b"", request.url),
            ResponseContract(200, {"content-type": "application/json"}, b"{}", request.url),
        ])
        result = transport.fetch(adapter, request)
        self.assertEqual(1, result.retry_count)
        self.assertEqual([2.0], transport.delays)

    def test_single_socket_timeout_honors_stricter_connect_and_read_ceiling(self) -> None:
        adapter = get_adapter("wikidata")
        request = adapter.build_request("Q42")
        transport = SequenceTransport(
            [ResponseContract(200, {"content-type": "application/json"}, b"{}", request.url)],
            policy=TransportPolicy(connect_timeout_seconds=3, read_timeout_seconds=11, total_timeout_seconds=30),
        )
        transport.fetch(adapter, request)
        self.assertEqual([3], transport.timeouts)

    def test_5xx_retry_is_exponential_and_bounded(self) -> None:
        adapter = get_adapter("wikidata")
        request = adapter.build_request("Q42")
        responses = [ResponseContract(503, {}, b"", request.url) for _ in range(5)]
        transport = SequenceTransport(responses)
        result = transport.fetch(adapter, request)
        self.assertEqual(503, result.status_code)
        self.assertEqual(4, transport.calls)
        self.assertEqual([0.5, 1.0, 2.0], transport.delays)

    def test_regular_4xx_is_not_retried(self) -> None:
        adapter = get_adapter("wikidata")
        request = adapter.build_request("Q42")
        transport = SequenceTransport([ResponseContract(404, {}, b"", request.url)])
        result = transport.fetch(adapter, request)
        self.assertEqual(404, result.status_code)
        self.assertEqual(1, transport.calls)

    def test_redirect_to_unapproved_host_is_rejected(self) -> None:
        adapter = get_adapter("wikidata")
        request = adapter.build_request("Q42")
        transport = SequenceTransport([ResponseContract(302, {"location": "https://evil.example/Q42"}, b"", request.url)])
        with self.assertRaises(PipelineError) as context:
            transport.fetch(adapter, request)
        self.assertEqual("endpoint_not_allowed", context.exception.code)

    def test_redirect_chain_is_recorded_for_approved_path(self) -> None:
        adapter = get_adapter("wikidata")
        request = adapter.build_request("Q42")
        redirected = adapter.build_request("Q1").url
        transport = SequenceTransport([
            ResponseContract(302, {"location": redirected}, b"", request.url),
            ResponseContract(200, {"content-type": "application/json"}, b"{}", redirected),
        ])
        result = transport.fetch(adapter, request)
        self.assertEqual((redirected,), result.redirect_chain)

    def test_private_dns_resolution_is_blocked(self) -> None:
        transport = HttpTransport(resolver=lambda *_args, **_kwargs: [(None, None, None, None, ("127.0.0.1", 443))])
        adapter = get_adapter("wikidata")
        with self.assertRaises(PipelineError) as context:
            transport.fetch(adapter, adapter.build_request("Q42"))
        self.assertEqual("private_network_blocked", context.exception.code)

    def test_shared_non_global_dns_range_is_blocked(self) -> None:
        transport = HttpTransport(resolver=lambda *_args, **_kwargs: [(None, None, None, None, ("100.64.0.1", 443))])
        adapter = get_adapter("wikidata")
        with self.assertRaises(PipelineError) as context:
            transport.fetch(adapter, adapter.build_request("Q42"))
        self.assertEqual("private_network_blocked", context.exception.code)

    def test_response_body_limit_blocks_response_bomb(self) -> None:
        transport = HttpTransport(policy=TransportPolicy(max_response_bytes=4))
        with self.assertRaises(PipelineError) as context:
            transport._read_response(200, {"content-length": "5"}, io.BytesIO(b"12345"), "https://example.org")
        self.assertEqual("response_too_large", context.exception.code)

    def test_cookie_request_header_is_forbidden(self) -> None:
        transport = HttpTransport(resolver=lambda *_args, **_kwargs: [(None, None, None, None, ("93.184.216.34", 443))])
        adapter = get_adapter("wikidata")
        request = adapter.build_request("Q42")
        request = RequestSpec(request.method, request.url, {**request.headers, "Cookie": "x=y"}, request.query_profile)
        with self.assertRaises(PipelineError) as context:
            transport._one_request(request, 1)
        self.assertEqual("cookie_persistence_forbidden", context.exception.code)

    def test_tls_context_requires_certificate_validation(self) -> None:
        transport = HttpTransport()
        contexts = [getattr(handler, "_context", None) for handler in transport.opener.handlers]
        contexts = [context for context in contexts if context is not None]
        self.assertTrue(contexts)
        self.assertTrue(all(context.verify_mode == ssl.CERT_REQUIRED and context.check_hostname for context in contexts))

    def test_retry_after_http_date_parser_never_returns_negative(self) -> None:
        self.assertEqual(0.0, _parse_retry_after("Thu, 01 Jan 1970 00:00:00 GMT"))


if __name__ == "__main__":
    unittest.main()
