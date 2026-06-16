from dataclasses import dataclass

from core.timezone import format_date
from models.enums import SponsorStatus
from models.subscription import Subscription
from models.user import User
from services.premium import PremiumService


@dataclass(frozen=True, slots=True)
class AccountInfo:
    user: User
    subscription: Subscription | None
    timezone: str

    @property
    def is_premium_active(self) -> bool:
        return self.subscription is not None

    @property
    def premium_button_text(self) -> str:
        return "⭐ Extend Subscription" if self.is_premium_active else "⭐ Buy Subscription"


class AccountService:
    def __init__(self, premium: PremiumService, timezone: str) -> None:
        self.premium = premium
        self.timezone = timezone

    async def get_account_info(self, user: User) -> AccountInfo:
        return AccountInfo(
            user=user,
            subscription=await self.premium.get_active_subscription(user.id),
            timezone=self.timezone,
        )


def format_account_info(account: AccountInfo) -> str:
    user = account.user
    subscription = account.subscription
    username = f"@{user.username}" if user.username else "—"
    sponsor_status = "Verified" if user.sponsor_status == SponsorStatus.VERIFIED else "Verification Required"
    premium_status = "Active" if subscription is not None else "Inactive"
    plan = subscription.plan.name if subscription is not None and subscription.plan is not None else "—"
    expires = format_date(subscription.expires_at if subscription is not None else None, account.timezone)
    joined = format_date(user.joined_at, account.timezone)

    return (
        "👤 <b>Account Information</b>\n\n"
        f"Name: {user.first_name or '—'}\n"
        f"Username: {username}\n"
        f"User ID: {user.telegram_id}\n\n"
        f"Premium: {premium_status}\n\n"
        f"Plan: {plan}\n\n"
        f"Expires: {expires}\n\n"
        f"Sponsor Status: {sponsor_status}\n\n"
        f"Joined: {joined}"
    )
