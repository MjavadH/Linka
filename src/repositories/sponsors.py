from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from models.sponsor import Sponsor, SponsorCampaign, SponsorRequirement
from repositories.base import BaseRepository


class SponsorRepository(BaseRepository[Sponsor]):
    async def list_active(self) -> list[Sponsor]:
        result = await self.session.execute(
            select(Sponsor).where(Sponsor.is_active.is_(True)).order_by(Sponsor.priority, Sponsor.id)
        )
        return list(result.scalars())

    async def list_all(self) -> list[Sponsor]:
        result = await self.session.execute(
            select(Sponsor).order_by(Sponsor.is_active.desc(), Sponsor.priority, Sponsor.id)
        )
        return list(result.scalars())

    async def get(self, sponsor_id: int) -> Sponsor | None:
        result = await self.session.execute(select(Sponsor).where(Sponsor.id == sponsor_id))
        return result.scalar_one_or_none()

    async def get_by_chat_id(self, chat_id: int) -> Sponsor | None:
        result = await self.session.execute(select(Sponsor).where(Sponsor.chat_id == chat_id))
        return result.scalar_one_or_none()

    async def create(
        self,
        *,
        chat_id: int,
        title: str,
        invite_url: str,
        channel_username: str | None = None,
        chat_type: str | None = None,
        expiration_type: str = "none",
        expiration_value: str | None = None,
        priority: int = 100,
    ) -> Sponsor:
        sponsor = await self.get_by_chat_id(chat_id)
        if sponsor is None:
            sponsor = Sponsor(chat_id=chat_id)
            self.session.add(sponsor)
        sponsor.title = title
        sponsor.invite_url = invite_url
        sponsor.channel_username = channel_username
        sponsor.chat_type = chat_type
        sponsor.expiration_type = expiration_type
        sponsor.expiration_value = expiration_value
        sponsor.priority = priority
        sponsor.is_active = True
        await self.session.flush()
        return sponsor

    async def update_expiration(
        self, sponsor: Sponsor, expiration_type: str, expiration_value: str | None
    ) -> Sponsor:
        sponsor.expiration_type = expiration_type
        sponsor.expiration_value = expiration_value
        sponsor.updated_at = datetime.now(UTC)
        await self.session.flush()
        return sponsor

    async def update_invite_url(self, sponsor: Sponsor, invite_url: str) -> Sponsor:
        sponsor.invite_url = invite_url
        sponsor.updated_at = datetime.now(UTC)
        await self.session.flush()
        return sponsor

    async def increment_join_counts(self, sponsors: list[Sponsor]) -> None:
        for sponsor in sponsors:
            sponsor.sponsor_join_count = (sponsor.sponsor_join_count or 0) + 1
            sponsor.current_member_count = sponsor.sponsor_join_count
            sponsor.updated_at = datetime.now(UTC)
        await self.session.flush()

    async def deactivate(self, sponsor: Sponsor, reason: str | None = None) -> Sponsor:
        sponsor.is_active = False
        sponsor.updated_at = datetime.now(UTC)
        await self.session.flush()
        return sponsor

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
                Sponsor.is_active.is_(True),
                (SponsorCampaign.starts_at.is_(None)) | (SponsorCampaign.starts_at <= now),
                (SponsorCampaign.expires_at.is_(None)) | (SponsorCampaign.expires_at > now),
            )
            .order_by(SponsorCampaign.priority, SponsorRequirement.priority)
        )
        return list(result.scalars())
