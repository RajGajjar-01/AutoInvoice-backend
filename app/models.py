import uuid
from datetime import date, datetime, timezone
from enum import Enum

from pydantic import EmailStr
from sqlalchemy import Column, DateTime, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, Relationship, SQLModel


def get_datetime_utc() -> datetime:
    return datetime.now(timezone.utc)


# Shared properties
class UserBase(SQLModel):
    email: EmailStr = Field(unique=True, index=True, max_length=255)
    is_active: bool = True
    is_superuser: bool = False
    full_name: str | None = Field(default=None, max_length=255)


# Properties to receive via API on creation
class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)


class UserRegister(SQLModel):
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=255)


# Properties to receive via API on update, all are optional
class UserUpdate(UserBase):
    email: EmailStr | None = Field(default=None, max_length=255)  # type: ignore
    password: str | None = Field(default=None, min_length=8, max_length=128)


class UserUpdateMe(SQLModel):
    full_name: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = Field(default=None, max_length=255)


class UpdatePassword(SQLModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


# Database model, database table inferred from class name
class User(UserBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    hashed_password: str
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
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


# Properties to return via API, id is always required
class UserPublic(UserBase):
    id: uuid.UUID
    created_at: datetime | None = None


class UsersPublic(SQLModel):
    data: list[UserPublic]
    count: int


# Shared properties
class ItemBase(SQLModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=255)


# Properties to receive on item creation
class ItemCreate(ItemBase):
    pass


# Properties to receive on item update
class ItemUpdate(ItemBase):
    title: str | None = Field(default=None, min_length=1, max_length=255)  # type: ignore


# Database model, database table inferred from class name
class Item(ItemBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    owner_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="CASCADE"
    )
    owner: User | None = Relationship(back_populates="items")


# Properties to return via API, id is always required
class ItemPublic(ItemBase):
    id: uuid.UUID
    owner_id: uuid.UUID
    created_at: datetime | None = None


class ItemsPublic(SQLModel):
    data: list[ItemPublic]
    count: int


# Generic message
class Message(SQLModel):
    message: str


# JSON payload containing access token
class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"


# Contents of JWT token
class TokenPayload(SQLModel):
    sub: str | None = None
    type: str | None = None


class NewPassword(SQLModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


# Data Tables Models

# Shared schema for a single DataTable column definition
class DataTableColumn(SQLModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=500)
    type: str = Field(min_length=1, max_length=100)
    mandatory: bool = False
    options: list[str] = Field(default_factory=list)


# Shared properties for DataTable
class DataTableBase(SQLModel):
    name: str = Field(min_length=1, max_length=255, index=True)
    description: str | None = Field(default=None, max_length=500)
    columns: list[dict] = Field(sa_column=Column(JSONB, nullable=False))


# Properties to receive via API on creation
class DataTableCreate(DataTableBase):
    columns: list[DataTableColumn]


# Properties to receive via API on update, all are optional
class DataTableUpdate(SQLModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=500)
    columns: list[DataTableColumn] | None = None


# Database model for DataTable
class DataTable(DataTableBase, table=True):
    __tablename__ = "data_tables"
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    owner_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, index=True, ondelete="CASCADE"
    )
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
        index=True
    )
    updated_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    
    # Relationships with cascade delete
    owner: User | None = Relationship(back_populates="data_tables")
    rows: list["TableRow"] = Relationship(
        back_populates="table",
        cascade_delete=True,
        sa_relationship_kwargs={"passive_deletes": True}
    )
    reminders: list["TableReminder"] = Relationship(
        back_populates="table",
        cascade_delete=True,
        sa_relationship_kwargs={"passive_deletes": True}
    )


# Properties to return via API
class DataTablePublic(DataTableBase):
    id: uuid.UUID
    owner_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


# DataTable with rows and reminders
class DataTableWithRows(DataTablePublic):
    rows: list["TableRowPublic"]
    reminders: list["TableReminderPublic"]


# Shared properties for TableRow
class TableRowBase(SQLModel):
    data: dict = Field(sa_column=Column(JSONB, nullable=False))


# Properties to receive via API on creation
class TableRowCreate(TableRowBase):
    pass


# Properties to receive via API on update
class TableRowUpdate(TableRowBase):
    pass


# Database model for TableRow
class TableRow(TableRowBase, table=True):
    __tablename__ = "table_rows"
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    table_id: uuid.UUID = Field(
        foreign_key="data_tables.id",
        nullable=False,
        index=True,
        ondelete="CASCADE"
    )
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
        index=True
    )
    
    # Relationship
    table: DataTable | None = Relationship(back_populates="rows")


