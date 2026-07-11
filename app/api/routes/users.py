import uuid
from typing import Any

from fastapi import APIRouter

from app.api.deps import CurrentUser, SuperUserDep, UserServiceDep
from app.schemas import UserPublic, UsersPublic, UserUpdate, UserUpdateMe

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/", response_model=UsersPublic)
async def read_users(
    superuser: SuperUserDep, user_service: UserServiceDep, skip: int = 0, limit: int = 100
) -> Any:
    users, count = await user_service.list_users(skip=skip, limit=limit)
    return UsersPublic(data=[UserPublic.model_validate(u) for u in users], count=count)


@router.get("/me", response_model=UserPublic)
def read_user_me(current_user: CurrentUser) -> Any:
    return UserPublic.model_validate(current_user)


@router.patch("/me", response_model=UserPublic)
async def update_user_me(
    current_user: CurrentUser, user_in: UserUpdateMe, user_service: UserServiceDep
) -> Any:
    user = await user_service.update_me(current_user, user_in)
    return UserPublic.model_validate(user)


@router.delete("/me", status_code=204)
async def delete_user_me(current_user: CurrentUser, user_service: UserServiceDep) -> None:
    await user_service.delete_me(current_user)


@router.get("/{user_id}", response_model=UserPublic)
async def read_user_by_id(
    user_id: uuid.UUID, current_user: CurrentUser, user_service: UserServiceDep
) -> Any:
    user = await user_service.get_by_id_for_user(user_id, current_user)
    return UserPublic.model_validate(user)


@router.patch("/{user_id}", response_model=UserPublic)
async def update_user(
    user_id: uuid.UUID, superuser: SuperUserDep, user_in: UserUpdate, user_service: UserServiceDep
) -> Any:
    user = await user_service.update_user(user_id, user_in)
    return UserPublic.model_validate(user)


@router.delete("/{user_id}", status_code=204)
async def delete_user(
    user_id: uuid.UUID, superuser: SuperUserDep, user_service: UserServiceDep
) -> None:
    await user_service.delete_user(user_id, superuser)
