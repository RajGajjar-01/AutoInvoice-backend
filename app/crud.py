import uuid
from typing import Any

from sqlmodel import Session, select

from app.core.security import get_password_hash, verify_password
from app.core.time import get_datetime_utc
from app.models import Customer, DataTable, Invoice, Item, TableReminder, TableRow, User
from app.schemas import (
    CustomerCreate,
    CustomerUpdate,
    DataTableCreate,
    DataTableUpdate,
    InvoiceCreate,
    InvoiceUpdate,
    ItemCreate,
    TableReminderCreate,
    TableRowCreate,
    UserCreate,
    UserUpdate,
)


DUMMY_HASH = "$argon2id$v=19$m=65536,t=3,p=4$MjQyZWE1MzBjYjJlZTI0Yw$YTU4NGM5ZTZmYjE2NzZlZjY0ZWY3ZGRkY2U2OWFjNjk"


def create_user(*, session: Session, user_create: UserCreate) -> User:
    db_obj = User.model_validate(
        user_create, update={"hashed_password": get_password_hash(user_create.password)}
    )
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def update_user(*, session: Session, db_user: User, user_in: UserUpdate) -> User:
    user_data = user_in.model_dump(exclude_unset=True)
    if "password" in user_data:
        password = user_data.pop("password")
        user_data["hashed_password"] = get_password_hash(password)
    db_user.sqlmodel_update(user_data)
    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    return db_user


def get_user_by_email(*, session: Session, email: str) -> User | None:
    statement = select(User).where(User.email == email)
    return session.exec(statement).first()


def get_user_by_id(*, session: Session, user_id: uuid.UUID) -> User | None:
    return session.get(User, user_id)


def authenticate(*, session: Session, email: str, password: str) -> User | None:
    db_user = get_user_by_email(session=session, email=email)
    if not db_user:
        verify_password(password, DUMMY_HASH)
        return None
    verified, updated_password_hash = verify_password(password, db_user.hashed_password)
    if not verified:
        return None
    if updated_password_hash:
        db_user.hashed_password = updated_password_hash
        session.add(db_user)
        session.commit()
        session.refresh(db_user)
    return db_user


def create_item(*, session: Session, item_in: ItemCreate, owner_id: uuid.UUID) -> Item:
    db_item = Item.model_validate(item_in, update={"owner_id": owner_id})
    session.add(db_item)
    session.commit()
    session.refresh(db_item)
    return db_item


