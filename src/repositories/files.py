from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from models.file import DeepLink, FileVariant
from repositories.base import BaseRepository


class DeepLinkRepository(BaseRepository[DeepLink]):
    async def get_active_by_token(self, token: str) -> DeepLink | None:
        now = datetime.now(UTC)
        result = await self.session.execute(
            select(DeepLink)
            .options(selectinload(DeepLink.file), selectinload(DeepLink.variant))
            .where(
                DeepLink.token == token,
                DeepLink.is_active.is_(True),
                (DeepLink.expires_at.is_(None)) | (DeepLink.expires_at > now),
            )
        )
        return result.scalar_one_or_none()


class FileVariantRepository(BaseRepository[FileVariant]):
    async def get_default_for_file(self, file_id: int) -> FileVariant | None:
        result = await self.session.execute(
            select(FileVariant)
            .where(FileVariant.file_id == file_id, FileVariant.is_active.is_(True))
            .order_by(FileVariant.id)
            .limit(1)
        )
        return result.scalar_one_or_none()
