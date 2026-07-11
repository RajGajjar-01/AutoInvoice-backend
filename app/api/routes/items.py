import uuid
from typing import Any

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, ItemServiceDep
from app.schemas import ItemCreate, ItemPublic, ItemsPublic, ItemUpdate

router = APIRouter(prefix="/items", tags=["items"])


@router.get("/", response_model=ItemsPublic)
async def read_items(
    current_user: CurrentUser,
    item_service: ItemServiceDep,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    search: str | None = None,
    category: str | None = None,
    stock_status: str | None = Query(
        None, pattern="^(in_stock|low_stock|out_of_stock)$"
    ),
) -> Any:
    items, count = await item_service.list_items(
        current_user.id,
        skip=skip,
        limit=limit,
        search=search,
        category=category,
        stock_status=stock_status,
    )
    return ItemsPublic(data=items, count=count)


@router.get("/categories/list")
async def list_categories(current_user: CurrentUser, item_service: ItemServiceDep) -> list[str]:
    return await item_service.list_categories(current_user.id)


@router.get("/{id}", response_model=ItemPublic)
async def read_item(current_user: CurrentUser, item_service: ItemServiceDep, id: uuid.UUID) -> Any:
    return await item_service.get_owned(id, current_user.id)


@router.post("/", response_model=ItemPublic, status_code=201)
async def create_item(
    *, current_user: CurrentUser, item_service: ItemServiceDep, item_in: ItemCreate
) -> Any:
    return await item_service.create(item_in, current_user.id)


@router.put("/{id}", response_model=ItemPublic)
async def update_item(
    *,
    current_user: CurrentUser,
    item_service: ItemServiceDep,
    id: uuid.UUID,
    item_in: ItemUpdate,
) -> Any:
    return await item_service.update(id, current_user.id, item_in)


@router.patch("/{id}/adjust-stock", response_model=ItemPublic)
async def adjust_stock(
    *,
    current_user: CurrentUser,
    item_service: ItemServiceDep,
    id: uuid.UUID,
    quantity: float,
    reason: str | None = None,
    reference: str | None = None,
) -> Any:
    return await item_service.adjust_stock(
        id, current_user.id, quantity=quantity, reason=reason, reference=reference
    )


@router.delete("/{id}", status_code=204)
async def delete_item(current_user: CurrentUser, item_service: ItemServiceDep, id: uuid.UUID) -> None:
    await item_service.delete(id, current_user.id)
