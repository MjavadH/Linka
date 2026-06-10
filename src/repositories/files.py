from datetime import UTC, datetime

from sqlalchemy import Select, func, or_, select, update
from sqlalchemy.orm import selectinload

from models.download import Download
from models.enums import FileAccessLevel, StorageType
from models.file import DeepLink, File, FileVariant
from repositories.base import BaseRepository

PAGE_SIZE = 5


class FileRepository(BaseRepository[File]):
    async def create(self, title: str, description: str | None = None) -> File:
        file = File(title=title, description=description)
        self.session.add(file)
        await self.session.flush()
        return file

    async def get_by_id(self, file_id: int) -> File | None:
        result = await self.session.execute(
            select(File).options(selectinload(File.variants)).where(File.id == file_id)
        )
        return result.scalar_one_or_none()

    async def list_with_stats(
        self, page: int = 1, search: str | None = None, page_size: int = PAGE_SIZE
    ) -> tuple[list[tuple[File, int, int]], int]:
        variant_counts = (
            select(FileVariant.file_id, func.count(FileVariant.id).label("variant_count"))
            .where(FileVariant.is_active.is_(True))
            .group_by(FileVariant.file_id)
            .subquery()
        )
        download_counts = (
            select(Download.file_id, func.count(Download.id).label("download_count"))
            .group_by(Download.file_id)
            .subquery()
        )
        stmt: Select[tuple[File, int, int]] = (
            select(
                File,
                func.coalesce(variant_counts.c.variant_count, 0),
                func.coalesce(download_counts.c.download_count, 0),
            )
            .outerjoin(variant_counts, variant_counts.c.file_id == File.id)
            .outerjoin(download_counts, download_counts.c.file_id == File.id)
            .where(File.is_active.is_(True))
            .order_by(File.created_at.desc(), File.id.desc())
        )
        count_stmt = select(func.count(File.id)).where(File.is_active.is_(True))
        if search:
            pattern = f"%{search}%"
            matching_variant_file_ids = select(FileVariant.file_id).where(FileVariant.filename.ilike(pattern))
            criterion = or_(File.title.ilike(pattern), File.id.in_(matching_variant_file_ids))
            stmt = stmt.where(criterion)
            count_stmt = count_stmt.where(criterion)

        total = int(await self.session.scalar(count_stmt) or 0)
        result = await self.session.execute(
            stmt.offset(max(page - 1, 0) * page_size).limit(page_size)
        )
        return [(row[0], int(row[1]), int(row[2])) for row in result.all()], total

    async def soft_delete(self, file_id: int) -> None:
        await self.session.execute(update(File).where(File.id == file_id).values(is_active=False))
        await self.session.execute(
            update(FileVariant).where(FileVariant.file_id == file_id).values(is_active=False)
        )
        await self.session.flush()


class DeepLinkRepository(BaseRepository[DeepLink]):
    async def create(
        self,
        *,
        token: str,
        file_id: int,
        file_variant_id: int | None,
        requires_premium: bool,
    ) -> DeepLink:
        link = DeepLink(
            token=token,
            file_id=file_id,
            file_variant_id=file_variant_id,
            requires_premium=requires_premium,
        )
        self.session.add(link)
        await self.session.flush()
        return link

    async def get_by_token(self, token: str) -> DeepLink | None:
        result = await self.session.execute(select(DeepLink).where(DeepLink.token == token))
        return result.scalar_one_or_none()

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

    async def get_active_by_variant_id(self, variant_id: int) -> DeepLink | None:
        result = await self.session.execute(
            select(DeepLink).where(
                DeepLink.file_variant_id == variant_id,
                DeepLink.is_active.is_(True),
            )
        )
        return result.scalar_one_or_none()

    async def list_active_for_file(self, file_id: int) -> list[DeepLink]:
        result = await self.session.execute(
            select(DeepLink)
            .options(selectinload(DeepLink.variant))
            .where(DeepLink.file_id == file_id, DeepLink.is_active.is_(True))
            .order_by(DeepLink.id)
        )
        return list(result.scalars().all())

    async def disable_for_file(self, file_id: int) -> None:
        await self.session.execute(
            update(DeepLink).where(DeepLink.file_id == file_id).values(is_active=False)
        )
        await self.session.flush()


class FileVariantRepository(BaseRepository[FileVariant]):
    async def create(
        self,
        *,
        file_id: int,
        quality: str,
        storage_type: StorageType,
        storage_key: str,
        telegram_file_id: str | None,
        telegram_file_unique_id: str | None,
        archive_chat_id: int | None,
        archive_message_id: int | None,
        filename: str | None,
        file_size: int | None,
        mime_type: str | None,
        is_premium: bool,
        access_level: FileAccessLevel,
    ) -> FileVariant:
        variant = FileVariant(
            file_id=file_id,
            quality=quality,
            storage_type=storage_type,
            storage_key=storage_key,
            telegram_file_id=telegram_file_id,
            telegram_file_unique_id=telegram_file_unique_id,
            archive_chat_id=archive_chat_id,
            archive_message_id=archive_message_id,
            filename=filename,
            file_size=file_size,
            mime_type=mime_type,
            is_premium=is_premium,
            access_level=access_level,
        )
        self.session.add(variant)
        await self.session.flush()
        return variant

    async def get_by_id(self, variant_id: int) -> FileVariant | None:
        result = await self.session.execute(select(FileVariant).where(FileVariant.id == variant_id))
        return result.scalar_one_or_none()

    async def get_default_for_file(self, file_id: int) -> FileVariant | None:
        result = await self.session.execute(
            select(FileVariant)
            .where(FileVariant.file_id == file_id, FileVariant.is_active.is_(True))
            .order_by(FileVariant.is_premium.asc(), FileVariant.id.asc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def list_by_file(self, file_id: int) -> list[FileVariant]:
        result = await self.session.execute(
            select(FileVariant)
            .where(FileVariant.file_id == file_id, FileVariant.is_active.is_(True))
            .order_by(FileVariant.id)
        )
        return list(result.scalars().all())
