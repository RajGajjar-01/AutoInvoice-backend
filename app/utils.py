import io
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import emails
import jwt
from jwt.exceptions import InvalidTokenError
from openpyxl import load_workbook
from string import Template

from app.core import security
from app.core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class EmailData:
    html_content: str
    subject: str


def render_email_template(*, template_name: str, context: dict[str, Any]) -> str:
    template_str = (
        Path(__file__).parent / "email-templates" / "build" / template_name
    ).read_text()
    html_content = Template(template_str).safe_substitute(context)
    return html_content


def send_email(
    *,
    email_to: str,
    subject: str = "",
    html_content: str = "",
) -> None:
    assert settings.emails_enabled, "no provided configuration for email variables"
    message = emails.Message(
        subject=subject,
        html=html_content,
        mail_from=(settings.EMAILS_FROM_NAME, settings.EMAILS_FROM_EMAIL),
    )
    smtp_options = {"host": settings.SMTP_HOST, "port": settings.SMTP_PORT}
    if settings.SMTP_TLS:
        smtp_options["tls"] = True
    elif settings.SMTP_SSL:
        smtp_options["ssl"] = True
    if settings.SMTP_USER:
        smtp_options["user"] = settings.SMTP_USER
    if settings.SMTP_PASSWORD:
        smtp_options["password"] = settings.SMTP_PASSWORD
    response = message.send(to=email_to, smtp=smtp_options)
    logger.info(f"send email result: {response}")


def generate_test_email(email_to: str) -> EmailData:
    project_name = settings.PROJECT_NAME
    subject = f"{project_name} - Test email"
    html_content = render_email_template(
        template_name="test_email.html",
        context={"project_name": settings.PROJECT_NAME, "email": email_to},
    )
    return EmailData(html_content=html_content, subject=subject)


def generate_reset_password_email(email_to: str, email: str, token: str) -> EmailData:
    project_name = settings.PROJECT_NAME
    subject = f"{project_name} - Password recovery for user {email}"
    link = f"{settings.FRONTEND_HOST}/reset-password?token={token}"
    html_content = render_email_template(
        template_name="reset_password.html",
        context={
            "project_name": settings.PROJECT_NAME,
            "username": email,
            "email": email_to,
            "valid_hours": settings.EMAIL_RESET_TOKEN_EXPIRE_HOURS,
            "link": link,
        },
    )
    return EmailData(html_content=html_content, subject=subject)


def generate_new_account_email(
    email_to: str, username: str, password: str | None = None
) -> EmailData:
    project_name = settings.PROJECT_NAME
    subject = f"{project_name} - New account for user {username}"
    html_content = render_email_template(
        template_name="new_account.html",
        context={
            "project_name": settings.PROJECT_NAME,
            "username": username,
            "password": password,
            "email": email_to,
            "link": settings.FRONTEND_HOST,
        },
    )
    return EmailData(html_content=html_content, subject=subject)


def generate_password_reset_token(email: str) -> str:
    delta = timedelta(hours=settings.EMAIL_RESET_TOKEN_EXPIRE_HOURS)
    now = datetime.now(timezone.utc)
    expires = now + delta
    exp = expires.timestamp()
    encoded_jwt = jwt.encode(
        {"exp": exp, "nbf": now, "sub": email},
        settings.SECRET_KEY,
        algorithm=security.ALGORITHM,
    )
    return encoded_jwt


def verify_password_reset_token(token: str) -> str | None:
    try:
        decoded_token = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[security.ALGORITHM]
        )
        return str(decoded_token["sub"])
    except InvalidTokenError:
        return None


COLUMN_MAPPING = {
    "item_name": [
        "item",
        "description",
        "product",
        "name",
        "item name",
        "item description",
        "product name",
        "service",
        "item/service",
    ],
    "quantity": [
        "qty",
        "quantity",
        "pieces",
        "units",
        "pcs",
        "pieces",
        "quantity pcs",
        "num",
        "number of items",
    ],
    "price": [
        "rate",
        "price",
        "unit price",
        "unit price rs",
        "amount",
        "unit rate",
        "price per unit",
        "price/unit",
        "rate per unit",
    ],
    "line_total": [
        "line total",
        "line amount",
        "total",
        "subtotal",
        "amount",
        "total amount",
        "line total amount",
        "total amount rs",
    ],
    "tax": [
        "tax",
        "gst",
        "vat",
        "tax rate",
        "gst %",
        "tax %",
        "tax amount",
        "cgst",
        "sgst",
        "igst",
        "tax rs",
    ],
    "invoice_number": [
        "invoice",
        "invoice number",
        "invoice #",
        "inv no",
        "inv number",
        "inv #",
        "invoice no",
        "number",
        "invoiceid",
    ],
    "invoice_date": [
        "date",
        "invoice date",
        "date of invoice",
        "inv date",
        "invoice dt",
        "invoice date dt",
    ],
    "customer_name": [
        "customer",
        "client",
        "bill to",
        "customer name",
        "client name",
        "party name",
        "buyer",
        "customer name/bill to",
    ],
    "customer_gst": ["customer gst", "gstin", "client gst", "buyer gst", "gstin no"],
    "customer_address": [
        "address",
        "bill to address",
        "billing address",
        "customer address",
        "party address",
    ],
}


def parse_excel_file(file_content: bytes) -> dict[str, Any]:
    try:
        wb = load_workbook(io.BytesIO(file_content), data_only=True)
        ws = wb.active

        if ws.max_row < 1:
            return {"error": "Excel file is empty", "columns": [], "data": []}

        headers = []
        for cell in ws[1]:
            value = cell.value
            if value is not None:
                headers.append(str(value).strip())
            else:
                headers.append("")

        column_mapping = {}
        excel_columns = []

        for idx, header in enumerate(headers, start=1):
            if not header:
                continue
            header_lower = header.lower()

            matched_field = None
            for field, variants in COLUMN_MAPPING.items():
                for variant in variants:
                    if variant in header_lower:
                        matched_field = field
                        break
                if matched_field:
                    break

            excel_columns.append(
                {
                    "index": idx,
                    "name": header,
                    "mapped_to": matched_field,
                }
            )
            if matched_field:
                column_mapping[matched_field] = idx

        rows = []
        max_data_rows = min(ws.max_row - 1, 100)

        for row_idx in range(2, max_data_rows + 2):
            row_data = {}
            has_data = False
            for col_idx, _header in enumerate(headers, start=1):
                cell_value = ws.cell(row=row_idx, column=col_idx).value
                if cell_value is not None and str(cell_value).strip():
                    has_data = True
                row_data[f"col_{col_idx}"] = cell_value

            if has_data:
                rows.append(row_data)

        return {
            "columns": excel_columns,
            "column_mapping": column_mapping,
            "data": rows[:50],
            "total_rows": ws.max_row - 1,
        }

    except Exception as e:
        logger.error(f"Error parsing Excel file: {e}")
        return {"error": str(e), "columns": [], "data": []}
