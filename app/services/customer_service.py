import uuid

from app.core.time import get_datetime_utc
from app.exceptions import ForbiddenError, NotFoundError
from app.models import Customer
from app.repositories.customer_repository import CustomerRepository
from app.schemas import CustomerCreate, CustomerUpdate


class CustomerService:
    def __init__(self, repo: CustomerRepository) -> None:
        self.repo = repo

    async def get_owned(self, customer_id: uuid.UUID, owner_id: uuid.UUID) -> Customer:
        customer = await self.repo.get(customer_id)
        if not customer:
            raise NotFoundError("Customer not found")
        if customer.owner_id != owner_id:
            raise ForbiddenError("Not enough permissions")
        return customer

    async def list_items(
        self, owner_id: uuid.UUID, *, skip: int, limit: int
    ) -> tuple[list[Customer], int]:
        return await self.repo.list_by_owner(owner_id, skip=skip, limit=limit)

    async def create(self, customer_in: CustomerCreate, owner_id: uuid.UUID) -> Customer:
        return await self.repo.create(customer_in, owner_id)

    async def update(
        self, customer_id: uuid.UUID, owner_id: uuid.UUID, customer_in: CustomerUpdate
    ) -> Customer:
        customer = await self.get_owned(customer_id, owner_id)
        update_data = customer_in.model_dump(exclude_unset=True)
        update_data["updated_at"] = get_datetime_utc()
        return await self.repo.update(customer, update_data)

    async def delete(self, customer_id: uuid.UUID, owner_id: uuid.UUID) -> None:
        customer = await self.get_owned(customer_id, owner_id)
        await self.repo.delete(customer)
