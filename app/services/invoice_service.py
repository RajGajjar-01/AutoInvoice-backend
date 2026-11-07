import uuid
from typing import Any

from app.core.security import decrypt_field, encrypt_field
from app.core.time import get_datetime_utc
from app.exceptions import ForbiddenError, NotFoundError
from app.models import Invoice
from app.repositories.base import get_owned
from app.repositories.customer_repository import CustomerRepository
from app.repositories.invoice_repository import InvoiceRepository
from app.schemas import InvoiceCreate, InvoiceUpdate

from .invoice_totals import compute_invoice_totals

# Fields that change the money math. An update that touches any of them makes
# the service compute the totals again.
_PRICING_FIELDS = frozenset(
    {
        "items",
        "document_type",
        "discount",
        "discount_type",
        "discount_value",
        "shipping_charge",
        "extra_charge_amount",
        "round_off",
    }
)
# Client-sent totals are never trusted; they are always recomputed.
_COMPUTED_FIELDS = ("subtotal", "total_tax", "grand_total")
_ENCRYPTED_BANK_FIELDS = ("account_number", "ifsc", "upi")


def _dump_items(items: list[Any]) -> list[dict[str, Any]]:
    return [i.model_dump() if hasattr(i, "model_dump") else i for i in items]


def _encrypt_bank_details(
    owner_id: uuid.UUID, details: dict[str, Any] | None
) -> dict[str, Any] | None:
    if not details or not any(details.values()):
        return None
    out = dict(details)
    for key in _ENCRYPTED_BANK_FIELDS:
        if out.get(key):
            out[key] = encrypt_field(owner_id, str(out[key]))
    return out


def decrypt_bank_details(
    owner_id: uuid.UUID, details: dict[str, Any] | None
) -> dict[str, Any] | None:
    if not details:
        return None
    out = dict(details)
    for key in _ENCRYPTED_BANK_FIELDS:
        if out.get(key):
            out[key] = decrypt_field(owner_id, out[key])
    return out


class InvoiceService:
    def __init__(
        self, repo: InvoiceRepository, customer_repo: CustomerRepository
    ) -> None:
        self.repo = repo
        self.customer_repo = customer_repo

    async def get_owned(self, invoice_id: uuid.UUID, owner_id: uuid.UUID) -> Invoice:
        return await get_owned(self.repo, invoice_id, owner_id, "Invoice not found")

    async def get_with_customer(
        self, invoice_id: uuid.UUID, owner_id: uuid.UUID
    ) -> Invoice:
        invoice = await self.repo.get_with_customer(invoice_id, owner_id)
        if not invoice:
            raise NotFoundError("Invoice not found")
        if invoice.owner_id != owner_id:
            raise ForbiddenError("Not enough permissions")
        return invoice

    async def list_items(
        self,
        owner_id: uuid.UUID,
        *,
        skip: int,
        limit: int,
        status: str | None,
        document_type: str | None,
        customer_id: uuid.UUID | None,
    ) -> tuple[list[Invoice], int]:
        return await self.repo.list_filtered(
            owner_id,
            status=status,
            document_type=document_type,
            customer_id=customer_id,
            skip=skip,
            limit=limit,
        )

    async def get_dashboard_stats(
        self, owner_id: uuid.UUID, document_type: str | None
    ) -> dict[str, Any]:
        return await self.repo.get_dashboard_stats(owner_id, document_type)

    async def create(self, invoice_in: InvoiceCreate, owner_id: uuid.UUID) -> Invoice:
        customer = await self.customer_repo.get(invoice_in.customer_id)
        if not customer:
            raise NotFoundError("Customer not found")
        if customer.owner_id != owner_id:
            raise ForbiddenError("Not enough permissions")

        invoice_data = invoice_in.model_dump()
        invoice_data["items"] = _dump_items(invoice_in.items)
        invoice_data["bank_details"] = _encrypt_bank_details(
            owner_id, invoice_data.get("bank_details")
        )
        for key in _COMPUTED_FIELDS:
            invoice_data.pop(key, None)
        invoice_data.update(compute_invoice_totals(invoice_data).persisted())

        return await self.repo.create(invoice_data, owner_id)

    async def update(
        self, invoice_id: uuid.UUID, owner_id: uuid.UUID, invoice_in: InvoiceUpdate
    ) -> Invoice:
        invoice = await self.get_owned(invoice_id, owner_id)
        update_data = invoice_in.model_dump(exclude_unset=True)
        for key in _COMPUTED_FIELDS:
            update_data.pop(key, None)

        if update_data.get("items") is not None:
            update_data["items"] = _dump_items(update_data["items"])
        elif "items" in update_data:
            del update_data["items"]

        if "bank_details" in update_data:
            update_data["bank_details"] = _encrypt_bank_details(
                owner_id, update_data["bank_details"]
            )

        if _PRICING_FIELDS & update_data.keys():
            merged = {
                key: getattr(invoice, key, None)
                for key in _PRICING_FIELDS
                if key not in update_data
            }
            merged.update(update_data)
            if "discount_type" in update_data or "discount_value" in update_data:
                # A new discount setting replaces any legacy flat amount.
                merged.pop("discount", None)
            update_data.update(compute_invoice_totals(merged).persisted())

        update_data["updated_at"] = get_datetime_utc()
        return await self.repo.update(invoice, update_data)

    async def delete(self, invoice_id: uuid.UUID, owner_id: uuid.UUID) -> None:
        invoice = await self.get_owned(invoice_id, owner_id)
        await self.repo.delete(invoice)
