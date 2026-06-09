from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from admin.callbacks import AdminMenuCallback, AdminNavAction, AdminNavigationCallback, AdminSection
from admin.keyboards import admin_section_keyboard

router = Router(name="admin_sponsors")


@router.callback_query(AdminMenuCallback.filter(F.section == AdminSection.SPONSORS))
async def open_sponsors(callback: CallbackQuery) -> None:
    await show_sponsors(callback)


@router.callback_query(
    AdminNavigationCallback.filter(
        (F.target == AdminSection.SPONSORS)
        & (F.action.in_({AdminNavAction.BACK, AdminNavAction.REFRESH}))
    )
)
async def navigate_sponsors(callback: CallbackQuery) -> None:
    await show_sponsors(callback)


async def show_sponsors(callback: CallbackQuery) -> None:
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            "📢 <b>Sponsors</b>\n\n"
            "Manage sponsor channels, campaigns, and join requirements.\n\n"
            "Business workflows will be added in the next admin modules.",
            reply_markup=admin_section_keyboard(AdminSection.SPONSORS),
        )
    await callback.answer()
