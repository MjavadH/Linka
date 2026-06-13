from decimal import Decimal, InvalidOperation

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from admin.callbacks import (
    AdminMenuCallback,
    AdminNavAction,
    AdminNavigationCallback,
    AdminPremiumAction,
    AdminPremiumCallback,
    AdminSection,
)
from admin.keyboards.navigation import navigation_row
from admin.states.premium import AdminPremiumStates
from core.config import Settings
from handlers.premium import format_money
from repositories.premium import PremiumPlanRepository
from repositories.audit_logs import AuditLogRepository
from repositories.settings import SettingsRepository
from repositories.subscriptions import SubscriptionRepository
from repositories.users import UserRepository
from services.premium import PremiumService
from services.audit_logs import AuditLogService
from services.settings import PREMIUM_SETTING_KEYS, PremiumSettingsService

router = Router(name="admin_premium")


@router.callback_query(AdminMenuCallback.filter(F.section == AdminSection.PREMIUM))
async def open_premium(callback: CallbackQuery) -> None:
    await show_premium(callback)


@router.callback_query(AdminNavigationCallback.filter((F.target == AdminSection.PREMIUM) & (F.action.in_({AdminNavAction.BACK, AdminNavAction.REFRESH}))))
async def navigate_premium(callback: CallbackQuery) -> None:
    await show_premium(callback)


@router.callback_query(AdminPremiumCallback.filter(F.action == AdminPremiumAction.PLANS))
async def premium_plans(callback: CallbackQuery, session: AsyncSession) -> None:
    await show_plans(callback, session)


