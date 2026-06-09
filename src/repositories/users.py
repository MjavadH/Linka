from datetime import UTC, datetime

from sqlalchemy import select

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

    async def list_telegram_ids_after(self, after_id: int | None, limit: int) -> list[int]:
        query = select(User.telegram_id).order_by(User.id).limit(limit)
        if after_id is not None:
            query = query.where(User.id > after_id)
        result = await self.session.execute(query)
        return list(result.scalars())
