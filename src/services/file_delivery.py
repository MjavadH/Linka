from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import cast

from aiogram import Bot
from aiogram.types import Message, MessageEntity

from models.enums import FileAccessLevel
from models.file import DeepLink, FileVariant
from repositories.downloads import DownloadRepository
from repositories.files import DeepLinkRepository, FileVariantRepository
from repositories.temporary_messages import TemporaryMessageRepository
from services.premium import PremiumService
from services.sponsors import SponsorCheckResult, SponsorService
from services.storage import StorageService


@dataclass(frozen=True)
class DeliveryResult:
    delivered: bool
    reason: str | None = None
    sponsor_check: SponsorCheckResult | None = None


class FileDeliveryService:
    def __init__(
        self,
        bot: Bot,
        deep_links: DeepLinkRepository,
        variants: FileVariantRepository,
        sponsors: SponsorService,
        premium: PremiumService,
        temporary_messages: TemporaryMessageRepository,
        downloads: DownloadRepository,
        storage: StorageService,
        delete_after_seconds: int,
    ) -> None:
        self.bot = bot
        self.deep_links = deep_links
        self.variants = variants
        self.sponsors = sponsors
        self.premium = premium
        self.temporary_messages = temporary_messages
        self.downloads = downloads
        self.storage = storage
        self.delete_after_seconds = delete_after_seconds

    async def deliver(self, token: str, user_id: int, telegram_id: int, chat_id: int) -> DeliveryResult:
        deep_link = await self.deep_links.get_active_by_token(token)
        if deep_link is None or not deep_link.file.is_active:
            return DeliveryResult(delivered=False, reason="invalid_token")

        requires_premium = deep_link.requires_premium
        has_premium = await self.premium.has_premium(user_id)
        sponsor_check = SponsorCheckResult(True, [], [])
        if not has_premium:
            sponsor_check = await self.sponsors.check_user(telegram_id)
            if not sponsor_check.passed:
                return DeliveryResult(
                    delivered=False, reason="missing_sponsors", sponsor_check=sponsor_check
                )

        variant = await self._resolve_variant(deep_link, has_premium)
        if variant is None:
            return DeliveryResult(delivered=False, reason="file_unavailable")

        requires_premium = requires_premium or variant.is_premium or variant.access_level == FileAccessLevel.PREMIUM
        if requires_premium and not has_premium:
            return DeliveryResult(delivered=False, reason="premium_required")

        sent = await self._send_file(chat_id, variant)
        delete_after = datetime.now(UTC) + timedelta(seconds=self.delete_after_seconds)
        await self.temporary_messages.create(chat_id, sent.message_id, delete_after, user_id=user_id)
        await self.downloads.create(
            user_id=user_id,
            file_id=deep_link.file_id,
            variant_id=variant.id,
            deep_link_id=deep_link.id,
            token=token,
            is_premium_download=requires_premium,
        )
        return DeliveryResult(delivered=True)

    async def _resolve_variant(self, deep_link: DeepLink, has_premium: bool) -> FileVariant | None:
        if deep_link.variant and deep_link.variant.is_active:
            return cast(FileVariant, deep_link.variant)
        if has_premium:
            premium_variant = await self.variants.get_premium_for_file(deep_link.file_id)
            if premium_variant is not None:
                return premium_variant
        return await self.variants.get_default_for_file(deep_link.file_id)

    async def _send_file(self, chat_id: int, variant: FileVariant) -> Message:
        reference = await self.storage.get_file(variant)
        if reference.file_id is None:
            raise RuntimeError("Storage provider did not return a Telegram-sendable file reference")
        caption = variant.caption if variant.caption is not None else variant.file.description
        caption_entities_raw = (
            variant.caption_entities
            if variant.caption is not None
            else variant.file.caption_entities
        )
        caption_entities = _message_entities(caption_entities_raw)
        if variant.media_type == "video":
            return await self.bot.send_video(
                chat_id=chat_id,
                video=reference.file_id,
                caption=caption,
                caption_entities=caption_entities,
            )
        if variant.media_type == "audio":
            return await self.bot.send_audio(
                chat_id=chat_id,
                audio=reference.file_id,
                caption=caption,
                caption_entities=caption_entities,
            )
        return await self.bot.send_document(
            chat_id=chat_id,
            document=reference.file_id,
            caption=caption,
            caption_entities=caption_entities,
        )


def _message_entities(raw: list[dict[str, object]] | None) -> list[MessageEntity] | None:
    if raw is None:
        return None
    return [MessageEntity.model_validate(entity) for entity in raw]
