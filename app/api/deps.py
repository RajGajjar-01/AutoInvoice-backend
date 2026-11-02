from collections.abc import Generator
from typing import Annotated
from urllib.parse import urlsplit

from fastapi import Cookie, Depends, HTTPException, Query, Request, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from pydantic import ValidationError
from sqlmodel import Session

from app.core import security
from app.core.config import settings
from app.core.db import engine
from app.models import TokenPayload, User

reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/login/access-token",
    auto_error=False,
)

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def get_db() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


def _request_origin(request: Request) -> str | None:
    origin = request.headers.get("origin")
    if origin and origin != "null":
        return origin.rstrip("/")
    referer = request.headers.get("referer")
    if referer:
        parts = urlsplit(referer)
        if parts.scheme and parts.netloc:
            return f"{parts.scheme}://{parts.netloc}"
    return None


def enforce_csrf_origin(request: Request) -> None:
    """Block cross-site requests that ride on the browser's auth cookies.

    Cookie-authenticated state-changing requests must come from a trusted origin
    (the configured frontend / CORS origins). Bearer-token requests are not
    affected because browsers never attach Authorization headers automatically.
    """
    if request.method in SAFE_METHODS:
        return
    origin = _request_origin(request)
    if origin is None or origin not in settings.csrf_trusted_origins:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cross-site request blocked",
        )


def get_token(
    request: Request,
    access_token: Annotated[str | None, Cookie()] = None,
    authorization: Annotated[str | None, Depends(reusable_oauth2)] = None,
) -> str:
    # An explicit Authorization header always wins over an ambient cookie, so a
    # client never silently acts as whichever user last logged in on that browser.
    if authorization:
        return authorization
    if access_token:
        enforce_csrf_origin(request)
        return access_token
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )


SessionDep = Annotated[Session, Depends(get_db)]
TokenDep = Annotated[str, Depends(get_token)]


def credentials_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Could not validate credentials",
    )


def user_from_token(
    session: Session, token: str, expected_type: security.TokenType
) -> User:
    """Resolve a session token to an active user, enforcing type and revocation."""
    try:
        payload = security.decode_token(token, expected_type)
        token_data = TokenPayload(**payload)
    except (InvalidTokenError, ValidationError):
        raise credentials_exception()
    user = session.get(User, token_data.sub)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if token_data.ver != user.token_version:
        # Revoked by logout, password change/reset or an administrator.
        raise credentials_exception()
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return user


def get_current_user(session: SessionDep, token: TokenDep) -> User:
    return user_from_token(session, token, security.TOKEN_TYPE_ACCESS)


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_current_active_superuser(current_user: CurrentUser) -> User:
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=403, detail="The user doesn't have enough privileges"
        )
    return current_user


SkipDep = Annotated[int, Query(ge=0)]
LimitDep = Annotated[int, Query(ge=1, le=settings.MAX_PAGE_SIZE)]
