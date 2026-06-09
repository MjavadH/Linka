from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from models.enums import SubscriptionSource
from models.subscription import Subscription
from repositories.base import BaseRepository


class SubscriptionRepository(BaseRepository[Subscription]):
    async def has_active_subscription(self, user_id: int) -> bool:
        result = await self.session.execute(
            select(Subscription.id).where(
                Subscription.user_id == user_id,
                Subscription.expires_at > datetime.now(UTC),
            )
        )
        return result.first() is not None

    async def extend(
        self,
        user_id: int,
        duration: timedelta,
        source: SubscriptionSource = SubscriptionSource.MANUAL,
        admin_id: int | None = None,
        note: str | None = None,
    ) -> Subscription:
        now = datetime.now(UTC)
        latest = await self.session.execute(
            select(Subscription)
            .where(Subscription.user_id == user_id)
            .order_by(Subscription.expires_at.desc())
            .limit(1)
        )
        current = latest.scalar_one_or_none()
        starts_at = max(now, current.expires_at) if current else now
        subscription = Subscription(
            user_id=user_id,
            starts_at=starts_at,
            expires_at=starts_at + duration,
            source=source,
            granted_by_admin_id=admin_id,
            note=note,
        )
        self.session.add(subscription)
        await self.session.flush()
        return subscription
