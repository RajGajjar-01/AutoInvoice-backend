import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from sqlmodel import col, func, select

from app.api.deps import CurrentUser, SessionDep
from app.core.time import get_datetime_utc
from app.models import Item
from app.schemas import ItemCreate, ItemPublic, ItemsPublic, ItemUpdate, Message

router = APIRouter(prefix="/items", tags=["items"])


@router.get("/", response_model=ItemsPublic)
def read_items(
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    search: str | None = None,
    category: str | None = None,
    stock_status: str | None = Query(
        None, pattern="^(in_stock|low_stock|out_of_stock)$"
    ),
) -> Any:
    """
    Retrieve items with optional filters.

    - **search**: Search by name, description, or SKU
    - **category**: Filter by category
    - **stock_status**: Filter by stock status (in_stock, low_stock, out_of_stock)
    """
    base_filter = Item.owner_id == current_user.id

    if search:
        search_term = f"%{search}%"
        base_filter = (
            (Item.name.ilike(search_term))
            | (Item.description.ilike(search_term))
            | (Item.sku.ilike(search_term))
        ) & (Item.owner_id == current_user.id)

    if category:
        base_filter = base_filter & (Item.category == category)

    if stock_status == "in_stock":
        base_filter = base_filter & (Item.stock >= Item.low_stock_threshold)
    elif stock_status == "low_stock":
        base_filter = base_filter & (
            (Item.stock > 0) & (Item.stock < Item.low_stock_threshold)
        )
    elif stock_status == "out_of_stock":
        base_filter = base_filter & (Item.stock == 0)

    count_statement = select(func.count()).select_from(Item).where(base_filter)
    count = session.exec(count_statement).one()

    statement = (
        select(Item)
        .where(base_filter)
        .order_by(col(Item.created_at).desc())
        .offset(skip)
        .limit(limit)
    )
    items = session.exec(statement).all()

    return ItemsPublic(data=items, count=count)


@router.get("/{id}", response_model=ItemPublic)
def read_item(session: SessionDep, current_user: CurrentUser, id: uuid.UUID) -> Any:
    """
    Get item by ID.
    """
    item = session.get(Item, id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if item.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return item


@router.post("/", response_model=ItemPublic)
def create_item(
    *, session: SessionDep, current_user: CurrentUser, item_in: ItemCreate
) -> Any:
    """
    Create new item.
    """
    item = Item.model_validate(item_in, update={"owner_id": current_user.id})
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


@router.put("/{id}", response_model=ItemPublic)
def update_item(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
    item_in: ItemUpdate,
) -> Any:
    """
    Update an item.
    """
    item = session.get(Item, id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if item.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    update_dict = item_in.model_dump(exclude_unset=True)
    update_dict["updated_at"] = get_datetime_utc()
    item.sqlmodel_update(update_dict)
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


@router.patch("/{id}/adjust-stock", response_model=ItemPublic)
def adjust_stock(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
    quantity: float,
    reason: str | None = None,
    reference: str | None = None,
) -> Any:
    """
    Adjust item stock by a quantity delta.

    - **quantity**: Amount to add (positive) or subtract (negative)
    - **reason**: Reason for adjustment (sale, purchase, adjustment, etc.)
    - **reference**: Optional reference (invoice number, PO number, etc.)
    """
    item = session.get(Item, id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if item.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    new_stock = item.stock + quantity
    if new_stock < 0:
        raise HTTPException(status_code=400, detail="Insufficient stock")

    stock_entry = {
        "date": get_datetime_utc().isoformat(),
        "quantity": quantity,
        "previous_stock": item.stock,
        "new_stock": new_stock,
        "reason": reason or "adjustment",
        "reference": reference,
    }

    item.stock = new_stock
    item.stock_history = item.stock_history + [stock_entry]
    item.updated_at = get_datetime_utc()

    session.add(item)
    session.commit()
    session.refresh(item)
    return item


@router.get("/categories/list")
def list_categories(session: SessionDep, current_user: CurrentUser) -> list[str]:
    """
    Get list of distinct categories used by user's items.
    """
    statement = (
        select(Item.category)
        .where(Item.owner_id == current_user.id, Item.category.isnot(None))
        .distinct()
    )
    categories = session.exec(statement).all()
    return sorted([c for c in categories if c])


@router.delete("/{id}")
def delete_item(
    session: SessionDep, current_user: CurrentUser, id: uuid.UUID
) -> Message:
    """
    Delete an item.
    """
    item = session.get(Item, id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if item.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    session.delete(item)
    session.commit()
    return Message(message="Item deleted successfully")
