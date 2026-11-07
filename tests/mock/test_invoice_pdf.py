import socket
import uuid
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api import deps
from app.core.config import settings
from app.exceptions import NotFoundError
from app.main import app
from app.services.invoice_pdf_service import (
    BUILT_IN_TEMPLATES,
    InvoicePDFService,
    build_context,
    resolve_template_id,
)
from app.services.safe_url_fetcher import (
    SafeURLFetcher,
    UnsafeURLError,
    ensure_public_https_url,
)


def _invoice(**overrides):
    data = {
        "id": uuid.uuid4(),
        "owner_id": uuid.uuid4(),
        "document_type": "invoice",
        "invoice_number": "INV-2611-0001",
        "invoice_date": date(2026, 11, 7),
        "due_date": date(2026, 12, 7),
        "valid_until": None,
        "currency": "INR",
        "items": [
            {"name": "Design", "quantity": 2, "price": 500, "tax": 18, "unit": "hrs"},
            {"name": "Hosting", "quantity": 1, "price": 300, "tax": 5},
        ],
        "discount": 0,
        "discount_type": "percent",
        "discount_value": 10,
        "shipping_charge": 50,
        "extra_charge_label": "Packing",
        "extra_charge_amount": 20,
        "round_off": True,
        "po_number": "PO-42",
        "place_of_supply": "Gujarat (24)",
        "reverse_charge": False,
        "vehicle_info": None,
        "delivery_notes": None,
        "notes": "Thanks!",
        "payment_terms": "Net 15",
        "status": "unpaid",
        "bank_details": None,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def _customer(**overrides):
    data = {
        "name": "Acme Pvt Ltd",
        "billing_address": "12 MG Road",
        "address": None,
        "gstin": "24AAAAA0000A1Z5",
        "gst": None,
        "phone": "9876543210",
        "email": "ap@acme.example",
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def _company(**overrides):
    data = {
        "name": "Raj Studio",
        "address": "45 CG Road",
        "city": "Ahmedabad",
        "state": "Gujarat",
        "pincode": "380009",
        "phone": "9000000000",
        "email": "hi@raj.example",
        "gstin": "24BBBBB1111B1Z5",
        "logo_url": None,
        "bank_name": "HDFC Bank",
        "bank_account": "50100012345678",
        "bank_ifsc": "HDFC0001234",
        "bank_branch": "CG Road",
        "upi_id": "raj@okhdfcbank",
        "terms_and_conditions": None,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


class TestResolveTemplate:
    def test_requested_built_in_wins(self):
        assert resolve_template_id("geometric", "built_in", "aizen-bold") == "geometric"

    def test_unknown_request_falls_back_to_active(self):
        assert resolve_template_id("nope", "built_in", "aizen-bold") == "aizen-bold"

    def test_active_built_in_with_unknown_id(self):
        assert resolve_template_id(None, "built_in", "removed") == "clean-teal"

    @pytest.mark.parametrize("kind", ["custom", "imported_html", "imported_pdf"])
    def test_custom_and_imported_kinds_use_default(self, kind):
        assert resolve_template_id(None, kind, None) == "default"

    def test_no_active_template(self):
        assert resolve_template_id(None) == "clean-teal"


class TestBuildContext:
    def test_summary_lists_every_charge(self):
        ctx = build_context(_invoice(), _customer(), _company())
        labels = [e.label for e in ctx["summary"]]
        assert labels == [
            "Subtotal",
            "Discount",
            "Tax",
            "Shipping",
            "Packing",
            "Round Off",
        ]
        # 1300 - 10% = 1170; tax 195 * 0.9 = 175.5; + 50 + 20 = 1415.5 -> 1416
        assert ctx["grand_total"] == "1416.00"

    def test_row_totals_include_line_discount_and_tax(self):
        inv = _invoice(
            items=[
                {"name": "A", "quantity": 1, "price": 100, "tax": 18, "discount": 10}
            ],
            discount_value=0,
            shipping_charge=0,
            extra_charge_amount=0,
            round_off=False,
        )
        ctx = build_context(inv, _customer(), _company())
        assert ctx["rows"][0]["total"] == "106.20"
        assert ctx["grand_total"] == "106.20"

    def test_items_without_name_are_skipped(self):
        inv = _invoice(items=[{"name": "", "quantity": 1, "price": 5}, {"name": "B"}])
        assert [
            r["name"] for r in build_context(inv, _customer(), _company())["rows"]
        ] == ["B"]

    def test_invoice_bank_details_override_company(self):
        ctx = build_context(
            _invoice(),
            _customer(),
            _company(),
            bank_details={"bank_name": "SBI", "account_number": "1234567890"},
        )
        assert ctx["bank"]["bank_name"] == "SBI"
        assert ctx["bank"]["upi"] == ""

    def test_no_bank_block_without_bank_data(self):
        company = _company(bank_name=None, bank_account=None, upi_id=None)
        assert build_context(_invoice(), _customer(), company)["bank"] is None

    def test_currency_without_symbol_uses_code(self):
        ctx = build_context(_invoice(currency="AED"), _customer(), _company())
        assert ctx["cs"] == "AED"


class TestTemplates:
    @pytest.mark.parametrize("template_id", sorted(BUILT_IN_TEMPLATES))
    @pytest.mark.parametrize("document_type", ["invoice", "quotation", "proforma"])
    def test_every_template_renders_totals(self, template_id, document_type):
        html = InvoicePDFService().render_html(
            _invoice(document_type=document_type), _customer(), _company(), template_id
        )
        assert "INV-2611-0001" in html
        assert "₹1416.00" in html
        assert "Packing" in html and "Shipping" in html
        assert "PO-42" in html
        assert "Acme Pvt Ltd" in html

    @pytest.mark.parametrize("template_id", sorted(BUILT_IN_TEMPLATES))
    def test_user_text_is_escaped(self, template_id):
        html = InvoicePDFService().render_html(
            _invoice(notes="<script>alert(1)</script>"),
            _customer(name='<img src=x onerror="alert(1)">'),
            _company(),
            template_id,
        )
        assert "<script>alert(1)" not in html
        assert "<img src=x" not in html
        assert "&lt;script&gt;" in html

    def test_logo_is_rendered_when_set(self):
        html = InvoicePDFService().render_html(
            _invoice(),
            _customer(),
            _company(logo_url="https://cdn.example.com/logo.png"),
            "aizen-bold",
        )
        assert 'src="https://cdn.example.com/logo.png"' in html


class TestRealPdf:
    def test_weasyprint_makes_a_one_page_pdf(self):
        import weasyprint

        svc = InvoicePDFService()
        html = svc.render_html(_invoice(), _customer(), _company())
        assert len(weasyprint.HTML(string=html).render().pages) == 1
        assert svc.html_to_pdf(html).startswith(b"%PDF")

    def test_long_invoice_flows_onto_more_pages(self):
        import weasyprint

        items = [{"name": f"Line {i}", "quantity": 1, "price": 10} for i in range(40)]
        html = InvoicePDFService().render_html(
            _invoice(items=items), _customer(), _company()
        )
        assert len(weasyprint.HTML(string=html).render().pages) > 1

    def test_internal_logo_url_is_never_fetched(self):
        with patch("urllib.request.OpenerDirector.open") as opener:
            pdf = InvoicePDFService().generate(
                _invoice(),
                _customer(),
                _company(logo_url="http://169.254.169.254/latest/meta-data/"),
                "aizen-bold",
            )
        opener.assert_not_called()
        assert pdf.startswith(b"%PDF")


def _addrinfo(*ips):
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 443)) for ip in ips]


