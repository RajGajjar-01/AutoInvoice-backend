import asyncio
from collections.abc import Coroutine
from typing import Any

import sentry_sdk
import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from fastapi.routing import APIRoute
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy import text
from starlette.middleware.cors import CORSMiddleware

from app.api.main import api_router
from app.core.config import settings
from app.core.db import async_engine
from app.core.logging import setup_logging
from app.core.rate_limit import limiter
from app.core.redis import redis_client
from app.exceptions import (
    ConflictError,
    ForbiddenError,
    GoogleOnlyAccountError,
    NotFoundError,
    RateLimitError,
    ValidationError,
)
from app.middleware.request_context import RequestContextMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware

setup_logging()

logger = structlog.get_logger(__name__)

SENSITIVE_KEYS = {
    "password",
    "hashed_password",
    "token",
    "access_token",
    "refresh_token",
    "secret",
    "key",
    "api_key",
    "authorization",
    "cookie",
    "bank_account",
    "bank_ifsc",
    "pan",
    "upi_id",
    "smtp_password",
    "openwa_api_key",
    "openwa_session_id",
    "google_access_token",
    "google_refresh_token",
}


def _scrub_sentry_event(
    event: dict[str, Any], hint: dict[str, Any]
) -> dict[str, Any] | None:
    _ = hint

    def _scrub_dict(d: dict[str, Any]) -> None:
        for k, v in list(d.items()):
            if any(sens in k.lower() for sens in SENSITIVE_KEYS):
                d[k] = "[REDACTED]"
            elif isinstance(v, dict):
                _scrub_dict(v)
            elif isinstance(v, list):
                for item in v:
                    if isinstance(item, dict):
                        _scrub_dict(item)

    if "request" in event and isinstance(event["request"], dict):
        req = event["request"]
        if "headers" in req and isinstance(req["headers"], dict):
            for h in list(req["headers"].keys()):
                if h.lower() in ("authorization", "cookie", "x-api-key", "set-cookie"):
                    req["headers"][h] = "[REDACTED]"
        if "data" in req and isinstance(req["data"], dict):
            _scrub_dict(req["data"])
        if "cookies" in req and isinstance(req["cookies"], dict):
            for c in list(req["cookies"].keys()):
                req["cookies"][c] = "[REDACTED]"

    if "extra" in event and isinstance(event["extra"], dict):
        _scrub_dict(event["extra"])

    return event


if settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.ENVIRONMENT,
        send_default_pii=False,
        before_send=_scrub_sentry_event,
        traces_sample_rate=1.0 if settings.ENVIRONMENT != "production" else 0.2,
    )
    logger.info("Sentry initialized", environment=settings.ENVIRONMENT)


def custom_generate_unique_id(route: APIRoute) -> str:
    if route.tags:
        return f"{route.tags[0]}-{route.name}"
    return route.name or "endpoint"


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    generate_unique_id_function=custom_generate_unique_id,
)


app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)


@app.exception_handler(RateLimitExceeded)
def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> Response:
    response = JSONResponse(
        status_code=429,
        content={
            "detail": str(exc.detail),
            "code": "rate_limit_exceeded",
        },
    )
    return app.state.limiter._inject_headers(  # type: ignore[no-any-return]
        response, request.state.view_rate_limit
    )


@app.exception_handler(RateLimitError)
async def rate_limit_error_handler(
    request: Request, exc: RateLimitError
) -> JSONResponse:
    logger.warning("Rate limit error", message=exc.message)
    return JSONResponse(
        status_code=429,
        content={"detail": exc.message, "code": exc.code},
    )


@app.exception_handler(NotFoundError)
async def not_found_exception_handler(
    request: Request, exc: NotFoundError
) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": exc.message})


@app.exception_handler(ForbiddenError)
async def forbidden_exception_handler(
    request: Request, exc: ForbiddenError
) -> JSONResponse:
    return JSONResponse(status_code=403, content={"detail": exc.message})


@app.exception_handler(ConflictError)
async def conflict_exception_handler(
    request: Request, exc: ConflictError
) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": exc.message})


@app.exception_handler(GoogleOnlyAccountError)
async def google_only_account_exception_handler(
    request: Request, exc: GoogleOnlyAccountError
) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": exc.message})


@app.exception_handler(ValidationError)
async def validation_exception_handler(
    request: Request, exc: ValidationError
) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": exc.message})


if settings.all_cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.all_cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=[
            "Content-Type",
            "Authorization",
        ],
        max_age=86400,
    )

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestContextMiddleware)

app.include_router(api_router, prefix=settings.API_V1_STR)


async def _check_postgres() -> None:
    async with async_engine.connect() as conn:
        await conn.execute(text("SELECT 1"))


async def _check_redis() -> None:
    await redis_client.ping()


async def _probe(name: str, check: Coroutine[Any, Any, None]) -> tuple[str, str]:
    try:
        await asyncio.wait_for(check, timeout=3)
        return name, "ok"
    except Exception as exc:
        logger.warning("Health check probe failed", check=name, error=str(exc))
        return name, "unreachable"


@app.get("/health")
@limiter.exempt  # type: ignore[untyped-decorator]
async def health(request: Request) -> JSONResponse:
    """Verify DB and Redis connectivity."""
    _ = request
    results = await asyncio.gather(
        _probe("postgres", _check_postgres()),
        _probe("redis", _check_redis()),
    )
    checks = dict(results)
    healthy = all(status == "ok" for status in checks.values())
    return JSONResponse(
        status_code=200 if healthy else 503,
        content={"status": "healthy" if healthy else "unhealthy", "checks": checks},
    )
