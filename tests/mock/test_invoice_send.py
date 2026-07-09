import base64
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api import deps
from app.core.config import settings
from app.main import app


def _invoice(overrides=None):
    m = MagicMock()
    m.id = uuid.uuid4()
    m.owner_id = uuid.uuid4()
    m.customer_id = uuid.uuid4()
    m.invoice_number = "INV-001"
    m.document_type = "invoice"
    m.invoice_date = "2024-01-15"
    m.due_date = "2024-02-15"
    m.currency = "INR"
    m.subtotal = 1000.0
    m.total_tax = 180.0
    m.grand_total = 1180.0
    m.discount = 0.0
    m.status = "unpaid"
    m.items = [{"name": "Item A", "quantity": 2, "price": 500, "tax": 18}]
    m.notes = None
    if overrides:
        for k, v in overrides.items():
            setattr(m, k, v)
    return m


def _customer(overrides=None):
    c = MagicMock()
    c.id = uuid.uuid4()
    c.owner_id = uuid.uuid4()
    c.name = "Test Customer"
    c.email = "customer@test.com"
    c.phone = "9876543210"
    c.whatsapp = "9876543210"
    c.billing_address = "123 Test St"
    c.gstin = None
    c.state = "Test State"
    if overrides:
        for k, v in overrides.items():
            setattr(c, k, v)
    return c


def _company(overrides=None):
    co = MagicMock()
    co.id = uuid.uuid4()
    co.owner_id = uuid.uuid4()
    co.name = "Test Company"
    co.address = "456 Company St"
    co.city = "Test City"
    co.state = "Test State"
    co.pincode = "123456"
    co.phone = "1234567890"
    co.email = "company@test.com"
    co.gstin = "GST123"
    co.bank_name = "Test Bank"
    co.bank_account = "123456789"
    co.bank_ifsc = "TEST0001234"
    co.upi_id = "company@upi"
    co.terms_and_conditions = "Standard terms apply"
    co.whatsapp_enabled = False
    co.openwa_base_url = "http://localhost:2785"
    co.openwa_api_key = None
    co.openwa_session_id = None
    co.smtp_host = None
    co.smtp_port = 587
    co.smtp_user = None
    co.smtp_password = None
    co.smtp_tls = True
    co.emails_from_email = None
    co.emails_from_name = None
    if overrides:
        for k, v in overrides.items():
            setattr(co, k, v)
    return co


def _mock_user_service(access_token="fake-google-access-token", side_effect=None):
    return AsyncMock(
        get_valid_google_access_token=AsyncMock(
            return_value=access_token, side_effect=side_effect
        )
    )


def _setup_deps(mock_user, **overrides):
    app.dependency_overrides[deps.get_current_user] = lambda: mock_user
    if "invoice_service" in overrides:
        app.dependency_overrides[deps.get_invoice_service] = lambda: overrides["invoice_service"]
    if "pdf_service" in overrides:
        app.dependency_overrides[deps.get_invoice_pdf_service] = lambda: overrides["pdf_service"]
    if "company_service" in overrides:
        app.dependency_overrides[deps.get_company_settings_service] = lambda: overrides["company_service"]
    if "whatsapp_service" in overrides:
        app.dependency_overrides[deps.get_whatsapp_service] = lambda: overrides["whatsapp_service"]
    if "user_service" in overrides:
        app.dependency_overrides[deps.get_user_service] = lambda: overrides["user_service"]


def _mock_invoice_svc(get_with_customer_return=None, get_with_customer_side_effect=None):
    svc = AsyncMock()
    svc.get_with_customer = AsyncMock(
        return_value=get_with_customer_return,
        side_effect=get_with_customer_side_effect,
    )
    return svc


