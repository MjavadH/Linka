from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from models.user_ban import UserBan
from repositories.base import BaseRepository


class UserBanRepository(BaseRepository[UserBan]):
    async def get_active_for_user(self, user_id: int, now: datetime | None = None) -> UserBan | None:
        moment = now or datetime.now(UTC)
        result = await self.session.execute(
            select(UserBan)
            .where(
                UserBan.user_id == user_id,
                UserBan.is_active.is_(True),
                (UserBan.is_permanent.is_(True)) | (UserBan.banned_until > moment),
            )
            .order_by(UserBan.created_at.desc(), UserBan.id.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def ban_permanent(self, user_id: int, reason: str = "admin_ban") -> UserBan:
        await self.deactivate_active(user_id)
        ban = UserBan(user_id=user_id, is_active=True, is_permanent=True, reason=reason)
        self.session.add(ban)
        await self.session.flush()
        return ban

    async def ban_temporary(self, user_id: int, banned_until: datetime, reason: str = "admin_ban") -> UserBan:
        await self.deactivate_active(user_id)
        ban = UserBan(
            user_id=user_id,
            is_active=True,
            is_permanent=False,
            reason=reason,
            banned_until=banned_until,
        )
        self.session.add(ban)
        await self.session.flush()
        return ban

    async def deactivate_active(self, user_id: int, now: datetime | None = None) -> list[UserBan]:
        moment = now or datetime.now(UTC)
        result = await self.session.execute(
            select(UserBan).where(UserBan.user_id == user_id, UserBan.is_active.is_(True))
        )
        bans = list(result.scalars())
        for ban in bans:
            ban.is_active = False
            ban.lifted_at = moment
        await self.session.flush()
        return bans

    async def expire_due(self, now: datetime | None = None) -> list[UserBan]:
        moment = now or datetime.now(UTC)
        result = await self.session.execute(
            select(UserBan)
            .options(selectinload(UserBan.user))
            .where(
                UserBan.is_active.is_(True),
                UserBan.is_permanent.is_(False),
                UserBan.banned_until <= moment,
            )
        )
        bans = list(result.scalars())
        for ban in bans:
            ban.is_active = False
            ban.lifted_at = moment
        await self.session.flush()
        return bans
