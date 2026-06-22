import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Column, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, Relationship

from app.core.time import get_datetime_utc
from app.models.customer import Customer
from app.models.user import User
from app.schemas.invoice import InvoiceBase


class Invoice(InvoiceBase, table=True):
    __tablename__ = "invoices"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    owner_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, index=True, ondelete="CASCADE"
    )
    customer_id: uuid.UUID = Field(
        foreign_key="customers.id", nullable=False, index=True, ondelete="CASCADE"
    )
    items: list[dict[str, Any]] = Field(
        default=[], sa_column=Column(JSONB, nullable=False, server_default="[]")
    )
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),
    )
    updated_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),
    )

    owner: User | None = Relationship(back_populates="invoices")
    customer: Customer | None = Relationship(back_populates="invoices")
