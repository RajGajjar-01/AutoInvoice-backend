import logging

try:
    import sentry_sdk
except ModuleNotFoundError:
    sentry_sdk = None

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware

from app.api.main import api_router
from app.core.config import settings
from app.exceptions import AuthError

logger = logging.getLogger(__name__)


def custom_generate_unique_id(route: APIRoute) -> str:
    return f"{route.tags[0]}-{route.name}"


if sentry_sdk and settings.SENTRY_DSN and settings.ENVIRONMENT != "local":
    sentry_sdk.init(dsn=str(settings.SENTRY_DSN), enable_tracing=True)

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    generate_unique_id_function=custom_generate_unique_id,
)


@app.exception_handler(AuthError)
async def auth_exception_handler(request: Request, exc: AuthError) -> JSONResponse:
    """Handle all authentication errors consistently."""
    logger.warning(f"Auth error: {exc.code} - {exc.message}")

    status_code = 401
    if exc.code in ["invalid_credentials", "user_not_found"]:
        status_code = 401
    elif exc.code in ["user_already_exists"]:
        status_code = 400
    elif exc.code in ["token_expired", "session_expired"]:
        status_code = 401
    elif exc.code in ["unauthorized", "mfa_required"]:
        status_code = 403
    elif exc.code in ["rate_limit_exceeded"]:
        status_code = 429

    return JSONResponse(
        status_code=status_code,
        content={
            "detail": exc.message,
            "code": exc.code,
            **exc.details,
        },
    )


class CSRFMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method in {"GET", "HEAD", "OPTIONS"}:
            return await call_next(request)

        path = request.url.path
        exempt_paths = {
            f"{settings.API_V1_STR}/auth/login",
            f"{settings.API_V1_STR}/auth/signup",
            f"{settings.API_V1_STR}/auth/refresh",
            f"{settings.API_V1_STR}/auth/logout",
            f"{settings.API_V1_STR}/auth/forgot-password",
            f"{settings.API_V1_STR}/auth/update-password",
            f"{settings.API_V1_STR}/auth/resend-verification",
            f"{settings.API_V1_STR}/auth/oauth/{path.split('/')[-1]}"
            if "/auth/oauth/" in path
            else None,
        }
        exempt_paths.discard(None)

        if path in exempt_paths or path.startswith(f"{settings.API_V1_STR}/auth/oauth"):
            return await call_next(request)

        access_token = request.cookies.get("access_token")
        if not access_token:
            return await call_next(request)

        csrf_cookie = request.cookies.get("csrf_token")
        csrf_header = request.headers.get("X-CSRF-Token")

        if not csrf_cookie or not csrf_header or csrf_cookie != csrf_header:
            return JSONResponse(
                status_code=403,
                content={"detail": "CSRF validation failed"},
            )

        return await call_next(request)


app.add_middleware(CSRFMiddleware)

if settings.all_cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.all_cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=[
            "Content-Type",
            "X-Requested-With",
            "X-CSRF-Token",
            "Authorization",
        ],
    )

app.include_router(api_router, prefix=settings.API_V1_STR)
