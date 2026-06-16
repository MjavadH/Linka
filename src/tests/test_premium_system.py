import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, cast

from handlers import premium as premium_handlers
from models.enums import FileAccessLevel, StorageType
from models.file import DeepLink, File, FileVariant
from models.sponsor import Sponsor
from models.subscription import PremiumPlan, Subscription
from models.user import User
from scheduler import premium as premium_scheduler
from services.file_delivery import FileDeliveryService
from services.premium import PremiumService
from services.sponsors import SponsorCheckResult, UserSponsorService
from services.storage import StoredFileReference


class _SubscriptionRepo:
    def __init__(self) -> None:
        self.items: list[Subscription] = []

    async def has_active_subscription(self, user_id: int) -> bool:
        return any(item.user_id == user_id and item.is_active and item.expires_at > datetime.now(UTC) for item in self.items)

    async def get_active_subscription(self, user_id: int) -> Subscription | None:
        active = [item for item in self.items if item.user_id == user_id and item.is_active and item.expires_at > datetime.now(UTC)]
        return max(active, key=lambda item: item.expires_at, default=None)

    async def activate(self, *, user_id: int, plan: PremiumPlan, admin_id: int | None = None, note: str | None = None, **_: Any) -> Subscription:
        starts_at = datetime.now(UTC)
        subscription = Subscription(id=len(self.items) + 1, user_id=user_id, plan_id=plan.id, starts_at=starts_at, expires_at=starts_at + timedelta(days=plan.duration_days), is_active=True, granted_by_admin_id=admin_id, note=note)
        self.items.append(subscription)
        return subscription

    async def expire_subscription(self, subscription: Subscription) -> Subscription:
        subscription.is_active = False
        return subscription

    async def stats(self) -> dict[str, object]:
        return {
            "active_premium_users": 2,
            "expired_subscriptions": 1,
            "total_subscriptions_sold": 3,
            "active_plans": 4,
            "most_popular_plan": "Gold",
        }


def test_premium_activation_creates_active_subscription() -> None:
    async def scenario() -> None:
        repo = _SubscriptionRepo()
        plan = PremiumPlan(id=1, name="Gold", duration_days=90, price=Decimal("250000"), is_active=True)
        subscription = await PremiumService(cast(Any, repo)).activate_subscription(42, plan, admin_user_id=7)
        assert subscription.user_id == 42
        assert subscription.plan_id == 1
        assert subscription.is_active is True
        assert subscription.expires_at > datetime.now(UTC) + timedelta(days=89)
        assert await PremiumService(cast(Any, repo)).has_active_subscription(42) is True

    asyncio.run(scenario())


def test_expiration_scheduler_deactivates_and_notifies(monkeypatch: Any) -> None:
    async def scenario() -> None:
        expired_user = User(id=5, telegram_id=500)
        expired = Subscription(id=1, user_id=5, user=expired_user, expires_at=datetime.now(UTC) - timedelta(seconds=1), is_active=True)

        class Repo:
            def __init__(self, session: Any) -> None:
                pass

            async def list_due_reminders(self, days_before: int, current: datetime | None = None) -> list[Subscription]:
                return []

            async def expire_due(self) -> list[Subscription]:
                expired.is_active = False
                return [expired]

        class Bot:
            def __init__(self) -> None:
                self.sent: list[tuple[int, str]] = []

            async def send_message(self, chat_id: int, text: str, reply_markup: Any = None) -> None:
                self.sent.append((chat_id, text))

        class Session:
            def __init__(self) -> None:
                self.committed = False

            async def commit(self) -> None:
                self.committed = True

        monkeypatch.setattr(premium_scheduler, "SubscriptionRepository", Repo)
        bot = Bot()
        session = Session()
        await premium_scheduler.PremiumExpirationJob(cast(Any, bot), cast(Any, session)).run()
        assert expired.is_active is False
        assert len(bot.sent) == 1
        assert bot.sent[0][0] == 500
        assert "❌ <b>Premium Subscription Expired</b>" in bot.sent[0][1]
        assert session.committed is True

    asyncio.run(scenario())


