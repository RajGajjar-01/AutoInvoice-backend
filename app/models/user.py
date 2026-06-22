import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime
from sqlmodel import Field, Relationship

from app.core.time import get_datetime_utc
from app.schemas.user import UserBase

if TYPE_CHECKING:
    from app.models.company_settings import CompanySettings
    from app.models.customer import Customer
    from app.models.invoice import Invoice
    from app.models.invoice_template import InvoiceTemplate
    from app.models.item import Item
    from app.models.notification import Notification
    from app.models.table import DataTable


class User(UserBase, table=True):
    __tablename__ = "user"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    hashed_password: str
    is_verified: bool = Field(default=False)
    avatar_url: str | None = Field(default=None, max_length=500)
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),
    )
    updated_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),
    )

    items: list["Item"] = Relationship(back_populates="owner", cascade_delete=True)
    data_tables: list["DataTable"] = Relationship(
        back_populates="owner", cascade_delete=True
    )
    customers: list["Customer"] = Relationship(
        back_populates="owner", cascade_delete=True
    )
    invoices: list["Invoice"] = Relationship(
        back_populates="owner", cascade_delete=True
    )
    invoice_templates: list["InvoiceTemplate"] = Relationship(
        back_populates="owner", cascade_delete=True
    )
    company_settings: "CompanySettings" = Relationship(
        back_populates="owner",
        cascade_delete=True,
        sa_relationship_kwargs={"uselist": False},
    )
    notifications: list["Notification"] = Relationship(
        back_populates="owner", cascade_delete=True
    )
