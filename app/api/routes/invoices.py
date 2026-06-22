import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from sqlmodel import col, func, select

from app.api.deps import CurrentUser, SessionDep
from app.core.time import get_datetime_utc
from app.models import Customer, Invoice
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
def get_dashboard_stats(
    session: SessionDep,
    current_user: CurrentUser,
    document_type: DocumentType | None = None,
) -> Any:
    """
    Get dashboard statistics for the current user.

    - **document_type**: Filter stats by document type (invoice, quotation, proforma, challan)
    """
    base_filter = Invoice.owner_id == current_user.id
    if document_type:
        base_filter = base_filter & (Invoice.document_type == document_type)

    total_invoices = session.exec(
        select(func.count()).select_from(Invoice).where(base_filter)
    ).one()

    paid_count = session.exec(
        select(func.count())
        .select_from(Invoice)
        .where(base_filter, Invoice.status == InvoiceStatus.paid)
    ).one()

    unpaid_count = session.exec(
        select(func.count())
        .select_from(Invoice)
        .where(base_filter, Invoice.status == InvoiceStatus.unpaid)
    ).one()

    overdue_count = session.exec(
        select(func.count())
        .select_from(Invoice)
        .where(base_filter, Invoice.status == InvoiceStatus.overdue)
    ).one()

    total_customers = session.exec(
        select(func.count())
        .select_from(Customer)
        .where(Customer.owner_id == current_user.id)
    ).one()

    total_revenue = session.exec(
        select(func.coalesce(func.sum(Invoice.grand_total), 0)).where(
            base_filter, Invoice.status == InvoiceStatus.paid
        )
    ).one()

    return DashboardStats(
        total_invoices=total_invoices,
        paid_count=paid_count,
        unpaid_count=unpaid_count,
        overdue_count=overdue_count,
        total_customers=total_customers,
        total_revenue=float(total_revenue),
    )


@router.get("/", response_model=InvoicesPublic)
def read_invoices(
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    status: InvoiceStatus | None = None,
    document_type: DocumentType | None = None,
    customer_id: uuid.UUID | None = None,
) -> Any:
    """
    Retrieve invoices owned by the current user.

    - **status**: Filter by invoice status
    - **document_type**: Filter by document type (invoice, quotation, proforma, challan)
    - **customer_id**: Filter by customer
    """
    base_filter = Invoice.owner_id == current_user.id

    if status:
        base_filter = base_filter & (Invoice.status == status)
    if document_type:
        base_filter = base_filter & (Invoice.document_type == document_type)
    if customer_id:
        base_filter = base_filter & (Invoice.customer_id == customer_id)

    count_stmt = select(func.count()).select_from(Invoice).where(base_filter)
    count = session.exec(count_stmt).one()

    data_stmt = (
        select(Invoice)
        .where(base_filter)
        .order_by(col(Invoice.created_at).desc())
        .offset(skip)
        .limit(limit)
    )
    invoices = session.exec(data_stmt).all()

    return InvoicesPublic(data=invoices, count=count)


@router.get("/{id}", response_model=InvoiceWithCustomer)
def read_invoice(session: SessionDep, current_user: CurrentUser, id: uuid.UUID) -> Any:
    """Get invoice by ID with customer details."""
    invoice = session.get(Invoice, id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if invoice.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return invoice


@router.post("/", response_model=InvoicePublic)
def create_invoice(
    *, session: SessionDep, current_user: CurrentUser, invoice_in: InvoiceCreate
) -> Any:
    """
    Create a new invoice/quotation/proforma/challan.

    Set **document_type** to create different document types:
    - invoice: Regular invoice
    - quotation: Price quote with validity period
    - proforma: Proforma invoice
    - challan: Delivery challan
    """
    customer = session.get(Customer, invoice_in.customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    if customer.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Customer does not belong to you")

    invoice_data = invoice_in.model_dump()
    invoice_data["items"] = [
        item.model_dump() if hasattr(item, "model_dump") else item
        for item in invoice_in.items
    ]
    invoice_data["owner_id"] = current_user.id
    db_invoice = Invoice(**invoice_data)
    session.add(db_invoice)
    session.commit()
    session.refresh(db_invoice)
    return db_invoice


@router.put("/{id}", response_model=InvoicePublic)
def update_invoice(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
    invoice_in: InvoiceUpdate,
) -> Any:
    """Update an invoice."""
    invoice = session.get(Invoice, id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if invoice.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    update_dict = invoice_in.model_dump(exclude_unset=True)

    if "customer_id" in update_dict and update_dict["customer_id"] is not None:
        customer = session.get(Customer, update_dict["customer_id"])
        if not customer or customer.owner_id != current_user.id:
            raise HTTPException(status_code=404, detail="Customer not found")

    if "items" in update_dict and update_dict["items"] is not None:
        update_dict["items"] = [
            item.model_dump() if hasattr(item, "model_dump") else item
            for item in update_dict["items"]
        ]

    update_dict["updated_at"] = get_datetime_utc()
    invoice.sqlmodel_update(update_dict)
    session.add(invoice)
    session.commit()
    session.refresh(invoice)
    return invoice


@router.delete("/{id}")
def delete_invoice(
    session: SessionDep, current_user: CurrentUser, id: uuid.UUID
) -> Message:
    """Delete an invoice."""
    invoice = session.get(Invoice, id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if invoice.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    session.delete(invoice)
    session.commit()
    return Message(message="Invoice deleted successfully")