def test_premium_file_access_allows_premium_and_blocks_normal_user() -> None:
    async def scenario() -> None:
        file = File(id=1, title="Premium file", is_active=True)
        variant = FileVariant(id=2, file_id=1, file=file, quality="HD", storage_key="key", telegram_file_id="tg", media_type="document", is_active=True, is_premium=True, access_level=FileAccessLevel.PREMIUM)
        link = DeepLink(id=3, token="premium", file_id=1, file=file, variant=variant, requires_premium=True, is_active=True)

        normal = await _delivery(link, variant, premium=False).deliver("premium", user_id=1, telegram_id=10, chat_id=100)
        assert normal.delivered is False
        assert normal.reason == "premium_required"

        service = _delivery(link, variant, premium=True)
        premium = await service.deliver("premium", user_id=1, telegram_id=10, chat_id=100)
        assert premium.delivered is True
        assert cast(Any, service.bot).sent_documents == ["tg"]

    asyncio.run(scenario())


def test_premium_user_bypasses_sponsor_checks() -> None:
    async def scenario() -> None:
        user = User(id=1, telegram_id=111)
        sponsor = Sponsor(id=1, chat_id=-100, title="Sponsor", invite_url="https://t.me/x")

        class Sponsors:
            def __init__(self) -> None:
                self.checked = False

            async def list_active_sponsors(self) -> list[Sponsor]:
                self.checked = True
                return [sponsor]

        class Premium:
            async def has_premium(self, user_id: int) -> bool:
                return True

        result = await UserSponsorService(cast(Any, object()), cast(Any, Sponsors()), cast(Any, object()), cast(Any, Premium())).ensure_access(user)
        assert result.passed is True
        assert result.missing_sponsors == []

    asyncio.run(scenario())


def test_plan_selection_renders_all_active_plan_details(monkeypatch: Any) -> None:
    async def scenario() -> None:
        plans = [
            PremiumPlan(id=1, name="Silver", duration_days=30, price=Decimal("100000"), is_active=True),
            PremiumPlan(id=2, name="Gold", duration_days=90, price=Decimal("250000"), is_active=True),
        ]

        class Repo:
            def __init__(self, session: Any) -> None:
                pass

            async def list_active(self) -> list[PremiumPlan]:
                return plans

        class Message:
            def __init__(self) -> None:
                self.text = ""
                self.markup: Any = None

            async def answer(self, text: str, reply_markup: Any = None) -> None:
                self.text = text
                self.markup = reply_markup

        monkeypatch.setattr(premium_handlers, "PremiumPlanRepository", Repo)
        message = Message()
        await premium_handlers.show_plan_selection(cast(Any, message), cast(Any, object()))
        assert "⭐ <b>Available Plans</b>" in message.text
        assert "Silver" in message.text and "30 Days" in message.text and "100,000" in message.text
        assert "Gold" in message.text and "90 Days" in message.text and "250,000" in message.text
        assert len(message.markup.inline_keyboard) == 2

    asyncio.run(scenario())


def test_statistics_generation_maps_repository_values() -> None:
    async def scenario() -> None:
        stats = await PremiumService(cast(Any, _SubscriptionRepo())).get_statistics()
        assert stats.active_premium_users == 2
        assert stats.expired_subscriptions == 1
        assert stats.total_subscriptions_sold == 3
        assert stats.active_plans == 4
        assert stats.most_popular_plan == "Gold"

    asyncio.run(scenario())


