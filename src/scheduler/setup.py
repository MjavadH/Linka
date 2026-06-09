from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from core.config import Settings
from scheduler.deletions import TemporaryMessageDeletionJob


def setup_scheduler(
    bot: Bot,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="UTC")

    async def run_deletions() -> None:
        async with session_factory() as session:
            await TemporaryMessageDeletionJob(bot, session).run()

    scheduler.add_job(
        run_deletions,
        "interval",
        seconds=settings.scheduler_interval_seconds,
        id="temporary-message-deletions",
        max_instances=1,
        coalesce=True,
    )
    return scheduler
