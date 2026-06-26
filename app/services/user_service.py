import uuid
from typing import Any

from app.core.security import get_password_hash, verify_password
from app.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.models import User
from app.repositories.user_repository import UserRepository
from app.schemas import UserCreate, UserRegister, UserUpdate, UserUpdateMe

DUMMY_HASH = "$argon2id$v=19$m=65536,t=3,p=4$MjQyZWE1MzBjYjJlZTI0Yw$YTU4NGM5ZTZmYjE2NzZlZjY0ZWY3ZGRkY2U2OWFjNjk"


def _validate_password(password: str) -> None:
    if len(password) < 8:
        raise ValidationError("Password must be at least 8 characters long")


class UserService:
    def __init__(self, repo: UserRepository) -> None:
        self.repo = repo

    async def get_by_email(self, email: str) -> User | None:
        return await self.repo.get_by_email(email)

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        return await self.repo.get(user_id)

    async def get_by_id_or_404(self, user_id: uuid.UUID) -> User:
        user = await self.repo.get(user_id)
        if not user:
            raise NotFoundError("User not found")
        return user

    async def signup(self, user_create: UserRegister) -> User:
        if await self.repo.get_by_email(user_create.email):
            raise ConflictError("A user with this email already exists")
        _validate_password(user_create.password)
        hashed_password = get_password_hash(user_create.password)
        return await self.repo.create(user_create, hashed_password)

    async def authenticate(self, email: str, password: str) -> User | None:
        db_user = await self.repo.get_by_email(email)
        if not db_user:
            verify_password(password, DUMMY_HASH)
            return None
        verified, updated_hash = verify_password(password, db_user.hashed_password)
        if not verified:
            return None
        if updated_hash:
            await self.repo.update(db_user, {"hashed_password": updated_hash})
        return db_user

    async def update_password(self, db_user: User, new_password: str) -> User:
        _validate_password(new_password)
        return await self.repo.update(
            db_user, {"hashed_password": get_password_hash(new_password)}
        )

    async def update_me(self, current_user: User, user_in: UserUpdateMe) -> User:
        update_data: dict[str, Any] = {}
        if user_in.full_name is not None:
            update_data["full_name"] = user_in.full_name
        if user_in.email is not None and user_in.email != current_user.email:
            if await self.repo.get_by_email(user_in.email):
                raise ConflictError("A user with this email already exists")
            update_data["email"] = user_in.email
            update_data["is_verified"] = False
        if not update_data:
            return current_user
        return await self.repo.update(current_user, update_data)

    async def delete_me(self, current_user: User) -> None:
        if current_user.is_superuser:
            raise ForbiddenError("Super users are not allowed to delete themselves")
        await self.repo.delete(current_user)

    async def get_by_id_for_user(self, user_id: uuid.UUID, current_user: User) -> User:
        user = await self.repo.get(user_id)
        if user is None:
            raise NotFoundError("User not found")
        if user.id != current_user.id and not current_user.is_superuser:
            raise ForbiddenError("The user doesn't have enough privileges")
        return user

    async def update_user(self, user_id: uuid.UUID, user_in: UserUpdate) -> User:
        user = await self.repo.get(user_id)
        if not user:
            raise NotFoundError("User not found")
        if user_in.email and user_in.email != user.email:
            if await self.repo.get_by_email(user_in.email):
                raise ConflictError("A user with this email already exists")
        update_data = user_in.model_dump(exclude_unset=True)
        if "password" in update_data:
            password = update_data.pop("password")
            _validate_password(password)
            update_data["hashed_password"] = get_password_hash(password)
        return await self.repo.update(user, update_data)

    async def delete_user(self, user_id: uuid.UUID, current_superuser: User) -> None:
        if user_id == current_superuser.id:
            raise ForbiddenError("Super users are not allowed to delete themselves")
        user = await self.repo.get(user_id)
        if not user:
            raise NotFoundError("User not found")
        await self.repo.delete(user)

    async def list_users(self, *, skip: int, limit: int) -> tuple[list[User], int]:
        return await self.repo.list_paginated(skip=skip, limit=limit)

    async def create_user_as_admin(
        self,
        *,
        email: str,
        password: str,
        full_name: str | None,
        is_superuser: bool,
    ) -> User:
        if await self.repo.get_by_email(email):
            raise ConflictError("A user with this email already exists")
        _validate_password(password)
        user_create = UserCreate(
            email=email, password=password, full_name=full_name, is_superuser=is_superuser
        )
        return await self.repo.create(user_create, get_password_hash(password))

    async def update_user_as_admin(
        self,
        user_id: uuid.UUID,
        *,
        email: str | None,
        password: str | None,
        full_name: str | None,
        is_superuser: bool | None,
        is_active: bool | None,
    ) -> User:
        user = await self.repo.get(user_id)
        if not user:
            raise NotFoundError("User not found")
        update_data: dict[str, Any] = {}
        if email and email != user.email:
            if await self.repo.get_by_email(email):
                raise ConflictError("A user with this email already exists")
            update_data["email"] = email
            update_data["is_verified"] = False
        if password:
            _validate_password(password)
            update_data["hashed_password"] = get_password_hash(password)
        if full_name is not None:
            update_data["full_name"] = full_name
        if is_superuser is not None:
            update_data["is_superuser"] = is_superuser
        if is_active is not None:
            update_data["is_active"] = is_active
        if not update_data:
            return user
        return await self.repo.update(user, update_data)

    async def create_user_private(
        self,
        *,
        email: str,
        password: str,
        full_name: str,
        is_superuser: bool,
        is_verified: bool,
    ) -> User:
        user_create = UserCreate(
            email=email, password=password, full_name=full_name, is_superuser=is_superuser
        )
        user = await self.repo.create(user_create, get_password_hash(password))
        if is_verified:
            user = await self.repo.update(user, {"is_verified": True})
        return user