def _delivery(link: DeepLink, variant: FileVariant, premium: bool) -> FileDeliveryService:
    class Links:
        async def get_active_by_token(self, token: str) -> DeepLink | None:
            return link if token == link.token else None

    class Variants:
        async def get_default_for_file(self, file_id: int) -> FileVariant | None:
            return variant

    class Sponsors:
        async def check_user(self, telegram_id: int) -> SponsorCheckResult:
            return SponsorCheckResult(True, [], [])

    class Premium:
        async def has_premium(self, user_id: int) -> bool:
            return premium

    class Temps:
        async def create(self, *args: Any, **kwargs: Any) -> object:
            return SimpleNamespace()

    class Downloads:
        async def create(self, **kwargs: Any) -> object:
            return SimpleNamespace(**kwargs)

    class Storage:
        async def get_file(self, variant: FileVariant) -> StoredFileReference:
            return StoredFileReference(StorageType.TELEGRAM, variant.storage_key, variant.telegram_file_id)

    class Bot:
        def __init__(self) -> None:
            self.sent_documents: list[str] = []

        async def send_document(self, **kwargs: Any) -> object:
            self.sent_documents.append(kwargs["document"])
            return SimpleNamespace(message_id=55)

    return FileDeliveryService(cast(Any, Bot()), cast(Any, Links()), cast(Any, Variants()), cast(Any, Sponsors()), cast(Any, Premium()), cast(Any, Temps()), cast(Any, Downloads()), cast(Any, Storage()), 60)


def test_account_display_premium_active_uses_timezone() -> None:
    from models.enums import SponsorStatus
    from services.accounts import AccountInfo, format_account_info

    plan = PremiumPlan(id=1, name="Diamond", duration_days=30, price=Decimal("1"), is_active=True)
    subscription = Subscription(
        id=1,
        user_id=1,
        plan=plan,
        expires_at=datetime(2026, 12, 14, 21, 0, tzinfo=UTC),
        is_active=True,
    )
    user = User(
        id=1,
        telegram_id=123456789,
        username="mohammad",
        first_name="Mohammad",
        sponsor_status=SponsorStatus.VERIFIED,
        joined_at=datetime(2026, 1, 2, 21, 0, tzinfo=UTC),
    )
    text = format_account_info(AccountInfo(user=user, subscription=subscription, timezone="Asia/Tehran"))
    assert "👤 <b>Account Information</b>" in text
    assert "Name: Mohammad" in text
    assert "Username: @mohammad" in text
    assert "User ID: 123456789" in text
    assert "Premium: Active" in text
    assert "Plan: Diamond" in text
    assert "Expires: 2026-12-15" in text
    assert "Sponsor Status: Verified" in text
    assert "Joined: 2026-01-03" in text


def test_account_display_premium_inactive_without_username() -> None:
    from models.enums import SponsorStatus
    from services.accounts import AccountInfo, format_account_info

    user = User(
        id=1,
        telegram_id=123456789,
        username=None,
        first_name="Mohammad",
        sponsor_status=SponsorStatus.PENDING,
        joined_at=datetime(2026, 1, 3, 8, 0, tzinfo=UTC),
    )
    text = format_account_info(AccountInfo(user=user, subscription=None, timezone="UTC"))
    assert "Username: —" in text
    assert "Premium: Inactive" in text
    assert "Plan: —" in text
    assert "Expires: —" in text
    assert "Sponsor Status: Verification Required" in text


def test_premium_required_screen_text_and_button() -> None:
    from keyboards.premium import premium_required_keyboard

    required_text = (
        "⭐ <b>Premium Required</b>\n\n"
        "This file is available only to premium members.\n\n"
        "<b>Premium Benefits:</b>\n\n"
        "• Access premium-only content\n\n"
        "• Access premium-only quality variants\n\n"
        "• No sponsor requirements\n\n"
        "Choose a subscription plan to continue."
    )
    markup = premium_required_keyboard()
    assert "Access premium-only quality variants" in required_text
    assert markup.inline_keyboard[0][0].text == "⭐ Buy Subscription"
    assert markup.inline_keyboard[0][0].callback_data == "premium:plans"


