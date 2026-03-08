import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from sqlmodel import Session, func, select

from app.api.deps import CurrentUser, SessionDep
from app.crud import (
    bulk_delete_rows,
    create_data_table,
    create_reminder,
    create_row,
    delete_data_table,
    delete_reminder,
    delete_row,
    duplicate_data_table,
    get_table_by_id,
    update_data_table,
    update_row,
    validate_row_data,
)
from app.models import (
    DataTable,
    DataTableCreate,
    DataTablePublic,
    DataTableUpdate,
    DataTableWithRows,
    PaginatedResponse,
    TableReminder,
    TableReminderCreate,
    TableReminderPublic,
    TableRow,
    TableRowCreate,
    TableRowPublic,
    TableRowUpdate,
)

router = APIRouter(prefix="/tables", tags=["tables"])


def get_table_or_404(
    session: Session, table_id: uuid.UUID, owner_id: uuid.UUID
) -> DataTable:
    """Get table and verify ownership. Raises 404 if not found or not owned."""
    table = get_table_by_id(session=session, table_id=table_id, owner_id=owner_id)

    if not table:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Table not found"
        )

    return table


@router.get("", response_model=PaginatedResponse[DataTablePublic])
def list_tables(
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    sort_by: str = Query("created_at", pattern="^(name|created_at)$"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    search: str | None = None,
) -> Any:
    """
    List all tables owned by the current user with pagination.
    
    - **skip**: Number of records to skip (default: 0)
    - **limit**: Number of records to return (default: 50, max: 100)
    - **sort_by**: Field to sort by (name or created_at)
    - **sort_order**: Sort direction (asc or desc)
    - **search**: Optional search term for table name
    """
    # Build query
    statement = select(DataTable).where(DataTable.owner_id == current_user.id)

    # Apply search filter
    if search:
        statement = statement.where(DataTable.name.ilike(f"%{search}%"))

    # Apply sorting
    if sort_by == "name":
        statement = statement.order_by(
            DataTable.name.asc() if sort_order == "asc" else DataTable.name.desc()
        )
    else:  # created_at
        statement = statement.order_by(
            DataTable.created_at.asc() if sort_order == "asc" else DataTable.created_at.desc()
        )

    # Get total count
    count_statement = select(func.count()).select_from(statement.subquery())
    total = session.exec(count_statement).one()

    # Apply pagination
    statement = statement.offset(skip).limit(limit)
    tables = session.exec(statement).all()

    return PaginatedResponse(
        data=list(tables),
        total=total,
        page=skip // limit + 1,
        page_size=limit,
        total_pages=(total + limit - 1) // limit
    )


@router.post("", response_model=DataTablePublic, status_code=status.HTTP_201_CREATED)
def create_table(
    session: SessionDep,
    current_user: CurrentUser,
    table_create: DataTableCreate,
) -> Any:
    """
    Create a new data table with column definitions.
    
    - **name**: Table name (1-255 characters)
    - **columns**: Array of column definitions
    """
    # Validate column names are unique
    column_names = [col.name for col in table_create.columns]
    if len(column_names) != len(set(column_names)):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Column names must be unique"
        )

    # Create table
    table = create_data_table(session=session, table_in=table_create, owner_id=current_user.id)
    return table


@router.get("/{table_id}", response_model=DataTableWithRows)
def get_table(
    session: SessionDep,
    current_user: CurrentUser,
    table_id: uuid.UUID,
) -> Any:
    """Get a specific table with all rows and reminders."""
    table = get_table_or_404(session, table_id, current_user.id)
    return table


@router.patch("/{table_id}", response_model=DataTablePublic)
def update_table(
    session: SessionDep,
    current_user: CurrentUser,
    table_id: uuid.UUID,
    table_update: DataTableUpdate,
) -> Any:
    """
    Update table name or column definitions.
    Only provided fields will be updated.
    """
    table = get_table_or_404(session, table_id, current_user.id)

    # Update table
    updated_table = update_data_table(session=session, db_table=table, table_in=table_update)
    return updated_table


@router.delete("/{table_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_table(
    session: SessionDep,
    current_user: CurrentUser,
    table_id: uuid.UUID,
) -> None:
    """Delete a table and all associated rows (cascade)."""
    table = get_table_or_404(session, table_id, current_user.id)

    delete_data_table(session=session, db_table=table)


