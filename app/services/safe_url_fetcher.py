"""A WeasyPrint URL fetcher that cannot be used for SSRF.

Invoice HTML contains user-controlled URLs (the company logo). WeasyPrint's
default fetcher would open any of them from inside our network: plain HTTP,
``file://``, cloud metadata (169.254.169.254), localhost, private ranges.

This fetcher allows only:
- ``data:`` URIs (inline images, no network), and
- ``https://`` URLs whose host resolves only to public addresses, without
  redirects, with a short timeout, a size cap and an ``image/*`` type.

Any refused or failed fetch raises; WeasyPrint catches the error and renders
the document without that resource.
"""

from __future__ import annotations

import ipaddress
import socket
from io import BytesIO
from typing import Any
from urllib.parse import urlsplit

from weasyprint.urls import URLFetcher, URLFetcherResponse

FETCH_TIMEOUT_SECONDS = 5
MAX_RESOURCE_BYTES = 2 * 1024 * 1024
_ALLOWED_SCHEMES = ("https", "data")


class UnsafeURLError(ValueError):
    pass


def _is_public(address: str) -> bool:
    ip = ipaddress.ip_address(address)
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return ip.is_global and not ip.is_multicast


def ensure_public_https_url(url: str) -> None:
    """Raise UnsafeURLError unless ``url`` is https to a public host."""
    parts = urlsplit(url)
    if parts.scheme.lower() != "https":
        raise UnsafeURLError(f"Only https URLs are allowed: {url}")
    host = parts.hostname
    if not host:
        raise UnsafeURLError(f"URL has no host: {url}")
    try:
        port = parts.port or 443
    except ValueError as exc:
        raise UnsafeURLError(f"Invalid port in URL: {url}") from exc
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise UnsafeURLError(f"Cannot resolve host: {host}") from exc
    addresses = {info[4][0] for info in infos}
    if not addresses or not all(_is_public(str(a)) for a in addresses):
        raise UnsafeURLError(f"Host resolves to a non-public address: {host}")


class SafeURLFetcher(URLFetcher):  # type: ignore[misc]
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(
            timeout=FETCH_TIMEOUT_SECONDS,
            allowed_protocols=_ALLOWED_SCHEMES,
            allow_redirects=False,
            fail_on_errors=False,
            **kwargs,
        )

    def fetch(self, url: str, headers: dict[str, str] | None = None) -> Any:
        scheme = urlsplit(url).scheme.lower()
        if scheme not in _ALLOWED_SCHEMES:
            raise UnsafeURLError(f"URI uses disallowed protocol: {url}")
        if scheme == "https":
            ensure_public_https_url(url)

        response = super().fetch(url, headers)
        try:
            content_type = response.headers.get_content_type()
            if not content_type.startswith("image/"):
                raise UnsafeURLError(f"Not an image ({content_type}): {url}")
            body = response.read(MAX_RESOURCE_BYTES + 1)
            if len(body) > MAX_RESOURCE_BYTES:
                raise UnsafeURLError(f"Resource larger than 2 MB: {url}")
        finally:
            response.close()
        return URLFetcherResponse(
            response.url, BytesIO(body), response.headers, response.status
        )


def make_safe_url_fetcher() -> SafeURLFetcher:
    """Return a new fetcher. URLFetcher keeps per-request state, so do not
    share one instance between concurrent renders."""
    return SafeURLFetcher()
