import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.security import decrypt_field
from app.schemas import InvoiceCreate, InvoiceUpdate
from app.services.invoice_service import InvoiceService, decrypt_bank_details
from app.services.invoice_totals import (
    compute_invoice_totals,
    compute_totals,
    line_amounts,
)

A = pytest.approx

# Expected values for cases without line discounts were produced by running the
# frontend computeInvoiceTotals (src/features/invoices/invoice-form/utils.ts).
TWO_LINES = [
    {"name": "A", "quantity": 2, "price": 500, "tax": 18},
    {"name": "B", "quantity": 1, "price": 300, "tax": 5},
]


class TestComputeTotals:
    def test_plain_items(self):
        t = compute_totals([{"quantity": 2, "price": 500, "tax": 18}])
        assert (t.subtotal, t.total_tax, t.grand_total) == (1000, 180, 1180)
        assert t.invoice_discount == 0 and t.items_discount == 0

    def test_invoice_percent_discount_matches_frontend(self):
        t = compute_totals(TWO_LINES, discount_type="percent", discount_value=10)
        assert t.invoice_discount == A(130)
        assert t.total_tax == A(175.5)
        assert t.grand_total == A(1345.5)

    def test_invoice_flat_discount_matches_frontend(self):
        t = compute_totals(TWO_LINES, discount_type="flat", discount_value=150)
        assert t.invoice_discount == A(150)
        assert t.total_tax == A(172.5)
        assert t.grand_total == A(1322.5)

    def test_flat_invoice_discount_is_capped(self):
        t = compute_totals(TWO_LINES, discount_type="flat", discount_value=99999)
        assert t.invoice_discount == A(1300)
        assert t.grand_total == A(0)

    def test_line_percent_discount_taxes_discounted_amount_once(self):
        # 3 x 199.99 = 599.97, 10% off = 539.973, 12% tax = 64.79676
        t = compute_totals(
            [{"quantity": 3, "price": 199.99, "tax": 12, "discount": 10}]
        )
        assert t.items_discount == A(59.997)
        assert t.total_tax == A(64.79676)
        assert t.grand_total == A(604.76976)

    def test_line_flat_discount_is_capped_at_line_base(self):
        line = line_amounts(
            {
                "quantity": 1,
                "price": 50,
                "tax": 5,
                "discount": 80,
                "discount_type": "flat",
            }
        )
        assert line.discount == 50 and line.total == 0

    def test_charges_and_round_off(self):
        t = compute_totals(
            [{"quantity": 7, "price": 33.33, "tax": 18, "discount": 5}],
            discount_type="flat",
            discount_value=20,
            shipping_charge=49.5,
            extra_charge_amount=10.25,
            round_off=True,
        )
        assert t.raw_grand_total == A(297.69051)
        assert t.grand_total == 298

    def test_charges_without_items(self):
        t = compute_totals(
            [], discount_type="percent", discount_value=10, shipping_charge=40
        )
        assert t.subtotal == 0 and t.total_tax == 0
        assert t.grand_total == 40

    def test_hide_pricing_returns_zeros(self):
        t = compute_totals(TWO_LINES, shipping_charge=50, hide_pricing=True)
        assert t.persisted() == {
            "subtotal": 0,
            "total_tax": 0,
            "discount": 0,
            "grand_total": 0,
        }

    def test_legacy_flat_discount_used_without_discount_type(self):
        t = compute_totals(TWO_LINES, legacy_discount=150)
        assert t.invoice_discount == A(150)

    def test_discount_type_overrides_legacy_discount(self):
        t = compute_totals(
            TWO_LINES, discount_type="percent", discount_value=0, legacy_discount=150
        )
        assert t.invoice_discount == 0

    def test_persisted_rounds_to_two_decimals(self):
        t = compute_totals(
            [{"quantity": 3, "price": 199.99, "tax": 12, "discount": 10}]
        )
        assert t.persisted()["grand_total"] == 604.77

    def test_accepts_objects_and_none_values(self):
        item = SimpleNamespace(quantity=2, price=10, tax=None, discount=None)
        assert compute_totals([item]).grand_total == 20

    def test_compute_invoice_totals_reads_saved_fields(self):
        invoice = SimpleNamespace(
            items=TWO_LINES,
            document_type=SimpleNamespace(value="invoice"),
            discount_type="flat",
            discount_value=150,
            discount=150,
            shipping_charge=10,
            extra_charge_amount=0,
            round_off=False,
        )
        assert compute_invoice_totals(invoice).grand_total == A(1332.5)

    def test_compute_invoice_totals_challan_is_zero(self):
        invoice = {"items": TWO_LINES, "document_type": "challan"}
        assert compute_invoice_totals(invoice).grand_total == 0


