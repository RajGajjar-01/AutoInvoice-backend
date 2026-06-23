import uuid

from app.core.time import get_datetime_utc
from app.exceptions import ConflictError, NotFoundError
from app.models import CompanySettings
from app.repositories.company_settings_repository import CompanySettingsRepository
from app.schemas import CompanySettingsCreate, CompanySettingsUpdate


class CompanySettingsService:
    def __init__(self, repo: CompanySettingsRepository) -> None:
        self.repo = repo

    async def get_for_owner(self, owner_id: uuid.UUID) -> CompanySettings:
        settings = await self.repo.get_by_owner(owner_id)
        if not settings:
            raise NotFoundError("Company settings not found")
        return settings

    async def create(
        self, settings_in: CompanySettingsCreate, owner_id: uuid.UUID
    ) -> CompanySettings:
        existing = await self.repo.get_by_owner(owner_id)
        if existing:
            raise ConflictError("Company settings already exist")
        return await self.repo.create(settings_in, owner_id)

    async def upsert(
        self, owner_id: uuid.UUID, settings_in: CompanySettingsUpdate
    ) -> CompanySettings:
        settings = await self.repo.get_by_owner(owner_id)
        if not settings:
            settings = await self.repo.create_default(
                owner_id, settings_in.name or "My Company"
            )
        update_data = settings_in.model_dump(exclude_unset=True)
        update_data["updated_at"] = get_datetime_utc()
        return await self.repo.update(settings, update_data)

    async def delete(self, owner_id: uuid.UUID) -> None:
        settings = await self.get_for_owner(owner_id)
        await self.repo.delete(settings)
