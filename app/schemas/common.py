from typing import Generic, TypeVar

from sqlmodel import Field, SQLModel

T = TypeVar("T")


class Message(SQLModel):
    message: str


class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"
    refresh_token: str | None = None
    expires_in: int | None = None


class TokenPayload(SQLModel):
    sub: str | None = None


class NewPassword(SQLModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


class VerifyEmailRequest(SQLModel):
    code: str = Field(min_length=6, max_length=6)


class PaginatedResponse(SQLModel, Generic[T]):
    data: list[T]
    total: int
    page: int
    page_size: int
    total_pages: int


class GoogleAuthUrl(SQLModel):
    url: str


class GoogleStatus(SQLModel):
    connected: bool
    email: str | None = None
