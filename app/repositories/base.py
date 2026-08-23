import uuid
from typing import Generic, TypeVar

from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.exceptions import ForbiddenError, NotFoundError

ModelType = TypeVar("ModelType", bound=SQLModel)


class BaseRepository(Generic[ModelType]):
    model: type[ModelType]

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, id: uuid.UUID) -> ModelType | None:
        return await self.session.get(self.model, id)

    async def add(self, obj: ModelType) -> ModelType:
        self.session.add(obj)
        await self.session.commit()
        await self.session.refresh(obj)
        return obj

    async def delete(self, obj: ModelType) -> None:
        await self.session.delete(obj)
        await self.session.commit()


async def get_owned(
    repo: BaseRepository[ModelType],
    obj_id: uuid.UUID,
    owner_id: uuid.UUID,
    not_found_message: str,
) -> ModelType:
    obj = await repo.get(obj_id)
    if not obj:
        raise NotFoundError(not_found_message)
    if obj.owner_id != owner_id:  # type: ignore[attr-defined]
        raise ForbiddenError("Not enough permissions")
    return obj