class TestSendEmail:
    def test_send_email_success(self, client: TestClient, mock_user):
        inv = _invoice()
        inv.customer = _customer()
        company = _company()
        mock_user.google_email = "user@gmail.com"

        _setup_deps(
            mock_user,
            invoice_service=_mock_invoice_svc(get_with_customer_return=inv),
            pdf_service=MagicMock(generate=MagicMock(return_value=b"%PDF-1.4 fake")),
            company_service=AsyncMock(get_for_owner=AsyncMock(return_value=company)),
            user_service=_mock_user_service(),
        )

        with patch("app.api.routes.invoices.send_gmail_email") as mock_send:
            r = client.post(
                f"{settings.API_V1_STR}/invoices/{inv.id}/send-email",
                json={"to_email": "customer@test.com", "subject": "Your Invoice"},
            )

        assert r.status_code == 200
        assert r.json() == {"message": "Email sent successfully"}
        mock_send.assert_called_once()
        _, kwargs = mock_send.call_args
        assert kwargs["access_token"] == "fake-google-access-token"
        assert kwargs["from_email"] == "user@gmail.com"
        assert kwargs["to_email"] == "customer@test.com"
        assert kwargs["subject"] == "Your Invoice"
        assert kwargs["attachment"] == (
            "invoice_INV-001.pdf",
            b"%PDF-1.4 fake",
            "application/pdf",
        )

    def test_send_email_default_subject(self, client: TestClient, mock_user):
        inv = _invoice()
        inv.customer = _customer()
        company = _company()
        mock_user.google_email = "user@gmail.com"

        _setup_deps(
            mock_user,
            invoice_service=_mock_invoice_svc(get_with_customer_return=inv),
            pdf_service=MagicMock(generate=MagicMock(return_value=b"pdf")),
            company_service=AsyncMock(get_for_owner=AsyncMock(return_value=company)),
            user_service=_mock_user_service(),
        )

        with patch("app.api.routes.invoices.send_gmail_email") as mock_send:
            r = client.post(
                f"{settings.API_V1_STR}/invoices/{inv.id}/send-email",
                json={"to_email": "customer@test.com"},
            )

        assert r.status_code == 200
        _, kwargs = mock_send.call_args
        assert kwargs["subject"] == f"Invoice INV-001 from {company.name}"

    def test_send_email_google_not_connected(self, client: TestClient, mock_user):
        from app.exceptions import ValidationError

        inv = _invoice()
        inv.customer = _customer()

        _setup_deps(
            mock_user,
            invoice_service=_mock_invoice_svc(get_with_customer_return=inv),
            user_service=_mock_user_service(
                side_effect=ValidationError(
                    "Connect your Google account in Settings to send invoice emails"
                )
            ),
        )

        r = client.post(
            f"{settings.API_V1_STR}/invoices/{inv.id}/send-email",
            json={"to_email": "customer@test.com"},
        )
        assert r.status_code == 422
        assert "Google" in r.text

    def test_send_email_invalid_email_422(self, client: TestClient, mock_user):
        inv = _invoice()
        inv.customer = _customer()
        _setup_deps(mock_user, invoice_service=_mock_invoice_svc(get_with_customer_return=inv))

        r = client.post(
            f"{settings.API_V1_STR}/invoices/{inv.id}/send-email",
            json={"to_email": "not-an-email"},
        )
        assert r.status_code == 422

    def test_send_email_missing_to_email_422(self, client: TestClient, mock_user):
        inv = _invoice()
        inv.customer = _customer()
        _setup_deps(mock_user, invoice_service=_mock_invoice_svc(get_with_customer_return=inv))

        r = client.post(
            f"{settings.API_V1_STR}/invoices/{inv.id}/send-email",
            json={},
        )
        assert r.status_code == 422

    def test_send_email_no_customer(self, client: TestClient, mock_user):
        inv = _invoice()
        inv.customer = None
        _setup_deps(mock_user, invoice_service=_mock_invoice_svc(get_with_customer_return=inv))

        r = client.post(
            f"{settings.API_V1_STR}/invoices/{inv.id}/send-email",
            json={"to_email": "customer@test.com"},
        )
        assert r.status_code == 404
        assert "Customer" in r.text

    def test_send_email_no_company(self, client: TestClient, mock_user):
        from app.exceptions import NotFoundError

        inv = _invoice()
        inv.customer = _customer()

        _setup_deps(
            mock_user,
            invoice_service=_mock_invoice_svc(get_with_customer_return=inv),
            company_service=AsyncMock(
                get_for_owner=AsyncMock(side_effect=NotFoundError("Company settings not found"))
            ),
            user_service=_mock_user_service(),
        )

        r = client.post(
            f"{settings.API_V1_STR}/invoices/{inv.id}/send-email",
            json={"to_email": "customer@test.com"},
        )
        assert r.status_code == 404

    def test_send_email_invoice_not_found(self, client: TestClient, mock_user):
        from app.exceptions import NotFoundError

        _setup_deps(
            mock_user,
            invoice_service=_mock_invoice_svc(get_with_customer_side_effect=NotFoundError("Invoice not found")),
        )

        r = client.post(
            f"{settings.API_V1_STR}/invoices/{uuid.uuid4()}/send-email",
            json={"to_email": "customer@test.com"},
        )
        assert r.status_code == 404

    def test_send_email_unauthorized(self, client: TestClient):
        r = client.post(
            f"{settings.API_V1_STR}/invoices/{uuid.uuid4()}/send-email",
            json={"to_email": "customer@test.com"},
        )
        assert r.status_code == 401