class TestSafeUrlFetcher:
    @pytest.mark.parametrize(
        "url",
        [
            "http://example.com/logo.png",
            "file:///etc/passwd",
            "ftp://example.com/x.png",
            "https:///nohost.png",
        ],
    )
    def test_rejects_non_https(self, url):
        with pytest.raises(UnsafeURLError):
            ensure_public_https_url(url)

    @pytest.mark.parametrize(
        "ip",
        [
            "127.0.0.1",
            "10.0.0.5",
            "172.16.0.1",
            "192.168.1.1",
            "169.254.169.254",
            "0.0.0.0",
        ],
    )
    def test_rejects_hosts_resolving_to_private_ips(self, ip):
        with patch("socket.getaddrinfo", return_value=_addrinfo(ip)):
            with pytest.raises(UnsafeURLError):
                ensure_public_https_url("https://logo.example.com/a.png")

    def test_rejects_if_any_resolved_ip_is_private(self):
        with patch(
            "socket.getaddrinfo", return_value=_addrinfo("93.184.216.34", "10.0.0.1")
        ):
            with pytest.raises(UnsafeURLError):
                ensure_public_https_url("https://logo.example.com/a.png")

    def test_rejects_ipv6_loopback_and_mapped(self):
        for ip in ("::1", "::ffff:127.0.0.1", "fd00::1"):
            info = [(socket.AF_INET6, socket.SOCK_STREAM, 6, "", (ip, 443, 0, 0))]
            with patch("socket.getaddrinfo", return_value=info):
                with pytest.raises(UnsafeURLError):
                    ensure_public_https_url("https://logo.example.com/a.png")

    def test_accepts_public_host(self):
        with patch("socket.getaddrinfo", return_value=_addrinfo("93.184.216.34")):
            ensure_public_https_url("https://logo.example.com/a.png")

    def test_fetcher_rejects_file_scheme(self):
        with pytest.raises(UnsafeURLError):
            SafeURLFetcher().fetch("file:///etc/passwd")

    def test_fetcher_allows_data_image(self):
        png = (
            "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAA"
            "DUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
        )
        response = SafeURLFetcher().fetch(png)
        assert response.read().startswith(b"\x89PNG")

    def test_fetcher_rejects_data_non_image(self):
        with pytest.raises(UnsafeURLError):
            SafeURLFetcher().fetch("data:text/html,<p>hi</p>")


