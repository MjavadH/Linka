from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any, cast

from aiogram.enums import MessageEntityType
from aiogram.types import MessageEntity

from models.enums import FileAccessLevel, StorageType, TemporaryMessageStatus
from models.file import DeepLink, File, FileVariant
from models.temporary_message import TemporaryMessage
from scheduler import deletions
from scheduler.deletions import TemporaryMessageDeletionJob
from services.file_delivery import FileDeliveryService
from services.files import FileService, FileVariantService
from services.sponsors import SponsorCheckResult
from services.storage import StoredFileReference


def test_file_editing_updates_file_and_variant_metadata() -> None:
    async def scenario() -> None:
        file = File(id=1, title="Old", description="old caption")
        variant = FileVariant(
            id=10,
            file_id=1,
            quality="720p",
            storage_type=StorageType.TELEGRAM,
            storage_key="telegram:old",
            telegram_file_id="old-file",
            archive_chat_id=-100,
            archive_message_id=5,
            media_type="document",
            is_premium=False,
            access_level=FileAccessLevel.FREE,
        )
        files = _InMemoryFileRepository(file)
        variants = _InMemoryVariantRepository(variant)

        updated_file = await FileService(cast(Any, files), cast(Any, _InMemoryDeepLinkRepository())).update_file(
            1,
            title="New title",
            description="New <b>caption</b>",
            caption_entities=[{"type": "bold", "offset": 4, "length": 7}],
        )
        updated_variant = await FileVariantService(cast(Any, variants), cast(Any, _NoopStorage())).update_variant(
            10,
            quality="1080p",
            is_premium=True,
            storage_key="telegram:new",
            telegram_file_id="new-file",
            archive_chat_id=-200,
            archive_message_id=9,
            caption="Variant caption",
            caption_entities=[{"type": "italic", "offset": 0, "length": 7}],
        )

        assert updated_file is file
        assert file.title == "New title"
        assert file.description == "New <b>caption</b>"
        assert file.caption_entities == [{"type": "bold", "offset": 4, "length": 7}]
        assert updated_variant is variant
        assert variant.quality == "1080p"
        assert variant.is_premium is True
        assert variant.access_level == FileAccessLevel.PREMIUM
        assert variant.storage_key == "telegram:new"
        assert variant.telegram_file_id == "new-file"
        assert variant.archive_chat_id == -200
        assert variant.archive_message_id == 9
        assert variant.caption == "Variant caption"

    asyncio.run(scenario())


def test_variant_deletion_soft_deletes_variant_and_disables_its_links_only() -> None:
    async def scenario() -> None:
        variant = FileVariant(
            id=10,
            file_id=1,
            quality="720p",
            storage_type=StorageType.TELEGRAM,
            storage_key="telegram:key",
            telegram_file_id="file-id",
            media_type="document",
            is_active=True,
        )
        links = _InMemoryDeepLinkRepository()
        deleted = await FileVariantService(cast(Any, _InMemoryVariantRepository(variant)), cast(Any, _NoopStorage())).delete_variant(
            10, cast(Any, links)
        )

        assert deleted is variant
        assert variant.is_active is False
        assert links.disabled_variant_ids == [10]

    asyncio.run(scenario())


def test_caption_delivery_uses_variant_caption_and_creates_temporary_deletion_record() -> None:
    async def scenario() -> None:
        file = File(id=1, title="Movie", description="Parent caption", is_active=True)
        variant = FileVariant(
            id=10,
            file_id=1,
            file=file,
            quality="720p",
            storage_type=StorageType.TELEGRAM,
            storage_key="telegram:key",
            telegram_file_id="file-id",
            media_type="document",
            caption="Variant caption",
            caption_entities=[{"type": "bold", "offset": 0, "length": 7}],
            is_premium=False,
            access_level=FileAccessLevel.FREE,
            is_active=True,
        )
        link = DeepLink(id=100, token="token", file_id=1, file=file, variant=variant, is_active=True)
        bot = _DeliveryBot()
        temporary_messages = _InMemoryTemporaryMessages()

        result = await FileDeliveryService(
            bot=cast(Any, bot),
            deep_links=cast(Any, _InMemoryDeepLinkRepository(active_link=link)),
            variants=cast(Any, _InMemoryVariantRepository(variant)),
            sponsors=cast(Any, _PassingSponsors()),
            premium=cast(Any, _NoPremiumRequired()),
            temporary_messages=cast(Any, temporary_messages),
            downloads=cast(Any, _InMemoryDownloads()),
            storage=cast(Any, _NoopStorage()),
            delete_after_seconds=60,
        ).deliver("token", user_id=7, telegram_id=700, chat_id=900)

        assert result.delivered is True
        assert bot.sent_documents[0]["caption"] == "Variant caption"
        assert bot.sent_documents[0]["caption_entities"] == [
            MessageEntity(type=MessageEntityType.BOLD, offset=0, length=7)
        ]
        assert temporary_messages.items[0].user_id == 7
        assert temporary_messages.items[0].chat_id == 900
        assert temporary_messages.items[0].message_id == 321
        assert temporary_messages.items[0].delete_at > datetime.now(UTC)

    asyncio.run(scenario())


