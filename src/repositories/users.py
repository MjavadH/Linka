from datetime import UTC, datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import selectinload

from models.enums import SponsorStatus
from models.user import User
from repositories.base import BaseRepository


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
        result = await self.session.execute(
            select(User)
            .where(or_(*clauses))
            .order_by(User.last_seen_at.desc(), User.id.desc())
            .limit(limit)
        )
        return list(result.scalars())

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