def _route_deps(mock_user, invoice, *, pdf=None, active=None, company=None):
    inv_svc = AsyncMock(get_with_customer=AsyncMock(return_value=invoice))
    if isinstance(invoice, Exception):
        inv_svc.get_with_customer = AsyncMock(side_effect=invoice)
    pdf_svc = pdf or MagicMock(
        render_html=MagicMock(return_value="<html>doc</html>"),
        html_to_pdf=MagicMock(return_value=b"%PDF-1.7 fake"),
    )
    tpl_svc = AsyncMock(
        get_active=AsyncMock(
            return_value=active, side_effect=None if active else NotFoundError("none")
        )
    )
    co_svc = AsyncMock(get_for_owner=AsyncMock(return_value=company or _company()))
    app.dependency_overrides[deps.get_current_principal] = lambda: mock_user
    app.dependency_overrides[deps.get_invoice_service] = lambda: inv_svc
    app.dependency_overrides[deps.get_invoice_pdf_service] = lambda: pdf_svc
    app.dependency_overrides[deps.get_invoice_template_service] = lambda: tpl_svc
    app.dependency_overrides[deps.get_company_settings_service] = lambda: co_svc
    return pdf_svc


def _with_customer(**overrides):
    inv = _invoice(**overrides)
    inv.customer = _customer()
    return inv


