"""Render invoices to HTML and PDF on the server.

The HTML is the single source for both the in-app preview and the PDF, so
the two always look the same. PDFs are made on request and never stored.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.models import CompanySettings, Customer, Invoice
from app.services.invoice_totals import compute_invoice_totals, line_amounts
from app.services.safe_url_fetcher import make_safe_url_fetcher

_TEMPLATE_DIR = Path(__file__).parent.parent / "templates"

_jinja_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
)

_CURRENCY_SYMBOLS = {"INR": "₹", "USD": "$", "EUR": "€", "GBP": "£"}


def _format_currency(value: float, currency: str = "INR") -> str:
    sym = _CURRENCY_SYMBOLS.get(currency, currency + " ")
    return f"{sym}{value:,.2f}"


_jinja_env.globals["format_currency"] = _format_currency

_DOCUMENT_TITLES = {
    "invoice": "Invoice",
    "quotation": "Quotation",
    "challan": "Delivery Challan",
    "proforma": "Proforma Invoice",
}

# Built-in template ids, as stored in InvoiceTemplate.built_in_id and used by
# the frontend template picker.
DEFAULT_TEMPLATE = "clean-teal"
BUILT_IN_TEMPLATES = frozenset(
    {"clean-teal", "geometric", "circle-studio", "aizen-bold", "default"}
)
DEFAULT_FOOTER_NOTE = "Thank you for your business!"


def document_title_for(document_type: str) -> str:
    return _DOCUMENT_TITLES.get(document_type, "Invoice")


def resolve_template_id(
    requested: str | None,
    active_kind: str | None = None,
    active_built_in_id: str | None = None,
) -> str:
    """Choose the template for a document.

    1. An explicitly requested built-in id.
    2. The user's active template: its built-in id, or ``default`` for the
       custom/imported kinds (same as the frontend, which has no renderer
       for those kinds either).
    3. ``clean-teal``.
    """
    if requested in BUILT_IN_TEMPLATES:
        return requested
    if active_kind == "built_in":
        if active_built_in_id in BUILT_IN_TEMPLATES:
            return active_built_in_id
        return DEFAULT_TEMPLATE
    if active_kind:
        return "default"
    return DEFAULT_TEMPLATE


def _enum_value(value: Any) -> Any:
    return getattr(value, "value", value)


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _attr(obj: Any, name: str) -> str:
    return _text(getattr(obj, name, None))


def _money(value: float) -> str:
    return f"{value:.2f}"


def _qty(value: Any) -> str:
    try:
        number = float(value or 0)
    except (TypeError, ValueError):
        return _text(value)
    return f"{number:g}"


@dataclass(frozen=True)
class SummaryEntry:
    label: str
    value: str
    red: bool = False


def _bank_details(
    company: CompanySettings, invoice_bank: dict[str, Any] | None
) -> dict[str, str] | None:
    if invoice_bank:
        bank = {k: _text(invoice_bank.get(k)) for k in _BANK_KEYS}
    else:
        bank = {
            "bank_name": _attr(company, "bank_name"),
            "account_name": _attr(company, "name"),
            "account_number": _attr(company, "bank_account"),
            "ifsc": _attr(company, "bank_ifsc"),
            "branch": _attr(company, "bank_branch"),
            "upi": _attr(company, "upi_id"),
        }
    if not (bank["bank_name"] or bank["account_number"] or bank["upi"]):
        return None
    return bank


_BANK_KEYS = ("bank_name", "account_name", "account_number", "ifsc", "branch", "upi")


def build_context(
    invoice: Invoice,
    customer: Customer,
    company: CompanySettings,
    *,
    bank_details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the template context from saved data only.

    ``bank_details`` are the invoice's own (already decrypted) bank details;
    when absent the company's bank details are used.
    """
    document_type = _enum_value(invoice.document_type) or "invoice"
    document_title = document_title_for(document_type)
    hide_pricing = document_type == "challan"
    currency = invoice.currency or "INR"
    cs = _CURRENCY_SYMBOLS.get(currency, currency)
    totals = compute_invoice_totals(invoice)

    items = [i for i in (invoice.items or []) if _text(_get(i, "name"))]
    lines = [line_amounts(i) for i in items]
    rows = [
        {
            "name": _text(_get(item, "name")),
            "description": _text(_get(item, "description")),
            "quantity": _qty(_get(item, "quantity")),
            "unit": _text(_get(item, "unit")),
            "hsn_code": _text(_get(item, "hsn_code")),
            "price": _money(float(_get(item, "price") or 0)),
            "total": _money(line.total),
        }
        for item, line in zip(items, lines, strict=True)
    ]

    summary: list[SummaryEntry] = [
        SummaryEntry("Subtotal", cs + _money(totals.subtotal))
    ]
    if totals.items_discount > 0:
        summary.append(
            SummaryEntry(
                "Item Discounts", f"-{cs}{_money(totals.items_discount)}", True
            )
        )
    if totals.invoice_discount > 0:
        summary.append(
            SummaryEntry("Discount", f"-{cs}{_money(totals.invoice_discount)}", True)
        )
    if totals.total_tax > 0:
        summary.append(SummaryEntry("Tax", cs + _money(totals.total_tax)))
    if totals.shipping_charge > 0:
        summary.append(SummaryEntry("Shipping", cs + _money(totals.shipping_charge)))
    if totals.extra_charge_amount > 0:
        summary.append(
            SummaryEntry(
                _attr(invoice, "extra_charge_label") or "Extra",
                cs + _money(totals.extra_charge_amount),
            )
        )
    if getattr(invoice, "round_off", False):
        diff = totals.grand_total - totals.raw_grand_total
        if abs(diff) >= 0.005:
            sign = "-" if diff < 0 else ""
            summary.append(SummaryEntry("Round Off", f"{sign}{cs}{_money(abs(diff))}"))

    biz_address = ", ".join(
        p
        for p in (
            _attr(company, "address"),
            _attr(company, "city"),
            _attr(company, "state"),
            _attr(company, "pincode"),
        )
        if p
    )
    status = _enum_value(getattr(invoice, "status", None))

    return {
        "document_type": document_type,
        "document_title": document_title,
        "doc_title": document_title.upper(),
        "hide_pricing": hide_pricing,
        "is_draft": status == "draft",
        "invoice_number": _attr(invoice, "invoice_number"),
        "invoice_date": _attr(invoice, "invoice_date"),
        "due_date": "" if hide_pricing else _attr(invoice, "due_date"),
        "valid_until": _attr(invoice, "valid_until")
        if document_type == "quotation"
        else "",
        "po_number": _attr(invoice, "po_number"),
        "place_of_supply": _attr(invoice, "place_of_supply"),
        "reverse_charge": bool(getattr(invoice, "reverse_charge", False)),
        "vehicle_info": _attr(invoice, "vehicle_info"),
        "delivery_notes": _attr(invoice, "delivery_notes"),
        "notes": _attr(invoice, "notes"),
        "payment_terms": _attr(invoice, "payment_terms"),
        "cs": cs,
        "currency": currency,
        "rows": rows,
        "summary": summary,
        "grand_total": _money(totals.grand_total),
        "biz": {
            "name": _attr(company, "name") or "Your Business",
            "tagline": "",
            "address": biz_address,
            "phone": _attr(company, "phone"),
            "email": _attr(company, "email"),
            "gstin": _attr(company, "gstin"),
            "logo": _attr(company, "logo_url") or None,
        },
        "cd": {
            "name": _attr(customer, "name") or "-",
            "address": _attr(customer, "billing_address") or _attr(customer, "address"),
            "gst": _attr(customer, "gstin") or _attr(customer, "gst"),
            "phone": _attr(customer, "phone"),
            "email": _attr(customer, "email"),
        },
        "bank": _bank_details(company, bank_details),
        "footer_note": _attr(company, "terms_and_conditions") or DEFAULT_FOOTER_NOTE,
    }


