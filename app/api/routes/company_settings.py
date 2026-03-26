import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlmodel import select

from app.api.deps import CurrentUser, SessionDep
from app.models import (
    CompanySettings,
    CompanySettingsCreate,
    CompanySettingsPublic,
    CompanySettingsUpdate,
    Message,
    get_datetime_utc,
)

router = APIRouter(prefix="/company-settings", tags=["company-settings"])


@router.get("/", response_model=CompanySettingsPublic)
def get_company_settings(session: SessionDep, current_user: CurrentUser) -> Any:
    """Get company settings for the current user."""
    statement = select(CompanySettings).where(
        CompanySettings.owner_id == current_user.id
    )
    settings = session.exec(statement).first()

    if not settings:
        raise HTTPException(status_code=404, detail="Company settings not found")

    return settings


@router.post("/", response_model=CompanySettingsPublic)
def create_company_settings(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    settings_in: CompanySettingsCreate,
) -> Any:
    """Create company settings for the current user."""
    existing = session.exec(
        select(CompanySettings).where(CompanySettings.owner_id == current_user.id)
    ).first()

    if existing:
        raise HTTPException(status_code=400, detail="Company settings already exist")

    settings = CompanySettings.model_validate(
        settings_in, update={"owner_id": current_user.id}
    )
    session.add(settings)
    session.commit()
    session.refresh(settings)
    return settings


@router.put("/", response_model=CompanySettingsPublic)
def update_company_settings(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    settings_in: CompanySettingsUpdate,
) -> Any:
    """Update company settings for the current user."""
    statement = select(CompanySettings).where(
        CompanySettings.owner_id == current_user.id
    )
    settings = session.exec(statement).first()

    if not settings:
        settings = CompanySettings(
            owner_id=current_user.id,
            name=settings_in.name or "My Company",
        )
        session.add(settings)
        session.commit()
        session.refresh(settings)

    update_dict = settings_in.model_dump(exclude_unset=True)
    update_dict["updated_at"] = get_datetime_utc()
    settings.sqlmodel_update(update_dict)
    session.add(settings)
    session.commit()
    session.refresh(settings)
    return settings


@router.delete("/", response_model=Message)
def delete_company_settings(session: SessionDep, current_user: CurrentUser) -> Any:
    """Delete company settings for the current user."""
    statement = select(CompanySettings).where(
        CompanySettings.owner_id == current_user.id
    )
    settings = session.exec(statement).first()

    if not settings:
        raise HTTPException(status_code=404, detail="Company settings not found")

    session.delete(settings)
    session.commit()
    return Message(message="Company settings deleted successfully")
