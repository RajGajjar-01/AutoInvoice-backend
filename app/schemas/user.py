import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import EmailStr
from sqlmodel import Field, SQLModel

if TYPE_CHECKING:
    from app.models.user import User


class UserBase(SQLModel):
    email: EmailStr = Field(unique=True, index=True, max_length=255)
    is_active: bool = True
    is_superuser: bool = False
    full_name: str | None = Field(default=None, max_length=255)


class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)


class UserUpdate(UserBase):
    email: EmailStr | None = Field(default=None, max_length=255)
    password: str | None = Field(default=None, min_length=8, max_length=128)


class UserPublic(UserBase):
    id: uuid.UUID
    is_verified: bool = False
    avatar_url: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    google_connected: bool = False
    google_email: str | None = None
    has_password: bool = True

    @classmethod
    def from_user(cls, user: "User") -> "UserPublic":
        return cls.model_validate(
            user, update={"has_password": user.hashed_password is not None}
        )


class UsersPublic(SQLModel):
    data: list[UserPublic]
    count: int


class UserRegister(SQLModel):
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=255)


class UserUpdateMe(SQLModel):
    full_name: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = Field(default=None, max_length=255)


class UpdatePassword(SQLModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class SetPassword(SQLModel):
    new_password: str = Field(min_length=8, max_length=128)