@router.post("/{table_id}/duplicate", response_model=DataTablePublic)
def duplicate_table(
    session: SessionDep,
    current_user: CurrentUser,
    table_id: uuid.UUID,
) -> Any:
    """Duplicate a table with all its rows."""
    original_table = get_table_or_404(session, table_id, current_user.id)

    new_table = duplicate_data_table(
        session=session, original_table=original_table, owner_id=current_user.id
    )
    return new_table


# Row Endpoints

@router.post("/{table_id}/rows", response_model=TableRowPublic, status_code=status.HTTP_201_CREATED)
def create_table_row(
    session: SessionDep,
    current_user: CurrentUser,
    table_id: uuid.UUID,
    row_create: TableRowCreate,
) -> Any:
    """Add a new row to a table."""
    table = get_table_or_404(session, table_id, current_user.id)

    is_valid, missing = validate_row_data(table.columns, row_create.data)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Missing mandatory fields: {', '.join(missing)}",
        )

    # Create row
    row = create_row(session=session, table_id=table_id, row_in=row_create)
    return row


@router.put("/{table_id}/rows/{row_id}", response_model=TableRowPublic)
def update_table_row(
    session: SessionDep,
    current_user: CurrentUser,
    table_id: uuid.UUID,
    row_id: uuid.UUID,
    row_update: TableRowUpdate,
) -> Any:
    """Update a specific row's data."""
    # Verify table ownership
    table = get_table_or_404(session, table_id, current_user.id)

    # Get row
    row = session.get(TableRow, row_id)
    if not row or row.table_id != table_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Row not found"
        )

    # Validate mandatory fields
    is_valid, missing = validate_row_data(table.columns, row_update.data)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Missing mandatory fields: {', '.join(missing)}"
        )

    # Update row
    updated_row = update_row(session=session, db_row=row, row_data=row_update.data)
    return updated_row


@router.delete("/{table_id}/rows/{row_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_table_row(
    session: SessionDep,
    current_user: CurrentUser,
    table_id: uuid.UUID,
    row_id: uuid.UUID,
) -> None:
    """Delete a specific row."""
    # Verify table ownership
    table = get_table_or_404(session, table_id, current_user.id)

    # Get and delete row
    row = session.get(TableRow, row_id)
    if not row or row.table_id != table_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Row not found"
        )

    delete_row(session=session, db_row=row)


@router.post("/{table_id}/rows/bulk-delete")
def bulk_delete_table_rows(
    session: SessionDep,
    current_user: CurrentUser,
    table_id: uuid.UUID,
    row_ids: list[uuid.UUID],
) -> Any:
    """Delete multiple rows in a single transaction."""
    # Verify table ownership
    table = get_table_or_404(session, table_id, current_user.id)

    # Delete rows
    deleted_count = bulk_delete_rows(session=session, table_id=table_id, row_ids=row_ids)

    return {"deleted": deleted_count}


# Reminder Endpoints

@router.post("/{table_id}/reminders", response_model=TableReminderPublic, status_code=status.HTTP_201_CREATED)
def create_table_reminder(
    session: SessionDep,
    current_user: CurrentUser,
    table_id: uuid.UUID,
    reminder_create: TableReminderCreate,
) -> Any:
    """Create a reminder for a table."""
    # Verify table ownership
    table = get_table_or_404(session, table_id, current_user.id)

    # Create reminder
    reminder = create_reminder(
        session=session, table_id=table_id, reminder_in=reminder_create
    )
    return reminder


@router.delete("/{table_id}/reminders/{reminder_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_table_reminder(
    session: SessionDep,
    current_user: CurrentUser,
    table_id: uuid.UUID,
    reminder_id: uuid.UUID,
) -> None:
    """Delete a specific reminder."""
    # Verify table ownership
    table = get_table_or_404(session, table_id, current_user.id)

    # Get and delete reminder
    reminder = session.get(TableReminder, reminder_id)
    if not reminder or reminder.table_id != table_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reminder not found"
        )

    delete_reminder(session=session, db_reminder=reminder)
