from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from admin.callbacks import AdminMenuCallback, AdminNavAction, AdminNavigationCallback, AdminSection
from admin.keyboards import admin_section_keyboard

router = Router(name="admin_files")


@router.callback_query(AdminMenuCallback.filter(F.section == AdminSection.FILES))
async def open_files(callback: CallbackQuery) -> None:
    await show_files(callback)


@router.callback_query(
    AdminNavigationCallback.filter(
        (F.target == AdminSection.FILES) & (F.action.in_({AdminNavAction.BACK, AdminNavAction.REFRESH}))
    )
)
async def navigate_files(callback: CallbackQuery) -> None:
    await show_files(callback)


async def show_files(callback: CallbackQuery) -> None:
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            "📁 <b>File Management</b>\n\n"
            "Manage uploaded files, variants, and deep links.\n\n"
            "Business workflows will be added in the next admin modules.",
            reply_markup=admin_section_keyboard(AdminSection.FILES),
        )
    await callback.answer()
