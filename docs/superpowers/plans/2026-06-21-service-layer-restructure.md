# Backend Layered Restructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the flat `app/models.py` + `app/crud.py` + fat-route structure with `app/models/` (tables) + `app/schemas/` (DTOs) + `app/repositories/` (async data access) + `app/services/` (business rules) + thin async routes, for every domain in the backend.

**Architecture:** Repositories extend a generic `BaseRepository[ModelType]` and do filtering/pagination only, on top of `AsyncSession` (SQLModel's async extension). Services own ownership checks, validation, and orchestration, raising a shared exception hierarchy (`NotFoundError`/`ForbiddenError`/`ConflictError`/`ValidationError`) that global FastAPI exception handlers translate to HTTP responses matching today's exact status codes and `detail` strings. Routes become a single `await`ed service call each. Alembic, bootstrap scripts, and test fixtures stay on the existing sync `Session`/`engine` — only the request-serving path goes async.

**Tech Stack:** FastAPI, SQLModel/SQLAlchemy 2.0 (`AsyncSession` on psycopg3 for the request path; sync `Session` on psycopg3 for Alembic/bootstrap/tests), pytest, mypy --strict, ruff.

## Global Constraints

- No change to API response shapes, status codes, or `detail` strings for any existing endpoint — verified by the existing test suite (`tests/api/routes/test_items.py`, `test_tables.py`, `test_users.py`, `test_login.py`, `test_private.py`, `tests/crud/test_user.py`) staying green throughout.
- `ConflictError` maps to HTTP 400 (not 409) — every existing "already exists" conflict in this codebase already returns 400 (see `auth.py` signup, `company_settings.py` create), so 409 would break `tests/api/routes/test_login.py::test_signup_existing_user` and others.
- `NotFoundError` → 404, `ForbiddenError` → 403, `ValidationError` → 422 (matches existing `HTTPException` usage being replaced).
- The request path (`deps.py` → routes → services → repositories) uses `AsyncSession`; Alembic, `init_db`/bootstrap scripts, and test fixtures (`tests/conftest.py`, `tests/utils/*.py`) keep using the existing sync `Session`/`engine` unchanged. No `pytest-asyncio` is needed — `TestClient` drives the ASGI event loop internally regardless of whether routes are sync or async.
- Single driver: **psycopg3** (already `psycopg[binary]>=3.2.0,<4.0.0` in `pyproject.toml`) for both sync and async — no new dependency. SQLAlchemy picks sync vs async based on `create_engine` vs `create_async_engine`, both against the same `postgresql+psycopg://` URL scheme.
- `mypy --strict` and `ruff check` must pass after every task (per `pyproject.toml`).
- Run tests with: `cd /home/rajgajjar04/Projects/AutoInvoice/backend && .venv/bin/pytest -q`
- Run mypy with: `cd /home/rajgajjar04/Projects/AutoInvoice/backend && .venv/bin/mypy app`
- Run ruff with: `cd /home/rajgajjar04/Projects/AutoInvoice/backend && .venv/bin/ruff check app tests`

---

## Task 1: Split `app/models.py` into `app/models/` + `app/schemas/` packages

This is a pure structural split — zero behavior change, and **entirely unaffected by the async decision** (models and schemas are plain data classes; no session/query code lives here). It must happen as one atomic task because Python cannot have both `app/models.py` and `app/models/` (a package) coexist: the old file is deleted in this same task as the new packages are created. Every later task builds repositories/services/routes on top of the already-split `app.models` / `app.schemas`.

**Files:**
- Create: `app/core/time.py`
- Create: `app/schemas/__init__.py`, `app/schemas/common.py`, `app/schemas/user.py`, `app/schemas/item.py`, `app/schemas/table.py`, `app/schemas/customer.py`, `app/schemas/invoice.py`, `app/schemas/invoice_template.py`, `app/schemas/company_settings.py`, `app/schemas/notification.py`
- Create: `app/models/__init__.py`, `app/models/user.py`, `app/models/item.py`, `app/models/table.py`, `app/models/customer.py`, `app/models/invoice.py`, `app/models/invoice_template.py`, `app/models/company_settings.py`, `app/models/notification.py`
- Delete: `app/models.py`
- Modify: `app/crud.py`, `app/core/db.py`, `app/api/deps.py`, `app/api/routes/admin.py`, `app/api/routes/auth.py`, `app/api/routes/company_settings.py`, `app/api/routes/customers.py`, `app/api/routes/invoice_templates.py`, `app/api/routes/invoices.py`, `app/api/routes/items.py`, `app/api/routes/notifications.py`, `app/api/routes/private.py`, `app/api/routes/tables.py`, `app/api/routes/users.py`, `app/api/routes/utils.py`, `app/alembic/env.py`
- Modify: `tests/conftest.py`, `tests/utils/user.py`, `tests/utils/item.py`, `tests/crud/test_user.py`, `tests/api/routes/test_users.py`, `tests/api/routes/test_items.py`, `tests/api/routes/test_tables.py` (only the import lines — no test logic changes)

**Interfaces:**
- Produces: `app.models.{User,Item,DataTable,TableRow,TableReminder,Customer,Invoice,InvoiceTemplate,CompanySettings,Notification}` (table classes, same names as before). `app.schemas.{...}` (all `*Base/Create/Update/Public` DTOs, enums, `Message`, `Token`, `TokenPayload`, `NewPassword`, `PaginatedResponse`). `app.core.time.get_datetime_utc()`.

- [ ] **Step 1: Create `app/core/time.py`**

```python
from datetime import datetime, timezone


def get_datetime_utc() -> datetime:
    return datetime.now(timezone.utc)
```

- [ ] **Step 2: Create `app/schemas/common.py`**

```python
from typing import Generic, TypeVar

from sqlmodel import Field, SQLModel

T = TypeVar("T")


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


class PaginatedResponse(SQLModel, Generic[T]):
    data: list[T]
    total: int
    page: int
    page_size: int
    total_pages: int
```

- [ ] **Step 3: Create `app/schemas/user.py`**

```python
import uuid
from datetime import datetime

from pydantic import EmailStr
from sqlmodel import Field, SQLModel


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
```

- [ ] **Step 4: Create `app/models/user.py`**

```python
import uuid
from datetime import datetime

from sqlalchemy import DateTime
from sqlmodel import Field, Relationship

from app.core.time import get_datetime_utc
from app.schemas.user import UserBase


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
```

- [ ] **Step 5: Create `app/schemas/item.py`**

```python
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
```

- [ ] **Step 6: Create `app/models/item.py`**

```python
import uuid
from datetime import datetime

from sqlalchemy import DateTime
from sqlmodel import Field, Relationship

from app.core.time import get_datetime_utc
from app.models.user import User
from app.schemas.item import ItemBase


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
```

- [ ] **Step 7: Create `app/schemas/table.py`**

```python
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


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


class DataTablePublic(DataTableBase):
    id: uuid.UUID
    owner_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class TableRowBase(SQLModel):
    data: dict[str, Any] = Field(sa_column=Column(JSONB, nullable=False))


class TableRowCreate(TableRowBase):
    pass


class TableRowUpdate(TableRowBase):
    pass


class TableRowPublic(TableRowBase):
    id: uuid.UUID
    table_id: uuid.UUID
    created_at: datetime


class DataTableWithRows(DataTablePublic):
    rows: list["TableRowPublic"]
    reminders: list["TableReminderPublic"]


class TableReminderBase(SQLModel):
    reminder_data: dict[str, Any] = Field(sa_column=Column(JSONB, nullable=False))


class TableReminderCreate(TableReminderBase):
    pass


class TableReminderPublic(TableReminderBase):
    id: uuid.UUID
    table_id: uuid.UUID
    created_at: datetime
```

- [ ] **Step 8: Create `app/models/table.py`**

```python
import uuid
from datetime import datetime

from sqlalchemy import DateTime
from sqlmodel import Field, Relationship

from app.core.time import get_datetime_utc
from app.models.user import User
from app.schemas.table import DataTableBase, TableReminderBase, TableRowBase


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
```

- [ ] **Step 9: Create `app/schemas/customer.py`**

```python
import uuid
from datetime import datetime
from typing import Any

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
```

- [ ] **Step 10: Create `app/models/customer.py`**

```python
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
```

- [ ] **Step 11: Create `app/schemas/invoice.py`**

```python
import uuid
from datetime import date, datetime
from enum import Enum

from sqlmodel import Field, SQLModel

from app.schemas.customer import CustomerPublic


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
```

- [ ] **Step 12: Create `app/models/invoice.py`**

```python
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
```

- [ ] **Step 13: Create `app/schemas/invoice_template.py`**

```python
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
```

- [ ] **Step 14: Create `app/models/invoice_template.py`**

```python
import uuid
from datetime import datetime

from sqlalchemy import DateTime
from sqlmodel import Field, Relationship

from app.core.time import get_datetime_utc
from app.models.user import User
from app.schemas.invoice_template import InvoiceTemplateBase


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
```

- [ ] **Step 15: Create `app/schemas/company_settings.py`**

```python
import uuid
from datetime import datetime

from sqlmodel import Field, SQLModel


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


class CompanySettingsPublic(CompanySettingsBase):
    id: uuid.UUID
    owner_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
```

- [ ] **Step 16: Create `app/models/company_settings.py`**

```python
import uuid
from datetime import datetime

from sqlalchemy import DateTime
from sqlmodel import Field, Relationship

from app.core.time import get_datetime_utc
from app.models.user import User
from app.schemas.company_settings import CompanySettingsBase


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
```

- [ ] **Step 17: Create `app/schemas/notification.py`**

```python
import uuid
from datetime import datetime
from enum import Enum

from sqlmodel import Field, SQLModel


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


class NotificationPublic(NotificationBase):
    id: uuid.UUID
    owner_id: uuid.UUID
    created_at: datetime


class NotificationsPublic(SQLModel):
    data: list[NotificationPublic]
    count: int
    unread_count: int
```

- [ ] **Step 18: Create `app/models/notification.py`**

```python
import uuid
from datetime import datetime

from sqlalchemy import DateTime
from sqlmodel import Field, Relationship

from app.core.time import get_datetime_utc
from app.models.user import User
from app.schemas.notification import NotificationBase


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
```

- [ ] **Step 19: Create `app/models/__init__.py`**

```python
from app.models.user import User
from app.models.item import Item
from app.models.customer import Customer
from app.models.table import DataTable, TableReminder, TableRow
from app.models.invoice import Invoice
from app.models.invoice_template import InvoiceTemplate
from app.models.company_settings import CompanySettings
from app.models.notification import Notification

__all__ = [
    "User",
    "Item",
    "Customer",
    "DataTable",
    "TableRow",
    "TableReminder",
    "Invoice",
    "InvoiceTemplate",
    "CompanySettings",
    "Notification",
]
```

- [ ] **Step 20: Create `app/schemas/__init__.py`**

```python
from app.schemas.common import (
    Message,
    NewPassword,
    PaginatedResponse,
    Token,
    TokenPayload,
)
from app.schemas.user import (
    UpdatePassword,
    UserCreate,
    UserPublic,
    UserRegister,
    UserUpdate,
    UserUpdateMe,
    UsersPublic,
)
from app.schemas.item import ItemCreate, ItemPublic, ItemsPublic, ItemUpdate
from app.schemas.customer import (
    CustomerCreate,
    CustomerPublic,
    CustomersPublic,
    CustomerUpdate,
)
from app.schemas.table import (
    DataTableColumn,
    DataTableCreate,
    DataTablePublic,
    DataTableUpdate,
    DataTableWithRows,
    TableReminderCreate,
    TableReminderPublic,
    TableRowCreate,
    TableRowPublic,
    TableRowUpdate,
)
from app.schemas.invoice import (
    DashboardStats,
    DocumentType,
    InvoiceCreate,
    InvoiceItemData,
    InvoicePublic,
    InvoicesPublic,
    InvoiceStatus,
    InvoiceUpdate,
    InvoiceWithCustomer,
)
from app.schemas.invoice_template import (
    InvoiceTemplateCreate,
    InvoiceTemplateKind,
    InvoiceTemplatePublic,
    InvoiceTemplatesPublic,
    InvoiceTemplateUpdate,
)
from app.schemas.company_settings import (
    CompanySettingsCreate,
    CompanySettingsPublic,
    CompanySettingsUpdate,
)
from app.schemas.notification import (
    NotificationCreate,
    NotificationPublic,
    NotificationsPublic,
    NotificationType,
    NotificationUpdate,
)

__all__ = [
    "Message", "NewPassword", "PaginatedResponse", "Token", "TokenPayload",
    "UpdatePassword", "UserCreate", "UserPublic", "UserRegister", "UserUpdate",
    "UserUpdateMe", "UsersPublic",
    "ItemCreate", "ItemPublic", "ItemsPublic", "ItemUpdate",
    "CustomerCreate", "CustomerPublic", "CustomersPublic", "CustomerUpdate",
    "DataTableColumn", "DataTableCreate", "DataTablePublic", "DataTableUpdate",
    "DataTableWithRows", "TableReminderCreate", "TableReminderPublic",
    "TableRowCreate", "TableRowPublic", "TableRowUpdate",
    "DashboardStats", "DocumentType", "InvoiceCreate", "InvoiceItemData",
    "InvoicePublic", "InvoicesPublic", "InvoiceStatus", "InvoiceUpdate",
    "InvoiceWithCustomer",
    "InvoiceTemplateCreate", "InvoiceTemplateKind", "InvoiceTemplatePublic",
    "InvoiceTemplatesPublic", "InvoiceTemplateUpdate",
    "CompanySettingsCreate", "CompanySettingsPublic", "CompanySettingsUpdate",
    "NotificationCreate", "NotificationPublic", "NotificationsPublic",
    "NotificationType", "NotificationUpdate",
]
```

- [ ] **Step 21: Delete the old flat `app/models.py`**

```bash
rm /home/rajgajjar04/Projects/AutoInvoice/backend/app/models.py
```

- [ ] **Step 22: Fix every importer's import lines (no logic changes)**

In each file below, split any `from app.models import (...)` block into a `from app.models import (...)` (table classes only) and `from app.schemas import (...)` (everything else), and replace `from app.models import get_datetime_utc` with `from app.core.time import get_datetime_utc`. Apply exactly these changes:

`app/crud.py` — replace the top import block:
```python
from app.models import (
    Customer,
    CustomerCreate,
    CustomerUpdate,
    DataTable,
    DataTableCreate,
    DataTableUpdate,
    Invoice,
    InvoiceCreate,
    InvoiceUpdate,
    Item,
    ItemCreate,
    TableReminder,
    TableReminderCreate,
    TableRow,
    TableRowCreate,
    User,
    UserCreate,
    UserUpdate,
    get_datetime_utc,
)
```
with:
```python
from app.core.time import get_datetime_utc
from app.models import Customer, DataTable, Invoice, Item, TableReminder, TableRow, User
from app.schemas import (
    CustomerCreate,
    CustomerUpdate,
    DataTableCreate,
    DataTableUpdate,
    InvoiceCreate,
    InvoiceUpdate,
    ItemCreate,
    TableReminderCreate,
    TableRowCreate,
    UserCreate,
    UserUpdate,
)
```

`app/core/db.py` — leave the engine/`init_db` body untouched for now (Task 2 rewrites this file for async); just confirm it still imports successfully after the split — no edit needed in this task since Task 2 supersedes it before any test run depends on the new shape. Skip this file.

`app/api/deps.py` — replace:
```python
from app import crud
```
```python
from app.models import TokenPayload, User
```
with (drop the unused `crud` import, it's never called in this file):
```python
from app.models import User
from app.schemas import TokenPayload
```

`app/api/routes/company_settings.py` — replace:
```python
from app.models import (
    CompanySettings,
    CompanySettingsCreate,
    CompanySettingsPublic,
    CompanySettingsUpdate,
    Message,
    get_datetime_utc,
)
```
with:
```python
from app.core.time import get_datetime_utc
from app.models import CompanySettings
from app.schemas import (
    CompanySettingsCreate,
    CompanySettingsPublic,
    CompanySettingsUpdate,
    Message,
)
```

`app/api/routes/auth.py` — replace:
```python
from app import crud
```
```python
from app.models import (
    Message,
    NewPassword,
    Token,
    UserCreate,
    UserPublic,
    UserUpdateMe,
)
```
with:
```python
from app import crud
from app.schemas import (
    Message,
    NewPassword,
    Token,
    UserCreate,
    UserPublic,
    UserUpdateMe,
)
```
Also replace both inline `from app.models import UserUpdate` occurrences (inside `reset_password` and `update_password`) with `from app.schemas import UserUpdate`.

`app/api/routes/utils.py` — replace:
```python
from app.models import Message
```
with:
```python
from app.schemas import Message
```

`app/api/routes/tables.py` — replace:
```python
from app.models import (
    DataTable,
    DataTableCreate,
    DataTablePublic,
    DataTableUpdate,
    DataTableWithRows,
    PaginatedResponse,
    TableReminder,
    TableReminderCreate,
    TableReminderPublic,
    TableRow,
    TableRowCreate,
    TableRowPublic,
    TableRowUpdate,
)
```
with:
```python
from app.models import DataTable, TableReminder, TableRow
from app.schemas import (
    DataTableCreate,
    DataTablePublic,
    DataTableUpdate,
    DataTableWithRows,
    PaginatedResponse,
    TableReminderCreate,
    TableReminderPublic,
    TableRowCreate,
    TableRowPublic,
    TableRowUpdate,
)
```

`app/api/routes/private.py` — replace:
```python
from app.models import (
    User,
    UserCreate,
    UserPublic,
)
```
with:
```python
from app.models import User
from app.schemas import UserCreate, UserPublic
```

`app/api/routes/users.py` — replace:
```python
from app.models import (
    Message,
    User,
    UserPublic,
    UserUpdate,
    UserUpdateMe,
    UsersPublic,
)
```
with:
```python
from app.models import User
from app.schemas import Message, UserPublic, UserUpdate, UserUpdateMe, UsersPublic
```

`app/api/routes/invoices.py` — replace:
```python
from app.models import (
    Customer,
    DashboardStats,
    DocumentType,
    Invoice,
    InvoiceCreate,
    InvoicePublic,
    InvoicesPublic,
    InvoiceStatus,
    InvoiceUpdate,
    InvoiceWithCustomer,
    Message,
    get_datetime_utc,
)
```
with:
```python
from app.core.time import get_datetime_utc
from app.models import Customer, Invoice
from app.schemas import (
    DashboardStats,
    DocumentType,
    InvoiceCreate,
    InvoicePublic,
    InvoicesPublic,
    InvoiceStatus,
    InvoiceUpdate,
    InvoiceWithCustomer,
    Message,
)
```

`app/api/routes/invoice_templates.py` — replace:
```python
from app.models import (
    InvoiceTemplate,
    InvoiceTemplateCreate,
    InvoiceTemplateKind,
    InvoiceTemplatePublic,
    InvoiceTemplatesPublic,
    InvoiceTemplateUpdate,
    Message,
    get_datetime_utc,
)
```
with:
```python
from app.core.time import get_datetime_utc
from app.models import InvoiceTemplate
from app.schemas import (
    InvoiceTemplateCreate,
    InvoiceTemplateKind,
    InvoiceTemplatePublic,
    InvoiceTemplatesPublic,
    InvoiceTemplateUpdate,
    Message,
)
```

`app/api/routes/items.py` — replace:
```python
from app.models import (
    Item,
    ItemCreate,
    ItemPublic,
    ItemsPublic,
    ItemUpdate,
    Message,
    get_datetime_utc,
)
```
with:
```python
from app.core.time import get_datetime_utc
from app.models import Item
from app.schemas import ItemCreate, ItemPublic, ItemsPublic, ItemUpdate, Message
```

`app/api/routes/notifications.py` — replace:
```python
from app.models import (
    Message,
    Notification,
    NotificationCreate,
    NotificationPublic,
    NotificationsPublic,
    NotificationType,
    NotificationUpdate,
    get_datetime_utc,
)
```
with:
```python
from app.core.time import get_datetime_utc
from app.models import Notification
from app.schemas import (
    Message,
    NotificationCreate,
    NotificationPublic,
    NotificationsPublic,
    NotificationType,
    NotificationUpdate,
)
```

`app/api/routes/admin.py` — replace:
```python
from app.models import (
    Message,
    PaginatedResponse,
    User,
    UserCreate,
    UserPublic,
    UserUpdate,
)
```
with:
```python
from app.models import User
from app.schemas import Message, PaginatedResponse, UserCreate, UserPublic, UserUpdate
```

`app/api/routes/customers.py` — replace:
```python
from app.models import (
    Customer,
    CustomerCreate,
    CustomerPublic,
    CustomersPublic,
    CustomerUpdate,
    Message,
)
```
with:
```python
from app.models import Customer
from app.schemas import CustomerCreate, CustomerPublic, CustomersPublic, CustomerUpdate, Message
```
Also replace the inline `from app.models import get_datetime_utc` (inside `update_customer`) with `from app.core.time import get_datetime_utc`.

`app/alembic/env.py` — replace:
```python
from app.models import SQLModel  # noqa
from app.core.config import settings # noqa
```
with:
```python
import app.models  # noqa: F401  (registers every table on SQLModel.metadata)
from app.core.config import settings  # noqa
from sqlmodel import SQLModel
```

`tests/conftest.py` — no change needed; `from app.models import Item, User` still resolves via the new package's `__init__.py`.

`tests/utils/user.py` — replace:
```python
from app.models import User, UserCreate
```
with:
```python
from app.models import User
from app.schemas import UserCreate
```

`tests/utils/item.py` — replace:
```python
from app.models import Item, ItemCreate
```
with:
```python
from app.models import Item
from app.schemas import ItemCreate
```

`tests/crud/test_user.py` — replace:
```python
from app.models import User, UserCreate, UserUpdate
```
with:
```python
from app.models import User
from app.schemas import UserCreate, UserUpdate
```

`tests/api/routes/test_users.py` — replace:
```python
from app.models import User, UserCreate
```
with:
```python
from app.models import User
from app.schemas import UserCreate
```

`tests/api/routes/test_items.py` — no change needed; only imports `User` (a table class) from `app.models`.

`tests/api/routes/test_tables.py` — replace the inline import inside `test_ownership_isolation`:
```python
    from app.models import UserUpdate
    from app import crud
```
with:
```python
    from app import crud
    from app.schemas import UserUpdate
```

- [ ] **Step 23: Run the full test suite to verify zero behavior change**

Run: `cd /home/rajgajjar04/Projects/AutoInvoice/backend && .venv/bin/pytest -q`
Expected: all existing tests pass (same pass count as before this task).

- [ ] **Step 24: Run mypy and ruff**

Run: `cd /home/rajgajjar04/Projects/AutoInvoice/backend && .venv/bin/mypy app && .venv/bin/ruff check app tests`
Expected: no errors. Fix any import-order or unused-import findings ruff reports (e.g. reorder `import app.models` above other imports in `alembic/env.py` if `ruff --fix` requests it).

- [ ] **Step 25: Commit**

```bash
git add app/core/time.py app/models app/schemas app/crud.py app/api app/alembic/env.py tests
git rm app/models.py
git commit -m "refactor: split app/models.py into models/ (tables) and schemas/ (DTOs) packages"
```

---

## Task 2: Async database foundation

Adds the async engine and converts the base request-time dependency chain (`get_db`, `SessionDep`, `get_current_user`) to `AsyncSession`. The sync `engine`/`Session` stays exactly as it is today for `init_db`/bootstrap — this task only adds the async path alongside it.

**Files:**
- Modify: `app/core/config.py`, `app/core/db.py`, `app/api/deps.py`

**Interfaces:**
- Produces: `app.core.config.settings.ASYNC_SQLALCHEMY_DATABASE_URI` (str). `app.core.db.async_engine` (`AsyncEngine`). `app.api.deps.SessionDep` = `Annotated[AsyncSession, Depends(get_db)]` (from `sqlmodel.ext.asyncio.session`).

- [ ] **Step 1: Add `ASYNC_SQLALCHEMY_DATABASE_URI` to `app/core/config.py`**

Add this computed field directly after the existing `SQLALCHEMY_DATABASE_URI` property (so it sits right next to it):

```python
    @computed_field  # type: ignore[prop-decorator]
    @property
    def ASYNC_SQLALCHEMY_DATABASE_URI(self) -> str:
        return self.SQLALCHEMY_DATABASE_URI.replace(
            "postgresql+psycopg://", "postgresql+psycopg_async://", 1
        )
```

Note: SQLAlchemy's `psycopg` (psycopg3) dialect uses the `postgresql+psycopg://` URL scheme for **both** sync and async — the sync-vs-async choice is made by which engine factory you call (`create_engine` vs `create_async_engine`), not by the URL. There is no real `postgresql+psycopg_async://` scheme; `create_async_engine` accepts the plain `postgresql+psycopg://` URL directly. Use this simpler, correct version instead:

```python
    @computed_field  # type: ignore[prop-decorator]
    @property
    def ASYNC_SQLALCHEMY_DATABASE_URI(self) -> str:
        return self.SQLALCHEMY_DATABASE_URI
```

This is intentionally a separate named setting (rather than reusing `SQLALCHEMY_DATABASE_URI` directly everywhere) so `app/core/db.py` and `app/alembic/env.py` each have an explicit, self-documenting name for which engine they're building.

- [ ] **Step 2: Add the async engine to `app/core/db.py`**

This file is fully rewritten in Task 3 (User/Auth domain) once `UserRepository` exists; for now, just add the async engine alongside the existing sync one. Modify `app/core/db.py` from:

```python
from sqlmodel import Session, create_engine, select

from app import crud
from app.core.config import settings
from app.models import User, UserCreate

engine = create_engine(str(settings.SQLALCHEMY_DATABASE_URI))


def init_db(session: Session) -> None:
    user = session.exec(
        select(User).where(User.email == settings.FIRST_SUPERUSER)
    ).first()
    if not user:
        user_in = UserCreate(
            email=settings.FIRST_SUPERUSER,
            password=settings.FIRST_SUPERUSER_PASSWORD,
            is_superuser=True,
        )
        user = crud.create_user(session=session, user_create=user_in)
```

to:

```python
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlmodel import Session, create_engine, select

from app import crud
from app.core.config import settings
from app.models import User, UserCreate

engine = create_engine(str(settings.SQLALCHEMY_DATABASE_URI))
async_engine: AsyncEngine = create_async_engine(str(settings.ASYNC_SQLALCHEMY_DATABASE_URI))


def init_db(session: Session) -> None:
    user = session.exec(
        select(User).where(User.email == settings.FIRST_SUPERUSER)
    ).first()
    if not user:
        user_in = UserCreate(
            email=settings.FIRST_SUPERUSER,
            password=settings.FIRST_SUPERUSER_PASSWORD,
            is_superuser=True,
        )
        user = crud.create_user(session=session, user_create=user_in)
```

(`init_db` itself is untouched here — it's bootstrap code, stays sync per the Global Constraints. Task 3 replaces its body to use `UserRepository` instead of `crud`, still synchronously.)

- [ ] **Step 3: Convert `app/api/deps.py`'s `get_db`/`SessionDep`/`get_current_user` to async**

Modify the top of `app/api/deps.py` from:

```python
import uuid
from collections.abc import Generator
from typing import Annotated

import jwt
from fastapi import Cookie, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from pydantic import ValidationError
from sqlmodel import Session

from app.core import security
from app.core.config import settings
from app.core.db import engine
from app.models import User
from app.schemas import TokenPayload

reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/login",
    auto_error=False,
)


def get_db() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_db)]
```

to:

```python
import uuid
from collections.abc import AsyncGenerator
from typing import Annotated

import jwt
from fastapi import Cookie, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from pydantic import ValidationError
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core import security
from app.core.config import settings
from app.core.db import async_engine
from app.models import User
from app.schemas import TokenPayload

reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/login",
    auto_error=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSession(async_engine) as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_db)]
```

Then modify `get_current_user` from:

```python
def get_current_user(session: SessionDep, token: TokenDep) -> User:
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[security.ALGORITHM]
        )
        token_data = TokenPayload(**payload)
    except (InvalidTokenError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        )

    if token_data.sub is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid token: missing subject",
        )

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid token type",
        )

    try:
        user_uuid = uuid.UUID(token_data.sub)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid user ID format",
        )

    user = session.get(User, user_uuid)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return user
```

to:

```python
async def get_current_user(session: SessionDep, token: TokenDep) -> User:
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[security.ALGORITHM]
        )
        token_data = TokenPayload(**payload)
    except (InvalidTokenError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        )

    if token_data.sub is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid token: missing subject",
        )

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid token type",
        )

    try:
        user_uuid = uuid.UUID(token_data.sub)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid user ID format",
        )

    user = await session.get(User, user_uuid)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return user
```

`get_current_active_superuser` stays unchanged (it doesn't touch the DB, just checks `current_user.is_superuser`).

- [ ] **Step 4: Run the full test suite**

Run: `cd /home/rajgajjar04/Projects/AutoInvoice/backend && .venv/bin/pytest -q`
Expected: every route that uses `SessionDep` directly (not yet migrated to a repository) currently calls sync `Session` methods like `session.exec(...)`/`session.get(...)` without `await` — **this will now fail** because those routes haven't been converted yet. This is expected and resolved by Task 3 onward; do not attempt to fix individual routes here. If you want a green checkpoint at this exact task boundary, skip running the full suite now and instead just confirm the app imports cleanly:

Run: `cd /home/rajgajjar04/Projects/AutoInvoice/backend && .venv/bin/python -c "from app.main import app; print('ok')"`
Expected: prints `ok` with no import errors.

- [ ] **Step 5: Run mypy and ruff**

Run: `cd /home/rajgajjar04/Projects/AutoInvoice/backend && .venv/bin/mypy app && .venv/bin/ruff check app`
Expected: mypy will flag every still-sync route in `app/api/routes/*.py` that calls `session.exec(...)`/`session.get(...)` without `await` against the now-`AsyncSession`-typed `SessionDep` (a missing-await/incompatible-type error). This is expected — Task 3 onward fixes each route as its domain migrates. Do not fix these here.

- [ ] **Step 6: Commit**

```bash
git add app/core/config.py app/core/db.py app/api/deps.py
git commit -m "feat: add async engine and convert base DI chain (get_db, get_current_user) to AsyncSession"
```

---

## Task 3: Exception scaffolding and async `BaseRepository`

Adds the shared exception hierarchy, global exception handlers, and the generic async `BaseRepository`. No route behavior changes yet — this just makes the building blocks available for Task 4 onward.

**Files:**
- Modify: `app/exceptions.py`
- Modify: `app/main.py`
- Create: `app/repositories/__init__.py`, `app/repositories/base.py`

**Interfaces:**
- Produces: `app.exceptions.{NotFoundError,ForbiddenError,ConflictError,ValidationError}`, `app.repositories.base.BaseRepository[ModelType]` with `__init__(self, session: AsyncSession)`, `async .get(id) -> ModelType | None`, `async .add(obj) -> ModelType`, `async .delete(obj) -> None`. Subclasses set a class attribute `model: type[ModelType]`.

- [ ] **Step 1: Add the new exception classes to `app/exceptions.py`**

Append to the end of the existing file (the `AuthError` family stays untouched):

```python


class NotFoundError(Exception):
    def __init__(self, message: str = "Resource not found"):
        self.message = message
        super().__init__(message)


class ForbiddenError(Exception):
    def __init__(self, message: str = "Not enough permissions"):
        self.message = message
        super().__init__(message)


class ConflictError(Exception):
    def __init__(self, message: str = "Conflict"):
        self.message = message
        super().__init__(message)


class ValidationError(Exception):
    def __init__(self, message: str = "Invalid request"):
        self.message = message
        super().__init__(message)
```

- [ ] **Step 2: Register handlers for the new exceptions in `app/main.py`**

Modify the import line:
```python
from app.exceptions import AuthError
```
to:
```python
from app.exceptions import AuthError, ConflictError, ForbiddenError, NotFoundError, ValidationError
```

Add these handlers directly after the existing `auth_exception_handler` function (after its closing `}` line, before the `if settings.all_cors_origins:` block). These are already `async def` — FastAPI exception handlers are conventionally async regardless of whether the route that raised the exception was sync or async, and these handlers don't touch the DB at all:

```python
@app.exception_handler(NotFoundError)
async def not_found_exception_handler(request: Request, exc: NotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": exc.message})


@app.exception_handler(ForbiddenError)
async def forbidden_exception_handler(request: Request, exc: ForbiddenError) -> JSONResponse:
    return JSONResponse(status_code=403, content={"detail": exc.message})


@app.exception_handler(ConflictError)
async def conflict_exception_handler(request: Request, exc: ConflictError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": exc.message})


@app.exception_handler(ValidationError)
async def validation_exception_handler(request: Request, exc: ValidationError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": exc.message})
```

Note: `ConflictError` maps to **400**, not 409 — every existing "already exists" conflict in this codebase (`auth.py` signup, `company_settings.py` create) already returns 400, and changing it to 409 would break `tests/api/routes/test_login.py::test_signup_existing_user` and other passing tests.

- [ ] **Step 3: Create `app/repositories/__init__.py`**

```python
```

(empty file — this package only ever needs explicit submodule imports, e.g. `from app.repositories.user_repository import UserRepository`)

- [ ] **Step 4: Create `app/repositories/base.py`**

```python
import uuid
from typing import Generic, TypeVar

from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

ModelType = TypeVar("ModelType", bound=SQLModel)


class BaseRepository(Generic[ModelType]):
    model: type[ModelType]

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, id: uuid.UUID) -> ModelType | None:
        return await self.session.get(self.model, id)

    async def add(self, obj: ModelType) -> ModelType:
        self.session.add(obj)
        await self.session.commit()
        await self.session.refresh(obj)
        return obj

    async def delete(self, obj: ModelType) -> None:
        await self.session.delete(obj)
        await self.session.commit()
```

- [ ] **Step 5: Run mypy and ruff**

Run: `cd /home/rajgajjar04/Projects/AutoInvoice/backend && .venv/bin/mypy app && .venv/bin/ruff check app`
Expected: no new errors from these three files (the pre-existing route-level async/await mismatches flagged in Task 2 remain until each domain migrates — that's expected).

- [ ] **Step 6: Commit**

```bash
git add app/exceptions.py app/main.py app/repositories
git commit -m "feat: add domain exception hierarchy, global handlers, and async BaseRepository"
```

---

## Task 4: User & Auth domain

Migrates `auth.py`, `users.py`, `admin.py`, `private.py` onto an async `UserRepository` + `UserService`. Email-sending stays sync (`email_service.py` has no DB access — pure SMTP/JWT/template functions, unaffected by the async decision). `app/core/db.py`'s `init_db` keeps using plain sync SQLModel calls directly (no repository) since it's bootstrap code exempt from both the async conversion and the repository abstraction — it's not part of the live request path.

Because the new repositories are async-only, any test helper that needs to set up DB state directly (not through an HTTP call) can no longer instantiate them against the sync `db` fixture. Those helpers switch to plain sync SQLModel calls (`User.model_validate(...)` + `db.add()`/`db.commit()`/`db.refresh()`) — exactly what `UserRepository.create()` does internally, just inlined for the sync test context.

**Files:**
- Create: `app/repositories/user_repository.py`
- Create: `app/services/user_service.py`
- Create: `app/services/email_service.py`
- Modify: `app/api/deps.py`, `app/core/db.py`
- Modify: `app/api/routes/auth.py`, `app/api/routes/users.py`, `app/api/routes/admin.py`, `app/api/routes/private.py`, `app/api/routes/utils.py`
- Modify: `tests/utils/user.py`, `tests/api/routes/test_users.py`, `tests/api/routes/test_login.py`, `tests/api/routes/test_tables.py`
- Delete: `tests/crud/test_user.py`, `tests/crud/__init__.py`
- Create: `tests/api/routes/test_admin.py`

**Interfaces:**
- Produces: `UserRepository(session: AsyncSession)` with `async .get_by_email(email)`, `async .create(user_create, hashed_password)`, `async .update(user, update_data: dict)`, `async .list_paginated(skip, limit)`, `async .list_page(page, page_size)` (plus inherited async `.get(id)`, `.delete(obj)`).
- Produces: `UserService(repo)` with `async .get_by_email`, `.get_by_id`, `.get_by_id_or_404`, `.signup`, `.authenticate`, `.update_password`, `.update_me`, `.delete_me`, `.get_by_id_for_user`, `.update_user`, `.delete_user`, `.list_users`, `.list_users_page`, `.create_user_as_admin`, `.update_user_as_admin`, `.create_user_private`.
- Produces in `app/api/deps.py`: `UserServiceDep = Annotated[UserService, Depends(get_user_service)]`. The provider functions (`get_user_repository`, `get_user_service`) stay plain `def` — constructing an object isn't async, only the methods that touch the DB are.

- [ ] **Step 1: Create `app/repositories/user_repository.py`**

```python
from sqlmodel import func, select

from app.models import User
from app.repositories.base import BaseRepository
from app.schemas import UserCreate


class UserRepository(BaseRepository[User]):
    model = User

    async def get_by_email(self, email: str) -> User | None:
        statement = select(User).where(User.email == email)
        result = await self.session.exec(statement)
        return result.first()

    async def create(self, user_create: UserCreate, hashed_password: str) -> User:
        db_obj = User.model_validate(
            user_create, update={"hashed_password": hashed_password}
        )
        return await self.add(db_obj)

    async def update(self, db_user: User, update_data: dict) -> User:
        db_user.sqlmodel_update(update_data)
        return await self.add(db_user)

    async def list_paginated(self, *, skip: int, limit: int) -> tuple[list[User], int]:
        count_result = await self.session.exec(select(func.count()).select_from(User))
        count = count_result.one()
        statement = (
            select(User).order_by(User.created_at.desc()).offset(skip).limit(limit)
        )
        result = await self.session.exec(statement)
        return list(result.all()), count

    async def list_page(self, *, page: int, page_size: int) -> tuple[list[User], int]:
        count_result = await self.session.exec(select(func.count()).select_from(User))
        count = count_result.one()
        offset = (page - 1) * page_size
        statement = (
            select(User)
            .order_by(User.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        result = await self.session.exec(statement)
        return list(result.all()), count
```

- [ ] **Step 2: Create `app/services/user_service.py`**

```python
import uuid

from app.core.security import get_password_hash, verify_password
from app.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.models import User
from app.repositories.user_repository import UserRepository
from app.schemas import UserCreate, UserUpdate, UserUpdateMe

DUMMY_HASH = "$argon2id$v=19$m=65536,t=3,p=4$MjQyZWE1MzBjYjJlZTI0Yw$YTU4NGM5ZTZmYjE2NzZlZjY0ZWY3ZGRkY2U2OWFjNjk"


class UserService:
    def __init__(self, repo: UserRepository) -> None:
        self.repo = repo

    async def get_by_email(self, email: str) -> User | None:
        return await self.repo.get_by_email(email)

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        return await self.repo.get(user_id)

    async def get_by_id_or_404(self, user_id: uuid.UUID) -> User:
        user = await self.repo.get(user_id)
        if not user:
            raise NotFoundError("User not found")
        return user

    async def signup(self, user_create: UserCreate) -> User:
        if await self.repo.get_by_email(user_create.email):
            raise ConflictError("A user with this email already exists")
        hashed_password = get_password_hash(user_create.password)
        return await self.repo.create(user_create, hashed_password)

    async def authenticate(self, email: str, password: str) -> User | None:
        db_user = await self.repo.get_by_email(email)
        if not db_user:
            verify_password(password, DUMMY_HASH)
            return None
        verified, updated_hash = verify_password(password, db_user.hashed_password)
        if not verified:
            return None
        if updated_hash:
            await self.repo.update(db_user, {"hashed_password": updated_hash})
        return db_user

    async def update_password(self, db_user: User, new_password: str) -> User:
        return await self.repo.update(
            db_user, {"hashed_password": get_password_hash(new_password)}
        )

    async def update_me(self, current_user: User, user_in: UserUpdateMe) -> User:
        update_data: dict = {}
        if user_in.full_name is not None:
            update_data["full_name"] = user_in.full_name
        if user_in.email is not None and user_in.email != current_user.email:
            if await self.repo.get_by_email(user_in.email):
                raise ConflictError("A user with this email already exists")
            update_data["email"] = user_in.email
            update_data["is_verified"] = False
        if not update_data:
            return current_user
        return await self.repo.update(current_user, update_data)

    async def delete_me(self, current_user: User) -> None:
        if current_user.is_superuser:
            raise ForbiddenError("Super users are not allowed to delete themselves")
        await self.repo.delete(current_user)

    async def get_by_id_for_user(self, user_id: uuid.UUID, current_user: User) -> User:
        user = await self.repo.get(user_id)
        if user is None:
            raise NotFoundError("User not found")
        if user.id != current_user.id and not current_user.is_superuser:
            raise ForbiddenError("The user doesn't have enough privileges")
        return user

    async def update_user(self, user_id: uuid.UUID, user_in: UserUpdate) -> User:
        user = await self.repo.get(user_id)
        if not user:
            raise NotFoundError("User not found")
        if user_in.email and user_in.email != user.email:
            if await self.repo.get_by_email(user_in.email):
                raise ConflictError("A user with this email already exists")
        update_data = user_in.model_dump(exclude_unset=True)
        if "password" in update_data:
            password = update_data.pop("password")
            update_data["hashed_password"] = get_password_hash(password)
        return await self.repo.update(user, update_data)

    async def delete_user(self, user_id: uuid.UUID, current_superuser: User) -> None:
        if user_id == current_superuser.id:
            raise ForbiddenError("Super users are not allowed to delete themselves")
        user = await self.repo.get(user_id)
        if not user:
            raise NotFoundError("User not found")
        await self.repo.delete(user)

    async def list_users(self, *, skip: int, limit: int) -> tuple[list[User], int]:
        return await self.repo.list_paginated(skip=skip, limit=limit)

    async def list_users_page(self, *, page: int, page_size: int) -> tuple[list[User], int]:
        return await self.repo.list_page(page=page, page_size=page_size)

    async def create_user_as_admin(
        self,
        *,
        email: str,
        password: str,
        full_name: str | None,
        is_superuser: bool,
    ) -> User:
        if await self.repo.get_by_email(email):
            raise ConflictError("A user with this email already exists")
        user_create = UserCreate(
            email=email, password=password, full_name=full_name, is_superuser=is_superuser
        )
        return await self.repo.create(user_create, get_password_hash(password))

    async def update_user_as_admin(
        self,
        user_id: uuid.UUID,
        *,
        email: str | None,
        password: str | None,
        full_name: str | None,
        is_superuser: bool | None,
        is_active: bool | None,
    ) -> User:
        user = await self.repo.get(user_id)
        if not user:
            raise NotFoundError("User not found")
        update_data: dict = {}
        if email and email != user.email:
            if await self.repo.get_by_email(email):
                raise ConflictError("A user with this email already exists")
            update_data["email"] = email
            update_data["is_verified"] = False
        if password:
            update_data["hashed_password"] = get_password_hash(password)
        if full_name is not None:
            update_data["full_name"] = full_name
        if is_superuser is not None:
            update_data["is_superuser"] = is_superuser
        if is_active is not None:
            update_data["is_active"] = is_active
        if not update_data:
            return user
        return await self.repo.update(user, update_data)

    async def create_user_private(
        self,
        *,
        email: str,
        password: str,
        full_name: str,
        is_superuser: bool,
        is_verified: bool,
    ) -> User:
        user_create = UserCreate(
            email=email, password=password, full_name=full_name, is_superuser=is_superuser
        )
        user = await self.repo.create(user_create, get_password_hash(password))
        if is_verified:
            user = await self.repo.update(user, {"is_verified": True})
        return user
```

- [ ] **Step 3: Create `app/services/email_service.py`**

No DB access in this file at all — pure SMTP/JWT/template-rendering functions, completely unaffected by the async decision:

```python
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from string import Template
from typing import Any

import emails
import jwt
from jwt.exceptions import InvalidTokenError

from app.core import security
from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class EmailData:
    html_content: str
    subject: str


def render_email_template(*, template_name: str, context: dict[str, Any]) -> str:
    template_str = (
        Path(__file__).parent.parent / "email-templates" / "build" / template_name
    ).read_text()
    return Template(template_str).safe_substitute(context)


def send_email(*, email_to: str, subject: str = "", html_content: str = "") -> None:
    assert settings.emails_enabled, "no provided configuration for email variables"
    message = emails.Message(
        subject=subject,
        html=html_content,
        mail_from=(settings.EMAILS_FROM_NAME, settings.EMAILS_FROM_EMAIL),
    )
    smtp_options = {"host": settings.SMTP_HOST, "port": settings.SMTP_PORT}
    if settings.SMTP_TLS:
        smtp_options["tls"] = True
    elif settings.SMTP_SSL:
        smtp_options["ssl"] = True
    if settings.SMTP_USER:
        smtp_options["user"] = settings.SMTP_USER
    if settings.SMTP_PASSWORD:
        smtp_options["password"] = settings.SMTP_PASSWORD
    response = message.send(to=email_to, smtp=smtp_options)
    logger.info(f"send email result: {response}")


def generate_test_email(email_to: str) -> EmailData:
    project_name = settings.PROJECT_NAME
    subject = f"{project_name} - Test email"
    html_content = render_email_template(
        template_name="test_email.html",
        context={"project_name": settings.PROJECT_NAME, "email": email_to},
    )
    return EmailData(html_content=html_content, subject=subject)


def generate_reset_password_email(email_to: str, email: str, token: str) -> EmailData:
    project_name = settings.PROJECT_NAME
    subject = f"{project_name} - Password recovery for user {email}"
    link = f"{settings.FRONTEND_HOST}/reset-password?token={token}"
    html_content = render_email_template(
        template_name="reset_password.html",
        context={
            "project_name": settings.PROJECT_NAME,
            "username": email,
            "email": email_to,
            "valid_hours": settings.EMAIL_RESET_TOKEN_EXPIRE_HOURS,
            "link": link,
        },
    )
    return EmailData(html_content=html_content, subject=subject)


def generate_new_account_email(
    email_to: str, username: str, password: str | None = None
) -> EmailData:
    project_name = settings.PROJECT_NAME
    subject = f"{project_name} - New account for user {username}"
    html_content = render_email_template(
        template_name="new_account.html",
        context={
            "project_name": settings.PROJECT_NAME,
            "username": username,
            "password": password,
            "email": email_to,
            "link": settings.FRONTEND_HOST,
        },
    )
    return EmailData(html_content=html_content, subject=subject)


def generate_password_reset_token(email: str) -> str:
    delta = timedelta(hours=settings.EMAIL_RESET_TOKEN_EXPIRE_HOURS)
    now = datetime.now(timezone.utc)
    expires = now + delta
    return jwt.encode(
        {"exp": expires.timestamp(), "nbf": now, "sub": email},
        settings.SECRET_KEY,
        algorithm=security.ALGORITHM,
    )


def verify_password_reset_token(token: str) -> str | None:
    try:
        decoded_token = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[security.ALGORITHM]
        )
        return str(decoded_token["sub"])
    except InvalidTokenError:
        return None
```

- [ ] **Step 4: Remove the email functions from `app/utils.py`**

Delete everything from the top of the file through `verify_password_reset_token` (i.e. the `EmailData` dataclass and the six functions: `render_email_template`, `send_email`, `generate_test_email`, `generate_reset_password_email`, `generate_new_account_email`, `generate_password_reset_token`, `verify_password_reset_token`), along with their now-unused imports (`emails`, `jwt`, `InvalidTokenError`, `Path`, `Template`, `security`). After this step `app/utils.py` should start directly with the `logging.basicConfig` line followed by the `COLUMN_MAPPING` dict and `parse_excel_file` function (these move out in Task 10, left as-is here).

- [ ] **Step 5: Update `app/api/routes/utils.py` to use the email service**

Replace:
```python
from app.utils import generate_test_email, send_email
```
with:
```python
from app.services.email_service import generate_test_email, send_email
```
This route handler (`test_email`) doesn't touch the DB at all, so it stays a plain `def` — no async needed.

- [ ] **Step 6: Add `UserRepository`/`UserService` providers to `app/api/deps.py`**

Add these imports near the top (after the existing `from app.models import User` / `from app.schemas import TokenPayload` lines):
```python
from app.repositories.user_repository import UserRepository
from app.services.user_service import UserService
```

Add at the end of the file (these stay plain `def` — constructing a repository/service object isn't async):
```python


def get_user_repository(session: SessionDep) -> UserRepository:
    return UserRepository(session)


def get_user_service(
    repo: Annotated[UserRepository, Depends(get_user_repository)],
) -> UserService:
    return UserService(repo)


UserServiceDep = Annotated[UserService, Depends(get_user_service)]
```

- [ ] **Step 7: Rewrite `app/core/db.py`'s `init_db` to drop the `crud` dependency**

`init_db` stays sync (bootstrap code, exempt from the async conversion) and now uses plain SQLModel calls directly instead of `app.crud` — it's not part of the live request path, so it doesn't need the repository abstraction either:

```python
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlmodel import Session, create_engine, select

from app.core.config import settings
from app.core.security import get_password_hash
from app.models import User
from app.schemas import UserCreate

engine = create_engine(str(settings.SQLALCHEMY_DATABASE_URI))
async_engine: AsyncEngine = create_async_engine(str(settings.ASYNC_SQLALCHEMY_DATABASE_URI))


def init_db(session: Session) -> None:
    user = session.exec(
        select(User).where(User.email == settings.FIRST_SUPERUSER)
    ).first()
    if not user:
        user_in = UserCreate(
            email=settings.FIRST_SUPERUSER,
            password=settings.FIRST_SUPERUSER_PASSWORD,
            is_superuser=True,
        )
        db_obj = User.model_validate(
            user_in, update={"hashed_password": get_password_hash(user_in.password)}
        )
        session.add(db_obj)
        session.commit()
        session.refresh(db_obj)
```

- [ ] **Step 8: Rewrite `app/api/routes/auth.py`**

```python
from datetime import timedelta
from typing import Annotated, Any

import jwt
from fastapi import APIRouter, Cookie, HTTPException, Response
from jwt.exceptions import InvalidTokenError
from sqlmodel import SQLModel

from app.api.deps import CurrentUser, UserServiceDep
from app.core import security
from app.core.config import settings
from app.schemas import Message, NewPassword, Token, UserCreate, UserPublic, UserUpdateMe
from app.services.email_service import (
    generate_password_reset_token,
    generate_reset_password_email,
    send_email,
    verify_password_reset_token,
)

router = APIRouter(tags=["auth"])

ACCESS_TOKEN_MAX_AGE = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
REFRESH_TOKEN_MAX_AGE = settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
COOKIE_SECURE = settings.ENVIRONMENT != "local"
COOKIE_SAMESITE = "none" if settings.ENVIRONMENT != "local" else "lax"


class LoginRequest(SQLModel):
    email: str
    password: str


class AuthResponse(Token):
    user: UserPublic | None = None


def _set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        max_age=ACCESS_TOKEN_MAX_AGE,
        path="/",
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        max_age=REFRESH_TOKEN_MAX_AGE,
        path="/",
    )


@router.post("/auth/signup", response_model=AuthResponse)
async def signup(response: Response, user_in: UserCreate, user_service: UserServiceDep) -> AuthResponse:
    user = await user_service.signup(user_in)
    access_token = security.create_access_token(subject=user.id)
    refresh_token = security.create_refresh_token(subject=user.id)
    _set_auth_cookies(response, access_token, refresh_token)
    return AuthResponse(
        access_token=access_token,
        token_type="bearer",
        refresh_token=refresh_token,
        user=UserPublic.model_validate(user),
    )


@router.post("/auth/login", response_model=AuthResponse)
async def login(response: Response, body: LoginRequest, user_service: UserServiceDep) -> AuthResponse:
    user = await user_service.authenticate(body.email, body.password)
    if not user:
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    access_token = security.create_access_token(subject=user.id)
    refresh_token = security.create_refresh_token(subject=user.id)
    _set_auth_cookies(response, access_token, refresh_token)
    return AuthResponse(
        access_token=access_token,
        token_type="bearer",
        refresh_token=refresh_token,
        user=UserPublic.model_validate(user),
    )


@router.post("/auth/refresh", response_model=Token)
def refresh_token(
    response: Response,
    refresh_token: Annotated[str | None, Cookie()] = None,
) -> Token:
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Refresh token not found")

    try:
        payload = jwt.decode(
            refresh_token, settings.SECRET_KEY, algorithms=[security.ALGORITHM]
        )
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=403, detail="Invalid token type")
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=403, detail="Invalid token")
    except InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    new_access_token = security.create_access_token(subject=user_id)
    new_refresh_token = security.create_refresh_token(subject=user_id)
    _set_auth_cookies(response, new_access_token, new_refresh_token)

    return Token(
        access_token=new_access_token,
        token_type="bearer",
        refresh_token=new_refresh_token,
    )


@router.post("/auth/logout", response_model=Message)
def logout(response: Response) -> Message:
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")
    return Message(message="Logged out successfully")


@router.get("/auth/me", response_model=UserPublic)
def get_current_user_info(current_user: CurrentUser) -> Any:
    return UserPublic.model_validate(current_user)


@router.patch("/auth/me", response_model=UserPublic)
async def update_current_user(
    current_user: CurrentUser, user_in: UserUpdateMe, user_service: UserServiceDep
) -> Any:
    user = await user_service.update_me(current_user, user_in)
    return UserPublic.model_validate(user)


@router.post("/auth/forgot-password", response_model=Message)
async def forgot_password(email: str, user_service: UserServiceDep) -> Message:
    user = await user_service.get_by_email(email)
    if user:
        password_reset_token = generate_password_reset_token(email=email)
        email_data = generate_reset_password_email(
            email_to=user.email, email=email, token=password_reset_token
        )
        send_email(
            email_to=user.email,
            subject=email_data.subject,
            html_content=email_data.html_content,
        )
    return Message(
        message="If that email is registered, a password reset link has been sent"
    )


@router.post("/auth/reset-password", response_model=Message)
async def reset_password(body: NewPassword, user_service: UserServiceDep) -> Message:
    email = verify_password_reset_token(token=body.token)
    if not email:
        raise HTTPException(status_code=400, detail="Invalid token")
    user = await user_service.get_by_email(email)
    if not user:
        raise HTTPException(status_code=400, detail="Invalid token")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    await user_service.update_password(user, body.new_password)
    return Message(message="Password updated successfully")


@router.post("/auth/update-password", response_model=Message)
async def update_password(
    current_user: CurrentUser, body: dict[str, str], user_service: UserServiceDep
) -> Message:
    current_password = body.get("current_password")
    new_password = body.get("new_password")

    if not current_password or not new_password:
        raise HTTPException(
            status_code=400,
            detail="Current password and new password are required",
        )

    user = await user_service.authenticate(current_user.email, current_password)
    if not user:
        raise HTTPException(status_code=400, detail="Incorrect current password")

    await user_service.update_password(user, new_password)
    return Message(message="Password updated successfully")
```

Note: `refresh_token` and `logout` stay plain `def` — they never touch the DB, only cookies and JWT decode/encode.

- [ ] **Step 9: Rewrite `app/api/routes/users.py`**

```python
import uuid
from typing import Any

from fastapi import APIRouter

from app.api.deps import CurrentUser, SuperUserDep, UserServiceDep
from app.schemas import Message, UserPublic, UserUpdate, UserUpdateMe, UsersPublic

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/", response_model=UsersPublic)
async def read_users(
    superuser: SuperUserDep, user_service: UserServiceDep, skip: int = 0, limit: int = 100
) -> Any:
    users, count = await user_service.list_users(skip=skip, limit=limit)
    return UsersPublic(data=[UserPublic.model_validate(u) for u in users], count=count)


@router.get("/me", response_model=UserPublic)
def read_user_me(current_user: CurrentUser) -> Any:
    return UserPublic.model_validate(current_user)


@router.patch("/me", response_model=UserPublic)
async def update_user_me(
    current_user: CurrentUser, user_in: UserUpdateMe, user_service: UserServiceDep
) -> Any:
    user = await user_service.update_me(current_user, user_in)
    return UserPublic.model_validate(user)


@router.delete("/me", response_model=Message)
async def delete_user_me(current_user: CurrentUser, user_service: UserServiceDep) -> Any:
    await user_service.delete_me(current_user)
    return Message(message="User deleted successfully")


@router.get("/{user_id}", response_model=UserPublic)
async def read_user_by_id(
    user_id: uuid.UUID, current_user: CurrentUser, user_service: UserServiceDep
) -> Any:
    user = await user_service.get_by_id_for_user(user_id, current_user)
    return UserPublic.model_validate(user)


@router.patch("/{user_id}", response_model=UserPublic)
async def update_user(
    user_id: uuid.UUID, superuser: SuperUserDep, user_in: UserUpdate, user_service: UserServiceDep
) -> Any:
    user = await user_service.update_user(user_id, user_in)
    return UserPublic.model_validate(user)


@router.delete("/{user_id}", response_model=Message)
async def delete_user(
    user_id: uuid.UUID, superuser: SuperUserDep, user_service: UserServiceDep
) -> Message:
    await user_service.delete_user(user_id, superuser)
    return Message(message="User deleted successfully")
```

- [ ] **Step 10: Rewrite `app/api/routes/admin.py`**

```python
import uuid

from fastapi import APIRouter
from pydantic import EmailStr
from sqlmodel import SQLModel

from app.api.deps import SuperUserDep, UserServiceDep
from app.schemas import Message, PaginatedResponse, UserPublic

router = APIRouter(prefix="/admin", tags=["admin"])


class AdminUserCreate(SQLModel):
    email: EmailStr
    password: str
    full_name: str | None = None
    is_superuser: bool = False


class AdminUserUpdate(SQLModel):
    email: EmailStr | None = None
    password: str | None = None
    full_name: str | None = None
    is_superuser: bool | None = None
    is_active: bool | None = None


@router.get("/users", response_model=PaginatedResponse[UserPublic])
async def list_users(
    superuser: SuperUserDep,
    user_service: UserServiceDep,
    page: int = 1,
    page_size: int = 50,
) -> PaginatedResponse[UserPublic]:
    users, total = await user_service.list_users_page(page=page, page_size=page_size)
    total_pages = (total + page_size - 1) // page_size if total > 0 else 1
    return PaginatedResponse(
        data=[UserPublic.model_validate(u) for u in users],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.post("/users", response_model=UserPublic)
async def create_user(
    superuser: SuperUserDep, user_in: AdminUserCreate, user_service: UserServiceDep
) -> UserPublic:
    user = await user_service.create_user_as_admin(
        email=user_in.email,
        password=user_in.password,
        full_name=user_in.full_name,
        is_superuser=user_in.is_superuser,
    )
    return UserPublic.model_validate(user)


@router.get("/users/{user_id}", response_model=UserPublic)
async def get_user(superuser: SuperUserDep, user_id: uuid.UUID, user_service: UserServiceDep) -> UserPublic:
    user = await user_service.get_by_id_or_404(user_id)
    return UserPublic.model_validate(user)


@router.patch("/users/{user_id}", response_model=UserPublic)
async def update_user(
    superuser: SuperUserDep,
    user_id: uuid.UUID,
    user_in: AdminUserUpdate,
    user_service: UserServiceDep,
) -> UserPublic:
    user = await user_service.update_user_as_admin(
        user_id,
        email=user_in.email,
        password=user_in.password,
        full_name=user_in.full_name,
        is_superuser=user_in.is_superuser,
        is_active=user_in.is_active,
    )
    return UserPublic.model_validate(user)


@router.delete("/users/{user_id}", response_model=Message)
async def delete_user(
    superuser: SuperUserDep, user_id: uuid.UUID, user_service: UserServiceDep
) -> Message:
    await user_service.delete_user(user_id, superuser)
    return Message(message="User deleted successfully")
```

- [ ] **Step 11: Rewrite `app/api/routes/private.py`**

```python
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, EmailStr

from app.api.deps import UserServiceDep
from app.schemas import UserPublic

router = APIRouter(tags=["private"], prefix="/private")


class PrivateUserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    is_verified: bool = False
    is_superuser: bool = False


@router.post("/users/", response_model=UserPublic)
async def create_user(user_in: PrivateUserCreate, user_service: UserServiceDep) -> Any:
    user = await user_service.create_user_private(
        email=user_in.email,
        password=user_in.password,
        full_name=user_in.full_name,
        is_superuser=user_in.is_superuser,
        is_verified=user_in.is_verified,
    )
    return UserPublic.model_validate(user)
```

- [ ] **Step 12: Update `tests/utils/user.py` to use plain sync SQLModel calls (no repository — it's async-only now)**

```python
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import settings
from app.core.security import get_password_hash
from app.models import User
from app.schemas import UserCreate
from tests.utils.utils import random_email, random_lower_string


def user_authentication_headers(
    *, client: TestClient, email: str, password: str
) -> dict[str, str]:
    r = client.post(
        f"{settings.API_V1_STR}/auth/login",
        json={"email": email, "password": password},
    )
    r.raise_for_status()
    return {"Authorization": f"Bearer {client.cookies.get('access_token')}"}


def create_random_user(db: Session) -> User:
    email = random_email()
    password = random_lower_string()
    user_in = UserCreate(email=email, password=password, full_name=random_lower_string())
    db_obj = User.model_validate(
        user_in, update={"hashed_password": get_password_hash(user_in.password)}
    )
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj


def authentication_token_from_email(
    *, client: TestClient, email: str, db: Session, password: str = "testpassword123"
) -> dict[str, str]:
    user = db.exec(select(User).where(User.email == email)).first()
    if not user:
        user_in = UserCreate(email=email, password=password, full_name=random_lower_string())
        db_obj = User.model_validate(
            user_in, update={"hashed_password": get_password_hash(user_in.password)}
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)

    return user_authentication_headers(client=client, email=email, password=password)
```

- [ ] **Step 13: Update `tests/api/routes/test_users.py` to use plain sync SQLModel calls instead of `crud`**

Replace the import block:
```python
from app import crud
from app.core.config import settings
from app.core.security import verify_password
from app.models import User, UserCreate
from tests.utils.user import create_random_user
from tests.utils.utils import random_email, random_lower_string
```
with:
```python
from sqlmodel import select

from app.core.config import settings
from app.core.security import get_password_hash
from app.models import User
from app.schemas import UserCreate
from tests.utils.user import create_random_user
from tests.utils.utils import random_email, random_lower_string


def _create_user(db, user_in: UserCreate) -> User:
    db_obj = User.model_validate(
        user_in, update={"hashed_password": get_password_hash(user_in.password)}
    )
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj


def _get_user_by_email(db, email: str) -> User | None:
    return db.exec(select(User).where(User.email == email)).first()
```

Then replace every occurrence of `crud.create_user(session=db, user_create=user_in)` with `_create_user(db, user_in)`, and `crud.get_user_by_email(session=db, email=...)` with `_get_user_by_email(db, ...)`. There are 7 call sites across `test_get_existing_user_as_superuser`, `test_retrieve_users` (×2), `test_update_user_me_email_exists`, `test_delete_user_me`, `test_delete_user_super_user`, `test_delete_user_current_super_user_error`, `test_delete_user_without_privileges` — apply the same mechanical substitution at each.

- [ ] **Step 14: Move the bcrypt→argon2 upgrade test from `tests/crud/test_user.py` into `tests/api/routes/test_login.py`, then delete `tests/crud/`**

The rest of `tests/crud/test_user.py` (plain `create_user`/`is_active`/`is_superuser` passthrough checks) is already covered by `test_login.py::test_signup`, `test_users.py`, and `test_private.py` exercising the same code through real HTTP requests — those are a better regression gate than a standalone unit test, since they test the actual wiring. Only the bcrypt→argon2 password-hash-upgrade behavior is worth keeping as a dedicated test, rewritten here to go through the real `/auth/login` endpoint (so it doesn't need direct access to the now-async `UserService`):

Add to the end of `tests/api/routes/test_login.py`:
```python
def test_login_upgrades_bcrypt_hash_to_argon2(client: TestClient, db: Session) -> None:
    """A user with a legacy bcrypt password hash gets upgraded to argon2 on login."""
    from pwdlib.hashers.bcrypt import BcryptHasher

    from app.core.security import verify_password
    from app.models import User

    email = random_email()
    password = random_lower_string()

    bcrypt_hash = BcryptHasher().hash(password)
    assert bcrypt_hash.startswith("$2")

    user = User(email=email, hashed_password=bcrypt_hash)
    db.add(user)
    db.commit()
    db.refresh(user)
    assert user.hashed_password.startswith("$2")

    response = client.post(
        f"{settings.API_V1_STR}/auth/login", json={"email": email, "password": password}
    )
    assert response.status_code == 200

    db.refresh(user)
    assert user.hashed_password.startswith("$argon2")
    verified, updated_hash = verify_password(password, user.hashed_password)
    assert verified
    assert updated_hash is None
```
Add `from sqlmodel import Session` to `test_login.py`'s existing imports if not already present (it already imports `Session` per the current file — verify before adding a duplicate import).

```bash
git rm -r tests/crud
```

- [ ] **Step 15: Update `tests/api/routes/test_tables.py`'s `test_ownership_isolation` to use plain sync SQLModel calls instead of `crud`**

Replace:
```python
    from tests.utils.user import create_random_user, user_authentication_headers
    from tests.utils.utils import random_lower_string

    password = random_lower_string()
    normal_user = create_random_user(db)

    # Update user password to known value
    from app.schemas import UserUpdate
    from app import crud
    user_update = UserUpdate(password=password)
    crud.update_user(session=db, db_user=normal_user, user_in=user_update)
```
with:
```python
    from tests.utils.user import create_random_user, user_authentication_headers
    from tests.utils.utils import random_lower_string

    password = random_lower_string()
    normal_user = create_random_user(db)

    # Update user password to known value
    from app.core.security import get_password_hash
    normal_user.hashed_password = get_password_hash(password)
    db.add(normal_user)
    db.commit()
```

- [ ] **Step 16: Create the smoke test `tests/api/routes/test_admin.py`**

`admin.py` has no existing test coverage (it's a separate `/admin`-prefixed superuser-only surface, distinct from `/users`, which `test_users.py` already covers):

```python
import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import settings
from app.models import User
from tests.utils.utils import random_email, random_lower_string


def test_admin_create_list_and_get_user(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    email = random_email()
    create_response = client.post(
        f"{settings.API_V1_STR}/admin/users",
        headers=superuser_token_headers,
        json={"email": email, "password": random_lower_string(), "full_name": "Admin Created"},
    )
    assert create_response.status_code == 200
    user_id = create_response.json()["id"]

    list_response = client.get(
        f"{settings.API_V1_STR}/admin/users", headers=superuser_token_headers
    )
    assert list_response.status_code == 200
    assert list_response.json()["total"] >= 1

    get_response = client.get(
        f"{settings.API_V1_STR}/admin/users/{user_id}", headers=superuser_token_headers
    )
    assert get_response.status_code == 200
    assert get_response.json()["email"] == email


def test_admin_get_user_not_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    response = client.get(
        f"{settings.API_V1_STR}/admin/users/{uuid.uuid4()}", headers=superuser_token_headers
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"


def test_admin_update_user(client: TestClient, superuser_token_headers: dict[str, str]) -> None:
    create_response = client.post(
        f"{settings.API_V1_STR}/admin/users",
        headers=superuser_token_headers,
        json={"email": random_email(), "password": random_lower_string()},
    )
    user_id = create_response.json()["id"]

    update_response = client.patch(
        f"{settings.API_V1_STR}/admin/users/{user_id}",
        headers=superuser_token_headers,
        json={"full_name": "Updated By Admin", "is_active": False},
    )
    assert update_response.status_code == 200
    content = update_response.json()
    assert content["full_name"] == "Updated By Admin"
    assert content["is_active"] is False


def test_admin_delete_user_self_forbidden(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    superuser = db.exec(select(User).where(User.email == settings.FIRST_SUPERUSER)).first()
    assert superuser is not None
    response = client.delete(
        f"{settings.API_V1_STR}/admin/users/{superuser.id}", headers=superuser_token_headers
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Super users are not allowed to delete themselves"
```

- [ ] **Step 17: Run the full test suite**

Run: `cd /home/rajgajjar04/Projects/AutoInvoice/backend && .venv/bin/pytest -q`
Expected: all User/Auth-domain tests pass — `test_login.py` (including the new bcrypt-upgrade test), `test_users.py`, `test_private.py`, and the new `test_admin.py`. Other domains' tests (items, tables, customers, etc.) will still fail at this checkpoint since their routes haven't been migrated to async yet — that's expected and resolved by Tasks 5–11.

- [ ] **Step 18: Run mypy and ruff**

Run: `cd /home/rajgajjar04/Projects/AutoInvoice/backend && .venv/bin/mypy app && .venv/bin/ruff check app tests`
Expected: no errors for the files touched in this task. Other not-yet-migrated routes will still show the expected async/await mismatch errors from Task 2 until their domain task runs.

- [ ] **Step 19: Commit**

```bash
git add app/repositories/user_repository.py app/services/user_service.py app/services/email_service.py
git add app/api/deps.py app/core/db.py app/api/routes/auth.py app/api/routes/users.py app/api/routes/admin.py app/api/routes/private.py app/api/routes/utils.py app/utils.py
git add tests/utils/user.py tests/api/routes/test_users.py tests/api/routes/test_login.py tests/api/routes/test_tables.py tests/api/routes/test_admin.py
git commit -m "refactor: migrate User/Auth domain to async repository + service layer, add admin smoke tests"
```

---

## Task 5: Items domain

**Files:**
- Create: `app/repositories/item_repository.py`
- Create: `app/services/item_service.py`
- Modify: `app/api/deps.py`, `app/api/routes/items.py`
- Modify: `tests/utils/item.py`, `tests/api/routes/test_items.py`

**Interfaces:**
- Produces: `ItemRepository(session: AsyncSession)` with `async .list_filtered(owner_id, *, search, category, stock_status, skip, limit)`, `async .list_categories(owner_id)`, `async .get_by_id_and_owner(item_id, owner_id)`, `async .create(item_in, owner_id)`, `async .update(item, update_data)` (plus inherited async `.get`, `.delete`).
- Produces: `ItemService(repo)` with `async .get_owned`, `.create`, `.update`, `.delete`, `.adjust_stock`, `.list_categories`, `.list`.
- Produces in `app/api/deps.py`: `ItemServiceDep`.

- [ ] **Step 1: Create `app/repositories/item_repository.py`**

```python
import uuid

from sqlmodel import col, func, select

from app.models import Item
from app.repositories.base import BaseRepository
from app.schemas import ItemCreate


class ItemRepository(BaseRepository[Item]):
    model = Item

    async def get_by_id_and_owner(self, item_id: uuid.UUID, owner_id: uuid.UUID) -> Item | None:
        statement = select(Item).where(Item.id == item_id, Item.owner_id == owner_id)
        result = await self.session.exec(statement)
        return result.first()

    async def list_filtered(
        self,
        owner_id: uuid.UUID,
        *,
        search: str | None,
        category: str | None,
        stock_status: str | None,
        skip: int,
        limit: int,
    ) -> tuple[list[Item], int]:
        base_filter = Item.owner_id == owner_id

        if search:
            search_term = f"%{search}%"
            base_filter = (
                (Item.name.ilike(search_term))
                | (Item.description.ilike(search_term))
                | (Item.sku.ilike(search_term))
            ) & (Item.owner_id == owner_id)

        if category:
            base_filter = base_filter & (Item.category == category)

        if stock_status == "in_stock":
            base_filter = base_filter & (Item.stock >= Item.low_stock_threshold)
        elif stock_status == "low_stock":
            base_filter = base_filter & (
                (Item.stock > 0) & (Item.stock < Item.low_stock_threshold)
            )
        elif stock_status == "out_of_stock":
            base_filter = base_filter & (Item.stock == 0)

        count_result = await self.session.exec(
            select(func.count()).select_from(Item).where(base_filter)
        )
        count = count_result.one()
        statement = (
            select(Item)
            .where(base_filter)
            .order_by(col(Item.created_at).desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.exec(statement)
        return list(result.all()), count

    async def list_categories(self, owner_id: uuid.UUID) -> list[str]:
        statement = (
            select(Item.category)
            .where(Item.owner_id == owner_id, Item.category.isnot(None))
            .distinct()
        )
        result = await self.session.exec(statement)
        categories = result.all()
        return sorted([c for c in categories if c])

    async def create(self, item_in: ItemCreate, owner_id: uuid.UUID) -> Item:
        item = Item.model_validate(item_in, update={"owner_id": owner_id})
        return await self.add(item)

    async def update(self, item: Item, update_data: dict) -> Item:
        item.sqlmodel_update(update_data)
        return await self.add(item)
```

- [ ] **Step 2: Create `app/services/item_service.py`**

```python
import uuid

from app.core.time import get_datetime_utc
from app.exceptions import ForbiddenError, NotFoundError, ValidationError
from app.models import Item
from app.repositories.item_repository import ItemRepository
from app.schemas import ItemCreate, ItemUpdate


class ItemService:
    def __init__(self, repo: ItemRepository) -> None:
        self.repo = repo

    async def get_owned(self, item_id: uuid.UUID, owner_id: uuid.UUID) -> Item:
        item = await self.repo.get(item_id)
        if not item:
            raise NotFoundError("Item not found")
        if item.owner_id != owner_id:
            raise ForbiddenError("Not enough permissions")
        return item

    async def list(
        self,
        owner_id: uuid.UUID,
        *,
        skip: int,
        limit: int,
        search: str | None,
        category: str | None,
        stock_status: str | None,
    ) -> tuple[list[Item], int]:
        return await self.repo.list_filtered(
            owner_id,
            search=search,
            category=category,
            stock_status=stock_status,
            skip=skip,
            limit=limit,
        )

    async def create(self, item_in: ItemCreate, owner_id: uuid.UUID) -> Item:
        return await self.repo.create(item_in, owner_id)

    async def update(self, item_id: uuid.UUID, owner_id: uuid.UUID, item_in: ItemUpdate) -> Item:
        item = await self.get_owned(item_id, owner_id)
        update_data = item_in.model_dump(exclude_unset=True)
        update_data["updated_at"] = get_datetime_utc()
        return await self.repo.update(item, update_data)

    async def delete(self, item_id: uuid.UUID, owner_id: uuid.UUID) -> None:
        item = await self.get_owned(item_id, owner_id)
        await self.repo.delete(item)

    async def adjust_stock(
        self,
        item_id: uuid.UUID,
        owner_id: uuid.UUID,
        *,
        quantity: float,
        reason: str | None,
        reference: str | None,
    ) -> Item:
        item = await self.get_owned(item_id, owner_id)
        new_stock = item.stock + quantity
        if new_stock < 0:
            raise ValidationError("Insufficient stock")

        stock_entry = {
            "date": get_datetime_utc().isoformat(),
            "quantity": quantity,
            "previous_stock": item.stock,
            "new_stock": new_stock,
            "reason": reason or "adjustment",
            "reference": reference,
        }
        update_data = {
            "stock": new_stock,
            "stock_history": item.stock_history + [stock_entry],
            "updated_at": get_datetime_utc(),
        }
        return await self.repo.update(item, update_data)

    async def list_categories(self, owner_id: uuid.UUID) -> list[str]:
        return await self.repo.list_categories(owner_id)
```

Note: `ValidationError("Insufficient stock")` changes the status code for this one case from the original `HTTPException(status_code=400, ...)` to 422 (the `ValidationError` global mapping). There is no existing test covering `adjust_stock`'s insufficient-stock path, so this is safe, but flag it as a deliberate, documented status-code change rather than an oversight.

- [ ] **Step 3: Add `ItemRepository`/`ItemService` providers to `app/api/deps.py`**

Add imports:
```python
from app.repositories.item_repository import ItemRepository
from app.services.item_service import ItemService
```

Add at the end of the file (plain `def` — constructing the objects isn't async):
```python


def get_item_repository(session: SessionDep) -> ItemRepository:
    return ItemRepository(session)


def get_item_service(
    repo: Annotated[ItemRepository, Depends(get_item_repository)],
) -> ItemService:
    return ItemService(repo)


ItemServiceDep = Annotated[ItemService, Depends(get_item_service)]
```

- [ ] **Step 4: Rewrite `app/api/routes/items.py`**

```python
import uuid
from typing import Any

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, ItemServiceDep
from app.schemas import ItemCreate, ItemPublic, ItemsPublic, ItemUpdate, Message

router = APIRouter(prefix="/items", tags=["items"])


@router.get("/", response_model=ItemsPublic)
async def read_items(
    current_user: CurrentUser,
    item_service: ItemServiceDep,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    search: str | None = None,
    category: str | None = None,
    stock_status: str | None = Query(
        None, pattern="^(in_stock|low_stock|out_of_stock)$"
    ),
) -> Any:
    """
    Retrieve items with optional filters.

    - **search**: Search by name, description, or SKU
    - **category**: Filter by category
    - **stock_status**: Filter by stock status (in_stock, low_stock, out_of_stock)
    """
    items, count = await item_service.list(
        current_user.id,
        skip=skip,
        limit=limit,
        search=search,
        category=category,
        stock_status=stock_status,
    )
    return ItemsPublic(data=items, count=count)


@router.get("/{id}", response_model=ItemPublic)
async def read_item(current_user: CurrentUser, item_service: ItemServiceDep, id: uuid.UUID) -> Any:
    """
    Get item by ID.
    """
    return await item_service.get_owned(id, current_user.id)


@router.post("/", response_model=ItemPublic)
async def create_item(
    *, current_user: CurrentUser, item_service: ItemServiceDep, item_in: ItemCreate
) -> Any:
    """
    Create new item.
    """
    return await item_service.create(item_in, current_user.id)


@router.put("/{id}", response_model=ItemPublic)
async def update_item(
    *,
    current_user: CurrentUser,
    item_service: ItemServiceDep,
    id: uuid.UUID,
    item_in: ItemUpdate,
) -> Any:
    """
    Update an item.
    """
    return await item_service.update(id, current_user.id, item_in)


@router.patch("/{id}/adjust-stock", response_model=ItemPublic)
async def adjust_stock(
    *,
    current_user: CurrentUser,
    item_service: ItemServiceDep,
    id: uuid.UUID,
    quantity: float,
    reason: str | None = None,
    reference: str | None = None,
) -> Any:
    """
    Adjust item stock by a quantity delta.

    - **quantity**: Amount to add (positive) or subtract (negative)
    - **reason**: Reason for adjustment (sale, purchase, adjustment, etc.)
    - **reference**: Optional reference (invoice number, PO number, etc.)
    """
    return await item_service.adjust_stock(
        id, current_user.id, quantity=quantity, reason=reason, reference=reference
    )


@router.get("/categories/list")
async def list_categories(current_user: CurrentUser, item_service: ItemServiceDep) -> list[str]:
    """
    Get list of distinct categories used by user's items.
    """
    return await item_service.list_categories(current_user.id)


@router.delete("/{id}")
async def delete_item(current_user: CurrentUser, item_service: ItemServiceDep, id: uuid.UUID) -> Message:
    """
    Delete an item.
    """
    await item_service.delete(id, current_user.id)
    return Message(message="Item deleted successfully")
```

- [ ] **Step 5: Update `tests/utils/item.py` to use plain sync SQLModel calls (no repository — it's async-only now)**

```python
import uuid

from sqlmodel import Session

from app.models import Item
from app.schemas import ItemCreate
from tests.utils.user import create_random_user
from tests.utils.utils import random_lower_string


def create_random_item(db: Session, owner_id: uuid.UUID | None = None) -> Item:
    if owner_id is None:
        user = create_random_user(db)
        owner_id = user.id
        assert owner_id is not None

    name = random_lower_string()
    description = random_lower_string()
    item_in = ItemCreate(name=name, description=description)
    item = Item.model_validate(item_in, update={"owner_id": owner_id})
    db.add(item)
    db.commit()
    db.refresh(item)
    return item
```

- [ ] **Step 6: Update `tests/api/routes/test_items.py` to drop the `crud` dependency**

Replace:
```python
from app import crud
from app.core.config import settings
from app.models import User
from tests.utils.item import create_random_item


def get_superuser(db: Session) -> User:
    user = crud.get_user_by_email(session=db, email=settings.FIRST_SUPERUSER)
    assert user is not None
    assert user.id is not None
    return user
```
with:
```python
from sqlmodel import select

from app.core.config import settings
from app.models import User
from tests.utils.item import create_random_item


def get_superuser(db: Session) -> User:
    user = db.exec(select(User).where(User.email == settings.FIRST_SUPERUSER)).first()
    assert user is not None
    assert user.id is not None
    return user
```

- [ ] **Step 7: Run the full test suite**

Run: `cd /home/rajgajjar04/Projects/AutoInvoice/backend && .venv/bin/pytest -q`
Expected: every `test_items.py` case passes (404/403/200 status codes and `detail` strings unchanged), plus everything from Task 4. Domains not yet migrated (customers, notifications, company_settings, tables, invoice_templates, invoices) still fail — expected, resolved by later tasks.

- [ ] **Step 8: Run mypy and ruff**

Run: `cd /home/rajgajjar04/Projects/AutoInvoice/backend && .venv/bin/mypy app && .venv/bin/ruff check app tests`
Expected: no errors for files touched in this task.

- [ ] **Step 9: Commit**

```bash
git add app/repositories/item_repository.py app/services/item_service.py app/api/deps.py app/api/routes/items.py tests/utils/item.py tests/api/routes/test_items.py
git commit -m "refactor: migrate Items domain to async repository + service layer"
```

---

## Task 6: Customers domain (async)

No existing tests today (`read_customer`/`update_customer`/`delete_customer` use
`session.get` + manual owner check, same shape as Items). Add a smoke test as
part of this task per the testing strategy.

- [ ] **Step 1: Create `app/repositories/customer_repository.py`**

```python
import uuid

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

    async def update(self, customer: Customer, update_data: dict) -> Customer:
        customer.sqlmodel_update(update_data)
        return await self.add(customer)
```

- [ ] **Step 2: Create `app/services/customer_service.py`**

```python
import uuid

from app.core.time import get_datetime_utc
from app.exceptions import ForbiddenError, NotFoundError
from app.models import Customer
from app.repositories.customer_repository import CustomerRepository
from app.schemas import CustomerCreate, CustomerUpdate


class CustomerService:
    def __init__(self, repo: CustomerRepository) -> None:
        self.repo = repo

    async def get_owned(self, customer_id: uuid.UUID, owner_id: uuid.UUID) -> Customer:
        customer = await self.repo.get(customer_id)
        if not customer:
            raise NotFoundError("Customer not found")
        if customer.owner_id != owner_id:
            raise ForbiddenError("Not enough permissions")
        return customer

    async def list(
        self, owner_id: uuid.UUID, *, skip: int, limit: int
    ) -> tuple[list[Customer], int]:
        return await self.repo.list_by_owner(owner_id, skip=skip, limit=limit)

    async def create(self, customer_in: CustomerCreate, owner_id: uuid.UUID) -> Customer:
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
```

- [ ] **Step 3: Add `CustomerRepository`/`CustomerService` providers to `app/api/deps.py`**

Add imports:
```python
from app.repositories.customer_repository import CustomerRepository
from app.services.customer_service import CustomerService
```

Add at the end of the file:
```python


def get_customer_repository(session: SessionDep) -> CustomerRepository:
    return CustomerRepository(session)


def get_customer_service(
    repo: Annotated[CustomerRepository, Depends(get_customer_repository)],
) -> CustomerService:
    return CustomerService(repo)


CustomerServiceDep = Annotated[CustomerService, Depends(get_customer_service)]
```

- [ ] **Step 4: Rewrite `app/api/routes/customers.py`**

```python
import uuid
from typing import Any

from fastapi import APIRouter

from app.api.deps import CurrentUser, CustomerServiceDep
from app.schemas import CustomerCreate, CustomerPublic, CustomersPublic, CustomerUpdate, Message

router = APIRouter(prefix="/customers", tags=["customers"])


@router.get("/", response_model=CustomersPublic)
async def read_customers(
    current_user: CurrentUser, customer_service: CustomerServiceDep, skip: int = 0, limit: int = 100
) -> Any:
    """Retrieve customers owned by the current user."""
    customers, count = await customer_service.list(current_user.id, skip=skip, limit=limit)
    return CustomersPublic(data=customers, count=count)


@router.get("/{id}", response_model=CustomerPublic)
async def read_customer(
    current_user: CurrentUser, customer_service: CustomerServiceDep, id: uuid.UUID
) -> Any:
    """Get customer by ID."""
    return await customer_service.get_owned(id, current_user.id)


@router.post("/", response_model=CustomerPublic)
async def create_customer(
    *, current_user: CurrentUser, customer_service: CustomerServiceDep, customer_in: CustomerCreate
) -> Any:
    """Create a new customer."""
    return await customer_service.create(customer_in, current_user.id)


@router.put("/{id}", response_model=CustomerPublic)
async def update_customer(
    *,
    current_user: CurrentUser,
    customer_service: CustomerServiceDep,
    id: uuid.UUID,
    customer_in: CustomerUpdate,
) -> Any:
    """Update a customer."""
    return await customer_service.update(id, current_user.id, customer_in)


@router.delete("/{id}")
async def delete_customer(
    current_user: CurrentUser, customer_service: CustomerServiceDep, id: uuid.UUID
) -> Message:
    """Delete a customer."""
    await customer_service.delete(id, current_user.id)
    return Message(message="Customer deleted successfully")
```

- [ ] **Step 5: Add `tests/utils/customer.py` (plain sync SQLModel calls)**

```python
import uuid

from sqlmodel import Session

from app.models import Customer
from app.schemas import CustomerCreate
from tests.utils.user import create_random_user
from tests.utils.utils import random_lower_string


def create_random_customer(db: Session, owner_id: uuid.UUID | None = None) -> Customer:
    if owner_id is None:
        user = create_random_user(db)
        owner_id = user.id
        assert owner_id is not None

    customer_in = CustomerCreate(name=random_lower_string())
    customer = Customer.model_validate(customer_in, update={"owner_id": owner_id})
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer
```

- [ ] **Step 6: Add `tests/api/routes/test_customers.py` smoke test**

```python
import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from tests.utils.customer import create_random_customer
from tests.utils.utils import random_lower_string


def test_create_customer(client: TestClient, normal_user_token_headers: dict[str, str]) -> None:
    data = {"name": random_lower_string()}
    response = client.post(
        f"{settings.API_V1_STR}/customers/", headers=normal_user_token_headers, json=data
    )
    assert response.status_code == 200
    content = response.json()
    assert content["name"] == data["name"]
    assert "id" in content


def test_read_customer(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    customer = create_random_customer(db)
    response = client.get(
        f"{settings.API_V1_STR}/customers/{customer.id}", headers=normal_user_token_headers
    )
    # Created by a different random owner than the normal test user, so this is forbidden.
    assert response.status_code == 403


def test_read_customer_not_found(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    response = client.get(
        f"{settings.API_V1_STR}/customers/{uuid.uuid4()}", headers=normal_user_token_headers
    )
    assert response.status_code == 404


def test_update_and_delete_customer(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    data = {"name": random_lower_string()}
    create_response = client.post(
        f"{settings.API_V1_STR}/customers/", headers=normal_user_token_headers, json=data
    )
    customer_id = create_response.json()["id"]

    update_data = {"name": "updated name"}
    update_response = client.put(
        f"{settings.API_V1_STR}/customers/{customer_id}",
        headers=normal_user_token_headers,
        json=update_data,
    )
    assert update_response.status_code == 200
    assert update_response.json()["name"] == "updated name"

    delete_response = client.delete(
        f"{settings.API_V1_STR}/customers/{customer_id}", headers=normal_user_token_headers
    )
    assert delete_response.status_code == 200
    assert delete_response.json()["message"] == "Customer deleted successfully"
```

Note: `test_read_customer` relies on `create_random_customer`'s default behavior of
creating a brand-new random owner when `owner_id` is omitted, which differs from
`normal_user_token_headers`'s fixed test user — this exercises the 403 ownership
path, mirroring the existing `test_items.py` pattern for ownership checks.

- [ ] **Step 7: Run the full test suite**

Run: `cd /home/rajgajjar04/Projects/AutoInvoice/backend && .venv/bin/pytest -q`
Expected: `test_customers.py` passes, plus everything from Tasks 4–5 still green.
Domains not yet migrated (notifications, company_settings, tables,
invoice_templates, invoices) still fail — expected.

- [ ] **Step 8: Run mypy and ruff**

Run: `cd /home/rajgajjar04/Projects/AutoInvoice/backend && .venv/bin/mypy app && .venv/bin/ruff check app tests`
Expected: no errors for files touched in this task.

- [ ] **Step 9: Commit**

```bash
git add app/repositories/customer_repository.py app/services/customer_service.py app/api/deps.py app/api/routes/customers.py tests/utils/customer.py tests/api/routes/test_customers.py
git commit -m "refactor: migrate Customers domain to async repository + service layer"
```

---

## Task 7: Notifications domain (async)

No existing tests today. `mark_all_read` and `clear_all` are bulk operations
on the full owner-filtered set — they don't fit `BaseRepository`'s per-object
methods, so `NotificationRepository` gets dedicated bulk methods.

- [ ] **Step 1: Create `app/repositories/notification_repository.py`**

```python
import uuid

from sqlmodel import col, func, select

from app.models import Notification, NotificationType
from app.repositories.base import BaseRepository
from app.schemas import NotificationCreate


class NotificationRepository(BaseRepository[Notification]):
    model = Notification

    async def list_filtered(
        self,
        owner_id: uuid.UUID,
        *,
        skip: int,
        limit: int,
        unread_only: bool,
        type: NotificationType | None,
    ) -> tuple[list[Notification], int, int]:
        base_filter = Notification.owner_id == owner_id
        if unread_only:
            base_filter = base_filter & (Notification.read == False)  # noqa: E712
        if type:
            base_filter = base_filter & (Notification.type == type)

        count_result = await self.session.exec(
            select(func.count()).select_from(Notification).where(base_filter)
        )
        count = count_result.one()

        unread_result = await self.session.exec(
            select(func.count())
            .select_from(Notification)
            .where(Notification.owner_id == owner_id, Notification.read == False)  # noqa: E712
        )
        unread_count = unread_result.one()

        statement = (
            select(Notification)
            .where(base_filter)
            .order_by(col(Notification.created_at).desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.exec(statement)
        return list(result.all()), count, unread_count

    async def create(
        self, notification_in: NotificationCreate, owner_id: uuid.UUID
    ) -> Notification:
        notification = Notification.model_validate(
            notification_in, update={"owner_id": owner_id}
        )
        return await self.add(notification)

    async def update(
        self, notification: Notification, update_data: dict
    ) -> Notification:
        notification.sqlmodel_update(update_data)
        return await self.add(notification)

    async def mark_all_read(self, owner_id: uuid.UUID) -> int:
        statement = select(Notification).where(
            Notification.owner_id == owner_id, Notification.read == False  # noqa: E712
        )
        result = await self.session.exec(statement)
        notifications = result.all()
        for notification in notifications:
            notification.read = True
            self.session.add(notification)
        await self.session.commit()
        return len(notifications)

    async def clear_all(self, owner_id: uuid.UUID) -> int:
        statement = select(Notification).where(Notification.owner_id == owner_id)
        result = await self.session.exec(statement)
        notifications = result.all()
        for notification in notifications:
            await self.session.delete(notification)
        await self.session.commit()
        return len(notifications)
```

- [ ] **Step 2: Create `app/services/notification_service.py`**

```python
import uuid

from app.exceptions import ForbiddenError, NotFoundError
from app.models import Notification, NotificationType
from app.repositories.notification_repository import NotificationRepository
from app.schemas import NotificationCreate, NotificationUpdate


class NotificationService:
    def __init__(self, repo: NotificationRepository) -> None:
        self.repo = repo

    async def get_owned(
        self, notification_id: uuid.UUID, owner_id: uuid.UUID
    ) -> Notification:
        notification = await self.repo.get(notification_id)
        if not notification:
            raise NotFoundError("Notification not found")
        if notification.owner_id != owner_id:
            raise ForbiddenError("Not enough permissions")
        return notification

    async def list(
        self,
        owner_id: uuid.UUID,
        *,
        skip: int,
        limit: int,
        unread_only: bool,
        type: NotificationType | None,
    ) -> tuple[list[Notification], int, int]:
        return await self.repo.list_filtered(
            owner_id, skip=skip, limit=limit, unread_only=unread_only, type=type
        )

    async def create(
        self, notification_in: NotificationCreate, owner_id: uuid.UUID
    ) -> Notification:
        return await self.repo.create(notification_in, owner_id)

    async def update(
        self,
        notification_id: uuid.UUID,
        owner_id: uuid.UUID,
        notification_in: NotificationUpdate,
    ) -> Notification:
        notification = await self.get_owned(notification_id, owner_id)
        update_data = notification_in.model_dump(exclude_unset=True)
        return await self.repo.update(notification, update_data)

    async def delete(self, notification_id: uuid.UUID, owner_id: uuid.UUID) -> None:
        notification = await self.get_owned(notification_id, owner_id)
        await self.repo.delete(notification)

    async def mark_all_read(self, owner_id: uuid.UUID) -> int:
        return await self.repo.mark_all_read(owner_id)

    async def clear_all(self, owner_id: uuid.UUID) -> int:
        return await self.repo.clear_all(owner_id)
```

- [ ] **Step 3: Add `NotificationRepository`/`NotificationService` providers to `app/api/deps.py`**

Add imports:
```python
from app.repositories.notification_repository import NotificationRepository
from app.services.notification_service import NotificationService
```

Add at the end of the file:
```python


def get_notification_repository(session: SessionDep) -> NotificationRepository:
    return NotificationRepository(session)


def get_notification_service(
    repo: Annotated[NotificationRepository, Depends(get_notification_repository)],
) -> NotificationService:
    return NotificationService(repo)


NotificationServiceDep = Annotated[NotificationService, Depends(get_notification_service)]
```

- [ ] **Step 4: Rewrite `app/api/routes/notifications.py`**

```python
import uuid
from typing import Any

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, NotificationServiceDep
from app.models import NotificationType
from app.schemas import (
    Message,
    NotificationCreate,
    NotificationPublic,
    NotificationsPublic,
    NotificationUpdate,
)

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("/", response_model=NotificationsPublic)
async def get_notifications(
    current_user: CurrentUser,
    notification_service: NotificationServiceDep,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    unread_only: bool = False,
    type: NotificationType | None = None,
) -> Any:
    """
    Get notifications for the current user.

    - **unread_only**: Only return unread notifications
    - **type**: Filter by notification type
    """
    notifications, count, unread_count = await notification_service.list(
        current_user.id, skip=skip, limit=limit, unread_only=unread_only, type=type
    )
    return NotificationsPublic(data=notifications, count=count, unread_count=unread_count)


@router.post("/", response_model=NotificationPublic)
async def create_notification(
    *,
    current_user: CurrentUser,
    notification_service: NotificationServiceDep,
    notification_in: NotificationCreate,
) -> Any:
    """Create a new notification."""
    return await notification_service.create(notification_in, current_user.id)


@router.get("/{id}", response_model=NotificationPublic)
async def get_notification(
    current_user: CurrentUser, notification_service: NotificationServiceDep, id: uuid.UUID
) -> Any:
    """Get a specific notification."""
    return await notification_service.get_owned(id, current_user.id)


@router.patch("/{id}", response_model=NotificationPublic)
async def update_notification(
    *,
    current_user: CurrentUser,
    notification_service: NotificationServiceDep,
    id: uuid.UUID,
    notification_in: NotificationUpdate,
) -> Any:
    """Update a notification (e.g., mark as read)."""
    return await notification_service.update(id, current_user.id, notification_in)


@router.post("/mark-all-read", response_model=Message)
async def mark_all_read(current_user: CurrentUser, notification_service: NotificationServiceDep) -> Any:
    """Mark all notifications as read."""
    n = await notification_service.mark_all_read(current_user.id)
    return Message(message=f"Marked {n} notifications as read")


@router.delete("/{id}")
async def delete_notification(
    current_user: CurrentUser, notification_service: NotificationServiceDep, id: uuid.UUID
) -> Message:
    """Delete a notification."""
    await notification_service.delete(id, current_user.id)
    return Message(message="Notification deleted successfully")


@router.delete("/")
async def clear_all(current_user: CurrentUser, notification_service: NotificationServiceDep) -> Message:
    """Delete all notifications for the current user."""
    n = await notification_service.clear_all(current_user.id)
    return Message(message=f"Deleted {n} notifications")
```

- [ ] **Step 5: Add `tests/api/routes/test_notifications.py` smoke test**

No `tests/utils/notification.py` is needed — notifications are simple enough
to create directly through the API in the test itself.

```python
from fastapi.testclient import TestClient

from app.core.config import settings


def test_create_and_list_notifications(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    data = {"title": "Test notification", "type": "info"}
    create_response = client.post(
        f"{settings.API_V1_STR}/notifications/", headers=normal_user_token_headers, json=data
    )
    assert create_response.status_code == 200
    notification_id = create_response.json()["id"]

    list_response = client.get(
        f"{settings.API_V1_STR}/notifications/", headers=normal_user_token_headers
    )
    assert list_response.status_code == 200
    content = list_response.json()
    assert content["count"] >= 1
    assert any(n["id"] == notification_id for n in content["data"])


def test_update_mark_read_and_delete(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    data = {"title": "Another notification", "type": "info"}
    create_response = client.post(
        f"{settings.API_V1_STR}/notifications/", headers=normal_user_token_headers, json=data
    )
    notification_id = create_response.json()["id"]

    update_response = client.patch(
        f"{settings.API_V1_STR}/notifications/{notification_id}",
        headers=normal_user_token_headers,
        json={"read": True},
    )
    assert update_response.status_code == 200
    assert update_response.json()["read"] is True

    delete_response = client.delete(
        f"{settings.API_V1_STR}/notifications/{notification_id}",
        headers=normal_user_token_headers,
    )
    assert delete_response.status_code == 200
    assert delete_response.json()["message"] == "Notification deleted successfully"


def test_mark_all_read_and_clear_all(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    for _ in range(2):
        client.post(
            f"{settings.API_V1_STR}/notifications/",
            headers=normal_user_token_headers,
            json={"title": "n", "type": "info"},
        )

    mark_response = client.post(
        f"{settings.API_V1_STR}/notifications/mark-all-read", headers=normal_user_token_headers
    )
    assert mark_response.status_code == 200

    clear_response = client.delete(
        f"{settings.API_V1_STR}/notifications/", headers=normal_user_token_headers
    )
    assert clear_response.status_code == 200
```

- [ ] **Step 6: Run the full test suite**

Run: `cd /home/rajgajjar04/Projects/AutoInvoice/backend && .venv/bin/pytest -q`
Expected: `test_notifications.py` passes, plus everything from Tasks 4–6 still
green. Domains not yet migrated (company_settings, tables, invoice_templates,
invoices) still fail — expected.

- [ ] **Step 7: Run mypy and ruff**

Run: `cd /home/rajgajjar04/Projects/AutoInvoice/backend && .venv/bin/mypy app && .venv/bin/ruff check app tests`
Expected: no errors for files touched in this task.

- [ ] **Step 8: Commit**

```bash
git add app/repositories/notification_repository.py app/services/notification_service.py app/api/deps.py app/api/routes/notifications.py tests/api/routes/test_notifications.py
git commit -m "refactor: migrate Notifications domain to async repository + service layer"
```

---

## Task 8: Company Settings domain (async)

Singleton-per-owner (`owner_id` is `unique=True`). No existing tests today.
`update_company_settings`'s upsert behavior (create-if-missing then update)
is preserved exactly.

- [ ] **Step 1: Create `app/repositories/company_settings_repository.py`**

```python
import uuid

from sqlmodel import select

from app.models import CompanySettings
from app.repositories.base import BaseRepository
from app.schemas import CompanySettingsCreate


class CompanySettingsRepository(BaseRepository[CompanySettings]):
    model = CompanySettings

    async def get_by_owner(self, owner_id: uuid.UUID) -> CompanySettings | None:
        statement = select(CompanySettings).where(CompanySettings.owner_id == owner_id)
        result = await self.session.exec(statement)
        return result.first()

    async def create(
        self, settings_in: CompanySettingsCreate, owner_id: uuid.UUID
    ) -> CompanySettings:
        settings = CompanySettings.model_validate(settings_in, update={"owner_id": owner_id})
        return await self.add(settings)

    async def create_default(self, owner_id: uuid.UUID, name: str) -> CompanySettings:
        settings = CompanySettings(owner_id=owner_id, name=name)
        return await self.add(settings)

    async def update(self, settings: CompanySettings, update_data: dict) -> CompanySettings:
        settings.sqlmodel_update(update_data)
        return await self.add(settings)
```

- [ ] **Step 2: Create `app/services/company_settings_service.py`**

```python
import uuid

from app.core.time import get_datetime_utc
from app.exceptions import ConflictError, NotFoundError
from app.models import CompanySettings
from app.repositories.company_settings_repository import CompanySettingsRepository
from app.schemas import CompanySettingsCreate, CompanySettingsUpdate


class CompanySettingsService:
    def __init__(self, repo: CompanySettingsRepository) -> None:
        self.repo = repo

    async def get_for_owner(self, owner_id: uuid.UUID) -> CompanySettings:
        settings = await self.repo.get_by_owner(owner_id)
        if not settings:
            raise NotFoundError("Company settings not found")
        return settings

    async def create(
        self, settings_in: CompanySettingsCreate, owner_id: uuid.UUID
    ) -> CompanySettings:
        existing = await self.repo.get_by_owner(owner_id)
        if existing:
            raise ConflictError("Company settings already exist")
        return await self.repo.create(settings_in, owner_id)

    async def upsert(
        self, owner_id: uuid.UUID, settings_in: CompanySettingsUpdate
    ) -> CompanySettings:
        settings = await self.repo.get_by_owner(owner_id)
        if not settings:
            settings = await self.repo.create_default(
                owner_id, settings_in.name or "My Company"
            )
        update_data = settings_in.model_dump(exclude_unset=True)
        update_data["updated_at"] = get_datetime_utc()
        return await self.repo.update(settings, update_data)

    async def delete(self, owner_id: uuid.UUID) -> None:
        settings = await self.get_for_owner(owner_id)
        await self.repo.delete(settings)
```

- [ ] **Step 3: Add `CompanySettingsRepository`/`CompanySettingsService` providers to `app/api/deps.py`**

Add imports:
```python
from app.repositories.company_settings_repository import CompanySettingsRepository
from app.services.company_settings_service import CompanySettingsService
```

Add at the end of the file:
```python


def get_company_settings_repository(session: SessionDep) -> CompanySettingsRepository:
    return CompanySettingsRepository(session)


def get_company_settings_service(
    repo: Annotated[CompanySettingsRepository, Depends(get_company_settings_repository)],
) -> CompanySettingsService:
    return CompanySettingsService(repo)


CompanySettingsServiceDep = Annotated[
    CompanySettingsService, Depends(get_company_settings_service)
]
```

- [ ] **Step 4: Rewrite `app/api/routes/company_settings.py`**

```python
from typing import Any

from fastapi import APIRouter

from app.api.deps import CompanySettingsServiceDep, CurrentUser
from app.schemas import (
    CompanySettingsCreate,
    CompanySettingsPublic,
    CompanySettingsUpdate,
    Message,
)

router = APIRouter(prefix="/company-settings", tags=["company-settings"])


@router.get("/", response_model=CompanySettingsPublic)
async def get_company_settings(
    current_user: CurrentUser, company_settings_service: CompanySettingsServiceDep
) -> Any:
    """Get company settings for the current user."""
    return await company_settings_service.get_for_owner(current_user.id)


@router.post("/", response_model=CompanySettingsPublic)
async def create_company_settings(
    *,
    current_user: CurrentUser,
    company_settings_service: CompanySettingsServiceDep,
    settings_in: CompanySettingsCreate,
) -> Any:
    """Create company settings for the current user."""
    return await company_settings_service.create(settings_in, current_user.id)


@router.put("/", response_model=CompanySettingsPublic)
async def update_company_settings(
    *,
    current_user: CurrentUser,
    company_settings_service: CompanySettingsServiceDep,
    settings_in: CompanySettingsUpdate,
) -> Any:
    """Update company settings for the current user."""
    return await company_settings_service.upsert(current_user.id, settings_in)


@router.delete("/", response_model=Message)
async def delete_company_settings(
    current_user: CurrentUser, company_settings_service: CompanySettingsServiceDep
) -> Any:
    """Delete company settings for the current user."""
    await company_settings_service.delete(current_user.id)
    return Message(message="Company settings deleted successfully")
```

- [ ] **Step 5: Add `tests/api/routes/test_company_settings.py` smoke test**

```python
from fastapi.testclient import TestClient

from app.core.config import settings


def test_get_company_settings_not_found(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    response = client.get(
        f"{settings.API_V1_STR}/company-settings/", headers=normal_user_token_headers
    )
    assert response.status_code == 404


def test_create_then_conflict(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    data = {"name": "Acme Inc"}
    first = client.post(
        f"{settings.API_V1_STR}/company-settings/", headers=normal_user_token_headers, json=data
    )
    assert first.status_code == 200
    assert first.json()["name"] == "Acme Inc"

    second = client.post(
        f"{settings.API_V1_STR}/company-settings/", headers=normal_user_token_headers, json=data
    )
    assert second.status_code == 400
    assert second.json()["detail"] == "Company settings already exist"


def test_upsert_and_delete(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    update_response = client.put(
        f"{settings.API_V1_STR}/company-settings/",
        headers=normal_user_token_headers,
        json={"name": "Upserted Co"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["name"] == "Upserted Co"

    delete_response = client.delete(
        f"{settings.API_V1_STR}/company-settings/", headers=normal_user_token_headers
    )
    assert delete_response.status_code == 200
    assert delete_response.json()["message"] == "Company settings deleted successfully"
```

Note: `tests/conftest.py`'s `db` fixture is **session-scoped** with no
per-test rollback (only `Item` and `User` rows get deleted, once, at session
teardown) — so `normal_user_token_headers` resolves to the same persistent
user, and `CompanySettings` rows survive across tests in this file. Since
`owner_id` is unique, these three tests are written to be order-dependent on
purpose: not-found check first (no settings yet) → create-then-conflict
(creates, leaves the row) → upsert-and-delete (updates the existing row, then
deletes it so the file ends with no leftover `CompanySettings` row for this
owner). Do not reorder these tests or add new ones in between without
accounting for this.

- [ ] **Step 6: Run the full test suite**

Run: `cd /home/rajgajjar04/Projects/AutoInvoice/backend && .venv/bin/pytest -q`
Expected: `test_company_settings.py` passes, plus everything from Tasks 4–7
still green. Domains not yet migrated (tables, invoice_templates, invoices)
still fail — expected.

- [ ] **Step 7: Run mypy and ruff**

Run: `cd /home/rajgajjar04/Projects/AutoInvoice/backend && .venv/bin/mypy app && .venv/bin/ruff check app tests`
Expected: no errors for files touched in this task.

- [ ] **Step 8: Commit**

```bash
git add app/repositories/company_settings_repository.py app/services/company_settings_service.py app/api/deps.py app/api/routes/company_settings.py tests/api/routes/test_company_settings.py
git commit -m "refactor: migrate Company Settings domain to async repository + service layer"
```

---

## Task 9: Tables (+rows+reminders) domain (async)

Most complex domain — has the existing `tests/api/routes/test_tables.py` (580
lines) which must keep passing exactly. `test_ownership_isolation`'s `crud`
usage was already fixed in Task 4 (it's about `User`, not `DataTable`).

**Async pitfall specific to this domain:** `GET /{table_id}` returns
`DataTableWithRows`, which Pydantic serializes by reading `table.rows` and
`table.reminders` — lazy SQLAlchemy relationships. Under `AsyncSession`,
accessing an unloaded relationship outside an `await` raises
`MissingGreenlet`/`greenlet_spawn has not been called`. The fix is to eager-load
both relationships with `selectinload` in the one repository method used for
this endpoint (`get_with_rows_and_reminders`), so by the time the route
returns, both lists are already in memory. Every other endpoint in this
domain returns `DataTablePublic` (no nested rows/reminders), so the plain
`get_by_id_and_owner` (no eager load) is fine for those. This exact pattern
recurs in Task 11 (Invoices) for `InvoiceWithCustomer.customer`.

- [ ] **Step 1: Create `app/repositories/table_repository.py`**

```python
import uuid
from typing import Any

from sqlalchemy.orm import selectinload
from sqlmodel import col, func, select

from app.models import DataTable, TableReminder, TableRow
from app.repositories.base import BaseRepository
from app.schemas import DataTableCreate, TableReminderCreate, TableRowCreate


class TableRepository(BaseRepository[DataTable]):
    model = DataTable

    async def get_by_id_and_owner(
        self, table_id: uuid.UUID, owner_id: uuid.UUID
    ) -> DataTable | None:
        statement = select(DataTable).where(
            DataTable.id == table_id, DataTable.owner_id == owner_id
        )
        result = await self.session.exec(statement)
        return result.first()

    async def get_with_rows_and_reminders(
        self, table_id: uuid.UUID, owner_id: uuid.UUID
    ) -> DataTable | None:
        statement = (
            select(DataTable)
            .where(DataTable.id == table_id, DataTable.owner_id == owner_id)
            .options(selectinload(DataTable.rows), selectinload(DataTable.reminders))
        )
        result = await self.session.exec(statement)
        return result.first()

    async def list_by_owner(
        self,
        owner_id: uuid.UUID,
        *,
        search: str | None,
        sort_by: str,
        sort_order: str,
        skip: int,
        limit: int,
    ) -> tuple[list[DataTable], int]:
        statement = select(DataTable).where(DataTable.owner_id == owner_id)
        if search:
            statement = statement.where(col(DataTable.name).ilike(f"%{search}%"))

        if sort_by == "name":
            statement = statement.order_by(
                col(DataTable.name).asc() if sort_order == "asc" else col(DataTable.name).desc()
            )
        else:
            statement = statement.order_by(
                col(DataTable.created_at).asc()
                if sort_order == "asc"
                else col(DataTable.created_at).desc()
            )

        count_statement = select(func.count()).select_from(statement.subquery())
        count_result = await self.session.exec(count_statement)
        total = count_result.one()

        statement = statement.offset(skip).limit(limit)
        result = await self.session.exec(statement)
        return list(result.all()), total

    async def create(self, table_in: DataTableCreate, owner_id: uuid.UUID) -> DataTable:
        table_data = table_in.model_dump()
        if table_data.get("columns") is not None:
            table_data["columns"] = [
                col.model_dump() if hasattr(col, "model_dump") else col
                for col in table_data["columns"]
            ]
        table = DataTable.model_validate(table_data, update={"owner_id": owner_id})
        return await self.add(table)

    async def update(self, table: DataTable, update_data: dict[str, Any]) -> DataTable:
        if update_data.get("columns") is not None:
            update_data["columns"] = [
                col.model_dump() if hasattr(col, "model_dump") else col
                for col in update_data["columns"]
            ]
        table.sqlmodel_update(update_data)
        return await self.add(table)

    async def duplicate(self, original: DataTable, owner_id: uuid.UUID) -> DataTable:
        columns = [
            col.model_dump() if hasattr(col, "model_dump") else col
            for col in (original.columns or [])
        ]
        new_table = DataTable(
            name=f"{original.name} (Copy)",
            description=original.description,
            columns=columns,
            owner_id=owner_id,
        )
        self.session.add(new_table)
        await self.session.flush()

        statement = select(TableRow).where(TableRow.table_id == original.id)
        result = await self.session.exec(statement)
        for original_row in result.all():
            self.session.add(TableRow(table_id=new_table.id, data=original_row.data))

        await self.session.commit()
        await self.session.refresh(new_table)
        return new_table

    async def add_row(self, table_id: uuid.UUID, row_in: TableRowCreate) -> TableRow:
        row = TableRow(table_id=table_id, data=row_in.data)
        self.session.add(row)
        await self.session.commit()
        await self.session.refresh(row)
        return row

    async def get_row(self, row_id: uuid.UUID) -> TableRow | None:
        return await self.session.get(TableRow, row_id)

    async def update_row(self, row: TableRow, data: dict[str, Any]) -> TableRow:
        row.data = data
        self.session.add(row)
        await self.session.commit()
        await self.session.refresh(row)
        return row

    async def delete_row(self, row: TableRow) -> None:
        await self.session.delete(row)
        await self.session.commit()

    async def bulk_delete_rows(self, table_id: uuid.UUID, row_ids: list[uuid.UUID]) -> int:
        statement = select(TableRow).where(
            TableRow.table_id == table_id, col(TableRow.id).in_(row_ids)
        )
        result = await self.session.exec(statement)
        rows = result.all()
        for row in rows:
            await self.session.delete(row)
        await self.session.commit()
        return len(rows)

    async def add_reminder(
        self, table_id: uuid.UUID, reminder_in: TableReminderCreate
    ) -> TableReminder:
        reminder = TableReminder(table_id=table_id, reminder_data=reminder_in.reminder_data)
        self.session.add(reminder)
        await self.session.commit()
        await self.session.refresh(reminder)
        return reminder

    async def get_reminder(self, reminder_id: uuid.UUID) -> TableReminder | None:
        return await self.session.get(TableReminder, reminder_id)

    async def delete_reminder(self, reminder: TableReminder) -> None:
        await self.session.delete(reminder)
        await self.session.commit()
```

- [ ] **Step 2: Create `app/services/table_service.py`**

```python
import uuid
from typing import Any

from app.exceptions import NotFoundError, ValidationError
from app.models import DataTable, TableReminder, TableRow
from app.repositories.table_repository import TableRepository
from app.schemas import (
    DataTableCreate,
    DataTableUpdate,
    TableReminderCreate,
    TableRowCreate,
    TableRowUpdate,
)


def _validate_row_data(
    columns: list[Any], row_data: dict[str, Any]
) -> tuple[bool, list[str]]:
    missing_fields = []
    for column in columns:
        if isinstance(column, dict):
            mandatory = column.get("mandatory", False)
            col_name = column.get("name")
        else:
            mandatory = bool(getattr(column, "mandatory", False))
            col_name = getattr(column, "name", None)

        if mandatory and col_name:
            if (
                col_name not in row_data
                or row_data[col_name] is None
                or row_data[col_name] == ""
            ):
                missing_fields.append(col_name)

    return (len(missing_fields) == 0, missing_fields)


class TableService:
    def __init__(self, repo: TableRepository) -> None:
        self.repo = repo

    async def get_table(self, table_id: uuid.UUID, owner_id: uuid.UUID) -> DataTable:
        table = await self.repo.get_by_id_and_owner(table_id, owner_id)
        if not table:
            raise NotFoundError("Table not found")
        return table

    async def get_table_with_rows(
        self, table_id: uuid.UUID, owner_id: uuid.UUID
    ) -> DataTable:
        table = await self.repo.get_with_rows_and_reminders(table_id, owner_id)
        if not table:
            raise NotFoundError("Table not found")
        return table

    async def list_tables(
        self,
        owner_id: uuid.UUID,
        *,
        skip: int,
        limit: int,
        sort_by: str,
        sort_order: str,
        search: str | None,
    ) -> tuple[list[DataTable], int]:
        return await self.repo.list_by_owner(
            owner_id, search=search, sort_by=sort_by, sort_order=sort_order, skip=skip, limit=limit
        )

    async def create_table(
        self, table_in: DataTableCreate, owner_id: uuid.UUID
    ) -> DataTable:
        column_names = [c.name for c in table_in.columns]
        if len(column_names) != len(set(column_names)):
            raise ValidationError("Column names must be unique")
        return await self.repo.create(table_in, owner_id)

    async def update_table(
        self, table_id: uuid.UUID, owner_id: uuid.UUID, table_in: DataTableUpdate
    ) -> DataTable:
        table = await self.get_table(table_id, owner_id)
        update_data = table_in.model_dump(exclude_unset=True)
        from app.core.time import get_datetime_utc

        update_data["updated_at"] = get_datetime_utc()
        return await self.repo.update(table, update_data)

    async def delete_table(self, table_id: uuid.UUID, owner_id: uuid.UUID) -> None:
        table = await self.get_table(table_id, owner_id)
        await self.repo.delete(table)

    async def duplicate_table(self, table_id: uuid.UUID, owner_id: uuid.UUID) -> DataTable:
        table = await self.get_table(table_id, owner_id)
        return await self.repo.duplicate(table, owner_id)

    async def add_row(
        self, table_id: uuid.UUID, owner_id: uuid.UUID, row_in: TableRowCreate
    ) -> TableRow:
        table = await self.get_table(table_id, owner_id)
        ok, missing = _validate_row_data(table.columns, row_in.data)
        if not ok:
            raise ValidationError(f"Missing mandatory fields: {', '.join(missing)}")
        return await self.repo.add_row(table_id, row_in)

    async def update_row(
        self,
        table_id: uuid.UUID,
        owner_id: uuid.UUID,
        row_id: uuid.UUID,
        row_in: TableRowUpdate,
    ) -> TableRow:
        table = await self.get_table(table_id, owner_id)
        row = await self.repo.get_row(row_id)
        if not row or row.table_id != table_id:
            raise NotFoundError("Row not found")

        ok, missing = _validate_row_data(table.columns, row_in.data)
        if not ok:
            raise ValidationError(f"Missing mandatory fields: {', '.join(missing)}")
        return await self.repo.update_row(row, row_in.data)

    async def delete_row(
        self, table_id: uuid.UUID, owner_id: uuid.UUID, row_id: uuid.UUID
    ) -> None:
        await self.get_table(table_id, owner_id)
        row = await self.repo.get_row(row_id)
        if not row or row.table_id != table_id:
            raise NotFoundError("Row not found")
        await self.repo.delete_row(row)

    async def bulk_delete_rows(
        self, table_id: uuid.UUID, owner_id: uuid.UUID, row_ids: list[uuid.UUID]
    ) -> int:
        await self.get_table(table_id, owner_id)
        return await self.repo.bulk_delete_rows(table_id, row_ids)

    async def add_reminder(
        self, table_id: uuid.UUID, owner_id: uuid.UUID, reminder_in: TableReminderCreate
    ) -> TableReminder:
        await self.get_table(table_id, owner_id)
        return await self.repo.add_reminder(table_id, reminder_in)

    async def delete_reminder(
        self, table_id: uuid.UUID, owner_id: uuid.UUID, reminder_id: uuid.UUID
    ) -> None:
        await self.get_table(table_id, owner_id)
        reminder = await self.repo.get_reminder(reminder_id)
        if not reminder or reminder.table_id != table_id:
            raise NotFoundError("Reminder not found")
        await self.repo.delete_reminder(reminder)
```

Note: `update_table`'s local `from app.core.time import get_datetime_utc`
mirrors the module-level import style used elsewhere in this plan — move it
to the top of the file alongside the other imports rather than leaving it
inline; it's written inline here only to keep this step's diff visually
scoped to the method being described.

- [ ] **Step 3: Add `TableRepository`/`TableService` providers to `app/api/deps.py`**

Add imports:
```python
from app.repositories.table_repository import TableRepository
from app.services.table_service import TableService
```

Add at the end of the file:
```python


def get_table_repository(session: SessionDep) -> TableRepository:
    return TableRepository(session)


def get_table_service(
    repo: Annotated[TableRepository, Depends(get_table_repository)],
) -> TableService:
    return TableService(repo)


TableServiceDep = Annotated[TableService, Depends(get_table_service)]
```

- [ ] **Step 4: Rewrite `app/api/routes/tables.py`**

```python
import uuid
from typing import Any

from fastapi import APIRouter, Query, status

from app.api.deps import CurrentUser, TableServiceDep
from app.schemas import (
    DataTableCreate,
    DataTablePublic,
    DataTableUpdate,
    DataTableWithRows,
    PaginatedResponse,
    TableReminderCreate,
    TableReminderPublic,
    TableRowCreate,
    TableRowPublic,
    TableRowUpdate,
)

router = APIRouter(prefix="/tables", tags=["tables"])


@router.get("", response_model=PaginatedResponse[DataTablePublic])
async def list_tables(
    current_user: CurrentUser,
    table_service: TableServiceDep,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    sort_by: str = Query("created_at", pattern="^(name|created_at)$"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    search: str | None = None,
) -> Any:
    """
    List all tables owned by the current user with pagination.

    - **skip**: Number of records to skip (default: 0)
    - **limit**: Number of records to return (default: 50, max: 100)
    - **sort_by**: Field to sort by (name or created_at)
    - **sort_order**: Sort direction (asc or desc)
    - **search**: Optional search term for table name
    """
    tables, total = await table_service.list_tables(
        current_user.id, skip=skip, limit=limit, sort_by=sort_by, sort_order=sort_order, search=search
    )
    return PaginatedResponse(
        data=list(tables),
        total=total,
        page=skip // limit + 1,
        page_size=limit,
        total_pages=(total + limit - 1) // limit,
    )


@router.post("", response_model=DataTablePublic, status_code=status.HTTP_201_CREATED)
async def create_table(
    current_user: CurrentUser, table_service: TableServiceDep, table_create: DataTableCreate
) -> Any:
    """
    Create a new data table with column definitions.

    - **name**: Table name (1-255 characters)
    - **columns**: Array of column definitions
    """
    return await table_service.create_table(table_create, current_user.id)


@router.get("/{table_id}", response_model=DataTableWithRows)
async def get_table(
    current_user: CurrentUser, table_service: TableServiceDep, table_id: uuid.UUID
) -> Any:
    """Get a specific table with all rows and reminders."""
    return await table_service.get_table_with_rows(table_id, current_user.id)


@router.patch("/{table_id}", response_model=DataTablePublic)
async def update_table(
    current_user: CurrentUser,
    table_service: TableServiceDep,
    table_id: uuid.UUID,
    table_update: DataTableUpdate,
) -> Any:
    """
    Update table name or column definitions.
    Only provided fields will be updated.
    """
    return await table_service.update_table(table_id, current_user.id, table_update)


@router.delete("/{table_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_table(
    current_user: CurrentUser, table_service: TableServiceDep, table_id: uuid.UUID
) -> None:
    """Delete a table and all associated rows (cascade)."""
    await table_service.delete_table(table_id, current_user.id)


@router.post("/{table_id}/duplicate", response_model=DataTablePublic)
async def duplicate_table(
    current_user: CurrentUser, table_service: TableServiceDep, table_id: uuid.UUID
) -> Any:
    """Duplicate a table with all its rows."""
    return await table_service.duplicate_table(table_id, current_user.id)


@router.post(
    "/{table_id}/rows", response_model=TableRowPublic, status_code=status.HTTP_201_CREATED
)
async def create_table_row(
    current_user: CurrentUser,
    table_service: TableServiceDep,
    table_id: uuid.UUID,
    row_create: TableRowCreate,
) -> Any:
    """Add a new row to a table."""
    return await table_service.add_row(table_id, current_user.id, row_create)


@router.put("/{table_id}/rows/{row_id}", response_model=TableRowPublic)
async def update_table_row(
    current_user: CurrentUser,
    table_service: TableServiceDep,
    table_id: uuid.UUID,
    row_id: uuid.UUID,
    row_update: TableRowUpdate,
) -> Any:
    """Update a specific row's data."""
    return await table_service.update_row(table_id, current_user.id, row_id, row_update)


@router.delete("/{table_id}/rows/{row_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_table_row(
    current_user: CurrentUser,
    table_service: TableServiceDep,
    table_id: uuid.UUID,
    row_id: uuid.UUID,
) -> None:
    """Delete a specific row."""
    await table_service.delete_row(table_id, current_user.id, row_id)


@router.post("/{table_id}/rows/bulk-delete")
async def bulk_delete_table_rows(
    current_user: CurrentUser,
    table_service: TableServiceDep,
    table_id: uuid.UUID,
    row_ids: list[uuid.UUID],
) -> Any:
    """Delete multiple rows in a single transaction."""
    deleted_count = await table_service.bulk_delete_rows(table_id, current_user.id, row_ids)
    return {"deleted": deleted_count}


@router.post(
    "/{table_id}/reminders",
    response_model=TableReminderPublic,
    status_code=status.HTTP_201_CREATED,
)
async def create_table_reminder(
    current_user: CurrentUser,
    table_service: TableServiceDep,
    table_id: uuid.UUID,
    reminder_create: TableReminderCreate,
) -> Any:
    """Create a reminder for a table."""
    return await table_service.add_reminder(table_id, current_user.id, reminder_create)


@router.delete("/{table_id}/reminders/{reminder_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_table_reminder(
    current_user: CurrentUser,
    table_service: TableServiceDep,
    table_id: uuid.UUID,
    reminder_id: uuid.UUID,
) -> None:
    """Delete a specific reminder."""
    await table_service.delete_reminder(table_id, current_user.id, reminder_id)
```

- [ ] **Step 5: Run the full test suite**

Run: `cd /home/rajgajjar04/Projects/AutoInvoice/backend && .venv/bin/pytest -q`
Expected: every existing `test_tables.py` case passes — pay special attention
to `test_get_table` and `test_duplicate_table` (exercise the eager-load path)
and `test_ownership_isolation` (exercises `NotFoundError` across an
`AsyncSession`/sync-`Session`-created user boundary, already fixed in Task
4). Plus everything from Tasks 4–8 still green. Domains not yet migrated
(invoice_templates, invoices) still fail — expected.

- [ ] **Step 6: Run mypy and ruff**

Run: `cd /home/rajgajjar04/Projects/AutoInvoice/backend && .venv/bin/mypy app && .venv/bin/ruff check app tests`
Expected: no errors for files touched in this task.

- [ ] **Step 7: Commit**

```bash
git add app/repositories/table_repository.py app/services/table_service.py app/api/deps.py app/api/routes/tables.py
git commit -m "refactor: migrate Tables domain to async repository + service layer"
```

---

## Task 10: Invoice Templates domain (async)

No existing tests today. `_ensure_valid_payload` (kind-specific field
validation) moves into the service and raises `ValidationError` instead of
inline `HTTPException(422, ...)`. The "deactivate all others when activating
one" logic (in `create`, `update`, and `activate`) is collected into a single
batch update per call — committing once, not once per changed row, matching
the original behavior's single-commit-per-request shape.

`excel_import_service.py` wraps `parse_excel_file` from `app/utils.py`, which
has **no DB access at all** (pure bytes-in, dict-out parsing) — like
`email_service.py` in Task 4, it stays a plain sync module with zero
`async`/`await`, just relocated under `app/services/` for consistency.

- [ ] **Step 1: Create `app/services/excel_import_service.py`**

```python
from typing import Any

from app.utils import parse_excel_file


def parse_excel_preview(file_content: bytes) -> dict[str, Any]:
    return parse_excel_file(file_content)
```

- [ ] **Step 2: Create `app/repositories/invoice_template_repository.py`**

```python
import uuid

from sqlmodel import col, func, select

from app.models import InvoiceTemplate
from app.repositories.base import BaseRepository
from app.schemas import InvoiceTemplateCreate


class InvoiceTemplateRepository(BaseRepository[InvoiceTemplate]):
    model = InvoiceTemplate

    async def list_by_owner(
        self, owner_id: uuid.UUID, *, skip: int, limit: int
    ) -> tuple[list[InvoiceTemplate], int]:
        count_result = await self.session.exec(
            select(func.count()).select_from(InvoiceTemplate).where(
                InvoiceTemplate.owner_id == owner_id
            )
        )
        count = count_result.one()

        statement = (
            select(InvoiceTemplate)
            .where(InvoiceTemplate.owner_id == owner_id)
            .order_by(col(InvoiceTemplate.updated_at).desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.exec(statement)
        return list(result.all()), count

    async def get_active(self, owner_id: uuid.UUID) -> InvoiceTemplate | None:
        statement = select(InvoiceTemplate).where(
            InvoiceTemplate.owner_id == owner_id,
            InvoiceTemplate.is_active == True,  # noqa: E712
        )
        result = await self.session.exec(statement)
        return result.first()

    async def list_others(
        self, owner_id: uuid.UUID, *, exclude_id: uuid.UUID | None = None
    ) -> list[InvoiceTemplate]:
        statement = select(InvoiceTemplate).where(InvoiceTemplate.owner_id == owner_id)
        if exclude_id is not None:
            statement = statement.where(InvoiceTemplate.id != exclude_id)
        result = await self.session.exec(statement)
        return list(result.all())

    async def create(
        self, template_in: InvoiceTemplateCreate, owner_id: uuid.UUID
    ) -> InvoiceTemplate:
        template = InvoiceTemplate.model_validate(template_in, update={"owner_id": owner_id})
        return await self.add(template)

    async def update(self, template: InvoiceTemplate, update_data: dict) -> InvoiceTemplate:
        template.sqlmodel_update(update_data)
        return await self.add(template)

    async def save_many(self, templates: list[InvoiceTemplate]) -> None:
        for template in templates:
            self.session.add(template)
        await self.session.commit()
```

- [ ] **Step 3: Create `app/services/invoice_template_service.py`**

```python
import uuid

from app.core.time import get_datetime_utc
from app.exceptions import ForbiddenError, NotFoundError, ValidationError
from app.models import InvoiceTemplate, InvoiceTemplateKind
from app.repositories.invoice_template_repository import InvoiceTemplateRepository
from app.schemas import InvoiceTemplateCreate, InvoiceTemplateUpdate


def _ensure_valid_payload(template: InvoiceTemplate) -> None:
    if template.kind == InvoiceTemplateKind.built_in:
        if not template.built_in_id:
            raise ValidationError("built_in_id is required for kind=built_in")
        if (
            template.custom_data is not None
            or template.imported_html
            or template.imported_pdf_data_url
        ):
            raise ValidationError("built_in templates cannot include custom/imported data")

    if template.kind == InvoiceTemplateKind.custom:
        if template.custom_data is None:
            raise ValidationError("custom_data is required for kind=custom")
        if template.built_in_id or template.imported_html or template.imported_pdf_data_url:
            raise ValidationError("custom templates cannot include built_in/imported data")

    if template.kind == InvoiceTemplateKind.imported_html:
        if not template.imported_html:
            raise ValidationError("imported_html is required for kind=imported_html")
        if (
            template.built_in_id
            or template.custom_data is not None
            or template.imported_pdf_data_url
        ):
            raise ValidationError(
                "imported_html templates cannot include other template data"
            )

    if template.kind == InvoiceTemplateKind.imported_pdf:
        if not template.imported_pdf_data_url:
            raise ValidationError("imported_pdf_data_url is required for kind=imported_pdf")
        if (
            template.built_in_id
            or template.custom_data is not None
            or template.imported_html
        ):
            raise ValidationError(
                "imported_pdf templates cannot include other template data"
            )

    if template.kind == InvoiceTemplateKind.imported_excel:
        if template.imported_excel_columns is None:
            raise ValidationError(
                "imported_excel_columns is required for kind=imported_excel"
            )
        if (
            template.built_in_id
            or template.custom_data is not None
            or template.imported_html
            or template.imported_pdf_data_url
        ):
            raise ValidationError(
                "imported_excel templates cannot include other template data"
            )


class InvoiceTemplateService:
    def __init__(self, repo: InvoiceTemplateRepository) -> None:
        self.repo = repo

    async def get_owned(
        self, template_id: uuid.UUID, owner_id: uuid.UUID
    ) -> InvoiceTemplate:
        template = await self.repo.get(template_id)
        if not template:
            raise NotFoundError("Invoice template not found")
        if template.owner_id != owner_id:
            raise ForbiddenError("Not enough permissions")
        return template

    async def list(
        self, owner_id: uuid.UUID, *, skip: int, limit: int
    ) -> tuple[list[InvoiceTemplate], int]:
        return await self.repo.list_by_owner(owner_id, skip=skip, limit=limit)

    async def get_active(self, owner_id: uuid.UUID) -> InvoiceTemplate:
        template = await self.repo.get_active(owner_id)
        if not template:
            raise NotFoundError("No active invoice template")
        return template

    async def create(
        self, template_in: InvoiceTemplateCreate, owner_id: uuid.UUID
    ) -> InvoiceTemplate:
        template = InvoiceTemplate.model_validate(template_in, update={"owner_id": owner_id})
        _ensure_valid_payload(template)

        if template.is_active:
            await self._deactivate_others(owner_id)

        self.repo.session.add(template)
        await self.repo.session.commit()
        await self.repo.session.refresh(template)
        return template

    async def update(
        self,
        template_id: uuid.UUID,
        owner_id: uuid.UUID,
        template_in: InvoiceTemplateUpdate,
    ) -> InvoiceTemplate:
        template = await self.get_owned(template_id, owner_id)
        update_data = template_in.model_dump(exclude_unset=True)

        template.sqlmodel_update(update_data)
        template.updated_at = get_datetime_utc()
        _ensure_valid_payload(template)

        if update_data.get("is_active") is True:
            await self._deactivate_others(owner_id, exclude_id=template.id)

        return await self.repo.update(template, {})

    async def activate(self, template_id: uuid.UUID, owner_id: uuid.UUID) -> InvoiceTemplate:
        template = await self.get_owned(template_id, owner_id)
        all_templates = await self.repo.list_others(owner_id)
        now = get_datetime_utc()

        changed = []
        for tpl in all_templates:
            next_active = tpl.id == template.id
            if tpl.is_active != next_active:
                tpl.is_active = next_active
                tpl.updated_at = now
                changed.append(tpl)

        if changed:
            await self.repo.save_many(changed)
        await self.repo.session.refresh(template)
        return template

    async def delete(self, template_id: uuid.UUID, owner_id: uuid.UUID) -> None:
        template = await self.get_owned(template_id, owner_id)
        await self.repo.delete(template)

    async def _deactivate_others(
        self, owner_id: uuid.UUID, *, exclude_id: uuid.UUID | None = None
    ) -> None:
        others = await self.repo.list_others(owner_id, exclude_id=exclude_id)
        changed = [o for o in others if o.is_active]
        for o in changed:
            o.is_active = False
            o.updated_at = get_datetime_utc()
        if changed:
            await self.repo.save_many(changed)
```

Note: `create()` and `update()` build the `InvoiceTemplate` object directly
(via `model_validate`/`sqlmodel_update`) rather than going through
`repo.create()`/`repo.update()`, because `_ensure_valid_payload` must run
*before* anything is committed, and the deactivate-others side effect must
share the same transaction. This mirrors the original route's structure,
just relocated. `repo.update(template, {})` in `update()` is a deliberate
no-op-update-data call — `sqlmodel_update` already applied the changes above
it; `repo.update()` is reused here only for its `add`/`commit`/`refresh`
sequence.

- [ ] **Step 4: Add `InvoiceTemplateRepository`/`InvoiceTemplateService` providers to `app/api/deps.py`**

Add imports:
```python
from app.repositories.invoice_template_repository import InvoiceTemplateRepository
from app.services.invoice_template_service import InvoiceTemplateService
```

Add at the end of the file:
```python


def get_invoice_template_repository(session: SessionDep) -> InvoiceTemplateRepository:
    return InvoiceTemplateRepository(session)


def get_invoice_template_service(
    repo: Annotated[InvoiceTemplateRepository, Depends(get_invoice_template_repository)],
) -> InvoiceTemplateService:
    return InvoiceTemplateService(repo)


InvoiceTemplateServiceDep = Annotated[
    InvoiceTemplateService, Depends(get_invoice_template_service)
]
```

- [ ] **Step 5: Rewrite `app/api/routes/invoice_templates.py`**

```python
import uuid
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.api.deps import CurrentUser, InvoiceTemplateServiceDep
from app.schemas import (
    InvoiceTemplateCreate,
    InvoiceTemplatePublic,
    InvoiceTemplatesPublic,
    InvoiceTemplateUpdate,
    Message,
)
from app.services.excel_import_service import parse_excel_preview as parse_excel

router = APIRouter(prefix="/invoice-templates", tags=["invoice-templates"])


@router.get("/", response_model=InvoiceTemplatesPublic)
async def read_invoice_templates(
    current_user: CurrentUser,
    invoice_template_service: InvoiceTemplateServiceDep,
    skip: int = 0,
    limit: int = 200,
) -> Any:
    data, count = await invoice_template_service.list(current_user.id, skip=skip, limit=limit)
    return InvoiceTemplatesPublic(data=data, count=count)


@router.get("/active", response_model=InvoiceTemplatePublic)
async def read_active_invoice_template(
    current_user: CurrentUser, invoice_template_service: InvoiceTemplateServiceDep
) -> Any:
    return await invoice_template_service.get_active(current_user.id)


@router.get("/{id}", response_model=InvoiceTemplatePublic)
async def read_invoice_template(
    current_user: CurrentUser, invoice_template_service: InvoiceTemplateServiceDep, id: uuid.UUID
) -> Any:
    return await invoice_template_service.get_owned(id, current_user.id)


@router.post("/", response_model=InvoiceTemplatePublic)
async def create_invoice_template(
    *,
    current_user: CurrentUser,
    invoice_template_service: InvoiceTemplateServiceDep,
    template_in: InvoiceTemplateCreate,
) -> Any:
    return await invoice_template_service.create(template_in, current_user.id)


@router.put("/{id}", response_model=InvoiceTemplatePublic)
async def update_invoice_template(
    *,
    current_user: CurrentUser,
    invoice_template_service: InvoiceTemplateServiceDep,
    id: uuid.UUID,
    template_in: InvoiceTemplateUpdate,
) -> Any:
    return await invoice_template_service.update(id, current_user.id, template_in)


@router.post("/{id}/activate", response_model=InvoiceTemplatePublic)
async def activate_invoice_template(
    current_user: CurrentUser, invoice_template_service: InvoiceTemplateServiceDep, id: uuid.UUID
) -> Any:
    return await invoice_template_service.activate(id, current_user.id)


@router.delete("/{id}")
async def delete_invoice_template(
    current_user: CurrentUser, invoice_template_service: InvoiceTemplateServiceDep, id: uuid.UUID
) -> Message:
    await invoice_template_service.delete(id, current_user.id)
    return Message(message="Invoice template deleted successfully")


@router.post("/parse-excel")
async def parse_excel_preview(
    _current_user: CurrentUser,
    file: UploadFile = File(...),
) -> Any:
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    allowed_extensions = [".xlsx", ".xls"]
    if not any(file.filename.lower().endswith(ext) for ext in allowed_extensions):
        raise HTTPException(
            status_code=400,
            detail="Invalid file type. Please upload an Excel file (.xlsx or .xls)",
        )

    try:
        file_content = file.file.read()
        if len(file_content) == 0:
            raise HTTPException(status_code=400, detail="Empty file provided")

        result = parse_excel(file_content)

        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])

        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error parsing Excel file: {str(e)}")
```

Note: `parse_excel_preview` stays a plain sync route handler in spirit (it
does no DB access — no `SessionDep`/`CurrentUser`-derived service call other
than the auth dependency itself), but is declared `async def` for consistency
with the rest of the file; FastAPI runs it the same either way since nothing
inside it awaits.

- [ ] **Step 6: Add `tests/api/routes/test_invoice_templates.py` smoke test**

```python
from fastapi.testclient import TestClient

from app.core.config import settings


def test_create_built_in_template(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    data = {"name": "Classic", "kind": "built_in", "built_in_id": "classic-1"}
    response = client.post(
        f"{settings.API_V1_STR}/invoice-templates/", headers=normal_user_token_headers, json=data
    )
    assert response.status_code == 200
    content = response.json()
    assert content["kind"] == "built_in"
    assert "id" in content


def test_create_built_in_template_missing_id(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    data = {"name": "Classic", "kind": "built_in"}
    response = client.post(
        f"{settings.API_V1_STR}/invoice-templates/", headers=normal_user_token_headers, json=data
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "built_in_id is required for kind=built_in"


def test_activate_deactivates_others(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    headers = normal_user_token_headers
    first = client.post(
        f"{settings.API_V1_STR}/invoice-templates/",
        headers=headers,
        json={"name": "A", "kind": "built_in", "built_in_id": "a", "is_active": True},
    )
    second = client.post(
        f"{settings.API_V1_STR}/invoice-templates/",
        headers=headers,
        json={"name": "B", "kind": "built_in", "built_in_id": "b"},
    )
    second_id = second.json()["id"]

    activate_response = client.post(
        f"{settings.API_V1_STR}/invoice-templates/{second_id}/activate", headers=headers
    )
    assert activate_response.status_code == 200
    assert activate_response.json()["is_active"] is True

    first_id = first.json()["id"]
    refreshed_first = client.get(
        f"{settings.API_V1_STR}/invoice-templates/{first_id}", headers=headers
    )
    assert refreshed_first.json()["is_active"] is False
```

- [ ] **Step 7: Run the full test suite**

Run: `cd /home/rajgajjar04/Projects/AutoInvoice/backend && .venv/bin/pytest -q`
Expected: `test_invoice_templates.py` passes, plus everything from Tasks 4–9
still green. Domain not yet migrated (invoices) still fails — expected.

- [ ] **Step 8: Run mypy and ruff**

Run: `cd /home/rajgajjar04/Projects/AutoInvoice/backend && .venv/bin/mypy app && .venv/bin/ruff check app tests`
Expected: no errors for files touched in this task.

- [ ] **Step 9: Commit**

```bash
git add app/services/excel_import_service.py app/repositories/invoice_template_repository.py app/services/invoice_template_service.py app/api/deps.py app/api/routes/invoice_templates.py tests/api/routes/test_invoice_templates.py
git commit -m "refactor: migrate Invoice Templates domain to async repository + service layer"
```

---

## Task 11: Invoices domain (async)

No existing tests today. Depends on `CustomerRepository` (Task 6) for the
`customer_id` ownership check on create/update. `GET /{id}` returns
`InvoiceWithCustomer`, which serializes `invoice.customer` — the same
eager-load pitfall as Task 9's `DataTableWithRows`, fixed the same way with
`selectinload(Invoice.customer)` in the one repository method used for that
endpoint.

- [ ] **Step 1: Create `app/repositories/invoice_repository.py`**

```python
import uuid
from typing import Any

from sqlalchemy.orm import selectinload
from sqlmodel import col, func, select

from app.models import Customer, Invoice, InvoiceStatus
from app.repositories.base import BaseRepository
from app.schemas import DocumentType, InvoiceCreate


class InvoiceRepository(BaseRepository[Invoice]):
    model = Invoice

    async def get_by_id_and_owner(
        self, invoice_id: uuid.UUID, owner_id: uuid.UUID
    ) -> Invoice | None:
        statement = select(Invoice).where(
            Invoice.id == invoice_id, Invoice.owner_id == owner_id
        )
        result = await self.session.exec(statement)
        return result.first()

    async def get_with_customer(
        self, invoice_id: uuid.UUID, owner_id: uuid.UUID
    ) -> Invoice | None:
        statement = (
            select(Invoice)
            .where(Invoice.id == invoice_id, Invoice.owner_id == owner_id)
            .options(selectinload(Invoice.customer))
        )
        result = await self.session.exec(statement)
        return result.first()

    async def list_filtered(
        self,
        owner_id: uuid.UUID,
        *,
        skip: int,
        limit: int,
        status: InvoiceStatus | None,
        document_type: DocumentType | None,
        customer_id: uuid.UUID | None,
    ) -> tuple[list[Invoice], int]:
        base_filter = Invoice.owner_id == owner_id
        if status:
            base_filter = base_filter & (Invoice.status == status)
        if document_type:
            base_filter = base_filter & (Invoice.document_type == document_type)
        if customer_id:
            base_filter = base_filter & (Invoice.customer_id == customer_id)

        count_result = await self.session.exec(
            select(func.count()).select_from(Invoice).where(base_filter)
        )
        count = count_result.one()

        statement = (
            select(Invoice)
            .where(base_filter)
            .order_by(col(Invoice.created_at).desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.exec(statement)
        return list(result.all()), count

    async def create(self, invoice_in: InvoiceCreate, owner_id: uuid.UUID) -> Invoice:
        invoice_data = invoice_in.model_dump()
        invoice_data["items"] = [
            item.model_dump() if hasattr(item, "model_dump") else item
            for item in invoice_in.items
        ]
        invoice_data["owner_id"] = owner_id
        invoice = Invoice(**invoice_data)
        return await self.add(invoice)

    async def update(self, invoice: Invoice, update_data: dict[str, Any]) -> Invoice:
        invoice.sqlmodel_update(update_data)
        return await self.add(invoice)

    async def get_stats(
        self, owner_id: uuid.UUID, *, document_type: DocumentType | None
    ) -> dict[str, Any]:
        base_filter = Invoice.owner_id == owner_id
        if document_type:
            base_filter = base_filter & (Invoice.document_type == document_type)

        total_result = await self.session.exec(
            select(func.count()).select_from(Invoice).where(base_filter)
        )
        total_invoices = total_result.one()

        paid_result = await self.session.exec(
            select(func.count())
            .select_from(Invoice)
            .where(base_filter, Invoice.status == InvoiceStatus.paid)
        )
        paid_count = paid_result.one()

        unpaid_result = await self.session.exec(
            select(func.count())
            .select_from(Invoice)
            .where(base_filter, Invoice.status == InvoiceStatus.unpaid)
        )
        unpaid_count = unpaid_result.one()

        overdue_result = await self.session.exec(
            select(func.count())
            .select_from(Invoice)
            .where(base_filter, Invoice.status == InvoiceStatus.overdue)
        )
        overdue_count = overdue_result.one()

        total_customers_result = await self.session.exec(
            select(func.count()).select_from(Customer).where(Customer.owner_id == owner_id)
        )
        total_customers = total_customers_result.one()

        total_revenue_result = await self.session.exec(
            select(func.coalesce(func.sum(Invoice.grand_total), 0)).where(
                base_filter, Invoice.status == InvoiceStatus.paid
            )
        )
        total_revenue = total_revenue_result.one()

        return {
            "total_invoices": total_invoices,
            "paid_count": paid_count,
            "unpaid_count": unpaid_count,
            "overdue_count": overdue_count,
            "total_customers": total_customers,
            "total_revenue": float(total_revenue),
        }
```

- [ ] **Step 2: Create `app/services/invoice_service.py`**

```python
import uuid

from app.core.time import get_datetime_utc
from app.exceptions import ForbiddenError, NotFoundError
from app.models import DashboardStats, DocumentType, Invoice, InvoiceStatus
from app.repositories.customer_repository import CustomerRepository
from app.repositories.invoice_repository import InvoiceRepository
from app.schemas import InvoiceCreate, InvoiceUpdate


class InvoiceService:
    def __init__(self, repo: InvoiceRepository, customer_repo: CustomerRepository) -> None:
        self.repo = repo
        self.customer_repo = customer_repo

    async def get_owned(self, invoice_id: uuid.UUID, owner_id: uuid.UUID) -> Invoice:
        invoice = await self.repo.get_by_id_and_owner(invoice_id, owner_id)
        if not invoice:
            raise NotFoundError("Invoice not found")
        return invoice

    async def get_with_customer(self, invoice_id: uuid.UUID, owner_id: uuid.UUID) -> Invoice:
        invoice = await self.repo.get_with_customer(invoice_id, owner_id)
        if not invoice:
            raise NotFoundError("Invoice not found")
        return invoice

    async def list(
        self,
        owner_id: uuid.UUID,
        *,
        skip: int,
        limit: int,
        status: InvoiceStatus | None,
        document_type: DocumentType | None,
        customer_id: uuid.UUID | None,
    ) -> tuple[list[Invoice], int]:
        return await self.repo.list_filtered(
            owner_id,
            skip=skip,
            limit=limit,
            status=status,
            document_type=document_type,
            customer_id=customer_id,
        )

    async def create(self, invoice_in: InvoiceCreate, owner_id: uuid.UUID) -> Invoice:
        customer = await self.customer_repo.get(invoice_in.customer_id)
        if not customer:
            raise NotFoundError("Customer not found")
        if customer.owner_id != owner_id:
            raise ForbiddenError("Customer does not belong to you")
        return await self.repo.create(invoice_in, owner_id)

    async def update(
        self, invoice_id: uuid.UUID, owner_id: uuid.UUID, invoice_in: InvoiceUpdate
    ) -> Invoice:
        invoice = await self.get_owned(invoice_id, owner_id)
        update_data = invoice_in.model_dump(exclude_unset=True)

        if update_data.get("customer_id") is not None:
            customer = await self.customer_repo.get(update_data["customer_id"])
            if not customer or customer.owner_id != owner_id:
                raise NotFoundError("Customer not found")

        if update_data.get("items") is not None:
            update_data["items"] = [
                item.model_dump() if hasattr(item, "model_dump") else item
                for item in update_data["items"]
            ]

        update_data["updated_at"] = get_datetime_utc()
        return await self.repo.update(invoice, update_data)

    async def delete(self, invoice_id: uuid.UUID, owner_id: uuid.UUID) -> None:
        invoice = await self.get_owned(invoice_id, owner_id)
        await self.repo.delete(invoice)

    async def get_dashboard_stats(
        self, owner_id: uuid.UUID, *, document_type: DocumentType | None
    ) -> DashboardStats:
        stats = await self.repo.get_stats(owner_id, document_type=document_type)
        return DashboardStats(**stats)
```

Note: `update()`'s customer-reassignment check raises `NotFoundError` (→404)
for both "no such customer" and "customer belongs to someone else" — this
matches the original route's behavior exactly (`if not customer or
customer.owner_id != current_user.id: raise HTTPException(status_code=404,
...)`), which is intentionally different from `create()`'s split between 404
(no such customer) and 403 (`ForbiddenError`, "Customer does not belong to
you"). Do not "fix" this asymmetry — it's preserved from the original code,
not an oversight.

- [ ] **Step 3: Add `InvoiceRepository`/`InvoiceService` providers to `app/api/deps.py`**

`InvoiceService` needs both `InvoiceRepository` and `CustomerRepository`, so
its service provider takes both repos as dependencies.

Add imports:
```python
from app.repositories.invoice_repository import InvoiceRepository
from app.services.invoice_service import InvoiceService
```

Add at the end of the file:
```python


def get_invoice_repository(session: SessionDep) -> InvoiceRepository:
    return InvoiceRepository(session)


def get_invoice_service(
    repo: Annotated[InvoiceRepository, Depends(get_invoice_repository)],
    customer_repo: Annotated[CustomerRepository, Depends(get_customer_repository)],
) -> InvoiceService:
    return InvoiceService(repo, customer_repo)


InvoiceServiceDep = Annotated[InvoiceService, Depends(get_invoice_service)]
```

- [ ] **Step 4: Rewrite `app/api/routes/invoices.py`**

```python
import uuid
from typing import Any

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, InvoiceServiceDep
from app.models import DocumentType, InvoiceStatus
from app.schemas import (
    DashboardStats,
    InvoiceCreate,
    InvoicePublic,
    InvoicesPublic,
    InvoiceUpdate,
    InvoiceWithCustomer,
    Message,
)

router = APIRouter(prefix="/invoices", tags=["invoices"])


@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats(
    current_user: CurrentUser,
    invoice_service: InvoiceServiceDep,
    document_type: DocumentType | None = None,
) -> Any:
    """
    Get dashboard statistics for the current user.

    - **document_type**: Filter stats by document type (invoice, quotation, proforma, challan)
    """
    return await invoice_service.get_dashboard_stats(current_user.id, document_type=document_type)


@router.get("/", response_model=InvoicesPublic)
async def read_invoices(
    current_user: CurrentUser,
    invoice_service: InvoiceServiceDep,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    status: InvoiceStatus | None = None,
    document_type: DocumentType | None = None,
    customer_id: uuid.UUID | None = None,
) -> Any:
    """
    Retrieve invoices owned by the current user.

    - **status**: Filter by invoice status
    - **document_type**: Filter by document type (invoice, quotation, proforma, challan)
    - **customer_id**: Filter by customer
    """
    invoices, count = await invoice_service.list(
        current_user.id,
        skip=skip,
        limit=limit,
        status=status,
        document_type=document_type,
        customer_id=customer_id,
    )
    return InvoicesPublic(data=invoices, count=count)


@router.get("/{id}", response_model=InvoiceWithCustomer)
async def read_invoice(
    current_user: CurrentUser, invoice_service: InvoiceServiceDep, id: uuid.UUID
) -> Any:
    """Get invoice by ID with customer details."""
    return await invoice_service.get_with_customer(id, current_user.id)


@router.post("/", response_model=InvoicePublic)
async def create_invoice(
    *, current_user: CurrentUser, invoice_service: InvoiceServiceDep, invoice_in: InvoiceCreate
) -> Any:
    """
    Create a new invoice/quotation/proforma/challan.

    Set **document_type** to create different document types:
    - invoice: Regular invoice
    - quotation: Price quote with validity period
    - proforma: Proforma invoice
    - challan: Delivery challan
    """
    return await invoice_service.create(invoice_in, current_user.id)


@router.put("/{id}", response_model=InvoicePublic)
async def update_invoice(
    *,
    current_user: CurrentUser,
    invoice_service: InvoiceServiceDep,
    id: uuid.UUID,
    invoice_in: InvoiceUpdate,
) -> Any:
    """Update an invoice."""
    return await invoice_service.update(id, current_user.id, invoice_in)


@router.delete("/{id}")
async def delete_invoice(
    current_user: CurrentUser, invoice_service: InvoiceServiceDep, id: uuid.UUID
) -> Message:
    """Delete an invoice."""
    await invoice_service.delete(id, current_user.id)
    return Message(message="Invoice deleted successfully")
```

- [ ] **Step 5: Add `tests/api/routes/test_invoices.py` smoke test**

```python
from fastapi.testclient import TestClient

from app.core.config import settings


def _create_customer(client: TestClient, headers: dict[str, str]) -> str:
    response = client.post(
        f"{settings.API_V1_STR}/customers/", headers=headers, json={"name": "Acme"}
    )
    customer_id: str = response.json()["id"]
    return customer_id


def test_create_and_read_invoice(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    headers = normal_user_token_headers
    customer_id = _create_customer(client, headers)

    data = {
        "invoice_number": "INV-0001",
        "invoice_date": "2026-01-01",
        "customer_id": customer_id,
        "items": [{"name": "Widget", "quantity": 2, "price": 10}],
    }
    create_response = client.post(f"{settings.API_V1_STR}/invoices/", headers=headers, json=data)
    assert create_response.status_code == 200
    invoice_id = create_response.json()["id"]

    read_response = client.get(f"{settings.API_V1_STR}/invoices/{invoice_id}", headers=headers)
    assert read_response.status_code == 200
    content = read_response.json()
    assert content["customer"]["id"] == customer_id


def test_create_invoice_customer_not_found(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    data = {
        "invoice_number": "INV-0002",
        "invoice_date": "2026-01-01",
        "customer_id": "00000000-0000-0000-0000-000000000000",
        "items": [],
    }
    response = client.post(
        f"{settings.API_V1_STR}/invoices/", headers=normal_user_token_headers, json=data
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Customer not found"


def test_dashboard_stats(client: TestClient, normal_user_token_headers: dict[str, str]) -> None:
    response = client.get(
        f"{settings.API_V1_STR}/invoices/stats", headers=normal_user_token_headers
    )
    assert response.status_code == 200
    content = response.json()
    assert "total_invoices" in content
    assert "total_revenue" in content


def test_delete_invoice(client: TestClient, normal_user_token_headers: dict[str, str]) -> None:
    headers = normal_user_token_headers
    customer_id = _create_customer(client, headers)
    data = {
        "invoice_number": "INV-0003",
        "invoice_date": "2026-01-01",
        "customer_id": customer_id,
        "items": [],
    }
    create_response = client.post(f"{settings.API_V1_STR}/invoices/", headers=headers, json=data)
    invoice_id = create_response.json()["id"]

    delete_response = client.delete(f"{settings.API_V1_STR}/invoices/{invoice_id}", headers=headers)
    assert delete_response.status_code == 200
    assert delete_response.json()["message"] == "Invoice deleted successfully"
```

- [ ] **Step 6: Run the full test suite**

Run: `cd /home/rajgajjar04/Projects/AutoInvoice/backend && .venv/bin/pytest -q`
Expected: every domain test file is now green — this is the first full
green run since the migration started. No domain remains on the old
`crud.py`/fat-route shape except the cleanup itself (Task 12).

- [ ] **Step 7: Run mypy and ruff**

Run: `cd /home/rajgajjar04/Projects/AutoInvoice/backend && .venv/bin/mypy app && .venv/bin/ruff check app tests`
Expected: no errors for files touched in this task.

- [ ] **Step 8: Commit**

```bash
git add app/repositories/invoice_repository.py app/services/invoice_service.py app/api/deps.py app/api/routes/invoices.py tests/api/routes/test_invoices.py
git commit -m "refactor: migrate Invoices domain to async repository + service layer"
```

---

## Task 12: Cleanup

By this point every domain has been migrated off `app/crud.py`, so it should
be fully orphaned. This task verifies that and deletes it.

- [ ] **Step 1: Verify `app/crud.py` has no remaining importers**

Run: `cd /home/rajgajjar04/Projects/AutoInvoice/backend && grep -rn "from app import crud\|from app\.crud" app tests`
Expected: no output (Tasks 4–11 already removed every importer — `app/api/deps.py`,
every route file, `app/core/db.py`'s `init_db`, `tests/utils/user.py`,
`tests/utils/item.py`, `tests/api/routes/test_users.py`,
`tests/api/routes/test_items.py`, `tests/api/routes/test_tables.py`, and
`tests/crud/test_user.py` which was deleted entirely in Task 4). If this
finds anything, stop and fix that importer first — do not delete `crud.py`
underneath a live caller.

- [ ] **Step 2: Delete `app/crud.py`**

```bash
git rm app/crud.py
```

- [ ] **Step 3: Full verification sweep**

Run, in order, stopping to fix at the first failure:
```bash
cd /home/rajgajjar04/Projects/AutoInvoice/backend
.venv/bin/pytest -q
.venv/bin/mypy app
.venv/bin/ruff check app tests
```
Expected: all green. This is the final regression gate for the entire
restructure — every domain's existing tests (`test_items.py`, `test_tables.py`,
`test_users.py`, `test_login.py`, `test_private.py`) plus every new smoke test
(`test_admin.py`, `test_customers.py`, `test_notifications.py`,
`test_company_settings.py`, `test_invoice_templates.py`, `test_invoices.py`)
must pass.

- [ ] **Step 4: Confirm no leftover references to the old flat structure**

Run: `cd /home/rajgajjar04/Projects/AutoInvoice/backend && grep -rn "app\.models\.models\|app/models\.py" app tests; ls app/models.py 2>&1; ls app/crud.py 2>&1`
Expected: no grep matches, and both `ls` commands report "No such file or
directory" (both were already deleted — `app/models.py` in Task 1,
`app/crud.py` in Step 2 above).

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor: remove app/crud.py now that every domain has a repository + service"
```

---

## Plan self-review notes

- **Spec coverage:** every domain listed in the design spec's "Migration
  order" (scaffolding, User/Auth, Items, Customers, Notifications, Company
  Settings, Tables, Invoice Templates, Invoices, Cleanup) has a corresponding
  task here (Tasks 1–3 cover scaffolding split across the models/schemas
  split and the async DB foundation; Tasks 4–11 cover each domain 1:1; Task
  12 is cleanup).
- **Async eager-loading pitfall** is called out explicitly in both places it
  applies (Task 9's `DataTableWithRows`, Task 11's `InvoiceWithCustomer`) —
  this is the one correctness risk specific to the async pivot that has no
  analog in a sync `Session` (lazy-loading just works there); every other
  task's repository methods are a mechanical `await`-ification of the
  original `crud.py` query, so this is the one place reviewers should look
  twice during execution.
- **`ConflictError`→400** convention is applied consistently in Task 8
  (Company Settings `create`) — the only other domain with an "already
  exists" conflict besides signup (already handled via `HTTPException` in
  `auth.py`, left untouched per the Global Constraints).
- **Bulk-operation / multi-commit consistency**: Task 7's
  `mark_all_read`/`clear_all` and Task 10's `_deactivate_others`/`activate`
  both batch their changes into a single `commit()` rather than one commit
  per row, matching the original single-transaction-per-request behavior and
  avoiding the multi-commit bug caught in self-review of the original sync
  plan (`InvoiceTemplateService.activate`).
- **No new test infrastructure**: every new smoke test added in Tasks 6, 7,
  8, 10, 11 (and `test_admin.py` in Task 4) drives the app exclusively
  through `TestClient` HTTP calls — none of them instantiate a repository or
  service directly, so none of them need `pytest-asyncio`/`anyio`, consistent
  with the Async I/O section of the design spec.

---
