import uuid
from datetime import date, datetime, timezone
from enum import Enum
from typing import Any, Generic, TypeVar

from pydantic import EmailStr
from sqlalchemy import Column, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, Relationship, SQLModel

T = TypeVar("T")


def get_datetime_utc() -> datetime:
    return datetime.now(timezone.utc)


class UserBase(SQLModel):
    email: EmailStr = Field(unique=True, index=True, max_length=255)
    is_active: bool = True
    is_superuser: bool = False
    full_name: str | None = Field(default=None, max_length=255)


class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)


class UserUpdate(UserBase):
    email: EmailStr | None = Field(default=None, max_length=255)
    password: str | None = Field(default=None, min_length=8, max_length=128)


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


class UserPublic(UserBase):
    id: uuid.UUID
    is_verified: bool = False
    avatar_url: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class UsersPublic(SQLModel):
    data: list[UserPublic]
    count: int


class UserRegister(SQLModel):
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=255)


class UserUpdateMe(SQLModel):
    full_name: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = Field(default=None, max_length=255)


class UpdatePassword(SQLModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class Message(SQLModel):
    message: str


class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"
    refresh_token: str | None = None
    expires_in: int | None = None


class TokenPayload(SQLModel):
    sub: str | None = None


class NewPassword(SQLModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


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


class Item(ItemBase, table=True):
    __tablename__ = "item"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),
    )
    updated_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),
    )
    owner_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, index=True, ondelete="CASCADE"
    )
    owner: User | None = Relationship(back_populates="items")


class ItemPublic(ItemBase):
    id: uuid.UUID
    owner_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class ItemsPublic(SQLModel):
    data: list[ItemPublic]
    count: int


class DataTableColumn(SQLModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=500)
    type: str = Field(min_length=1, max_length=100)
    mandatory: bool = False
    options: list[str] = Field(default_factory=list)


class DataTableBase(SQLModel):
    name: str = Field(min_length=1, max_length=255, index=True)
    description: str | None = Field(default=None, max_length=500)
    columns: list[dict[str, Any]] = Field(sa_column=Column(JSONB, nullable=False))


class DataTableCreate(DataTableBase):
    columns: list[DataTableColumn]


class DataTableUpdate(SQLModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=500)
    columns: list[DataTableColumn] | None = None


class DataTable(DataTableBase, table=True):
    __tablename__ = "data_tables"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    owner_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, index=True, ondelete="CASCADE"
    )
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),
        index=True,
    )
    updated_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),
    )

    owner: User | None = Relationship(back_populates="data_tables")
    rows: list["TableRow"] = Relationship(
        back_populates="table",
        cascade_delete=True,
        sa_relationship_kwargs={"passive_deletes": True},
    )
    reminders: list["TableReminder"] = Relationship(
        back_populates="table",
        cascade_delete=True,
        sa_relationship_kwargs={"passive_deletes": True},
    )


class DataTablePublic(DataTableBase):
    id: uuid.UUID
    owner_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class DataTableWithRows(DataTablePublic):
    rows: list["TableRowPublic"]
    reminders: list["TableReminderPublic"]


class TableRowBase(SQLModel):
    data: dict[str, Any] = Field(sa_column=Column(JSONB, nullable=False))


class TableRowCreate(TableRowBase):
    pass


class TableRowUpdate(TableRowBase):
    pass


class TableRow(TableRowBase, table=True):
    __tablename__ = "table_rows"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    table_id: uuid.UUID = Field(
        foreign_key="data_tables.id",
        nullable=False,
        index=True,
        ondelete="CASCADE",
    )
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),
        index=True,
    )

    table: DataTable | None = Relationship(back_populates="rows")


class TableRowPublic(TableRowBase):
    id: uuid.UUID
    table_id: uuid.UUID
    created_at: datetime


class TableReminderBase(SQLModel):
    reminder_data: dict[str, Any] = Field(sa_column=Column(JSONB, nullable=False))


class TableReminderCreate(TableReminderBase):
    pass


class TableReminder(TableReminderBase, table=True):
    __tablename__ = "table_reminders"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    table_id: uuid.UUID = Field(
        foreign_key="data_tables.id",
        nullable=False,
        index=True,
        ondelete="CASCADE",
    )
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),
    )

    table: DataTable | None = Relationship(back_populates="reminders")


class TableReminderPublic(TableReminderBase):
    id: uuid.UUID
    table_id: uuid.UUID
    created_at: datetime


class PaginatedResponse(SQLModel, Generic[T]):
    data: list[T]
    total: int
    page: int
    page_size: int
    total_pages: int


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


class CustomerPublic(CustomerBase):
    id: uuid.UUID
    owner_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class CustomersPublic(SQLModel):
    data: list[CustomerPublic]
    count: int


class DocumentType(str, Enum):
    invoice = "invoice"
    quotation = "quotation"
    proforma = "proforma"
    challan = "challan"


class InvoiceStatus(str, Enum):
    unpaid = "unpaid"
    paid = "paid"
    overdue = "overdue"
    draft = "draft"
    expired = "expired"
    accepted = "accepted"
    rejected = "rejected"


class InvoiceItemData(SQLModel):
    name: str
    description: str | None = None
    quantity: float = 1
    price: float = 0
    tax: float = 0
    unit: str | None = None
    hsn_code: str | None = None


class InvoiceBase(SQLModel):
    invoice_number: str = Field(max_length=50)
    document_type: DocumentType = DocumentType.invoice
    invoice_date: date
    due_date: date | None = None
    valid_until: date | None = None
    currency: str = Field(default="INR", max_length=10)
    subtotal: float = 0
    total_tax: float = 0
    grand_total: float = 0
    discount: float = 0
    notes: str | None = Field(default=None, max_length=2000)
    payment_terms: str | None = Field(default=None, max_length=500)
    status: InvoiceStatus = InvoiceStatus.unpaid
    place_of_supply: str | None = Field(default=None, max_length=100)
    reverse_charge: bool = False


