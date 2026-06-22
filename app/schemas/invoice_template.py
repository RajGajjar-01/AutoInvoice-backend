import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


class InvoiceTemplateKind(str, Enum):
    built_in = "built_in"
    custom = "custom"
    imported_html = "imported_html"
    imported_pdf = "imported_pdf"
    imported_excel = "imported_excel"


class InvoiceTemplateBase(SQLModel):
    name: str = Field(max_length=255)
    kind: InvoiceTemplateKind
    is_active: bool = False
    built_in_id: str | None = Field(default=None, max_length=100)
    custom_data: dict[str, Any] | None = Field(default=None, sa_column=Column(JSONB))
    imported_html: str | None = None
    imported_pdf_data_url: str | None = None
    imported_excel_columns: dict[str, Any] | None = Field(
        default=None, sa_column=Column(JSONB)
    )
    imported_excel_data: list[dict[str, Any]] | None = Field(
        default=None, sa_column=Column(JSONB)
    )


class InvoiceTemplateCreate(InvoiceTemplateBase):
    pass


class InvoiceTemplateUpdate(SQLModel):
    name: str | None = Field(default=None, max_length=255)
    kind: InvoiceTemplateKind | None = None
    is_active: bool | None = None
    built_in_id: str | None = Field(default=None, max_length=100)
    custom_data: dict[str, Any] | None = None
    imported_html: str | None = None
    imported_pdf_data_url: str | None = None
    imported_excel_columns: dict[str, Any] | None = None
    imported_excel_data: list[dict[str, Any]] | None = None


class InvoiceTemplatePublic(InvoiceTemplateBase):
    id: uuid.UUID
    owner_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class InvoiceTemplatesPublic(SQLModel):
    data: list[InvoiceTemplatePublic]
    count: int
