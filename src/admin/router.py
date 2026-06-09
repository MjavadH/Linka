from aiogram import Router

from admin.filters import AdminFilter
from admin.handlers import broadcast, dashboard, files, premium, sponsors, statistics
from admin.handlers import settings as settings_handlers
from core.config import Settings


def create_admin_router(settings: Settings) -> Router:
    """Build the admin panel router with one shared permission gate."""
    router = Router(name="admin")
    admin_filter = AdminFilter(settings.admin_telegram_ids)
    router.message.filter(admin_filter)
    router.callback_query.filter(admin_filter)
    router.include_routers(
        dashboard.router,
        files.router,
        sponsors.router,
        premium.router,
        broadcast.router,
        statistics.router,
        settings_handlers.router,
    )
    return router
