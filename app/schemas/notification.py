import uuid
from datetime import datetime
from enum import Enum

from sqlmodel import Field, SQLModel


class NotificationType(str, Enum):
    reminder = "reminder"
    due_date = "due_date"
    expiry = "expiry"
    info = "info"


class NotificationBase(SQLModel):
    type: NotificationType = NotificationType.info
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    table_id: uuid.UUID | None = None
    table_name: str | None = Field(default=None, max_length=255)
    row_id: uuid.UUID | None = None
    row_label: str | None = Field(default=None, max_length=255)
    read: bool = False
    scheduled_for: datetime | None = None


class NotificationCreate(NotificationBase):
    pass


class NotificationUpdate(SQLModel):
    read: bool | None = None


class NotificationPublic(NotificationBase):
    id: uuid.UUID
    owner_id: uuid.UUID
    created_at: datetime


class NotificationsPublic(SQLModel):
    data: list[NotificationPublic]
    count: int
    unread_count: int
