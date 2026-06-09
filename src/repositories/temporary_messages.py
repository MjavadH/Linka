from datetime import UTC, datetime

from sqlalchemy import select

from models.enums import TemporaryMessageStatus
from models.temporary_message import TemporaryMessage
from repositories.base import BaseRepository


class TemporaryMessageRepository(BaseRepository[TemporaryMessage]):
    async def create(self, chat_id: int, message_id: int, delete_after: datetime) -> TemporaryMessage:
        item = TemporaryMessage(chat_id=chat_id, message_id=message_id, delete_after=delete_after)
        self.session.add(item)
        await self.session.flush()
        return item

    async def list_due(self, limit: int = 100) -> list[TemporaryMessage]:
        result = await self.session.execute(
            select(TemporaryMessage)
            .where(
                TemporaryMessage.status == TemporaryMessageStatus.PENDING,
                TemporaryMessage.delete_after <= datetime.now(UTC),
            )
            .order_by(TemporaryMessage.delete_after)
            .limit(limit)
        )
        return list(result.scalars())