class TestSendWhatsApp:
    def test_send_whatsapp_success(self, client: TestClient, mock_user):
        inv = _invoice()
        inv.customer = _customer()
        company = _company()

        _setup_deps(
            mock_user,
            invoice_service=_mock_invoice_svc(get_with_customer_return=inv),
            pdf_service=MagicMock(generate=MagicMock(return_value=b"pdf-data")),
            company_service=AsyncMock(get_for_owner=AsyncMock(return_value=company)),
            whatsapp_service=MagicMock(
                send_document=MagicMock(return_value={"messageId": "wa_msg_123"})
            ),
        )

        r = client.post(
            f"{settings.API_V1_STR}/invoices/{inv.id}/send-whatsapp",
            json={"to_phone": "9876543210"},
        )

        assert r.status_code == 200
        assert r.json() == {"message": "WhatsApp message sent", "message_id": "wa_msg_123"}

    def test_send_whatsapp_strips_plus_prefix(self, client: TestClient, mock_user):
        inv = _invoice()
        inv.customer = _customer()
        company = _company()
        wa_mock = MagicMock(send_document=MagicMock(return_value={"messageId": "x"}))

        _setup_deps(
            mock_user,
            invoice_service=_mock_invoice_svc(get_with_customer_return=inv),
            pdf_service=MagicMock(generate=MagicMock(return_value=b"pdf")),
            company_service=AsyncMock(get_for_owner=AsyncMock(return_value=company)),
            whatsapp_service=wa_mock,
        )

        client.post(
            f"{settings.API_V1_STR}/invoices/{inv.id}/send-whatsapp",
            json={"to_phone": "+919876543210"},
        )

        _, kwargs = wa_mock.send_document.call_args
        assert kwargs["chat_id"] == "919876543210@c.us"

    def test_send_whatsapp_caption_contains_amount(self, client: TestClient, mock_user):
        inv = _invoice()
        inv.customer = _customer()
        company = _company()
        wa_mock = MagicMock(send_document=MagicMock(return_value={"messageId": "x"}))

        _setup_deps(
            mock_user,
            invoice_service=_mock_invoice_svc(get_with_customer_return=inv),
            pdf_service=MagicMock(generate=MagicMock(return_value=b"pdf")),
            company_service=AsyncMock(get_for_owner=AsyncMock(return_value=company)),
            whatsapp_service=wa_mock,
        )

        client.post(
            f"{settings.API_V1_STR}/invoices/{inv.id}/send-whatsapp",
            json={"to_phone": "9876543210"},
        )

        _, kwargs = wa_mock.send_document.call_args
        assert "INV-001" in kwargs["caption"]
        assert "1,180.00" in kwargs["caption"]

    def test_send_whatsapp_missing_phone_422(self, client: TestClient, mock_user):
        inv = _invoice()
        inv.customer = _customer()
        _setup_deps(mock_user, invoice_service=_mock_invoice_svc(get_with_customer_return=inv))

        r = client.post(
            f"{settings.API_V1_STR}/invoices/{inv.id}/send-whatsapp",
            json={},
        )
        assert r.status_code == 422

    def test_send_whatsapp_no_customer(self, client: TestClient, mock_user):
        inv = _invoice()
        inv.customer = None
        _setup_deps(mock_user, invoice_service=_mock_invoice_svc(get_with_customer_return=inv))

        r = client.post(
            f"{settings.API_V1_STR}/invoices/{inv.id}/send-whatsapp",
            json={"to_phone": "9876543210"},
        )
        assert r.status_code == 404

    def test_send_whatsapp_no_company(self, client: TestClient, mock_user):
        from app.exceptions import NotFoundError

        inv = _invoice()
        inv.customer = _customer()

        _setup_deps(
            mock_user,
            invoice_service=_mock_invoice_svc(get_with_customer_return=inv),
            company_service=AsyncMock(
                get_for_owner=AsyncMock(side_effect=NotFoundError("Company settings not found"))
            ),
        )

        r = client.post(
            f"{settings.API_V1_STR}/invoices/{inv.id}/send-whatsapp",
            json={"to_phone": "9876543210"},
        )
        assert r.status_code == 404

    def test_send_whatsapp_invoice_not_found(self, client: TestClient, mock_user):
        from app.exceptions import NotFoundError

        _setup_deps(
            mock_user,
            invoice_service=_mock_invoice_svc(get_with_customer_side_effect=NotFoundError("Invoice not found")),
        )

        r = client.post(
            f"{settings.API_V1_STR}/invoices/{uuid.uuid4()}/send-whatsapp",
            json={"to_phone": "9876543210"},
        )
        assert r.status_code == 404

    def test_send_whatsapp_unauthorized(self, client: TestClient):
        r = client.post(
            f"{settings.API_V1_STR}/invoices/{uuid.uuid4()}/send-whatsapp",
            json={"to_phone": "9876543210"},
        )
        assert r.status_code == 401


