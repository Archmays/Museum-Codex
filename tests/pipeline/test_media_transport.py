from __future__ import annotations

import hashlib
import io
import socket
import ssl
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from museum_pipeline.errors import PipelineError
from museum_pipeline.media.transport import (
    MediaAcquisitionEvidence,
    MediaDownloadRequest,
    MediaTransport,
    MediaTransportPolicy,
    MetadataFetchRequest,
)


PUBLIC_IP = "93.184.216.34"
JPEG = b"\xff\xd8\xff\xe0" + b"governed-image"


def public_resolver(host: str, port: int, **_kwargs):  # noqa: ANN001
    return [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (PUBLIC_IP, port))]


class FakeResponse:
    def __init__(self, status: int, headers: dict[str, str] | None = None, body: bytes = b"") -> None:
        self.status = status
        self._headers = headers or {}
        self._body = io.BytesIO(body)
        self.closed = False

    def getheaders(self) -> list[tuple[str, str]]:
        return list(self._headers.items())

    def read(self, amount: int = -1) -> bytes:
        return self._body.read(amount)

    def close(self) -> None:
        self.closed = True


class FakeConnection:
    def __init__(
        self,
        response: FakeResponse,
        *,
        peer_ip: str = PUBLIC_IP,
        connect_error: BaseException | None = None,
    ) -> None:
        self.response = response
        self.peer_ip = peer_ip
        self.connect_error = connect_error
        self.requests: list[tuple[str, str, dict[str, str]]] = []
        self.connected = False
        self.closed = False
        self.sock = None

    def connect(self) -> None:
        if self.connect_error is not None:
            raise self.connect_error
        self.connected = True

    def request(self, method: str, target: str, body=None, headers=None) -> None:  # noqa: ANN001
        self.requests.append((method, target, dict(headers or {})))

    def getresponse(self) -> FakeResponse:
        return self.response

    def close(self) -> None:
        self.closed = True


class ConnectionQueue:
    def __init__(self, *connections: FakeConnection) -> None:
        self.pending = list(connections)
        self.created: list[FakeConnection] = []
        self.calls: list[tuple[str, int, tuple[str, ...], float, ssl.SSLContext]] = []

    def __call__(
        self,
        host: str,
        port: int,
        resolved_ips,
        timeout: float,
        context: ssl.SSLContext,
    ) -> FakeConnection:
        if not self.pending:
            raise AssertionError("unexpected network request")
        connection = self.pending.pop(0)
        self.created.append(connection)
        self.calls.append((host, port, tuple(resolved_ips), timeout, context))
        return connection


class FakeClock:
    def __init__(self) -> None:
        self.value = 0.0
        self.delays: list[float] = []

    def now(self) -> float:
        return self.value

    def sleep(self, delay: float) -> None:
        self.delays.append(delay)
        self.value += delay


def media_request(
    destination: Path,
    *,
    url: str = "https://media.example/object.jpg",
    source_id: str = "source:met_open_access",
    etag: str | None = None,
    expected_sha256: str | None = None,
    resume_evidence: MediaAcquisitionEvidence | None = None,
    dedupe_candidates: tuple[Path, ...] = (),
) -> MediaDownloadRequest:
    return MediaDownloadRequest(
        url=url,
        source_id=source_id,
        trusted_hosts=frozenset({"media.example"}),
        destination=destination,
        etag=etag,
        expected_sha256=expected_sha256,
        resume_evidence=resume_evidence,
        dedupe_candidates=dedupe_candidates,
    )


def image_response(
    body: bytes = JPEG,
    *,
    status: int = 200,
    extra_headers: dict[str, str] | None = None,
) -> FakeResponse:
    headers = {"Content-Type": "image/jpeg", "Content-Length": str(len(body)), "ETag": '"v1"'}
    headers.update(extra_headers or {})
    return FakeResponse(status, headers, body)


def acquisition_evidence(result, **overrides) -> MediaAcquisitionEvidence:  # noqa: ANN001
    values = {
        "request_url": "https://media.example/object.jpg",
        "final_url": result.final_url,
        "redirect_chain": result.redirect_chain,
        "status_code": result.status_code,
        "response_headers": result.response_headers,
        "resolved_public_ips": result.resolved_public_ips,
        "connected_peer_ip": result.connected_peer_ip,
        "sha256": result.sha256,
        "file_size": result.file_size,
    }
    values.update(overrides)
    return MediaAcquisitionEvidence(**values)


