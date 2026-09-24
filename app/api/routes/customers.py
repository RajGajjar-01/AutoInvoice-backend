import html
import uuid
from typing import Any

import httpx
import structlog
from fastapi import APIRouter, HTTPException

from app.api.deps import (
    CompanySettingsServiceDep,
    CurrentPrincipal,
    CurrentUser,
    CustomerServiceDep,
    InvoicePDFServiceDep,
    InvoiceServiceDep,
    UserServiceDep,
)
from app.exceptions import NotFoundError
from app.schemas import (
    CustomerCreate,
    CustomerPublic,
    CustomerSendEmailRequest,
    CustomersPublic,
    CustomerUpdate,
)
from app.services.gmail_service import send_email as send_gmail_email

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/customers", tags=["customers"])


@router.get("/", response_model=CustomersPublic)
async def read_customers(
    current_user: CurrentPrincipal,
    customer_service: CustomerServiceDep,
    skip: int = 0,
    limit: int = 100,
) -> Any:
    customers, count = await customer_service.list_items(
        current_user.id, skip=skip, limit=limit
    )
    return CustomersPublic(data=customers, count=count)


@router.get("/{id}", response_model=CustomerPublic)
async def read_customer(
    current_user: CurrentPrincipal, customer_service: CustomerServiceDep, id: uuid.UUID
) -> Any:
    return await customer_service.get_owned(id, current_user.id)


@router.post("/", response_model=CustomerPublic, status_code=201)
async def create_customer(
    *,
    current_user: CurrentPrincipal,
    customer_service: CustomerServiceDep,
    customer_in: CustomerCreate,
) -> Any:
    return await customer_service.create(customer_in, current_user.id)


@router.put("/{id}", response_model=CustomerPublic)
async def update_customer(
    *,
    current_user: CurrentPrincipal,
    customer_service: CustomerServiceDep,
    id: uuid.UUID,
    customer_in: CustomerUpdate,
) -> Any:
    return await customer_service.update(id, current_user.id, customer_in)


@router.delete("/{id}", status_code=204)
async def delete_customer(
    current_user: CurrentPrincipal, customer_service: CustomerServiceDep, id: uuid.UUID
) -> None:
    await customer_service.delete(id, current_user.id)


@router.post("/{id}/send-email", status_code=200)
async def send_customer_email(
    *,
    current_user: CurrentUser,
    customer_service: CustomerServiceDep,
    invoice_service: InvoiceServiceDep,
    pdf_service: InvoicePDFServiceDep,
    company_settings_service: CompanySettingsServiceDep,
    user_service: UserServiceDep,
    id: uuid.UUID,
    req: CustomerSendEmailRequest,
) -> dict[str, str]:
    customer = await customer_service.get_owned(id, current_user.id)
    access_token = await user_service.get_valid_google_access_token(current_user)
    company = await company_settings_service.get_for_owner(current_user.id)

    attachment = None
    if req.invoice_id:
        invoice = await invoice_service.get_with_customer(
            req.invoice_id, current_user.id
        )
        if not invoice.customer or invoice.customer.id != customer.id:
            raise NotFoundError("Invoice not found for this customer")
        pdf_bytes = pdf_service.generate(invoice, invoice.customer, company)
        attachment = (f"{invoice.invoice_number}.pdf", pdf_bytes, "application/pdf")

    subject = req.subject or f"Message from {company.name}"
    body_html = "<br>".join(html.escape(line) for line in req.message.splitlines())
    html_content = f"<p>{body_html}</p>" if body_html else "<p></p>"

    try:
        send_gmail_email(
            access_token=access_token,
            from_email=current_user.google_email or current_user.email,
            to_email=req.to_email,
            subject=subject,
            html_content=html_content,
            attachment=attachment,
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
