from datetime import UTC, datetime

import structlog
from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import Settings
from core.timezone import format_date
from keyboards.premium import expired_subscription_keyboard, renewal_keyboard
from models.subscription import Subscription
from repositories.subscriptions import SubscriptionRepository
from services.premium import PremiumService

logger = structlog.get_logger(__name__)


class PremiumExpirationJob:
    def __init__(self, bot: Bot, session: AsyncSession, settings: Settings | None = None) -> None:
        self.bot = bot
        self.session = session
        self.settings = settings
        self.repository = SubscriptionRepository(session)
        self.premium = PremiumService(self.repository)

    async def run(self) -> None:
        for days_before in (7, 3, 1):
            await self._send_reminders(days_before)
        await self._expire_due_subscriptions()
        await self.session.commit()

    async def _send_reminders(self, days_before: int) -> None:
        now = datetime.now(UTC)
        subscriptions = await self.repository.list_due_reminders(days_before, now)
        for subscription in subscriptions:
            try:
                await self.bot.send_message(
                    subscription.user.telegram_id,
                    _reminder_text(subscription, days_before, self._timezone),
                    reply_markup=renewal_keyboard(),
                )
                await self.repository.mark_reminder_sent(subscription, days_before, now)
            except Exception as exc:  # noqa: BLE001 - notification failure must not rollback other work
                logger.warning(
                    "premium_reminder_notification_failed",
                    user_id=subscription.user_id,
                    days_before=days_before,
                    error=str(exc),
                )

    async def _expire_due_subscriptions(self) -> None:
        expired = await self.repository.expire_due()
        for subscription in expired:
            try:
                await self.bot.send_message(
                    subscription.user.telegram_id,
                    _expiration_text(),
                    reply_markup=expired_subscription_keyboard(),
                )
            except Exception as exc:  # noqa: BLE001 - notification failure must not rollback expiration
                logger.warning("premium_expiration_notification_failed", user_id=subscription.user_id, error=str(exc))

    @property
    def _timezone(self) -> str:
        return self.settings.timezone if self.settings is not None else "UTC"


def _reminder_text(subscription: Subscription, days_before: int, timezone: str) -> str:
    expires = format_date(subscription.expires_at, timezone)
    plan = subscription.plan.name if subscription.plan is not None else "—"
    remaining = "tomorrow" if days_before == 1 else f"in {days_before} days"
    ending = "Renew now to avoid interruption." if days_before == 1 else "Renew now to continue enjoying premium benefits."
    return (
        "⚠️ <b>Premium Subscription Reminder</b>\n\n"
        f"Your premium subscription will expire {remaining}.\n\n"
        "Current Plan:\n"
        f"{plan}\n\n"
        "Expiration Date:\n"
        f"{expires}\n\n"
        f"{ending}"
    )


def _expiration_text() -> str:
    return (
        "❌ <b>Premium Subscription Expired</b>\n\n"
        "Your premium subscription has ended.\n\n"
        "You have been returned to a standard account.\n\n"
        "You can purchase a new subscription at any time."
    )
