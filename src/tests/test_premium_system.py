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

            async def expire_due(self) -> list[Subscription]:
                expired.is_active = False
                return [expired]

        class Bot:
            def __init__(self) -> None:
                self.sent: list[tuple[int, str]] = []

            async def send_message(self, chat_id: int, text: str) -> None:
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
        assert bot.sent == [(500, "⚠️ Your premium subscription has expired.")]
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
