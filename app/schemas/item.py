import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


class ItemBase(SQLModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=500)
    category: str | None = Field(default=None, max_length=100)
    sku: str | None = Field(default=None, max_length=50)
    unit: str | None = Field(default=None, max_length=20)
    price: float = Field(default=0)
    tax_rate: float = Field(default=0)
    stock: float = Field(default=0)
    low_stock_threshold: float = Field(default=5)
    stock_history: list[dict[str, Any]] = Field(
        default_factory=list,
        sa_column=Column(JSONB, nullable=False, server_default="[]"),
    )


class ItemCreate(ItemBase):
    pass


class ItemUpdate(SQLModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=500)
    category: str | None = Field(default=None, max_length=100)
    sku: str | None = Field(default=None, max_length=50)
    unit: str | None = Field(default=None, max_length=20)
    price: float | None = None
    tax_rate: float | None = None
    stock: float | None = None
    low_stock_threshold: float | None = None
    stock_history: list[dict[str, Any]] | None = None


class ItemPublic(ItemBase):
    id: uuid.UUID
    owner_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class ItemsPublic(SQLModel):
    data: list[ItemPublic]
    count: int
