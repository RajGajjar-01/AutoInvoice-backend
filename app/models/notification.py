import uuid
from datetime import datetime

from sqlalchemy import DateTime
from sqlmodel import Field, Relationship

from app.core.time import get_datetime_utc
from app.models.user import User
from app.schemas.notification import NotificationBase


class Notification(NotificationBase, table=True):
    __tablename__ = "notifications"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    owner_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, index=True, ondelete="CASCADE"
    )
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),
        index=True,
    )

    owner: User | None = Relationship(back_populates="notifications")
