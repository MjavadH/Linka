from aiogram.types import InlineKeyboardMarkup

from admin.callbacks import AdminSection
from admin.keyboards.navigation import navigation_row


def admin_section_keyboard(section: AdminSection) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[navigation_row()],
    )