def test_premium_reminder_texts_use_expected_copy_and_timezone() -> None:
    plan = PremiumPlan(id=1, name="Diamond", duration_days=30, price=Decimal("1"), is_active=True)
    subscription = Subscription(plan=plan, expires_at=datetime(2026, 12, 14, 21, 0, tzinfo=UTC), is_active=True)
    assert "will expire in 7 days" in premium_scheduler._reminder_text(subscription, 7, "Asia/Tehran")
    assert "will expire in 3 days" in premium_scheduler._reminder_text(subscription, 3, "Asia/Tehran")
    one_day = premium_scheduler._reminder_text(subscription, 1, "Asia/Tehran")
    assert "will expire tomorrow" in one_day
    assert "Current Plan:\nDiamond" in one_day
    assert "Expiration Date:\n2026-12-15" in one_day
    assert "Renew now to avoid interruption." in one_day


def test_expiration_notification_text_and_keyboard() -> None:
    from keyboards.premium import expired_subscription_keyboard

    text = premium_scheduler._expiration_text()
    markup = expired_subscription_keyboard()
    assert "❌ <b>Premium Subscription Expired</b>" in text
    assert "You have been returned to a standard account." in text
    assert markup.inline_keyboard[0][0].text == "⭐ Buy Subscription"
    assert markup.inline_keyboard[0][0].callback_data == "premium:plans"


def test_premium_reminders_and_expiration_are_sent_once(monkeypatch: Any) -> None:
    async def scenario() -> None:
        now = datetime(2026, 12, 8, 0, 0, tzinfo=UTC)
        users = {days: User(id=days, telegram_id=1000 + days) for days in (7, 3, 1)}
        plan = PremiumPlan(id=1, name="Diamond", duration_days=30, price=Decimal("1"), is_active=True)
        reminders = {
            7: [Subscription(id=7, user_id=7, user=users[7], plan=plan, expires_at=now + timedelta(days=7), is_active=True)],
            3: [Subscription(id=3, user_id=3, user=users[3], plan=plan, expires_at=now + timedelta(days=3), is_active=True)],
            1: [Subscription(id=1, user_id=1, user=users[1], plan=plan, expires_at=now + timedelta(days=1), is_active=True)],
        }
        expired_user = User(id=9, telegram_id=1009)
        expired = Subscription(id=9, user_id=9, user=expired_user, plan=plan, expires_at=now - timedelta(seconds=1), is_active=True)

        class Repo:
            def __init__(self, session: Any) -> None:
                pass

            async def list_due_reminders(self, days_before: int, current: datetime | None = None) -> list[Subscription]:
                return [item for item in reminders[days_before] if getattr(item, f"reminder_{days_before}d_sent_at") is None]

            async def mark_reminder_sent(self, subscription: Subscription, days_before: int, current: datetime | None = None) -> Subscription:
                setattr(subscription, f"reminder_{days_before}d_sent_at", current or now)
                return subscription

            async def expire_due(self) -> list[Subscription]:
                if expired.expiration_notified_at is not None:
                    return []
                expired.is_active = False
                expired.expiration_notified_at = now
                return [expired]

        class Bot:
            def __init__(self) -> None:
                self.sent: list[tuple[int, str, Any]] = []

            async def send_message(self, chat_id: int, text: str, reply_markup: Any = None) -> None:
                self.sent.append((chat_id, text, reply_markup))

        class Session:
            async def commit(self) -> None:
                pass

        monkeypatch.setattr(premium_scheduler, "SubscriptionRepository", Repo)
        bot = Bot()
        job = premium_scheduler.PremiumExpirationJob(cast(Any, bot), cast(Any, Session()))
        await job.run()
        await job.run()
        assert len(bot.sent) == 4
        assert any("will expire in 7 days" in item[1] for item in bot.sent)
        assert any("will expire in 3 days" in item[1] for item in bot.sent)
        assert any("will expire tomorrow" in item[1] for item in bot.sent)
        assert any("Premium Subscription Expired" in item[1] for item in bot.sent)

    asyncio.run(scenario())
