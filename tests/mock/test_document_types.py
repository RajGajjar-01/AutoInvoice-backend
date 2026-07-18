import uuid
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from app.api import deps
from app.core.config import settings
from app.main import app
from app.models import Invoice
from app.schemas.invoice import DocumentType, InvoiceCreate
from app.services.invoice_pdf_service import InvoicePDFService


def _company():
    return SimpleNamespace(
        name="Acme Traders",
        address="42 Market Road",
        city="Pune",
        state="Maharashtra",
        pincode="411001",
        phone="9999999999",
        email="acme@example.com",
        gstin="27AAAAA0000A1Z5",
        bank_name=None,
        bank_account=None,
        bank_ifsc=None,
        bank_branch=None,
        upi_id=None,
        terms_and_conditions=None,
    )


def _customer():
    return SimpleNamespace(
        name="Bob Kumar",
        billing_address="1 Client Street",
        gstin=None,
        state="Gujarat",
        shipping_address=None,
        address=None,
    )


def _invoice(document_type, **overrides):
    data = {
        "owner_id": uuid.uuid4(),
        "customer_id": uuid.uuid4(),
        "invoice_number": f"{document_type.value[:3].upper()}-2607-1234",
        "invoice_date": date(2026, 7, 18),
        "document_type": document_type,
        "items": [
            {
                "name": "Widget",
                "description": "Blue widget",
                "quantity": 2,
                "unit": "pcs",
                "price": 100,
                "tax": 18,
            }
        ],
        "subtotal": 200.0,
        "total_tax": 36.0,
        "grand_total": 236.0,
    }
    data.update(overrides)
    return Invoice(**data)


class TestInvoicePdfDocumentTypes:
    def _render(self, invoice):
        return InvoicePDFService().render_html(invoice, _customer(), _company())

    def test_invoice_shows_pricing_and_title(self):
        html = self._render(_invoice(DocumentType.invoice))
        assert "<h2>Invoice</h2>" in html
        assert "Rate" in html and "Grand Total" in html
        # invoice_number must not be double-prefixed with a hardcoded INV-
        assert "INV-INV" not in html

    def test_quotation_shows_valid_until_and_pricing(self):
        html = self._render(
            _invoice(
                DocumentType.quotation,
                status="draft",
                valid_until=date(2026, 8, 18),
            )
        )
        assert "<h2>Quotation</h2>" in html
        assert "Valid Until: 2026-08-18" in html
        assert "Grand Total" in html and "Rate" in html
        assert "DRAFT" in html

    def test_challan_hides_pricing_and_shows_delivery(self):
        html = self._render(
            _invoice(
                DocumentType.challan,
                vehicle_info="MH-12 AB 1234",
                delivery_notes="Handle with care",
            )
        )
        assert "<h2>Delivery Challan</h2>" in html
        assert "Rate" not in html
        assert "Grand Total" not in html
        assert "Subtotal" not in html
        assert "MH-12 AB 1234" in html
        assert "Handle with care" in html

    def test_challan_number_not_prefixed_with_inv(self):
        html = self._render(
            _invoice(DocumentType.challan, invoice_number="CHL-2607-1234")
        )
        assert "CHL-2607-1234" in html
        assert "INV-CHL" not in html

    def test_proforma_title_and_pricing(self):
        html = self._render(_invoice(DocumentType.proforma))
        assert "<h2>Proforma Invoice</h2>" in html
        assert "Grand Total" in html

    def test_document_type_as_plain_string(self):
        # a persisted invoice may expose document_type as a plain string
        invoice = _invoice(DocumentType.challan)
        invoice.document_type = "challan"
        html = self._render(invoice)
        assert "<h2>Delivery Challan</h2>" in html
        assert "Rate" not in html


