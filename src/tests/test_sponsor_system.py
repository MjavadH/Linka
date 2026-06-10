import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from models.enums import SponsorStatus, TemporaryMessageStatus
from models.sponsor import Sponsor
from models.temporary_message import TemporaryMessage
from models.user import User
from scheduler.sponsors import BotAdminNotifier
from services.sponsors import UserSponsorService


class FakeSession:
    def __init__(self) -> None:
        self.flushed = 0

    async def flush(self) -> None:
        self.flushed += 1


class FakeUserSponsorRepository:
    def __init__(self, temporary_messages: list[TemporaryMessage] | None = None) -> None:
        self.session = FakeSession()
        self.temporary_messages = temporary_messages or []

    async def set_status(self, user: User, status: SponsorStatus) -> User:
        user.sponsor_status = status
        user.last_sponsor_check_at = datetime.now(UTC)
        if status == SponsorStatus.VERIFIED:
            user.sponsor_verified_at = datetime.now(UTC)
        await self.session.flush()
        return user

    async def pending_temporary_messages_for_user(self, user_id: int) -> list[TemporaryMessage]:
        return [
            message
            for message in self.temporary_messages
            if message.user_id == user_id and message.status == TemporaryMessageStatus.PENDING
        ]


class FakePremiumService:
    def __init__(self, premium: bool = False) -> None:
        self.premium = premium

    async def has_premium(self, user_id: int) -> bool:
        return self.premium


class FakeSponsorService:
    def __init__(
        self, missing: list[Sponsor] | None = None, active: list[Sponsor] | None = None
    ) -> None:
        self.missing = missing or []
        self.active = active if active is not None else self.missing

    async def check_user_against_active_sponsors(self, telegram_id: int) -> list[Sponsor]:
        return self.missing

    async def list_active_sponsors(self) -> list[Sponsor]:
        return self.active

    async def is_user_missing_sponsor(self, telegram_id: int, sponsor: Sponsor) -> bool:
        return sponsor in self.missing

    async def record_successful_verification(self, sponsors: list[Sponsor]) -> None:
        for sponsor in sponsors:
            sponsor.sponsor_join_count = (sponsor.sponsor_join_count or 0) + 1


class FakeBot:
    def __init__(self) -> None:
        self.sent_messages: list[tuple[int, str]] = []
        self.deleted_messages: list[tuple[int, int]] = []

    async def send_message(self, chat_id: int, text: str) -> None:
        self.sent_messages.append((chat_id, text))

    async def delete_message(self, chat_id: int, message_id: int) -> None:
        self.deleted_messages.append((chat_id, message_id))


def user(status: SponsorStatus = SponsorStatus.PENDING) -> User:
    return User(id=1, telegram_id=12345, sponsor_status=status, last_seen_at=datetime.now(UTC))


def sponsor(title: str = "Sponsor") -> Sponsor:
    return Sponsor(id=10, chat_id=-10010, title=title, invite_url="https://t.me/+abc")


def test_user_transitions_pending_verified_revoked_verified() -> None:
    async def scenario() -> None:
        bot = FakeBot()
        repo = FakeUserSponsorRepository()
        premium = FakePremiumService(False)
        current_user = user(SponsorStatus.PENDING)

        service = UserSponsorService(cast(Any, bot), cast(Any, FakeSponsorService([])), cast(Any, repo), cast(Any, premium))
        result = await service.verify_joined(current_user)
        assert result.passed is True
        assert current_user.sponsor_status == SponsorStatus.VERIFIED

        missing_sponsor = sponsor()
        service = UserSponsorService(cast(Any, bot), cast(Any, FakeSponsorService([missing_sponsor])), cast(Any, repo), cast(Any, premium))
        missing_result = await service.check_verified_user(current_user)
        assert missing_result == [missing_sponsor]
        assert current_user.sponsor_status.value == SponsorStatus.REVOKED.value

        service = UserSponsorService(cast(Any, bot), cast(Any, FakeSponsorService([])), cast(Any, repo), cast(Any, premium))
        result = await service.verify_joined(current_user)
        assert result.passed is True
        assert current_user.sponsor_status == SponsorStatus.VERIFIED

    asyncio.run(scenario())


