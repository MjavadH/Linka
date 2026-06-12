import asyncio
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from aiogram import Bot
from aiogram.exceptions import (
    TelegramAPIError,
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramRetryAfter,
)
from aiogram.types import InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from models.broadcast import BroadcastJob
from models.enums import BroadcastResultStatus, BroadcastStatus, BroadcastTargetType
from repositories.broadcasts import BroadcastRepository


@dataclass(frozen=True)
class BroadcastPayload:
    kind: str
    data: dict[str, str | int | bool | None]

    @classmethod
    def copy_message(cls, *, from_chat_id: int, message_id: int) -> "BroadcastPayload":
        return cls("copy_message", {"from_chat_id": from_chat_id, "message_id": message_id})


@dataclass(frozen=True)
class DeliveryOutcome:
    status: BroadcastResultStatus
    message_id: int | None = None
    error_code: str | None = None
    error_message: str | None = None


class BroadcastCancellationRegistry:
    def __init__(self) -> None:
        self._events: dict[int, asyncio.Event] = {}

    def event(self, job_id: int) -> asyncio.Event:
        return self._events.setdefault(job_id, asyncio.Event())

    def cancel(self, job_id: int) -> None:
        self.event(job_id).set()

    def cleanup(self, job_id: int) -> None:
        self._events.pop(job_id, None)


broadcast_cancellations = BroadcastCancellationRegistry()


class BroadcastService:
    def __init__(self, bot: Bot, rate_limit_per_second: int) -> None:
        self.bot = bot
        self.delay = 1 / max(rate_limit_per_second, 1)

    async def send_to_user(self, telegram_id: int, payload: BroadcastPayload) -> DeliveryOutcome:
        try:
            if payload.kind != "copy_message":
                raise ValueError(f"Unsupported broadcast kind: {payload.kind}")
            copied = await self.bot.copy_message(
                chat_id=telegram_id,
                from_chat_id=int(payload.data["from_chat_id"]),
                message_id=int(payload.data["message_id"]),
            )
            return DeliveryOutcome(BroadcastResultStatus.SENT, copied.message_id)
        except TelegramRetryAfter as exc:
            await asyncio.sleep(float(exc.retry_after))
            return DeliveryOutcome(
                BroadcastResultStatus.DELIVERY_ERROR,
                error_code="flood_wait",
                error_message=f"Flood wait: retry after {exc.retry_after}s",
            )
        except TelegramForbiddenError as exc:
            return DeliveryOutcome(BroadcastResultStatus.BLOCKED, error_code="bot_blocked", error_message=str(exc))
        except TelegramBadRequest as exc:
            error_text = str(exc).lower()
            if any(marker in error_text for marker in ("chat not found", "user is deactivated", "bot was blocked")):
                return DeliveryOutcome(BroadcastResultStatus.BLOCKED, error_code="chat_unavailable", error_message=str(exc))
            return DeliveryOutcome(BroadcastResultStatus.DELIVERY_ERROR, error_code="telegram_bad_request", error_message=str(exc))
        except TelegramAPIError as exc:
            return DeliveryOutcome(BroadcastResultStatus.DELIVERY_ERROR, error_code=exc.__class__.__name__, error_message=str(exc))
        except Exception as exc:  # defensive isolation: one user must never stop the broadcast
            return DeliveryOutcome(BroadcastResultStatus.FAILED, error_code=exc.__class__.__name__, error_message=str(exc))
        finally:
            await asyncio.sleep(self.delay)


class BroadcastJobRunner:
    def __init__(
        self,
        *,
        bot: Bot,
        session_factory: async_sessionmaker[AsyncSession],
        rate_limit_per_second: int,
        batch_size: int,
        progress_interval: float = 5.0,
        cancellation_registry: BroadcastCancellationRegistry = broadcast_cancellations,
    ) -> None:
        self.bot = bot
        self.session_factory = session_factory
        self.sender = BroadcastService(bot, rate_limit_per_second)
        self.batch_size = max(batch_size, 1)
        self.progress_interval = progress_interval
        self.cancellation_registry = cancellation_registry

    async def run(self, job_id: int) -> None:
        started = datetime.now(UTC)
        payload: BroadcastPayload
        recipients: list[int]
        async with self.session_factory() as session:
            repo = BroadcastRepository(session)
            job = await repo.get(job_id)
            if job is None:
                return
            await repo.mark_running(job)
            payload = BroadcastPayload(kind=str(job.payload["kind"]), data=dict(job.payload))
            recipients = await repo.list_recipient_telegram_ids(job.target_type)
            job.total_recipients = len(recipients)
            await session.commit()

        event = self.cancellation_registry.event(job_id)
        last_progress = 0.0
        final_status = BroadcastStatus.COMPLETED
        try:
            for batch_start in range(0, len(recipients), self.batch_size):
                batch = recipients[batch_start : batch_start + self.batch_size]
                for telegram_id in batch:
                    if event.is_set():
                        final_status = BroadcastStatus.CANCELLED
                        break
                    outcome = await self.sender.send_to_user(telegram_id, payload)
                    async with self.session_factory() as session:
                        repo = BroadcastRepository(session)
                        job = await repo.get(job_id)
                        if job is None:
                            return
                        await repo.add_result(
                            job,
                            telegram_id=telegram_id,
                            status=outcome.status,
                            message_id=outcome.message_id,
                            error_code=outcome.error_code,
                            error_message=outcome.error_message,
                        )
                        await session.commit()
                    now = asyncio.get_running_loop().time()
                    if now - last_progress >= self.progress_interval:
                        await self.update_progress(job_id)
                        last_progress = now
                await self.update_progress(job_id)
                if event.is_set():
                    final_status = BroadcastStatus.CANCELLED
                    break
        finally:
            async with self.session_factory() as session:
                repo = BroadcastRepository(session)
                job = await repo.get(job_id)
                if job is not None:
                    await repo.mark_finished(job, final_status)
                    await session.commit()
                    await self.update_progress(job_id)
                    await self.send_final_report(job_id, started)
            self.cancellation_registry.cleanup(job_id)

    async def update_progress(self, job_id: int) -> None:
        async with self.session_factory() as session:
            job = await BroadcastRepository(session).get(job_id)
            if job is None or job.progress_message_chat_id is None or job.progress_message_id is None:
                return
            try:
                await self.bot.edit_message_text(
                    chat_id=job.progress_message_chat_id,
                    message_id=job.progress_message_id,
                    text=format_progress(job),
                    reply_markup=stop_broadcast_keyboard(job.id) if job.status == BroadcastStatus.RUNNING else None,
                )
            except TelegramAPIError:
                return

    async def send_final_report(self, job_id: int, started: datetime | None = None) -> None:
        async with self.session_factory() as session:
            job = await BroadcastRepository(session).get(job_id)
            if job is None:
                return
            text = format_cancelled_report(job) if job.status == BroadcastStatus.CANCELLED else format_final_report(job, started)
            try:
                await self.bot.send_message(job.admin_telegram_id, text)
            except TelegramAPIError:
                return