class TestDocumentTypeSchema:
    def test_challan_fields_accepted(self):
        model = InvoiceCreate(
            invoice_number="CHL-2607-1",
            customer_id=uuid.uuid4(),
            invoice_date=date(2026, 7, 18),
            document_type=DocumentType.challan,
            vehicle_info="MH-12 AB 1234",
            delivery_notes="Leave at gate",
            items=[{"name": "Box", "quantity": 3, "price": 0}],
        )
        assert model.document_type == DocumentType.challan
        assert model.vehicle_info == "MH-12 AB 1234"
        assert model.delivery_notes == "Leave at gate"

    def test_quotation_valid_until_and_draft_status(self):
        model = InvoiceCreate(
            invoice_number="QUO-2607-1",
            customer_id=uuid.uuid4(),
            invoice_date=date(2026, 7, 18),
            document_type=DocumentType.quotation,
            valid_until=date(2026, 8, 18),
            status="draft",
            items=[{"name": "Service", "quantity": 1, "price": 500}],
        )
        assert model.valid_until == date(2026, 8, 18)
        assert model.status.value == "draft"

    def test_defaults_when_not_a_challan(self):
        model = InvoiceCreate(
            invoice_number="INV-2607-1",
            customer_id=uuid.uuid4(),
            invoice_date=date(2026, 7, 18),
            items=[{"name": "Item", "quantity": 1, "price": 100}],
        )
        assert model.document_type == DocumentType.invoice
        assert model.vehicle_info is None
        assert model.delivery_notes is None


class TestDocumentTypeApi:
    def _override(self, mock_user, mock_svc):
        app.dependency_overrides[deps.get_current_user] = lambda: mock_user
        app.dependency_overrides[deps.get_invoice_service] = lambda: mock_svc

    def test_create_challan_persists_delivery_fields(
        self, client: TestClient, mock_user
    ):
        mock_svc = AsyncMock()
        mock_svc.create = AsyncMock(
            return_value=_invoice(DocumentType.challan, id=uuid.uuid4())
        )
        self._override(mock_user, mock_svc)

        r = client.post(
            f"{settings.API_V1_STR}/invoices/",
            json={
                "invoice_number": "CHL-2607-1",
                "customer_id": str(uuid.uuid4()),
                "invoice_date": "2026-07-18",
                "document_type": "challan",
                "vehicle_info": "MH-12 AB 1234",
                "delivery_notes": "Leave at gate",
                "items": [{"name": "Box", "quantity": 3, "price": 0}],
            },
        )
        assert r.status_code == 201
        invoice_in = mock_svc.create.call_args.args[0]
        assert invoice_in.document_type == DocumentType.challan
        assert invoice_in.vehicle_info == "MH-12 AB 1234"
        assert invoice_in.delivery_notes == "Leave at gate"

    def test_create_quotation_with_valid_until_and_draft(
        self, client: TestClient, mock_user
    ):
        mock_svc = AsyncMock()
        mock_svc.create = AsyncMock(
            return_value=_invoice(DocumentType.quotation, id=uuid.uuid4())
        )
        self._override(mock_user, mock_svc)

        r = client.post(
            f"{settings.API_V1_STR}/invoices/",
            json={
                "invoice_number": "QUO-2607-1",
                "customer_id": str(uuid.uuid4()),
                "invoice_date": "2026-07-18",
                "document_type": "quotation",
                "valid_until": "2026-08-18",
                "status": "draft",
                "items": [{"name": "Service", "quantity": 1, "price": 500}],
            },
        )
        assert r.status_code == 201
        invoice_in = mock_svc.create.call_args.args[0]
        assert invoice_in.document_type == DocumentType.quotation
        assert invoice_in.valid_until == date(2026, 8, 18)
        assert invoice_in.status.value == "draft"

    def test_create_proforma(self, client: TestClient, mock_user):
        mock_svc = AsyncMock()
        mock_svc.create = AsyncMock(
            return_value=_invoice(DocumentType.proforma, id=uuid.uuid4())
        )
        self._override(mock_user, mock_svc)

        r = client.post(
            f"{settings.API_V1_STR}/invoices/",
            json={
                "invoice_number": "PRO-2607-1",
                "customer_id": str(uuid.uuid4()),
                "invoice_date": "2026-07-18",
                "document_type": "proforma",
                "items": [{"name": "Item", "quantity": 1, "price": 100}],
            },
        )
        assert r.status_code == 201
        assert mock_svc.create.call_args.args[0].document_type == DocumentType.proforma

    def test_invalid_document_type_rejected(self, client: TestClient, mock_user):
        mock_svc = AsyncMock()
        self._override(mock_user, mock_svc)

        r = client.post(
            f"{settings.API_V1_STR}/invoices/",
            json={
                "invoice_number": "XXX-1",
                "customer_id": str(uuid.uuid4()),
                "invoice_date": "2026-07-18",
                "document_type": "bogus",
                "items": [{"name": "Item", "quantity": 1, "price": 100}],
            },
        )
        assert r.status_code == 422
