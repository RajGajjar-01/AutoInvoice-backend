import uuid
from datetime import date, datetime
from enum import Enum
from typing import Literal

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
    discount: float = Field(default=0, ge=0)
    discount_type: Literal["percent", "flat"] | None = None


class InvoiceBankDetails(SQLModel):
    """Bank details printed on one invoice instead of the company defaults."""

    bank_name: str | None = Field(default=None, max_length=100)
    account_name: str | None = Field(default=None, max_length=255)
    account_number: str | None = Field(default=None, max_length=50)
    ifsc: str | None = Field(default=None, max_length=20)
    branch: str | None = Field(default=None, max_length=100)
    upi: str | None = Field(default=None, max_length=256)


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
    vehicle_info: str | None = Field(default=None, max_length=200)
    delivery_notes: str | None = Field(default=None, max_length=1000)
    po_number: str | None = Field(default=None, max_length=100)
    discount_type: str | None = Field(default=None, max_length=10)
    discount_value: float = Field(default=0, ge=0)
    shipping_charge: float = Field(default=0, ge=0)
    extra_charge_label: str | None = Field(default=None, max_length=100)
    extra_charge_amount: float = Field(default=0, ge=0)
    round_off: bool = False


class InvoiceCreate(InvoiceBase):
    customer_id: uuid.UUID
    items: list[InvoiceItemData] = []
    discount_type: Literal["percent", "flat"] | None = None
    bank_details: InvoiceBankDetails | None = None


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
    vehicle_info: str | None = Field(default=None, max_length=200)
    delivery_notes: str | None = Field(default=None, max_length=1000)
    customer_id: uuid.UUID | None = None
    items: list[InvoiceItemData] | None = None
    po_number: str | None = Field(default=None, max_length=100)
    discount_type: Literal["percent", "flat"] | None = None
    discount_value: float | None = Field(default=None, ge=0)
    shipping_charge: float | None = Field(default=None, ge=0)
    extra_charge_label: str | None = Field(default=None, max_length=100)
    extra_charge_amount: float | None = Field(default=None, ge=0)
    round_off: bool | None = None
    bank_details: InvoiceBankDetails | None = None


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
