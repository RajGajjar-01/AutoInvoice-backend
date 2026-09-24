from typing import Any

from sqlmodel import col, select

from app.models import User
from app.repositories.base import BaseRepository
from app.schemas import UserCreate


class UserRepository(BaseRepository[User]):
    model = User

    async def get_by_email(self, email: str) -> User | None:
        statement = select(User).where(User.email == email)
        result = await self.session.exec(statement)
        return result.first()

    async def get_by_google_sub(self, google_sub: str) -> User | None:
        statement = select(User).where(User.google_sub == google_sub)
        result = await self.session.exec(statement)
        return result.first()

    async def create(self, user_create: UserCreate, hashed_password: str | None) -> User:
        db_obj = User.model_validate(
            user_create, update={"hashed_password": hashed_password}
        )
        return await self.add(db_obj)

    async def update(self, db_user: User, update_data: dict[str, Any]) -> User:
        db_user.sqlmodel_update(update_data)
        return await self.add(db_user)

    async def list_paginated(self, *, skip: int, limit: int) -> tuple[list[User], int]:
        statement = select(User).order_by(col(User.created_at).desc())
        return await self.paginate(statement, skip=skip, limit=limit)
