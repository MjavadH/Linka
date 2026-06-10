from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol

import structlog
from aiogram import Bot
from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest, TelegramForbiddenError

from models.enums import SponsorStatus, TemporaryMessageStatus
from models.sponsor import Sponsor, SponsorRequirement
from models.user import User
from repositories.sponsors import SponsorRepository
from repositories.user_sponsors import UserSponsorRepository
from services.premium import PremiumService

logger = structlog.get_logger(__name__)


class AdminNotifier(Protocol):
    async def sponsor_inaccessible(self, sponsor: Sponsor, error: Exception) -> None: ...

    async def sponsor_expired(self, sponsor: Sponsor) -> None: ...

    async def sponsor_join_target_reached(self, sponsor: Sponsor) -> None: ...


@dataclass(frozen=True)
class SponsorCheckResult:
    passed: bool
    missing_requirements: list[SponsorRequirement] = field(default_factory=list)
    missing_sponsors: list[Sponsor] = field(default_factory=list)


class SponsorService:
    def __init__(self, repository: SponsorRepository, bot: Bot) -> None:
        self.repository = repository
        self.bot = bot

    async def list_active_sponsors(self) -> list[Sponsor]:
        return await self.repository.list_active()

    async def expire_sponsors(self, notifier: AdminNotifier | None = None) -> None:
        now = datetime.now(UTC)
        for sponsor in await self.repository.list_all():
            if not sponsor.is_active:
                continue
            if sponsor.expiration_type == "date" and sponsor.expiration_value:
                expires_at = datetime.fromisoformat(sponsor.expiration_value)
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=UTC)
                if expires_at <= now:
                    await self.repository.deactivate(sponsor, "expired")
                    if notifier is not None:
                        await notifier.sponsor_expired(sponsor)
            elif sponsor.expiration_type == "members" and sponsor.expiration_value:
                target = int(sponsor.expiration_value)
                if (sponsor.sponsor_join_count or 0) >= target:
                    await self.repository.deactivate(sponsor, "member_target_reached")
                    if notifier is not None:
                        await notifier.sponsor_join_target_reached(sponsor)

    async def check_user(self, telegram_id: int) -> SponsorCheckResult:
        missing = await self.check_user_against_active_sponsors(telegram_id)
        return SponsorCheckResult(passed=not missing, missing_sponsors=missing)

    async def check_user_against_active_sponsors(self, telegram_id: int) -> list[Sponsor]:
        missing: list[Sponsor] = []
        for sponsor in await self.list_active_sponsors():
            if await self.is_user_missing_sponsor(telegram_id, sponsor):
                missing.append(sponsor)
        return missing

    async def is_user_missing_sponsor(self, telegram_id: int, sponsor: Sponsor) -> bool:
        member = await self.bot.get_chat_member(sponsor.chat_id, telegram_id)
        return member.status in {ChatMemberStatus.LEFT, ChatMemberStatus.KICKED}

    async def record_successful_verification(self, sponsors: list[Sponsor]) -> None:
        await self.repository.increment_join_counts(sponsors)

    async def deactivate_inaccessible_sponsor(
        self, sponsor: Sponsor, error: Exception, notifier: AdminNotifier | None = None
    ) -> None:
        await self.repository.deactivate(sponsor, str(error))
        if notifier is not None:
            await notifier.sponsor_inaccessible(sponsor, error)


class UserSponsorService:
    def __init__(
        self,
        bot: Bot,
        sponsors: SponsorService,
        repository: UserSponsorRepository,
        premium: PremiumService,
    ) -> None:
        self.bot = bot
        self.sponsors = sponsors
        self.repository = repository
        self.premium = premium

    async def ensure_access(self, user: User) -> SponsorCheckResult:
        if await self.premium.has_premium(user.id):
            return SponsorCheckResult(True, [], [])
        active_sponsors = await self.sponsors.list_active_sponsors()
        missing: list[Sponsor] = []
        for sponsor in active_sponsors:
            if await self.sponsors.is_user_missing_sponsor(user.telegram_id, sponsor):
                missing.append(sponsor)
        if missing:
            if user.sponsor_status == SponsorStatus.VERIFIED:
                await self.revoke_user(user, missing)
            else:
                await self.repository.set_status(user, SponsorStatus.PENDING)
            return SponsorCheckResult(False, [], missing)
        became_verified = user.sponsor_status != SponsorStatus.VERIFIED
        await self.repository.set_status(user, SponsorStatus.VERIFIED)
        if became_verified:
            await self.sponsors.record_successful_verification(active_sponsors)
        return SponsorCheckResult(True, [], [])

    async def verify_joined(self, user: User) -> SponsorCheckResult:
        return await self.ensure_access(user)

    async def revoke_user(self, user: User, missing_sponsors: list[Sponsor]) -> None:
        if user.sponsor_status == SponsorStatus.REVOKED:
            user.last_sponsor_check_at = datetime.now(UTC)
            await self.repository.session.flush()
            return
        await self.repository.set_status(user, SponsorStatus.REVOKED)
        await self._delete_pending_temporary_files(user.id)
        first_missing = missing_sponsors[0]
        await self.bot.send_message(
            user.telegram_id,
            f"⚠️ You have left {first_missing.title}. You cannot use the bot until you rejoin all sponsor channels.",
        )

    async def _delete_pending_temporary_files(self, user_id: int) -> None:
        messages = await self.repository.pending_temporary_messages_for_user(user_id)
        for message in messages:
            try:
                await self.bot.delete_message(message.chat_id, message.message_id)
                message.status = TemporaryMessageStatus.DELETED
                message.processed_at = datetime.now(UTC)
            except TelegramAPIError as exc:
                message.attempts += 1
                message.last_error = str(exc)[:1000]
                logger.warning("revoked_user_temp_delete_failed", id=message.id, error=str(exc))

    async def check_verified_user(
        self, user: User, notifier: AdminNotifier | None = None
    ) -> list[Sponsor]:
        if await self.premium.has_premium(user.id):
            user.last_sponsor_check_at = datetime.now(UTC)
            await self.repository.session.flush()
            return []
        missing: list[Sponsor] = []
        for sponsor in await self.sponsors.list_active_sponsors():
            try:
                if await self.sponsors.is_user_missing_sponsor(user.telegram_id, sponsor):
                    missing.append(sponsor)
            except (TelegramBadRequest, TelegramForbiddenError) as exc:
                await self.sponsors.deactivate_inaccessible_sponsor(sponsor, exc, notifier)
            except TelegramAPIError as exc:
                logger.warning("sponsor_check_api_error", user_id=user.id, sponsor_id=sponsor.id, error=str(exc))
        user.last_sponsor_check_at = datetime.now(UTC)
        if missing:
            await self.revoke_user(user, missing)
        await self.repository.session.flush()
        return missing
