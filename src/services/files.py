from __future__ import annotations

from dataclasses import dataclass
from secrets import token_urlsafe

from aiogram.types import Message

from models.enums import FileAccessLevel, StorageType
from models.file import DeepLink, File, FileVariant
from repositories.files import DeepLinkRepository, FileRepository, FileVariantRepository
from services.storage import StorageService, StoredFile


@dataclass(frozen=True)
class FileListItem:
    file: File
    variant_count: int
    download_count: int


class FileService:
    def __init__(self, files: FileRepository, deep_links: DeepLinkRepository) -> None:
        self.files = files
        self.deep_links = deep_links

    async def create_file(self, title: str, description: str | None = None) -> File:
        return await self.files.create(title=title, description=description)

    async def get_file(self, file_id: int) -> File | None:
        return await self.files.get_by_id(file_id)

    async def list_files(self, page: int = 1, search: str | None = None) -> tuple[list[FileListItem], int]:
        rows, total = await self.files.list_with_stats(page=page, search=search)
        return ([FileListItem(file=row[0], variant_count=row[1], download_count=row[2]) for row in rows], total)

    async def soft_delete_file(self, file_id: int) -> None:
        await self.files.soft_delete(file_id)
        await self.deep_links.disable_for_file(file_id)


class FileVariantService:
    def __init__(self, variants: FileVariantRepository, storage: StorageService) -> None:
        self.variants = variants
        self.storage = storage

    async def create_variant_from_message(
        self,
        *,
        file_id: int,
        quality: str,
        is_premium: bool,
        message: Message,
        storage_type: StorageType = StorageType.TELEGRAM,
    ) -> FileVariant:
        stored = await self.storage.save_file(storage_type, message)
        return await self.variants.create(
            file_id=file_id,
            quality=quality,
            storage_type=stored.storage_type,
            storage_key=stored.storage_key,
            telegram_file_id=stored.file_id,
            telegram_file_unique_id=stored.file_unique_id,
            archive_chat_id=stored.archive_chat_id,
            archive_message_id=stored.archive_message_id,
            filename=stored.filename,
            file_size=stored.file_size,
            mime_type=stored.mime_type,
            is_premium=is_premium,
            access_level=FileAccessLevel.PREMIUM if is_premium else FileAccessLevel.FREE,
        )


    async def create_variant_from_stored(
        self,
        *,
        file_id: int,
        quality: str,
        is_premium: bool,
        stored: StoredFile,
    ) -> FileVariant:
        return await self.variants.create(
            file_id=file_id,
            quality=quality,
            storage_type=stored.storage_type,
            storage_key=stored.storage_key,
            telegram_file_id=stored.file_id,
            telegram_file_unique_id=stored.file_unique_id,
            archive_chat_id=stored.archive_chat_id,
            archive_message_id=stored.archive_message_id,
            filename=stored.filename,
            file_size=stored.file_size,
            mime_type=stored.mime_type,
            is_premium=is_premium,
            access_level=FileAccessLevel.PREMIUM if is_premium else FileAccessLevel.FREE,
        )

    async def get_file_variants(self, file_id: int) -> list[FileVariant]:
        return await self.variants.list_by_file(file_id)


class DeepLinkService:
    def __init__(self, links: DeepLinkRepository, bot_username: str) -> None:
        self.links = links
        self.bot_username = bot_username

    async def get_or_create_for_variant(self, variant: FileVariant) -> DeepLink:
        existing = await self.links.get_active_by_variant_id(variant.id)
        if existing is not None:
            return existing
        for _ in range(5):
            token = token_urlsafe(24)
            if await self.links.get_by_token(token) is None:
                return await self.links.create(
                    token=token,
                    file_id=variant.file_id,
                    file_variant_id=variant.id,
                    requires_premium=variant.is_premium,
                )
        raise RuntimeError("Unable to generate unique deep-link token")

    def build_link(self, token: str) -> str:
        return f"https://t.me/{self.bot_username}?start={token}"
