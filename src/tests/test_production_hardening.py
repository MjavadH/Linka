import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from core.config import Settings
from models.audit_log import AuditLog
from models.subscription import Subscription
from repositories.audit_logs import AuditLogPage
from services.audit_logs import AuditLogService
from services.system import HealthService, SystemNotificationService, validate_startup


class MemoryAuditRepo:
    def __init__(self) -> None:
        self.items: list[AuditLog] = []

    async def create(self, **values: object) -> AuditLog:
        log = AuditLog(id=len(self.items) + 1, created_at=datetime.now(UTC), **values)  # type: ignore[arg-type]
        self.items.append(log)
        return log

    async def get(self, log_id: int) -> AuditLog | None:
        return next((item for item in self.items if item.id == log_id), None)

    async def list_page(self, *, page: int = 1, per_page: int = 8, admin_user_id: int | None = None, action: str | None = None, day: datetime | None = None) -> AuditLogPage:
        data = list(self.items)
        if admin_user_id is not None:
            data = [item for item in data if item.admin_user_id == admin_user_id]
        if action:
            data = [item for item in data if item.action == action]
        if day:
            data = [item for item in data if item.created_at.date() == day.date()]
        data.sort(key=lambda item: item.id, reverse=True)
        return AuditLogPage(data[(page - 1) * per_page : page * per_page], len(data), page, per_page)

    async def list_admins(self) -> list[tuple[int, str]]:
        return [(10, "Ali")]


def test_audit_log_creation_search_filtering_and_pagination() -> None:
    async def scenario() -> None:
        service = AuditLogService(cast(Any, MemoryAuditRepo()))
        admin = cast(Any, type("Admin", (), {"id": 10, "username": "ali", "full_name": "Ali"})())
        for idx in range(12):
            await service.record(admin=admin, action="Grant Premium" if idx % 2 else "Ban User", target_type="User", target_id=100 + idx, details=f"event {idx}")

        first = await service.list_logs(page=1, per_page=8)
        second = await service.list_logs(page=2, per_page=8)
        by_admin = await service.list_logs(page=1, per_page=8, admin_user_id=10)
        by_action = await service.list_logs(page=1, per_page=8, action="Grant Premium")
        by_day = await service.list_logs(page=1, per_page=8, day=datetime.now(UTC))

        assert first.total == 12
        assert len(first.items) == 8
        assert len(second.items) == 4
        assert by_admin.total == 12
        assert by_action.total == 6
        assert by_day.total == 12
        assert (await service.get(first.items[0].id)) is not None

    asyncio.run(scenario())


class FakeSession:
    async def execute(self, *_: Any, **__: Any) -> None:
        return None

    async def get(self, *_: Any, **__: Any) -> None:
        return None

    async def __aenter__(self) -> "FakeSession":
        return self

    async def __aexit__(self, *_: Any) -> None:
        return None


class FakeFactory:
    def __call__(self) -> FakeSession:
        return FakeSession()


def test_health_checks_report_component_statuses() -> None:
    async def scenario() -> None:
        class Bot:
            async def get_me(self) -> Any:
                return type("Me", (), {"id": 99})()

            async def get_chat_member(self, chat_id: int, user_id: int) -> Any:
                return type("Member", (), {"status": "administrator"})()

        settings = Settings(bot_token="1234567890:test-token", bot_username="linka_bot", database_url="postgresql+asyncpg://db", archive_chat_id=-100, admin_telegram_ids=(1,))
        report = await HealthService(bot=cast(Any, Bot()), settings=settings, session_factory=cast(Any, FakeFactory()), scheduler=object()).check()
        assert report.database.healthy
        assert report.archive_channel.healthy
        assert report.bot_api.healthy
        assert report.scheduler.healthy

    asyncio.run(scenario())


