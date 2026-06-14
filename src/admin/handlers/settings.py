from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from admin.callbacks import AdminMenuCallback, AdminNavAction, AdminNavigationCallback, AdminSection
from admin.keyboards import admin_section_keyboard
from admin.services import AdminSettingsService, AdminSettingsView
from core.config import Settings

router = Router(name="admin_settings")


@router.callback_query(AdminMenuCallback.filter(F.section == AdminSection.SETTINGS))
async def open_settings(callback: CallbackQuery, settings: Settings) -> None:
    await show_settings(callback, settings)


@router.callback_query(
    AdminNavigationCallback.filter(
        (F.target == AdminSection.SETTINGS)
        & (F.action.in_({AdminNavAction.BACK}))
    )
)
async def navigate_settings(callback: CallbackQuery, settings: Settings) -> None:
    await show_settings(callback, settings)


async def show_settings(callback: CallbackQuery, settings: Settings) -> None:
    settings_view = await AdminSettingsService(settings).get_settings()
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            _settings_text(settings_view),
            reply_markup=admin_section_keyboard(AdminSection.SETTINGS),
        )
    await callback.answer()


def _settings_text(settings_view: AdminSettingsView) -> str:
    return (
        "⚙️ <b>Settings</b>\n\n"
        f"🗑 Delete timeout: <b>{settings_view.delete_timeout_seconds}s</b>\n"
        f"⭐ Premium default duration: <b>{settings_view.premium_default_duration_days} days</b>\n"
        f"📨 Broadcast batch size: <b>{settings_view.broadcast_batch_size}</b>\n"
        f"🗄 Archive chat ID: <b>{settings_view.archive_chat_id or 'not configured'}</b>"
    )
