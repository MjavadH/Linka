import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, cast

from models.subscription import PremiumPlan, Subscription
from models.user import User
from models.user_ban import UserBan
from scheduler.user_bans import UserBanExpirationJob
from services.file_delivery import FileDeliveryService
from services.premium import PremiumService
from services.user_messaging import UserMessagingService
from services.users import UserManagementService


class FakeUsers:
    def __init__(self) -> None:
        self.users = [
            User(id=1, telegram_id=1001, username="alice", first_name="Alice"),
            User(id=2, telegram_id=1002, username="alice_support", first_name="Alice S"),
        ]

    async def search(self, query: str) -> list[User]:
        q = query.strip().lstrip("@")
        return [u for u in self.users if str(u.telegram_id) == q or u.username == q]

    async def get_details(self, user_id: int) -> User | None:
        return next((u for u in self.users if u.id == user_id), None)


class FakeSubscriptionRepo:
    def __init__(self) -> None:
        self.items: list[Subscription] = []

    async def has_active_subscription(self, user_id: int) -> bool:
        return await self.get_active_subscription(user_id) is not None

    async def get_active_subscription(self, user_id: int) -> Subscription | None:
        active = [item for item in self.items if item.user_id == user_id and item.is_active and item.expires_at > datetime.now(UTC)]
        return max(active, key=lambda item: item.expires_at, default=None)

    async def activate(self, *, user_id: int, plan: PremiumPlan, admin_id: int | None = None, note: str | None = None, **_: Any) -> Subscription:
        now = datetime.now(UTC)
        sub = Subscription(id=len(self.items) + 1, user_id=user_id, plan_id=plan.id, plan=plan, starts_at=now, expires_at=now + timedelta(days=plan.duration_days), is_active=True, granted_by_admin_id=admin_id, note=note)
        self.items.append(sub)
        return sub

    async def extend(self, user_id: int, duration: timedelta, admin_id: int | None = None, note: str | None = None, **_: Any) -> Subscription:
        now = datetime.now(UTC)
        sub = Subscription(id=len(self.items) + 1, user_id=user_id, starts_at=now, expires_at=now + duration, is_active=True, granted_by_admin_id=admin_id, note=note)
        self.items.append(sub)
        return sub

    async def expire_subscription(self, subscription: Subscription) -> Subscription:
        subscription.is_active = False
        return subscription


class FakeBans:
    def __init__(self) -> None:
        self.items: list[UserBan] = []

    async def get_active_for_user(self, user_id: int, now: datetime | None = None) -> UserBan | None:
        moment = now or datetime.now(UTC)
        return next((b for b in self.items if b.user_id == user_id and b.is_active and (b.is_permanent or (b.banned_until and b.banned_until > moment))), None)

    async def ban_permanent(self, user_id: int, reason: str = "admin_ban") -> UserBan:
        await self.deactivate_active(user_id)
        ban = UserBan(id=len(self.items) + 1, user_id=user_id, is_active=True, is_permanent=True, reason=reason)
        self.items.append(ban)
        return ban

    async def ban_temporary(self, user_id: int, banned_until: datetime, reason: str = "admin_ban") -> UserBan:
        await self.deactivate_active(user_id)
        ban = UserBan(id=len(self.items) + 1, user_id=user_id, is_active=True, is_permanent=False, banned_until=banned_until, reason=reason)
        self.items.append(ban)
        return ban

    async def deactivate_active(self, user_id: int) -> list[UserBan]:
        active = [b for b in self.items if b.user_id == user_id and b.is_active]
        for ban in active:
            ban.is_active = False
        return active


def test_user_search_by_telegram_id_and_username() -> None:
    async def scenario() -> None:
        service = UserManagementService(cast(Any, FakeUsers()), cast(Any, FakeBans()), cast(Any, PremiumService(cast(Any, FakeSubscriptionRepo()))))
        assert [u.telegram_id for u in await service.search_users("1001")] == [1001]
        assert [u.telegram_id for u in await service.search_users("@alice")] == [1001]
        assert await service.search_users("missing") == []

    asyncio.run(scenario())


