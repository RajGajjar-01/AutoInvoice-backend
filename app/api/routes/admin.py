import uuid

from fastapi import APIRouter
from pydantic import EmailStr
from sqlmodel import SQLModel

from app.api.deps import SuperUserDep, UserServiceDep
from app.schemas import Message, PaginatedResponse, UserPublic

router = APIRouter(prefix="/admin", tags=["admin"])


class AdminUserCreate(SQLModel):
    email: EmailStr
    password: str
    full_name: str | None = None
    is_superuser: bool = False


class AdminUserUpdate(SQLModel):
    email: EmailStr | None = None
    password: str | None = None
    full_name: str | None = None
    is_superuser: bool | None = None
    is_active: bool | None = None


@router.get("/users", response_model=PaginatedResponse[UserPublic])
async def list_users(
    superuser: SuperUserDep,
    user_service: UserServiceDep,
    page: int = 1,
    page_size: int = 50,
) -> PaginatedResponse[UserPublic]:
    users, total = await user_service.list_users_page(page=page, page_size=page_size)
    total_pages = (total + page_size - 1) // page_size if total > 0 else 1
    return PaginatedResponse(
        data=[UserPublic.model_validate(u) for u in users],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.post("/users", response_model=UserPublic)
async def create_user(
    superuser: SuperUserDep, user_in: AdminUserCreate, user_service: UserServiceDep
) -> UserPublic:
    user = await user_service.create_user_as_admin(
        email=user_in.email,
        password=user_in.password,
        full_name=user_in.full_name,
        is_superuser=user_in.is_superuser,
    )
    return UserPublic.model_validate(user)


@router.get("/users/{user_id}", response_model=UserPublic)
async def get_user(superuser: SuperUserDep, user_id: uuid.UUID, user_service: UserServiceDep) -> UserPublic:
    user = await user_service.get_by_id_or_404(user_id)
    return UserPublic.model_validate(user)


@router.patch("/users/{user_id}", response_model=UserPublic)
async def update_user(
    superuser: SuperUserDep,
    user_id: uuid.UUID,
    user_in: AdminUserUpdate,
    user_service: UserServiceDep,
) -> UserPublic:
    user = await user_service.update_user_as_admin(
        user_id,
        email=user_in.email,
        password=user_in.password,
        full_name=user_in.full_name,
        is_superuser=user_in.is_superuser,
        is_active=user_in.is_active,
    )
    return UserPublic.model_validate(user)


@router.delete("/users/{user_id}", response_model=Message)
async def delete_user(
    superuser: SuperUserDep, user_id: uuid.UUID, user_service: UserServiceDep
) -> Message:
    await user_service.delete_user(user_id, superuser)
    return Message(message="User deleted successfully")
