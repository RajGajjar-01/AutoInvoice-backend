import html
import re
import uuid
from typing import Any, Literal
from urllib.parse import quote

import httpx
import structlog
from fastapi import APIRouter, HTTPException, Query, Response
from fastapi.responses import HTMLResponse
from starlette.concurrency import run_in_threadpool

from app.api.deps import (
    CompanySettingsServiceDep,
    CurrentPrincipal,
    CurrentUser,
    InvoicePDFServiceDep,
    InvoiceServiceDep,
    InvoiceTemplateServiceDep,
    UserServiceDep,
    WhatsAppServiceDep,
)
from app.exceptions import NotFoundError
from app.models import CompanySettings, Invoice
from app.schemas import (
    DashboardStats,
    DocumentType,
    InvoiceCreate,
    InvoicePublic,
    InvoicesPublic,
    InvoiceStatus,
    InvoiceUpdate,
    InvoiceWithCustomer,
    SendEmailRequest,
    SendReminderRequest,
    SendWhatsAppRequest,
)
from app.services.gmail_service import send_email as send_gmail_email
from app.services.invoice_pdf_service import (
    BUILT_IN_TEMPLATES,
    InvoicePDFService,
    document_title_for,
    resolve_template_id,
)
from app.services.invoice_service import InvoiceService, decrypt_bank_details
from app.services.invoice_template_service import InvoiceTemplateService
from app.services.whatsapp_service import (
    InvalidPhoneError,
    WhatsAppService,
    to_whatsapp_chat_id,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/invoices", tags=["invoices"])


@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats(
    current_user: CurrentPrincipal,
    invoice_service: InvoiceServiceDep,
    document_type: DocumentType | None = None,
) -> Any:
    stats = await invoice_service.get_dashboard_stats(current_user.id, document_type)
    return DashboardStats(**stats)


@router.get("/", response_model=InvoicesPublic)
async def read_invoices(
    current_user: CurrentPrincipal,
    invoice_service: InvoiceServiceDep,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    status: InvoiceStatus | None = None,
    document_type: DocumentType | None = None,
    customer_id: uuid.UUID | None = None,
) -> Any:
    invoices, count = await invoice_service.list_items(
        current_user.id,
        skip=skip,
        limit=limit,
        status=status,
        document_type=document_type,
        customer_id=customer_id,
    )
    return InvoicesPublic(data=invoices, count=count)


@router.get("/{id}", response_model=InvoiceWithCustomer)
async def read_invoice(
    current_user: CurrentPrincipal, invoice_service: InvoiceServiceDep, id: uuid.UUID
) -> Any:
    return await invoice_service.get_with_customer(id, current_user.id)


@router.post("/", response_model=InvoicePublic, status_code=201)
async def create_invoice(
    *,
    current_user: CurrentPrincipal,
    invoice_service: InvoiceServiceDep,
    invoice_in: InvoiceCreate,
) -> Any:
    return await invoice_service.create(invoice_in, current_user.id)


@router.put("/{id}", response_model=InvoicePublic)
async def update_invoice(
    *,
    current_user: CurrentPrincipal,
    invoice_service: InvoiceServiceDep,
    id: uuid.UUID,
    invoice_in: InvoiceUpdate,
) -> Any:
    return await invoice_service.update(id, current_user.id, invoice_in)


@router.delete("/{id}", status_code=204)
async def delete_invoice(
    current_user: CurrentPrincipal, invoice_service: InvoiceServiceDep, id: uuid.UUID
) -> None:
    await invoice_service.delete(id, current_user.id)


def _document_label(invoice: Invoice) -> str:
    dt = (
        invoice.document_type.value
        if hasattr(invoice.document_type, "value")
        else invoice.document_type
    )
    return document_title_for(dt)


def _pdf_filename(doc_label: str, invoice_number: str) -> str:
    return f"{doc_label.lower().replace(' ', '_')}_{invoice_number}.pdf"


def _content_disposition(disposition: str, filename: str) -> str:
    """RFC 6266 header with an ASCII fallback and a UTF-8 filename*."""
    ascii_name = re.sub(r"[^A-Za-z0-9._-]+", "_", filename).strip("_") or "document.pdf"
    return (
        f"{disposition}; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename)}"
    )


async def _load_invoice(
    invoice_service: InvoiceService, invoice_id: uuid.UUID, owner_id: uuid.UUID
) -> Invoice:
    invoice = await invoice_service.get_with_customer(invoice_id, owner_id)
    if not invoice.customer:
        raise NotFoundError("Customer not found for this invoice")
    return invoice


async def _company_or_blank(
    company_settings_service: Any, owner_id: uuid.UUID
) -> CompanySettings:
    try:
        company: CompanySettings = await company_settings_service.get_for_owner(
            owner_id
        )
        return company
    except NotFoundError:
        # A user who has not filled company settings can still download.
        return CompanySettings(owner_id=owner_id, name="Your Business")


async def _template_for(
    template_service: InvoiceTemplateService,
    owner_id: uuid.UUID,
    requested: str | None,
) -> str:
    if requested in BUILT_IN_TEMPLATES:
        return requested
    try:
        active = await template_service.get_active(owner_id)
    except NotFoundError:
        return resolve_template_id(None)
    kind = getattr(active.kind, "value", active.kind)
    return resolve_template_id(None, kind, active.built_in_id)


async def _render_invoice_html(
    *,
    owner_id: uuid.UUID,
    invoice_id: uuid.UUID,
    invoice_service: InvoiceService,
    company_settings_service: Any,
    template_service: InvoiceTemplateService,
    pdf_service: InvoicePDFService,
    template: str | None = None,
    invoice: Invoice | None = None,
    company: CompanySettings | None = None,
) -> tuple[Invoice, CompanySettings, str]:
    """Load saved data, choose the template and render the document HTML."""
    if invoice is None:
        invoice = await _load_invoice(invoice_service, invoice_id, owner_id)
    if company is None:
        company = await _company_or_blank(company_settings_service, owner_id)
    template_id = await _template_for(template_service, owner_id, template)
    raw_bank = getattr(invoice, "bank_details", None)
    bank = (
        decrypt_bank_details(owner_id, raw_bank) if isinstance(raw_bank, dict) else None
    )
    html_doc = pdf_service.render_html(
        invoice, invoice.customer, company, template_id, bank_details=bank
    )
    return invoice, company, html_doc


async def _render_invoice_pdf(**kwargs: Any) -> tuple[Invoice, CompanySettings, bytes]:
    pdf_service: InvoicePDFService = kwargs["pdf_service"]
    invoice, company, html_doc = await _render_invoice_html(**kwargs)
    # WeasyPrint is CPU-bound and synchronous: keep it off the event loop.
    pdf_bytes = await run_in_threadpool(pdf_service.html_to_pdf, html_doc)
    return invoice, company, pdf_bytes


TemplateQuery = Query(
    default=None,
    description="Built-in template id. Defaults to the user's active template.",
)


@router.get(
    "/{id}/pdf",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}, "description": "PDF file"}},
)
async def download_invoice_pdf(
    *,
    current_user: CurrentPrincipal,
    invoice_service: InvoiceServiceDep,
    pdf_service: InvoicePDFServiceDep,
    company_settings_service: CompanySettingsServiceDep,
    template_service: InvoiceTemplateServiceDep,
    id: uuid.UUID,
    template: str | None = TemplateQuery,
    disposition: Literal["attachment", "inline"] = "attachment",
) -> Response:
    """Render the saved invoice as a PDF, on request. Nothing is stored."""
    invoice, _, pdf_bytes = await _render_invoice_pdf(
        owner_id=current_user.id,
        invoice_id=id,
        invoice_service=invoice_service,
        company_settings_service=company_settings_service,
        template_service=template_service,
        pdf_service=pdf_service,
        template=template,
    )
    filename = _pdf_filename(_document_label(invoice), invoice.invoice_number)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": _content_disposition(disposition, filename),
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/{id}/preview-html", response_class=HTMLResponse)
async def preview_invoice_html(
    *,
    current_user: CurrentPrincipal,
    invoice_service: InvoiceServiceDep,
    pdf_service: InvoicePDFServiceDep,
    company_settings_service: CompanySettingsServiceDep,
    template_service: InvoiceTemplateServiceDep,
    id: uuid.UUID,
    template: str | None = TemplateQuery,
) -> HTMLResponse:
    """The exact HTML that the PDF is made from, for the in-app preview."""
    _, _, html_doc = await _render_invoice_html(
        owner_id=current_user.id,
        invoice_id=id,
        invoice_service=invoice_service,
        company_settings_service=company_settings_service,
        template_service=template_service,
        pdf_service=pdf_service,
        template=template,
    )
    return HTMLResponse(
        content=html_doc,
        headers={
            "Cache-Control": "no-store",
            # The page is static: no scripts, only inline styles and images.
            "Content-Security-Policy": (
                "default-src 'none'; style-src 'unsafe-inline'; img-src https: data:"
            ),
        },
    )


