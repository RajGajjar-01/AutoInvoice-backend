import uuid

from fastapi import APIRouter, HTTPException, Query
from pydantic import EmailStr
from sqlmodel import SQLModel

from app.api.deps import SessionDep, SuperUserDep
from app.core.supabase_client import admin_auth_service
from app.exceptions import parse_supabase_error
from app.models import (
    AuthSession,
    Message,
    PaginatedResponse,
    UserPublic,
)

router = APIRouter(prefix="/admin", tags=["admin"])


class AdminUserCreate(SQLModel):
    email: EmailStr
    password: str
    full_name: str | None = None
    email_confirm: bool = True


class AdminUserUpdate(SQLModel):
    email: EmailStr | None = None
    password: str | None = None
    full_name: str | None = None
    is_superuser: bool | None = None
    ban_duration: str | None = None


@router.get("/users", response_model=PaginatedResponse[UserPublic])
async def list_users(
    superuser: SuperUserDep,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
) -> PaginatedResponse[UserPublic]:
    """
    List all users (paginated).

    Requires superuser privileges.
    """
    try:
        result = await admin_auth_service.list_users(
            page=page,
            page_size=page_size,
        )

        users = [
            UserPublic(
                id=uuid.UUID(user["id"]),
                email=user.get("email", ""),
                full_name=user.get("user_metadata", {}).get("full_name"),
                avatar_url=user.get("user_metadata", {}).get("avatar_url"),
                is_superuser=user.get("app_metadata", {}).get("is_superuser", False),
                is_verified=bool(user.get("email_confirmed_at")),
                created_at=user.get("created_at"),
                updated_at=user.get("updated_at"),
            )
            for user in result.get("users", [])
        ]

        total_pages = (result.get("total", 0) + page_size - 1) // page_size

        return PaginatedResponse(
            data=users,
            total=result.get("total", 0),
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )
    except Exception as e:
        parsed_error = parse_supabase_error(e)
        raise HTTPException(
            status_code=400,
            detail=parsed_error.message,
        )


@router.post("/users", response_model=UserPublic)
async def create_user(
    superuser: SuperUserDep,
    session: SessionDep,
    user_in: AdminUserCreate,
) -> UserPublic:
    """
    Create a new user via admin API.

    Requires superuser privileges.
    """
    try:
        result = await admin_auth_service.create_user(
            email=user_in.email,
            password=user_in.password,
            email_confirm=user_in.email_confirm,
            full_name=user_in.full_name,
        )

        import uuid as uuid_module

        from app.models import Profile

        user_uuid = uuid_module.UUID(result.get("id", ""))
        profile = Profile(
            id=user_uuid,
            email=user_in.email,
            full_name=user_in.full_name,
            is_verified=user_in.email_confirm,
        )
        session.add(profile)
        session.commit()
        session.refresh(profile)

        return UserPublic(
            id=profile.id,
            email=profile.email,
            full_name=profile.full_name,
            avatar_url=profile.avatar_url,
            is_superuser=profile.is_superuser,
            is_verified=profile.is_verified,
            created_at=profile.created_at,
            updated_at=profile.updated_at,
        )
    except Exception as e:
        parsed_error = parse_supabase_error(e)
        raise HTTPException(
            status_code=400,
            detail=parsed_error.message,
        )


@router.get("/users/{user_id}", response_model=UserPublic)
async def get_user(
    superuser: SuperUserDep,
    user_id: uuid.UUID,
) -> UserPublic:
    """
    Get user by ID.

    Requires superuser privileges.
    """
    try:
        result = await admin_auth_service.get_user_by_id(str(user_id))

        if not result:
            raise HTTPException(status_code=404, detail="User not found")

        return UserPublic(
            id=uuid.UUID(result.get("id", "")),
            email=result.get("email", ""),
            full_name=result.get("user_metadata", {}).get("full_name"),
            avatar_url=result.get("user_metadata", {}).get("avatar_url"),
            is_superuser=result.get("app_metadata", {}).get("is_superuser", False),
            is_verified=bool(result.get("email_confirmed_at")),
            created_at=result.get("created_at"),
            updated_at=result.get("updated_at"),
        )
    except HTTPException:
        raise
    except Exception as e:
        parsed_error = parse_supabase_error(e)
        raise HTTPException(
            status_code=400,
            detail=parsed_error.message,
        )


@router.patch("/users/{user_id}", response_model=UserPublic)
async def update_user(
    superuser: SuperUserDep,
    session: SessionDep,
    user_id: uuid.UUID,
    user_in: AdminUserUpdate,
) -> UserPublic:
    """
    Update user by ID.

    Requires superuser privileges.
    """
    try:
        result = await admin_auth_service.update_user_by_id(
            user_id=str(user_id),
            email=user_in.email,
            password=user_in.password,
            full_name=user_in.full_name,
            ban_duration=user_in.ban_duration,
        )

        from app import crud

        profile = crud.get_profile_by_id(session=session, user_id=user_id)
        if profile:
            if user_in.full_name is not None:
                profile.full_name = user_in.full_name
            if user_in.is_superuser is not None:
                profile.is_superuser = user_in.is_superuser
            from app.models import get_datetime_utc

            profile.updated_at = get_datetime_utc()
            session.add(profile)
            session.commit()
            session.refresh(profile)

        return UserPublic(
            id=uuid.UUID(result.get("id", "")),
            email=result.get("email", ""),
            full_name=result.get("user_metadata", {}).get("full_name"),
            avatar_url=result.get("user_metadata", {}).get("avatar_url"),
            is_superuser=result.get("app_metadata", {}).get("is_superuser", False),
            is_verified=bool(result.get("email_confirmed_at")),
            created_at=result.get("created_at"),
            updated_at=result.get("updated_at"),
        )
    except Exception as e:
        parsed_error = parse_supabase_error(e)
        raise HTTPException(
            status_code=400,
            detail=parsed_error.message,
        )


@router.delete("/users/{user_id}", response_model=Message)
async def delete_user(
    superuser: SuperUserDep,
    session: SessionDep,
    user_id: uuid.UUID,
) -> Message:
    """
    Delete user by ID.

    Deletes from both Supabase Auth and local profile.
    Requires superuser privileges.
    """
    try:
        await admin_auth_service.delete_user(str(user_id))

        from app import crud

        profile = crud.get_profile_by_id(session=session, user_id=user_id)
        if profile:
            session.delete(profile)
            session.commit()

        return Message(message="User deleted successfully")
    except Exception as e:
        parsed_error = parse_supabase_error(e)
        raise HTTPException(
            status_code=400,
            detail=parsed_error.message,
        )


@router.get("/users/{user_id}/sessions", response_model=list[AuthSession])
async def list_user_sessions(
    superuser: SuperUserDep,
    user_id: uuid.UUID,
) -> list[AuthSession]:
    """
    List all active sessions for a user.

    Requires superuser privileges.
    """
    raise HTTPException(
        status_code=501,
        detail="Session listing requires Supabase client implementation",
    )


@router.delete("/users/{user_id}/sessions/{session_id}", response_model=Message)
async def revoke_user_session(
    superuser: SuperUserDep,
    user_id: uuid.UUID,
    session_id: str,
) -> Message:
    """
    Revoke a specific session for a user.

    Requires superuser privileges.
    """
    raise HTTPException(
        status_code=501,
        detail="Session revocation requires Supabase client implementation",
    )