@router.callback_query(AdminPremiumCallback.filter(F.action == AdminPremiumAction.PLAN_ADD))
async def add_plan(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(AdminPremiumStates.waiting_for_plan_name)
    if isinstance(callback.message, Message):
        await callback.message.edit_text("Send plan name, for example: Silver")
    await callback.answer()


@router.message(AdminPremiumStates.waiting_for_plan_name)
async def receive_plan_name(message: Message, state: FSMContext) -> None:
    name = (message.text or "").strip()
    if not name:
        await message.answer("Plan name is required.")
        return
    await state.update_data(name=name)
    await state.set_state(AdminPremiumStates.waiting_for_plan_duration)
    await message.answer("Send duration in days, for example: 30")


@router.message(AdminPremiumStates.waiting_for_plan_duration)
async def receive_plan_duration(message: Message, state: FSMContext) -> None:
    try:
        duration = int((message.text or "").strip())
    except ValueError:
        await message.answer("Duration must be a positive integer.")
        return
    if duration <= 0:
        await message.answer("Duration must be greater than zero.")
        return
    await state.update_data(duration_days=duration)
    await state.set_state(AdminPremiumStates.waiting_for_plan_price)
    await message.answer("Send price, for example: 100000")


@router.message(AdminPremiumStates.waiting_for_plan_price)
async def receive_plan_price(message: Message, state: FSMContext) -> None:
    try:
        price = Decimal((message.text or "").replace(",", "").strip())
    except InvalidOperation:
        await message.answer("Price must be a number.")
        return
    if price < 0:
        await message.answer("Price cannot be negative.")
        return
    await state.update_data(price=str(price))
    await state.set_state(AdminPremiumStates.waiting_for_plan_description)
    await message.answer("Send plan description, or '-' for no description.")


@router.message(AdminPremiumStates.waiting_for_plan_description)
async def receive_plan_description(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    description = (message.text or "").strip()
    plan = await PremiumPlanRepository(session).create(
        name=str(data["name"]),
        duration_days=int(data["duration_days"]),
        price=Decimal(str(data["price"])),
        description=None if description == "-" else description,
    )
    await AuditLogService(AuditLogRepository(session)).record(admin=message.from_user, action="Create Premium Plan", target_type="Premium Plan", target_id=plan.id, details=f"{plan.name} ({plan.duration_days} Days)")
    await state.clear()
    await message.answer("✅ Premium plan created.")


@router.callback_query(AdminPremiumCallback.filter(F.action == AdminPremiumAction.PLAN_VIEW))
async def view_plan(callback: CallbackQuery, callback_data: AdminPremiumCallback, session: AsyncSession) -> None:
    await show_plan(callback, session, callback_data.plan_id)


@router.callback_query(AdminPremiumCallback.filter(F.action == AdminPremiumAction.PLAN_EDIT))
async def edit_plan(callback: CallbackQuery, callback_data: AdminPremiumCallback, state: FSMContext) -> None:
    await state.clear()
    await state.update_data(plan_id=callback_data.plan_id)
    await state.set_state(AdminPremiumStates.waiting_for_edit_value)
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            "Send updated plan values in this format:\n\n"
            "name | duration_days | price | description\n\n"
            "Example:\nGold | 90 | 250000 | 90-day premium access"
        )
    await callback.answer()


@router.message(AdminPremiumStates.waiting_for_edit_value)
async def receive_plan_edit(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    parts = [part.strip() for part in (message.text or "").split("|", maxsplit=3)]
    if len(parts) != 4:
        await message.answer("Use: name | duration_days | price | description")
        return
    try:
        duration = int(parts[1])
        price = Decimal(parts[2].replace(",", ""))
    except (ValueError, InvalidOperation):
        await message.answer("Duration must be an integer and price must be a number.")
        return
    if duration <= 0 or price < 0:
        await message.answer("Duration must be positive and price cannot be negative.")
        return
    repo = PremiumPlanRepository(session)
    plan = await repo.get(int(data["plan_id"]))
    if plan is None:
        await message.answer("Plan not found.")
        await state.clear()
        return
    await repo.update(plan, name=parts[0], duration_days=duration, price=price, description=None if parts[3] == "-" else parts[3])
    await AuditLogService(AuditLogRepository(session)).record(admin=message.from_user, action="Edit Premium Plan", target_type="Premium Plan", target_id=plan.id, details=f"{plan.name} ({plan.duration_days} Days)")
    await state.clear()
    await message.answer("✅ Premium plan updated.")


@router.callback_query(AdminPremiumCallback.filter(F.action == AdminPremiumAction.PLAN_TOGGLE))
async def toggle_plan(callback: CallbackQuery, callback_data: AdminPremiumCallback, session: AsyncSession) -> None:
    repo = PremiumPlanRepository(session)
    plan = await repo.get(callback_data.plan_id)
    if plan is None:
        await callback.answer("Plan not found", show_alert=True)
        return
    await repo.update(plan, is_active=not plan.is_active)
    await AuditLogService(AuditLogRepository(session)).record(admin=callback.from_user, action="Edit Premium Plan", target_type="Premium Plan", target_id=plan.id, details=f"{plan.name} ({plan.duration_days} Days)")
    await show_plan(callback, session, plan.id)


@router.callback_query(AdminPremiumCallback.filter(F.action == AdminPremiumAction.PLAN_DELETE))
async def delete_plan(callback: CallbackQuery, callback_data: AdminPremiumCallback, session: AsyncSession) -> None:
    repo = PremiumPlanRepository(session)
    plan = await repo.get(callback_data.plan_id)
    if plan is None:
        await callback.answer("Plan not found", show_alert=True)
        return
    details = f"{plan.name} ({plan.duration_days} Days)"
    await repo.delete(plan)
    await AuditLogService(AuditLogRepository(session)).record(admin=callback.from_user, action="Delete Premium Plan", target_type="Premium Plan", target_id=callback_data.plan_id, details=details)
    await show_plans(callback, session)


@router.callback_query(AdminPremiumCallback.filter(F.action == AdminPremiumAction.GRANT))
async def grant_premium(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(AdminPremiumStates.waiting_for_user)
    if isinstance(callback.message, Message):
        await callback.message.edit_text("Enter Telegram User ID to grant premium.")
    await callback.answer()


@router.message(AdminPremiumStates.waiting_for_user)
async def receive_grant_user(message: Message, state: FSMContext, session: AsyncSession) -> None:
    try:
        telegram_id = int((message.text or "").strip())
    except ValueError:
        await message.answer("Telegram User ID must be numeric.")
        return
    user = await UserRepository(session).get_by_telegram_id(telegram_id)
    if user is None:
        await message.answer("User not found. The user must start the bot first.")
        return
    plans = await PremiumPlanRepository(session).list_active()
    if not plans:
        await message.answer("No active plans available.")
        await state.clear()
        return
    await state.update_data(user_id=user.id, telegram_id=user.telegram_id)
    rows = [[InlineKeyboardButton(text=plan.name, callback_data=AdminPremiumCallback(action=AdminPremiumAction.GRANT_PLAN, plan_id=plan.id).pack())] for plan in plans]
    await message.answer("Select plan to activate:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


@router.callback_query(AdminPremiumCallback.filter(F.action == AdminPremiumAction.GRANT_PLAN))
async def activate_grant(callback: CallbackQuery, callback_data: AdminPremiumCallback, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    if "user_id" not in data:
        await callback.answer("Grant workflow expired", show_alert=True)
        return
    plan = await PremiumPlanRepository(session).get(callback_data.plan_id)
    if plan is None:
        await callback.answer("Plan not found", show_alert=True)
        return
    admin_user = await UserRepository(session).upsert_from_telegram(callback.from_user.id, callback.from_user.username, callback.from_user.first_name)
    subscription = await PremiumService(SubscriptionRepository(session), PremiumPlanRepository(session)).activate_subscription(int(data["user_id"]), plan, admin_user.id)
    await AuditLogService(AuditLogRepository(session)).record(admin=callback.from_user, action="Grant Premium", target_type="User", target_id=int(data["telegram_id"]), details=f"{plan.name} ({plan.duration_days} Days)")
    await state.clear()
    if callback.bot is not None:
        await callback.bot.send_message(int(data["telegram_id"]), "✅ Premium subscription activated.")
    if isinstance(callback.message, Message):
        await callback.message.edit_text(f"✅ Activated {plan.name} until {subscription.expires_at:%Y-%m-%d}.")
    await callback.answer()


@router.callback_query(AdminPremiumCallback.filter(F.action == AdminPremiumAction.STATS))
async def premium_stats(callback: CallbackQuery, session: AsyncSession) -> None:
    stats = await PremiumService(SubscriptionRepository(session), PremiumPlanRepository(session)).get_statistics()
    text = (
        "📊 <b>Premium Statistics</b>\n\n"
        f"Active premium users: <b>{stats.active_premium_users}</b>\n"
        f"Expired subscriptions: <b>{stats.expired_subscriptions}</b>\n"
        f"Total subscriptions sold: <b>{stats.total_subscriptions_sold}</b>\n"
        f"Active plans: <b>{stats.active_plans}</b>\n"
        f"Most popular plan: <b>{stats.most_popular_plan}</b>"
    )
    if isinstance(callback.message, Message):
        await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[navigation_row(back_to=AdminSection.PREMIUM, refresh=AdminSection.PREMIUM)]))
    await callback.answer()


@router.callback_query(AdminPremiumCallback.filter(F.action == AdminPremiumAction.SETTINGS))
async def premium_settings(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    await show_settings(callback, session, settings)


@router.callback_query(AdminPremiumCallback.filter(F.action == AdminPremiumAction.SETTING_EDIT))
async def edit_setting(callback: CallbackQuery, callback_data: AdminPremiumCallback, state: FSMContext) -> None:
    await state.clear()
    await state.update_data(key=callback_data.key)
    await state.set_state(AdminPremiumStates.waiting_for_setting_value)
    if isinstance(callback.message, Message):
        await callback.message.edit_text(f"Send new value for {callback_data.key}.")
    await callback.answer()


@router.message(AdminPremiumStates.waiting_for_setting_value)
async def receive_setting(message: Message, state: FSMContext, session: AsyncSession, settings: Settings) -> None:
    data = await state.get_data()
    await PremiumSettingsService(SettingsRepository(session), settings).set_value(str(data["key"]), (message.text or "").strip())
    await AuditLogService(AuditLogRepository(session)).record(admin=message.from_user, action="Settings Change", target_type="Premium Settings", target_id=None, details=f"{data['key']} updated")
    await state.clear()
    await message.answer("✅ Premium setting updated.")


async def show_premium(callback: CallbackQuery) -> None:
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Plans", callback_data=AdminPremiumCallback(action=AdminPremiumAction.PLANS).pack())],
        [InlineKeyboardButton(text="🎁 Grant Premium", callback_data=AdminPremiumCallback(action=AdminPremiumAction.GRANT).pack())],
        [InlineKeyboardButton(text="📊 Premium Statistics", callback_data=AdminPremiumCallback(action=AdminPremiumAction.STATS).pack())],
        [InlineKeyboardButton(text="⚙️ Payment Settings", callback_data=AdminPremiumCallback(action=AdminPremiumAction.SETTINGS).pack())],
        navigation_row(refresh=AdminSection.PREMIUM),
    ])
    if isinstance(callback.message, Message):
        await callback.message.edit_text("⭐ <b>Premium</b>\n\nManage plans, manual activations, payment settings, and subscription audits.", reply_markup=keyboard)
    await callback.answer()


async def show_plans(callback: CallbackQuery, session: AsyncSession) -> None:
    plans = await PremiumPlanRepository(session).list_all()
    rows = [[InlineKeyboardButton(text="➕ Create Plan", callback_data=AdminPremiumCallback(action=AdminPremiumAction.PLAN_ADD).pack())]]
    rows.extend([[InlineKeyboardButton(text=f"{'✅' if plan.is_active else '⛔'} {plan.name}", callback_data=AdminPremiumCallback(action=AdminPremiumAction.PLAN_VIEW, plan_id=plan.id).pack())] for plan in plans])
    rows.append(navigation_row(back_to=AdminSection.PREMIUM, refresh=AdminSection.PREMIUM))
    body = "No plans configured." if not plans else "Select a plan to manage it."
    if isinstance(callback.message, Message):
        await callback.message.edit_text(f"📋 <b>Premium Plans</b>\n\n{body}", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await callback.answer()


async def show_plan(callback: CallbackQuery, session: AsyncSession, plan_id: int) -> None:
    plan = await PremiumPlanRepository(session).get(plan_id)
    if plan is None:
        await callback.answer("Plan not found", show_alert=True)
        return
    text = f"⭐ <b>{plan.name}</b>\n\nDuration: <b>{plan.duration_days} Days</b>\nPrice: <b>{format_money(plan.price)}</b>\nDescription: {plan.description or '—'}\nStatus: <b>{'Active' if plan.is_active else 'Inactive'}</b>"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Edit", callback_data=AdminPremiumCallback(action=AdminPremiumAction.PLAN_EDIT, plan_id=plan.id).pack())],
        [InlineKeyboardButton(text="⏸ Disable" if plan.is_active else "▶️ Enable", callback_data=AdminPremiumCallback(action=AdminPremiumAction.PLAN_TOGGLE, plan_id=plan.id).pack())],
        [InlineKeyboardButton(text="🗑 Delete", callback_data=AdminPremiumCallback(action=AdminPremiumAction.PLAN_DELETE, plan_id=plan.id).pack())],
        [InlineKeyboardButton(text="⬅️ Plans", callback_data=AdminPremiumCallback(action=AdminPremiumAction.PLANS).pack())],
    ])
    if isinstance(callback.message, Message):
        await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


async def show_settings(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    values = await PremiumSettingsService(SettingsRepository(session), settings).get()
    text = (
        "⚙️ <b>Premium Payment Settings</b>\n\n"
        f"Admin username: {values.admin_username}\n"
        f"Card holder: {values.card_holder_name}\n"
        f"Card number: <code>{values.card_number}</code>\n"
        f"Crypto network: {values.crypto_network}\n"
        f"Crypto wallet: <code>{values.crypto_wallet_address}</code>\n"
        f"Support instructions: {values.support_instructions}"
    )
    labels = dict(zip(PREMIUM_SETTING_KEYS, ["Admin Username", "Card Holder", "Card Number", "Crypto Wallet", "Crypto Network", "Support Text"], strict=True))
    rows = [[InlineKeyboardButton(text=f"✏️ {label}", callback_data=AdminPremiumCallback(action=AdminPremiumAction.SETTING_EDIT, key=key).pack())] for key, label in labels.items()]
    rows.append(navigation_row(back_to=AdminSection.PREMIUM, refresh=AdminSection.PREMIUM))
    if isinstance(callback.message, Message):
        await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await callback.answer()
