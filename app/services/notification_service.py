import uuid

from app.models import Notification
from app.repositories.base import get_owned
from app.repositories.notification_repository import NotificationRepository
from app.schemas import NotificationCreate, NotificationType, NotificationUpdate


class NotificationService:
    def __init__(self, repo: NotificationRepository) -> None:
        self.repo = repo

    async def get_owned(
        self, notification_id: uuid.UUID, owner_id: uuid.UUID
    ) -> Notification:
        return await get_owned(
            self.repo, notification_id, owner_id, "Notification not found"
        )

    async def list_items(
        self,
        owner_id: uuid.UUID,
        *,
        skip: int,
        limit: int,
        unread_only: bool,
        type: NotificationType | None,
    ) -> tuple[list[Notification], int, int]:
        return await self.repo.list_filtered(
            owner_id, skip=skip, limit=limit, unread_only=unread_only, type=type
        )

    async def create(
        self, notification_in: NotificationCreate, owner_id: uuid.UUID
    ) -> Notification:
        return await self.repo.create(notification_in, owner_id)

    async def update(
        self,
        notification_id: uuid.UUID,
        owner_id: uuid.UUID,
        notification_in: NotificationUpdate,
    ) -> Notification:
        notification = await self.get_owned(notification_id, owner_id)
        update_data = notification_in.model_dump(exclude_unset=True)
        return await self.repo.update(notification, update_data)

    async def delete(self, notification_id: uuid.UUID, owner_id: uuid.UUID) -> None:
        notification = await self.get_owned(notification_id, owner_id)
        await self.repo.delete(notification)

    async def mark_all_read(self, owner_id: uuid.UUID) -> int:
        return await self.repo.mark_all_read(owner_id)

    async def clear_all(self, owner_id: uuid.UUID) -> int:
        return await self.repo.clear_all(owner_id)
