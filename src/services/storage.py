from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from aiogram import Bot
from aiogram.enums import ChatMemberStatus
from aiogram.types import Audio, Document, Message, Video

from models.enums import StorageType
from models.file import FileVariant


class StorageError(RuntimeError):
    """Raised when a storage provider cannot persist or resolve a file."""


@dataclass(frozen=True)
class StoredFile:
    storage_type: StorageType
    storage_key: str
    file_id: str
    file_unique_id: str | None
    archive_chat_id: int
    archive_message_id: int
    filename: str | None
    file_size: int | None
    mime_type: str | None


@dataclass(frozen=True)
class StoredFileReference:
    storage_type: StorageType
    storage_key: str
    file_id: str | None
    archive_chat_id: int | None = None
    archive_message_id: int | None = None


@dataclass(frozen=True)
class StorageValidationResult:
    is_valid: bool
    errors: tuple[str, ...] = ()


class StorageProvider(Protocol):
    storage_type: StorageType

    async def save_file(self, message: Message) -> StoredFile: ...

    async def get_file(self, variant: FileVariant) -> StoredFileReference: ...

    async def delete_file(self, variant: FileVariant) -> None: ...

    async def validate_file(self, variant: FileVariant) -> StorageValidationResult: ...


class TelegramStorageProvider:
    """Telegram archive-channel-backed storage provider."""

    storage_type = StorageType.TELEGRAM

    def __init__(self, bot: Bot, archive_chat_id: int) -> None:
        self.bot = bot
        self.archive_chat_id = archive_chat_id

    async def save_file(self, message: Message) -> StoredFile:
        media = _extract_media(message)
        if media is None:
            raise StorageError("Only document, video, and audio uploads are supported.")

        archived = await self.bot.copy_message(
            chat_id=self.archive_chat_id,
            from_chat_id=message.chat.id,
            message_id=message.message_id,
        )
        storage_key = f"telegram:{self.archive_chat_id}:{archived.message_id}"
        return StoredFile(
            storage_type=self.storage_type,
            storage_key=storage_key,
            file_id=media.file_id,
            file_unique_id=media.file_unique_id,
            archive_chat_id=self.archive_chat_id,
            archive_message_id=archived.message_id,
            filename=getattr(media, "file_name", None),
            file_size=media.file_size,
            mime_type=media.mime_type,
        )

    async def get_file(self, variant: FileVariant) -> StoredFileReference:
        return StoredFileReference(
            storage_type=self.storage_type,
            storage_key=variant.storage_key,
            file_id=variant.telegram_file_id,
            archive_chat_id=variant.archive_chat_id,
            archive_message_id=variant.archive_message_id,
        )

    async def delete_file(self, variant: FileVariant) -> None:
        # V1 uses soft deletion at the business layer to preserve archive and audit history.
        return None

    async def validate_file(self, variant: FileVariant) -> StorageValidationResult:
        errors: list[str] = []
        if not variant.telegram_file_id:
            errors.append("missing Telegram file_id")
        if variant.archive_chat_id is None:
            errors.append("missing archive chat id")
        if variant.archive_message_id is None:
            errors.append("missing archive message id")
        return StorageValidationResult(is_valid=not errors, errors=tuple(errors))


class StorageService:
    def __init__(self, providers: dict[StorageType, StorageProvider]) -> None:
        self.providers = providers

    def provider_for(self, storage_type: StorageType) -> StorageProvider:
        try:
            return self.providers[storage_type]
        except KeyError as exc:
            raise StorageError(f"Storage provider is not configured: {storage_type}") from exc

    async def save_file(self, storage_type: StorageType, message: Message) -> StoredFile:
        return await self.provider_for(storage_type).save_file(message)

    async def get_file(self, variant: FileVariant) -> StoredFileReference:
        return await self.provider_for(variant.storage_type).get_file(variant)

    async def delete_file(self, variant: FileVariant) -> None:
        await self.provider_for(variant.storage_type).delete_file(variant)

    async def validate_file(self, variant: FileVariant) -> StorageValidationResult:
        return await self.provider_for(variant.storage_type).validate_file(variant)


class ArchiveChannelValidationService:
    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    async def validate(self, archive_chat_id: int) -> StorageValidationResult:
        errors: list[str] = []
        bot_user = await self.bot.get_me()
        try:
            member = await self.bot.get_chat_member(archive_chat_id, bot_user.id)
        except Exception as exc:  # TelegramBadRequest subclasses vary by failure mode.
            return StorageValidationResult(False, (f"cannot access archive channel: {exc}",))

        if member.status not in {ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR}:
            errors.append("bot must be an administrator in the archive channel")
        can_post = bool(getattr(member, "can_post_messages", False)) or member.status == ChatMemberStatus.CREATOR
        if not can_post:
            errors.append("bot must be allowed to post messages in the archive channel")
        if member.status != ChatMemberStatus.CREATOR and not bool(getattr(member, "can_delete_messages", False)):
            errors.append("bot must be able to read/manage archive channel messages")
        return StorageValidationResult(is_valid=not errors, errors=tuple(errors))


def build_storage_service(bot: Bot, archive_chat_id: int | None) -> StorageService:
    providers: dict[StorageType, StorageProvider] = {}
    if archive_chat_id is not None:
        providers[StorageType.TELEGRAM] = TelegramStorageProvider(bot, archive_chat_id)
    return StorageService(providers)


def _extract_media(message: Message) -> Document | Video | Audio | None:
    return message.document or message.video or message.audio
