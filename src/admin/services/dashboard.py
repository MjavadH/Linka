from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.file import File
from models.sponsor import Sponsor, SponsorCampaign, SponsorRequirement
from models.subscription import Subscription
from models.user import User


@dataclass(frozen=True, slots=True)
class AdminDashboardStats:
    total_users: int
    total_files: int
    active_sponsors: int
    active_premium_users: int


class AdminDashboardService:
    """Read-only dashboard metrics for the admin panel."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_stats(self) -> AdminDashboardStats:
        now = datetime.now(UTC)
        total_users = await self._count(select(func.count(User.id)))
        total_files = await self._count(select(func.count(File.id)))
        active_sponsors = await self._count(
            select(func.count(distinct(Sponsor.id)))
            .select_from(SponsorRequirement)
            .join(SponsorRequirement.sponsor)
            .join(SponsorRequirement.campaign)
            .where(
                Sponsor.is_active.is_(True),
                SponsorRequirement.is_active.is_(True),
                SponsorCampaign.is_active.is_(True),
                (SponsorCampaign.starts_at.is_(None)) | (SponsorCampaign.starts_at <= now),
                (SponsorCampaign.expires_at.is_(None)) | (SponsorCampaign.expires_at > now),
            )
        )
        active_premium_users = await self._count(
            select(func.count(distinct(Subscription.user_id))).where(Subscription.expires_at > now)
        )
        return AdminDashboardStats(
            total_users=total_users,
            total_files=total_files,
            active_sponsors=active_sponsors,
            active_premium_users=active_premium_users,
        )

    async def _count(self, statement: Any) -> int:
        result = await self.session.execute(statement)
        return int(result.scalar_one() or 0)
