import uuid
from typing import Any

from app.core.security import decrypt_field, encrypt_field
from app.core.time import get_datetime_utc
from app.exceptions import ConflictError, NotFoundError
from app.models import CompanySettings
from app.repositories.company_settings_repository import CompanySettingsRepository
from app.schemas import CompanySettingsCreate, CompanySettingsUpdate

ENCRYPTED_FIELDS = (
    "bank_account",
    "bank_ifsc",
    "pan",
    "upi_id",
    "smtp_password",
    "openwa_api_key",
    "openwa_session_id",
)


def _decrypt_model(settings: CompanySettings | None) -> CompanySettings | None:
    if not settings:
        return None
    for field in ENCRYPTED_FIELDS:
        val = getattr(settings, field, None)
        if val:
            setattr(settings, field, decrypt_field(settings.owner_id, val))
    return settings


def _encrypt_data(owner_id: uuid.UUID, data: dict[str, Any]) -> dict[str, Any]:
    encrypted = dict(data)
    for field in ENCRYPTED_FIELDS:
        if field in encrypted and encrypted[field] is not None:
            encrypted[field] = encrypt_field(owner_id, encrypted[field])
    return encrypted


class CompanySettingsService:
    def __init__(self, repo: CompanySettingsRepository) -> None:
        self.repo = repo

    async def get_for_owner(self, owner_id: uuid.UUID) -> CompanySettings:
        settings = await self.repo.get_by_owner(owner_id)
        if not settings:
            raise NotFoundError("Company settings not found")
        decrypted = _decrypt_model(settings)
        assert decrypted is not None
        return decrypted

    async def create(
        self, settings_in: CompanySettingsCreate, owner_id: uuid.UUID
    ) -> CompanySettings:
        existing = await self.repo.get_by_owner(owner_id)
        if existing:
            raise ConflictError("Company settings already exist")
        data = settings_in.model_dump()
        encrypted_data = _encrypt_data(owner_id, data)
        encrypted_in = CompanySettingsCreate(**encrypted_data)
        saved = await self.repo.create(encrypted_in, owner_id)
        decrypted = _decrypt_model(saved)
        assert decrypted is not None
        return decrypted

    async def upsert(
        self, owner_id: uuid.UUID, settings_in: CompanySettingsUpdate
    ) -> CompanySettings:
        settings = await self.repo.get_by_owner(owner_id)
        if not settings:
            settings = await self.repo.create_default(
                owner_id, settings_in.name or "My Company"
            )
        update_data = settings_in.model_dump(exclude_unset=True)
        encrypted_update = _encrypt_data(owner_id, update_data)
        encrypted_update["updated_at"] = get_datetime_utc()
        saved = await self.repo.update(settings, encrypted_update)
        decrypted = _decrypt_model(saved)
        assert decrypted is not None
        return decrypted

    async def delete(self, owner_id: uuid.UUID) -> None:
        settings = await self.get_for_owner(owner_id)
        await self.repo.delete(settings)