def test_warning_message_sent_only_once_per_violation() -> None:
    async def scenario() -> None:
        bot = FakeBot()
        current_user = user(SponsorStatus.VERIFIED)
        service = UserSponsorService(
            cast(Any, bot),
            cast(Any, FakeSponsorService([sponsor("News")])),
            cast(Any, FakeUserSponsorRepository()),
            cast(Any, FakePremiumService(False)),
        )

        await service.check_verified_user(current_user)
        await service.check_verified_user(current_user)

        assert len(bot.sent_messages) == 1
        assert "You have left News" in bot.sent_messages[0][1]

    asyncio.run(scenario())


def test_temporary_files_deleted_when_user_revoked() -> None:
    async def scenario() -> None:
        bot = FakeBot()
        temp = TemporaryMessage(
            id=55,
            user_id=1,
            chat_id=12345,
            message_id=777,
            delete_at=datetime.now(UTC) + timedelta(hours=1),
            status=TemporaryMessageStatus.PENDING,
        )
        current_user = user(SponsorStatus.VERIFIED)
        service = UserSponsorService(
            cast(Any, bot),
            cast(Any, FakeSponsorService([sponsor()])),
            cast(Any, FakeUserSponsorRepository([temp])),
            cast(Any, FakePremiumService(False)),
        )

        await service.check_verified_user(current_user)

        assert bot.deleted_messages == [(12345, 777)]
        assert temp.status == TemporaryMessageStatus.DELETED

    asyncio.run(scenario())


def test_verified_batch_recent_users_first_ordering() -> None:
    now = datetime.now(UTC)
    users = [
        User(id=1, telegram_id=1, sponsor_status=SponsorStatus.VERIFIED, last_seen_at=now),
        User(
            id=2,
            telegram_id=2,
            sponsor_status=SponsorStatus.VERIFIED,
            last_seen_at=now + timedelta(seconds=5),
        ),
        User(
            id=3,
            telegram_id=3,
            sponsor_status=SponsorStatus.PENDING,
            last_seen_at=now + timedelta(seconds=10),
        ),
    ]

    ordered = sorted(
        (item for item in users if item.sponsor_status == SponsorStatus.VERIFIED),
        key=lambda item: (item.last_seen_at, item.id),
        reverse=True,
    )

    assert [item.id for item in ordered] == [2, 1]


def test_sponsor_deactivation_admin_alert_message() -> None:
    async def scenario() -> None:
        bot = FakeBot()
        notifier = BotAdminNotifier(cast(Any, bot), (111, 222))
        item = sponsor("Partner")

        await notifier.sponsor_inaccessible(item, RuntimeError("chat not found"))

        assert bot.sent_messages == [
            (
                111,
                '⚠️ Sponsor channel "Partner" is no longer accessible. Please re-add the bot or deactivate the sponsor.',
            ),
            (
                222,
                '⚠️ Sponsor channel "Partner" is no longer accessible. Please re-add the bot or deactivate the sponsor.',
            ),
        ]

    asyncio.run(scenario())


def test_successful_verification_increments_active_sponsor_join_count_once() -> None:
    async def scenario() -> None:
        active_sponsor = sponsor("Growth")
        current_user = user(SponsorStatus.PENDING)
        service = UserSponsorService(
            cast(Any, FakeBot()),
            cast(Any, FakeSponsorService([], [active_sponsor])),
            cast(Any, FakeUserSponsorRepository()),
            cast(Any, FakePremiumService(False)),
        )

        await service.verify_joined(current_user)
        await service.verify_joined(current_user)

        assert active_sponsor.sponsor_join_count == 1

    asyncio.run(scenario())


def test_admin_notifier_sends_expiration_messages() -> None:
    async def scenario() -> None:
        bot = FakeBot()
        notifier = BotAdminNotifier(cast(Any, bot), (111,))
        item = sponsor("Partner")

        await notifier.sponsor_expired(item)
        await notifier.sponsor_join_target_reached(item)

        assert bot.sent_messages == [
            (111, '✅ Sponsor "Partner" expired automatically.'),
            (111, '✅ Sponsor "Partner" reached target join count and was deactivated.'),
        ]

    asyncio.run(scenario())
