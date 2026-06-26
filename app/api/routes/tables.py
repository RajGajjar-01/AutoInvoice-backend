import uuid
from typing import Any

from fastapi import APIRouter, Query, status
from pydantic import BaseModel

from app.api.deps import CurrentUser, TableServiceDep
from app.schemas import (
    DataTableCreate,
    DataTablePublic,
    DataTableUpdate,
    DataTableWithRows,
    PaginatedResponse,
    TableReminderCreate,
    TableReminderPublic,
    TableRowCreate,
    TableRowPublic,
    TableRowUpdate,
)

router = APIRouter(prefix="/tables", tags=["tables"])


@router.get("", response_model=PaginatedResponse[DataTablePublic])
async def list_tables(
    current_user: CurrentUser,
    table_service: TableServiceDep,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    sort_by: str = Query("created_at", pattern="^(name|created_at)$"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    search: str | None = None,
) -> Any:
    tables, total = await table_service.list_items(
        current_user.id,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
        skip=skip,
        limit=limit,
    )
    return PaginatedResponse(
        data=list(tables),
        total=total,
        page=skip // limit + 1,
        page_size=limit,
        total_pages=(total + limit - 1) // limit,
    )


@router.post("", response_model=DataTablePublic, status_code=status.HTTP_201_CREATED)
async def create_table(
    current_user: CurrentUser,
    table_service: TableServiceDep,
    table_create: DataTableCreate,
) -> Any:
    return await table_service.create(table_create, current_user.id)


@router.get("/{table_id}", response_model=DataTableWithRows)
async def get_table(
    current_user: CurrentUser,
    table_service: TableServiceDep,
    table_id: uuid.UUID,
) -> Any:
    return await table_service.get_table_with_rows(table_id, current_user.id)


@router.patch("/{table_id}", response_model=DataTablePublic)
async def update_table(
    current_user: CurrentUser,
    table_service: TableServiceDep,
    table_id: uuid.UUID,
    table_update: DataTableUpdate,
) -> Any:
    return await table_service.update(table_id, current_user.id, table_update)


@router.delete("/{table_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_table(
    current_user: CurrentUser,
    table_service: TableServiceDep,
    table_id: uuid.UUID,
) -> None:
    await table_service.delete(table_id, current_user.id)


@router.post("/{table_id}/duplicate", response_model=DataTablePublic)
async def duplicate_table(
    current_user: CurrentUser,
    table_service: TableServiceDep,
    table_id: uuid.UUID,
) -> Any:
    return await table_service.duplicate(table_id, current_user.id)


@router.post("/{table_id}/rows", response_model=TableRowPublic, status_code=status.HTTP_201_CREATED)
async def create_table_row(
    current_user: CurrentUser,
    table_service: TableServiceDep,
    table_id: uuid.UUID,
    row_create: TableRowCreate,
) -> Any:
    return await table_service.add_row(table_id, current_user.id, row_create)


@router.put("/{table_id}/rows/{row_id}", response_model=TableRowPublic)
async def update_table_row(
    current_user: CurrentUser,
    table_service: TableServiceDep,
    table_id: uuid.UUID,
    row_id: uuid.UUID,
    row_update: TableRowUpdate,
) -> Any:
    return await table_service.update_row(table_id, current_user.id, row_id, row_update)


@router.delete("/{table_id}/rows/{row_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_table_row(
    current_user: CurrentUser,
    table_service: TableServiceDep,
    table_id: uuid.UUID,
    row_id: uuid.UUID,
) -> None:
    await table_service.delete_row(table_id, current_user.id, row_id)


class BulkDeleteResponse(BaseModel):
    deleted: int


@router.post("/{table_id}/rows/bulk-delete", response_model=BulkDeleteResponse)
async def bulk_delete_table_rows(
    current_user: CurrentUser,
    table_service: TableServiceDep,
    table_id: uuid.UUID,
    row_ids: list[uuid.UUID],
) -> Any:
    deleted = await table_service.bulk_delete_rows(table_id, current_user.id, row_ids)
    return BulkDeleteResponse(deleted=deleted)


@router.post(
    "/{table_id}/reminders",
    response_model=TableReminderPublic,
    status_code=status.HTTP_201_CREATED,
)
async def create_table_reminder(
    current_user: CurrentUser,
    table_service: TableServiceDep,
    table_id: uuid.UUID,
    reminder_create: TableReminderCreate,
) -> Any:
    return await table_service.add_reminder(table_id, current_user.id, reminder_create)


@router.delete(
    "/{table_id}/reminders/{reminder_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_table_reminder(
    current_user: CurrentUser,
    table_service: TableServiceDep,
    table_id: uuid.UUID,
    reminder_id: uuid.UUID,
) -> None:
    await table_service.delete_reminder(table_id, current_user.id, reminder_id)