class TestPdfRoutes:
    def test_download_pdf(self, client: TestClient, mock_user):
        inv = _with_customer()
        pdf_svc = _route_deps(mock_user, inv)
        r = client.get(f"{settings.API_V1_STR}/invoices/{inv.id}/pdf")
        assert r.status_code == 200
        assert r.content == b"%PDF-1.7 fake"
        assert r.headers["content-type"] == "application/pdf"
        assert r.headers["cache-control"] == "no-store"
        assert r.headers["content-disposition"] == (
            'attachment; filename="invoice_INV-2611-0001.pdf"; '
            "filename*=UTF-8''invoice_INV-2611-0001.pdf"
        )
        # no active template -> clean-teal
        assert pdf_svc.render_html.call_args.args[3] == "clean-teal"

    def test_inline_disposition_and_unicode_filename(
        self, client: TestClient, mock_user
    ):
        inv = _with_customer(invoice_number="बिल-1", document_type="quotation")
        _route_deps(mock_user, inv)
        r = client.get(
            f"{settings.API_V1_STR}/invoices/{inv.id}/pdf",
            params={"disposition": "inline"},
        )
        cd = r.headers["content-disposition"]
        assert cd.startswith('inline; filename="quotation_')
        assert "filename*=UTF-8''quotation_%E0%A4%AC" in cd

    def test_requested_template_is_used(self, client: TestClient, mock_user):
        inv = _with_customer()
        pdf_svc = _route_deps(mock_user, inv)
        client.get(
            f"{settings.API_V1_STR}/invoices/{inv.id}/pdf",
            params={"template": "geometric"},
        )
        assert pdf_svc.render_html.call_args.args[3] == "geometric"

    def test_active_template_is_used(self, client: TestClient, mock_user):
        inv = _with_customer()
        active = SimpleNamespace(
            kind=SimpleNamespace(value="built_in"), built_in_id="aizen-bold"
        )
        pdf_svc = _route_deps(mock_user, inv, active=active)
        client.get(f"{settings.API_V1_STR}/invoices/{inv.id}/pdf")
        assert pdf_svc.render_html.call_args.args[3] == "aizen-bold"

    def test_invoice_bank_details_are_decrypted_for_render(
        self, client: TestClient, mock_user
    ):
        from app.core.security import encrypt_field

        owner = mock_user.id
        inv = _with_customer(
            bank_details={
                "bank_name": "SBI",
                "account_number": encrypt_field(owner, "999"),
            }
        )
        pdf_svc = _route_deps(mock_user, inv)
        client.get(f"{settings.API_V1_STR}/invoices/{inv.id}/pdf")
        bank = pdf_svc.render_html.call_args.kwargs["bank_details"]
        assert bank == {"bank_name": "SBI", "account_number": "999"}

    def test_other_users_invoice_is_404(self, client: TestClient, mock_user):
        _route_deps(mock_user, NotFoundError("Invoice not found"))
        r = client.get(f"{settings.API_V1_STR}/invoices/{uuid.uuid4()}/pdf")
        assert r.status_code == 404

    def test_invoice_without_customer_is_404(self, client: TestClient, mock_user):
        inv = _invoice()
        inv.customer = None
        _route_deps(mock_user, inv)
        r = client.get(f"{settings.API_V1_STR}/invoices/{inv.id}/pdf")
        assert r.status_code == 404

    def test_requires_auth(self, client: TestClient):
        r = client.get(f"{settings.API_V1_STR}/invoices/{uuid.uuid4()}/pdf")
        assert r.status_code == 401

    def test_preview_html(self, client: TestClient, mock_user):
        inv = _with_customer()
        _route_deps(mock_user, inv)
        r = client.get(f"{settings.API_V1_STR}/invoices/{inv.id}/preview-html")
        assert r.status_code == 200
        assert r.text == "<html>doc</html>"
        assert r.headers["content-type"].startswith("text/html")
        assert "default-src 'none'" in r.headers["content-security-policy"]
        assert r.headers["cache-control"] == "no-store"

    def test_end_to_end_real_render(self, client: TestClient, mock_user):
        inv = _with_customer()
        _route_deps(mock_user, inv, pdf=InvoicePDFService())
        r = client.get(f"{settings.API_V1_STR}/invoices/{inv.id}/pdf")
        assert r.status_code == 200
        assert r.content.startswith(b"%PDF")