def validate_row_data(
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


def create_data_table(
    *, session: Session, table_in: DataTableCreate, owner_id: uuid.UUID
) -> DataTable:
    table_data = table_in.model_dump()
    if "columns" in table_data and table_data["columns"] is not None:
        table_data["columns"] = [
            col.model_dump() if hasattr(col, "model_dump") else col
            for col in table_data["columns"]
        ]
    db_table = DataTable.model_validate(table_data, update={"owner_id": owner_id})
    session.add(db_table)
    session.commit()
    session.refresh(db_table)
    return db_table


def get_table_by_id(
    *, session: Session, table_id: uuid.UUID, owner_id: uuid.UUID
) -> DataTable | None:
    statement = select(DataTable).where(
        DataTable.id == table_id, DataTable.owner_id == owner_id
    )
    return session.exec(statement).first()


def update_data_table(
    *, session: Session, db_table: DataTable, table_in: DataTableUpdate
) -> DataTable:
    table_data = table_in.model_dump(exclude_unset=True)

    if "columns" in table_data and table_data["columns"] is not None:
        table_data["columns"] = [
            col.model_dump() if hasattr(col, "model_dump") else col
            for col in table_data["columns"]
        ]

    table_data["updated_at"] = get_datetime_utc()

    db_table.sqlmodel_update(table_data)
    session.add(db_table)
    session.commit()
    session.refresh(db_table)
    return db_table


def delete_data_table(*, session: Session, db_table: DataTable) -> None:
    session.delete(db_table)
    session.commit()


def duplicate_data_table(
    *, session: Session, original_table: DataTable, owner_id: uuid.UUID
) -> DataTable:
    columns = [
        col.model_dump() if hasattr(col, "model_dump") else col
        for col in (original_table.columns or [])
    ]
    new_table = DataTable(
        name=f"{original_table.name} (Copy)",
        description=original_table.description,
        columns=columns,
        owner_id=owner_id,
    )
    session.add(new_table)
    session.flush()

    statement = select(TableRow).where(TableRow.table_id == original_table.id)
    original_rows = session.exec(statement).all()

    for original_row in original_rows:
        new_row = TableRow(table_id=new_table.id, data=original_row.data)
        session.add(new_row)

    session.commit()
    session.refresh(new_table)
    return new_table


def create_row(
    *, session: Session, table_id: uuid.UUID, row_in: TableRowCreate
) -> TableRow:
    db_row = TableRow(table_id=table_id, data=row_in.data)
    session.add(db_row)
    session.commit()
    session.refresh(db_row)
    return db_row


def update_row(
    *, session: Session, db_row: TableRow, row_data: dict[str, Any]
) -> TableRow:
    db_row.data = row_data
    session.add(db_row)
    session.commit()
    session.refresh(db_row)
    return db_row


def delete_row(*, session: Session, db_row: TableRow) -> None:
    session.delete(db_row)
    session.commit()


def bulk_delete_rows(
    *, session: Session, table_id: uuid.UUID, row_ids: list[uuid.UUID]
) -> int:
    from sqlmodel import col

    statement = select(TableRow).where(
        TableRow.table_id == table_id, col(TableRow.id).in_(row_ids)
    )
    rows = session.exec(statement).all()
    count = len(rows)
    for row in rows:
        session.delete(row)
    session.commit()
    return count


def create_reminder(
    *, session: Session, table_id: uuid.UUID, reminder_in: TableReminderCreate
) -> TableReminder:
    db_reminder = TableReminder(
        table_id=table_id,
        reminder_data=reminder_in.reminder_data,
    )
    session.add(db_reminder)
    session.commit()
    session.refresh(db_reminder)
    return db_reminder


def delete_reminder(*, session: Session, db_reminder: TableReminder) -> None:
    session.delete(db_reminder)
    session.commit()


def create_customer(
    *, session: Session, customer_in: CustomerCreate, owner_id: uuid.UUID
) -> Customer:
    db_customer = Customer.model_validate(customer_in, update={"owner_id": owner_id})
    session.add(db_customer)
    session.commit()
    session.refresh(db_customer)
    return db_customer


def get_customer_by_id(
    *, session: Session, customer_id: uuid.UUID, owner_id: uuid.UUID
) -> Customer | None:
    statement = select(Customer).where(
        Customer.id == customer_id,
        Customer.owner_id == owner_id,
    )
    return session.exec(statement).first()


def update_customer(
    *, session: Session, db_customer: Customer, customer_in: CustomerUpdate
) -> Customer:
    customer_data = customer_in.model_dump(exclude_unset=True)
    customer_data["updated_at"] = get_datetime_utc()
    db_customer.sqlmodel_update(customer_data)
    session.add(db_customer)
    session.commit()
    session.refresh(db_customer)
    return db_customer


def delete_customer(*, session: Session, db_customer: Customer) -> None:
    session.delete(db_customer)
    session.commit()


def create_invoice(
    *, session: Session, invoice_in: InvoiceCreate, owner_id: uuid.UUID
) -> Invoice:
    invoice_data = invoice_in.model_dump()
    invoice_data["items"] = [
        item.model_dump() if hasattr(item, "model_dump") else item
        for item in invoice_data.get("items", [])
    ]
    invoice_data["owner_id"] = owner_id
    db_invoice = Invoice(**invoice_data)
    session.add(db_invoice)
    session.commit()
    session.refresh(db_invoice)
    return db_invoice


def get_invoice_by_id(
    *, session: Session, invoice_id: uuid.UUID, owner_id: uuid.UUID
) -> Invoice | None:
    statement = select(Invoice).where(
        Invoice.id == invoice_id,
        Invoice.owner_id == owner_id,
    )
    return session.exec(statement).first()


def update_invoice(
    *, session: Session, db_invoice: Invoice, invoice_in: InvoiceUpdate
) -> Invoice:
    invoice_data = invoice_in.model_dump(exclude_unset=True)
    if "items" in invoice_data and invoice_data["items"] is not None:
        invoice_data["items"] = [
            item.model_dump() if hasattr(item, "model_dump") else item
            for item in invoice_data["items"]
        ]
    invoice_data["updated_at"] = get_datetime_utc()
    db_invoice.sqlmodel_update(invoice_data)
    session.add(db_invoice)
    session.commit()
    session.refresh(db_invoice)
    return db_invoice


def delete_invoice(*, session: Session, db_invoice: Invoice) -> None:
    session.delete(db_invoice)
    session.commit()
