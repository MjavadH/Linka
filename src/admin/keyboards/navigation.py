from aiogram.types import InlineKeyboardButton

from admin.callbacks import AdminNavAction, AdminNavigationCallback, AdminSection


def back_button(target: AdminSection) -> InlineKeyboardButton:
    return InlineKeyboardButton(
        text="⬅️ Back",
        callback_data=AdminNavigationCallback(action=AdminNavAction.BACK, target=target).pack(),
    )


def home_button() -> InlineKeyboardButton:
    return InlineKeyboardButton(
        text="🏠 Home",
        callback_data=AdminNavigationCallback(
            action=AdminNavAction.HOME,
            target=AdminSection.DASHBOARD,
        ).pack(),
    )

def navigation_row(
    *,
    back_to: AdminSection | None = AdminSection.DASHBOARD,
    include_home: bool = True,
) -> list[InlineKeyboardButton]:
    buttons: list[InlineKeyboardButton] = []
    if back_to is not None:
        buttons.append(back_button(back_to))
    if include_home:
        buttons.append(home_button())
    return buttons

