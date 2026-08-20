import uuid
from unittest.mock import AsyncMock, MagicMock
import pytest

from app.core.security import encrypt_field
from app.main import _scrub_sentry_event
from app.models import CompanySettings
from app.schemas.company_settings import (
    CompanySettingsCreate,
    CompanySettingsPublic,
    CompanySettingsUpdate,
)
from app.services.company_settings_service import CompanySettingsService


class TestCompanySettingsEncryptionService:
    @pytest.mark.anyio
    async def test_create_encrypts_and_decrypts(self):
        owner_id = uuid.uuid4()
        repo = MagicMock()

        # Mock repo.get_by_owner returns None on first call (no existing settings)
        repo.get_by_owner = AsyncMock(return_value=None)

        # Mock repo.create to store the model as passed (with encrypted fields) and return it
        async def mock_repo_create(settings_in, owner_id):
            model = CompanySettings.model_validate(settings_in, update={"owner_id": owner_id})
            return model

        repo.create = AsyncMock(side_effect=mock_repo_create)

        service = CompanySettingsService(repo)
        create_payload = CompanySettingsCreate(
            name="Secure Enterprise Ltd",
            gstin="22AAAAA0000A1Z5",
            pan="ABCDE1234F",
            bank_account="123456789012",
            bank_ifsc="SBIN0001234",
            upi_id="business@okaxis",
            smtp_password="super_secret_smtp_password",
            openwa_api_key="whatsapp_secret_key_123",
        )

        result = await service.create(create_payload, owner_id)

        # Verify that repo.create received encrypted data
        call_args = repo.create.call_args[0]
        passed_in = call_args[0]
        assert passed_in.bank_account.startswith("v1:")
        assert passed_in.bank_ifsc.startswith("v1:")
        assert passed_in.pan.startswith("v1:")
        assert passed_in.upi_id.startswith("v1:")
        assert passed_in.smtp_password.startswith("v1:")
        assert passed_in.openwa_api_key.startswith("v1:")

        # Verify that returned service object has transparently decrypted values
        assert result.bank_account == "123456789012"
        assert result.bank_ifsc == "SBIN0001234"
        assert result.pan == "ABCDE1234F"
        assert result.upi_id == "business@okaxis"
        assert result.smtp_password == "super_secret_smtp_password"
        assert result.openwa_api_key == "whatsapp_secret_key_123"

        # Verify that CompanySettingsPublic excludes secrets
        pub = CompanySettingsPublic.from_model(result)
        dump = pub.model_dump()
        assert "smtp_password" not in dump
        assert "openwa_api_key" not in dump
        assert dump["smtp_password_set"] is True
        assert dump["openwa_api_key_set"] is True

    @pytest.mark.anyio
    async def test_get_for_owner_decrypts(self):
        owner_id = uuid.uuid4()
        repo = MagicMock()

        raw_model = CompanySettings(
            owner_id=owner_id,
            name="Stored Corp",
            bank_account=encrypt_field(owner_id, "987654321098"),
            bank_ifsc=encrypt_field(owner_id, "HDFC0001234"),
            pan=encrypt_field(owner_id, "WXYZP9876Q"),
            smtp_password=encrypt_field(owner_id, "mail_secret_99"),
        )
        repo.get_by_owner = AsyncMock(return_value=raw_model)

        service = CompanySettingsService(repo)
        decrypted = await service.get_for_owner(owner_id)

        assert decrypted.bank_account == "987654321098"
        assert decrypted.bank_ifsc == "HDFC0001234"
        assert decrypted.pan == "WXYZP9876Q"
        assert decrypted.smtp_password == "mail_secret_99"


class TestSentryPIIScrubber:
    def test_scrub_sentry_event_redacts_sensitive_fields(self):
        event = {
            "request": {
                "headers": {
                    "Authorization": "Bearer sensitive_token_123",
                    "Cookie": "access_token=xyz; refresh_token=abc",
                    "Content-Type": "application/json",
                },
                "data": {
                    "name": "Test User",
                    "bank_account": "123456789012",
                    "smtp_password": "super_secret_pass",
                    "nested": {
                        "api_key": "secret_key_abc",
                        "public_field": "hello",
                    },
                },
                "cookies": {
                    "session_cookie": "secret_cookie_data",
                },
            },
            "extra": {
                "user_token": "token_value",
                "normal_extra": "safe",
            },
        }

        scrubbed = _scrub_sentry_event(event, {})
        assert scrubbed is not None

        req = scrubbed["request"]
        assert req["headers"]["Authorization"] == "[REDACTED]"
        assert req["headers"]["Cookie"] == "[REDACTED]"
        assert req["headers"]["Content-Type"] == "application/json"

        assert req["data"]["name"] == "Test User"
        assert req["data"]["bank_account"] == "[REDACTED]"
        assert req["data"]["smtp_password"] == "[REDACTED]"
        assert req["data"]["nested"]["api_key"] == "[REDACTED]"
        assert req["data"]["nested"]["public_field"] == "hello"

        assert req["cookies"]["session_cookie"] == "[REDACTED]"
        assert scrubbed["extra"]["user_token"] == "[REDACTED]"
        assert scrubbed["extra"]["normal_extra"] == "safe"
