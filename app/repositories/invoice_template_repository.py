import uuid
from typing import Any

from sqlmodel import col, func, select

from app.models import InvoiceTemplate
from app.repositories.base import BaseRepository
from app.schemas import InvoiceTemplateCreate


class InvoiceTemplateRepository(BaseRepository[InvoiceTemplate]):
    model = InvoiceTemplate

    async def get_by_id_and_owner(
        self, template_id: uuid.UUID, owner_id: uuid.UUID
    ) -> InvoiceTemplate | None:
        statement = select(InvoiceTemplate).where(
            InvoiceTemplate.id == template_id, InvoiceTemplate.owner_id == owner_id
        )
        result = await self.session.exec(statement)
        return result.first()

    async def list_by_owner(
        self, owner_id: uuid.UUID, *, skip: int, limit: int
    ) -> tuple[list[InvoiceTemplate], int]:
        base_filter = InvoiceTemplate.owner_id == owner_id
        count_result = await self.session.exec(
            select(func.count()).select_from(InvoiceTemplate).where(base_filter)
        )
        count = count_result.one()
        statement = (
            select(InvoiceTemplate)
            .where(base_filter)
            .order_by(col(InvoiceTemplate.updated_at).desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.exec(statement)
        return list(result.all()), count

    async def get_active_by_owner(self, owner_id: uuid.UUID) -> InvoiceTemplate | None:
        statement = select(InvoiceTemplate).where(
            InvoiceTemplate.owner_id == owner_id,
            InvoiceTemplate.is_active == True,  # noqa: E712
        )
        result = await self.session.exec(statement)
        return result.first()

    async def get_all_by_owner(self, owner_id: uuid.UUID) -> list[InvoiceTemplate]:
        statement = select(InvoiceTemplate).where(InvoiceTemplate.owner_id == owner_id)
        result = await self.session.exec(statement)
        return list(result.all())

    async def create(self, template_in: InvoiceTemplateCreate, owner_id: uuid.UUID) -> InvoiceTemplate:
        template = InvoiceTemplate.model_validate(template_in, update={"owner_id": owner_id})
        return await self.add(template)

    async def update(self, template: InvoiceTemplate, update_data: dict[str, Any]) -> InvoiceTemplate:
        template.sqlmodel_update(update_data)
        return await self.add(template)
