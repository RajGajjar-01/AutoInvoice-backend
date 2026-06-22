import uuid
from datetime import datetime

from sqlalchemy import DateTime
from sqlmodel import Field, Relationship

from app.core.time import get_datetime_utc
from app.models.user import User
from app.schemas.table import DataTableBase, TableReminderBase, TableRowBase


class DataTable(DataTableBase, table=True):
    __tablename__ = "data_tables"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    owner_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, index=True, ondelete="CASCADE"
    )
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),
        index=True,
    )
    updated_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),
    )

    owner: User | None = Relationship(back_populates="data_tables")
    rows: list["TableRow"] = Relationship(
        back_populates="table",
        cascade_delete=True,
        sa_relationship_kwargs={"passive_deletes": True},
    )
    reminders: list["TableReminder"] = Relationship(
        back_populates="table",
        cascade_delete=True,
        sa_relationship_kwargs={"passive_deletes": True},
    )


class TableRow(TableRowBase, table=True):
    __tablename__ = "table_rows"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    table_id: uuid.UUID = Field(
        foreign_key="data_tables.id",
        nullable=False,
        index=True,
        ondelete="CASCADE",
    )
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),
        index=True,
    )

    table: DataTable | None = Relationship(back_populates="rows")


class TableReminder(TableReminderBase, table=True):
    __tablename__ = "table_reminders"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    table_id: uuid.UUID = Field(
        foreign_key="data_tables.id",
        nullable=False,
        index=True,
        ondelete="CASCADE",
    )
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),
    )

    table: DataTable | None = Relationship(back_populates="reminders")
