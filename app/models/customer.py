import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime
from sqlmodel import Field, Relationship

from app.core.time import get_datetime_utc
from app.models.user import User
from app.schemas.customer import CustomerBase

if TYPE_CHECKING:
    from app.models.invoice import Invoice


class Customer(CustomerBase, table=True):
    __tablename__ = "customers"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    owner_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, index=True, ondelete="CASCADE"
    )
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),
    )
    updated_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),
    )

    owner: User | None = Relationship(back_populates="customers")
    invoices: list["Invoice"] = Relationship(
        back_populates="customer", cascade_delete=True
    )
