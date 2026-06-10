import structlog
from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import Settings
from models.sponsor import Sponsor
from repositories.sponsors import SponsorRepository
from repositories.subscriptions import SubscriptionRepository
from repositories.user_sponsors import UserSponsorRepository
from services.premium import PremiumService
from services.sponsors import AdminNotifier, SponsorService, UserSponsorService

logger = structlog.get_logger(__name__)


class BotAdminNotifier(AdminNotifier):
    def __init__(self, bot: Bot, admin_ids: tuple[int, ...]) -> None:
        self.bot = bot
        self.admin_ids = admin_ids

    async def sponsor_inaccessible(self, sponsor: Sponsor, error: Exception) -> None:
        await self._notify(
            f'⚠️ Sponsor channel "{sponsor.title}" is no longer accessible. '
            "Please re-add the bot or deactivate the sponsor."
        )

    async def sponsor_expired(self, sponsor: Sponsor) -> None:
        await self._notify(f'✅ Sponsor "{sponsor.title}" expired automatically.')

    async def sponsor_join_target_reached(self, sponsor: Sponsor) -> None:
        await self._notify(
            f'✅ Sponsor "{sponsor.title}" reached target join count and was deactivated.'
        )

    async def _notify(self, message: str) -> None:
        for admin_id in self.admin_ids:
            try:
                await self.bot.send_message(admin_id, message)
            except Exception as exc:  # noqa: BLE001 - admin alert must not crash scheduler
                logger.warning("sponsor_admin_alert_failed", admin_id=admin_id, error=str(exc))


class SponsorVerificationJob:
    def __init__(self, bot: Bot, session: AsyncSession, settings: Settings) -> None:
        self.bot = bot
        self.session = session
        self.settings = settings
        sponsor_service = SponsorService(SponsorRepository(session), bot)
        self.repository = UserSponsorRepository(session)
        self.user_sponsors = UserSponsorService(
            bot=bot,
            sponsors=sponsor_service,
            repository=self.repository,
            premium=PremiumService(SubscriptionRepository(session)),
        )
        self.notifier = BotAdminNotifier(bot, settings.admin_telegram_ids)

    async def run(self, after_user_id: int | None = None) -> int | None:
        users = await self.repository.list_verified_batch(
            after_user_id=after_user_id,
            limit=self.settings.sponsor_verification_batch_size,
        )
        next_cursor: int | None = None
        for user in users:
            try:
                await self.user_sponsors.check_verified_user(user, self.notifier)
                next_cursor = user.id
            except Exception as exc:  # noqa: BLE001 - one user must not block batch
                logger.warning("sponsor_user_verification_failed", user_id=user.id, error=str(exc))
        await self.session.commit()
        return next_cursor


class SponsorExpirationJob:
    def __init__(self, bot: Bot, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.sponsors = SponsorService(SponsorRepository(session), bot)
        self.notifier = BotAdminNotifier(bot, settings.admin_telegram_ids)

    async def run(self) -> None:
        await self.sponsors.expire_sponsors(self.notifier)
        await self.session.commit()
