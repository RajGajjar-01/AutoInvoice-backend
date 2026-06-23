import uuid
from typing import Any

from app.core.time import get_datetime_utc
from app.exceptions import ForbiddenError, NotFoundError
from app.models import Invoice
from app.repositories.invoice_repository import InvoiceRepository
from app.schemas import InvoiceCreate, InvoiceUpdate


class InvoiceService:
    def __init__(self, repo: InvoiceRepository) -> None:
        self.repo = repo

    async def get_owned(self, invoice_id: uuid.UUID, owner_id: uuid.UUID) -> Invoice:
        invoice = await self.repo.get(invoice_id)
        if not invoice:
            raise NotFoundError("Invoice not found")
        if invoice.owner_id != owner_id:
            raise ForbiddenError("Not enough permissions")
        return invoice

    async def get_with_customer(self, invoice_id: uuid.UUID, owner_id: uuid.UUID) -> Invoice:
        invoice = await self.repo.get_with_customer(invoice_id, owner_id)
        if not invoice:
            raise NotFoundError("Invoice not found")
        if invoice.owner_id != owner_id:
            raise ForbiddenError("Not enough permissions")
        return invoice

    async def list_items(
        self,
        owner_id: uuid.UUID,
        *,
        skip: int,
        limit: int,
        status: str | None,
        document_type: str | None,
        customer_id: uuid.UUID | None,
    ) -> tuple[list[Invoice], int]:
        return await self.repo.list_filtered(
            owner_id,
            status=status,
            document_type=document_type,
            customer_id=customer_id,
            skip=skip,
            limit=limit,
        )

    async def get_dashboard_stats(
        self, owner_id: uuid.UUID, document_type: str | None
    ) -> dict[str, Any]:
        return await self.repo.get_dashboard_stats(owner_id, document_type)

    async def create(self, invoice_in: InvoiceCreate, owner_id: uuid.UUID) -> Invoice:
        invoice_data = invoice_in.model_dump()
        invoice_data["items"] = [
            item.model_dump() if hasattr(item, "model_dump") else item
            for item in invoice_in.items
        ]
        return await self.repo.create(invoice_data, owner_id)

    async def update(
        self, invoice_id: uuid.UUID, owner_id: uuid.UUID, invoice_in: InvoiceUpdate
    ) -> Invoice:
        invoice = await self.get_owned(invoice_id, owner_id)
        update_data = invoice_in.model_dump(exclude_unset=True)

        if "items" in update_data and update_data["items"] is not None:
            update_data["items"] = [
                item.model_dump() if hasattr(item, "model_dump") else item
                for item in update_data["items"]
            ]

        update_data["updated_at"] = get_datetime_utc()
        return await self.repo.update(invoice, update_data)

    async def delete(self, invoice_id: uuid.UUID, owner_id: uuid.UUID) -> None:
        invoice = await self.get_owned(invoice_id, owner_id)
        await self.repo.delete(invoice)
