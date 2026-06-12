import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any, cast

from aiogram.exceptions import TelegramForbiddenError

from admin.handlers import broadcast as broadcast_handlers
from models.broadcast import BroadcastJob
from models.enums import BroadcastResultStatus, BroadcastStatus, BroadcastTargetType
from models.subscription import Subscription
from models.user import User
from services.broadcasts import (
    BroadcastJobRunner,
    BroadcastPayload,
    BroadcastService,
    format_final_report,
    format_progress,
)


def test_audience_filtering_uses_active_premium_subscriptions() -> None:
    now = datetime.now(UTC)
    users = [User(id=1, telegram_id=101), User(id=2, telegram_id=102), User(id=3, telegram_id=103)]
    subscriptions = [
        Subscription(user_id=1, is_active=True, expires_at=now + timedelta(days=1)),
        Subscription(user_id=2, is_active=False, expires_at=now + timedelta(days=1)),
        Subscription(user_id=3, is_active=True, expires_at=now - timedelta(days=1)),
    ]

    def audience(target: BroadcastTargetType) -> list[int]:
        premium_ids = {item.user_id for item in subscriptions if item.is_active and item.expires_at > now}
        if target == BroadcastTargetType.PREMIUM:
            return [user.telegram_id for user in users if user.id in premium_ids]
        if target == BroadcastTargetType.FREE:
            return [user.telegram_id for user in users if user.id not in premium_ids]
        return [user.telegram_id for user in users]

    assert audience(BroadcastTargetType.ALL) == [101, 102, 103]
    assert audience(BroadcastTargetType.PREMIUM) == [101]
    assert audience(BroadcastTargetType.FREE) == [102, 103]


def test_preview_workflow_copies_original_message_and_requires_confirmation() -> None:
    async def scenario() -> None:
        class State:
            def __init__(self) -> None:
                self.data: dict[str, Any] = {"target_type": "all", "total_recipients": 12}
                self.state: Any = None

            async def get_data(self) -> dict[str, Any]:
                return self.data

            async def update_data(self, **kwargs: Any) -> None:
                self.data.update(kwargs)

            async def set_state(self, state: Any) -> None:
                self.state = state

        class Bot:
            def __init__(self) -> None:
                self.copied: list[tuple[int, int, int]] = []

            async def copy_message(self, *, chat_id: int, from_chat_id: int, message_id: int) -> Any:
                self.copied.append((chat_id, from_chat_id, message_id))
                return SimpleNamespace(message_id=999)

        class Message:
            def __init__(self) -> None:
                self.chat = SimpleNamespace(id=777)
                self.message_id = 55
                self.answers: list[str] = []
                self.markup: Any = None

            async def answer(self, text: str, reply_markup: Any = None) -> None:
                self.answers.append(text)
                self.markup = reply_markup

        state = State()
        bot = Bot()
        message = Message()
        await broadcast_handlers.receive_broadcast_message(cast(Any, message), cast(Any, state), cast(Any, bot))
        assert bot.copied == [(777, 777, 55)]
        assert state.data["from_chat_id"] == 777
        assert state.data["message_id"] == 55
        assert "Total Estimated Users" in message.answers[0]
        assert "Start Broadcast" in str(message.markup.inline_keyboard)

    asyncio.run(scenario())


def test_queue_processing_respects_batch_size_and_records_final_report() -> None:
    async def scenario() -> None:
        class Bot:
            def __init__(self) -> None:
                self.copied: list[int] = []
                self.edits: list[str] = []
                self.reports: list[str] = []

            async def copy_message(self, *, chat_id: int, from_chat_id: int, message_id: int) -> Any:
                self.copied.append(chat_id)
                return SimpleNamespace(message_id=chat_id + 1000)

            async def edit_message_text(self, **kwargs: Any) -> None:
                self.edits.append(kwargs["text"])

            async def send_message(self, chat_id: int, text: str) -> None:
                self.reports.append(text)

        runner = make_memory_runner(Bot(), [1, 2, 3], batch_size=2)
        await runner.run(1)
        store = runner.session_factory.store
        assert runner.bot.copied == [1, 2, 3]
        assert store.job.status == BroadcastStatus.COMPLETED
        assert store.job.delivered_count == 3
        assert len(store.results) == 3
        assert "Broadcast Completed" in runner.bot.reports[-1]

    asyncio.run(scenario())


def test_cancellation_finishes_safely_after_requested_stop() -> None:
    async def scenario() -> None:
        class Bot:
            def __init__(self) -> None:
                self.copied: list[int] = []
                self.reports: list[str] = []

            async def copy_message(self, *, chat_id: int, from_chat_id: int, message_id: int) -> Any:
                self.copied.append(chat_id)
                if chat_id == 1:
                    runner.cancellation_registry.cancel(1)
                return SimpleNamespace(message_id=chat_id)

            async def edit_message_text(self, **kwargs: Any) -> None:
                pass

            async def send_message(self, chat_id: int, text: str) -> None:
                self.reports.append(text)

        bot = Bot()
        runner = make_memory_runner(bot, [1, 2, 3], batch_size=10)
        await runner.run(1)
        assert bot.copied == [1]
        assert runner.session_factory.store.job.status == BroadcastStatus.CANCELLED
        assert "Broadcast Cancelled" in bot.reports[-1]

    asyncio.run(scenario())


