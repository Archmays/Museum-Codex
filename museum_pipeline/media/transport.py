from __future__ import annotations

import email.utils
import hashlib
import http.client
import ipaddress
import json
import os
import socket
import ssl
import tempfile
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping, Sequence
from urllib.parse import urljoin, urlsplit

from museum_pipeline.errors import PipelineError


_REDIRECT_STATUSES = {301, 302, 303, 307, 308}
_SUPPORTED_MIME_TYPES = frozenset(
    {"image/avif", "image/gif", "image/jpeg", "image/png", "image/tiff", "image/webp"}
)
_SAFE_RESPONSE_HEADERS = frozenset(
    {
        "cache-control",
        "content-disposition",
        "content-encoding",
        "content-length",
        "content-type",
        "etag",
        "last-modified",
    }
)
_USED_RESPONSE_HEADERS = _SAFE_RESPONSE_HEADERS | {"location", "retry-after", "transfer-encoding"}


@dataclass(frozen=True)
class MediaTransportPolicy:
    connect_timeout_seconds: float = 10.0
    read_timeout_seconds: float = 30.0
    total_timeout_seconds: float = 120.0
    max_bytes: int = 64 * 1024 * 1024
    max_metadata_bytes: int = 2 * 1024 * 1024
    max_redirects: int = 4
    max_retries: int = 2
    retry_backoff_seconds: float = 1.0
    chunk_size: int = 64 * 1024
    lock_timeout_seconds: float = 10.0
    lock_poll_seconds: float = 0.1
    source_min_interval_seconds: Mapping[str, float] = field(
        default_factory=lambda: {"aic_api": 1.0, "source:aic_api": 1.0}
    )


@dataclass(frozen=True)
class MediaAcquisitionEvidence:
    """Persisted evidence required before existing media bytes may be reused."""

    request_url: str
    final_url: str
    redirect_chain: tuple[str, ...]
    status_code: int
    response_headers: Mapping[str, str]
    resolved_public_ips: tuple[str, ...]
    connected_peer_ip: str
    sha256: str
    file_size: int


@dataclass(frozen=True)
class MediaDownloadRequest:
    url: str
    source_id: str
    trusted_hosts: frozenset[str]
    destination: Path
    etag: str | None = None
    expected_sha256: str | None = None
    resume_evidence: MediaAcquisitionEvidence | None = None
    dedupe_candidates: tuple[Path, ...] = ()


@dataclass(frozen=True)
class MetadataFetchRequest:
    url: str
    source_id: str
    trusted_hosts: frozenset[str]
    etag: str | None = None


@dataclass(frozen=True)
class NetworkHopEvidence:
    url: str
    host: str
    resolved_public_ips: tuple[str, ...]
    connected_peer_ip: str
    status_code: int


@dataclass(frozen=True)
class MediaDownloadResult:
    status_code: int | None
    final_url: str
    redirect_chain: tuple[str, ...]
    destination: Path
    content_type: str
    etag: str | None
    sha256: str
    file_size: int
    bytes_downloaded: int
    retry_count: int
    response_headers: Mapping[str, str]
    resolved_public_ips: tuple[str, ...]
    connected_peer_ip: str | None
    hop_evidence: tuple[NetworkHopEvidence, ...]
    reused_existing: bool = False
    not_modified: bool = False
    deduplicated_from: Path | None = None


@dataclass(frozen=True)
class MetadataFetchResult:
    status_code: int
    final_url: str
    redirect_chain: tuple[str, ...]
    response_headers: Mapping[str, str]
    body: bytes
    etag: str | None
    retry_count: int
    not_modified: bool
    resolved_public_ips: tuple[str, ...]
    connected_peer_ip: str
    hop_evidence: tuple[NetworkHopEvidence, ...]


@dataclass(frozen=True)
class _Endpoint:
    url: str
    host: str
    port: int
    request_target: str
    resolved_ips: tuple[str, ...]


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    """HTTPSConnection that connects only to already-vetted literal IPs."""

    def __init__(
        self,
        host: str,
        port: int,
        resolved_ips: Sequence[str],
        timeout: float,
        context: ssl.SSLContext,
    ) -> None:
        super().__init__(host, port=port, timeout=timeout, context=context)
        self._resolved_ips = tuple(resolved_ips)
        self.peer_ip: str | None = None

    def connect(self) -> None:
        if self._tunnel_host is not None:
            raise OSError("HTTP tunnels are disabled")
        last_error: OSError | ssl.SSLError | None = None
        for address in self._resolved_ips:
            raw_socket: socket.socket | None = None
            try:
                raw_socket = socket.create_connection(
                    (address, self.port), self.timeout, self.source_address
                )
                tls_socket = self._context.wrap_socket(raw_socket, server_hostname=self.host)
                self.sock = tls_socket
                self.peer_ip = _canonical_ip(tls_socket.getpeername()[0])
                return
            except (OSError, ssl.SSLError) as error:
                last_error = error
                if raw_socket is not None:
                    raw_socket.close()
        if last_error is None:
            raise OSError("No validated address was available")
        raise last_error


