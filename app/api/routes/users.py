import uuid
from typing import Any

from fastapi import APIRouter, Header, HTTPException
from sqlmodel import col, func, select

from app.api.deps import CurrentUser, SessionDep, SuperUserDep
from app.core.supabase_client import admin_auth_service, auth_service
from app.exceptions import parse_supabase_error
from app.models import (
    Message,
    Profile,
    ProfilePublic,
    ProfilesPublic,
    UpdatePassword,
    UserPublic,
    UserUpdateMe,
    get_datetime_utc,
)

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/", response_model=ProfilesPublic)
def read_profiles(
    session: SessionDep,
    superuser: SuperUserDep,
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """
    Retrieve profiles (superuser only).
    """
    count_statement = select(func.count()).select_from(Profile)
    count = session.exec(count_statement).one()

    statement = (
        select(Profile)
        .order_by(col(Profile.created_at).desc())
        .offset(skip)
        .limit(limit)
    )
    profiles = session.exec(statement).all()

    return ProfilesPublic(
        data=[
            ProfilePublic(
                id=p.id,
                email=p.email,
                full_name=p.full_name,
                avatar_url=p.avatar_url,
                is_superuser=p.is_superuser,
                is_verified=p.is_verified,
                created_at=p.created_at,
                updated_at=p.updated_at,
            )
            for p in profiles
        ],
        count=count,
    )


@router.get("/me", response_model=UserPublic)
def read_user_me(current_user: CurrentUser) -> Any:
    """
    Get current user.
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


@router.patch("/me", response_model=UserPublic)
async def update_user_me(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    user_in: UserUpdateMe,
    authorization: str | None = Header(None),
) -> Any:
    """
    Update own user profile.
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
        token = authorization[7:]
        try:
            await auth_service.update_user(access_token=token, email=user_in.email)
            current_user.email = user_in.email
            current_user.updated_at = get_datetime_utc()
            session.add(current_user)
            session.commit()
            session.refresh(current_user)
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=str(e),
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


@router.patch("/me/password", response_model=Message)
async def update_password_me(
    *,
    current_user: CurrentUser,
    body: UpdatePassword,
    authorization: str | None = Header(None),
) -> Any:
    """
    Update own password.

    This is handled by Supabase Auth.
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
        return Message(message="Password updated successfully")
    except Exception as e:
        parsed_error = parse_supabase_error(e)
        raise HTTPException(
            status_code=400,
            detail=parsed_error.message,
        )


@router.delete("/me", response_model=Message)
async def delete_user_me(
    session: SessionDep,
    current_user: CurrentUser,
    authorization: str | None = Header(None),
) -> Any:
    """
    Delete own user account.

    Requires access token to delete from Supabase Auth.
    """
    if current_user.is_superuser:
        raise HTTPException(
            status_code=403,
            detail="Super users are not allowed to delete themselves",
        )

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Not authenticated",
        )

    try:
        await admin_auth_service.delete_user(str(current_user.id))
    except Exception:
        pass

    session.delete(current_user)
    session.commit()

    return Message(message="User deleted successfully")


@router.get("/{user_id}", response_model=UserPublic)
def read_user_by_id(
    user_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
) -> Any:
    """
    Get a specific user by id.
    """
    profile = session.get(Profile, user_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="User not found")

    if profile.id != current_user.id and not current_user.is_superuser:
        raise HTTPException(
            status_code=403,
            detail="The user doesn't have enough privileges",
        )

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


@router.delete("/{user_id}", response_model=Message)
async def delete_user(
    session: SessionDep,
    superuser: SuperUserDep,
    user_id: uuid.UUID,
) -> Message:
    """
    Delete a user (superuser only).
    """
    if user_id == superuser.id:
        raise HTTPException(
            status_code=403,
            detail="Super users are not allowed to delete themselves",
        )

    profile = session.get(Profile, user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="User not found")

    try:
        await admin_auth_service.delete_user(str(user_id))
    except Exception:
        pass

    session.delete(profile)
    session.commit()

    return Message(message="User deleted successfully")
