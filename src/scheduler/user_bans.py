from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from repositories.user_bans import UserBanRepository


class UserBanExpirationJob:
    def __init__(self, bot: Bot, session: AsyncSession) -> None:
        self.bot = bot
        self.session = session

    async def run(self) -> None:
        expired_bans = await UserBanRepository(self.session).expire_due()
        for ban in expired_bans:
            if ban.user is None:
                continue
            try:
                await self.bot.send_message(
                    ban.user.telegram_id,
                    "✅ Your temporary ban has expired.\n\nYou can now use the bot normally.",
                )
            except TelegramAPIError:
                continue
        await self.session.commit()
