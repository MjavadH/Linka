from dataclasses import dataclass

from aiogram import Bot
from aiogram.enums import ChatMemberStatus

from models.sponsor import SponsorRequirement
from repositories.sponsors import SponsorRepository


@dataclass(frozen=True)
class SponsorCheckResult:
    passed: bool
    missing_requirements: list[SponsorRequirement]


class SponsorService:
    def __init__(self, repository: SponsorRepository, bot: Bot) -> None:
        self.repository = repository
        self.bot = bot

    async def check_user(self, telegram_id: int) -> SponsorCheckResult:
        missing: list[SponsorRequirement] = []
        requirements = await self.repository.list_active_requirements()
        for requirement in requirements:
            sponsor = requirement.sponsor
            if not sponsor.is_active:
                continue
            if requirement.campaign.target_member_count is not None:
                current = sponsor.current_member_count or 0
                if current >= requirement.campaign.target_member_count:
                    continue
            member = await self.bot.get_chat_member(sponsor.chat_id, telegram_id)
            if member.status in {ChatMemberStatus.LEFT, ChatMemberStatus.KICKED}:
                missing.append(requirement)
        return SponsorCheckResult(passed=not missing, missing_requirements=missing)
