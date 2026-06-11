import structlog
from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

from repositories.subscriptions import SubscriptionRepository
from services.premium import PremiumService

logger = structlog.get_logger(__name__)


class PremiumExpirationJob:
    def __init__(self, bot: Bot, session: AsyncSession) -> None:
        self.bot = bot
        self.session = session
        self.repository = SubscriptionRepository(session)
        self.premium = PremiumService(self.repository)

    async def run(self) -> None:
        expired = await self.repository.expire_due()
        for subscription in expired:
            try:
                await self.bot.send_message(subscription.user.telegram_id, "⚠️ Your premium subscription has expired.")
            except Exception as exc:  # noqa: BLE001 - notification failure must not rollback expiration
                logger.warning("premium_expiration_notification_failed", user_id=subscription.user_id, error=str(exc))
        await self.session.commit()
