from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from models.sponsor import SponsorRequirement


def sponsor_join_keyboard(requirements: list[SponsorRequirement]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=f"Join {item.sponsor.title}", url=item.sponsor.invite_url)]
        for item in requirements
    ]
    rows.append([InlineKeyboardButton(text="Check again", callback_data="check_sponsors")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
