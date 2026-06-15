from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from admin.callbacks import AdminSection, AdminUserAction, AdminUserCallback
from admin.keyboards.navigation import back_button, home_button, navigation_row
from models.subscription import PremiumPlan
from models.user import User


def user_management_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔍 Search User", callback_data=AdminUserCallback(action=AdminUserAction.SEARCH).pack())],
            navigation_row(),
        ]
    )


def user_search_results_keyboard(users: list[User]) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=_user_label(user),
                callback_data=AdminUserCallback(action=AdminUserAction.VIEW, user_id=user.id).pack(),
            )
        ]
        for user in users
    ]
    rows.append(navigation_row(back_to=AdminSection.USERS))
    return InlineKeyboardMarkup(inline_keyboard=rows)


def user_detail_keyboard(
    user_id: int,
    *,
    is_banned: bool,
    has_premium: bool,
) -> InlineKeyboardMarkup:
    rows = []

    premium_row = [
        InlineKeyboardButton(
            text="⭐ Grant Premium",
            callback_data=AdminUserCallback(
                action=AdminUserAction.GRANT_PREMIUM,
                user_id=user_id,
            ).pack(),
        )
    ]

    if has_premium:
        premium_row.append(
            InlineKeyboardButton(
                text="❌ Remove Premium",
                callback_data=AdminUserCallback(
                    action=AdminUserAction.REMOVE_PREMIUM,
                    user_id=user_id,
                ).pack(),
            )
        )

    rows.append(premium_row)

    if is_banned:
        rows.append([
            InlineKeyboardButton(
                text="✅ Unban User",
                callback_data=AdminUserCallback(
                    action=AdminUserAction.UNBAN,
                    user_id=user_id,
                ).pack(),
                style="success"
            )
        ])
    else:
        rows.append([
            InlineKeyboardButton(
                text="⛔️ Ban User",
                callback_data=AdminUserCallback(
                    action=AdminUserAction.BAN,
                    user_id=user_id,
                ).pack(),
                style="danger"
            )
        ])

    rows.append([
        InlineKeyboardButton(
            text="📨 Send Message",
            callback_data=AdminUserCallback(
                action=AdminUserAction.MESSAGE,
                user_id=user_id,
            ).pack(),
        )
    ])

    rows.append([
        back_button(AdminSection.USERS),
        home_button(),
    ])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def premium_plan_keyboard(user_id: int, plans: list[PremiumPlan]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=plan.name, callback_data=AdminUserCallback(action=AdminUserAction.GRANT_PLAN, user_id=user_id, plan_id=plan.id).pack())]
        for plan in plans
    ]
    rows.append([InlineKeyboardButton(text="⚙️ Custom Duration", callback_data=AdminUserCallback(action=AdminUserAction.CUSTOM_PREMIUM, user_id=user_id).pack())])
    rows.append([InlineKeyboardButton(text="⬅️ Back", callback_data=AdminUserCallback(action=AdminUserAction.VIEW, user_id=user_id).pack())])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def ban_type_keyboard(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⛔ Permanent Ban", callback_data=AdminUserCallback(action=AdminUserAction.BAN_PERMANENT, user_id=user_id).pack())],
            [InlineKeyboardButton(text="⏳ Temporary Ban", callback_data=AdminUserCallback(action=AdminUserAction.BAN_TEMPORARY, user_id=user_id).pack())],
            [InlineKeyboardButton(text="⬅️ Back", callback_data=AdminUserCallback(action=AdminUserAction.VIEW, user_id=user_id).pack())],
        ]
    )

def cancel_action_keyboard(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Cancel", callback_data=AdminUserCallback(action=AdminUserAction.VIEW, user_id=user_id).pack())]
        ]
    )

def _user_label(user: User) -> str:
    name = user.first_name or "User"
    username = f"@{user.username}" if user.username else "no username"
    return f"{name} ({username}) · {user.telegram_id}"
