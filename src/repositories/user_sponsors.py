from datetime import UTC, datetime

from sqlalchemy import select

from models.enums import SponsorStatus, TemporaryMessageStatus
from models.temporary_message import TemporaryMessage
from models.user import User
from repositories.base import BaseRepository


class UserSponsorRepository(BaseRepository[User]):
    async def set_status(self, user: User, status: SponsorStatus) -> User:
        now = datetime.now(UTC)
        user.sponsor_status = status
        user.last_sponsor_check_at = now
        if status == SponsorStatus.VERIFIED:
            user.sponsor_verified_at = now
        await self.session.flush()
        return user

    async def list_verified_batch(
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

    async def pending_temporary_messages_for_user(self, user_id: int) -> list[TemporaryMessage]:
        result = await self.session.execute(
            select(TemporaryMessage).where(
                TemporaryMessage.user_id == user_id,
                TemporaryMessage.status == TemporaryMessageStatus.PENDING,
            )
        )
        return list(result.scalars())
