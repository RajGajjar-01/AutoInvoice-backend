import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from starlette.middleware.cors import CORSMiddleware

from app.api.main import api_router
from app.core.config import settings
from app.exceptions import AuthError

logger = logging.getLogger(__name__)


def custom_generate_unique_id(route: APIRoute) -> str:
    if route.tags:
        return f"{route.tags[0]}-{route.name}"
    return route.name or "endpoint"


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

app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/health")
async def health() -> dict:
    """Health check endpoint for Railway and Docker."""
    return {"status": "healthy"}