def test_progress_updates_show_counts_and_remaining_percentage() -> None:
    job = BroadcastJob(
        id=1,
        target_type=BroadcastTargetType.ALL,
        status=BroadcastStatus.RUNNING,
        payload={"kind": "copy_message", "from_chat_id": 1, "message_id": 2},
        admin_telegram_id=9,
        total_recipients=10,
        delivered_count=4,
        blocked_count=1,
        delivery_error_count=1,
        other_failure_count=0,
    )
    text = format_progress(job)
    assert "Sent: <b>4</b>" in text
    assert "Blocked: <b>1</b>" in text
    assert "Remaining: <b>4</b>" in text
    assert "Progress: <b>60%</b>" in text


def test_final_reporting_contains_delivery_totals() -> None:
    job = BroadcastJob(
        id=1,
        target_type=BroadcastTargetType.PREMIUM,
        status=BroadcastStatus.COMPLETED,
        payload={"kind": "copy_message", "from_chat_id": 1, "message_id": 2},
        admin_telegram_id=9,
        total_recipients=5,
        delivered_count=3,
        blocked_count=1,
        delivery_error_count=1,
        other_failure_count=0,
        started_at=datetime.now(UTC) - timedelta(seconds=65),
        finished_at=datetime.now(UTC),
    )
    report = format_final_report(job)
    assert "Premium Users" in report
    assert "Delivered:\n<b>3</b>" in report
    assert "Blocked:\n<b>1</b>" in report
    assert "Failed:\n<b>1</b>" in report


def test_blocked_users_are_classified_separately() -> None:
    async def scenario() -> None:
        class Bot:
            async def copy_message(self, **kwargs: Any) -> Any:
                raise TelegramForbiddenError(method=cast(Any, SimpleNamespace()), message="Forbidden: bot was blocked by the user")

        outcome = await BroadcastService(cast(Any, Bot()), rate_limit_per_second=10_000).send_to_user(
            123,
            BroadcastPayload.copy_message(from_chat_id=1, message_id=2),
        )
        assert outcome.status == BroadcastResultStatus.BLOCKED
        assert outcome.error_code == "bot_blocked"

    asyncio.run(scenario())


class MemoryStore:
    def __init__(self, recipients: list[int]) -> None:
        self.recipients = recipients
        self.job = BroadcastJob(
            id=1,
            target_type=BroadcastTargetType.ALL,
            status=BroadcastStatus.DRAFT,
            payload={"kind": "copy_message", "from_chat_id": 10, "message_id": 20},
            admin_telegram_id=999,
            total_recipients=len(recipients),
            progress_message_chat_id=999,
            progress_message_id=111,
        )
        self.results: list[tuple[int, BroadcastResultStatus]] = []


class MemorySession:
    def __init__(self, store: MemoryStore) -> None:
        self.store = store

    async def __aenter__(self) -> "MemorySession":
        return self

    async def __aexit__(self, *_: Any) -> None:
        return None

    async def commit(self) -> None:
        pass


class MemorySessionFactory:
    def __init__(self, recipients: list[int]) -> None:
        self.store = MemoryStore(recipients)

    def __call__(self) -> MemorySession:
        return MemorySession(self.store)


def make_memory_runner(bot: Any, recipients: list[int], batch_size: int) -> BroadcastJobRunner:
    from services import broadcasts as service_module

    class Repo:
        def __init__(self, session: MemorySession) -> None:
            self.store = session.store

        async def get(self, job_id: int) -> BroadcastJob | None:
            return self.store.job if job_id == self.store.job.id else None

        async def mark_running(self, job: BroadcastJob) -> None:
            job.status = BroadcastStatus.RUNNING
            job.started_at = datetime.now(UTC)

        async def list_recipient_telegram_ids(self, target_type: BroadcastTargetType) -> list[int]:
            return self.store.recipients

        async def add_result(self, job: BroadcastJob, *, telegram_id: int, status: BroadcastResultStatus, **kwargs: Any) -> None:
            self.store.results.append((telegram_id, status))
            if status == BroadcastResultStatus.SENT:
                job.delivered_count = (job.delivered_count or 0) + 1
            elif status == BroadcastResultStatus.BLOCKED:
                job.blocked_count = (job.blocked_count or 0) + 1
            elif status == BroadcastResultStatus.DELIVERY_ERROR:
                job.delivery_error_count = (job.delivery_error_count or 0) + 1
            else:
                job.other_failure_count = (job.other_failure_count or 0) + 1

        async def mark_finished(self, job: BroadcastJob, status: BroadcastStatus) -> None:
            job.status = status
            job.finished_at = datetime.now(UTC)

    old_repo = service_module.BroadcastRepository
    service_module.BroadcastRepository = cast(Any, Repo)
    runner = BroadcastJobRunner(
        bot=cast(Any, bot),
        session_factory=cast(Any, MemorySessionFactory(recipients)),
        rate_limit_per_second=10_000,
        batch_size=batch_size,
        progress_interval=0,
    )
    original_run = runner.run

    async def run_and_restore(job_id: int) -> None:
        try:
            await original_run(job_id)
        finally:
            service_module.BroadcastRepository = old_repo

    runner.run = run_and_restore  # type: ignore[method-assign]
    return runner
