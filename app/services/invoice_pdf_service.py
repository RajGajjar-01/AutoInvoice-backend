import base64
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.models import CompanySettings, Customer, Invoice

_TEMPLATE_DIR = Path(__file__).parent.parent / "templates"

_jinja_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
)


def _format_currency(value: float, currency: str = "INR") -> str:
    symbols = {"INR": "\u20B9", "USD": "$", "EUR": "\u20AC", "GBP": "\u00A3"}
    sym = symbols.get(currency, currency + " ")
    return f"{sym}{value:,.2f}"


_jinja_env.globals["format_currency"] = _format_currency

_DOCUMENT_TITLES = {
    "invoice": "Invoice",
    "quotation": "Quotation",
    "challan": "Delivery Challan",
    "proforma": "Proforma Invoice",
}


def document_title_for(document_type: str) -> str:
    return _DOCUMENT_TITLES.get(document_type, "Invoice")


class InvoicePDFService:
    def render_html(
        self,
        invoice: Invoice,
        customer: Customer,
        company: CompanySettings,
    ) -> str:
        template = _jinja_env.get_template("invoice_pdf.html")

        document_type = (
            invoice.document_type.value
            if hasattr(invoice.document_type, "value")
            else invoice.document_type
        )

        return template.render(
            invoice=invoice,
            customer=customer,
            company=company,
            items=invoice.items,
            currency=invoice.currency or "INR",
            document_type=document_type,
            document_title=_DOCUMENT_TITLES.get(document_type, "Invoice"),
            hide_pricing=document_type == "challan",
        )

    def generate(
        self,
        invoice: Invoice,
        customer: Customer,
        company: CompanySettings,
    ) -> bytes:
        html = self.render_html(invoice, customer, company)

        import weasyprint

        pdf_bytes = weasyprint.HTML(string=html).write_pdf()
        return pdf_bytes

    def generate_base64(
        self,
        invoice: Invoice,
        customer: Customer,
        company: CompanySettings,
    ) -> str:
        pdf_bytes = self.generate(invoice, customer, company)
        return base64.b64encode(pdf_bytes).decode("ascii")
