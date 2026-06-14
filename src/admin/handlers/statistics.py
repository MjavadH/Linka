from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from admin.callbacks import AdminMenuCallback, AdminNavAction, AdminNavigationCallback, AdminSection
from admin.keyboards import admin_section_keyboard
from admin.services import AdminStatistics, AdminStatisticsService

router = Router(name="admin_statistics")


@router.callback_query(AdminMenuCallback.filter(F.section == AdminSection.STATISTICS))
async def open_statistics(callback: CallbackQuery, session: AsyncSession) -> None:
    await show_statistics(callback, session)


@router.callback_query(
    AdminNavigationCallback.filter(
        (F.target == AdminSection.STATISTICS)
        & (F.action.in_({AdminNavAction.BACK}))
    )
)
async def navigate_statistics(callback: CallbackQuery, session: AsyncSession) -> None:
    await show_statistics(callback, session)


async def show_statistics(callback: CallbackQuery, session: AsyncSession) -> None:
    statistics = await AdminStatisticsService(session).get_statistics()
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            _statistics_text(statistics),
            reply_markup=admin_section_keyboard(AdminSection.STATISTICS),
        )
    await callback.answer()


def _statistics_text(statistics: AdminStatistics) -> str:
    return (
        "📊 <b>Statistics</b>\n\n"
        f"👥 Total Users: <b>{statistics.total_users}</b>\n"
        f"⭐ Premium Users: <b>{statistics.premium_users}</b>\n"
        f"⬇️ Total Downloads: <b>{statistics.total_downloads}</b>\n"
        f"📁 Total Files: <b>{statistics.total_files}</b>"
    )
