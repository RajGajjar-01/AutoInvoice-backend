import secrets
import uuid
from typing import Annotated, Any

import jwt
import structlog
from fastapi import APIRouter, BackgroundTasks, Cookie, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from jwt.exceptions import InvalidTokenError
from sqlmodel import SQLModel

from app.api.deps import CurrentUser, SessionDep, UserServiceDep
from app.api.routes.google_auth import NONCE_COOKIE, NONCE_COOKIE_MAX_AGE
from app.core import security
from app.core.auth_cookies import (
    COOKIE_SAMESITE,
    COOKIE_SECURE,
    clear_auth_cookies,
    set_auth_cookies,
)
from app.core.config import settings
from app.core.rate_limit import limiter
from app.models import User
from app.schemas import (
    Message,
    NewPassword,
    SetPassword,
    UpdatePassword,
    UserPublic,
    UserRegister,
    UserUpdateMe,
    VerifyEmailRequest,
)
from app.services import google_oauth_service, verification_service
from app.services.email_service import (
    generate_password_reset_token,
    generate_reset_password_email,
    generate_verify_email,
    send_email,
    verify_password_reset_token,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(SQLModel):
    email: str
    password: str


class AuthResponse(SQLModel):
    user: UserPublic


@router.get("/google/login")
def google_login() -> RedirectResponse:
    if not settings.google_oauth_enabled:
        raise HTTPException(
            status_code=503, detail="Google sign-in is not configured on this server"
        )
    nonce = secrets.token_urlsafe(32)
    state = google_oauth_service.create_state_token(
        user_id=None, mode="login", nonce=nonce
    )
    redirect = RedirectResponse(google_oauth_service.get_authorization_url(state))
    redirect.set_cookie(
        key=NONCE_COOKIE,
        value=nonce,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        max_age=NONCE_COOKIE_MAX_AGE,
        path="/",
    )
    return redirect


@router.post("/signup", response_model=AuthResponse, status_code=201)
@limiter.limit(settings.RATE_LIMIT_AUTH)
async def signup(
    request: Request,
    response: Response,
    user_in: UserRegister,
    user_service: UserServiceDep,
    background_tasks: BackgroundTasks,
) -> AuthResponse:
    _ = request
    user = await user_service.signup(user_in)
    code = await verification_service.issue_code(user.id)
    if settings.emails_enabled:
        email_data = generate_verify_email(
            email_to=user.email, username=user.full_name or user.email, code=code
        )
        background_tasks.add_task(
            send_email,
            email_to=user.email,
            subject=email_data.subject,
            html_content=email_data.html_content,
        )
    else:
        logger.warning(
            "[DEV / NO BREVO KEY] Verification code", email=user.email, code=code
        )
    set_auth_cookies(response, user)
    return AuthResponse(user=UserPublic.from_user(user))


@router.post("/login", response_model=AuthResponse)
@limiter.limit(settings.RATE_LIMIT_AUTH)
async def login(
    request: Request,
    response: Response,
    body: LoginRequest,
    user_service: UserServiceDep,
) -> AuthResponse:
    _ = request
    user = await user_service.authenticate(body.email, body.password)
    if not user:
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    set_auth_cookies(response, user)
    return AuthResponse(user=UserPublic.from_user(user))


@router.post("/refresh", response_model=Message)
@limiter.limit(settings.RATE_LIMIT_AUTH)
async def refresh_token(
    request: Request,
    response: Response,
    session: SessionDep,
    refresh_token: Annotated[str | None, Cookie()] = None,
) -> Message:
    _ = request
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Refresh token not found")

    try:
        payload = jwt.decode(
            refresh_token, settings.SECRET_KEY, algorithms=[security.ALGORITHM]
        )
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=403, detail="Invalid token type")
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=403, detail="Invalid token")
    except InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=403, detail="Invalid user ID format")

    user = await session.get(User, user_uuid)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    set_auth_cookies(response, user)
    return Message(message="Token refreshed")


@router.post("/logout", response_model=Message)
def logout(response: Response) -> Message:
    clear_auth_cookies(response)
    return Message(message="Logged out successfully")


@router.get("/me", response_model=UserPublic)
def get_current_user_info(current_user: CurrentUser) -> Any:
    return UserPublic.from_user(current_user)


