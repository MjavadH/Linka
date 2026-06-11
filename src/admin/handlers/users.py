from datetime import UTC, datetime
from html import escape
from typing import Any

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from admin.callbacks import (
    AdminMenuCallback,
    AdminNavAction,
    AdminNavigationCallback,
    AdminSection,
    AdminUserAction,
    AdminUserCallback,
)
from admin.keyboards.users import (
    ban_type_keyboard,
    premium_plan_keyboard,
    user_detail_keyboard,
    user_management_keyboard,
    user_search_results_keyboard,
)
from admin.states.users import AdminUserStates
from models.enums import SponsorStatus
from models.user import User
from models.user_ban import UserBan
from repositories.premium import PremiumPlanRepository
from repositories.users import UserRepository
from services.user_messaging import UserMessagingService
from services.users import ManagedUserDetails, build_user_management_service

router = Router(name="admin_users")


@router.callback_query(AdminMenuCallback.filter(F.section == AdminSection.USERS))
async def open_users(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await show_user_management(callback)


@router.callback_query(
    AdminNavigationCallback.filter(
        (F.target == AdminSection.USERS) & (F.action.in_({AdminNavAction.BACK, AdminNavAction.REFRESH}))
    )
)
async def navigate_users(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await show_user_management(callback)


@router.callback_query(AdminUserCallback.filter(F.action == AdminUserAction.SEARCH))
async def search_user(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(AdminUserStates.waiting_for_search)
    if isinstance(callback.message, Message):
        await callback.message.edit_text("🔍 <b>Search User</b>\n\nSend Telegram ID or username.")
    await callback.answer()


@router.message(AdminUserStates.waiting_for_search, F.text)
async def receive_search(message: Message, state: FSMContext, session: AsyncSession) -> None:
    users = await build_user_management_service(session).search_users(message.text or "")
    if not users:
        await message.answer("❌ User not found.", reply_markup=user_management_keyboard())
        await state.clear()
        return
    if len(users) == 1:
        await state.clear()
        await _send_user_details(message, session, users[0].id)
        return
    await state.clear()
    await message.answer("Select a user:", reply_markup=user_search_results_keyboard(users))


@router.callback_query(AdminUserCallback.filter(F.action == AdminUserAction.VIEW))
async def view_user(callback: CallbackQuery, callback_data: AdminUserCallback, session: AsyncSession) -> None:
    await _edit_user_details(callback, session, callback_data.user_id)


@router.callback_query(AdminUserCallback.filter(F.action == AdminUserAction.GRANT_PREMIUM))
async def grant_premium(callback: CallbackQuery, callback_data: AdminUserCallback, session: AsyncSession) -> None:
    plans = await PremiumPlanRepository(session).list_active()
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            "⭐ <b>Grant Premium</b>\n\nSelect an active plan or use a custom duration.",
            reply_markup=premium_plan_keyboard(callback_data.user_id, plans),
        )
    await callback.answer()


@router.callback_query(AdminUserCallback.filter(F.action == AdminUserAction.GRANT_PLAN))
async def grant_plan(callback: CallbackQuery, callback_data: AdminUserCallback, session: AsyncSession) -> None:
    plan = await PremiumPlanRepository(session).get(callback_data.plan_id)
    user = await UserRepository(session).get_by_telegram_id(callback.from_user.id)
    target = await UserRepository(session).get_details(callback_data.user_id)
    if plan is None or target is None:
        await callback.answer("Plan or user not found", show_alert=True)
        return
    admin_user = user or await UserRepository(session).upsert_from_telegram(callback.from_user.id, callback.from_user.username, callback.from_user.first_name)
    subscription = await build_user_management_service(session).grant_plan(target.id, plan, admin_user.id)
    await _safe_notify(callback, target.telegram_id, "✅ Your premium subscription has been activated.")
    if isinstance(callback.message, Message):
        await callback.message.edit_text(f"✅ Premium activated until {_fmt(subscription.expires_at)}.", reply_markup=user_detail_keyboard(target.id))
    await callback.answer()


@router.callback_query(AdminUserCallback.filter(F.action == AdminUserAction.CUSTOM_PREMIUM))
async def custom_premium(callback: CallbackQuery, callback_data: AdminUserCallback, state: FSMContext) -> None:
    await state.update_data(user_id=callback_data.user_id)
    await state.set_state(AdminUserStates.waiting_for_custom_premium_days)
    if isinstance(callback.message, Message):
        await callback.message.edit_text("Enter duration in days.\n\nExample:\n5\n30\n180")
    await callback.answer()


@router.message(AdminUserStates.waiting_for_custom_premium_days, F.text)
async def receive_custom_premium(message: Message, state: FSMContext, session: AsyncSession) -> None:
    days = _positive_int(message.text or "")
    if days is None:
        await message.answer("Duration must be a positive number of days.")
        return
    data = await state.get_data()
    target = await UserRepository(session).get_details(int(data["user_id"]))
    if target is None or message.from_user is None:
        await message.answer("User not found.")
        await state.clear()
        return
    admin_user = await UserRepository(session).upsert_from_telegram(message.from_user.id, message.from_user.username, message.from_user.first_name)
    subscription = await build_user_management_service(session).grant_custom(target.id, days, admin_user.id)
    await state.clear()
    if message.bot is not None:
        try:
            await message.bot.send_message(target.telegram_id, "✅ Your premium subscription has been activated.")
        except TelegramAPIError:
            pass
    await message.answer(f"✅ Premium activated until {_fmt(subscription.expires_at)}.", reply_markup=user_detail_keyboard(target.id))


@router.callback_query(AdminUserCallback.filter(F.action == AdminUserAction.REMOVE_PREMIUM))
async def remove_premium(callback: CallbackQuery, callback_data: AdminUserCallback, session: AsyncSession) -> None:
    target = await UserRepository(session).get_details(callback_data.user_id)
    if target is None:
        await callback.answer("User not found", show_alert=True)
        return
    await build_user_management_service(session).remove_premium(target.id)
    await _safe_notify(callback, target.telegram_id, "⚠️ Your premium subscription has been removed by administration.")
    await _edit_user_details(callback, session, target.id, notice="✅ Premium removed.")


@router.callback_query(AdminUserCallback.filter(F.action == AdminUserAction.BAN))
async def choose_ban(callback: CallbackQuery, callback_data: AdminUserCallback) -> None:
    if isinstance(callback.message, Message):
        await callback.message.edit_text("🔨 <b>Ban User</b>\n\nSelect ban type.", reply_markup=ban_type_keyboard(callback_data.user_id))
    await callback.answer()


@router.callback_query(AdminUserCallback.filter(F.action == AdminUserAction.BAN_PERMANENT))
async def permanent_ban(callback: CallbackQuery, callback_data: AdminUserCallback, session: AsyncSession) -> None:
    target = await UserRepository(session).get_details(callback_data.user_id)
    if target is None:
        await callback.answer("User not found", show_alert=True)
        return
    await build_user_management_service(session).ban_permanent(target.id)
    await _safe_notify(callback, target.telegram_id, "🚫 You have been banned by the administration.\n\nIf you believe this is a mistake,\nplease contact support.")
    await _edit_user_details(callback, session, target.id, notice="✅ User banned permanently.")


@router.callback_query(AdminUserCallback.filter(F.action == AdminUserAction.BAN_TEMPORARY))
async def temporary_ban(callback: CallbackQuery, callback_data: AdminUserCallback, state: FSMContext) -> None:
    await state.update_data(user_id=callback_data.user_id)
    await state.set_state(AdminUserStates.waiting_for_temporary_ban_days)
    if isinstance(callback.message, Message):
        await callback.message.edit_text("Enter duration in days.\n\nExample:\n5")
    await callback.answer()


@router.message(AdminUserStates.waiting_for_temporary_ban_days, F.text)
async def receive_temporary_ban(message: Message, state: FSMContext, session: AsyncSession) -> None:
    days = _positive_int(message.text or "")
    if days is None:
        await message.answer("Duration must be a positive number of days.")
        return
    data = await state.get_data()
    target = await UserRepository(session).get_details(int(data["user_id"]))
    if target is None:
        await message.answer("User not found.")
        await state.clear()
        return
    await build_user_management_service(session).ban_temporary(target.id, days)
    await state.clear()
    if message.bot is not None:
        try:
            await message.bot.send_message(target.telegram_id, f"🚫 You have been temporarily banned.\n\nBan Duration:\n{days} days\n\nIf you believe this is a mistake,\nplease contact support.")
        except TelegramAPIError:
            pass
    await message.answer("✅ User temporarily banned.", reply_markup=user_detail_keyboard(target.id))


@router.callback_query(AdminUserCallback.filter(F.action == AdminUserAction.UNBAN))
async def unban(callback: CallbackQuery, callback_data: AdminUserCallback, session: AsyncSession) -> None:
    target = await UserRepository(session).get_details(callback_data.user_id)
    if target is None:
        await callback.answer("User not found", show_alert=True)
        return
    await build_user_management_service(session).unban(target.id)
    await _safe_notify(callback, target.telegram_id, "✅ Your access to the bot has been restored.")
    await _edit_user_details(callback, session, target.id, notice="✅ User unbanned.")


@router.callback_query(AdminUserCallback.filter(F.action == AdminUserAction.MESSAGE))
async def message_user(callback: CallbackQuery, callback_data: AdminUserCallback, state: FSMContext) -> None:
    await state.update_data(user_id=callback_data.user_id)
    await state.set_state(AdminUserStates.waiting_for_message)
    if isinstance(callback.message, Message):
        await callback.message.edit_text("📨 Send the message content for this user.")
    await callback.answer()


@router.message(AdminUserStates.waiting_for_message, F.text)
async def receive_message(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    target = await UserRepository(session).get_details(int(data["user_id"]))
    if target is None or message.bot is None:
        await message.answer("User not found.")
        await state.clear()
        return
    delivered = await UserMessagingService(message.bot).send_direct_message(target.telegram_id, message.text or "")
    if delivered:
        await message.answer("✅ Message delivered.", reply_markup=user_detail_keyboard(target.id))
    else:
        await message.answer("❌ Message delivery failed.", reply_markup=user_detail_keyboard(target.id))
    await state.clear()


async def show_user_management(callback: CallbackQuery) -> None:
    if isinstance(callback.message, Message):
        await callback.message.edit_text("👥 <b>User Management</b>", reply_markup=user_management_keyboard())
    await callback.answer()


async def _send_user_details(message: Message, session: AsyncSession, user_id: int) -> None:
    details = await build_user_management_service(session).get_details(user_id)
    if details is None:
        await message.answer("❌ User not found.", reply_markup=user_management_keyboard())
        return
    await message.answer(_details_text(details), reply_markup=user_detail_keyboard(details.user.id))


async def _edit_user_details(callback: CallbackQuery, session: AsyncSession, user_id: int, notice: str | None = None) -> None:
    details = await build_user_management_service(session).get_details(user_id)
    if details is None:
        await callback.answer("User not found", show_alert=True)
        return
    text = _details_text(details)
    if notice:
        text = f"{notice}\n\n{text}"
    if isinstance(callback.message, Message):
        await callback.message.edit_text(text, reply_markup=user_detail_keyboard(details.user.id))
    await callback.answer()


def _details_text(details: ManagedUserDetails) -> str:
    user = details.user
    subscription = details.active_subscription
    ban = details.active_ban
    return (
        "👤 <b>User Information</b>\n\n"
        f"Name:\n{escape(user.first_name or '—')}\n\n"
        f"Username:\n{('@' + escape(user.username)) if user.username else '—'}\n\n"
        f"Telegram ID:\n<code>{user.telegram_id}</code>\n\n"
        f"Internal User ID:\n<code>{user.id}</code>\n\n"
        f"Joined:\n{_fmt(user.joined_at)}\n\n"
        f"Last Seen:\n{_fmt(user.last_seen_at)}\n\n"
        f"Premium Status:\n{_premium_status(subscription)}\n\n"
        f"Ban Status:\n{_ban_status(ban)}\n\n"
        f"Sponsor Status:\n{_sponsor_status(user)}\n\n"
        f"Total Downloads:\n{user.total_downloads}\n\n"
        f"Sponsor Verified At:\n{_fmt(user.sponsor_verified_at)}\n\n"
        f"Last Sponsor Check:\n{_fmt(user.last_sponsor_check_at)}"
    )


def _premium_status(subscription: Any | None) -> str:
    if subscription is None:
        return "Inactive"
    plan_name = subscription.plan.name if getattr(subscription, "plan", None) is not None else "Custom"
    return f"Active\nPlan: {escape(plan_name)}\nExpires: {_fmt(subscription.expires_at)}"


def _ban_status(ban: UserBan | None) -> str:
    if ban is None:
        return "Not Banned"
    if ban.is_permanent:
        return f"Banned\nType: Permanent\nReason: {escape(ban.reason)}"
    return f"Banned\nType: Temporary\nUntil: {_fmt(ban.banned_until)}\nReason: {escape(ban.reason)}"


def _sponsor_status(user: User) -> str:
    label = "Verified" if user.sponsor_status == SponsorStatus.VERIFIED else user.sponsor_status.value.title()
    return escape(label)


def _fmt(value: datetime | None) -> str:
    if value is None:
        return "—"
    if value.tzinfo is not None:
        value = value.astimezone(UTC)
    return value.strftime("%Y-%m-%d %H:%M")


def _positive_int(value: str) -> int | None:
    try:
        number = int(value.strip())
    except ValueError:
        return None
    return number if number > 0 else None


async def _safe_notify(callback: CallbackQuery, telegram_id: int, text: str) -> None:
    if callback.bot is None:
        return
    try:
        await callback.bot.send_message(telegram_id, text)
    except TelegramAPIError:
        await callback.answer("Action saved, but Telegram delivery failed.", show_alert=True)
