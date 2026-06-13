from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from admin.callbacks import AdminMenuCallback, AdminSection
from admin.keyboards.navigation import refresh_button


def admin_dashboard_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                _menu_button("📁 File Management", AdminSection.FILES),
                _menu_button("📢 Sponsors", AdminSection.SPONSORS),
            ],
            [
                _menu_button("⭐ Premium", AdminSection.PREMIUM),
                _menu_button("👥 User Management", AdminSection.USERS),
            ],
            [
                _menu_button("📨 Broadcast", AdminSection.BROADCAST),
                _menu_button("📊 Analytics", AdminSection.ANALYTICS),
            ],
            [
                _menu_button("⚙️ Settings", AdminSection.SETTINGS),
                _menu_button("🛠 System", AdminSection.SYSTEM),
            ],
            [refresh_button(AdminSection.DASHBOARD)],
        ]
    )


def _menu_button(text: str, section: AdminSection) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=AdminMenuCallback(section=section).pack())