class InvoiceCreate(InvoiceBase):
    customer_id: uuid.UUID
    items: list[InvoiceItemData] = []


class InvoiceUpdate(SQLModel):
    invoice_number: str | None = Field(default=None, max_length=50)
    document_type: DocumentType | None = None
    invoice_date: date | None = None
    due_date: date | None = None
    valid_until: date | None = None
    currency: str | None = Field(default=None, max_length=10)
    subtotal: float | None = None
    total_tax: float | None = None
    grand_total: float | None = None
    discount: float | None = None
    notes: str | None = Field(default=None, max_length=2000)
    payment_terms: str | None = Field(default=None, max_length=500)
    status: InvoiceStatus | None = None
    place_of_supply: str | None = Field(default=None, max_length=100)
    reverse_charge: bool | None = None
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


class InvoiceTemplate(InvoiceTemplateBase, table=True):
    __tablename__ = "invoice_templates"

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

    owner: User | None = Relationship(back_populates="invoice_templates")


class InvoiceTemplatePublic(InvoiceTemplateBase):
    id: uuid.UUID
    owner_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class InvoiceTemplatesPublic(SQLModel):
    data: list[InvoiceTemplatePublic]
    count: int


# ───────────────────────────────────────────────────────────────────────────────
# Company Settings
# ───────────────────────────────────────────────────────────────────────────────


class CompanySettingsBase(SQLModel):
    name: str = Field(min_length=1, max_length=255)
    gstin: str | None = Field(default=None, max_length=50)
    pan: str | None = Field(default=None, max_length=20)
    address: str | None = Field(default=None, max_length=500)
    city: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=100)
    pincode: str | None = Field(default=None, max_length=20)
    phone: str | None = Field(default=None, max_length=50)
    email: str | None = Field(default=None, max_length=255)
    website: str | None = Field(default=None, max_length=255)
    logo_url: str | None = Field(default=None, max_length=500)
    signature_url: str | None = Field(default=None, max_length=500)
    bank_name: str | None = Field(default=None, max_length=100)
    bank_account: str | None = Field(default=None, max_length=50)
    bank_ifsc: str | None = Field(default=None, max_length=20)
    bank_branch: str | None = Field(default=None, max_length=100)
    upi_id: str | None = Field(default=None, max_length=50)
    terms_and_conditions: str | None = Field(default=None, max_length=2000)
    invoice_prefix: str = Field(default="INV-", max_length=20)
    quotation_prefix: str = Field(default="QUO-", max_length=20)
    proforma_prefix: str = Field(default="PRO-", max_length=20)
    challan_prefix: str = Field(default="CHL-", max_length=20)


class CompanySettingsCreate(CompanySettingsBase):
    pass


class CompanySettingsUpdate(SQLModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    gstin: str | None = Field(default=None, max_length=50)
    pan: str | None = Field(default=None, max_length=20)
    address: str | None = Field(default=None, max_length=500)
    city: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=100)
    pincode: str | None = Field(default=None, max_length=20)
    phone: str | None = Field(default=None, max_length=50)
    email: str | None = Field(default=None, max_length=255)
    website: str | None = Field(default=None, max_length=255)
    logo_url: str | None = Field(default=None, max_length=500)
    signature_url: str | None = Field(default=None, max_length=500)
    bank_name: str | None = Field(default=None, max_length=100)
    bank_account: str | None = Field(default=None, max_length=50)
    bank_ifsc: str | None = Field(default=None, max_length=20)
    bank_branch: str | None = Field(default=None, max_length=100)
    upi_id: str | None = Field(default=None, max_length=50)
    terms_and_conditions: str | None = Field(default=None, max_length=2000)
    invoice_prefix: str | None = Field(default=None, max_length=20)
    quotation_prefix: str | None = Field(default=None, max_length=20)
    proforma_prefix: str | None = Field(default=None, max_length=20)
    challan_prefix: str | None = Field(default=None, max_length=20)


class CompanySettings(CompanySettingsBase, table=True):
    __tablename__ = "company_settings"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    owner_id: uuid.UUID = Field(
        foreign_key="user.id",
        nullable=False,
        unique=True,
        index=True,
        ondelete="CASCADE",
    )
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),
    )
    updated_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),
    )

    owner: User | None = Relationship(back_populates="company_settings")


class CompanySettingsPublic(CompanySettingsBase):
    id: uuid.UUID
    owner_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


# ───────────────────────────────────────────────────────────────────────────────
# Notifications
# ───────────────────────────────────────────────────────────────────────────────


class NotificationType(str, Enum):
    reminder = "reminder"
    due_date = "due_date"
    expiry = "expiry"
    info = "info"


class NotificationBase(SQLModel):
    type: NotificationType = NotificationType.info
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    table_id: uuid.UUID | None = None
    table_name: str | None = Field(default=None, max_length=255)
    row_id: uuid.UUID | None = None
    row_label: str | None = Field(default=None, max_length=255)
    read: bool = False
    scheduled_for: datetime | None = None


class NotificationCreate(NotificationBase):
    pass


class NotificationUpdate(SQLModel):
    read: bool | None = None


class Notification(NotificationBase, table=True):
    __tablename__ = "notifications"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    owner_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, index=True, ondelete="CASCADE"
    )
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),
        index=True,
    )

    owner: User | None = Relationship(back_populates="notifications")


class NotificationPublic(NotificationBase):
    id: uuid.UUID
    owner_id: uuid.UUID
    created_at: datetime


class NotificationsPublic(SQLModel):
    data: list[NotificationPublic]
    count: int
    unread_count: int
