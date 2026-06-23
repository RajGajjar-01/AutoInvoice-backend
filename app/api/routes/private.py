from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, EmailStr

from app.api.deps import UserServiceDep
from app.schemas import UserPublic

router = APIRouter(tags=["private"], prefix="/private")


class PrivateUserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    is_verified: bool = False
    is_superuser: bool = False


@router.post("/users/", response_model=UserPublic)
async def create_user(user_in: PrivateUserCreate, user_service: UserServiceDep) -> Any:
    user = await user_service.create_user_private(
        email=user_in.email,
        password=user_in.password,
        full_name=user_in.full_name,
        is_superuser=user_in.is_superuser,
        is_verified=user_in.is_verified,
    )
    return UserPublic.model_validate(user)
