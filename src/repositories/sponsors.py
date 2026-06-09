from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from models.sponsor import SponsorCampaign, SponsorRequirement
from repositories.base import BaseRepository


class SponsorRepository(BaseRepository[SponsorRequirement]):
    async def list_active_requirements(self) -> list[SponsorRequirement]:
        now = datetime.now(UTC)
        result = await self.session.execute(
            select(SponsorRequirement)
            .join(SponsorRequirement.campaign)
            .join(SponsorRequirement.sponsor)
            .options(
                selectinload(SponsorRequirement.sponsor),
                selectinload(SponsorRequirement.campaign),
            )
            .where(
                SponsorRequirement.is_active.is_(True),
                SponsorCampaign.is_active.is_(True),
                (SponsorCampaign.starts_at.is_(None)) | (SponsorCampaign.starts_at <= now),
                (SponsorCampaign.expires_at.is_(None)) | (SponsorCampaign.expires_at > now),
            )
            .order_by(SponsorCampaign.priority, SponsorRequirement.priority)
        )
        return list(result.scalars())
