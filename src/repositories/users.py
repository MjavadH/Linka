from datetime import UTC, datetime
from math import ceil
from typing import NamedTuple

from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from models.enums import SponsorStatus
from models.subscription import Subscription
from models.user import User
from models.user_ban import UserBan
from repositories.base import BaseRepository


class UserListItem(NamedTuple):
    user: User
    has_premium: bool
    is_banned: bool


class UserPage(NamedTuple):
    items: list[UserListItem]
    total: int
    page: int
    per_page: int

    @property
    def pages(self) -> int:
        return max(1, ceil(self.total / self.per_page))


class UserRepository(BaseRepository[User]):
    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        result = await self.session.execute(select(User).where(User.telegram_id == telegram_id))
        return result.scalar_one_or_none()

    async def upsert_from_telegram(
        self, telegram_id: int, username: str | None, first_name: str | None
    ) -> User:
        user = await self.get_by_telegram_id(telegram_id)
        if user is None:
            user = User(telegram_id=telegram_id, username=username, first_name=first_name)
            self.session.add(user)
        else:
            user.username = username
            user.first_name = first_name
            user.last_seen_at = datetime.now(UTC)
        await self.session.flush()
        return user


    async def search(self, query: str, limit: int = 10) -> list[User]:
        normalized = query.strip().lstrip("@")
        if not normalized:
            return []
        clauses = []
        if normalized.isdigit():
            clauses.append(User.telegram_id == int(normalized))
        clauses.append(User.username.ilike(normalized))
        clauses.append(User.first_name.ilike(f"%{normalized}%"))
        result = await self.session.execute(
            select(User)
            .where(or_(*clauses))
            .order_by(User.last_seen_at.desc(), User.id.desc())
            .limit(limit)
        )
        return list(result.scalars())

    async def list_page(self, *, page: int = 1, per_page: int = 8, premium_only: bool = False, banned_only: bool = False) -> UserPage:
        page = max(1, page)
        now = datetime.now(UTC)
        premium_exists = (
            select(Subscription.id)
            .where(
                Subscription.user_id == User.id,
                Subscription.is_active.is_(True),
                Subscription.expires_at > now,
            )
            .exists()
        )
        active_ban_exists = (
            select(UserBan.id)
            .where(
                UserBan.user_id == User.id,
                UserBan.is_active.is_(True),
                or_(UserBan.is_permanent.is_(True), UserBan.banned_until > now),
            )
            .exists()
        )
        filters = []
        if premium_only:
            filters.append(premium_exists)
        if banned_only:
            filters.append(active_ban_exists)
        query = select(User, premium_exists.label("has_premium"), active_ban_exists.label("is_banned")).where(*filters)
        total_query = select(func.count()).select_from(select(User.id).where(*filters).subquery())
        total = int(await self.session.scalar(total_query) or 0)
        result = await self.session.execute(
            query.order_by(User.last_seen_at.desc(), User.id.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        items = [UserListItem(user=row[0], has_premium=bool(row[1]), is_banned=bool(row[2])) for row in result.all()]
        return UserPage(items, total, page, per_page)

    async def get_details(self, user_id: int) -> User | None:
        result = await self.session.execute(
            select(User)
            .options(selectinload(User.subscriptions), selectinload(User.bans))
            .where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def list_telegram_ids_after(self, after_id: int | None, limit: int) -> list[int]:
        query = select(User.telegram_id).order_by(User.id).limit(limit)
        if after_id is not None:
            query = query.where(User.id > after_id)
        result = await self.session.execute(query)
        return list(result.scalars())

    async def list_verified_sponsor_users(
        self, *, after_user_id: int | None, limit: int
    ) -> list[User]:
        query = (
            select(User)
            .where(User.sponsor_status == SponsorStatus.VERIFIED)
            .order_by(User.last_seen_at.desc(), User.id.desc())
            .limit(limit)
        )
        if after_user_id is not None:
            cursor = await self.session.get(User, after_user_id)
            if cursor is not None:
                query = query.where(
                    (User.last_seen_at < cursor.last_seen_at)
                    | ((User.last_seen_at == cursor.last_seen_at) & (User.id < cursor.id))
                )
        result = await self.session.execute(query)
        return list(result.scalars())
