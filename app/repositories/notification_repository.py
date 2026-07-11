import uuid
from typing import Any

from sqlalchemy import delete as sa_delete
from sqlalchemy import update as sa_update
from sqlmodel import col, func, select

from app.models import Notification
from app.repositories.base import BaseRepository
from app.schemas import NotificationCreate, NotificationType


class NotificationRepository(BaseRepository[Notification]):
    model = Notification

    async def list_filtered(
        self,
        owner_id: uuid.UUID,
        *,
        skip: int,
        limit: int,
        unread_only: bool,
        type: NotificationType | None,
    ) -> tuple[list[Notification], int, int]:
        base_filter = Notification.owner_id == owner_id
        if unread_only:
            base_filter = base_filter & (Notification.read == False)  # noqa: E712
        if type:
            base_filter = base_filter & (Notification.type == type)

        count_result = await self.session.exec(
            select(func.count()).select_from(Notification).where(base_filter)
        )
        count = count_result.one()

        unread_result = await self.session.exec(
            select(func.count())
            .select_from(Notification)
            .where(Notification.owner_id == owner_id, Notification.read == False)  # noqa: E712
        )
        unread_count = unread_result.one()

        statement = (
            select(Notification)
            .where(base_filter)
            .order_by(col(Notification.created_at).desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.exec(statement)
        return list(result.all()), count, unread_count

    async def create(
        self, notification_in: NotificationCreate, owner_id: uuid.UUID
    ) -> Notification:
        notification = Notification.model_validate(
            notification_in, update={"owner_id": owner_id}
        )
        return await self.add(notification)

    async def update(
        self, notification: Notification, update_data: dict[str, Any]
    ) -> Notification:
        notification.sqlmodel_update(update_data)
        return await self.add(notification)

    async def mark_all_read(self, owner_id: uuid.UUID) -> int:
        stmt = (
            sa_update(Notification)
            .where(Notification.owner_id == owner_id, Notification.read == False)  # noqa: E712
            .values(read=True)
        )
        result = await self.session.exec(stmt)
        await self.session.commit()
        return result.rowcount

    async def clear_all(self, owner_id: uuid.UUID) -> int:
        stmt = sa_delete(Notification).where(Notification.owner_id == owner_id)
        result = await self.session.exec(stmt)
        await self.session.commit()
        return result.rowcount
