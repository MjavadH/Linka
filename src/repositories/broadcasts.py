from datetime import UTC, datetime

from sqlalchemy import Select, func, select

from models.broadcast import BroadcastJob, BroadcastResult
from models.enums import BroadcastResultStatus, BroadcastStatus, BroadcastTargetType
from models.subscription import Subscription
from models.user import User
from repositories.base import BaseRepository


class BroadcastRepository(BaseRepository[BroadcastJob]):
    async def create_job(
        self,
        *,
        target_type: BroadcastTargetType,
        payload: dict[str, str | int | bool | None],
        admin_telegram_id: int,
        total_recipients: int,
    ) -> BroadcastJob:
        job = BroadcastJob(
            target_type=target_type,
            payload=payload,
            admin_telegram_id=admin_telegram_id,
            total_recipients=total_recipients,
            status=BroadcastStatus.DRAFT,
        )
        self.session.add(job)
        await self.session.flush()
        return job

    async def get(self, job_id: int) -> BroadcastJob | None:
        return await self.session.get(BroadcastJob, job_id)

    async def list_recent(self, limit: int = 10) -> list[BroadcastJob]:
        result = await self.session.execute(
            select(BroadcastJob).order_by(BroadcastJob.created_at.desc(), BroadcastJob.id.desc()).limit(limit)
        )
        return list(result.scalars())

    async def mark_running(self, job: BroadcastJob) -> None:
        now = datetime.now(UTC)
        job.status = BroadcastStatus.RUNNING
        job.started_at = now
        job.updated_at = now
        await self.session.flush()

    async def mark_finished(self, job: BroadcastJob, status: BroadcastStatus) -> None:
        now = datetime.now(UTC)
        job.status = status
        job.finished_at = now
        job.updated_at = now
        await self.session.flush()

    async def request_cancel(self, job: BroadcastJob) -> None:
        job.status = BroadcastStatus.CANCELLED
        job.updated_at = datetime.now(UTC)
        await self.session.flush()

    async def set_progress_message(self, job: BroadcastJob, *, chat_id: int, message_id: int) -> None:
        job.progress_message_chat_id = chat_id
        job.progress_message_id = message_id
        job.updated_at = datetime.now(UTC)
        await self.session.flush()

    async def add_result(
        self,
        job: BroadcastJob,
        *,
        telegram_id: int,
        status: BroadcastResultStatus,
        message_id: int | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> BroadcastResult:
        result = BroadcastResult(
            job_id=job.id,
            telegram_id=telegram_id,
            status=status,
            message_id=message_id,
            error_code=error_code,
            error_message=error_message,
            sent_at=datetime.now(UTC) if status == BroadcastResultStatus.SENT else None,
        )
        self.session.add(result)
        if status == BroadcastResultStatus.SENT:
            job.delivered_count = (job.delivered_count or 0) + 1
        elif status == BroadcastResultStatus.BLOCKED:
            job.blocked_count = (job.blocked_count or 0) + 1
        elif status == BroadcastResultStatus.DELIVERY_ERROR:
            job.delivery_error_count = (job.delivery_error_count or 0) + 1
        else:
            job.other_failure_count = (job.other_failure_count or 0) + 1
        job.updated_at = datetime.now(UTC)
        await self.session.flush()
        return result

    async def count_recipients(self, target_type: BroadcastTargetType) -> int:
        return int(await self.session.scalar(self._audience_query(target_type, count=True)) or 0)

    async def list_recipient_telegram_ids(self, target_type: BroadcastTargetType) -> list[int]:
        result = await self.session.execute(self._audience_query(target_type, count=False))
        return list(result.scalars())

    def _audience_query(self, target_type: BroadcastTargetType, *, count: bool) -> Select[tuple[int]]:
        active_subscribers = (
            select(Subscription.user_id)
            .where(Subscription.is_active.is_(True), Subscription.expires_at > datetime.now(UTC))
            .distinct()
        )
        column = func.count(User.id) if count else User.telegram_id
        query = select(column)
        if target_type == BroadcastTargetType.PREMIUM:
            query = query.where(User.id.in_(active_subscribers))
        elif target_type == BroadcastTargetType.FREE:
            query = query.where(User.id.not_in(active_subscribers))
        if not count:
            query = query.order_by(User.id)
        return query