class MediaTransport:
    """Direct, proxy-free HTTPS downloader for governed image acquisition."""

    def __init__(
        self,
        *,
        policy: MediaTransportPolicy | None = None,
        resolver: Callable[..., Sequence[Any]] = socket.getaddrinfo,
        connection_factory: Callable[[str, int, Sequence[str], float, ssl.SSLContext], Any]
        | None = None,
        ssl_context: ssl.SSLContext | None = None,
        sleeper: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.policy = policy or MediaTransportPolicy()
        _validate_policy(self.policy)
        self.resolver = resolver
        self.sleeper = sleeper
        self.clock = clock
        self.ssl_context = ssl_context or ssl.create_default_context()
        if self.ssl_context.verify_mode != ssl.CERT_REQUIRED or not self.ssl_context.check_hostname:
            raise PipelineError(
                "media_tls_verification_required",
                "Media TLS must verify certificates and hostnames",
                exit_code=5,
            )
        self.connection_factory = connection_factory or _PinnedHTTPSConnection
        self._state_lock = threading.Lock()
        self._last_request_started: dict[str, float] = {}
        self._hash_index: dict[str, Path] = {}

    def fetch_metadata(self, request: MetadataFetchRequest) -> MetadataFetchResult:
        trusted_hosts = _normalize_trusted_hosts(request.trusted_hosts)
        if not request.source_id.strip():
            raise PipelineError("media_source_missing", "A source ID is required", exit_code=5)
        started = self.clock()
        current_url = request.url
        visited = {current_url}
        redirects: list[str] = []
        hops: list[NetworkHopEvidence] = []
        retry_count = 0

        while True:
            endpoint = self._validate_endpoint(current_url, trusted_hosts)
            self._throttle(request.source_id, started)
            connection, response, peer_ip = self._open_response(
                endpoint, request.etag, started, accept="application/json"
            )
            headers = _response_headers(response)
            status = int(response.status)
            hop = NetworkHopEvidence(
                url=current_url,
                host=endpoint.host,
                resolved_public_ips=endpoint.resolved_ips,
                connected_peer_ip=peer_ip,
                status_code=status,
            )
            hops.append(hop)
            try:
                if status in _REDIRECT_STATUSES:
                    if len(redirects) >= self.policy.max_redirects:
                        raise PipelineError(
                            "media_redirect_limit",
                            "Media redirect chain exceeded its configured limit",
                            exit_code=5,
                        )
                    location = headers.get("location")
                    if not location:
                        raise PipelineError(
                            "media_redirect_location_missing",
                            "Media redirect omitted its Location header",
                            exit_code=5,
                        )
                    redirected_url = urljoin(current_url, location)
                    self._validate_endpoint(redirected_url, trusted_hosts)
                    if redirected_url in visited:
                        raise PipelineError("media_redirect_loop", "Media redirect loop detected", exit_code=5)
                    redirects.append(redirected_url)
                    visited.add(redirected_url)
                    current_url = redirected_url
                    continue
                if status == 429 or 500 <= status <= 599:
                    if retry_count >= self.policy.max_retries:
                        raise PipelineError(
                            "media_http_status",
                            "Metadata server remained unavailable after bounded retries",
                            exit_code=5,
                        )
                    delay = _retry_delay(headers.get("retry-after"), retry_count, self.policy)
                    self._sleep_with_deadline(delay, started)
                    retry_count += 1
                    continue
                safe_headers = _safe_response_headers(headers)
                if status == 304:
                    return MetadataFetchResult(
                        status_code=304,
                        final_url=current_url,
                        redirect_chain=tuple(redirects),
                        response_headers=safe_headers,
                        body=b"",
                        etag=headers.get("etag", request.etag),
                        retry_count=retry_count,
                        not_modified=True,
                        resolved_public_ips=endpoint.resolved_ips,
                        connected_peer_ip=peer_ip,
                        hop_evidence=tuple(hops),
                    )
                if status != 200:
                    raise PipelineError(
                        "media_http_status",
                        f"Metadata server returned HTTP {status}",
                        exit_code=5,
                    )
                body = self._read_metadata_body(response, headers, started)
                return MetadataFetchResult(
                    status_code=200,
                    final_url=current_url,
                    redirect_chain=tuple(redirects),
                    response_headers=safe_headers,
                    body=body,
                    etag=headers.get("etag"),
                    retry_count=retry_count,
                    not_modified=False,
                    resolved_public_ips=endpoint.resolved_ips,
                    connected_peer_ip=peer_ip,
                    hop_evidence=tuple(hops),
                )
            finally:
                try:
                    response.close()
                finally:
                    connection.close()

    def download(self, request: MediaDownloadRequest) -> MediaDownloadResult:
        destination = Path(request.destination)
        expected_hash = _normalize_expected_hash(request.expected_sha256)
        trusted_hosts = _normalize_trusted_hosts(request.trusted_hosts)
        if not request.source_id.strip():
            raise PipelineError("media_source_missing", "A source ID is required", exit_code=5)
        _reject_symlink_components(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.is_symlink():
            raise PipelineError("media_destination_symlink", "Media destination cannot be a symlink", exit_code=5)

        with self._destination_lock(destination):
            existing = self._resume_existing(request, destination, expected_hash, trusted_hosts)
            if existing is not None:
                return existing
            if request.resume_evidence is not None:
                raise PipelineError(
                    "media_resume_file_missing",
                    "Persisted acquisition evidence cannot be reused without its exact local media file",
                    exit_code=5,
                )
            return self._download_locked(request, destination, expected_hash, trusted_hosts)

    def _resume_existing(
        self,
        request: MediaDownloadRequest,
        destination: Path,
        expected_hash: str | None,
        trusted_hosts: frozenset[str],
    ) -> MediaDownloadResult | None:
        if not destination.exists():
            return None
        if not destination.is_file() or destination.is_symlink():
            raise PipelineError("media_destination_invalid", "Media destination is not a regular file", exit_code=5)
        evidence = request.resume_evidence
        if expected_hash is None or evidence is None:
            raise PipelineError(
                "media_resume_evidence_missing",
                "Existing media requires persisted acquisition evidence and an evidence-bound SHA-256",
                exit_code=5,
            )
        evidence_hash = _normalize_expected_hash(evidence.sha256)
        if evidence_hash != expected_hash:
            raise PipelineError(
                "media_resume_evidence_mismatch",
                "Persisted acquisition evidence does not bind the expected SHA-256",
                exit_code=5,
            )
        if evidence.status_code != 200:
            raise PipelineError(
                "media_resume_evidence_invalid",
                "Persisted acquisition evidence must record the original HTTP 200 response",
                exit_code=5,
            )
        if evidence.request_url != request.url:
            raise PipelineError(
                "media_resume_evidence_mismatch",
                "Persisted acquisition evidence belongs to a different request URL",
                exit_code=5,
            )
        request_host, _request_port, _request_target = _validate_trusted_https_url(
            evidence.request_url, trusted_hosts
        )
        final_host, _final_port, _final_target = _validate_trusted_https_url(
            evidence.final_url, trusted_hosts
        )
        if len(evidence.redirect_chain) > self.policy.max_redirects:
            raise PipelineError(
                "media_resume_evidence_invalid",
                "Persisted acquisition evidence exceeds the redirect limit",
                exit_code=5,
            )
        for redirect_url in evidence.redirect_chain:
            _validate_trusted_https_url(redirect_url, trusted_hosts)
        if evidence.redirect_chain:
            if evidence.redirect_chain[-1] != evidence.final_url:
                raise PipelineError(
                    "media_resume_evidence_mismatch",
                    "Persisted redirect evidence does not terminate at the recorded final URL",
                    exit_code=5,
                )
        elif evidence.final_url != evidence.request_url or final_host != request_host:
            raise PipelineError(
                "media_resume_evidence_mismatch",
                "Persisted acquisition evidence changed endpoints without redirect evidence",
                exit_code=5,
            )
        resolved_public_ips = _validate_persisted_public_ips(evidence.resolved_public_ips)
        try:
            connected_peer_ip = _canonical_ip(evidence.connected_peer_ip)
        except ValueError as error:
            raise PipelineError(
                "media_resume_evidence_invalid",
                "Persisted acquisition evidence has an invalid peer address",
                exit_code=5,
            ) from error
        if connected_peer_ip not in resolved_public_ips:
            raise PipelineError(
                "media_resume_evidence_mismatch",
                "Persisted peer evidence is not in the recorded public DNS set",
                exit_code=5,
            )
        if not isinstance(evidence.file_size, int) or isinstance(evidence.file_size, bool):
            raise PipelineError(
                "media_resume_evidence_invalid",
                "Persisted acquisition evidence has an invalid byte count",
                exit_code=5,
            )
        if evidence.file_size <= 0 or evidence.file_size > self.policy.max_bytes:
            raise PipelineError(
                "media_resume_evidence_invalid",
                "Persisted acquisition evidence has an invalid byte count",
                exit_code=5,
            )
        response_headers = _validate_persisted_response_headers(evidence.response_headers)
        declared_type = _declared_content_type(response_headers)
        content_length = _content_length(response_headers.get("content-length"))
        if content_length is not None and content_length != evidence.file_size:
            raise PipelineError(
                "media_resume_evidence_mismatch",
                "Persisted Content-Length does not bind the recorded byte count",
                exit_code=5,
            )
        digest, size, content_type = _inspect_existing_file(destination)
        if digest != expected_hash or digest != evidence_hash:
            raise PipelineError(
                "media_existing_hash_mismatch",
                "Existing media does not match the expected SHA-256",
                exit_code=5,
            )
        if size != evidence.file_size:
            raise PipelineError(
                "media_resume_evidence_mismatch",
                "Existing media does not match the persisted byte count",
                exit_code=5,
            )
        if content_type != declared_type:
            raise PipelineError(
                "media_resume_evidence_mismatch",
                "Existing media does not match the persisted response MIME type",
                exit_code=5,
            )
        final_hop = NetworkHopEvidence(
            url=evidence.final_url,
            host=final_host,
            resolved_public_ips=resolved_public_ips,
            connected_peer_ip=connected_peer_ip,
            status_code=evidence.status_code,
        )
        self._register_hash(digest, destination)
        return MediaDownloadResult(
            status_code=evidence.status_code,
            final_url=evidence.final_url,
            redirect_chain=tuple(evidence.redirect_chain),
            destination=destination,
            content_type=content_type,
            etag=response_headers.get("etag", request.etag),
            sha256=digest,
            file_size=size,
            bytes_downloaded=0,
            retry_count=0,
            response_headers=response_headers,
            resolved_public_ips=resolved_public_ips,
            connected_peer_ip=connected_peer_ip,
            hop_evidence=(final_hop,),
            reused_existing=True,
        )

    def _download_locked(
        self,
        request: MediaDownloadRequest,
        destination: Path,
        expected_hash: str | None,
        trusted_hosts: frozenset[str],
    ) -> MediaDownloadResult:
        started = self.clock()
        current_url = request.url
        visited = {current_url}
        redirects: list[str] = []
        hops: list[NetworkHopEvidence] = []
        retry_count = 0

        while True:
            endpoint = self._validate_endpoint(current_url, trusted_hosts)
            self._throttle(request.source_id, started)
            connection, response, peer_ip = self._open_response(
                endpoint,
                request.etag,
                started,
                accept=", ".join(sorted(_SUPPORTED_MIME_TYPES)),
            )
            headers = _response_headers(response)
            status = int(response.status)
            hops.append(
                NetworkHopEvidence(
                    url=current_url,
                    host=endpoint.host,
                    resolved_public_ips=endpoint.resolved_ips,
                    connected_peer_ip=peer_ip,
                    status_code=status,
                )
            )
            try:
                if status in _REDIRECT_STATUSES:
                    if len(redirects) >= self.policy.max_redirects:
                        raise PipelineError(
                            "media_redirect_limit",
                            "Media redirect chain exceeded its configured limit",
                            exit_code=5,
                        )
                    location = headers.get("location")
                    if not location:
                        raise PipelineError(
                            "media_redirect_location_missing",
                            "Media redirect omitted its Location header",
                            exit_code=5,
                        )
                    redirected_url = urljoin(current_url, location)
                    self._validate_endpoint(redirected_url, trusted_hosts)
                    if redirected_url in visited:
                        raise PipelineError("media_redirect_loop", "Media redirect loop detected", exit_code=5)
                    redirects.append(redirected_url)
                    visited.add(redirected_url)
                    current_url = redirected_url
                    continue

                if status == 429 or 500 <= status <= 599:
                    if retry_count >= self.policy.max_retries:
                        raise PipelineError(
                            "media_http_status",
                            "Media server remained unavailable after bounded retries",
                            exit_code=5,
                        )
                    delay = _retry_delay(headers.get("retry-after"), retry_count, self.policy)
                    self._sleep_with_deadline(delay, started)
                    retry_count += 1
                    continue

                if status == 304:
                    return self._not_modified_result(
                        request,
                        destination,
                        current_url,
                        tuple(redirects),
                        headers,
                        retry_count,
                        endpoint.resolved_ips,
                        peer_ip,
                        tuple(hops),
                    )
                if status != 200:
                    raise PipelineError(
                        "media_http_status",
                        f"Media server returned HTTP {status}",
                        exit_code=5,
                    )
                return self._stream_to_destination(
                    request=request,
                    response=response,
                    headers=headers,
                    destination=destination,
                    final_url=current_url,
                    redirect_chain=tuple(redirects),
                    retry_count=retry_count,
                    expected_hash=expected_hash,
                    started=started,
                    resolved_public_ips=endpoint.resolved_ips,
                    connected_peer_ip=peer_ip,
                    hop_evidence=tuple(hops),
                )
            finally:
                try:
                    response.close()
                finally:
                    connection.close()

    def _validate_endpoint(self, url: str, trusted_hosts: frozenset[str]) -> _Endpoint:
        host, port, target = _validate_trusted_https_url(url, trusted_hosts)
        resolved_ips = self._resolve_public_ips(host, port)
        return _Endpoint(url=url, host=host, port=port, request_target=target, resolved_ips=resolved_ips)

    def _resolve_public_ips(self, host: str, port: int) -> tuple[str, ...]:
        try:
            answers = self.resolver(host, port, type=socket.SOCK_STREAM, proto=socket.IPPROTO_TCP)
        except OSError as error:
            raise PipelineError("media_dns_failed", "Media host could not be resolved", exit_code=5) from error
        addresses: list[str] = []
        for answer in answers:
            raw = answer if isinstance(answer, str) else answer[4][0]
            try:
                canonical = _canonical_ip(raw)
                address = ipaddress.ip_address(canonical)
            except (IndexError, TypeError, ValueError) as error:
                raise PipelineError(
                    "media_dns_invalid", "Media DNS returned an invalid address", exit_code=5
                ) from error
            if not _is_public_address(address):
                raise PipelineError(
                    "media_private_network_blocked",
                    "Media DNS resolved to a non-public address",
                    exit_code=5,
                )
            if canonical not in addresses:
                addresses.append(canonical)
        if not addresses:
            raise PipelineError("media_dns_failed", "Media host resolved to no addresses", exit_code=5)
        return tuple(addresses)

    def _open_response(
        self, endpoint: _Endpoint, etag: str | None, started: float, *, accept: str
    ) -> tuple[Any, Any, str]:
        remaining = self.policy.total_timeout_seconds - (self.clock() - started)
        if remaining <= 0:
            raise PipelineError("media_total_timeout", "Media transfer exceeded its deadline", exit_code=5)
        timeout = min(self.policy.connect_timeout_seconds, remaining)
        connection = self.connection_factory(
            endpoint.host, endpoint.port, endpoint.resolved_ips, timeout, self.ssl_context
        )
        try:
            connection.connect()
            peer_ip = _connection_peer_ip(connection)
            if peer_ip not in endpoint.resolved_ips:
                raise PipelineError(
                    "media_peer_mismatch",
                    "Connected media peer was not in the validated DNS set",
                    exit_code=5,
                )
            sock = getattr(connection, "sock", None)
            if sock is not None:
                sock.settimeout(min(self.policy.read_timeout_seconds, remaining))
            headers = {
                "Accept": accept,
                "Accept-Encoding": "identity",
                "Connection": "close",
                "User-Agent": "Museum-Codex/1.0 governed-media-acquisition",
            }
            if etag is not None:
                if "\r" in etag or "\n" in etag:
                    raise PipelineError("media_etag_invalid", "Media ETag contains invalid bytes", exit_code=5)
                headers["If-None-Match"] = etag
            connection.request("GET", endpoint.request_target, body=None, headers=headers)
            return connection, connection.getresponse(), peer_ip
        except PipelineError:
            connection.close()
            raise
        except (OSError, TimeoutError, socket.timeout, ssl.SSLError, http.client.HTTPException) as error:
            connection.close()
            raise PipelineError(
                "media_transport_failure",
                "Direct HTTPS media request failed",
                exit_code=5,
            ) from error

    def _stream_to_destination(
        self,
        *,
        request: MediaDownloadRequest,
        response: Any,
        headers: Mapping[str, str],
        destination: Path,
        final_url: str,
        redirect_chain: tuple[str, ...],
        retry_count: int,
        expected_hash: str | None,
        started: float,
        resolved_public_ips: tuple[str, ...],
        connected_peer_ip: str,
        hop_evidence: tuple[NetworkHopEvidence, ...],
    ) -> MediaDownloadResult:
        declared_type = _declared_content_type(headers)
        encoding = headers.get("content-encoding", "identity").strip().lower()
        if encoding not in {"", "identity"}:
            raise PipelineError(
                "media_content_encoding_forbidden",
                "Encoded media responses are not accepted",
                exit_code=5,
            )
        content_length = _content_length(headers.get("content-length"))
        if content_length is not None and content_length > self.policy.max_bytes:
            raise PipelineError("media_too_large", "Media exceeds the maximum byte limit", exit_code=5)
        if destination.exists() or destination.is_symlink():
            raise PipelineError("media_destination_exists", "Existing media is never overwritten", exit_code=5)

        fd, raw_temp = tempfile.mkstemp(
            dir=destination.parent,
            prefix=f".{destination.name[:80]}.",
            suffix=".part",
        )
        temp_path = Path(raw_temp)
        digest = hashlib.sha256()
        prefix = bytearray()
        total = 0
        try:
            with os.fdopen(fd, "wb") as stream:
                while True:
                    if self.clock() - started >= self.policy.total_timeout_seconds:
                        raise PipelineError(
                            "media_total_timeout", "Media transfer exceeded its deadline", exit_code=5
                        )
                    try:
                        chunk = response.read(self.policy.chunk_size)
                    except (OSError, TimeoutError, socket.timeout, http.client.HTTPException) as error:
                        raise PipelineError(
                            "media_transport_failure",
                            "Media response stream failed",
                            exit_code=5,
                        ) from error
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > self.policy.max_bytes:
                        raise PipelineError("media_too_large", "Media exceeds the maximum byte limit", exit_code=5)
                    if len(prefix) < 512:
                        prefix.extend(chunk[: 512 - len(prefix)])
                    digest.update(chunk)
                    stream.write(chunk)
                stream.flush()
                os.fsync(stream.fileno())
            if content_length is not None and total != content_length:
                raise PipelineError(
                    "media_content_length_mismatch",
                    "Media body length did not match Content-Length",
                    exit_code=5,
                )
            if total == 0:
                raise PipelineError("media_empty_body", "Media response was empty", exit_code=5)
            content_type = _validate_magic_and_mime(bytes(prefix), declared_type)
            sha256 = "sha256:" + digest.hexdigest()
            if expected_hash is not None and sha256 != expected_hash:
                raise PipelineError(
                    "media_hash_mismatch", "Downloaded media failed its expected SHA-256", exit_code=5
                )

            duplicate = self._find_duplicate(sha256, request.dedupe_candidates, destination)
            if duplicate is not None:
                try:
                    os.link(duplicate, destination)
                    _fsync_directory(destination.parent)
                except FileExistsError as error:
                    raise PipelineError(
                        "media_destination_exists", "Existing media is never overwritten", exit_code=5
                    ) from error
                except OSError:
                    duplicate = None
                else:
                    temp_path.unlink(missing_ok=True)
            if duplicate is None:
                try:
                    _atomic_publish_no_overwrite(temp_path, destination)
                    _fsync_directory(destination.parent)
                except FileExistsError as error:
                    raise PipelineError(
                        "media_destination_exists", "Existing media is never overwritten", exit_code=5
                    ) from error
                except OSError as error:
                    raise PipelineError(
                        "media_atomic_publish_failed",
                        "Media could not be published atomically",
                        exit_code=5,
                    ) from error

            self._register_hash(sha256, destination)
            return MediaDownloadResult(
                status_code=200,
                final_url=final_url,
                redirect_chain=redirect_chain,
                destination=destination,
                content_type=content_type,
                etag=headers.get("etag"),
                sha256=sha256,
                file_size=total,
                bytes_downloaded=total,
                retry_count=retry_count,
                response_headers=_safe_response_headers(headers),
                resolved_public_ips=resolved_public_ips,
                connected_peer_ip=connected_peer_ip,
                hop_evidence=hop_evidence,
                deduplicated_from=duplicate,
            )
        finally:
            temp_path.unlink(missing_ok=True)

    def _not_modified_result(
        self,
        request: MediaDownloadRequest,
        destination: Path,
        final_url: str,
        redirect_chain: tuple[str, ...],
        headers: Mapping[str, str],
        retry_count: int,
        resolved_public_ips: tuple[str, ...],
        connected_peer_ip: str,
        hop_evidence: tuple[NetworkHopEvidence, ...],
    ) -> MediaDownloadResult:
        if not destination.is_file() or destination.is_symlink():
            raise PipelineError(
                "media_304_without_local",
                "HTTP 304 requires an existing regular media file",
                exit_code=5,
            )
        digest, size, content_type = _inspect_existing_file(destination)
        self._register_hash(digest, destination)
        return MediaDownloadResult(
            status_code=304,
            final_url=final_url,
            redirect_chain=redirect_chain,
            destination=destination,
            content_type=content_type,
            etag=headers.get("etag", request.etag),
            sha256=digest,
            file_size=size,
            bytes_downloaded=0,
            retry_count=retry_count,
            response_headers=_safe_response_headers(headers),
            resolved_public_ips=resolved_public_ips,
            connected_peer_ip=connected_peer_ip,
            hop_evidence=hop_evidence,
            not_modified=True,
        )

    def _read_metadata_body(
        self, response: Any, headers: Mapping[str, str], started: float
    ) -> bytes:
        content_type = headers.get("content-type", "").split(";", 1)[0].strip().lower()
        if content_type == "text/html":
            raise PipelineError("media_html_response", "Metadata endpoint returned HTML", exit_code=5)
        if content_type != "application/json" and not content_type.endswith("+json"):
            raise PipelineError(
                "media_metadata_mime_invalid",
                "Metadata response must use a JSON MIME type",
                exit_code=5,
            )
        encoding = headers.get("content-encoding", "identity").strip().lower()
        if encoding not in {"", "identity"}:
            raise PipelineError(
                "media_content_encoding_forbidden",
                "Encoded metadata responses are not accepted",
                exit_code=5,
            )
        content_length = _content_length(headers.get("content-length"))
        if content_length is not None and content_length > self.policy.max_metadata_bytes:
            raise PipelineError("media_metadata_too_large", "Metadata exceeds its byte limit", exit_code=5)
        chunks: list[bytes] = []
        total = 0
        prefix = bytearray()
        while True:
            if self.clock() - started >= self.policy.total_timeout_seconds:
                raise PipelineError("media_total_timeout", "Metadata transfer exceeded its deadline", exit_code=5)
            try:
                chunk = response.read(
                    min(self.policy.chunk_size, self.policy.max_metadata_bytes + 1 - total)
                )
            except (OSError, TimeoutError, socket.timeout, http.client.HTTPException) as error:
                raise PipelineError(
                    "media_transport_failure",
                    "Metadata response stream failed",
                    exit_code=5,
                ) from error
            if not chunk:
                break
            total += len(chunk)
            if total > self.policy.max_metadata_bytes:
                raise PipelineError("media_metadata_too_large", "Metadata exceeds its byte limit", exit_code=5)
            if len(prefix) < 512:
                prefix.extend(chunk[: 512 - len(prefix)])
            chunks.append(chunk)
        body = b"".join(chunks)
        if content_length is not None and total != content_length:
            raise PipelineError(
                "media_content_length_mismatch",
                "Metadata body length did not match Content-Length",
                exit_code=5,
            )
        stripped = bytes(prefix).lstrip(b"\xef\xbb\xbf\x00\t\r\n ").lower()
        if stripped.startswith((b"<!doctype html", b"<html", b"<head", b"<body")):
            raise PipelineError("media_html_response", "Metadata endpoint returned HTML bytes", exit_code=5)
        if not body:
            raise PipelineError("media_metadata_empty", "Metadata response was empty", exit_code=5)
        try:
            json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise PipelineError("media_metadata_invalid", "Metadata response is not valid UTF-8 JSON", exit_code=5) from error
        return body

    def _throttle(self, source_id: str, started: float) -> None:
        interval = _source_interval(source_id, self.policy.source_min_interval_seconds)
        key = source_id.strip().lower()
        with self._state_lock:
            now = self.clock()
            previous = self._last_request_started.get(key)
            if previous is not None:
                delay = interval - (now - previous)
                if delay > 0:
                    self._sleep_with_deadline(delay, started)
                    now = self.clock()
            self._last_request_started[key] = now

    def _sleep_with_deadline(self, delay: float, started: float) -> None:
        remaining = self.policy.total_timeout_seconds - (self.clock() - started)
        if delay >= remaining:
            raise PipelineError("media_total_timeout", "Media retry exceeded its deadline", exit_code=5)
        self.sleeper(max(0.0, delay))

    def _find_duplicate(
        self, sha256: str, candidates: Sequence[Path], destination: Path
    ) -> Path | None:
        with self._state_lock:
            indexed = self._hash_index.get(sha256)
        ordered = ([indexed] if indexed is not None else []) + [Path(item) for item in candidates]
        for candidate in ordered:
            if candidate == destination or not candidate.is_file() or candidate.is_symlink():
                continue
            digest, _size, _content_type = _inspect_existing_file(candidate)
            if digest == sha256:
                return candidate
        return None

    def _register_hash(self, sha256: str, path: Path) -> None:
        with self._state_lock:
            self._hash_index.setdefault(sha256, path)

    @contextmanager
    def _destination_lock(self, destination: Path) -> Iterator[None]:
        lock_path = destination.with_name(f".{destination.name}.lock")
        waited = 0.0
        descriptor: int | None = None
        while descriptor is None:
            try:
                descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            except FileExistsError as error:
                if waited >= self.policy.lock_timeout_seconds:
                    raise PipelineError(
                        "media_lock_timeout", "Media destination lock is already held", exit_code=5
                    ) from error
                delay = min(
                    self.policy.lock_poll_seconds,
                    self.policy.lock_timeout_seconds - waited,
                )
                self.sleeper(delay)
                waited += delay
        try:
            os.write(descriptor, b"museum-media-transport\n")
            os.fsync(descriptor)
            yield
        finally:
            os.close(descriptor)
            lock_path.unlink(missing_ok=True)


SafeMediaTransport = MediaTransport


def _validate_policy(policy: MediaTransportPolicy) -> None:
    positive = (
        policy.connect_timeout_seconds,
        policy.read_timeout_seconds,
        policy.total_timeout_seconds,
        policy.max_bytes,
        policy.max_metadata_bytes,
        policy.chunk_size,
        policy.lock_poll_seconds,
    )
    if any(value <= 0 for value in positive):
        raise ValueError("Media transport limits must be positive")
    if policy.max_redirects < 0 or policy.max_retries < 0 or policy.lock_timeout_seconds < 0:
        raise ValueError("Media transport counts cannot be negative")
    if any(value < 0 for value in policy.source_min_interval_seconds.values()):
        raise ValueError("Source rate limits cannot be negative")


def _normalize_trusted_hosts(hosts: Sequence[str]) -> frozenset[str]:
    if not hosts:
        raise PipelineError("media_trusted_hosts_missing", "Trusted media hosts are required", exit_code=5)
    normalized: set[str] = set()
    for host in hosts:
        if "*" in host or ":" in host or "/" in host:
            raise PipelineError("media_trusted_host_invalid", "Trusted media host is invalid", exit_code=5)
        normalized.add(_normalize_host(host))
    return frozenset(normalized)


def _validate_trusted_https_url(
    url: str, trusted_hosts: frozenset[str]
) -> tuple[str, int, str]:
    if not isinstance(url, str):
        raise PipelineError("media_url_invalid", "Media URL is invalid", exit_code=5)
    parsed = urlsplit(url)
    if parsed.scheme.lower() != "https" or parsed.hostname is None:
        raise PipelineError("media_https_required", "Media URLs must use HTTPS", exit_code=5)
    if parsed.fragment:
        raise PipelineError("media_url_fragment_forbidden", "Media URLs cannot contain fragments", exit_code=5)
    if any(ord(character) < 32 or ord(character) == 127 for character in url):
        raise PipelineError("media_url_invalid", "Media URL contains control bytes", exit_code=5)
    if parsed.username is not None or parsed.password is not None:
        raise PipelineError("media_url_credentials_forbidden", "Media URLs cannot contain credentials", exit_code=5)
    try:
        host = _normalize_host(parsed.hostname)
    except UnicodeError as error:
        raise PipelineError("media_host_invalid", "Media host is invalid", exit_code=5) from error
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise PipelineError(
            "media_ip_literal_forbidden", "Media endpoints must use registered hostnames", exit_code=5
        )
    if host not in trusted_hosts:
        raise PipelineError("media_host_not_trusted", "Media host is not registered", exit_code=5)
    try:
        port = parsed.port or 443
    except ValueError as error:
        raise PipelineError("media_port_invalid", "Media URL port is invalid", exit_code=5) from error
    if port != 443:
        raise PipelineError("media_port_not_allowed", "Media HTTPS is restricted to port 443", exit_code=5)
    target = parsed.path or "/"
    if parsed.query:
        target += "?" + parsed.query
    return host, port, target


def _normalize_host(host: str) -> str:
    value = host.rstrip(".").encode("idna").decode("ascii").lower()
    if not value or value.startswith(".") or ".." in value:
        raise UnicodeError("invalid host")
    return value


def _canonical_ip(raw: str) -> str:
    address = ipaddress.ip_address(str(raw).split("%", 1)[0])
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None:
        address = address.ipv4_mapped
    return str(address)


def _is_public_address(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return address.is_global and not any(
        (
            address.is_loopback,
            address.is_link_local,
            address.is_multicast,
            address.is_private,
            address.is_reserved,
            address.is_unspecified,
        )
    )


def _validate_persisted_public_ips(values: Sequence[str]) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not values:
        raise PipelineError(
            "media_resume_evidence_invalid",
            "Persisted acquisition evidence requires public DNS addresses",
            exit_code=5,
        )
    addresses: list[str] = []
    for raw in values:
        try:
            canonical = _canonical_ip(raw)
            address = ipaddress.ip_address(canonical)
        except (TypeError, ValueError) as error:
            raise PipelineError(
                "media_resume_evidence_invalid",
                "Persisted acquisition evidence has an invalid DNS address",
                exit_code=5,
            ) from error
        if not _is_public_address(address):
            raise PipelineError(
                "media_resume_evidence_invalid",
                "Persisted acquisition evidence contains a non-public DNS address",
                exit_code=5,
            )
        if canonical not in addresses:
            addresses.append(canonical)
    return tuple(addresses)


def _connection_peer_ip(connection: Any) -> str:
    peer = getattr(connection, "peer_ip", None)
    if peer is None:
        sock = getattr(connection, "sock", None)
        if sock is None:
            raise PipelineError("media_peer_unavailable", "Media peer address is unavailable", exit_code=5)
        peer = sock.getpeername()[0]
    try:
        return _canonical_ip(peer)
    except ValueError as error:
        raise PipelineError("media_peer_invalid", "Media peer address is invalid", exit_code=5) from error


def _response_headers(response: Any) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for raw_name, raw_value in response.getheaders():
        name = str(raw_name).lower()
        if name not in _USED_RESPONSE_HEADERS:
            continue
        value = str(raw_value).strip()
        if "\r" in name or "\n" in name or "\r" in value or "\n" in value:
            raise PipelineError(
                "media_response_header_invalid",
                "Media response contained an invalid header",
                exit_code=5,
            )
        if name in normalized and normalized[name] != value:
            raise PipelineError(
                "media_response_header_conflict",
                "Media response contained conflicting duplicate headers",
                exit_code=5,
            )
        normalized[name] = value
    return normalized


def _safe_response_headers(headers: Mapping[str, str]) -> dict[str, str]:
    return {name: value for name, value in headers.items() if name in _SAFE_RESPONSE_HEADERS}


def _validate_persisted_response_headers(headers: Mapping[str, str]) -> dict[str, str]:
    if not isinstance(headers, Mapping):
        raise PipelineError(
            "media_resume_evidence_invalid",
            "Persisted acquisition evidence has invalid response headers",
            exit_code=5,
        )
    normalized: dict[str, str] = {}
    for raw_name, raw_value in headers.items():
        if not isinstance(raw_name, str) or not isinstance(raw_value, str):
            raise PipelineError(
                "media_resume_evidence_invalid",
                "Persisted acquisition evidence has invalid response headers",
                exit_code=5,
            )
        name = raw_name.lower()
        value = raw_value.strip()
        if name not in _SAFE_RESPONSE_HEADERS or "\r" in name or "\n" in name or "\r" in value or "\n" in value:
            raise PipelineError(
                "media_resume_evidence_invalid",
                "Persisted acquisition evidence has unsafe response headers",
                exit_code=5,
            )
        if name in normalized and normalized[name] != value:
            raise PipelineError(
                "media_resume_evidence_invalid",
                "Persisted acquisition evidence has conflicting response headers",
                exit_code=5,
            )
        normalized[name] = value
    encoding = normalized.get("content-encoding", "identity").lower()
    if encoding not in {"", "identity"}:
        raise PipelineError(
            "media_resume_evidence_invalid",
            "Persisted acquisition evidence used a forbidden content encoding",
            exit_code=5,
        )
    return normalized


def _declared_content_type(headers: Mapping[str, str]) -> str:
    raw = headers.get("content-type", "")
    value = raw.split(";", 1)[0].strip().lower()
    if value == "image/jpg":
        value = "image/jpeg"
    if value == "text/html":
        raise PipelineError("media_html_response", "Media endpoint returned HTML", exit_code=5)
    if value not in _SUPPORTED_MIME_TYPES:
        raise PipelineError("media_mime_not_allowed", "Media MIME type is not allowed", exit_code=5)
    return value


def _content_length(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        result = int(value)
    except ValueError as error:
        raise PipelineError("media_content_length_invalid", "Media Content-Length is invalid", exit_code=5) from error
    if result < 0:
        raise PipelineError("media_content_length_invalid", "Media Content-Length is invalid", exit_code=5)
    return result


def _validate_magic_and_mime(prefix: bytes, declared_type: str) -> str:
    stripped = prefix.lstrip(b"\xef\xbb\xbf\x00\t\r\n ").lower()
    if stripped.startswith((b"<!doctype html", b"<html", b"<head", b"<body")):
        raise PipelineError("media_html_response", "Media endpoint returned HTML bytes", exit_code=5)
    detected = _detect_image_mime(prefix)
    if detected is None:
        raise PipelineError("media_magic_invalid", "Media bytes do not match a supported image", exit_code=5)
    if detected != declared_type:
        raise PipelineError("media_mime_magic_mismatch", "Media MIME and magic bytes disagree", exit_code=5)
    return detected


def _detect_image_mime(prefix: bytes) -> str | None:
    if prefix.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if prefix.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if prefix.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if prefix.startswith((b"II*\x00", b"MM\x00*")):
        return "image/tiff"
    if len(prefix) >= 12 and prefix[:4] == b"RIFF" and prefix[8:12] == b"WEBP":
        return "image/webp"
    if len(prefix) >= 12 and prefix[4:8] == b"ftyp" and prefix[8:12] in {b"avif", b"avis"}:
        return "image/avif"
    return None


def _normalize_expected_hash(value: str | None) -> str | None:
    if value is None:
        return None
    lowered = value.lower()
    if lowered.startswith("sha256:"):
        lowered = lowered[7:]
    if len(lowered) != 64 or any(character not in "0123456789abcdef" for character in lowered):
        raise PipelineError("media_expected_hash_invalid", "Expected SHA-256 is invalid", exit_code=5)
    return "sha256:" + lowered


def _reject_symlink_components(path: Path) -> None:
    for component in (path, *path.parents):
        is_junction = getattr(component, "is_junction", lambda: False)
        if component.exists() and (component.is_symlink() or is_junction()):
            raise PipelineError(
                "media_destination_symlink",
                "Media destination cannot contain a symlink or junction component",
                exit_code=5,
            )


def _inspect_existing_file(path: Path) -> tuple[str, int, str]:
    digest = hashlib.sha256()
    prefix = b""
    size = 0
    with path.open("rb") as stream:
        while True:
            chunk = stream.read(64 * 1024)
            if not chunk:
                break
            if len(prefix) < 512:
                prefix += chunk[: 512 - len(prefix)]
            size += len(chunk)
            digest.update(chunk)
    content_type = _detect_image_mime(prefix)
    if size == 0 or content_type is None:
        raise PipelineError("media_existing_invalid", "Existing media is not a supported image", exit_code=5)
    return "sha256:" + digest.hexdigest(), size, content_type


def _source_interval(source_id: str, configured: Mapping[str, float]) -> float:
    key = source_id.strip().lower()
    short_key = key.removeprefix("source:")
    interval = float(configured.get(key, configured.get(short_key, 0.0)))
    if short_key in {"aic", "aic_api"}:
        interval = max(1.0, interval)
    return interval


def _retry_delay(value: str | None, retry_count: int, policy: MediaTransportPolicy) -> float:
    parsed = _parse_retry_after(value)
    if parsed is not None:
        return min(parsed, 60.0)
    return policy.retry_backoff_seconds * (2**retry_count)


def _parse_retry_after(value: str | None) -> float | None:
    if not value:
        return None
    if value.isdigit():
        return float(value)
    try:
        parsed = email.utils.parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return max(0.0, (parsed - datetime.now(timezone.utc)).total_seconds())


def _atomic_publish_no_overwrite(temp_path: Path, destination: Path) -> None:
    """Atomically publish without replacement on Windows and POSIX."""

    if os.name == "nt":
        os.rename(temp_path, destination)  # Windows rename fails if destination exists.
        return
    # POSIX rename replaces an existing path. link+unlink provides an atomic,
    # no-replace publication while keeping the temporary file on one filesystem.
    os.link(temp_path, destination)
    temp_path.unlink()


def _fsync_directory(path: Path) -> None:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        os.close(descriptor)
