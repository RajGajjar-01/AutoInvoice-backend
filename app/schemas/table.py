import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


class DataTableColumn(SQLModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=500)
    type: str = Field(min_length=1, max_length=100)
    mandatory: bool = False
    options: list[str] = Field(default_factory=list)


class DataTableBase(SQLModel):
    name: str = Field(min_length=1, max_length=255, index=True)
    description: str | None = Field(default=None, max_length=500)
    columns: list[dict[str, Any]] = Field(sa_column=Column(JSONB, nullable=False))


class DataTableCreate(DataTableBase):
    columns: list[DataTableColumn]


class DataTableUpdate(SQLModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=500)
    columns: list[DataTableColumn] | None = None


class DataTablePublic(DataTableBase):
    id: uuid.UUID
    owner_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class TableRowBase(SQLModel):
    data: dict[str, Any] = Field(sa_column=Column(JSONB, nullable=False))


class TableRowCreate(TableRowBase):
    pass


class TableRowUpdate(TableRowBase):
    pass


class TableRowPublic(TableRowBase):
    id: uuid.UUID
    table_id: uuid.UUID
    created_at: datetime


class DataTableWithRows(DataTablePublic):
    rows: list["TableRowPublic"]
    reminders: list["TableReminderPublic"]


class TableReminderBase(SQLModel):
    reminder_data: dict[str, Any] = Field(sa_column=Column(JSONB, nullable=False))


class TableReminderCreate(TableReminderBase):
    pass


class TableReminderPublic(TableReminderBase):
    id: uuid.UUID
    table_id: uuid.UUID
    created_at: datetime
