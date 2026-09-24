import uuid
from datetime import timedelta
from typing import Any, Protocol

from app.core.security import (
    decrypt_token,
    encrypt_token,
    get_password_hash,
    verify_password,
)
from app.core.time import get_datetime_utc
from app.exceptions import (
    ConflictError,
    ForbiddenError,
    GoogleOnlyAccountError,
    NotFoundError,
    ValidationError,
)
from app.models import User
from app.repositories.user_repository import UserRepository
from app.schemas import UserCreate, UserRegister, UserUpdate, UserUpdateMe
from app.services import google_oauth_service

GOOGLE_TOKEN_REFRESH_MARGIN = timedelta(minutes=1)

DUMMY_HASH = "$argon2id$v=19$m=65536,t=3,p=4$MjQyZWE1MzBjYjJlZTI0Yw$YTU4NGM5ZTZmYjE2NzZlZjY0ZWY3ZGRkY2U2OWFjNjk"


class _HasId(Protocol):
    id: uuid.UUID


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
        if not db_user or db_user.hashed_password is None:
            verify_password(password, DUMMY_HASH)
            if db_user is not None:
                raise GoogleOnlyAccountError(
                    "This account uses Google sign-in. Continue with Google, "
                    "or set a password in Settings."
                )
            return None
        verified, updated_hash = verify_password(password, db_user.hashed_password)
        if not verified:
            return None
        if updated_hash:
            await self.repo.update(db_user, {"hashed_password": updated_hash})
        return db_user

    async def verify_email(self, db_user: User) -> User:
        return await self.repo.update(db_user, {"is_verified": True})

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

    async def delete_user(self, user_id: uuid.UUID, current_superuser: _HasId) -> None:
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
            email=email,
            password=password,
            full_name=full_name,
            is_superuser=is_superuser,
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

    async def save_google_tokens(
        self,
        user: User,
        *,
        google_sub: str,
        email: str,
        access_token: str,
        refresh_token: str | None,
        expires_in: int,
    ) -> User:
        existing = await self.repo.get_by_google_sub(google_sub)
        if existing and existing.id != user.id:
            raise ConflictError(
                "This Google account is already linked to a different user"
            )
        update_data: dict[str, Any] = {
            "google_sub": google_sub,
            "google_email": email,
            "google_access_token": encrypt_token(access_token),
            "google_token_expires_at": get_datetime_utc()
            + timedelta(seconds=expires_in),
        }
        if refresh_token:
            update_data["google_refresh_token"] = encrypt_token(refresh_token)
        return await self.repo.update(user, update_data)

    async def get_valid_google_access_token(self, user: User) -> str:
        if not user.google_refresh_token:
            raise ValidationError(
                "Connect your Google account in Settings to send invoice emails"
            )
        now = get_datetime_utc()
        if (
            user.google_access_token
            and user.google_token_expires_at
            and user.google_token_expires_at > now + GOOGLE_TOKEN_REFRESH_MARGIN
        ):
            return decrypt_token(user.google_access_token)

        tokens = google_oauth_service.refresh_access_token(
            decrypt_token(user.google_refresh_token)
        )
        access_token: str = tokens["access_token"]
        await self.repo.update(
            user,
            {
                "google_access_token": encrypt_token(access_token),
                "google_token_expires_at": now
                + timedelta(seconds=tokens.get("expires_in", 3600)),
            },
        )
        return access_token

    async def disconnect_google(self, user: User) -> User:
        if user.hashed_password is None:
            raise ValidationError(
                "Set a password in Settings before disconnecting Google, "
                "otherwise you won't be able to log in."
            )
        return await self.repo.update(
            user,
            {
                "google_sub": None,
                "google_email": None,
                "google_access_token": None,
                "google_refresh_token": None,
                "google_token_expires_at": None,
            },
        )

    async def login_with_google(
        self, *, sub: str, email: str, email_verified: bool, name: str | None,
        picture: str | None,
    ) -> User:
        user = await self.repo.get_by_google_sub(sub)
        if user:
            if not user.is_active:
                raise ForbiddenError("Inactive user")
            return user

        user = await self.repo.get_by_email(email)
        if user:
            if not (email_verified and user.is_verified):
                raise ConflictError(
                    "An account with this email already exists. Log in with your "
                    "password, then connect Google from Settings."
                )
            if not user.is_active:
                raise ForbiddenError("Inactive user")
            return await self.repo.update(user, {"google_sub": sub})

        user_create = UserCreate(
            email=email, password=str(uuid.uuid4()), full_name=name
        )
        db_obj = await self.repo.create(user_create, hashed_password=None)
        return await self.repo.update(
            db_obj,
            {"google_sub": sub, "is_verified": True, "avatar_url": picture},
        )

    async def create_user_private(
        self,
        *,
        email: str,
        password: str,
        full_name: str,
        is_superuser: bool,
        is_verified: bool,
    ) -> User:
        if await self.repo.get_by_email(email):
            raise ConflictError("A user with this email already exists")
        user_create = UserCreate(
            email=email,
            password=password,
            full_name=full_name,
            is_superuser=is_superuser,
        )
        user = await self.repo.create(user_create, get_password_hash(password))
        if is_verified:
            user = await self.repo.update(user, {"is_verified": True})
        return user
