from sqlalchemy import update

from models.download import Download
from models.user import User
from repositories.base import BaseRepository


class DownloadRepository(BaseRepository[Download]):
    async def create(
        self,
        user_id: int,
        file_id: int,
        variant_id: int | None,
        deep_link_id: int | None,
        token: str | None,
        is_premium_download: bool,
    ) -> Download:
        download = Download(
            user_id=user_id,
            file_id=file_id,
            variant_id=variant_id,
            deep_link_id=deep_link_id,
            token=token,
            is_premium_download=is_premium_download,
        )
        self.session.add(download)
        await self.session.execute(
            update(User).where(User.id == user_id).values(total_downloads=User.total_downloads + 1)
        )
        await self.session.flush()
        return download
