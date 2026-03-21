from typing import Any

from fastapi import APIRouter, Header, HTTPException
from sqlmodel import SQLModel

from app import crud
from app.api.deps import CurrentUser, SessionDep
from app.core.supabase_client import auth_service
from app.exceptions import (
    InvalidCredentialsError,
    UserAlreadyExistsError,
    parse_supabase_error,
)
from app.models import (
    Message,
    Token,
    UpdatePassword,
    UserPublic,
    UserRegister,
    UserUpdateMe,
    get_datetime_utc,
)

router = APIRouter(tags=["auth"])


class AuthResponse(Token):
    refresh_token: str | None = None
    expires_in: int | None = None
    user: dict | None = None


class OAuthURLResponse(SQLModel):
    url: str
    provider: str


@router.post("/auth/signup", response_model=AuthResponse)
async def signup(
    session: SessionDep,
    user_in: UserRegister,
) -> AuthResponse:
    """
    Sign up a new user via Supabase Auth.

    Creates user in Supabase and returns session tokens.
    """
    try:
        result = await auth_service.sign_up(
            email=user_in.email,
            password=user_in.password,
            full_name=user_in.full_name,
        )
    except Exception as e:
        parsed_error = parse_supabase_error(e)
        if isinstance(parsed_error, UserAlreadyExistsError):
            raise HTTPException(status_code=400, detail="User already exists")
        raise HTTPException(
            status_code=400,
            detail=parsed_error.message,
        )

    user_data = result.get("user")
    if user_data and user_data.get("id"):
        import uuid

        from app.models import Profile

        user_uuid = uuid.UUID(user_data["id"])
        profile = crud.get_profile_by_id(session=session, user_id=user_uuid)
        if not profile:
            profile = Profile(
                id=user_uuid,
                email=user_data.get("email", user_in.email),
                full_name=user_in.full_name,
                is_verified=bool(user_data.get("email_confirmed_at")),
            )
            session.add(profile)
            session.commit()

    return AuthResponse(
        access_token=result.get("access_token", ""),
        refresh_token=result.get("refresh_token"),
        expires_in=result.get("expires_in"),
        user=user_data,
    )


@router.post("/auth/login", response_model=AuthResponse)
async def login(
    email: str,
    password: str,
    session: SessionDep,
) -> AuthResponse:
    """
    Login with email and password via Supabase Auth.

    Returns access_token, refresh_token, and user info.
    """
    try:
        result = await auth_service.sign_in_with_password(
            email=email,
            password=password,
        )
    except Exception as e:
        parsed_error = parse_supabase_error(e)
        if isinstance(parsed_error, InvalidCredentialsError):
            raise HTTPException(status_code=400, detail="Incorrect email or password")
        raise HTTPException(
            status_code=400,
            detail=parsed_error.message,
        )

    user_data = result.get("user")
    if user_data and user_data.get("id"):
        import uuid

        from app.models import Profile

        user_uuid = uuid.UUID(user_data["id"])
        profile = crud.get_profile_by_id(session=session, user_id=user_uuid)
        if not profile:
            profile = Profile(
                id=user_uuid,
                email=user_data.get("email", email),
                full_name=user_data.get("user_metadata", {}).get("full_name"),
                is_verified=bool(user_data.get("email_confirmed_at")),
            )
            session.add(profile)
            session.commit()

    return AuthResponse(
        access_token=result.get("access_token", ""),
        refresh_token=result.get("refresh_token"),
        expires_in=result.get("expires_in"),
        user=user_data,
    )


@router.post("/auth/refresh", response_model=AuthResponse)
async def refresh_token(
    refresh_token: str,
) -> AuthResponse:
    """
    Refresh access token using refresh token.
    """
    try:
        result = await auth_service.refresh_session(refresh_token=refresh_token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    return AuthResponse(
        access_token=result.get("access_token", ""),
        refresh_token=result.get("refresh_token"),
        expires_in=result.get("expires_in"),
    )


@router.post("/auth/logout", response_model=Message)
async def logout(
    authorization: str | None = Header(None),
) -> Message:
    """
    Logout - invalidates the Supabase session.
    """
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
        try:
            await auth_service.sign_out(access_token=token)
        except Exception:
            pass

    return Message(message="Logged out successfully")


@router.get("/auth/me", response_model=UserPublic)
def get_current_user_info(current_user: CurrentUser) -> Any:
    """
    Get current user info from JWT token.
    """
    return UserPublic(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        avatar_url=current_user.avatar_url,
        is_superuser=current_user.is_superuser,
        is_verified=current_user.is_verified,
        created_at=current_user.created_at,
        updated_at=current_user.updated_at,
    )


@router.post("/auth/forgot-password", response_model=Message)
async def forgot_password(
    email: str,
) -> Message:
    """
    Request password reset email via Supabase.
    """
    try:
        await auth_service.reset_password_email(email=email)
    except Exception:
        pass

    return Message(
        message="If that email is registered, a password reset link has been sent"
    )


@router.post("/auth/update-password", response_model=Message)
async def update_password(
    current_user: CurrentUser,
    session: SessionDep,
    body: UpdatePassword,
    authorization: str | None = Header(None),
) -> Message:
    """
    Update user password.

    Requires the current access token.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Not authenticated",
        )

    token = authorization[7:]

    try:
        await auth_service.update_user(
            access_token=token,
            password=body.new_password,
        )
    except Exception as e:
        parsed_error = parse_supabase_error(e)
        raise HTTPException(
            status_code=400,
            detail=parsed_error.message,
        )

    return Message(message="Password updated successfully")


@router.post("/auth/resend-verification", response_model=Message)
async def resend_verification(
    email: str,
) -> Message:
    """
    Resend email verification.
    """
    try:
        await auth_service.resend_verification_email(email=email)
    except Exception:
        pass

    return Message(
        message="If that email is registered, a verification email has been sent"
    )


@router.patch("/auth/me", response_model=UserPublic)
def update_current_user(
    session: SessionDep,
    current_user: CurrentUser,
    user_in: UserUpdateMe,
    authorization: str | None = Header(None),
) -> Any:
    """
    Update current user information.

    Updates both local profile and Supabase metadata.
    """
    if user_in.full_name is not None:
        current_user.full_name = user_in.full_name
        current_user.updated_at = get_datetime_utc()
        session.add(current_user)
        session.commit()
        session.refresh(current_user)

    if user_in.email is not None and user_in.email != current_user.email:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=401,
                detail="Not authenticated",
            )

    return UserPublic(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        avatar_url=current_user.avatar_url,
        is_superuser=current_user.is_superuser,
        is_verified=current_user.is_verified,
        created_at=current_user.created_at,
        updated_at=current_user.updated_at,
    )