def _resolve_whatsapp_service(
    default: WhatsAppService, company: CompanySettings
) -> WhatsAppService:
    if (
        company.whatsapp_enabled
        and company.openwa_api_key
        and company.openwa_session_id
    ):
        return WhatsAppService(
            base_url=company.openwa_base_url,
            api_key=company.openwa_api_key,
            session_id=company.openwa_session_id,
        )
    return default


WHATSAPP_NOT_SET_UP = (
    "WhatsApp sending is not set up. Add your OpenWA server URL, API key and "
    "session ID in Settings, then try again."
)


async def _send_invoice_on_whatsapp(
    *,
    owner_id: uuid.UUID,
    invoice_id: uuid.UUID,
    to_phone: str,
    caption_for: Any,
    invoice_service: InvoiceService,
    company_settings_service: Any,
    template_service: InvoiceTemplateService,
    pdf_service: InvoicePDFService,
    whatsapp_service: WhatsAppService,
) -> dict[str, Any]:
    """Check everything that can fail cheaply first, then render and send."""
    invoice = await _load_invoice(invoice_service, invoice_id, owner_id)
    company = await _company_or_blank(company_settings_service, owner_id)
    wa_svc = _resolve_whatsapp_service(whatsapp_service, company)
    if not wa_svc.is_configured:
        raise HTTPException(status_code=503, detail=WHATSAPP_NOT_SET_UP)
    try:
        chat_id = to_whatsapp_chat_id(to_phone)
    except InvalidPhoneError:
        raise HTTPException(
            status_code=422,
            detail="The customer's phone number is not valid for WhatsApp. "
            "Save it with the country code, for example +91 98765 43210.",
        )

    _, _, pdf_bytes = await _render_invoice_pdf(
        owner_id=owner_id,
        invoice_id=invoice_id,
        invoice_service=invoice_service,
        company_settings_service=company_settings_service,
        template_service=template_service,
        pdf_service=pdf_service,
        invoice=invoice,
        company=company,
    )
    doc_label = _document_label(invoice)
    try:
        result = await run_in_threadpool(
            wa_svc.send_document,
            chat_id=chat_id,
            pdf_bytes=pdf_bytes,
            filename=_pdf_filename(doc_label, invoice.invoice_number),
            caption=caption_for(invoice, doc_label),
        )
    except httpx.HTTPStatusError as e:
        logger.error(
            "OpenWA send failed", status=e.response.status_code, body=e.response.text
        )
        raise HTTPException(
            status_code=502,
            detail="WhatsApp (OpenWA) refused the message. Check that your "
            "OpenWA session is connected and the API key is correct.",
        )
    except httpx.HTTPError:
        logger.exception("OpenWA unreachable")
        raise HTTPException(
            status_code=502,
            detail="Could not reach your WhatsApp (OpenWA) server. Check the "
            "server URL in Settings and that the server is running.",
        )
    return result if isinstance(result, dict) else {}


