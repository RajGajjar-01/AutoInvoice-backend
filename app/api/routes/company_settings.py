from typing import Any

from fastapi import APIRouter

from app.api.deps import CompanySettingsServiceDep, CurrentUser
from app.schemas import (
    CompanySettingsCreate,
    CompanySettingsPublic,
    CompanySettingsUpdate,
)

router = APIRouter(prefix="/company-settings", tags=["company-settings"])


@router.get("/", response_model=CompanySettingsPublic)
async def get_company_settings(
    current_user: CurrentUser, company_settings_service: CompanySettingsServiceDep
) -> Any:
    return await company_settings_service.get_for_owner(current_user.id)


@router.post("/", response_model=CompanySettingsPublic, status_code=201)
async def create_company_settings(
    *,
    current_user: CurrentUser,
    company_settings_service: CompanySettingsServiceDep,
    settings_in: CompanySettingsCreate,
) -> Any:
    return await company_settings_service.create(settings_in, current_user.id)


@router.put("/", response_model=CompanySettingsPublic)
async def update_company_settings(
    *,
    current_user: CurrentUser,
    company_settings_service: CompanySettingsServiceDep,
    settings_in: CompanySettingsUpdate,
) -> Any:
    return await company_settings_service.upsert(current_user.id, settings_in)


@router.delete("/", status_code=204)
async def delete_company_settings(
    current_user: CurrentUser, company_settings_service: CompanySettingsServiceDep
) -> None:
    await company_settings_service.delete(current_user.id)