class TestSendReminder:
    def test_send_reminder_with_overdue(self, client: TestClient, mock_user):
        inv = _invoice()
        inv.customer = _customer()
        company = _company()
        wa_mock = MagicMock(send_document=MagicMock(return_value={"messageId": "rem_123"}))

        _setup_deps(
            mock_user,
            invoice_service=_mock_invoice_svc(get_with_customer_return=inv),
            pdf_service=MagicMock(generate=MagicMock(return_value=b"pdf")),
            company_service=AsyncMock(get_for_owner=AsyncMock(return_value=company)),
            whatsapp_service=wa_mock,
        )

        r = client.post(
            f"{settings.API_V1_STR}/invoices/{inv.id}/send-reminder",
            json={"to_phone": "9876543210", "days_overdue": 5},
        )

        assert r.status_code == 200
        assert r.json()["message"] == "Reminder sent"
        _, kwargs = wa_mock.send_document.call_args
        assert "5 days overdue" in kwargs["caption"]
        assert kwargs["chat_id"] == "9876543210@c.us"

    def test_send_reminder_without_overdue(self, client: TestClient, mock_user):
        inv = _invoice()
        inv.customer = _customer()
        company = _company()
        wa_mock = MagicMock(send_document=MagicMock(return_value={"messageId": "rem_456"}))

        _setup_deps(
            mock_user,
            invoice_service=_mock_invoice_svc(get_with_customer_return=inv),
            pdf_service=MagicMock(generate=MagicMock(return_value=b"pdf")),
            company_service=AsyncMock(get_for_owner=AsyncMock(return_value=company)),
            whatsapp_service=wa_mock,
        )

        r = client.post(
            f"{settings.API_V1_STR}/invoices/{inv.id}/send-reminder",
            json={"to_phone": "9876543210"},
        )

        assert r.status_code == 200
        _, kwargs = wa_mock.send_document.call_args
        assert "overdue" not in kwargs["caption"]

    def test_send_reminder_no_customer(self, client: TestClient, mock_user):
        inv = _invoice()
        inv.customer = None
        _setup_deps(mock_user, invoice_service=_mock_invoice_svc(get_with_customer_return=inv))

        r = client.post(
            f"{settings.API_V1_STR}/invoices/{inv.id}/send-reminder",
            json={"to_phone": "9876543210"},
        )
        assert r.status_code == 404

    def test_send_reminder_no_company(self, client: TestClient, mock_user):
        from app.exceptions import NotFoundError

        inv = _invoice()
        inv.customer = _customer()

        _setup_deps(
            mock_user,
            invoice_service=_mock_invoice_svc(get_with_customer_return=inv),
            company_service=AsyncMock(
                get_for_owner=AsyncMock(side_effect=NotFoundError("Company settings not found"))
            ),
        )

        r = client.post(
            f"{settings.API_V1_STR}/invoices/{inv.id}/send-reminder",
            json={"to_phone": "9876543210"},
        )
        assert r.status_code == 404

    def test_send_reminder_invoice_not_found(self, client: TestClient, mock_user):
        from app.exceptions import NotFoundError

        _setup_deps(
            mock_user,
            invoice_service=_mock_invoice_svc(get_with_customer_side_effect=NotFoundError("Invoice not found")),
        )

        r = client.post(
            f"{settings.API_V1_STR}/invoices/{uuid.uuid4()}/send-reminder",
            json={"to_phone": "9876543210"},
        )
        assert r.status_code == 404

    def test_send_reminder_missing_phone_422(self, client: TestClient, mock_user):
        inv = _invoice()
        inv.customer = _customer()
        _setup_deps(mock_user, invoice_service=_mock_invoice_svc(get_with_customer_return=inv))

        r = client.post(
            f"{settings.API_V1_STR}/invoices/{inv.id}/send-reminder",
            json={},
        )
        assert r.status_code == 422

    def test_send_reminder_unauthorized(self, client: TestClient):
        r = client.post(
            f"{settings.API_V1_STR}/invoices/{uuid.uuid4()}/send-reminder",
            json={"to_phone": "9876543210"},
        )
        assert r.status_code == 401


