from dataclasses import dataclass
from datetime import UTC, datetime

import structlog
from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from core.config import Settings
from core.timezone import validate_timezone
from repositories.settings import SettingsRepository

logger = structlog.get_logger(__name__)

CRITICAL_NOTIFICATION_EVENTS = (
    "Scheduler Failure", "Database Failure", "Archive Channel Failure", "Broadcast Worker Failure",
    "Startup Validation Failure", "Unexpected Critical Errors",
)

@dataclass(frozen=True, slots=True)
class ComponentStatus:
    name: str
    healthy: bool
    detail: str

@dataclass(frozen=True, slots=True)
class HealthReport:
    database: ComponentStatus
    scheduler: ComponentStatus
    archive_channel: ComponentStatus
    broadcast_worker: ComponentStatus
    bot_api: ComponentStatus
    checked_at: datetime

class SystemNotificationService:
    def __init__(self, bot: Bot, settings: Settings, session: AsyncSession | None = None) -> None:
        self.bot = bot
        self.settings = settings
        self.session = session

    async def enabled(self) -> bool:
        if self.session is None:
            return True
        value = await SettingsRepository(self.session).get("system_notifications_enabled")
        return value != "false"

    async def notify_admins(self, event: str, message: str) -> None:
        if not await self.enabled():
            return
        for admin_id in self.settings.admin_telegram_ids:
            try:
                await self.bot.send_message(admin_id, f"🚨 <b>{event}</b>\n\n{message}")
            except TelegramAPIError as exc:
                logger.warning("admin_notification_failed", event=event, admin_id=admin_id, error=str(exc))

class HealthService:
    def __init__(self, *, bot: Bot, settings: Settings, session_factory: async_sessionmaker[AsyncSession] | None = None, session: AsyncSession | None = None, scheduler: object | None = None) -> None:
        self.bot = bot; self.settings = settings; self.session_factory = session_factory; self.session = session; self.scheduler = scheduler
        self.last_report: HealthReport | None = None

    async def check(self) -> HealthReport:
        checked_at = datetime.now(UTC)
        database = await self._check_database()
        archive = await self._check_archive()
        bot_api = await self._check_bot_api()
        scheduler = self._check_scheduler()
        broadcast = ComponentStatus("Broadcast Queue", database.healthy, "Healthy" if database.healthy else "Failed")
        self.last_report = HealthReport(database, scheduler, archive, broadcast, bot_api, checked_at)
        return self.last_report

    def _check_scheduler(self) -> ComponentStatus:
        if self.scheduler is None:
            return ComponentStatus("Scheduler", False, "Failed")
        running = bool(getattr(self.scheduler, "running", False))
        if not running and getattr(self.scheduler, "state", None) == 1:
            running = True
        if not hasattr(self.scheduler, "get_jobs"):
            return ComponentStatus("Scheduler", True, "Running")
        try:
            jobs = list(self.scheduler.get_jobs())
        except Exception as exc:
            logger.error("health_scheduler_failed", error=str(exc))
            return ComponentStatus("Scheduler", False, "Failed")
        healthy = running and bool(jobs)
        return ComponentStatus("Scheduler", healthy, "Running" if healthy else "Failed")

    async def _check_database(self) -> ComponentStatus:
        try:
            if self.session is not None:
                await self.session.execute(text("SELECT 1"))
            elif self.session_factory is not None:
                async with self.session_factory() as session:
                    await session.execute(text("SELECT 1"))
            return ComponentStatus("Database", True, "Healthy")
        except Exception as exc:
            logger.error("health_database_failed", error=str(exc))
            return ComponentStatus("Database", False, str(exc))

    async def _check_archive(self) -> ComponentStatus:
        if self.settings.archive_chat_id is None:
            return ComponentStatus("Archive Channel", False, "Not configured")
        try:
            me = await self.bot.get_me()
            member = await self.bot.get_chat_member(self.settings.archive_chat_id, me.id)
            ok = member.status in {"administrator", "creator"}
            return ComponentStatus("Archive Channel", ok, "Accessible" if ok else "Bot is not admin")
        except Exception as exc:
            logger.error("health_archive_failed", error=str(exc))
            return ComponentStatus("Archive Channel", False, str(exc))

    async def _check_bot_api(self) -> ComponentStatus:
        try:
            await self.bot.get_me()
            return ComponentStatus("Bot API", True, "Online")
        except Exception as exc:
            logger.error("health_bot_api_failed", error=str(exc))
            return ComponentStatus("Bot API", False, str(exc))

async def validate_startup(*, bot: Bot, settings: Settings, session_factory: async_sessionmaker[AsyncSession], scheduler: object) -> None:
    errors: list[str] = []
    try:
        validate_timezone(settings.timezone)
        logger.info("timezone_configured", timezone=settings.timezone)
    except ValueError as exc:
        errors.append(str(exc))
    if not settings.admin_telegram_ids: errors.append("ADMIN_TELEGRAM_IDS is required")
    if settings.archive_chat_id is None: errors.append("ARCHIVE_CHAT_ID is required")
    report = await HealthService(bot=bot, settings=settings, session_factory=session_factory, scheduler=scheduler).check()
    for status in [report.database, report.archive_channel, report.bot_api, report.scheduler]:
        if not status.healthy: errors.append(f"{status.name}: {status.detail}")
    if errors:
        message = "; ".join(errors)
        logger.error("startup_validation_failed", errors=errors)
        async with session_factory() as session:
            await SystemNotificationService(bot, settings, session).notify_admins("Startup Validation Failure", message)
        raise RuntimeError(f"Startup validation failed: {message}")
