import uuid
from typing import Any

from app.core.time import get_datetime_utc
from app.exceptions import NotFoundError, ValidationError
from app.models import DataTable, TableReminder, TableRow
from app.repositories.table_repository import TableRepository
from app.schemas import (
    DataTableCreate,
    DataTableUpdate,
    TableReminderCreate,
    TableRowCreate,
    TableRowUpdate,
)


def _validate_row_data(
    columns: list[Any], row_data: dict[str, Any]
) -> tuple[bool, list[str]]:
    missing_fields = []
    for column in columns:
        if isinstance(column, dict):
            mandatory = column.get("mandatory", False)
            col_name = column.get("name")
        else:
            mandatory = bool(getattr(column, "mandatory", False))
            col_name = getattr(column, "name", None)

        if mandatory and col_name:
            if (
                col_name not in row_data
                or row_data[col_name] is None
                or row_data[col_name] == ""
            ):
                missing_fields.append(col_name)
    return (len(missing_fields) == 0, missing_fields)


class TableService:
    def __init__(self, repo: TableRepository) -> None:
        self.repo = repo

    async def get_owned_table(
        self, table_id: uuid.UUID, owner_id: uuid.UUID
    ) -> DataTable:
        table = await self.repo.get_by_id_and_owner(table_id, owner_id)
        if not table:
            raise NotFoundError("Table not found")
        return table

    async def get_table_with_rows(
        self, table_id: uuid.UUID, owner_id: uuid.UUID
    ) -> DataTable:
        table = await self.repo.get_with_rows_and_reminders(table_id, owner_id)
        if not table:
            raise NotFoundError("Table not found")
        return table

    async def list_items(
        self,
        owner_id: uuid.UUID,
        *,
        search: str | None,
        sort_by: str,
        sort_order: str,
        skip: int,
        limit: int,
    ) -> tuple[list[DataTable], int]:
        return await self.repo.list_by_owner(
            owner_id,
            search=search,
            sort_by=sort_by,
            sort_order=sort_order,
            skip=skip,
            limit=limit,
        )

    async def create(self, table_in: DataTableCreate, owner_id: uuid.UUID) -> DataTable:
        column_names = [col.name for col in table_in.columns]
        if len(column_names) != len(set(column_names)):
            raise ValidationError("Column names must be unique")
        return await self.repo.create(table_in, owner_id)

    async def update(
        self, table_id: uuid.UUID, owner_id: uuid.UUID, table_in: DataTableUpdate
    ) -> DataTable:
        table = await self.get_owned_table(table_id, owner_id)
        update_data = table_in.model_dump(exclude_unset=True)
        update_data["updated_at"] = get_datetime_utc()
        return await self.repo.update(table, update_data)

    async def delete(self, table_id: uuid.UUID, owner_id: uuid.UUID) -> None:
        table = await self.get_owned_table(table_id, owner_id)
        await self.repo.delete(table)

    async def duplicate(self, table_id: uuid.UUID, owner_id: uuid.UUID) -> DataTable:
        table = await self.get_owned_table(table_id, owner_id)
        return await self.repo.duplicate(table, owner_id)

    async def add_row(
        self, table_id: uuid.UUID, owner_id: uuid.UUID, row_in: TableRowCreate
    ) -> TableRow:
        table = await self.get_owned_table(table_id, owner_id)
        is_valid, missing = _validate_row_data(table.columns, row_in.data)
        if not is_valid:
            raise ValidationError(f"Missing mandatory fields: {', '.join(missing)}")
        return await self.repo.add_row(table_id, row_in)

    async def update_row(
        self,
        table_id: uuid.UUID,
        owner_id: uuid.UUID,
        row_id: uuid.UUID,
        row_in: TableRowUpdate,
    ) -> TableRow:
        table = await self.get_owned_table(table_id, owner_id)
        row = await self.repo.get_row(row_id)
        if not row or row.table_id != table_id:
            raise NotFoundError("Row not found")
        is_valid, missing = _validate_row_data(table.columns, row_in.data)
        if not is_valid:
            raise ValidationError(f"Missing mandatory fields: {', '.join(missing)}")
        return await self.repo.update_row(row, row_in.data)

    async def delete_row(
        self, table_id: uuid.UUID, owner_id: uuid.UUID, row_id: uuid.UUID
    ) -> None:
        await self.get_owned_table(table_id, owner_id)
        row = await self.repo.get_row(row_id)
        if not row or row.table_id != table_id:
            raise NotFoundError("Row not found")
        await self.repo.delete_row(row)

    async def bulk_delete_rows(
        self, table_id: uuid.UUID, owner_id: uuid.UUID, row_ids: list[uuid.UUID]
    ) -> int:
        await self.get_owned_table(table_id, owner_id)
        return await self.repo.bulk_delete_rows(table_id, row_ids)

    async def add_reminder(
        self, table_id: uuid.UUID, owner_id: uuid.UUID, reminder_in: TableReminderCreate
    ) -> TableReminder:
        await self.get_owned_table(table_id, owner_id)
        return await self.repo.add_reminder(table_id, reminder_in)

    async def delete_reminder(
        self, table_id: uuid.UUID, owner_id: uuid.UUID, reminder_id: uuid.UUID
    ) -> None:
        await self.get_owned_table(table_id, owner_id)
        reminder = await self.repo.get_reminder(reminder_id)
        if not reminder or reminder.table_id != table_id:
            raise NotFoundError("Reminder not found")
        await self.repo.delete_reminder(reminder)
