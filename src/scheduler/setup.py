from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore[import-untyped]
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from core.config import Settings
from scheduler.deletions import TemporaryMessageDeletionJob
from scheduler.sponsors import SponsorExpirationJob, SponsorVerificationJob


def setup_scheduler(
    bot: Bot,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="UTC")

    sponsor_cursor: int | None = None

    async def run_deletions() -> None:
        async with session_factory() as session:
            await TemporaryMessageDeletionJob(bot, session).run()

    async def run_sponsor_verification() -> None:
        nonlocal sponsor_cursor
        async with session_factory() as session:
            next_cursor = await SponsorVerificationJob(bot, session, settings).run(sponsor_cursor)
            sponsor_cursor = next_cursor
            if next_cursor is None:
                sponsor_cursor = None

    async def run_sponsor_expiration() -> None:
        async with session_factory() as session:
            await SponsorExpirationJob(bot, session, settings).run()

    scheduler.add_job(
        run_deletions,
        "interval",
        seconds=settings.scheduler_interval_seconds,
        id="temporary-message-deletions",
        max_instances=1,
        coalesce=True,
    )

    scheduler.add_job(
        run_sponsor_verification,
        "interval",
        seconds=settings.sponsor_verification_interval_seconds,
        id="sponsor-verification",
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        run_sponsor_expiration,
        "interval",
        seconds=settings.sponsor_verification_interval_seconds,
        id="sponsor-expiration",
        max_instances=1,
        coalesce=True,
    )
    return scheduler
