from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.download import Download
from models.file import File
from models.subscription import Subscription
from models.user import User


@dataclass(frozen=True, slots=True)
class AdminStatistics:
    total_users: int
    premium_users: int
    total_downloads: int
    total_files: int


class AdminStatisticsService:
    """Aggregates bot-wide counters for admin statistics pages."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_statistics(self) -> AdminStatistics:
        now = datetime.now(UTC)
        total_users = await self._count(select(func.count(User.id)))
        premium_users = await self._count(
            select(func.count(distinct(Subscription.user_id))).where(Subscription.expires_at > now)
        )
        total_downloads = await self._count(select(func.count(Download.id)))
        total_files = await self._count(select(func.count(File.id)))
        return AdminStatistics(
            total_users=total_users,
            premium_users=premium_users,
            total_downloads=total_downloads,
            total_files=total_files,
        )

    async def _count(self, statement: Any) -> int:
        result = await self.session.execute(statement)
        return int(result.scalar_one() or 0)
