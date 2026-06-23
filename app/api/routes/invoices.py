import uuid
from typing import Any

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, InvoiceServiceDep
from app.schemas import (
    DashboardStats,
    DocumentType,
    InvoiceCreate,
    InvoicePublic,
    InvoicesPublic,
    InvoiceStatus,
    InvoiceUpdate,
    InvoiceWithCustomer,
    Message,
)

router = APIRouter(prefix="/invoices", tags=["invoices"])


@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats(
    current_user: CurrentUser,
    invoice_service: InvoiceServiceDep,
    document_type: DocumentType | None = None,
) -> Any:
    stats = await invoice_service.get_dashboard_stats(current_user.id, document_type)
    return DashboardStats(**stats)


@router.get("/", response_model=InvoicesPublic)
async def read_invoices(
    current_user: CurrentUser,
    invoice_service: InvoiceServiceDep,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    status: InvoiceStatus | None = None,
    document_type: DocumentType | None = None,
    customer_id: uuid.UUID | None = None,
) -> Any:
    invoices, count = await invoice_service.list_items(
        current_user.id,
        skip=skip,
        limit=limit,
        status=status,
        document_type=document_type,
        customer_id=customer_id,
    )
    return InvoicesPublic(data=invoices, count=count)


@router.get("/{id}", response_model=InvoiceWithCustomer)
async def read_invoice(
    current_user: CurrentUser, invoice_service: InvoiceServiceDep, id: uuid.UUID
) -> Any:
    return await invoice_service.get_with_customer(id, current_user.id)


@router.post("/", response_model=InvoicePublic)
async def create_invoice(
    *, current_user: CurrentUser, invoice_service: InvoiceServiceDep, invoice_in: InvoiceCreate
) -> Any:
    return await invoice_service.create(invoice_in, current_user.id)


@router.put("/{id}", response_model=InvoicePublic)
async def update_invoice(
    *,
    current_user: CurrentUser,
    invoice_service: InvoiceServiceDep,
    id: uuid.UUID,
    invoice_in: InvoiceUpdate,
) -> Any:
    return await invoice_service.update(id, current_user.id, invoice_in)


@router.delete("/{id}")
async def delete_invoice(
    current_user: CurrentUser, invoice_service: InvoiceServiceDep, id: uuid.UUID
) -> Message:
    await invoice_service.delete(id, current_user.id)
    return Message(message="Invoice deleted successfully")
