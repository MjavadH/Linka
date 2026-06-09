import asyncio
from dataclasses import dataclass

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError


@dataclass(frozen=True)
class BroadcastPayload:
    kind: str
    data: dict[str, str | int | bool | None]


class BroadcastService:
    def __init__(self, bot: Bot, rate_limit_per_second: int) -> None:
        self.bot = bot
        self.delay = 1 / rate_limit_per_second

    async def send_to_user(self, telegram_id: int, payload: BroadcastPayload) -> int:
        try:
            if payload.kind == "text":
                message = await self.bot.send_message(telegram_id, str(payload.data["text"]))
            elif payload.kind == "copy_message":
                message = await self.bot.copy_message(
                    chat_id=telegram_id,
                    from_chat_id=int(payload.data["from_chat_id"]),
                    message_id=int(payload.data["message_id"]),
                )
            elif payload.kind == "photo":
                message = await self.bot.send_photo(telegram_id, str(payload.data["file_id"]))
            elif payload.kind == "video":
                message = await self.bot.send_video(telegram_id, str(payload.data["file_id"]))
            elif payload.kind == "document":
                message = await self.bot.send_document(telegram_id, str(payload.data["file_id"]))
            else:
                raise ValueError(f"Unsupported broadcast kind: {payload.kind}")
            await asyncio.sleep(self.delay)
            return message.message_id
        except TelegramAPIError:
            await asyncio.sleep(self.delay)
            raise
