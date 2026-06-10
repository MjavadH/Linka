from aiogram import Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import Settings
from keyboards.sponsors import sponsor_join_keyboard
from repositories.downloads import DownloadRepository
from repositories.files import DeepLinkRepository, FileVariantRepository
from repositories.sponsors import SponsorRepository
from repositories.subscriptions import SubscriptionRepository
from repositories.temporary_messages import TemporaryMessageRepository
from repositories.users import UserRepository
from services.file_delivery import FileDeliveryService
from services.premium import PremiumService
from services.sponsors import SponsorService
from services.storage import build_storage_service

router = Router(name="start")


@router.message(CommandStart(deep_link=True))
async def start_with_deep_link(
    message: Message, command: CommandObject, settings: Settings, session: AsyncSession
) -> None:
    if message.from_user is None or message.bot is None:
        return
    token = command.args
    if not token:
        await message.answer("Invalid link.")
        return

    user = await UserRepository(session).upsert_from_telegram(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
    )
    service = FileDeliveryService(
        bot=message.bot,
        deep_links=DeepLinkRepository(session),
        variants=FileVariantRepository(session),
        sponsors=SponsorService(SponsorRepository(session), message.bot),
        premium=PremiumService(SubscriptionRepository(session)),
        temporary_messages=TemporaryMessageRepository(session),
        downloads=DownloadRepository(session),
        storage=build_storage_service(message.bot, settings.archive_chat_id),
        delete_after_seconds=settings.file_delete_after_seconds,
    )
    result = await service.deliver(token, user.id, message.from_user.id, message.chat.id)

    if result.delivered:
        await message.answer("Your file has been delivered. It will be removed automatically.")
    elif result.reason == "missing_sponsors" and result.sponsor_check is not None:
        await message.answer(
            "Please join the required sponsor channels, then open the link again.",
            reply_markup=sponsor_join_keyboard(result.sponsor_check.missing_requirements),
        )
    elif result.reason == "premium_required":
        await message.answer("This file requires an active premium subscription.")
    else:
        await message.answer("This file link is invalid or unavailable.")


@router.message(CommandStart())
async def start_plain(message: Message) -> None:
    await message.answer("Welcome to Linka. Open a file deep link to receive protected content.")
