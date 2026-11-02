"""Small in-process sliding-window rate limiter for authentication endpoints.

This protects login, signup, password recovery and password reset from online
guessing and enumeration (OWASP A07). State is kept per process: when running
several workers or replicas, each enforces its own window, so put a shared
limiter (reverse proxy, API gateway, or a Redis-backed limiter) in front of the
service for a global limit.
"""

import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status

from app.core.config import settings


class SlidingWindowLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def _prune(self, key: str, window: float, now: float) -> deque[float]:
        q = self._hits[key]
        while q and q[0] <= now - window:
            q.popleft()
        return q

    def is_limited(self, key: str, limit: int, window: float) -> bool:
        now = time.monotonic()
        with self._lock:
            q = self._prune(key, window, now)
            if not q:
                self._hits.pop(key, None)
            return len(q) >= limit

    def hit(self, key: str, window: float) -> None:
        now = time.monotonic()
        with self._lock:
            self._prune(key, window, now).append(now)
            # Opportunistic cleanup so the table cannot grow without bound.
            if len(self._hits) > 100_000:
                for k in [k for k, v in self._hits.items() if not v][:10_000]:
                    self._hits.pop(k, None)

    def reset(self, key: str | None = None) -> None:
        with self._lock:
            if key is None:
                self._hits.clear()
            else:
                self._hits.pop(key, None)


limiter = SlidingWindowLimiter()


def client_ip(request: Request) -> str:
    # request.client honours uvicorn's --proxy-headers / --forwarded-allow-ips, so
    # X-Forwarded-For is only trusted when it comes from a configured proxy.
    return request.client.host if request.client else "unknown"


def _too_many() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Too many requests. Please try again later.",
        headers={"Retry-After": str(settings.RATE_LIMIT_WINDOW_SECONDS)},
    )


def enforce(key: str, limit: int) -> None:
    """Count one request against ``key`` and raise 429 once ``limit`` is reached."""
    if not settings.RATE_LIMIT_ENABLED:
        return
    window = settings.RATE_LIMIT_WINDOW_SECONDS
    if limiter.is_limited(key, limit, window):
        raise _too_many()
    limiter.hit(key, window)


def check_login_allowed(ip: str, email: str) -> None:
    """Reject before verifying the password if this IP or IP+account is locked."""
    if not settings.RATE_LIMIT_ENABLED:
        return
    window = settings.RATE_LIMIT_WINDOW_SECONDS
    # Per-IP cap on all login attempts.
    enforce(f"login-ip:{ip}", settings.LOGIN_RATE_LIMIT_PER_IP)
    # Per IP+account cap on failed attempts. Keyed by IP as well so an attacker
    # cannot lock a victim out of their account from elsewhere.
    if limiter.is_limited(
        f"login-fail:{ip}:{email.lower()}", settings.LOGIN_MAX_FAILED_ATTEMPTS, window
    ):
        raise _too_many()


def record_login_failure(ip: str, email: str) -> None:
    if settings.RATE_LIMIT_ENABLED:
        limiter.hit(
            f"login-fail:{ip}:{email.lower()}", settings.RATE_LIMIT_WINDOW_SECONDS
        )


def clear_login_failures(ip: str, email: str) -> None:
    limiter.reset(f"login-fail:{ip}:{email.lower()}")
