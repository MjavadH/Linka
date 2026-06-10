from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from models.sponsor import Sponsor, SponsorRequirement


def sponsor_join_keyboard(requirements: list[SponsorRequirement]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=f"Join {item.sponsor.title}", url=item.sponsor.invite_url)]
        for item in requirements
    ]
    rows.append([InlineKeyboardButton(text="I've Joined", callback_data="check_sponsors")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def sponsor_join_keyboard_for_sponsors(sponsors: list[Sponsor]) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=f"Join {item.title}", url=item.invite_url)] for item in sponsors]
    rows.append([InlineKeyboardButton(text="I've Joined", callback_data="check_sponsors")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