@router.post("/{id}/send-email", status_code=200)
async def send_invoice_email(
    *,
    current_user: CurrentUser,
    invoice_service: InvoiceServiceDep,
    pdf_service: InvoicePDFServiceDep,
    company_settings_service: CompanySettingsServiceDep,
    template_service: InvoiceTemplateServiceDep,
    user_service: UserServiceDep,
    id: uuid.UUID,
    req: SendEmailRequest,
) -> dict[str, str]:
    invoice = await _load_invoice(invoice_service, id, current_user.id)
    assert invoice.customer is not None

    access_token = await user_service.get_valid_google_access_token(current_user)

    invoice, company, pdf_bytes = await _render_invoice_pdf(
        owner_id=current_user.id,
        invoice_id=id,
        invoice_service=invoice_service,
        company_settings_service=company_settings_service,
        template_service=template_service,
        pdf_service=pdf_service,
        invoice=invoice,
    )

    doc_label = _document_label(invoice)

    subject = req.subject or f"{doc_label} {invoice.invoice_number} from {company.name}"
    body_html = (
        "<br>".join(html.escape(line) for line in req.message.splitlines())
        if req.message.strip()
        else f"Please find your {doc_label.lower()} <strong>{invoice.invoice_number}</strong> attached."
    )
    html_content = f"""<p>Dear {invoice.customer.name},</p>
<p>{body_html}</p>
<p>Amount: {invoice.currency} {invoice.grand_total:,.2f}<br>
Due Date: {invoice.due_date or "N/A"}</p>
<p>Thank you for your business!</p>"""

    try:
        send_gmail_email(
            access_token=access_token,
            from_email=current_user.google_email or current_user.email,
            to_email=req.to_email,
            subject=subject,
            html_content=html_content,
            attachment=(
                _pdf_filename(doc_label, invoice.invoice_number),
                pdf_bytes,
                "application/pdf",
            ),
        )
    except httpx.HTTPStatusError as e:
        logger.error(
            "Gmail send failed", status=e.response.status_code, body=e.response.text
        )
        raise HTTPException(
            status_code=502,
            detail="Gmail rejected the email. Try reconnecting your Google "
            "account in Settings, then send again.",
        )
    except httpx.HTTPError:
        logger.exception("Gmail send failed")
        raise HTTPException(
            status_code=502, detail="Could not reach Gmail. Please try again."
        )
    return {"message": "Email sent successfully"}


