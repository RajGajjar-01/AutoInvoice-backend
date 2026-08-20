import uuid

from fastapi import APIRouter
from pydantic import EmailStr
from sqlmodel import SQLModel

from app.api.deps import SuperUserDep, UserServiceDep
from app.schemas import PaginatedResponse, UserPublic

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
    skip: int = 0,
    limit: int = 50,
) -> PaginatedResponse[UserPublic]:
    users, total = await user_service.list_users(skip=skip, limit=limit)
    total_pages = (total + limit - 1) // limit if total > 0 else 1
    return PaginatedResponse(
        data=[UserPublic.model_validate(u) for u in users],
        total=total,
        page=skip // limit + 1,
        page_size=limit,
        total_pages=total_pages,
    )


@router.post("/users", response_model=UserPublic, status_code=201)
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
async def get_user(
    superuser: SuperUserDep, user_id: uuid.UUID, user_service: UserServiceDep
) -> UserPublic:
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


@router.delete("/users/{user_id}", status_code=204)
async def delete_user(
    superuser: SuperUserDep, user_id: uuid.UUID, user_service: UserServiceDep
) -> None:
    await user_service.delete_user(user_id, superuser)
