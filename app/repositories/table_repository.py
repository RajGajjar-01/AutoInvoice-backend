import uuid
from typing import Any

from sqlalchemy.orm import selectinload
from sqlmodel import col, func, select

from app.models import DataTable, TableReminder, TableRow
from app.repositories.base import BaseRepository
from app.schemas import DataTableCreate, TableReminderCreate, TableRowCreate


class TableRepository(BaseRepository[DataTable]):
    model = DataTable

    async def get_by_id_and_owner(
        self, table_id: uuid.UUID, owner_id: uuid.UUID
    ) -> DataTable | None:
        statement = select(DataTable).where(
            DataTable.id == table_id, DataTable.owner_id == owner_id
        )
        result = await self.session.exec(statement)
        return result.first()

    async def get_with_rows_and_reminders(
        self, table_id: uuid.UUID, owner_id: uuid.UUID
    ) -> DataTable | None:
        statement = (
            select(DataTable)
            .where(DataTable.id == table_id, DataTable.owner_id == owner_id)
            .options(selectinload(DataTable.rows), selectinload(DataTable.reminders))  # type: ignore[arg-type]
        )
        result = await self.session.exec(statement)
        return result.first()

    async def list_by_owner(
        self,
        owner_id: uuid.UUID,
        *,
        search: str | None,
        sort_by: str,
        sort_order: str,
        skip: int,
        limit: int,
    ) -> tuple[list[DataTable], int]:
        statement = select(DataTable).where(DataTable.owner_id == owner_id)
        if search:
            statement = statement.where(col(DataTable.name).ilike(f"%{search}%"))

        if sort_by == "name":
            statement = statement.order_by(
                col(DataTable.name).asc()
                if sort_order == "asc"
                else col(DataTable.name).desc()
            )
        else:
            statement = statement.order_by(
                col(DataTable.created_at).asc()
                if sort_order == "asc"
                else col(DataTable.created_at).desc()
            )

        count_statement = select(func.count()).select_from(statement.subquery())
        count_result = await self.session.exec(count_statement)
        total = count_result.one()

        statement = statement.offset(skip).limit(limit)
        result = await self.session.exec(statement)
        return list(result.all()), total

    async def create(self, table_in: DataTableCreate, owner_id: uuid.UUID) -> DataTable:
        table_data = table_in.model_dump()
        if table_data.get("columns") is not None:
            table_data["columns"] = [
                col.model_dump() if hasattr(col, "model_dump") else col
                for col in table_data["columns"]
            ]
        table = DataTable.model_validate(table_data, update={"owner_id": owner_id})
        return await self.add(table)

    async def update(self, table: DataTable, update_data: dict[str, Any]) -> DataTable:
        if update_data.get("columns") is not None:
            update_data["columns"] = [
                col.model_dump() if hasattr(col, "model_dump") else col
                for col in update_data["columns"]
            ]
        table.sqlmodel_update(update_data)
        return await self.add(table)

    async def duplicate(self, original: DataTable, owner_id: uuid.UUID) -> DataTable:
        columns = [
            col.model_dump() if hasattr(col, "model_dump") else col
            for col in (original.columns or [])
        ]
        new_table = DataTable(
            name=f"{original.name} (Copy)",
            description=original.description,
            columns=columns,
            owner_id=owner_id,
        )
        self.session.add(new_table)
        await self.session.flush()

        statement = select(TableRow).where(TableRow.table_id == original.id)
        result = await self.session.exec(statement)
        for original_row in result.all():
            self.session.add(TableRow(table_id=new_table.id, data=original_row.data))

        await self.session.commit()
        await self.session.refresh(new_table)
        return new_table

    async def add_row(self, table_id: uuid.UUID, row_in: TableRowCreate) -> TableRow:
        row = TableRow(table_id=table_id, data=row_in.data)
        self.session.add(row)
        await self.session.commit()
        await self.session.refresh(row)
        return row

    async def get_row(self, row_id: uuid.UUID) -> TableRow | None:
        return await self.session.get(TableRow, row_id)

    async def update_row(self, row: TableRow, data: dict[str, Any]) -> TableRow:
        row.data = data
        self.session.add(row)
        await self.session.commit()
        await self.session.refresh(row)
        return row

    async def delete_row(self, row: TableRow) -> None:
        await self.session.delete(row)
        await self.session.commit()

    async def bulk_delete_rows(
        self, table_id: uuid.UUID, row_ids: list[uuid.UUID]
    ) -> int:
        statement = select(TableRow).where(
            TableRow.table_id == table_id, col(TableRow.id).in_(row_ids)
        )
        result = await self.session.exec(statement)
        rows = result.all()
        for row in rows:
            await self.session.delete(row)
        await self.session.commit()
        return len(rows)

    async def add_reminder(
        self, table_id: uuid.UUID, reminder_in: TableReminderCreate
    ) -> TableReminder:
        reminder = TableReminder(
            table_id=table_id, reminder_data=reminder_in.reminder_data
        )
        self.session.add(reminder)
        await self.session.commit()
        await self.session.refresh(reminder)
        return reminder

    async def get_reminder(self, reminder_id: uuid.UUID) -> TableReminder | None:
        return await self.session.get(TableReminder, reminder_id)

    async def delete_reminder(self, reminder: TableReminder) -> None:
        await self.session.delete(reminder)
        await self.session.commit()
