import uuid

from app.core.time import get_datetime_utc
from app.models import Customer
from app.repositories.base import get_owned
from app.repositories.customer_repository import CustomerRepository
from app.schemas import CustomerCreate, CustomerUpdate


class CustomerService:
    def __init__(self, repo: CustomerRepository) -> None:
        self.repo = repo

    async def get_owned(self, customer_id: uuid.UUID, owner_id: uuid.UUID) -> Customer:
        return await get_owned(self.repo, customer_id, owner_id, "Customer not found")

    async def list_items(
        self, owner_id: uuid.UUID, *, skip: int, limit: int
    ) -> tuple[list[Customer], int]:
        return await self.repo.list_by_owner(owner_id, skip=skip, limit=limit)

    async def create(
        self, customer_in: CustomerCreate, owner_id: uuid.UUID
    ) -> Customer:
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
