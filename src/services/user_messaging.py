from aiogram import Bot
from aiogram.exceptions import TelegramAPIError


class UserMessagingService:
    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    async def send_direct_message(self, telegram_id: int, text: str) -> bool:
        try:
            await self.bot.send_message(telegram_id, text)
        except TelegramAPIError:
            return False
        return True
