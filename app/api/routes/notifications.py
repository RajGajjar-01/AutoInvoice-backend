import uuid
from typing import Any

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, NotificationServiceDep
from app.schemas import (
    Message,
    NotificationCreate,
    NotificationPublic,
    NotificationsPublic,
    NotificationType,
    NotificationUpdate,
)

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("/", response_model=NotificationsPublic)
async def get_notifications(
    current_user: CurrentUser,
    notification_service: NotificationServiceDep,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    unread_only: bool = False,
    type: NotificationType | None = None,
) -> Any:
    notifications, count, unread_count = await notification_service.list_items(
        current_user.id, skip=skip, limit=limit, unread_only=unread_only, type=type
    )
    return NotificationsPublic(data=notifications, count=count, unread_count=unread_count)


@router.post("/", response_model=NotificationPublic, status_code=201)
async def create_notification(
    *,
    current_user: CurrentUser,
    notification_service: NotificationServiceDep,
    notification_in: NotificationCreate,
) -> Any:
    return await notification_service.create(notification_in, current_user.id)


@router.get("/{id}", response_model=NotificationPublic)
async def get_notification(
    current_user: CurrentUser, notification_service: NotificationServiceDep, id: uuid.UUID
) -> Any:
    return await notification_service.get_owned(id, current_user.id)


@router.patch("/{id}", response_model=NotificationPublic)
async def update_notification(
    *,
    current_user: CurrentUser,
    notification_service: NotificationServiceDep,
    id: uuid.UUID,
    notification_in: NotificationUpdate,
) -> Any:
    return await notification_service.update(id, current_user.id, notification_in)


@router.post("/mark-all-read", response_model=Message)
async def mark_all_read(current_user: CurrentUser, notification_service: NotificationServiceDep) -> Any:
    n = await notification_service.mark_all_read(current_user.id)
    return Message(message=f"Marked {n} notifications as read")


@router.delete("/{id}", status_code=204)
async def delete_notification(
    current_user: CurrentUser, notification_service: NotificationServiceDep, id: uuid.UUID
) -> None:
    await notification_service.delete(id, current_user.id)


@router.delete("/", status_code=204)
async def clear_all(current_user: CurrentUser, notification_service: NotificationServiceDep) -> None:
    await notification_service.clear_all(current_user.id)
