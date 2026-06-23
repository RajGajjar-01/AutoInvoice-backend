import uuid
from typing import Any

from sqlmodel import col, func, select

from app.models import Customer
from app.repositories.base import BaseRepository
from app.schemas import CustomerCreate


class CustomerRepository(BaseRepository[Customer]):
    model = Customer

    async def list_by_owner(
        self, owner_id: uuid.UUID, *, skip: int, limit: int
    ) -> tuple[list[Customer], int]:
        count_statement = (
            select(func.count()).select_from(Customer).where(Customer.owner_id == owner_id)
        )
        count_result = await self.session.exec(count_statement)
        count = count_result.one()

        statement = (
            select(Customer)
            .where(Customer.owner_id == owner_id)
            .order_by(col(Customer.created_at).desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.exec(statement)
        return list(result.all()), count

    async def create(self, customer_in: CustomerCreate, owner_id: uuid.UUID) -> Customer:
        customer = Customer.model_validate(customer_in, update={"owner_id": owner_id})
        return await self.add(customer)

    async def update(self, customer: Customer, update_data: dict[str, Any]) -> Customer:
        customer.sqlmodel_update(update_data)
        return await self.add(customer)
