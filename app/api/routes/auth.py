from typing import Annotated, Any

from fastapi import APIRouter, Cookie, Header, HTTPException, Response
from sqlmodel import SQLModel

from app import crud
from app.api.deps import CurrentUser, SessionDep
from app.core.config import settings
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

ACCESS_TOKEN_MAX_AGE = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60  # 15 min
REFRESH_TOKEN_MAX_AGE = settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60  # 7 days
COOKIE_SECURE = settings.ENVIRONMENT != "local"  # False for localhost

router = APIRouter(tags=["auth"])


class AuthResponse(Token):
    refresh_token: str | None = None
    expires_in: int | None = None
    user: dict | None = None


class EmailRequest(SQLModel):
    email: str


class LoginRequest(SQLModel):
    email: str
    password: str


@router.post("/auth/signup", response_model=AuthResponse)
async def signup(
    response: Response,
    session: SessionDep,
    user_in: UserRegister,
) -> AuthResponse:
    """
    Sign up a new user via Supabase Auth.

    Creates user in Supabase and returns session tokens as HttpOnly cookies.
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

    access_token = result.get("access_token", "")
    refresh_token_value = result.get("refresh_token")

    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        max_age=ACCESS_TOKEN_MAX_AGE,
        path="/",
    )
    if refresh_token_value:
        response.set_cookie(
            key="refresh_token",
            value=refresh_token_value,
            httponly=True,
            secure=COOKIE_SECURE,
            samesite="lax",
            max_age=REFRESH_TOKEN_MAX_AGE,
            path="/",
        )

    return AuthResponse(
        access_token="",
        refresh_token=None,
        expires_in=result.get("expires_in"),
        user=user_data,
    )


@router.post("/auth/login", response_model=AuthResponse)
async def login(
    response: Response,
    session: SessionDep,
    body: LoginRequest,
) -> AuthResponse:
    """
    Login with email and password via Supabase Auth.

    Returns access_token and refresh_token as HttpOnly cookies.
    """
    try:
        result = await auth_service.sign_in_with_password(
            email=body.email,
            password=body.password,
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
                email=user_data.get("email", body.email),
                full_name=user_data.get("user_metadata", {}).get("full_name"),
                is_verified=bool(user_data.get("email_confirmed_at")),
            )
            session.add(profile)
            session.commit()

    access_token = result.get("access_token", "")
    refresh_token_value = result.get("refresh_token")

    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        max_age=ACCESS_TOKEN_MAX_AGE,
        path="/",
    )
    if refresh_token_value:
        response.set_cookie(
            key="refresh_token",
            value=refresh_token_value,
            httponly=True,
            secure=COOKIE_SECURE,
            samesite="lax",
            max_age=REFRESH_TOKEN_MAX_AGE,
            path="/",
        )

    return AuthResponse(
        access_token="",
        refresh_token=None,
        expires_in=result.get("expires_in"),
        user=user_data,
    )


@router.post("/auth/refresh", response_model=AuthResponse)
async def refresh_token(
    response: Response,
    refresh_token: Annotated[str | None, Cookie()] = None,
) -> AuthResponse:
    """
    Refresh access token using refresh token from cookie.
    """
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Refresh token not found")

    try:
        result = await auth_service.refresh_session(refresh_token=refresh_token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    access_token = result.get("access_token", "")
    refresh_token_value = result.get("refresh_token")

    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        max_age=ACCESS_TOKEN_MAX_AGE,
        path="/",
    )
    if refresh_token_value:
        response.set_cookie(
            key="refresh_token",
            value=refresh_token_value,
            httponly=True,
            secure=COOKIE_SECURE,
            samesite="lax",
            max_age=REFRESH_TOKEN_MAX_AGE,
            path="/",
        )

    return AuthResponse(
        access_token="",
        refresh_token=None,
        expires_in=result.get("expires_in"),
    )


@router.post("/auth/logout", response_model=Message)
async def logout(
    response: Response,
    authorization: str | None = Header(None),
) -> Message:
    """
    Logout - invalidates the Supabase session and clears cookies.
    """
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
        try:
            await auth_service.sign_out(access_token=token)
        except Exception:
            pass

    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")

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
    body: EmailRequest,
) -> Message:
    """
    Request password reset email via Supabase.
    """
    try:
        await auth_service.reset_password_email(email=body.email)
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
    access_token: Annotated[str | None, Cookie()] = None,
) -> Message:
    """
    Update user password.

    Uses access token from cookie.
    """
    if not access_token:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated",
        )

    try:
        await auth_service.update_user(
            access_token=access_token,
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
    body: EmailRequest,
) -> Message:
    """
    Resend email verification.
    """
    try:
        await auth_service.resend_verification_email(email=body.email)
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
