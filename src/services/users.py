from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from models.subscription import PremiumPlan, Subscription
from models.user import User
from models.user_ban import UserBan
from repositories.premium import PremiumPlanRepository
from repositories.subscriptions import SubscriptionRepository
from repositories.user_bans import UserBanRepository
from repositories.users import UserRepository
from services.premium import PremiumService


@dataclass(frozen=True, slots=True)
class ManagedUserDetails:
    user: User
    active_subscription: Subscription | None
    active_ban: UserBan | None


class UserManagementService:
    def __init__(
        self,
        users: UserRepository,
        bans: UserBanRepository,
        premium: PremiumService,
    ) -> None:
        self.users = users
        self.bans = bans
        self.premium = premium

    async def search_users(self, query: str) -> list[User]:
        return await self.users.search(query)

    async def get_details(self, user_id: int) -> ManagedUserDetails | None:
        user = await self.users.get_details(user_id)
        if user is None:
            return None
        active_subscription = await self.premium.get_active_subscription(user.id)
        active_ban = await self.bans.get_active_for_user(user.id)
        return ManagedUserDetails(user=user, active_subscription=active_subscription, active_ban=active_ban)

    async def grant_plan(self, user_id: int, plan: PremiumPlan, admin_user_id: int) -> Subscription:
        return await self.premium.activate_subscription(user_id, plan, admin_user_id, note="admin_user_management")

    async def grant_custom(self, user_id: int, days: int, admin_user_id: int) -> Subscription:
        return await self.premium.grant_manual(user_id, days, admin_user_id, note="admin_user_management_custom")

    async def remove_premium(self, user_id: int) -> Subscription | None:
        subscription = await self.premium.get_active_subscription(user_id)
        if subscription is None:
            return None
        return await self.premium.expire_subscription(subscription)

    async def ban_permanent(self, user_id: int) -> UserBan:
        return await self.bans.ban_permanent(user_id=user_id, reason="admin_ban")

    async def ban_temporary(self, user_id: int, days: int) -> UserBan:
        if days <= 0:
            raise ValueError("Ban duration must be positive")
        return await self.bans.ban_temporary(
            user_id=user_id,
            banned_until=datetime.now(UTC) + timedelta(days=days),
            reason="admin_ban",
        )

    async def unban(self, user_id: int) -> None:
        await self.bans.deactivate_active(user_id)


def build_user_management_service(session: AsyncSession) -> UserManagementService:
    return UserManagementService(
        users=UserRepository(session),
        bans=UserBanRepository(session),
        premium=PremiumService(SubscriptionRepository(session), PremiumPlanRepository(session)),
    )
