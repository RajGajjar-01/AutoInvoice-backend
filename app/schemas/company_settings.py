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

    whatsapp_enabled: bool = False
    openwa_base_url: str = Field(default="http://localhost:2785", max_length=500)
    openwa_api_key: str | None = Field(default=None, max_length=500)
    openwa_session_id: str | None = Field(default=None, max_length=255)

    smtp_host: str | None = Field(default=None, max_length=255)
    smtp_port: int = 587
    smtp_user: str | None = Field(default=None, max_length=255)
    smtp_password: str | None = Field(default=None, max_length=500)
    smtp_tls: bool = True
    emails_from_email: str | None = Field(default=None, max_length=255)
    emails_from_name: str | None = Field(default=None, max_length=255)


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

    whatsapp_enabled: bool | None = None
    openwa_base_url: str | None = Field(default=None, max_length=500)
    openwa_api_key: str | None = Field(default=None, max_length=500)
    openwa_session_id: str | None = Field(default=None, max_length=255)

    smtp_host: str | None = Field(default=None, max_length=255)
    smtp_port: int | None = None
    smtp_user: str | None = Field(default=None, max_length=255)
    smtp_password: str | None = Field(default=None, max_length=500)
    smtp_tls: bool | None = None
    emails_from_email: str | None = Field(default=None, max_length=255)
    emails_from_name: str | None = Field(default=None, max_length=255)


class CompanySettingsPublic(CompanySettingsBase):
    id: uuid.UUID
    owner_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