@router.patch("/me", response_model=UserPublic)
async def update_current_user(
    current_user: CurrentUser, user_in: UserUpdateMe, user_service: UserServiceDep
) -> Any:
    user = await user_service.update_me(current_user, user_in)
    return UserPublic.from_user(user)


@router.post("/verify-email", response_model=Message)
async def verify_email(
    current_user: CurrentUser, body: VerifyEmailRequest, user_service: UserServiceDep
) -> Message:
    if current_user.is_verified:
        return Message(message="Email already verified")
    await verification_service.verify_code(current_user.id, body.code)
    await user_service.verify_email(current_user)
    return Message(message="Email verified successfully")


@router.post("/resend-verification-email", response_model=Message)
@limiter.limit(settings.RATE_LIMIT_AUTH)
async def resend_verification_email(
    request: Request,
    response: Response,
    current_user: CurrentUser,
    background_tasks: BackgroundTasks,
) -> Message:
    _ = request
    _ = response
    if current_user.is_verified:
        return Message(message="Email already verified")
    code = await verification_service.request_resend(current_user.id)
    if settings.emails_enabled:
        email_data = generate_verify_email(
            email_to=current_user.email,
            username=current_user.full_name or current_user.email,
            code=code,
        )
        background_tasks.add_task(
            send_email,
            email_to=current_user.email,
            subject=email_data.subject,
            html_content=email_data.html_content,
        )
    else:
        logger.warning(
            "[DEV / NO BREVO KEY] Verification code",
            email=current_user.email,
            code=code,
        )
    return Message(message="Verification code resent")


@router.post("/forgot-password", response_model=Message)
@limiter.limit(settings.RATE_LIMIT_AUTH)
async def forgot_password(
    request: Request,
    response: Response,
    email: str,
    user_service: UserServiceDep,
    background_tasks: BackgroundTasks,
) -> Message:
    _ = request
    _ = response
    user = await user_service.get_by_email(email)
    if user:
        password_reset_token = generate_password_reset_token(email=email)
        if settings.emails_enabled:
            email_data = generate_reset_password_email(
                email_to=user.email, email=email, token=password_reset_token
            )
            background_tasks.add_task(
                send_email,
                email_to=user.email,
                subject=email_data.subject,
                html_content=email_data.html_content,
            )
        else:
            logger.warning(
                "[DEV / NO BREVO KEY] Password reset link",
                email=user.email,
                reset_url=f"{settings.FRONTEND_HOST}/reset-password?token={password_reset_token}",
            )
    return Message(
        message="If that email is registered, a password reset link has been sent"
    )


@router.post("/reset-password", response_model=Message)
@limiter.limit(settings.RATE_LIMIT_AUTH)
async def reset_password(
    request: Request,
    response: Response,
    body: NewPassword,
    user_service: UserServiceDep,
) -> Message:
    _ = request
    _ = response
    email = verify_password_reset_token(token=body.token)
    if not email:
        raise HTTPException(status_code=400, detail="Invalid token")
    user = await user_service.get_by_email(email)
    if not user:
        raise HTTPException(status_code=400, detail="Invalid token")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    await user_service.update_password(user, body.new_password)
    return Message(message="Password updated successfully")


@router.post("/update-password", response_model=Message)
async def update_password(
    current_user: CurrentUser, body: UpdatePassword, user_service: UserServiceDep
) -> Message:
    if current_user.hashed_password is None:
        raise HTTPException(
            status_code=400,
            detail="This account has no password yet. Use /auth/set-password to create one.",
        )
    user = await user_service.authenticate(current_user.email, body.current_password)
    if not user:
        raise HTTPException(status_code=400, detail="Incorrect current password")

    await user_service.update_password(user, body.new_password)
    return Message(message="Password updated successfully")


@router.post("/set-password", response_model=Message)
async def set_password(
    current_user: CurrentUser, body: SetPassword, user_service: UserServiceDep
) -> Message:
    if current_user.hashed_password is not None:
        raise HTTPException(
            status_code=400,
            detail="This account already has a password. Use /auth/update-password instead.",
        )
    await user_service.update_password(current_user, body.new_password)
    return Message(message="Password set successfully")
