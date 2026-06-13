from datetime import datetime, time
from math import ceil
from typing import NamedTuple

from sqlalchemy import Select, func, select

from models.audit_log import AuditLog
from repositories.base import BaseRepository


class AuditLogPage(NamedTuple):
    items: list[AuditLog]
    total: int
    page: int
    per_page: int

    @property
    def pages(self) -> int:
        return max(1, ceil(self.total / self.per_page))


class AuditLogRepository(BaseRepository[AuditLog]):
    async def create(self, **values: object) -> AuditLog:
        log = AuditLog(**values)
        self.session.add(log)
        await self.session.flush()
        return log

    async def get(self, log_id: int) -> AuditLog | None:
        return await self.session.get(AuditLog, log_id)

    async def list_page(self, *, page: int = 1, per_page: int = 8, admin_user_id: int | None = None, action: str | None = None, day: datetime | None = None) -> AuditLogPage:
        page = max(1, page)
        query: Select[tuple[AuditLog]] = select(AuditLog)
        if admin_user_id is not None:
            query = query.where(AuditLog.admin_user_id == admin_user_id)
        if action:
            query = query.where(AuditLog.action == action)
        if day is not None:
            start = datetime.combine(day.date(), time.min, tzinfo=day.tzinfo)
            end = datetime.combine(day.date(), time.max, tzinfo=day.tzinfo)
            query = query.where(AuditLog.created_at >= start, AuditLog.created_at <= end)
        total = int(await self.session.scalar(select(func.count()).select_from(query.subquery())) or 0)
        result = await self.session.execute(query.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).offset((page - 1) * per_page).limit(per_page))
        return AuditLogPage(list(result.scalars()), total, page, per_page)

    async def list_admins(self) -> list[tuple[int, str]]:
        result = await self.session.execute(
            select(AuditLog.admin_user_id, func.max(AuditLog.admin_full_name))
            .where(AuditLog.admin_user_id.is_not(None))
            .group_by(AuditLog.admin_user_id)
            .order_by(func.max(AuditLog.created_at).desc())
        )
        return [(int(row[0]), str(row[1] or row[0])) for row in result.all()]
