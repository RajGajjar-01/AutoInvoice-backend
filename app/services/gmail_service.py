import base64
import logging
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

import httpx

logger = logging.getLogger(__name__)

GMAIL_SEND_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"


def send_email(
    *,
    access_token: str,
    from_email: str,
    to_email: str,
    subject: str,
    html_content: str,
    attachment: tuple[str, bytes, str] | None = None,
) -> dict[str, Any]:
    message = MIMEMultipart("mixed")
    message["To"] = to_email
    message["From"] = from_email
    message["Subject"] = subject
    message.attach(MIMEText(html_content, "html"))

    if attachment:
        filename, data, content_type = attachment
        _, _, subtype = content_type.partition("/")
        part = MIMEApplication(data, _subtype=subtype or "octet-stream")
        part.add_header("Content-Disposition", "attachment", filename=filename)
        message.attach(part)

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")
    response = httpx.post(
        GMAIL_SEND_URL,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        json={"raw": raw},
        timeout=30,
    )
    response.raise_for_status()
    result: dict[str, Any] = response.json()
    logger.info(f"gmail send result: {result}")
    return result
