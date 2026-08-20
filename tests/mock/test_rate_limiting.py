from collections.abc import Generator
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from limits.storage import storage_from_string
from slowapi.wrappers import LimitGroup

from app.core.rate_limit import get_client_ip, limiter
from app.main import app


@pytest.fixture(autouse=True)
def _patch_limiter() -> Generator[None, None, None]:
    """Replace Redis-backed storage with in-memory storage and low test limits.

    Patches the shared limiter object in-place so that both SlowAPIMiddleware
    (via app.state.limiter) and per-route @limiter.limit() decorators (which
    captured the same object at decoration time) use the test configuration.
    The _exempt_routes set is preserved.
    """
    original_storage = limiter._storage
    original_rate_limiter_storage = limiter._limiter.storage
    original_default_limits = limiter._default_limits

    mem_storage = storage_from_string("memory://")
    limiter._storage = mem_storage
    limiter._limiter.storage = mem_storage  # type: ignore[assignment]
    limiter._default_limits = [
        LimitGroup(
            "5/minute", limiter._key_func, None, False, None, None, None, 1, False
        ),
    ]

    yield

    limiter._storage = original_storage
    limiter._limiter.storage = original_rate_limiter_storage
    limiter._default_limits = original_default_limits


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as c:
        yield c


class TestRateLimitingExempt:
    """Routes marked with @limiter.exempt should never be rate limited."""

    def test_health_root_not_429(self, client: TestClient) -> None:
        for _ in range(30):
            resp = client.get("/health")
            assert resp.status_code != 429, "Exempt path /health returned 429"

    def test_health_check_not_429(self, client: TestClient) -> None:
        for _ in range(30):
            resp = client.get("/api/v1/utils/health-check/")
            assert resp.status_code != 429, "Exempt path returned 429"


class TestRateLimitingGlobal:
    """Global default_limits apply to all non-exempt routes."""

    def test_global_limit_blocks_after_exceeding(self, client: TestClient) -> None:
        for _ in range(100):
            resp = client.get("/api/v1/openapi.json")
            if resp.status_code == 429:
                return
        pytest.fail("Did not receive a 429 within 100 requests")

    def test_exempt_route_not_blocked_by_other_route_limit(
        self, client: TestClient
    ) -> None:
        for _ in range(10):
            client.get("/api/v1/openapi.json")
        resp = client.get("/health")
        assert resp.status_code != 429, "Exempt route should not be blocked"

    def test_global_limit_429_response_format(self, client: TestClient) -> None:
        for _ in range(100):
            resp = client.get("/api/v1/openapi.json")
            if resp.status_code == 429:
                body = resp.json()
                assert "detail" in body
                assert body["code"] == "rate_limit_exceeded"
                return
        pytest.fail("Did not receive a 429 response")


class TestRateLimiting429Response:
    """The 429 response format meets expectations."""

    def test_429_includes_retry_after_header(self, client: TestClient) -> None:
        for _ in range(100):
            resp = client.get("/api/v1/openapi.json")
            if resp.status_code == 429:
                assert "Retry-After" in resp.headers
                assert resp.headers["Retry-After"].isdigit()
                return
        pytest.fail("Did not receive a 429 response")


class TestGetClientIP:
    """The custom key function handles X-Forwarded-For correctly."""

    def test_forwarded_for_ip_is_used(self) -> None:
        request = MagicMock()
        request.headers = {"X-Forwarded-For": "203.0.113.1, 10.0.0.1"}
        request.client.host = "10.0.0.1"
        result = get_client_ip(request)
        assert result == "203.0.113.1"

    def test_fallback_to_remote_address(self) -> None:
        request = MagicMock()
        request.headers = {}
        request.client.host = "198.51.100.1"
        result = get_client_ip(request)
        assert result == "198.51.100.1"
