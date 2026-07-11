import asyncio
import logging
from collections.abc import Coroutine
from typing import Any

import sentry_sdk
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
from app.core.rate_limit import limiter
from app.core.redis import redis_client
from app.exceptions import (
    AuthError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ValidationError,
)
from app.middleware.security_headers import SecurityHeadersMiddleware

logger = logging.getLogger(__name__)

if settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.ENVIRONMENT,
        send_default_pii=True,
        traces_sample_rate=1.0 if settings.ENVIRONMENT != "production" else 0.2,
    )
    logger.info("Sentry initialized for environment: %s", settings.ENVIRONMENT)


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
def rate_limit_exceeded_handler(
    request: Request, exc: RateLimitExceeded
) -> Response:
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


@app.exception_handler(AuthError)
async def auth_exception_handler(request: Request, exc: AuthError) -> JSONResponse:
    logger.warning(f"Auth error: {exc.code} - {exc.message}")

    status_map = {
        "user_already_exists": 400,
        "unauthorized": 403,
        "mfa_required": 403,
        "rate_limit_exceeded": 429,
    }
    status_code = status_map.get(exc.code, 401)

    return JSONResponse(
        status_code=status_code,
        content={
            "detail": exc.message,
            "code": exc.code,
            **exc.details,
        },
    )


@app.exception_handler(NotFoundError)
async def not_found_exception_handler(request: Request, exc: NotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": exc.message})


@app.exception_handler(ForbiddenError)
async def forbidden_exception_handler(request: Request, exc: ForbiddenError) -> JSONResponse:
    return JSONResponse(status_code=403, content={"detail": exc.message})


@app.exception_handler(ConflictError)
async def conflict_exception_handler(request: Request, exc: ConflictError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": exc.message})


@app.exception_handler(ValidationError)
async def validation_exception_handler(request: Request, exc: ValidationError) -> JSONResponse:
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
        logger.warning("Health check: %s unreachable: %s", name, exc)
        return name, "unreachable"


@app.get("/health")
@limiter.exempt  # type: ignore[untyped-decorator]
async def health(request: Request) -> JSONResponse:
    _ = request
    """Health check endpoint for Railway and Docker - verifies DB and Redis connectivity."""
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


# ⚠️  TEMPORARY — remove after verifying Sentry is working
@app.get("/sentry-debug")
async def sentry_debug() -> dict[str, str]:
    """Intentionally triggers an error to verify Sentry is capturing events."""
    _ = 1 / 0
    return {"status": "unreachable"}
