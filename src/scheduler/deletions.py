from datetime import UTC, datetime

import structlog
from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from models.enums import TemporaryMessageStatus
from repositories.temporary_messages import TemporaryMessageRepository

logger = structlog.get_logger(__name__)


class TemporaryMessageDeletionJob:
    def __init__(self, bot: Bot, session: AsyncSession) -> None:
        self.bot = bot
        self.session = session
        self.repository = TemporaryMessageRepository(session)

    async def run(self) -> None:
        messages = await self.repository.list_due()
        for message in messages:
            try:
                await self.bot.delete_message(message.chat_id, message.message_id)
                message.status = TemporaryMessageStatus.DELETED
                message.processed_at = datetime.now(UTC)
            except TelegramAPIError as exc:
                message.attempts += 1
                message.last_error = str(exc)[:1000]
                if message.attempts >= 3:
                    message.status = TemporaryMessageStatus.FAILED
                    message.processed_at = datetime.now(UTC)
                logger.warning("temporary_message_delete_failed", id=message.id, error=str(exc))
        await self.session.commit()