def test_temporary_message_deletion_job_marks_due_messages_deleted(monkeypatch: Any) -> None:
    async def scenario() -> None:
        message = TemporaryMessage(
            id=1,
            user_id=7,
            chat_id=900,
            message_id=321,
            delete_at=datetime.now(UTC) - timedelta(seconds=1),
            status=TemporaryMessageStatus.PENDING,
        )
        repository = _DueTemporaryRepository([message])
        monkeypatch.setattr(deletions, "TemporaryMessageRepository", lambda session: repository)
        session = _CommitOnlySession()
        bot = _DeletionBot()

        await TemporaryMessageDeletionJob(cast(Any, bot), cast(Any, session)).run()

        assert bot.deleted == [(900, 321)]
        assert message.status == TemporaryMessageStatus.DELETED
        assert message.processed_at is not None
        assert session.committed is True

    asyncio.run(scenario())


class _InMemoryFileRepository:
    def __init__(self, file: File) -> None:
        self.file = file

    async def update_metadata(
        self,
        file_id: int,
        *,
        title: str | None = None,
        description: str | None = None,
        caption_entities: list[dict[str, object]] | None = None,
    ) -> File | None:
        if file_id != self.file.id:
            return None
        if title is not None:
            self.file.title = title
        if description is not None:
            self.file.description = description or None
            self.file.caption_entities = caption_entities
        return self.file

    async def get_by_id(self, file_id: int) -> File | None:
        return self.file if file_id == self.file.id else None

    async def soft_delete(self, file_id: int) -> None:
        if file_id == self.file.id:
            self.file.is_active = False


class _InMemoryVariantRepository:
    def __init__(self, variant: FileVariant) -> None:
        self.variant = variant

    async def update_metadata(self, variant_id: int, **kwargs: Any) -> FileVariant | None:
        if variant_id != self.variant.id:
            return None
        for key, value in kwargs.items():
            if value is None:
                continue
            setattr(self.variant, key, value)
        if "is_premium" in kwargs and kwargs["is_premium"] is not None:
            self.variant.access_level = FileAccessLevel.PREMIUM if kwargs["is_premium"] else FileAccessLevel.FREE
        return self.variant

    async def soft_delete(self, variant_id: int) -> FileVariant | None:
        if variant_id != self.variant.id:
            return None
        self.variant.is_active = False
        return self.variant

    async def get_default_for_file(self, file_id: int) -> FileVariant | None:
        return self.variant if self.variant.file_id == file_id and self.variant.is_active else None


class _InMemoryDeepLinkRepository:
    def __init__(self, active_link: DeepLink | None = None) -> None:
        self.active_link = active_link
        self.disabled_variant_ids: list[int] = []
        self.disabled_file_ids: list[int] = []

    async def get_active_by_token(self, token: str) -> DeepLink | None:
        if self.active_link is not None and self.active_link.token == token:
            return self.active_link
        return None

    async def disable_for_variant(self, variant_id: int) -> None:
        self.disabled_variant_ids.append(variant_id)

    async def disable_for_file(self, file_id: int) -> None:
        self.disabled_file_ids.append(file_id)


class _NoopStorage:
    async def get_file(self, variant: FileVariant) -> StoredFileReference:
        return StoredFileReference(StorageType.TELEGRAM, variant.storage_key, variant.telegram_file_id)


class _PassingSponsors:
    async def check_user(self, telegram_id: int) -> SponsorCheckResult:
        return SponsorCheckResult(passed=True, missing_requirements=[])


class _NoPremiumRequired:
    async def has_premium(self, user_id: int) -> bool:
        return False


class _InMemoryDownloads:
    async def create(self, **kwargs: Any) -> object:
        return SimpleNamespace(**kwargs)


class _InMemoryTemporaryMessages:
    def __init__(self) -> None:
        self.items: list[TemporaryMessage] = []

    async def create(
        self, chat_id: int, message_id: int, delete_at: datetime, user_id: int | None = None
    ) -> TemporaryMessage:
        item = TemporaryMessage(user_id=user_id, chat_id=chat_id, message_id=message_id, delete_at=delete_at)
        self.items.append(item)
        return item


class _DeliveryBot:
    def __init__(self) -> None:
        self.sent_documents: list[dict[str, Any]] = []

    async def send_document(self, **kwargs: Any) -> object:
        self.sent_documents.append(kwargs)
        return SimpleNamespace(message_id=321)


class _DueTemporaryRepository:
    def __init__(self, messages: list[TemporaryMessage]) -> None:
        self.messages = messages

    async def list_due(self, limit: int = 100) -> list[TemporaryMessage]:
        return self.messages[:limit]


class _DeletionBot:
    def __init__(self) -> None:
        self.deleted: list[tuple[int, int]] = []

    async def delete_message(self, chat_id: int, message_id: int) -> None:
        self.deleted.append((chat_id, message_id))


class _CommitOnlySession:
    def __init__(self) -> None:
        self.committed = False

    async def commit(self) -> None:
        self.committed = True
