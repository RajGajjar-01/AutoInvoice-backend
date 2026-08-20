import base64
from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.services.invoice_pdf_service import _format_currency


class TestFormatCurrency:
    def test_inr(self):
        assert "\u20b9" in _format_currency(1000.50)
        assert "1,000.50" in _format_currency(1000.50)

    def test_usd(self):
        result = _format_currency(99.99, "USD")
        assert "$" in result
        assert "99.99" in result

    def test_eur(self):
        result = _format_currency(50, "EUR")
        assert "\u20ac" in result
        assert "50.00" in result

    def test_zero(self):
        result = _format_currency(0)
        assert "0.00" in result

    def test_unknown_currency(self):
        result = _format_currency(100, "JPY")
        assert "JPY" in result


class TestWhatsAppService:
    @patch("app.services.whatsapp_service.settings")
    @patch("app.services.whatsapp_service.httpx.post")
    def test_send_text(self, mock_post, mock_settings):
        mock_settings.OPENWA_BASE_URL = "http://wa:2785"
        mock_settings.OPENWA_API_KEY = "test-key"
        mock_settings.OPENWA_SESSION_ID = "sess_123"

        mock_post.return_value = MagicMock(
            status_code=201,
            json=lambda: {"messageId": "msg_1", "timestamp": 1719312000},
            raise_for_status=lambda: None,
        )

        from app.services.whatsapp_service import WhatsAppService

        svc = WhatsAppService()
        result = svc.send_text("919876@c.us", "Hello")

        assert result["messageId"] == "msg_1"
        mock_post.assert_called_once_with(
            "http://wa:2785/api/sessions/sess_123/messages/send-text",
            headers={
                "X-API-Key": "test-key",
                "Content-Type": "application/json",
            },
            json={"chatId": "919876@c.us", "text": "Hello"},
            timeout=30,
        )

    @patch("app.services.whatsapp_service.settings")
    @patch("app.services.whatsapp_service.httpx.post")
    def test_send_document_with_caption(self, mock_post, mock_settings):
        mock_settings.OPENWA_BASE_URL = "http://wa:2785"
        mock_settings.OPENWA_API_KEY = "test-key"
        mock_settings.OPENWA_SESSION_ID = "sess_123"

        mock_post.return_value = MagicMock(
            status_code=201,
            json=lambda: {"messageId": "doc_1", "timestamp": 1719312001},
            raise_for_status=lambda: None,
        )

        from app.services.whatsapp_service import WhatsAppService

        svc = WhatsAppService()
        pdf_bytes = b"%PDF-1.4 test"
        result = svc.send_document(
            "919876@c.us",
            pdf_bytes,
            filename="invoice.pdf",
            caption="Your invoice",
        )

        assert result["messageId"] == "doc_1"
        call_kwargs = mock_post.call_args
        assert call_kwargs[1]["json"]["chatId"] == "919876@c.us"
        assert call_kwargs[1]["json"]["filename"] == "invoice.pdf"
        assert call_kwargs[1]["json"]["caption"] == "Your invoice"
        assert call_kwargs[1]["json"]["mimetype"] == "application/pdf"
        assert call_kwargs[1]["json"]["base64"] == base64.b64encode(pdf_bytes).decode(
            "ascii"
        )

    @patch("app.services.whatsapp_service.settings")
    @patch("app.services.whatsapp_service.httpx.post")
    def test_send_document_no_caption(self, mock_post, mock_settings):
        mock_settings.OPENWA_BASE_URL = "http://wa:2785"
        mock_settings.OPENWA_API_KEY = "test-key"
        mock_settings.OPENWA_SESSION_ID = "sess_123"

        mock_post.return_value = MagicMock(
            status_code=201,
            json=lambda: {"messageId": "doc_2"},
            raise_for_status=lambda: None,
        )

        from app.services.whatsapp_service import WhatsAppService

        svc = WhatsAppService()
        result = svc.send_document("919876@c.us", b"pdf")

        assert result["messageId"] == "doc_2"
        call_kwargs = mock_post.call_args
        assert "caption" not in call_kwargs[1]["json"]

    @patch("app.services.whatsapp_service.settings")
    @patch("app.services.whatsapp_service.httpx.post")
    def test_send_document_http_error(self, mock_post, mock_settings):
        mock_settings.OPENWA_BASE_URL = "http://wa:2785"
        mock_settings.OPENWA_API_KEY = "test-key"
        mock_settings.OPENWA_SESSION_ID = "sess_123"

        resp = MagicMock(status_code=400)
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Bad Request", request=MagicMock(), response=resp
        )
        mock_post.return_value = resp

        from app.services.whatsapp_service import WhatsAppService

        svc = WhatsAppService()
        with pytest.raises(httpx.HTTPStatusError):
            svc.send_document("919876@c.us", b"pdf")


class TestInvoicePDFService:
    def test_generate_base64(self):
        from app.services.invoice_pdf_service import InvoicePDFService

        svc = InvoicePDFService()
        with patch.object(svc, "generate", return_value=b"pdf-bytes"):
            result = svc.generate_base64(MagicMock(), MagicMock(), MagicMock())
            assert result == base64.b64encode(b"pdf-bytes").decode("ascii")
