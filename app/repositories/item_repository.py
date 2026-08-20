import uuid
from typing import Any

from sqlmodel import col, func, select

from app.models import Item
from app.repositories.base import BaseRepository
from app.schemas import ItemCreate


class ItemRepository(BaseRepository[Item]):
    model = Item

    async def get_by_id_and_owner(
        self, item_id: uuid.UUID, owner_id: uuid.UUID
    ) -> Item | None:
        statement = select(Item).where(Item.id == item_id, Item.owner_id == owner_id)
        result = await self.session.exec(statement)
        return result.first()

    async def list_filtered(
        self,
        owner_id: uuid.UUID,
        *,
        search: str | None,
        category: str | None,
        stock_status: str | None,
        skip: int,
        limit: int,
    ) -> tuple[list[Item], int]:
        base_filter: Any = Item.owner_id == owner_id

        if search:
            search_term = f"%{search}%"
            base_filter = (
                (col(Item.name).ilike(search_term))
                | (col(Item.description).ilike(search_term))
                | (col(Item.sku).ilike(search_term))
            ) & (Item.owner_id == owner_id)

        if category:
            base_filter = base_filter & (Item.category == category)

        if stock_status == "in_stock":
            base_filter = base_filter & (Item.stock >= Item.low_stock_threshold)
        elif stock_status == "low_stock":
            base_filter = base_filter & (
                (Item.stock > 0) & (Item.stock < Item.low_stock_threshold)
            )
        elif stock_status == "out_of_stock":
            base_filter = base_filter & (Item.stock == 0)

        count_result = await self.session.exec(
            select(func.count()).select_from(Item).where(base_filter)
        )
        count = count_result.one()
        statement = (
            select(Item)
            .where(base_filter)
            .order_by(col(Item.created_at).desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.exec(statement)
        return list(result.all()), count

    async def list_categories(self, owner_id: uuid.UUID) -> list[str]:
        statement = (
            select(Item.category)
            .where(Item.owner_id == owner_id, col(Item.category).isnot(None))
            .distinct()
        )
        result = await self.session.exec(statement)
        categories = result.all()
        return sorted([c for c in categories if c])

    async def create(self, item_in: ItemCreate, owner_id: uuid.UUID) -> Item:
        item = Item.model_validate(item_in, update={"owner_id": owner_id})
        return await self.add(item)

    async def update(self, item: Item, update_data: dict[str, Any]) -> Item:
        item.sqlmodel_update(update_data)
        return await self.add(item)