def test_user_management_grants_and_removes_premium_using_premium_service() -> None:
    async def scenario() -> None:
        repo = FakeSubscriptionRepo()
        service = UserManagementService(cast(Any, FakeUsers()), cast(Any, FakeBans()), PremiumService(cast(Any, repo)))
        plan = PremiumPlan(id=9, name="Gold", duration_days=30, price=Decimal("10"), is_active=True)
        sub = await service.grant_plan(1, plan, admin_user_id=99)
        assert sub.plan_id == 9
        assert sub.granted_by_admin_id == 99
        assert await PremiumService(cast(Any, repo)).has_premium(1) is True
        await service.remove_premium(1)
        assert await PremiumService(cast(Any, repo)).has_premium(1) is False

    asyncio.run(scenario())


def test_user_management_temporary_and_permanent_bans() -> None:
    async def scenario() -> None:
        bans = FakeBans()
        service = UserManagementService(cast(Any, FakeUsers()), cast(Any, bans), PremiumService(cast(Any, FakeSubscriptionRepo())))
        temporary = await service.ban_temporary(1, 5)
        assert temporary.is_active is True
        assert temporary.is_permanent is False
        assert temporary.banned_until and temporary.banned_until > datetime.now(UTC) + timedelta(days=4)
        permanent = await service.ban_permanent(1)
        assert temporary.is_active is False
        assert permanent.is_active is True
        assert permanent.is_permanent is True
        assert permanent.reason == "admin_ban"

    asyncio.run(scenario())


def test_automatic_unban_expires_temporary_bans_and_notifies(monkeypatch: Any) -> None:
    async def scenario() -> None:
        expired_user = User(id=1, telegram_id=12345)
        expired_ban = UserBan(id=1, user_id=1, user=expired_user, is_active=True, is_permanent=False, banned_until=datetime.now(UTC) - timedelta(seconds=1))

        class Repo:
            def __init__(self, session: Any) -> None:
                pass

            async def expire_due(self) -> list[UserBan]:
                expired_ban.is_active = False
                return [expired_ban]

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

        import scheduler.user_bans as scheduler_module

        monkeypatch.setattr(scheduler_module, "UserBanRepository", Repo)
        bot = Bot()
        session = Session()
        await UserBanExpirationJob(cast(Any, bot), cast(Any, session)).run()
        assert expired_ban.is_active is False
        assert bot.sent == [(12345, "✅ Your temporary ban has expired.\n\nYou can now use the bot normally.")]
        assert session.committed is True

    asyncio.run(scenario())


def test_file_access_restricted_for_banned_users() -> None:
    async def scenario() -> None:
        class DeepLinks:
            called = False

            async def get_active_by_token(self, token: str) -> Any:
                self.called = True
                return None

        class Bans:
            async def get_active_for_user(self, user_id: int) -> UserBan:
                return UserBan(id=1, user_id=user_id, is_active=True, is_permanent=True)

        deep_links = DeepLinks()
        service = FileDeliveryService(
            bot=cast(Any, object()),
            deep_links=cast(Any, deep_links),
            variants=cast(Any, object()),
            sponsors=cast(Any, object()),
            premium=cast(Any, object()),
            temporary_messages=cast(Any, object()),
            downloads=cast(Any, object()),
            storage=cast(Any, object()),
            delete_after_seconds=60,
            bans=cast(Any, Bans()),
        )
        result = await service.deliver("token", user_id=1, telegram_id=10, chat_id=20)
        assert result.delivered is False
        assert result.reason == "banned"
        assert deep_links.called is False

    asyncio.run(scenario())


def test_direct_messaging_delivers_only_selected_user() -> None:
    async def scenario() -> None:
        class Bot:
            def __init__(self) -> None:
                self.sent: list[tuple[int, str]] = []

            async def send_message(self, chat_id: int, text: str) -> None:
                self.sent.append((chat_id, text))

        bot = Bot()
        delivered = await UserMessagingService(cast(Any, bot)).send_direct_message(555, "hello")
        assert delivered is True
        assert bot.sent == [(555, "hello")]

    asyncio.run(scenario())
