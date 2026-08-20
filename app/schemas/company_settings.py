import re
import uuid
from datetime import datetime

from pydantic import field_validator
from sqlmodel import Field, SQLModel

GSTIN_REGEX = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$")
PAN_REGEX = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]{1}$")
IFSC_REGEX = re.compile(r"^[A-Z]{4}0[A-Z0-9]{6}$")
BANK_ACCOUNT_REGEX = re.compile(r"^[0-9]{9,18}$")
UPI_ID_REGEX = re.compile(r"^[a-zA-Z0-9.\-_]{2,256}@[a-zA-Z]{2,64}$")


class CompanySettingsBase(SQLModel):
    name: str = Field(min_length=1, max_length=255)
    gstin: str | None = Field(default=None, max_length=50)
    pan: str | None = Field(default=None, max_length=500)
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
    bank_account: str | None = Field(default=None, max_length=500)
    bank_ifsc: str | None = Field(default=None, max_length=500)
    bank_branch: str | None = Field(default=None, max_length=100)
    upi_id: str | None = Field(default=None, max_length=500)
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

    @field_validator("gstin", mode="before")
    @classmethod
    def validate_gstin(cls, v: str | None) -> str | None:
        if not v or not str(v).strip():
            return None
        v_clean = str(v).strip().upper()
        if not GSTIN_REGEX.match(v_clean):
            raise ValueError(
                "Invalid GSTIN format. Expected 15 characters (e.g. 22AAAAA0000A1Z5)"
            )
        return v_clean

    @field_validator("pan", mode="before")
    @classmethod
    def validate_pan(cls, v: str | None) -> str | None:
        if not v or not str(v).strip():
            return None
        v_clean = str(v).strip().upper()
        # If it's already an encrypted string (e.g. during internal validation), allow it
        if v_clean.startswith("V1:") or v_clean.startswith("GAAAAA"):
            return v
        if not PAN_REGEX.match(v_clean):
            raise ValueError(
                "Invalid PAN format. Expected 10 alphanumeric characters (e.g. ABCDE1234F)"
            )
        return v_clean

    @field_validator("bank_ifsc", mode="before")
    @classmethod
    def validate_bank_ifsc(cls, v: str | None) -> str | None:
        if not v or not str(v).strip():
            return None
        v_clean = str(v).strip().upper()
        if v_clean.startswith("V1:") or v_clean.startswith("GAAAAA"):
            return v
        if not IFSC_REGEX.match(v_clean):
            raise ValueError(
                "Invalid IFSC format. Expected 11 characters (e.g. SBIN0001234)"
            )
        return v_clean

    @field_validator("bank_account", mode="before")
    @classmethod
    def validate_bank_account(cls, v: str | None) -> str | None:
        if not v or not str(v).strip():
            return None
        v_clean = str(v).strip()
        if v_clean.startswith("v1:") or v_clean.startswith("gAAAAA"):
            return v
        if not BANK_ACCOUNT_REGEX.match(v_clean):
            raise ValueError(
                "Invalid bank account number. Expected 9 to 18 numeric digits"
            )
        return v_clean

    @field_validator("upi_id", mode="before")
    @classmethod
    def validate_upi_id(cls, v: str | None) -> str | None:
        if not v or not str(v).strip():
            return None
        v_clean = str(v).strip().lower()
        if v_clean.startswith("v1:") or v_clean.startswith("gaaaaa"):
            return v
        if not UPI_ID_REGEX.match(v_clean):
            raise ValueError("Invalid UPI ID format (e.g. username@okhdfcbank)")
        return v_clean


class CompanySettingsCreate(CompanySettingsBase):
    pass


class CompanySettingsUpdate(SQLModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    gstin: str | None = Field(default=None, max_length=50)
    pan: str | None = Field(default=None, max_length=500)
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
    bank_account: str | None = Field(default=None, max_length=500)
    bank_ifsc: str | None = Field(default=None, max_length=500)
    bank_branch: str | None = Field(default=None, max_length=100)
    upi_id: str | None = Field(default=None, max_length=500)
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

    @field_validator("gstin", mode="before")
    @classmethod
    def validate_gstin(cls, v: str | None) -> str | None:
        if v is None or not str(v).strip():
            return None
        v_clean = str(v).strip().upper()
        if not GSTIN_REGEX.match(v_clean):
            raise ValueError(
                "Invalid GSTIN format. Expected 15 characters (e.g. 22AAAAA0000A1Z5)"
            )
        return v_clean

    @field_validator("pan", mode="before")
    @classmethod
    def validate_pan(cls, v: str | None) -> str | None:
        if v is None or not str(v).strip():
            return None
        v_clean = str(v).strip().upper()
        if v_clean.startswith("V1:") or v_clean.startswith("GAAAAA"):
            return v
        if not PAN_REGEX.match(v_clean):
            raise ValueError(
                "Invalid PAN format. Expected 10 alphanumeric characters (e.g. ABCDE1234F)"
            )
        return v_clean

    @field_validator("bank_ifsc", mode="before")
    @classmethod
    def validate_bank_ifsc(cls, v: str | None) -> str | None:
        if v is None or not str(v).strip():
            return None
        v_clean = str(v).strip().upper()
        if v_clean.startswith("V1:") or v_clean.startswith("GAAAAA"):
            return v
        if not IFSC_REGEX.match(v_clean):
            raise ValueError(
                "Invalid IFSC format. Expected 11 characters (e.g. SBIN0001234)"
            )
        return v_clean

    @field_validator("bank_account", mode="before")
    @classmethod
    def validate_bank_account(cls, v: str | None) -> str | None:
        if v is None or not str(v).strip():
            return None
        v_clean = str(v).strip()
        if v_clean.startswith("v1:") or v_clean.startswith("gAAAAA"):
            return v
        if not BANK_ACCOUNT_REGEX.match(v_clean):
            raise ValueError(
                "Invalid bank account number. Expected 9 to 18 numeric digits"
            )
        return v_clean

    @field_validator("upi_id", mode="before")
    @classmethod
    def validate_upi_id(cls, v: str | None) -> str | None:
        if v is None or not str(v).strip():
            return None
        v_clean = str(v).strip().lower()
        if v_clean.startswith("v1:") or v_clean.startswith("gaaaaa"):
            return v
        if not UPI_ID_REGEX.match(v_clean):
            raise ValueError("Invalid UPI ID format (e.g. username@okhdfcbank)")
        return v_clean


class CompanySettingsPublic(CompanySettingsBase):
    id: uuid.UUID
    owner_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    # Never expose secrets in responses.
    smtp_password: str | None = Field(default=None, exclude=True)
    openwa_api_key: str | None = Field(default=None, exclude=True)
    openwa_session_id: str | None = Field(default=None, exclude=True)

    # Expose only whether each credential is configured.
    smtp_password_set: bool = False
    openwa_api_key_set: bool = False
    openwa_session_id_set: bool = False

    @classmethod
    def from_model(cls, m) -> "CompanySettingsPublic":
        obj = cls.model_validate(m)
        obj.smtp_password_set = bool(getattr(m, "smtp_password", None))
        obj.openwa_api_key_set = bool(getattr(m, "openwa_api_key", None))
        obj.openwa_session_id_set = bool(getattr(m, "openwa_session_id", None))
        return obj
