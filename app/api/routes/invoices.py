import logging
import uuid
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Query

from app.api.deps import (
    CompanySettingsServiceDep,
    CurrentUser,
    InvoicePDFServiceDep,
    InvoiceServiceDep,
    UserServiceDep,
    WhatsAppServiceDep,
)
from app.exceptions import NotFoundError
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
from app.services.invoice_pdf_service import document_title_for
from app.services.whatsapp_service import WhatsAppService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/invoices", tags=["invoices"])


@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats(
    current_user: CurrentUser,
    invoice_service: InvoiceServiceDep,
    document_type: DocumentType | None = None,
) -> Any:
    stats = await invoice_service.get_dashboard_stats(current_user.id, document_type)
    return DashboardStats(**stats)


@router.get("/", response_model=InvoicesPublic)
async def read_invoices(
    current_user: CurrentUser,
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
    current_user: CurrentUser, invoice_service: InvoiceServiceDep, id: uuid.UUID
) -> Any:
    return await invoice_service.get_with_customer(id, current_user.id)


@router.post("/", response_model=InvoicePublic, status_code=201)
async def create_invoice(
    *, current_user: CurrentUser, invoice_service: InvoiceServiceDep, invoice_in: InvoiceCreate
) -> Any:
    return await invoice_service.create(invoice_in, current_user.id)


@router.put("/{id}", response_model=InvoicePublic)
async def update_invoice(
    *,
    current_user: CurrentUser,
    invoice_service: InvoiceServiceDep,
    id: uuid.UUID,
    invoice_in: InvoiceUpdate,
) -> Any:
    return await invoice_service.update(id, current_user.id, invoice_in)


@router.delete("/{id}", status_code=204)
async def delete_invoice(
    current_user: CurrentUser, invoice_service: InvoiceServiceDep, id: uuid.UUID
) -> None:
    await invoice_service.delete(id, current_user.id)


@router.post("/{id}/send-email", status_code=200)
async def send_invoice_email(
    *,
    current_user: CurrentUser,
    invoice_service: InvoiceServiceDep,
    pdf_service: InvoicePDFServiceDep,
    company_settings_service: CompanySettingsServiceDep,
    user_service: UserServiceDep,
    background_tasks: BackgroundTasks,
    id: uuid.UUID,
    req: SendEmailRequest,
) -> dict[str, str]:
    invoice = await invoice_service.get_with_customer(id, current_user.id)
    if not invoice.customer:
        raise NotFoundError("Customer not found for this invoice")

    access_token = await user_service.get_valid_google_access_token(current_user)

    company = await company_settings_service.get_for_owner(current_user.id)
    pdf_bytes = pdf_service.generate(invoice, invoice.customer, company)

    dt = invoice.document_type.value if hasattr(invoice.document_type, "value") else invoice.document_type
    doc_label = document_title_for(dt)

    subject = req.subject or f"{doc_label} {invoice.invoice_number} from {company.name}"
    html_content = f"""<p>Dear {invoice.customer.name},</p>
<p>Please find your {doc_label.lower()} <strong>{invoice.invoice_number}</strong> attached.</p>
<p>Amount: {invoice.currency} {invoice.grand_total:,.2f}<br>
Due Date: {invoice.due_date or 'N/A'}</p>
<p>Thank you for your business!</p>"""

    background_tasks.add_task(
        send_gmail_email,
        access_token=access_token,
        from_email=current_user.google_email or current_user.email,
        to_email=req.to_email,
        subject=subject,
        html_content=html_content,
        attachment=(
            f"{doc_label.lower().replace(' ', '_')}_{invoice.invoice_number}.pdf",
            pdf_bytes,
            "application/pdf",
        ),
    )
    return {"message": "Email sent successfully"}


@router.post("/{id}/send-whatsapp", status_code=200)
async def send_invoice_whatsapp(
    *,
    current_user: CurrentUser,
    invoice_service: InvoiceServiceDep,
    pdf_service: InvoicePDFServiceDep,
    company_settings_service: CompanySettingsServiceDep,
    whatsapp_service: WhatsAppServiceDep,
    id: uuid.UUID,
    req: SendWhatsAppRequest,
) -> dict[str, Any]:
    invoice = await invoice_service.get_with_customer(id, current_user.id)
    if not invoice.customer:
        raise NotFoundError("Customer not found for this invoice")

    company = await company_settings_service.get_for_owner(current_user.id)
    pdf_bytes = pdf_service.generate(invoice, invoice.customer, company)

    dt = invoice.document_type.value if hasattr(invoice.document_type, "value") else invoice.document_type
    doc_label = document_title_for(dt)

    wa_svc = whatsapp_service
    if company.whatsapp_enabled and company.openwa_api_key and company.openwa_session_id:
        wa_svc = WhatsAppService(
            base_url=company.openwa_base_url,
            api_key=company.openwa_api_key,
            session_id=company.openwa_session_id,
        )

    chat_id = f"{req.to_phone.lstrip('+')}@c.us"
    result = wa_svc.send_document(
        chat_id=chat_id,
        pdf_bytes=pdf_bytes,
        filename=f"{doc_label.lower().replace(' ', '_')}_{invoice.invoice_number}.pdf",
        caption=f"{doc_label} {invoice.invoice_number} - {invoice.currency} {invoice.grand_total:,.2f}",
    )
    return {"message": "WhatsApp message sent", "message_id": result.get("messageId")}

@router.post("/{id}/send-reminder", status_code=200)
async def send_invoice_reminder(
    *,
    current_user: CurrentUser,
    invoice_service: InvoiceServiceDep,
    pdf_service: InvoicePDFServiceDep,
    company_settings_service: CompanySettingsServiceDep,
    whatsapp_service: WhatsAppServiceDep,
    id: uuid.UUID,
    req: SendReminderRequest,
) -> dict[str, Any]:
    invoice = await invoice_service.get_with_customer(id, current_user.id)
    if not invoice.customer:
        raise NotFoundError("Customer not found for this invoice")

    company = await company_settings_service.get_for_owner(current_user.id)
    pdf_bytes = pdf_service.generate(invoice, invoice.customer, company)

    dt = invoice.document_type.value if hasattr(invoice.document_type, "value") else invoice.document_type
    doc_label = document_title_for(dt)

    wa_svc = whatsapp_service
    if company.whatsapp_enabled and company.openwa_api_key and company.openwa_session_id:
        wa_svc = WhatsAppService(
            base_url=company.openwa_base_url,
            api_key=company.openwa_api_key,
            session_id=company.openwa_session_id,
        )

    chat_id = f"{req.to_phone.lstrip('+')}@c.us"

    caption = f"Reminder: {doc_label} {invoice.invoice_number} is due. "
    if req.days_overdue:
        caption += f"({req.days_overdue} days overdue) "
    caption += f"Amount: {invoice.currency} {invoice.grand_total:,.2f}"

    result = whatsapp_service.send_document(
        chat_id=chat_id,
        pdf_bytes=pdf_bytes,
        filename=f"{doc_label.lower().replace(' ', '_')}_{invoice.invoice_number}.pdf",
        caption=caption,
    )
    return {"message": "Reminder sent", "message_id": result.get("messageId")}