@router.post("/{id}/send-whatsapp", status_code=200)
async def send_invoice_whatsapp(
    *,
    current_user: CurrentUser,
    invoice_service: InvoiceServiceDep,
    pdf_service: InvoicePDFServiceDep,
    company_settings_service: CompanySettingsServiceDep,
    template_service: InvoiceTemplateServiceDep,
    whatsapp_service: WhatsAppServiceDep,
    id: uuid.UUID,
    req: SendWhatsAppRequest,
) -> dict[str, Any]:
    result = await _send_invoice_on_whatsapp(
        owner_id=current_user.id,
        invoice_id=id,
        to_phone=req.to_phone,
        caption_for=lambda inv, label: (
            f"{label} {inv.invoice_number} - {inv.currency} {inv.grand_total:,.2f}"
        ),
        invoice_service=invoice_service,
        company_settings_service=company_settings_service,
        template_service=template_service,
        pdf_service=pdf_service,
        whatsapp_service=whatsapp_service,
    )
    return {"message": "WhatsApp message sent", "message_id": result.get("messageId")}


@router.post("/{id}/send-reminder", status_code=200)
async def send_invoice_reminder(
    *,
    current_user: CurrentUser,
    invoice_service: InvoiceServiceDep,
    pdf_service: InvoicePDFServiceDep,
    company_settings_service: CompanySettingsServiceDep,
    template_service: InvoiceTemplateServiceDep,
    whatsapp_service: WhatsAppServiceDep,
    id: uuid.UUID,
    req: SendReminderRequest,
) -> dict[str, Any]:
    def caption_for(inv: Invoice, label: str) -> str:
        caption = f"Reminder: {label} {inv.invoice_number} is due. "
        if req.days_overdue:
            caption += f"({req.days_overdue} days overdue) "
        return caption + f"Amount: {inv.currency} {inv.grand_total:,.2f}"

    result = await _send_invoice_on_whatsapp(
        owner_id=current_user.id,
        invoice_id=id,
        to_phone=req.to_phone,
        caption_for=caption_for,
        invoice_service=invoice_service,
        company_settings_service=company_settings_service,
        template_service=template_service,
        pdf_service=pdf_service,
        whatsapp_service=whatsapp_service,
    )
    return {"message": "Reminder sent", "message_id": result.get("messageId")}
