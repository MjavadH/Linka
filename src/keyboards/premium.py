from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from models.subscription import PremiumPlan


def premium_required_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⭐ Buy Subscription", callback_data="premium:plans")]])


def plan_selection_keyboard(plans: list[PremiumPlan]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=_plan_button_label(plan), callback_data=f"premium:plan:{plan.id}")]
            for plan in plans
        ]
    )


def payment_method_keyboard(plan_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💳 Card To Card", callback_data=f"premium:pay:card:{plan_id}")],
            [InlineKeyboardButton(text="🪙 Crypto", callback_data=f"premium:pay:crypto:{plan_id}")],
        ]
    )


def _plan_button_label(plan: PremiumPlan) -> str:
    icons = {"silver": "🥈", "gold": "🥇", "diamond": "💎", "platinum": "👑"}
    return f"{icons.get(plan.name.lower(), '⭐')} {plan.name}"