class TestSendEmailServiceAttachment:
    @patch("app.services.email_service.settings")
    @patch("app.services.email_service.httpx.post")
    def test_send_email_with_attachment(self, mock_post, mock_settings):
        mock_settings.emails_enabled = True
        mock_settings.EMAILS_FROM_NAME = "Test"
        mock_settings.EMAILS_FROM_EMAIL = "test@test.com"
        mock_settings.BREVO_API_KEY = "fake-brevo-key"

        mock_response = MagicMock()
        mock_response.json.return_value = {"messageId": "abc123"}
        mock_post.return_value = mock_response

        from app.services.email_service import send_email

        send_email(
            email_to="x@y.com",
            subject="Test",
            html_content="<p>Hi</p>",
            attachment=("invoice.pdf", b"pdf-data", "application/pdf"),
        )

        mock_post.assert_called_once()
        _, kwargs = mock_post.call_args
        assert kwargs["headers"]["api-key"] == "fake-brevo-key"
        assert kwargs["json"]["to"] == [{"email": "x@y.com"}]
        assert kwargs["json"]["attachment"] == [
            {"name": "invoice.pdf", "content": base64.b64encode(b"pdf-data").decode("ascii")}
        ]
        mock_response.raise_for_status.assert_called_once()

    @patch("app.services.email_service.settings")
    @patch("app.services.email_service.httpx.post")
    def test_send_email_without_attachment(self, mock_post, mock_settings):
        mock_settings.emails_enabled = True
        mock_settings.EMAILS_FROM_NAME = "Test"
        mock_settings.EMAILS_FROM_EMAIL = "test@test.com"
        mock_settings.BREVO_API_KEY = "fake-brevo-key"

        mock_response = MagicMock()
        mock_response.json.return_value = {"messageId": "abc123"}
        mock_post.return_value = mock_response

        from app.services.email_service import send_email

        send_email(
            email_to="x@y.com",
            subject="No Attach",
            html_content="<p>No file</p>",
        )

        mock_post.assert_called_once()
        _, kwargs = mock_post.call_args
        assert "attachment" not in kwargs["json"]
        mock_response.raise_for_status.assert_called_once()
