from datetime import timedelta
from typing import Annotated, Any

import jwt
from fastapi import APIRouter, Cookie, HTTPException, Response
from jwt.exceptions import InvalidTokenError
from sqlmodel import SQLModel

from app import crud
from app.api.deps import CurrentUser, SessionDep
from app.core import security
from app.core.config import settings
from app.schemas import (
    Message,
    NewPassword,
    Token,
    UserCreate,
    UserPublic,
    UserUpdateMe,
)
from app.utils import (
    generate_password_reset_token,
    generate_reset_password_email,
    send_email,
    verify_password_reset_token,
)

router = APIRouter(tags=["auth"])

ACCESS_TOKEN_MAX_AGE = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
REFRESH_TOKEN_MAX_AGE = settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
COOKIE_SECURE = settings.ENVIRONMENT != "local"
COOKIE_SAMESITE = "none" if settings.ENVIRONMENT != "local" else "lax"


class LoginRequest(SQLModel):
    email: str
    password: str


class AuthResponse(Token):
    user: UserPublic | None = None


@router.post("/auth/signup", response_model=AuthResponse)
def signup(
    response: Response,
    session: SessionDep,
    user_in: UserCreate,
) -> AuthResponse:
    user = crud.get_user_by_email(session=session, email=user_in.email)
    if user:
        raise HTTPException(
            status_code=400,
            detail="A user with this email already exists",
        )

    user = crud.create_user(session=session, user_create=user_in)

    access_token = security.create_access_token(subject=user.id)
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

    return AuthResponse(
        access_token=access_token,
        token_type="bearer",
        refresh_token=refresh_token,
        user=UserPublic.model_validate(user),
    )


@router.post("/auth/login", response_model=AuthResponse)
def login(
    response: Response,
    session: SessionDep,
    body: LoginRequest,
) -> AuthResponse:
    user = crud.authenticate(session=session, email=body.email, password=body.password)
    if not user:
        raise HTTPException(status_code=400, detail="Incorrect email or password")

    access_token = security.create_access_token(subject=user.id)
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

    return AuthResponse(
        access_token=access_token,
        token_type="bearer",
        refresh_token=refresh_token,
        user=UserPublic.model_validate(user),
    )


@router.post("/auth/refresh", response_model=Token)
def refresh_token(
    response: Response,
    refresh_token: Annotated[str | None, Cookie()] = None,
) -> Token:
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

    new_access_token = security.create_access_token(subject=user_id)
    new_refresh_token = security.create_refresh_token(subject=user_id)

    response.set_cookie(
        key="access_token",
        value=new_access_token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        max_age=ACCESS_TOKEN_MAX_AGE,
        path="/",
    )
    response.set_cookie(
        key="refresh_token",
        value=new_refresh_token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        max_age=REFRESH_TOKEN_MAX_AGE,
        path="/",
    )

    return Token(
        access_token=new_access_token,
        token_type="bearer",
        refresh_token=new_refresh_token,
    )


@router.post("/auth/logout", response_model=Message)
def logout(response: Response) -> Message:
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")
    return Message(message="Logged out successfully")


@router.get("/auth/me", response_model=UserPublic)
def get_current_user_info(current_user: CurrentUser) -> Any:
    return UserPublic.model_validate(current_user)


@router.patch("/auth/me", response_model=UserPublic)
def update_current_user(
    session: SessionDep,
    current_user: CurrentUser,
    user_in: UserUpdateMe,
) -> Any:
    if user_in.full_name is not None:
        current_user.full_name = user_in.full_name
    if user_in.email is not None and user_in.email != current_user.email:
        existing_user = crud.get_user_by_email(session=session, email=user_in.email)
        if existing_user:
            raise HTTPException(
                status_code=400,
                detail="A user with this email already exists",
            )
        current_user.email = user_in.email
        current_user.is_verified = False

    session.add(current_user)
    session.commit()
    session.refresh(current_user)

    return UserPublic.model_validate(current_user)


@router.post("/auth/forgot-password", response_model=Message)
def forgot_password(
    session: SessionDep,
    email: str,
) -> Message:
    user = crud.get_user_by_email(session=session, email=email)
    if user:
        password_reset_token = generate_password_reset_token(email=email)
        email_data = generate_reset_password_email(
            email_to=user.email, email=email, token=password_reset_token
        )
        send_email(
            email_to=user.email,
            subject=email_data.subject,
            html_content=email_data.html_content,
        )

    return Message(
        message="If that email is registered, a password reset link has been sent"
    )


@router.post("/auth/reset-password", response_model=Message)
def reset_password(
    session: SessionDep,
    body: NewPassword,
) -> Message:
    email = verify_password_reset_token(token=body.token)
    if not email:
        raise HTTPException(status_code=400, detail="Invalid token")
    user = crud.get_user_by_email(session=session, email=email)
    if not user:
        raise HTTPException(status_code=400, detail="Invalid token")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")

    from app.schemas import UserUpdate

    user_update = UserUpdate(password=body.new_password)
    crud.update_user(session=session, db_user=user, user_in=user_update)

    return Message(message="Password updated successfully")


@router.post("/auth/update-password", response_model=Message)
def update_password(
    session: SessionDep,
    current_user: CurrentUser,
    body: dict[str, str],
) -> Message:
    current_password = body.get("current_password")
    new_password = body.get("new_password")

    if not current_password or not new_password:
        raise HTTPException(
            status_code=400,
            detail="Current password and new password are required",
        )

    user = crud.authenticate(
        session=session, email=current_user.email, password=current_password
    )
    if not user:
        raise HTTPException(status_code=400, detail="Incorrect current password")

    from app.schemas import UserUpdate

    user_update = UserUpdate(password=new_password)
    crud.update_user(session=session, db_user=user, user_in=user_update)

    return Message(message="Password updated successfully")
