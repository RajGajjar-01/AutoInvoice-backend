from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, EmailStr

from app.api.deps import SessionDep
from app.core.supabase_client import admin_auth_service
from app.models import (
    Profile,
    UserPublic,
)

router = APIRouter(tags=["private"], prefix="/private")


class PrivateUserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    is_verified: bool = False


@router.post("/users/", response_model=UserPublic)
async def create_user(user_in: PrivateUserCreate, session: SessionDep) -> Any:
    """
    Create a new user via Supabase admin API (private endpoint).
    """
    import uuid

    result = await admin_auth_service.create_user(
        email=user_in.email,
        password=user_in.password,
        email_confirm=user_in.is_verified,
        full_name=user_in.full_name,
    )

    user_uuid = uuid.UUID(result.get("id", ""))
    profile = Profile(
        id=user_uuid,
        email=user_in.email,
        full_name=user_in.full_name,
        is_verified=user_in.is_verified,
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
