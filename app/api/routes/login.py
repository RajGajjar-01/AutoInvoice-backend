import logging
from datetime import timedelta
from typing import Annotated, Any

from fastapi import (
    APIRouter,
    Cookie,
    Depends,
    HTTPException,
    Request,
    Response,
    status,
)
from fastapi.responses import HTMLResponse
from fastapi.security import OAuth2PasswordRequestForm

from app import crud
from app.api.deps import (
    CurrentUser,
    SessionDep,
    enforce_csrf_origin,
    get_current_active_superuser,
    user_from_token,
)
from app.core import rate_limit, security
from app.core.config import settings
from app.models import Message, NewPassword, Token, User, UserPublic
from app.utils import (
    generate_password_reset_token,
    generate_reset_password_email,
    send_email,
    verify_password_reset_token,
)

logger = logging.getLogger("app.security")

router = APIRouter(tags=["login"])

REFRESH_COOKIE_PATH = f"{settings.API_V1_STR}/login/refresh"


def _cookie_secure() -> bool:
    return settings.ENVIRONMENT != "local"


def _set_session_cookies(response: Response, user: User) -> str:
    access_token = security.create_access_token(
        user.id,
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        token_version=user.token_version,
    )
    refresh_token = security.create_refresh_token(
        user.id,
        expires_delta=timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        token_version=user.token_version,
    )
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=_cookie_secure(),
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    # Refresh tokens are rotated on every use.
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=_cookie_secure(),
        samesite="strict",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        path=REFRESH_COOKIE_PATH,
    )
    return access_token


def _clear_session_cookies(response: Response) -> None:
    response.delete_cookie(
        key="access_token", httponly=True, secure=_cookie_secure(), samesite="lax"
    )
    response.delete_cookie(
        key="refresh_token",
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        secure=_cookie_secure(),
        samesite="strict",
    )


@router.post("/login/access-token")
def login_access_token(
    request: Request,
    session: SessionDep,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    response: Response,
) -> Token:
    """
    OAuth2 compatible token login, get an access token for future requests
    """
    ip = rate_limit.client_ip(request)
    rate_limit.check_login_allowed(ip, form_data.username)
    user = crud.authenticate(
        session=session, email=form_data.username, password=form_data.password
    )
    if not user:
        rate_limit.record_login_failure(ip, form_data.username)
        logger.warning("login_failed ip=%s", ip)
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    elif not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    rate_limit.clear_login_failures(ip, form_data.username)
    logger.info("login_succeeded user_id=%s ip=%s", user.id, ip)

    access_token = _set_session_cookies(response, user)
    return Token(access_token=access_token)


@router.post("/login/test-token", response_model=UserPublic)
def test_token(current_user: CurrentUser) -> Any:
    """
    Test access token
    """
    return current_user


@router.post("/login/refresh")
def refresh_token(
    request: Request,
    response: Response,
    session: SessionDep,
    refresh_token: Annotated[str | None, Cookie()] = None,
) -> Token:
    """
    Refresh access token (and rotate the refresh token).
    """
    enforce_csrf_origin(request)
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token missing",
        )
    # Only a token of type "refresh" is accepted here; access and reset tokens
    # are rejected, as are tokens revoked via token_version.
    user = user_from_token(session, refresh_token, security.TOKEN_TYPE_REFRESH)
    access_token = _set_session_cookies(response, user)
    return Token(access_token=access_token)


@router.post("/login/logout")
def logout(
    request: Request,
    response: Response,
    session: SessionDep,
    access_token: Annotated[str | None, Cookie()] = None,
) -> Message:
    """
    Logout: clear the session cookies and revoke all of the user's tokens.
    """
    token = None
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        token = auth[7:].strip()
    elif access_token:
        enforce_csrf_origin(request)
        token = access_token
    if token:
        try:
            user = user_from_token(session, token, security.TOKEN_TYPE_ACCESS)
        except HTTPException:
            user = None
        if user:
            crud.revoke_user_tokens(session=session, db_user=user)
            logger.info("logout user_id=%s", user.id)
    _clear_session_cookies(response)
    return Message(message="Logged out successfully")


@router.post("/password-recovery/{email}")
def recover_password(email: str, request: Request, session: SessionDep) -> Message:
    """
    Password Recovery
    """
    ip = rate_limit.client_ip(request)
    rate_limit.enforce(
        f"recovery-ip:{ip}", settings.PASSWORD_RECOVERY_RATE_LIMIT_PER_IP
    )
    rate_limit.enforce(
        f"recovery-email:{email.lower()}",
        settings.PASSWORD_RECOVERY_RATE_LIMIT_PER_EMAIL,
    )
    user = crud.get_user_by_email(session=session, email=email)

    # Always return the same response to prevent email enumeration attacks
    # Only send email if user actually exists
    if user and user.is_active and settings.emails_enabled:
        password_reset_token = generate_password_reset_token(user=user)
        email_data = generate_reset_password_email(
            email_to=user.email, email=user.email, token=password_reset_token
        )
        send_email(
            email_to=user.email,
            subject=email_data.subject,
            html_content=email_data.html_content,
        )
        logger.info("password_recovery_requested user_id=%s ip=%s", user.id, ip)
    return Message(
        message="If that email is registered, we sent a password recovery link"
    )


@router.post("/reset-password/")
def reset_password(request: Request, session: SessionDep, body: NewPassword) -> Message:
    """
    Reset password
    """
    ip = rate_limit.client_ip(request)
    rate_limit.enforce(f"reset-ip:{ip}", settings.RESET_PASSWORD_RATE_LIMIT_PER_IP)
    # verify_password_reset_token checks signature, expiry, token type and that
    # the password has not changed since the token was issued (single use).
    user = verify_password_reset_token(session=session, token=body.token)
    if not user:
        raise HTTPException(status_code=400, detail="Invalid token")
    elif not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    crud.set_user_password(session=session, db_user=user, password=body.new_password)
    logger.info("password_reset user_id=%s ip=%s", user.id, ip)
    return Message(message="Password updated successfully")


@router.post(
    "/password-recovery-html-content/{email}",
    dependencies=[Depends(get_current_active_superuser)],
    response_class=HTMLResponse,
)
def recover_password_html_content(email: str, session: SessionDep) -> Any:
    """
    HTML Content for Password Recovery
    """
    user = crud.get_user_by_email(session=session, email=email)

    if not user:
        raise HTTPException(
            status_code=404,
            detail="The user with this username does not exist in the system.",
        )
    password_reset_token = generate_password_reset_token(user=user)
    email_data = generate_reset_password_email(
        email_to=user.email, email=user.email, token=password_reset_token
    )

    return HTMLResponse(
        content=email_data.html_content,
        headers={"X-Email-Subject": email_data.subject},
    )
