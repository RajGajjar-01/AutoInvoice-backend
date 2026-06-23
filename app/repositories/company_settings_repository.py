import uuid
from typing import Any

from sqlmodel import select

from app.models import CompanySettings
from app.repositories.base import BaseRepository
from app.schemas import CompanySettingsCreate


class CompanySettingsRepository(BaseRepository[CompanySettings]):
    model = CompanySettings

    async def get_by_owner(self, owner_id: uuid.UUID) -> CompanySettings | None:
        statement = select(CompanySettings).where(CompanySettings.owner_id == owner_id)
        result = await self.session.exec(statement)
        return result.first()

    async def create(
        self, settings_in: CompanySettingsCreate, owner_id: uuid.UUID
    ) -> CompanySettings:
        settings = CompanySettings.model_validate(settings_in, update={"owner_id": owner_id})
        return await self.add(settings)

    async def create_default(self, owner_id: uuid.UUID, name: str) -> CompanySettings:
        settings = CompanySettings(owner_id=owner_id, name=name)
        return await self.add(settings)

    async def update(self, settings: CompanySettings, update_data: dict[str, Any]) -> CompanySettings:
        settings.sqlmodel_update(update_data)
        return await self.add(settings)
