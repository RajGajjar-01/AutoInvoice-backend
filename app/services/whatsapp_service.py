import base64
import re

import httpx

from app.core.config import settings


class InvalidPhoneError(ValueError):
    pass


def to_whatsapp_chat_id(phone: str, default_country_code: str | None = None) -> str:
    """Turn a phone number as users type it into a WhatsApp chat id.

    WhatsApp ids are the full international number, digits only, with
    "@c.us". Numbers saved without a country code (10 digits, or 11 with a
    leading trunk 0) get the default country code.
    """
    country_code = re.sub(
        r"\D", "", default_country_code or settings.DEFAULT_PHONE_COUNTRY_CODE
    )
    digits = re.sub(r"\D", "", phone or "")
    if digits.startswith("00"):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = country_code + digits[1:]
    elif len(digits) == 10:
        digits = country_code + digits
    if not 8 <= len(digits) <= 15:
        raise InvalidPhoneError(f"Not a valid phone number: {phone!r}")
    return f"{digits}@c.us"


class WhatsAppService:
    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        session_id: str | None = None,
    ) -> None:
        self.base_url = (base_url or settings.OPENWA_BASE_URL).rstrip("/")
        self.api_key = api_key or settings.OPENWA_API_KEY
        self.session_id = session_id or settings.OPENWA_SESSION_ID

    @property
    def is_configured(self) -> bool:
        """True when there is an OpenWA server to send through."""
        return bool(self.api_key and self.session_id)

    def _headers(self) -> dict[str, str]:
        return {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json",
        }

    def send_text(self, chat_id: str, text: str) -> dict:
        url = f"{self.base_url}/api/sessions/{self.session_id}/messages/send-text"
        payload = {"chatId": chat_id, "text": text}
        response = httpx.post(url, headers=self._headers(), json=payload, timeout=30)
        response.raise_for_status()
        return response.json()

    def send_document(
        self,
        chat_id: str,
        pdf_bytes: bytes,
        *,
        filename: str = "invoice.pdf",
        caption: str = "",
    ) -> dict:
        url = f"{self.base_url}/api/sessions/{self.session_id}/messages/send-document"
        payload = {
            "chatId": chat_id,
            "base64": base64.b64encode(pdf_bytes).decode("ascii"),
            "mimetype": "application/pdf",
            "filename": filename,
        }
        if caption:
            payload["caption"] = caption
        response = httpx.post(url, headers=self._headers(), json=payload, timeout=60)
        response.raise_for_status()
        return response.json()
