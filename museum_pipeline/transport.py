from __future__ import annotations

import email.utils
import ipaddress
import random
import socket
import ssl
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable
from urllib.parse import urljoin, urlsplit

from museum_pipeline.adapters.base import RequestSpec, ResponseContract, SourceAdapter
from museum_pipeline.errors import PipelineError


@dataclass(frozen=True)
class TransportPolicy:
    connect_timeout_seconds: float = 5.0
    read_timeout_seconds: float = 20.0
    total_timeout_seconds: float = 30.0
    max_response_bytes: int = 5 * 1024 * 1024
    max_redirects: int = 3
    max_retries: int = 3
    base_backoff_seconds: float = 0.5
    jitter_seconds: float = 0.25


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, file_pointer, code, message, headers, new_url):  # noqa: ANN001
        return None


class HttpTransport:
    """Small injectable HTTPS transport with bounded retries and redirects."""

    def __init__(
        self,
        *,
        policy: TransportPolicy | None = None,
        sleeper: Callable[[float], None] = time.sleep,
        random_value: Callable[[], float] = random.random,
        resolver: Callable[..., list[tuple]] = socket.getaddrinfo,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.policy = policy or TransportPolicy()
        self.sleeper = sleeper
        self.random_value = random_value
        self.resolver = resolver
        self.clock = clock
        context = ssl.create_default_context()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPSHandler(context=context),
            _NoRedirect(),
        )

    def fetch(self, adapter: SourceAdapter, request: RequestSpec) -> ResponseContract:
        adapter.validate_request(request)
        started = self.clock()
        retry_count = 0
        current = request
        redirects: list[str] = []
        while True:
            self._assert_public_host(current.url)
            remaining = self.policy.total_timeout_seconds - (self.clock() - started)
            if remaining <= 0:
                raise PipelineError("transport_total_timeout", "Request exceeded the total timeout", exit_code=5)
            # urllib exposes one socket timeout for both phases. Use the stricter
            # bound so neither the declared connect nor read ceiling is exceeded.
            timeout = min(self.policy.connect_timeout_seconds, self.policy.read_timeout_seconds, remaining)
            response = self._one_request(current, timeout)
            if response.status_code in {301, 302, 303, 307, 308}:
                if len(redirects) >= self.policy.max_redirects:
                    raise PipelineError("redirect_limit_exceeded", "Redirect chain exceeded the configured limit", exit_code=5)
                location = response.headers.get("location")
                if not location:
                    raise PipelineError("redirect_location_missing", "Redirect response has no Location header", exit_code=5)
                redirected_url = urljoin(current.url, location)
                redirected = RequestSpec(current.method, redirected_url, current.headers, current.query_profile, current.credential_alias)
                adapter.validate_request(redirected)
                redirects.append(redirected_url)
                current = redirected
                continue
            if response.status_code == 429 or 500 <= response.status_code <= 599:
                if retry_count >= self.policy.max_retries:
                    return ResponseContract(
                        response.status_code, response.headers, response.body, response.final_url,
                        tuple(redirects), retry_count,
                    )
                delay = self._retry_delay(response, retry_count)
                remaining = self.policy.total_timeout_seconds - (self.clock() - started)
                if delay >= remaining:
                    raise PipelineError("transport_total_timeout", "Retry would exceed the total timeout", exit_code=5)
                self.sleeper(delay)
                retry_count += 1
                continue
            return ResponseContract(
                response.status_code, response.headers, response.body, response.final_url,
                tuple(redirects), retry_count,
            )

    def _one_request(self, request: RequestSpec, timeout: float) -> ResponseContract:
        if any(name.lower() == "cookie" for name in request.headers):
            raise PipelineError("cookie_persistence_forbidden", "Adapters may not send Cookie headers")
        wire_request = urllib.request.Request(request.url, method=request.method, headers=request.headers)
        try:
            with self.opener.open(wire_request, timeout=timeout) as response:
                return self._read_response(response.status, response.headers, response, response.geturl())
        except urllib.error.HTTPError as error:
            return self._read_response(error.code, error.headers, error, error.geturl())
        except (urllib.error.URLError, TimeoutError, socket.timeout, ssl.SSLError) as error:
            raise PipelineError("transport_failure", "HTTPS request failed without exposing local details", exit_code=5) from error

    def _read_response(self, status: int, headers, stream, final_url: str) -> ResponseContract:  # noqa: ANN001
        normalized_headers = {name.lower(): value for name, value in headers.items()}
        content_length = normalized_headers.get("content-length")
        if content_length and content_length.isdigit() and int(content_length) > self.policy.max_response_bytes:
            raise PipelineError("response_too_large", "Response Content-Length exceeds the configured maximum", exit_code=5)
        body = stream.read(self.policy.max_response_bytes + 1)
        if len(body) > self.policy.max_response_bytes:
            raise PipelineError("response_too_large", "Response body exceeds the configured maximum", exit_code=5)
        return ResponseContract(status, normalized_headers, body, final_url)

    def _assert_public_host(self, url: str) -> None:
        parsed = urlsplit(url)
        host = parsed.hostname
        if parsed.scheme != "https" or host is None:
            raise PipelineError("endpoint_not_https", "Transport accepts only allowlisted HTTPS endpoints")
        try:
            addresses = self.resolver(host, parsed.port or 443, type=socket.SOCK_STREAM)
        except OSError as error:
            raise PipelineError("dns_resolution_failed", "Approved host could not be resolved", exit_code=5) from error
        if not addresses:
            raise PipelineError("dns_resolution_failed", "Approved host resolved to no addresses", exit_code=5)
        for address in addresses:
            ip = ipaddress.ip_address(address[4][0].split("%", 1)[0])
            if not ip.is_global or any((ip.is_loopback, ip.is_link_local, ip.is_multicast, ip.is_reserved, ip.is_unspecified)):
                raise PipelineError("private_network_blocked", "Approved host resolved to a non-public network address", exit_code=5)

    def _retry_delay(self, response: ResponseContract, retry_count: int) -> float:
        if response.status_code == 429:
            parsed = _parse_retry_after(response.headers.get("retry-after"))
            if parsed is not None:
                return min(parsed, 30.0)
        exponential = self.policy.base_backoff_seconds * (2 ** retry_count)
        return exponential + self.policy.jitter_seconds * self.random_value()


def _parse_retry_after(value: str | None) -> float | None:
    if not value:
        return None
    if value.isdigit():
        return max(0.0, float(value))
    try:
        parsed = email.utils.parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return max(0.0, (parsed - datetime.now(timezone.utc)).total_seconds())


class FakeTransport:
    def __init__(self, responses: list[ResponseContract]) -> None:
        self.responses = list(responses)
        self.requests: list[RequestSpec] = []

    def fetch(self, adapter: SourceAdapter, request: RequestSpec) -> ResponseContract:
        adapter.validate_request(request)
        self.requests.append(request)
        if not self.responses:
            raise PipelineError("fake_transport_empty", "Fake transport has no remaining response")
        return self.responses.pop(0)
