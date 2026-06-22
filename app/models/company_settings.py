import uuid
from datetime import datetime

from sqlalchemy import DateTime
from sqlmodel import Field, Relationship

from app.core.time import get_datetime_utc
from app.models.user import User
from app.schemas.company_settings import CompanySettingsBase


class CompanySettings(CompanySettingsBase, table=True):
    __tablename__ = "company_settings"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    owner_id: uuid.UUID = Field(
        foreign_key="user.id",
        nullable=False,
        unique=True,
        index=True,
        ondelete="CASCADE",
    )
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),
    )
    updated_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),
    )

    owner: User | None = Relationship(back_populates="company_settings")
