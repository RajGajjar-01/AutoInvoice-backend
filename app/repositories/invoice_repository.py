import uuid
from typing import Any

from sqlalchemy.orm import selectinload
from sqlmodel import col, func, select

from app.models import Customer, Invoice
from app.repositories.base import BaseRepository


class InvoiceRepository(BaseRepository[Invoice]):
    model = Invoice

    async def get_by_id_and_owner(
        self, invoice_id: uuid.UUID, owner_id: uuid.UUID
    ) -> Invoice | None:
        statement = select(Invoice).where(
            Invoice.id == invoice_id, Invoice.owner_id == owner_id
        )
        result = await self.session.exec(statement)
        return result.first()

    async def get_with_customer(
        self, invoice_id: uuid.UUID, owner_id: uuid.UUID
    ) -> Invoice | None:
        statement = (
            select(Invoice)
            .where(Invoice.id == invoice_id, Invoice.owner_id == owner_id)
            .options(selectinload(Invoice.customer))  # type: ignore[arg-type]
        )
        result = await self.session.exec(statement)
        return result.first()

    async def list_filtered(
        self,
        owner_id: uuid.UUID,
        *,
        status: str | None,
        document_type: str | None,
        customer_id: uuid.UUID | None,
        skip: int,
        limit: int,
    ) -> tuple[list[Invoice], int]:
        base_filter = Invoice.owner_id == owner_id
        if status:
            base_filter = base_filter & (Invoice.status == status)
        if document_type:
            base_filter = base_filter & (Invoice.document_type == document_type)
        if customer_id:
            base_filter = base_filter & (Invoice.customer_id == customer_id)

        count_result = await self.session.exec(
            select(func.count()).select_from(Invoice).where(base_filter)
        )
        count = count_result.one()
        statement = (
            select(Invoice)
            .where(base_filter)
            .order_by(col(Invoice.created_at).desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.exec(statement)
        return list(result.all()), count

    async def get_dashboard_stats(
        self, owner_id: uuid.UUID, document_type: str | None
    ) -> dict[str, Any]:
        base_filter = Invoice.owner_id == owner_id
        if document_type:
            base_filter = base_filter & (Invoice.document_type == document_type)

        total_invoices = (
            await self.session.exec(
                select(func.count()).select_from(Invoice).where(base_filter)
            )
        ).one()

        paid_count = (
            await self.session.exec(
                select(func.count())
                .select_from(Invoice)
                .where(base_filter, Invoice.status == "paid")
            )
        ).one()

        unpaid_count = (
            await self.session.exec(
                select(func.count())
                .select_from(Invoice)
                .where(base_filter, Invoice.status == "unpaid")
            )
        ).one()

        overdue_count = (
            await self.session.exec(
                select(func.count())
                .select_from(Invoice)
                .where(base_filter, Invoice.status == "overdue")
            )
        ).one()

        total_customers = (
            await self.session.exec(
                select(func.count())
                .select_from(Customer)
                .where(Customer.owner_id == owner_id)
            )
        ).one()

        total_revenue = (
            await self.session.exec(
                select(func.coalesce(func.sum(Invoice.grand_total), 0)).where(
                    base_filter, Invoice.status == "paid"
                )
            )
        ).one()

        return {
            "total_invoices": total_invoices,
            "paid_count": paid_count,
            "unpaid_count": unpaid_count,
            "overdue_count": overdue_count,
            "total_customers": total_customers,
            "total_revenue": float(total_revenue),
        }

    async def create(
        self, invoice_data: dict[str, Any], owner_id: uuid.UUID
    ) -> Invoice:
        invoice_data["owner_id"] = owner_id
        db_invoice = Invoice(**invoice_data)
        return await self.add(db_invoice)

    async def update(self, invoice: Invoice, update_data: dict[str, Any]) -> Invoice:
        invoice.sqlmodel_update(update_data)
        return await self.add(invoice)
