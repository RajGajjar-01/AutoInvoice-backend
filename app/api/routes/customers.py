import uuid
from typing import Any

from fastapi import APIRouter

from app.api.deps import CurrentUser, CustomerServiceDep
from app.schemas import (
    CustomerCreate,
    CustomerPublic,
    CustomersPublic,
    CustomerUpdate,
)

router = APIRouter(prefix="/customers", tags=["customers"])


@router.get("/", response_model=CustomersPublic)
async def read_customers(
    current_user: CurrentUser, customer_service: CustomerServiceDep, skip: int = 0, limit: int = 100
) -> Any:
    customers, count = await customer_service.list_items(current_user.id, skip=skip, limit=limit)
    return CustomersPublic(data=customers, count=count)


@router.get("/{id}", response_model=CustomerPublic)
async def read_customer(
    current_user: CurrentUser, customer_service: CustomerServiceDep, id: uuid.UUID
) -> Any:
    return await customer_service.get_owned(id, current_user.id)


@router.post("/", response_model=CustomerPublic, status_code=201)
async def create_customer(
    *, current_user: CurrentUser, customer_service: CustomerServiceDep, customer_in: CustomerCreate
) -> Any:
    return await customer_service.create(customer_in, current_user.id)


@router.put("/{id}", response_model=CustomerPublic)
async def update_customer(
    *,
    current_user: CurrentUser,
    customer_service: CustomerServiceDep,
    id: uuid.UUID,
    customer_in: CustomerUpdate,
) -> Any:
    return await customer_service.update(id, current_user.id, customer_in)


@router.delete("/{id}", status_code=204)
async def delete_customer(
    current_user: CurrentUser, customer_service: CustomerServiceDep, id: uuid.UUID
) -> None:
    await customer_service.delete(id, current_user.id)
