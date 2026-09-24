from fastapi import Response

from app.core import security
from app.core.config import settings
from app.models import User

ACCESS_TOKEN_MAX_AGE = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
REFRESH_TOKEN_MAX_AGE = settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
COOKIE_SECURE = settings.ENVIRONMENT != "local"
COOKIE_SAMESITE = "none" if settings.ENVIRONMENT != "local" else "lax"


def set_auth_cookies(response: Response, user: User) -> None:
    access_token = security.create_access_token(
        subject=user.id,
        email=user.email,
        is_superuser=user.is_superuser,
        is_verified=user.is_verified,
    )
    refresh_token = security.create_refresh_token(subject=user.id)
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        max_age=ACCESS_TOKEN_MAX_AGE,
        path="/",
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        max_age=REFRESH_TOKEN_MAX_AGE,
        path="/",
    )


def clear_auth_cookies(response: Response) -> None:
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")
