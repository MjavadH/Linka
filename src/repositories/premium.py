from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select, update
from sqlalchemy.orm import selectinload

from models.enums import SubscriptionSource
from models.subscription import PremiumPlan, Subscription
from repositories.base import BaseRepository


class PremiumPlanRepository(BaseRepository[PremiumPlan]):
    async def list_all(self) -> list[PremiumPlan]:
        result = await self.session.execute(select(PremiumPlan).order_by(PremiumPlan.id))
        return list(result.scalars())

    async def list_active(self) -> list[PremiumPlan]:
        result = await self.session.execute(
            select(PremiumPlan).where(PremiumPlan.is_active.is_(True)).order_by(PremiumPlan.price, PremiumPlan.id)
        )
        return list(result.scalars())

    async def get(self, plan_id: int) -> PremiumPlan | None:
        result = await self.session.execute(select(PremiumPlan).where(PremiumPlan.id == plan_id))
        return result.scalar_one_or_none()

    async def create(self, *, name: str, duration_days: int, price: Decimal, description: str | None, is_active: bool = True) -> PremiumPlan:
        plan = PremiumPlan(name=name, duration_days=duration_days, price=price, description=description, is_active=is_active)
        self.session.add(plan)
        await self.session.flush()
        return plan

    async def update(self, plan: PremiumPlan, *, name: str | None = None, duration_days: int | None = None, price: Decimal | None = None, description: str | None = None, is_active: bool | None = None) -> PremiumPlan:
        if name is not None:
            plan.name = name
        if duration_days is not None:
            plan.duration_days = duration_days
        if price is not None:
            plan.price = price
        if description is not None:
            plan.description = description
        if is_active is not None:
            plan.is_active = is_active
        plan.updated_at = datetime.now(UTC)
        await self.session.flush()
        return plan

    async def delete(self, plan: PremiumPlan) -> None:
        await self.session.execute(update(Subscription).where(Subscription.plan_id == plan.id).values(plan_id=None))
        await self.session.delete(plan)
        await self.session.flush()


class SubscriptionRepository(BaseRepository[Subscription]):
    async def has_active_subscription(self, user_id: int) -> bool:
        result = await self.session.execute(
            select(Subscription.id).where(
                Subscription.user_id == user_id,
                Subscription.is_active.is_(True),
                Subscription.expires_at > datetime.now(UTC),
            )
        )
        return result.first() is not None

    async def get_active_subscription(self, user_id: int) -> Subscription | None:
        result = await self.session.execute(
            select(Subscription)
            .options(selectinload(Subscription.plan))
            .where(
                Subscription.user_id == user_id,
                Subscription.is_active.is_(True),
                Subscription.expires_at > datetime.now(UTC),
            )
            .order_by(Subscription.expires_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def activate(
        self,
        *,
        user_id: int,
        plan: PremiumPlan,
        source: SubscriptionSource = SubscriptionSource.MANUAL,
        admin_id: int | None = None,
        note: str | None = None,
    ) -> Subscription:
        now = datetime.now(UTC)
        current = await self.get_active_subscription(user_id)
        starts_at = max(now, current.expires_at) if current else now
        subscription = Subscription(
            user_id=user_id,
            plan_id=plan.id,
            starts_at=starts_at,
            expires_at=starts_at + timedelta(days=plan.duration_days),
            is_active=True,
            source=source,
            granted_by_admin_id=admin_id,
            note=note,
        )
        self.session.add(subscription)
        await self.session.flush()
        return subscription

    async def extend(self, user_id: int, duration: timedelta, source: SubscriptionSource = SubscriptionSource.MANUAL, admin_id: int | None = None, note: str | None = None) -> Subscription:
        now = datetime.now(UTC)
        current = await self.get_active_subscription(user_id)
        starts_at = max(now, current.expires_at) if current else now
        subscription = Subscription(user_id=user_id, starts_at=starts_at, expires_at=starts_at + duration, is_active=True, source=source, granted_by_admin_id=admin_id, note=note)
        self.session.add(subscription)
        await self.session.flush()
        return subscription

    async def expire_subscription(self, subscription: Subscription) -> Subscription:
        subscription.is_active = False
        await self.session.flush()
        return subscription

    async def list_due_reminders(self, days_before: int, now: datetime | None = None) -> list[Subscription]:
        moment = now or datetime.now(UTC)
        threshold = moment + timedelta(days=days_before)
        sent_column = {
            7: Subscription.reminder_7d_sent_at,
            3: Subscription.reminder_3d_sent_at,
            1: Subscription.reminder_1d_sent_at,
        }[days_before]
        result = await self.session.execute(
            select(Subscription)
            .options(selectinload(Subscription.user), selectinload(Subscription.plan))
            .where(
                Subscription.is_active.is_(True),
                Subscription.expires_at > moment,
                Subscription.expires_at <= threshold,
                sent_column.is_(None),
            )
        )
        return list(result.scalars())

    async def mark_reminder_sent(self, subscription: Subscription, days_before: int, now: datetime | None = None) -> Subscription:
        moment = now or datetime.now(UTC)
        if days_before == 7:
            subscription.reminder_7d_sent_at = moment
        elif days_before == 3:
            subscription.reminder_3d_sent_at = moment
        elif days_before == 1:
            subscription.reminder_1d_sent_at = moment
        else:
            raise ValueError("Unsupported premium reminder window")
        await self.session.flush()
        return subscription

    async def expire_due(self, now: datetime | None = None) -> list[Subscription]:
        moment = now or datetime.now(UTC)
        result = await self.session.execute(
            select(Subscription)
            .options(selectinload(Subscription.user), selectinload(Subscription.plan))
            .where(Subscription.is_active.is_(True), Subscription.expires_at <= moment, Subscription.expiration_notified_at.is_(None))
        )
        subscriptions = list(result.scalars())
        for subscription in subscriptions:
            subscription.is_active = False
            subscription.expiration_notified_at = moment
        await self.session.flush()
        return subscriptions

    async def stats(self) -> dict[str, object]:
        active_users = await self.session.scalar(
            select(func.count(func.distinct(Subscription.user_id))).where(
                Subscription.is_active.is_(True), Subscription.expires_at > datetime.now(UTC)
            )
        )
        expired = await self.session.scalar(select(func.count(Subscription.id)).where(Subscription.is_active.is_(False)))
        total = await self.session.scalar(select(func.count(Subscription.id)))
        active_plans = await self.session.scalar(select(func.count(PremiumPlan.id)).where(PremiumPlan.is_active.is_(True)))
        popular_result = await self.session.execute(
            select(PremiumPlan.name, func.count(Subscription.id).label("sales"))
            .join(Subscription, Subscription.plan_id == PremiumPlan.id)
            .group_by(PremiumPlan.id)
            .order_by(func.count(Subscription.id).desc(), PremiumPlan.id)
            .limit(1)
        )
        row = popular_result.first()
        return {
            "active_premium_users": active_users or 0,
            "expired_subscriptions": expired or 0,
            "total_subscriptions_sold": total or 0,
            "active_plans": active_plans or 0,
            "most_popular_plan": row[0] if row else "—",
        }
