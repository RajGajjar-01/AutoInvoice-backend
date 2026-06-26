import base64
import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


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
