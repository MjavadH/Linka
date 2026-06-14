from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from admin.callbacks import AdminAnalyticsAction, AdminAnalyticsCallback, AdminSection
from admin.keyboards.navigation import navigation_row


def analytics_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                _button("📈 Overview", AdminAnalyticsAction.OVERVIEW),
                _button("👥 Users", AdminAnalyticsAction.USERS),
            ],
            [
                _button("⭐ Premium", AdminAnalyticsAction.PREMIUM),
                _button("📥 Downloads", AdminAnalyticsAction.DOWNLOADS),
            ],
            [
                _button("🏆 Top Content", AdminAnalyticsAction.TOP_CONTENT),
                _button("🎞 Top Variants", AdminAnalyticsAction.TOP_VARIANTS),
            ],
            [
                _button("🤝 Sponsors", AdminAnalyticsAction.SPONSORS),
                _button("📢 Broadcast Reports", AdminAnalyticsAction.BROADCASTS),
            ],
            [
                _button("📺 Series Analytics", AdminAnalyticsAction.SERIES),
            ],
            navigation_row(),
        ]
    )


def analytics_report_keyboard(action: AdminAnalyticsAction, page: int = 1, has_next: bool = False) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    nav: list[InlineKeyboardButton] = []
    if page > 1:
        nav.append(InlineKeyboardButton(text="⬅️ Previous", callback_data=AdminAnalyticsCallback(action=action, page=page - 1).pack()))
    if has_next:
        nav.append(InlineKeyboardButton(text="➡️ Next", callback_data=AdminAnalyticsCallback(action=action, page=page + 1).pack()))
    if nav:
        rows.append(nav)
    rows.append(navigation_row(back_to=AdminSection.ANALYTICS))
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _button(text: str, action: AdminAnalyticsAction) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=AdminAnalyticsCallback(action=action).pack())
