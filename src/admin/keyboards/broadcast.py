from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from admin.callbacks import AdminBroadcastAction, AdminBroadcastCallback, AdminSection
from admin.keyboards.navigation import navigation_row
from models.enums import BroadcastTargetType


def broadcast_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="👥 All Users",
                    callback_data=AdminBroadcastCallback(action=AdminBroadcastAction.TARGET, target=BroadcastTargetType.ALL).pack(),
                )
            ],
            [
                InlineKeyboardButton(
                    text="⭐ Premium Users",
                    callback_data=AdminBroadcastCallback(action=AdminBroadcastAction.TARGET, target=BroadcastTargetType.PREMIUM).pack(),
                )
            ],
            [
                InlineKeyboardButton(
                    text="🆓 Free Users",
                    callback_data=AdminBroadcastCallback(action=AdminBroadcastAction.TARGET, target=BroadcastTargetType.FREE).pack(),
                )
            ],
            [
                InlineKeyboardButton(
                    text="📜 Broadcast History",
                    callback_data=AdminBroadcastCallback(action=AdminBroadcastAction.HISTORY).pack(),
                )
            ],
            navigation_row(),
        ]
    )


def broadcast_preview_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Start Broadcast", callback_data=AdminBroadcastCallback(action=AdminBroadcastAction.START).pack()),
                InlineKeyboardButton(text="❌ Cancel", callback_data=AdminBroadcastCallback(action=AdminBroadcastAction.CANCEL).pack()),
            ]
        ]
    )


def stop_broadcast_keyboard(job_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⛔ Stop Broadcast", callback_data=AdminBroadcastCallback(action=AdminBroadcastAction.STOP, job_id=job_id).pack())]
        ]
    )


def history_keyboard(job_ids: list[int]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=f"Details #{job_id}", callback_data=AdminBroadcastCallback(action=AdminBroadcastAction.VIEW, job_id=job_id).pack())]
        for job_id in job_ids
    ]
    rows.append(navigation_row(back_to=AdminSection.BROADCAST))
    return InlineKeyboardMarkup(inline_keyboard=rows)
