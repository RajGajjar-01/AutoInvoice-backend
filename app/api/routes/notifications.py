import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from sqlmodel import col, func, select

from app.api.deps import CurrentUser, SessionDep
from app.models import (
    Message,
    Notification,
    NotificationCreate,
    NotificationPublic,
    NotificationsPublic,
    NotificationType,
    NotificationUpdate,
    get_datetime_utc,
)

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("/", response_model=NotificationsPublic)
def get_notifications(
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    unread_only: bool = False,
    type: NotificationType | None = None,
) -> Any:
    """
    Get notifications for the current user.

    - **unread_only**: Only return unread notifications
    - **type**: Filter by notification type
    """
    base_filter = Notification.owner_id == current_user.id

    if unread_only:
        base_filter = base_filter & (Notification.read == False)

    if type:
        base_filter = base_filter & (Notification.type == type)

    count_statement = select(func.count()).select_from(Notification).where(base_filter)
    count = session.exec(count_statement).one()

    unread_count = session.exec(
        select(func.count())
        .select_from(Notification)
        .where(Notification.owner_id == current_user.id, Notification.read == False)
    ).one()

    statement = (
        select(Notification)
        .where(base_filter)
        .order_by(col(Notification.created_at).desc())
        .offset(skip)
        .limit(limit)
    )
    notifications = session.exec(statement).all()

    return NotificationsPublic(
        data=notifications,
        count=count,
        unread_count=unread_count,
    )


@router.post("/", response_model=NotificationPublic)
def create_notification(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    notification_in: NotificationCreate,
) -> Any:
    """Create a new notification."""
    notification = Notification.model_validate(
        notification_in, update={"owner_id": current_user.id}
    )
    session.add(notification)
    session.commit()
    session.refresh(notification)
    return notification


@router.get("/{id}", response_model=NotificationPublic)
def get_notification(
    session: SessionDep, current_user: CurrentUser, id: uuid.UUID
) -> Any:
    """Get a specific notification."""
    notification = session.get(Notification, id)
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    if notification.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return notification


@router.patch("/{id}", response_model=NotificationPublic)
def update_notification(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
    notification_in: NotificationUpdate,
) -> Any:
    """Update a notification (e.g., mark as read)."""
    notification = session.get(Notification, id)
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    if notification.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    update_dict = notification_in.model_dump(exclude_unset=True)
    notification.sqlmodel_update(update_dict)
    session.add(notification)
    session.commit()
    session.refresh(notification)
    return notification


@router.post("/mark-all-read", response_model=Message)
def mark_all_read(session: SessionDep, current_user: CurrentUser) -> Any:
    """Mark all notifications as read."""
    statement = select(Notification).where(
        Notification.owner_id == current_user.id,
        Notification.read == False,
    )
    notifications = session.exec(statement).all()

    for notification in notifications:
        notification.read = True
        session.add(notification)

    session.commit()
    return Message(message=f"Marked {len(notifications)} notifications as read")


@router.delete("/{id}")
def delete_notification(
    session: SessionDep, current_user: CurrentUser, id: uuid.UUID
) -> Message:
    """Delete a notification."""
    notification = session.get(Notification, id)
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    if notification.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    session.delete(notification)
    session.commit()
    return Message(message="Notification deleted successfully")


@router.delete("/")
def clear_all(session: SessionDep, current_user: CurrentUser) -> Message:
    """Delete all notifications for the current user."""
    statement = select(Notification).where(Notification.owner_id == current_user.id)
    notifications = session.exec(statement).all()

    for notification in notifications:
        session.delete(notification)

    session.commit()
    return Message(message=f"Deleted {len(notifications)} notifications")
