from decimal import Decimal

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import Settings
from keyboards.premium import payment_method_keyboard, plan_selection_keyboard
from repositories.premium import PremiumPlanRepository
from repositories.settings import SettingsRepository
from services.settings import PremiumSettingsService

router = Router(name="premium")


def format_money(value: Decimal) -> str:
    if value == value.to_integral_value():
        return f"{int(value):,}"
    return f"{value:,.2f}"


def plan_icon(name: str) -> str:
    return {"silver": "🥈", "gold": "🥇", "diamond": "💎", "platinum": "👑"}.get(name.lower(), "⭐")


async def show_plan_selection(message: Message, session: AsyncSession) -> None:
    plans = await PremiumPlanRepository(session).list_active()
    if not plans:
        await message.answer("⭐ No subscription plans are available right now. Please contact support.")
        return
    lines = ["⭐ <b>Available Plans</b>", ""]
    for plan in plans:
        lines.extend([f"{plan_icon(plan.name)} <b>{plan.name}</b>", f"{plan.duration_days} Days", format_money(plan.price), ""])
        if plan.description:
            lines.extend([plan.description, ""])
    await message.answer("\n".join(lines).strip(), reply_markup=plan_selection_keyboard(plans))


@router.message(F.text == "⭐ Buy Subscription")
async def buy_subscription_message(message: Message, session: AsyncSession) -> None:
    await show_plan_selection(message, session)


@router.callback_query(F.data == "premium:plans")
async def buy_subscription_callback(callback: CallbackQuery, session: AsyncSession) -> None:
    if isinstance(callback.message, Message):
        await show_plan_selection(callback.message, session)
    await callback.answer()


@router.callback_query(F.data.startswith("premium:plan:"))
async def select_plan(callback: CallbackQuery, session: AsyncSession) -> None:
    plan_id = int(str(callback.data).split(":")[-1])
    plan = await PremiumPlanRepository(session).get(plan_id)
    if plan is None or not plan.is_active:
        await callback.answer("Plan is not available", show_alert=True)
        return
    text = (
        f"{plan_icon(plan.name)} <b>{plan.name}</b>\n\n"
        f"Duration:\n{plan.duration_days} Days\n\n"
        f"Price:\n{format_money(plan.price)}\n\n"
        "Choose payment method."
    )
    if isinstance(callback.message, Message):
        await callback.message.edit_text(text, reply_markup=payment_method_keyboard(plan.id))
    await callback.answer()


@router.callback_query(F.data.startswith("premium:pay:card:"))
async def card_payment(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    plan_id = int(str(callback.data).split(":")[-1])
    plan = await PremiumPlanRepository(session).get(plan_id)
    if plan is None:
        await callback.answer("Plan not found", show_alert=True)
        return
    premium_settings = await PremiumSettingsService(SettingsRepository(session), settings).get()
    text = (
        f"💳 <b>Card To Card Payment</b>\n\n"
        f"<b>Plan:</b> {plan.name}\n"
        f"<b>Price:</b> {format_money(plan.price)}\n\n"
        f"<b>Card Number</b>\n<code>{premium_settings.card_number}</code>\n\n"
        f"<b>Card Holder Name</b>\n{premium_settings.card_holder_name}\n\n"
        "<b>Instructions:</b>\n"
        "1. Transfer payment.\n"
        "2. Send receipt directly to admin.\n\n"
        f"Support/Admin: {premium_settings.admin_username}"
    )
    if isinstance(callback.message, Message):
        await callback.message.edit_text(text)
    await callback.answer()


@router.callback_query(F.data.startswith("premium:pay:crypto:"))
async def crypto_payment(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    plan_id = int(str(callback.data).split(":")[-1])
    plan = await PremiumPlanRepository(session).get(plan_id)
    if plan is None:
        await callback.answer("Plan not found", show_alert=True)
        return
    premium_settings = await PremiumSettingsService(SettingsRepository(session), settings).get()
    text = (
        f"🪙 <b>Crypto Payment</b>\n\n"
        f"<b>Plan:</b> {plan.name}\n"
        f"<b>Price:</b> {format_money(plan.price)}\n\n"
        f"<b>{premium_settings.crypto_network}</b>\n"
        f"<code>{premium_settings.crypto_wallet_address}</code>\n\n"
        "<b>Instructions:</b>\n"
        "1. Transfer payment.\n"
        "2. Send transaction proof directly to admin.\n\n"
        f"Support/Admin: {premium_settings.admin_username}"
    )
    if isinstance(callback.message, Message):
        await callback.message.edit_text(text)
    await callback.answer()


@router.message(F.text == "🛠 Support")
async def support(message: Message, session: AsyncSession, settings: Settings) -> None:
    premium_settings = await PremiumSettingsService(SettingsRepository(session), settings).get()
    await message.answer(
        "🛠 <b>Support</b>\n\n"
        f"Admin: {premium_settings.admin_username}\n\n"
        f"{premium_settings.support_instructions}"
    )
