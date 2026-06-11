from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from typing import cast

from models.subscription import PremiumPlan, Subscription
from repositories.premium import PremiumPlanRepository
from repositories.subscriptions import SubscriptionRepository


@dataclass(frozen=True, slots=True)
class PremiumStats:
    active_premium_users: int
    expired_subscriptions: int
    total_subscriptions_sold: int
    active_plans: int
    most_popular_plan: str


class PremiumService:
    def __init__(self, repository: SubscriptionRepository, plans: PremiumPlanRepository | None = None) -> None:
        self.repository = repository
        self.plans = plans

    async def has_active_subscription(self, user_id: int) -> bool:
        return await self.repository.has_active_subscription(user_id)

    async def has_premium(self, user_id: int) -> bool:
        return await self.has_active_subscription(user_id)

    async def get_active_subscription(self, user_id: int) -> Subscription | None:
        return await self.repository.get_active_subscription(user_id)

    async def activate_subscription(
        self, user_id: int, plan: PremiumPlan, admin_user_id: int | None = None, note: str | None = None
    ) -> Subscription:
        if plan.duration_days <= 0:
            raise ValueError("Premium duration must be positive")
        return await self.repository.activate(user_id=user_id, plan=plan, admin_id=admin_user_id, note=note)

    async def expire_subscription(self, subscription: Subscription) -> Subscription:
        return await self.repository.expire_subscription(subscription)

    async def grant_manual(self, user_id: int, days: int, admin_user_id: int | None, note: str | None = None) -> Subscription:
        if days <= 0:
            raise ValueError("Premium duration must be positive")
        return await self.repository.extend(user_id=user_id, duration=timedelta(days=days), admin_id=admin_user_id, note=note)

    async def list_active_plans(self) -> list[PremiumPlan]:
        if self.plans is None:
            raise RuntimeError("PremiumPlanRepository is required")
        return await self.plans.list_active()

    async def get_plan(self, plan_id: int) -> PremiumPlan | None:
        if self.plans is None:
            raise RuntimeError("PremiumPlanRepository is required")
        return await self.plans.get(plan_id)

    async def create_plan(self, name: str, duration_days: int, price: Decimal, description: str | None) -> PremiumPlan:
        if self.plans is None:
            raise RuntimeError("PremiumPlanRepository is required")
        if duration_days <= 0:
            raise ValueError("Plan duration must be positive")
        if price < 0:
            raise ValueError("Plan price cannot be negative")
        return await self.plans.create(name=name, duration_days=duration_days, price=price, description=description)

    async def get_statistics(self) -> PremiumStats:
        raw = await self.repository.stats()
        return PremiumStats(
            active_premium_users=cast(int, raw["active_premium_users"]),
            expired_subscriptions=cast(int, raw["expired_subscriptions"]),
            total_subscriptions_sold=cast(int, raw["total_subscriptions_sold"]),
            active_plans=cast(int, raw["active_plans"]),
            most_popular_plan=str(raw["most_popular_plan"]),
        )
