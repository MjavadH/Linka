from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from admin.callbacks import AdminMenuCallback, AdminNavAction, AdminNavigationCallback, AdminSection
from admin.keyboards import admin_section_keyboard

router = Router(name="admin_broadcast")


@router.callback_query(AdminMenuCallback.filter(F.section == AdminSection.BROADCAST))
async def open_broadcast(callback: CallbackQuery) -> None:
    await show_broadcast(callback)


@router.callback_query(
    AdminNavigationCallback.filter(
        (F.target == AdminSection.BROADCAST)
        & (F.action.in_({AdminNavAction.BACK, AdminNavAction.REFRESH}))
    )
)
async def navigate_broadcast(callback: CallbackQuery) -> None:
    await show_broadcast(callback)


async def show_broadcast(callback: CallbackQuery) -> None:
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            "📨 <b>Broadcast</b>\n\n"
            "Prepare announcements and deliver batched messages to users.\n\n"
            "Business workflows will be added in the next admin modules.",
            reply_markup=admin_section_keyboard(AdminSection.BROADCAST),
        )
    await callback.answer()