def _service():
    repo = MagicMock()
    repo.create = AsyncMock(side_effect=lambda data, owner_id: data)
    repo.update = AsyncMock(side_effect=lambda invoice, data: data)
    customer_repo = MagicMock()
    return InvoiceService(repo, customer_repo), repo, customer_repo


class TestInvoiceServiceTotals:
    @pytest.mark.anyio
    async def test_create_ignores_client_totals_and_encrypts_bank(self):
        svc, _, customer_repo = _service()
        owner = uuid.uuid4()
        customer_repo.get = AsyncMock(return_value=SimpleNamespace(owner_id=owner))
        payload = InvoiceCreate(
            invoice_number="INV-1",
            invoice_date="2026-11-07",
            customer_id=uuid.uuid4(),
            items=TWO_LINES,
            subtotal=1,
            total_tax=1,
            grand_total=1,
            discount_type="percent",
            discount_value=10,
            shipping_charge=20,
            bank_details={"bank_name": "HDFC", "account_number": "123456789012"},
        )
        data = await svc.create(payload, owner)

        assert data["subtotal"] == 1300
        assert data["discount"] == 130
        assert data["grand_total"] == 1365.5
        stored = data["bank_details"]
        assert stored["bank_name"] == "HDFC"
        assert stored["account_number"].startswith("v1:")
        assert decrypt_field(owner, stored["account_number"]) == "123456789012"
        assert decrypt_bank_details(owner, stored)["account_number"] == "123456789012"

    @pytest.mark.anyio
    async def test_create_drops_empty_bank_details(self):
        svc, _, customer_repo = _service()
        owner = uuid.uuid4()
        customer_repo.get = AsyncMock(return_value=SimpleNamespace(owner_id=owner))
        payload = InvoiceCreate(
            invoice_number="INV-1",
            invoice_date="2026-11-07",
            customer_id=uuid.uuid4(),
            bank_details={"bank_name": ""},
        )
        data = await svc.create(payload, owner)
        assert data["bank_details"] is None

    @pytest.mark.anyio
    async def test_update_recomputes_when_only_a_charge_changes(self):
        svc, _, _ = _service()
        owner = uuid.uuid4()
        invoice = SimpleNamespace(
            owner_id=owner,
            items=TWO_LINES,
            document_type="invoice",
            discount=0,
            discount_type="percent",
            discount_value=0,
            shipping_charge=0,
            extra_charge_amount=0,
            round_off=False,
        )
        svc.get_owned = AsyncMock(return_value=invoice)
        data = await svc.update(
            uuid.uuid4(), owner, InvoiceUpdate(shipping_charge=100, grand_total=5)
        )
        assert data["shipping_charge"] == 100
        assert data["grand_total"] == 1300 + 195 + 100  # tax 180 + 15

    @pytest.mark.anyio
    async def test_update_without_pricing_fields_keeps_totals(self):
        svc, _, _ = _service()
        invoice = SimpleNamespace(owner_id=uuid.uuid4())
        svc.get_owned = AsyncMock(return_value=invoice)
        data = await svc.update(
            uuid.uuid4(), invoice.owner_id, InvoiceUpdate(notes="hello", grand_total=5)
        )
        assert "grand_total" not in data
        assert data["notes"] == "hello"
