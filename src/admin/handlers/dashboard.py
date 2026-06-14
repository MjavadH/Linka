from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from admin.callbacks import AdminNavAction, AdminNavigationCallback, AdminSection
from admin.keyboards import admin_dashboard_keyboard
from admin.services import AdminDashboardService, AdminDashboardStats

router = Router(name="admin_dashboard")


@router.message(CommandStart())
async def open_dashboard(message: Message, session: AsyncSession) -> None:
    stats = await AdminDashboardService(session).get_stats()
    await message.answer(_dashboard_text(stats), reply_markup=admin_dashboard_keyboard())


@router.callback_query(
    AdminNavigationCallback.filter(
        (F.action.in_({AdminNavAction.BACK, AdminNavAction.HOME}))
        & (F.target == AdminSection.DASHBOARD)
    )
)

async def navigate_dashboard(
    callback: CallbackQuery,
    session: AsyncSession,
) -> None:
    stats = await AdminDashboardService(session).get_stats()
    await _edit_callback_message(
        callback,
        _dashboard_text(stats),
    )
    await callback.answer()

async def _edit_callback_message(callback: CallbackQuery, text: str) -> None:
    if isinstance(callback.message, Message):
        await callback.message.edit_text(text, reply_markup=admin_dashboard_keyboard())


def _dashboard_text(stats: AdminDashboardStats) -> str:
    return (
        "🛡 <b>Linka Admin Panel</b>\n\n"
        "📌 <b>Dashboard</b>\n"
        f"👥 Total Users: <b>{stats.total_users}</b>\n"
        f"📁 Total Files: <b>{stats.total_files}</b>\n"
        f"📢 Active Sponsors: <b>{stats.active_sponsors}</b>\n"
        f"⭐ Active Premium Users: <b>{stats.active_premium_users}</b>"
    )
