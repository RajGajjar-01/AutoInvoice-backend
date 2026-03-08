import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlmodel import col, func, select

from app.api.deps import CurrentUser, SessionDep
from app.models import (
    Customer,
    DashboardStats,
    Invoice,
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
    session: SessionDep, current_user: CurrentUser
) -> Any:
    """Get dashboard statistics for the current user."""
    # Invoice counts
    total_invoices = session.exec(
        select(func.count())
        .select_from(Invoice)
        .where(Invoice.owner_id == current_user.id)
    ).one()

    paid_count = session.exec(
        select(func.count())
        .select_from(Invoice)
        .where(Invoice.owner_id == current_user.id, Invoice.status == InvoiceStatus.paid)
    ).one()

    unpaid_count = session.exec(
        select(func.count())
        .select_from(Invoice)
        .where(Invoice.owner_id == current_user.id, Invoice.status == InvoiceStatus.unpaid)
    ).one()

    overdue_count = session.exec(
        select(func.count())
        .select_from(Invoice)
        .where(Invoice.owner_id == current_user.id, Invoice.status == InvoiceStatus.overdue)
    ).one()

    # Total customers
    total_customers = session.exec(
        select(func.count())
        .select_from(Customer)
        .where(Customer.owner_id == current_user.id)
    ).one()

    # Total revenue (sum of grand_total for paid invoices)
    total_revenue = session.exec(
        select(func.coalesce(func.sum(Invoice.grand_total), 0))
        .where(Invoice.owner_id == current_user.id, Invoice.status == InvoiceStatus.paid)
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
    skip: int = 0,
    limit: int = 100,
    status: InvoiceStatus | None = None,
) -> Any:
    """Retrieve invoices owned by the current user, with optional status filter."""
    base_filter = Invoice.owner_id == current_user.id

    # Count
    count_stmt = select(func.count()).select_from(Invoice).where(base_filter)
    if status:
        count_stmt = count_stmt.where(Invoice.status == status)
    count = session.exec(count_stmt).one()

    # Data
    data_stmt = (
        select(Invoice)
        .where(base_filter)
        .order_by(col(Invoice.created_at).desc())
        .offset(skip)
        .limit(limit)
    )
    if status:
        data_stmt = data_stmt.where(Invoice.status == status)
    invoices = session.exec(data_stmt).all()

    return InvoicesPublic(data=invoices, count=count)


@router.get("/{id}", response_model=InvoiceWithCustomer)
def read_invoice(
    session: SessionDep, current_user: CurrentUser, id: uuid.UUID
) -> Any:
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
    """Create a new invoice."""
    # Verify customer exists and belongs to user
    customer = session.get(Customer, invoice_in.customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    if customer.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Customer does not belong to you")

    invoice_data = invoice_in.model_dump()
    # Convert InvoiceItemData to plain dicts for JSONB
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

    # If updating customer_id, verify it exists and belongs to user
    if "customer_id" in update_dict and update_dict["customer_id"] is not None:
        customer = session.get(Customer, update_dict["customer_id"])
        if not customer or customer.owner_id != current_user.id:
            raise HTTPException(status_code=404, detail="Customer not found")

    # Convert items to plain dicts if present
    if "items" in update_dict and update_dict["items"] is not None:
        update_dict["items"] = [
            item.model_dump() if hasattr(item, "model_dump") else item
            for item in update_dict["items"]
        ]

    from app.models import get_datetime_utc
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