class MediaTransportTests(unittest.TestCase):
    def test_metadata_fetch_is_memory_only_and_records_network_evidence(self) -> None:
        response = FakeResponse(
            200,
            {
                "Content-Type": "application/json; charset=utf-8",
                "Content-Length": "11",
                "ETag": '"meta-v1"',
                "Cache-Control": "max-age=60",
                "Set-Cookie": "forbidden=persistence",
            },
            b'{"ok":true}',
        )
        queue = ConnectionQueue(FakeConnection(response))
        transport = MediaTransport(resolver=public_resolver, connection_factory=queue)

        result = transport.fetch_metadata(
            MetadataFetchRequest(
                url="https://media.example/object.json",
                source_id="source:met_open_access",
                trusted_hosts=frozenset({"media.example"}),
            )
        )

        self.assertEqual(b'{"ok":true}', result.body)
        self.assertEqual((PUBLIC_IP,), result.resolved_public_ips)
        self.assertEqual(PUBLIC_IP, result.connected_peer_ip)
        self.assertEqual(PUBLIC_IP, result.hop_evidence[0].connected_peer_ip)
        self.assertNotIn("set-cookie", result.response_headers)
        self.assertEqual('"meta-v1"', result.response_headers["etag"])
        sent_headers = queue.created[0].requests[0][2]
        self.assertEqual("application/json", sent_headers["Accept"])
        self.assertNotIn("Cookie", sent_headers)
        self.assertNotIn("Authorization", sent_headers)

    def test_download_streams_to_an_atomic_destination(self) -> None:
        queue = ConnectionQueue(FakeConnection(image_response()))
        transport = MediaTransport(resolver=public_resolver, connection_factory=queue)
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "media" / "object.jpg"
            result = transport.download(media_request(destination))

            self.assertEqual(JPEG, destination.read_bytes())
            self.assertEqual("sha256:" + hashlib.sha256(JPEG).hexdigest(), result.sha256)
            self.assertEqual("image/jpeg", result.content_type)
            self.assertEqual((PUBLIC_IP,), result.resolved_public_ips)
            self.assertEqual(PUBLIC_IP, result.connected_peer_ip)
            self.assertEqual(1, len(result.hop_evidence))
            self.assertEqual('"v1"', result.response_headers["etag"])
            self.assertIn("image/jpeg", queue.created[0].requests[0][2]["Accept"])
            self.assertFalse(list(destination.parent.glob("*.part")))
            self.assertFalse(list(destination.parent.glob("*.lock")))

    def test_private_dns_result_is_blocked_before_connection(self) -> None:
        queue = ConnectionQueue(FakeConnection(image_response()))
        resolver = lambda *_args, **_kwargs: [  # noqa: E731
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("127.0.0.1", 443))
        ]
        transport = MediaTransport(resolver=resolver, connection_factory=queue)
        with tempfile.TemporaryDirectory() as temporary, self.assertRaises(PipelineError) as context:
            transport.download(media_request(Path(temporary) / "object.jpg"))
        self.assertEqual("media_private_network_blocked", context.exception.code)
        self.assertEqual([], queue.calls)

    def test_redirect_to_untrusted_host_is_blocked_before_second_connection(self) -> None:
        redirect = FakeResponse(302, {"Location": "https://evil.example/object.jpg"})
        queue = ConnectionQueue(FakeConnection(redirect))
        transport = MediaTransport(resolver=public_resolver, connection_factory=queue)
        with tempfile.TemporaryDirectory() as temporary, self.assertRaises(PipelineError) as context:
            transport.download(media_request(Path(temporary) / "object.jpg"))
        self.assertEqual("media_host_not_trusted", context.exception.code)
        self.assertEqual(1, len(queue.calls))

    def test_connected_peer_must_match_validated_dns_set_before_http_request(self) -> None:
        connection = FakeConnection(image_response(), peer_ip="1.1.1.1")
        queue = ConnectionQueue(connection)
        transport = MediaTransport(resolver=public_resolver, connection_factory=queue)
        with tempfile.TemporaryDirectory() as temporary, self.assertRaises(PipelineError) as context:
            transport.download(media_request(Path(temporary) / "object.jpg"))
        self.assertEqual("media_peer_mismatch", context.exception.code)
        self.assertEqual([], connection.requests)

    def test_declared_oversize_is_rejected_without_partial_file(self) -> None:
        response = image_response(extra_headers={"Content-Length": "999"})
        queue = ConnectionQueue(FakeConnection(response))
        transport = MediaTransport(
            policy=MediaTransportPolicy(max_bytes=8),
            resolver=public_resolver,
            connection_factory=queue,
        )
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "object.jpg"
            with self.assertRaises(PipelineError) as context:
                transport.download(media_request(destination))
            self.assertEqual("media_too_large", context.exception.code)
            self.assertFalse(destination.exists())
            self.assertFalse(list(destination.parent.glob("*.part")))

    def test_streaming_oversize_is_rejected_without_partial_file(self) -> None:
        response = FakeResponse(200, {"Content-Type": "image/jpeg"}, JPEG)
        queue = ConnectionQueue(FakeConnection(response))
        transport = MediaTransport(
            policy=MediaTransportPolicy(max_bytes=8, chunk_size=4),
            resolver=public_resolver,
            connection_factory=queue,
        )
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "object.jpg"
            with self.assertRaises(PipelineError) as context:
                transport.download(media_request(destination))
            self.assertEqual("media_too_large", context.exception.code)
            self.assertFalse(destination.exists())
            self.assertFalse(list(destination.parent.glob("*.part")))

    def test_html_disguised_as_jpeg_is_rejected(self) -> None:
        body = b"<!doctype html><html>upstream error</html>"
        queue = ConnectionQueue(FakeConnection(image_response(body)))
        transport = MediaTransport(resolver=public_resolver, connection_factory=queue)
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "object.jpg"
            with self.assertRaises(PipelineError) as context:
                transport.download(media_request(destination))
            self.assertEqual("media_html_response", context.exception.code)
            self.assertFalse(destination.exists())

    def test_mime_and_magic_must_agree(self) -> None:
        body = b"\x89PNG\r\n\x1a\nimage"
        queue = ConnectionQueue(FakeConnection(image_response(body)))
        transport = MediaTransport(resolver=public_resolver, connection_factory=queue)
        with tempfile.TemporaryDirectory() as temporary, self.assertRaises(PipelineError) as context:
            transport.download(media_request(Path(temporary) / "object.jpg"))
        self.assertEqual("media_mime_magic_mismatch", context.exception.code)

    def test_atomic_publish_failure_cleans_temp_and_lock(self) -> None:
        queue = ConnectionQueue(FakeConnection(image_response()))
        transport = MediaTransport(resolver=public_resolver, connection_factory=queue)
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "object.jpg"
            with patch(
                "museum_pipeline.media.transport._atomic_publish_no_overwrite",
                side_effect=OSError("simulated atomic failure"),
            ), self.assertRaises(PipelineError) as context:
                transport.download(media_request(destination))
            self.assertEqual("media_atomic_publish_failed", context.exception.code)
            self.assertFalse(destination.exists())
            self.assertFalse(list(destination.parent.glob("*.part")))
            self.assertFalse(list(destination.parent.glob("*.lock")))

    def test_evidence_bound_hash_makes_resume_idempotent_without_network(self) -> None:
        queue = ConnectionQueue(FakeConnection(image_response()))
        transport = MediaTransport(resolver=public_resolver, connection_factory=queue)
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "object.jpg"
            first = transport.download(media_request(destination))
            second = transport.download(
                media_request(
                    destination,
                    expected_sha256=first.sha256,
                    resume_evidence=acquisition_evidence(first),
                )
            )

            self.assertTrue(second.reused_existing)
            self.assertEqual(0, second.bytes_downloaded)
            self.assertEqual(first.sha256, second.sha256)
            self.assertEqual(200, second.status_code)
            self.assertEqual((PUBLIC_IP,), second.resolved_public_ips)
            self.assertEqual(PUBLIC_IP, second.connected_peer_ip)
            self.assertEqual(1, len(second.hop_evidence))
            self.assertEqual(1, len(queue.calls))

    def test_exact_hash_without_persisted_evidence_cannot_authorize_resume(self) -> None:
        queue = ConnectionQueue(FakeConnection(image_response()))
        transport = MediaTransport(resolver=public_resolver, connection_factory=queue)
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "object.jpg"
            first = transport.download(media_request(destination))
            with self.assertRaises(PipelineError) as context:
                transport.download(media_request(destination, expected_sha256=first.sha256))
        self.assertEqual("media_resume_evidence_missing", context.exception.code)
        self.assertEqual(1, len(queue.calls))

    def test_resume_rejects_evidence_whose_byte_count_does_not_bind_file(self) -> None:
        queue = ConnectionQueue(FakeConnection(image_response()))
        transport = MediaTransport(resolver=public_resolver, connection_factory=queue)
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "object.jpg"
            first = transport.download(media_request(destination))
            forged = acquisition_evidence(first, file_size=first.file_size + 1)
            with self.assertRaises(PipelineError) as context:
                transport.download(
                    media_request(
                        destination,
                        expected_sha256=first.sha256,
                        resume_evidence=forged,
                    )
                )
        self.assertEqual("media_resume_evidence_mismatch", context.exception.code)

    def test_resume_rejects_non_200_or_private_hop_evidence(self) -> None:
        queue = ConnectionQueue(FakeConnection(image_response()))
        transport = MediaTransport(resolver=public_resolver, connection_factory=queue)
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "object.jpg"
            first = transport.download(media_request(destination))
            for forged in (
                acquisition_evidence(first, status_code=304),
                acquisition_evidence(
                    first,
                    resolved_public_ips=("127.0.0.1",),
                    connected_peer_ip="127.0.0.1",
                ),
            ):
                with self.subTest(forged=forged), self.assertRaises(PipelineError) as context:
                    transport.download(
                        media_request(
                            destination,
                            expected_sha256=first.sha256,
                            resume_evidence=forged,
                        )
                    )
                self.assertEqual("media_resume_evidence_invalid", context.exception.code)

    def test_existing_destination_is_never_overwritten(self) -> None:
        queue = ConnectionQueue(FakeConnection(image_response()))
        transport = MediaTransport(resolver=public_resolver, connection_factory=queue)
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "object.jpg"
            destination.write_bytes(JPEG)
            with self.assertRaises(PipelineError) as context:
                transport.download(media_request(destination))
            self.assertEqual("media_resume_evidence_missing", context.exception.code)
            self.assertEqual([], queue.calls)

    def test_symlinked_parent_is_rejected_before_lock_temp_or_network(self) -> None:
        queue = ConnectionQueue(FakeConnection(image_response()))
        transport = MediaTransport(resolver=public_resolver, connection_factory=queue)
        with tempfile.TemporaryDirectory() as temporary:
            link = Path(temporary) / "link"
            link.mkdir()
            destination = link / "object.jpg"
            original_is_symlink = Path.is_symlink

            def simulated_is_symlink(path: Path) -> bool:
                return path == link or original_is_symlink(path)

            with (
                patch.object(Path, "is_symlink", autospec=True, side_effect=simulated_is_symlink),
                self.assertRaises(PipelineError) as context,
            ):
                transport.download(media_request(destination))
            self.assertEqual("media_destination_symlink", context.exception.code)
            self.assertFalse(destination.exists())
            self.assertFalse(list(link.glob("*.lock")))
            self.assertFalse(list(link.glob("*.part")))
            self.assertEqual([], queue.calls)

    def test_duplicate_hash_is_hardlinked_without_duplicate_content(self) -> None:
        queue = ConnectionQueue(
            FakeConnection(image_response()),
            FakeConnection(image_response()),
        )
        transport = MediaTransport(resolver=public_resolver, connection_factory=queue)
        with tempfile.TemporaryDirectory() as temporary:
            first_path = Path(temporary) / "first.jpg"
            second_path = Path(temporary) / "second.jpg"
            transport.download(media_request(first_path, url="https://media.example/first.jpg"))
            second = transport.download(media_request(second_path, url="https://media.example/second.jpg"))

            self.assertEqual(first_path, second.deduplicated_from)
            self.assertEqual(JPEG, second_path.read_bytes())
            self.assertEqual(first_path.stat().st_ino, second_path.stat().st_ino)

    def test_aic_rate_limit_has_a_hard_one_second_floor(self) -> None:
        clock = FakeClock()
        queue = ConnectionQueue(
            FakeConnection(image_response()),
            FakeConnection(image_response()),
        )
        transport = MediaTransport(
            policy=MediaTransportPolicy(source_min_interval_seconds={"aic_api": 0.1}),
            resolver=public_resolver,
            connection_factory=queue,
            sleeper=clock.sleep,
            clock=clock.now,
        )
        with tempfile.TemporaryDirectory() as temporary:
            transport.download(
                media_request(Path(temporary) / "one.jpg", source_id="source:aic_api")
            )
            transport.download(
                media_request(Path(temporary) / "two.jpg", source_id="source:aic_api")
            )
        self.assertEqual([1.0], clock.delays)

    def test_retry_after_and_retry_count_are_preserved(self) -> None:
        clock = FakeClock()
        queue = ConnectionQueue(
            FakeConnection(FakeResponse(429, {"Retry-After": "2"})),
            FakeConnection(image_response()),
        )
        transport = MediaTransport(
            resolver=public_resolver,
            connection_factory=queue,
            sleeper=clock.sleep,
            clock=clock.now,
        )
        with tempfile.TemporaryDirectory() as temporary:
            result = transport.download(media_request(Path(temporary) / "object.jpg"))
        self.assertEqual([2.0], clock.delays)
        self.assertEqual(1, result.retry_count)
        self.assertEqual(2, len(result.hop_evidence))

    def test_etag_cannot_turn_unproven_existing_bytes_into_a_304_success(self) -> None:
        response = FakeResponse(
            304,
            {"ETag": '"v1"', "Cache-Control": "max-age=30", "Set-Cookie": "ignored=yes"},
        )
        queue = ConnectionQueue(FakeConnection(response))
        transport = MediaTransport(resolver=public_resolver, connection_factory=queue)
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "object.jpg"
            destination.write_bytes(JPEG)
            with self.assertRaises(PipelineError) as context:
                transport.download(media_request(destination, etag='"v1"'))

            self.assertEqual("media_resume_evidence_missing", context.exception.code)
            self.assertEqual(JPEG, destination.read_bytes())
            self.assertEqual([], queue.calls)

    def test_transport_timeout_is_redacted_to_stable_error(self) -> None:
        queue = ConnectionQueue(FakeConnection(image_response(), connect_error=socket.timeout()))
        transport = MediaTransport(resolver=public_resolver, connection_factory=queue)
        with tempfile.TemporaryDirectory() as temporary, self.assertRaises(PipelineError) as context:
            transport.download(media_request(Path(temporary) / "object.jpg"))
        self.assertEqual("media_transport_failure", context.exception.code)

    def test_tls_context_cannot_disable_hostname_or_certificate_checks(self) -> None:
        insecure = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        insecure.check_hostname = False
        insecure.verify_mode = ssl.CERT_NONE
        with self.assertRaises(PipelineError) as context:
            MediaTransport(ssl_context=insecure)
        self.assertEqual("media_tls_verification_required", context.exception.code)

    def test_metadata_size_and_html_guards_use_no_files(self) -> None:
        queue = ConnectionQueue(
            FakeConnection(FakeResponse(200, {"Content-Type": "application/json"}, b"<html>x</html>"))
        )
        transport = MediaTransport(resolver=public_resolver, connection_factory=queue)
        with self.assertRaises(PipelineError) as context:
            transport.fetch_metadata(
                MetadataFetchRequest(
                    url="https://media.example/object.json",
                    source_id="source:met_open_access",
                    trusted_hosts=frozenset({"media.example"}),
                )
            )
        self.assertEqual("media_html_response", context.exception.code)


if __name__ == "__main__":
    unittest.main()
