from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def user_main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👤 My Account")],
            [KeyboardButton(text="⭐ Buy Subscription"), KeyboardButton(text="🛠 Support")],
        ],
        resize_keyboard=True,
    )