def test_startup_validation_fails_for_missing_critical_settings() -> None:
    async def scenario() -> None:
        class Bot:
            async def get_me(self) -> Any:
                return type("Me", (), {"id": 99})()

            async def send_message(self, chat_id: int, text: str) -> None:
                pass

            async def get_chat_member(self, chat_id: int, user_id: int) -> Any:
                return type("Member", (), {"status": "administrator"})()

        settings = Settings(bot_token="1234567890:test-token", bot_username="linka_bot", database_url="postgresql+asyncpg://db")
        try:
            await validate_startup(bot=cast(Any, Bot()), settings=settings, session_factory=cast(Any, FakeFactory()), scheduler=object())
        except RuntimeError as exc:
            assert "ADMIN_TELEGRAM_IDS" in str(exc)
            assert "ARCHIVE_CHAT_ID" in str(exc)
        else:
            raise AssertionError("startup validation should fail")

    asyncio.run(scenario())


def test_admin_notifications_respect_settings_toggle() -> None:
    async def scenario() -> None:
        class Bot:
            def __init__(self) -> None:
                self.messages: list[int] = []

            async def send_message(self, chat_id: int, text: str) -> None:
                self.messages.append(chat_id)

        bot = Bot()
        settings = Settings(bot_token="1234567890:test-token", bot_username="linka_bot", database_url="postgresql+asyncpg://db", admin_telegram_ids=(1, 2))
        notifier = SystemNotificationService(cast(Any, bot), settings, session=None)
        await notifier.notify_admins("Database Failure", "down")
        assert bot.messages == [1, 2]

    asyncio.run(scenario())


def test_cleanup_expired_records_query_model_supports_maintenance_operation() -> None:
    now = datetime.now(UTC)
    expired = Subscription(user_id=1, is_active=True, expires_at=now - timedelta(days=1))
    active = Subscription(user_id=2, is_active=True, expires_at=now + timedelta(days=1))
    records = [s for s in [expired, active] if s.is_active and s.expires_at <= now]
    assert records == [expired]


def test_production_hardening_audit_actions_and_scheduler_jobs() -> None:
    async def scenario() -> None:
        service = AuditLogService(cast(Any, MemoryAuditRepo()))
        admin = cast(Any, type("Admin", (), {"id": 10, "username": "ali", "full_name": "Ali"})())
        required = [
            "Create Movie", "Edit Movie", "Delete Movie", "Create Series", "Edit Series", "Delete Series",
            "Create Episode", "Edit Episode", "Delete Episode", "Create Variant", "Edit Variant", "Delete Variant",
            "Create Sponsor", "Edit Sponsor", "Delete Sponsor", "Create Premium Plan", "Edit Premium Plan",
            "Delete Premium Plan", "Grant Premium", "Remove Premium", "Ban User", "Unban User",
            "Admin Message", "Broadcast Start", "Broadcast Cancel", "Settings Change",
        ]
        for action in required:
            await service.record(admin=admin, action=action, target_type="Target", target_id=1, details="details")
        assert (await service.list_logs(action="Admin Message")).total == 1
        assert (await service.list_logs(action="Create Premium Plan")).items[0].details == "details"

        class Scheduler:
            running = True
            def get_jobs(self) -> list[object]:
                return [object()]

        class EmptyScheduler:
            running = True
            def get_jobs(self) -> list[object]:
                return []

        class Bot:
            async def get_me(self) -> Any:
                return type("Me", (), {"id": 99})()
            async def get_chat_member(self, chat_id: int, user_id: int) -> Any:
                return type("Member", (), {"status": "administrator"})()

        settings = Settings(bot_token="1234567890:test-token", bot_username="linka_bot", database_url="postgresql+asyncpg://db", archive_chat_id=-100, admin_telegram_ids=(1,))
        ok = await HealthService(bot=cast(Any, Bot()), settings=settings, session_factory=cast(Any, FakeFactory()), scheduler=Scheduler()).check()
        failed = await HealthService(bot=cast(Any, Bot()), settings=settings, session_factory=cast(Any, FakeFactory()), scheduler=EmptyScheduler()).check()
        assert ok.scheduler.healthy and ok.scheduler.detail == "Running"
        assert not failed.scheduler.healthy and failed.scheduler.detail == "Failed"

    asyncio.run(scenario())