def chunks(items: Sequence[int], size: int) -> list[Sequence[int]]:
    return [items[index : index + size] for index in range(0, len(items), size)]


def target_label(target_type: BroadcastTargetType) -> str:
    return {
        BroadcastTargetType.ALL: "All Users",
        BroadcastTargetType.PREMIUM: "Premium Users",
        BroadcastTargetType.FREE: "Free Users",
    }[target_type]


def format_progress(job: BroadcastJob) -> str:
    delivered = job.delivered_count or 0
    blocked = job.blocked_count or 0
    delivery_errors = job.delivery_error_count or 0
    other_failures = job.other_failure_count or 0
    total = job.total_recipients or 0
    processed = delivered + blocked + delivery_errors + other_failures
    remaining = max(total - processed, 0)
    percentage = int((processed / total) * 100) if total else 100
    return (
        "📢 <b>Broadcast Progress</b>\n\n"
        f"Sent: <b>{delivered}</b>\n"
        f"Failed: <b>{delivery_errors + other_failures}</b>\n"
        f"Blocked: <b>{blocked}</b>\n"
        f"Remaining: <b>{remaining}</b>\n\n"
        f"Progress: <b>{percentage}%</b>"
    )


def format_duration(started_at: datetime | None, finished_at: datetime | None = None) -> str:
    if started_at is None:
        return "—"
    finish = finished_at or datetime.now(UTC)
    seconds = max(int((finish - started_at).total_seconds()), 0)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes}m {seconds}s"
    return f"{minutes}m {seconds}s"


def format_final_report(job: BroadcastJob, started: datetime | None = None) -> str:
    return (
        "📢 <b>Broadcast Completed</b>\n\n"
        f"Target:\n<b>{target_label(job.target_type)}</b>\n\n"
        f"Total Users:\n<b>{job.total_recipients or 0}</b>\n\n"
        f"Delivered:\n<b>{job.delivered_count or 0}</b>\n\n"
        f"Blocked:\n<b>{job.blocked_count or 0}</b>\n\n"
        f"Failed:\n<b>{(job.delivery_error_count or 0) + (job.other_failure_count or 0)}</b>\n\n"
        f"Duration:\n<b>{format_duration(job.started_at or started, job.finished_at)}</b>"
    )


def format_cancelled_report(job: BroadcastJob) -> str:
    return (
        "📢 <b>Broadcast Cancelled</b>\n\n"
        f"Target:\n<b>{target_label(job.target_type)}</b>\n\n"
        f"Delivered:\n<b>{job.delivered_count or 0}</b>\n\n"
        f"Blocked:\n<b>{job.blocked_count or 0}</b>\n\n"
        f"Failed:\n<b>{(job.delivery_error_count or 0) + (job.other_failure_count or 0)}</b>\n\n"
        "Stopped By:\n<b>Admin</b>"
    )


def stop_broadcast_keyboard(job_id: int) -> InlineKeyboardMarkup:  # intentionally untyped to avoid importing UI layer at module import in tests
    from admin.keyboards.broadcast import stop_broadcast_keyboard as keyboard

    return keyboard(job_id)


def start_broadcast_background(
    *,
    bot: Bot,
    session_factory: async_sessionmaker[AsyncSession],
    job_id: int,
    rate_limit_per_second: int,
    batch_size: int,
    task_factory: Callable[[asyncio.Task[None]], object] | None = None,
) -> asyncio.Task[None]:
    runner = BroadcastJobRunner(
        bot=bot,
        session_factory=session_factory,
        rate_limit_per_second=rate_limit_per_second,
        batch_size=batch_size,
    )
    task = asyncio.create_task(runner.run(job_id), name=f"broadcast:{job_id}")
    if task_factory is not None:
        task_factory(task)
    return task