# Properties to return via API
class TableRowPublic(TableRowBase):
    id: uuid.UUID
    table_id: uuid.UUID
    created_at: datetime


# Shared properties for TableReminder
class TableReminderBase(SQLModel):
    reminder_data: dict = Field(sa_column=Column(JSONB, nullable=False))


# Properties to receive via API on creation
class TableReminderCreate(TableReminderBase):
    pass


# Database model for TableReminder
class TableReminder(TableReminderBase, table=True):
    __tablename__ = "table_reminders"
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    table_id: uuid.UUID = Field(
        foreign_key="data_tables.id",
        nullable=False,
        index=True,
        ondelete="CASCADE"
    )
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    
    # Relationship
    table: DataTable | None = Relationship(back_populates="reminders")


# Properties to return via API
class TableReminderPublic(TableReminderBase):
    id: uuid.UUID
    table_id: uuid.UUID
    created_at: datetime


# Paginated response model
from typing import Generic, TypeVar

T = TypeVar('T')


class PaginatedResponse(SQLModel, Generic[T]):
    data: list[T]
    total: int
    page: int
    page_size: int
    total_pages: int


# ──────────────────────────────────────────────────────────
# Customer Models
# ──────────────────────────────────────────────────────────

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
    tags: list[str] = Field(default_factory=list, sa_column=Column(JSONB, nullable=False, server_default="[]"))
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


class Customer(CustomerBase, table=True):
    __tablename__ = "customers"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    owner_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, index=True, ondelete="CASCADE"
    )
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    updated_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )

    owner: User | None = Relationship(back_populates="customers")
    invoices: list["Invoice"] = Relationship(
        back_populates="customer", cascade_delete=True
    )


class CustomerPublic(CustomerBase):
    id: uuid.UUID
    owner_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class CustomersPublic(SQLModel):
    data: list[CustomerPublic]
    count: int


# ──────────────────────────────────────────────────────────
# Invoice Models
# ──────────────────────────────────────────────────────────

class InvoiceStatus(str, Enum):
    unpaid = "unpaid"
    paid = "paid"
    overdue = "overdue"


class InvoiceItemData(SQLModel):
    """Schema for a single line item embedded in the invoice JSONB."""
    name: str
    description: str | None = None
    quantity: float = 1
    price: float = 0
    tax: float = 0


class InvoiceBase(SQLModel):
    invoice_number: str = Field(max_length=50)
    invoice_date: date
    due_date: date | None = None
    currency: str = Field(default="INR", max_length=10)
    subtotal: float = 0
    total_tax: float = 0
    grand_total: float = 0
    notes: str | None = Field(default=None, max_length=2000)
    payment_terms: str | None = Field(default=None, max_length=500)
    status: InvoiceStatus = InvoiceStatus.unpaid


class InvoiceCreate(InvoiceBase):
    customer_id: uuid.UUID
    items: list[InvoiceItemData] = []


class InvoiceUpdate(SQLModel):
    invoice_date: date | None = None
    due_date: date | None = None
    currency: str | None = Field(default=None, max_length=10)
    subtotal: float | None = None
    total_tax: float | None = None
    grand_total: float | None = None
    notes: str | None = Field(default=None, max_length=2000)
    payment_terms: str | None = Field(default=None, max_length=500)
    status: InvoiceStatus | None = None
    customer_id: uuid.UUID | None = None
    items: list[InvoiceItemData] | None = None


class Invoice(InvoiceBase, table=True):
    __tablename__ = "invoices"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    owner_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, index=True, ondelete="CASCADE"
    )
    customer_id: uuid.UUID = Field(
        foreign_key="customers.id", nullable=False, index=True, ondelete="CASCADE"
    )
    items: list = Field(default=[], sa_column=Column(JSONB, nullable=False, server_default="[]"))
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    updated_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )

    owner: User | None = Relationship(back_populates="invoices")
    customer: Customer | None = Relationship(back_populates="invoices")


class InvoicePublic(InvoiceBase):
    id: uuid.UUID
    owner_id: uuid.UUID
    customer_id: uuid.UUID
    items: list[InvoiceItemData] = []
    created_at: datetime
    updated_at: datetime


class InvoiceWithCustomer(InvoicePublic):
    customer: CustomerPublic | None = None


class InvoicesPublic(SQLModel):
    data: list[InvoicePublic]
    count: int


class DashboardStats(SQLModel):
    total_invoices: int = 0
    paid_count: int = 0
    unpaid_count: int = 0
    overdue_count: int = 0
    total_customers: int = 0
    total_revenue: float = 0
