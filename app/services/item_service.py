import uuid

from app.core.time import get_datetime_utc
from app.exceptions import ForbiddenError, NotFoundError, ValidationError
from app.models import Item
from app.repositories.item_repository import ItemRepository
from app.schemas import ItemCreate, ItemUpdate


class ItemService:
    def __init__(self, repo: ItemRepository) -> None:
        self.repo = repo

    async def get_owned(self, item_id: uuid.UUID, owner_id: uuid.UUID) -> Item:
        item = await self.repo.get(item_id)
        if not item:
            raise NotFoundError("Item not found")
        if item.owner_id != owner_id:
            raise ForbiddenError("Not enough permissions")
        return item

    async def list_items(
        self,
        owner_id: uuid.UUID,
        *,
        skip: int,
        limit: int,
        search: str | None,
        category: str | None,
        stock_status: str | None,
    ) -> tuple[list[Item], int]:
        return await self.repo.list_filtered(
            owner_id,
            search=search,
            category=category,
            stock_status=stock_status,
            skip=skip,
            limit=limit,
        )

    async def create(self, item_in: ItemCreate, owner_id: uuid.UUID) -> Item:
        return await self.repo.create(item_in, owner_id)

    async def update(
        self, item_id: uuid.UUID, owner_id: uuid.UUID, item_in: ItemUpdate
    ) -> Item:
        item = await self.get_owned(item_id, owner_id)
        update_data = item_in.model_dump(exclude_unset=True)
        update_data["updated_at"] = get_datetime_utc()
        return await self.repo.update(item, update_data)

    async def delete(self, item_id: uuid.UUID, owner_id: uuid.UUID) -> None:
        item = await self.get_owned(item_id, owner_id)
        await self.repo.delete(item)

    async def adjust_stock(
        self,
        item_id: uuid.UUID,
        owner_id: uuid.UUID,
        *,
        quantity: float,
        reason: str | None,
        reference: str | None,
    ) -> Item:
        item = await self.get_owned(item_id, owner_id)
        new_stock = item.stock + quantity
        if new_stock < 0:
            raise ValidationError("Insufficient stock")

        stock_entry = {
            "date": get_datetime_utc().isoformat(),
            "quantity": quantity,
            "previous_stock": item.stock,
            "new_stock": new_stock,
            "reason": reason or "adjustment",
            "reference": reference,
        }
        update_data = {
            "stock": new_stock,
            "stock_history": item.stock_history + [stock_entry],
            "updated_at": get_datetime_utc(),
        }
        return await self.repo.update(item, update_data)

    async def list_categories(self, owner_id: uuid.UUID) -> list[str]:
        return await self.repo.list_categories(owner_id)