def _get(item: Any, key: str) -> Any:
    if isinstance(item, dict):
        return item.get(key)
    return getattr(item, key, None)


class InvoicePDFService:
    def render_html(
        self,
        invoice: Invoice,
        customer: Customer,
        company: CompanySettings,
        template_id: str | None = None,
        *,
        bank_details: dict[str, Any] | None = None,
    ) -> str:
        context = build_context(invoice, customer, company, bank_details=bank_details)
        if context["hide_pricing"]:
            name = "challan"
        else:
            name = (
                template_id if template_id in BUILT_IN_TEMPLATES else DEFAULT_TEMPLATE
            )
        template = _jinja_env.get_template(f"invoices/{name}.html")
        return template.render(**context)

    def html_to_pdf(self, html: str) -> bytes:
        import weasyprint

        pdf: bytes = weasyprint.HTML(
            string=html, url_fetcher=make_safe_url_fetcher()
        ).write_pdf()
        return pdf

    def generate(
        self,
        invoice: Invoice,
        customer: Customer,
        company: CompanySettings,
        template_id: str | None = None,
        *,
        bank_details: dict[str, Any] | None = None,
    ) -> bytes:
        html = self.render_html(
            invoice, customer, company, template_id, bank_details=bank_details
        )
        return self.html_to_pdf(html)
