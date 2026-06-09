from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from admin.callbacks import AdminMenuCallback, AdminNavAction, AdminNavigationCallback, AdminSection
from admin.keyboards import admin_section_keyboard

router = Router(name="admin_premium")


@router.callback_query(AdminMenuCallback.filter(F.section == AdminSection.PREMIUM))
async def open_premium(callback: CallbackQuery) -> None:
    await show_premium(callback)


@router.callback_query(
    AdminNavigationCallback.filter(
        (F.target == AdminSection.PREMIUM)
        & (F.action.in_({AdminNavAction.BACK, AdminNavAction.REFRESH}))
    )
)
async def navigate_premium(callback: CallbackQuery) -> None:
    await show_premium(callback)


async def show_premium(callback: CallbackQuery) -> None:
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            "⭐ <b>Premium</b>\n\n"
            "Manage premium grants, extensions, and subscription audits.\n\n"
            "Business workflows will be added in the next admin modules.",
            reply_markup=admin_section_keyboard(AdminSection.PREMIUM),
        )
    await callback.answer()
