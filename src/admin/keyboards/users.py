from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from admin.callbacks import AdminSection, AdminUserAction, AdminUserCallback
from admin.keyboards.navigation import back_button, home_button, navigation_row
from models.subscription import PremiumPlan
from models.user import User
from repositories.users import UserListItem, UserPage


def user_management_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔍 Search User", callback_data=AdminUserCallback(action=AdminUserAction.SEARCH).pack()),
                InlineKeyboardButton(text="📋 All Users", callback_data=AdminUserCallback(action=AdminUserAction.LIST_ALL).pack()),
            ],
            [
                InlineKeyboardButton(text="⭐ Premium Users", callback_data=AdminUserCallback(action=AdminUserAction.LIST_PREMIUM).pack()),
                InlineKeyboardButton(text="🚫 Banned Users", callback_data=AdminUserCallback(action=AdminUserAction.LIST_BANNED).pack()),
            ],
            navigation_row(),
        ]
    )

def user_list_keyboard(page: UserPage, action: AdminUserAction) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=_user_list_label(item),
                callback_data=AdminUserCallback(action=AdminUserAction.VIEW, user_id=item.user.id).pack(),
            )
            for item in page.items[i:i + 2]
        ]
        for i in range(0, len(page.items), 2)
    ]
    start = 0 if page.total == 0 else (page.page - 1) * page.per_page + 1
    end = min(page.total, page.page * page.per_page)
    rows.append([InlineKeyboardButton(text=f"Showing {start}-{end} of {page.total} users", callback_data=AdminUserCallback(action=AdminUserAction.NOOP).pack())])
    nav = []
    if page.page > 1:
        nav.append(InlineKeyboardButton(text="⬅️ Previous", callback_data=AdminUserCallback(action=action, page=page.page - 1).pack()))
    nav.append(InlineKeyboardButton(text=f"Page {page.page} / {page.pages}", callback_data=AdminUserCallback(action=AdminUserAction.NOOP).pack()))
    if page.page < page.pages:
        nav.append(InlineKeyboardButton(text="➡️ Next", callback_data=AdminUserCallback(action=action, page=page.page + 1).pack()))
    rows.append(nav)
    rows.append(navigation_row(back_to=AdminSection.USERS))
    return InlineKeyboardMarkup(inline_keyboard=rows)


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


def _user_list_label(item: UserListItem) -> str:
    user = item.user
    prefix = ("🚫" if item.is_banned else "") + ("⭐" if item.has_premium else "")
    name = user.first_name or "User"
    display = f"{name} (@{user.username})" if user.username else name
    return f"{prefix} {display}" if prefix else display
