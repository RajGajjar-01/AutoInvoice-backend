import uuid
from datetime import datetime

from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


class CustomerBase(SQLModel):
    name: str = Field(min_length=1, max_length=255)
    party_type: str | None = Field(default="customer", max_length=20)
    phone: str | None = Field(default=None, max_length=50)
    whatsapp: str | None = Field(default=None, max_length=50)
    email: str | None = Field(default=None, max_length=255)
    billing_address: str | None = Field(default=None, max_length=500)
    shipping_address: str | None = Field(default=None, max_length=500)
    address: str | None = Field(default=None, max_length=500)
    gstin: str | None = Field(default=None, max_length=50)
    gst: str | None = Field(default=None, max_length=50)
    state: str | None = Field(default=None, max_length=100)
    tags: list[str] = Field(
        default_factory=list,
        sa_column=Column(JSONB, nullable=False, server_default="[]"),
    )
    opening_balance: float = Field(default=0)
    credit_limit: float | None = Field(default=None)
    payment_terms: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=1000)


class CustomerCreate(CustomerBase):
    pass


class CustomerUpdate(SQLModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    party_type: str | None = Field(default=None, max_length=20)
    phone: str | None = Field(default=None, max_length=50)
    whatsapp: str | None = Field(default=None, max_length=50)
    email: str | None = Field(default=None, max_length=255)
    billing_address: str | None = Field(default=None, max_length=500)
    shipping_address: str | None = Field(default=None, max_length=500)
    address: str | None = Field(default=None, max_length=500)
    gstin: str | None = Field(default=None, max_length=50)
    gst: str | None = Field(default=None, max_length=50)
    state: str | None = Field(default=None, max_length=100)
    tags: list[str] | None = None
    opening_balance: float | None = None
    credit_limit: float | None = None
    payment_terms: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=1000)


class CustomerPublic(CustomerBase):
    id: uuid.UUID
    owner_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class CustomersPublic(SQLModel):
    data: list[CustomerPublic]
    count: int
