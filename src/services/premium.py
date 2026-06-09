from datetime import timedelta

from models.subscription import Subscription
from repositories.subscriptions import SubscriptionRepository


class PremiumService:
    def __init__(self, repository: SubscriptionRepository) -> None:
        self.repository = repository

    async def has_premium(self, user_id: int) -> bool:
        return await self.repository.has_active_subscription(user_id)

    async def grant_manual(
        self, user_id: int, days: int, admin_user_id: int | None, note: str | None = None
    ) -> Subscription:
        if days <= 0:
            raise ValueError("Premium duration must be positive")
        return await self.repository.extend(
            user_id=user_id,
            duration=timedelta(days=days),
            admin_id=admin_user_id,
            note=note,
        )
