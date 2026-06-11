import asyncio

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from admin.router import create_admin_router
from core.config import get_settings
from core.logging import configure_logging
from database.session import create_engine, create_session_factory
from handlers.premium import router as premium_router
from handlers.start import router as start_router
from middlewares.database import DatabaseSessionMiddleware
from scheduler.setup import setup_scheduler


async def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)

    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    bot = Bot(token=settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dispatcher = Dispatcher(settings=settings)
    dispatcher.update.middleware(DatabaseSessionMiddleware(session_factory))
    dispatcher.include_router(create_admin_router(settings))
    dispatcher.include_router(premium_router)
    dispatcher.include_router(start_router)

    scheduler = setup_scheduler(bot, session_factory, settings)
    scheduler.start()
    try:
        await dispatcher.start_polling(bot)
    finally:
        scheduler.shutdown(wait=False)
        await bot.session.close()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
