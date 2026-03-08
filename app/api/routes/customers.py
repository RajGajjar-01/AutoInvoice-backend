import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlmodel import col, func, select

from app.api.deps import CurrentUser, SessionDep
from app.models import (
    Customer,
    CustomerCreate,
    CustomerPublic,
    CustomersPublic,
    CustomerUpdate,
    Message,
)

router = APIRouter(prefix="/customers", tags=["customers"])


@router.get("/", response_model=CustomersPublic)
def read_customers(
    session: SessionDep, current_user: CurrentUser, skip: int = 0, limit: int = 100
) -> Any:
    """Retrieve customers owned by the current user."""
    count_statement = (
        select(func.count())
        .select_from(Customer)
        .where(Customer.owner_id == current_user.id)
    )
    count = session.exec(count_statement).one()
    statement = (
        select(Customer)
        .where(Customer.owner_id == current_user.id)
        .order_by(col(Customer.created_at).desc())
        .offset(skip)
        .limit(limit)
    )
    customers = session.exec(statement).all()
    return CustomersPublic(data=customers, count=count)


@router.get("/{id}", response_model=CustomerPublic)
def read_customer(
    session: SessionDep, current_user: CurrentUser, id: uuid.UUID
) -> Any:
    """Get customer by ID."""
    customer = session.get(Customer, id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    if customer.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return customer


@router.post("/", response_model=CustomerPublic)
def create_customer(
    *, session: SessionDep, current_user: CurrentUser, customer_in: CustomerCreate
) -> Any:
    """Create a new customer."""
    customer = Customer.model_validate(
        customer_in, update={"owner_id": current_user.id}
    )
    session.add(customer)
    session.commit()
    session.refresh(customer)
    return customer


@router.put("/{id}", response_model=CustomerPublic)
def update_customer(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
    customer_in: CustomerUpdate,
) -> Any:
    """Update a customer."""
    customer = session.get(Customer, id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    if customer.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    update_dict = customer_in.model_dump(exclude_unset=True)
    from app.models import get_datetime_utc
    update_dict["updated_at"] = get_datetime_utc()
    customer.sqlmodel_update(update_dict)
    session.add(customer)
    session.commit()
    session.refresh(customer)
    return customer


@router.delete("/{id}")
def delete_customer(
    session: SessionDep, current_user: CurrentUser, id: uuid.UUID
) -> Message:
    """Delete a customer."""
    customer = session.get(Customer, id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    if customer.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    session.delete(customer)
    session.commit()
    return Message(message="Customer deleted successfully")
