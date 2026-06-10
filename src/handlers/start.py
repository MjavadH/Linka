from aiogram import Bot, F, Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import Settings
from keyboards.sponsors import sponsor_join_keyboard_for_sponsors
from repositories.downloads import DownloadRepository
from repositories.files import DeepLinkRepository, FileVariantRepository
from repositories.sponsors import SponsorRepository
from repositories.subscriptions import SubscriptionRepository
from repositories.temporary_messages import TemporaryMessageRepository
from repositories.user_sponsors import UserSponsorRepository
from repositories.users import UserRepository
from services.file_delivery import FileDeliveryService
from services.premium import PremiumService
from services.sponsors import SponsorService, UserSponsorService
from services.storage import build_storage_service

router = Router(name="start")


def _sponsor_services(session: AsyncSession, bot: Bot) -> tuple[SponsorService, PremiumService, UserSponsorService]:
    sponsor_service = SponsorService(SponsorRepository(session), bot)
    premium_service = PremiumService(SubscriptionRepository(session))
    user_sponsor_service = UserSponsorService(
        bot=bot,
        sponsors=sponsor_service,
        repository=UserSponsorRepository(session),
        premium=premium_service,
    )
    return sponsor_service, premium_service, user_sponsor_service


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
    sponsor_service, premium_service, user_sponsor_service = _sponsor_services(session, message.bot)
    access_result = await user_sponsor_service.ensure_access(user)
    if not access_result.passed:
        await message.answer(
            "Please join all required sponsor channels, then press <b>I've Joined</b>.",
            reply_markup=sponsor_join_keyboard_for_sponsors(access_result.missing_sponsors),
        )
        return

    service = FileDeliveryService(
        bot=message.bot,
        deep_links=DeepLinkRepository(session),
        variants=FileVariantRepository(session),
        sponsors=sponsor_service,
        premium=premium_service,
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
            "Please join all required sponsor channels, then press <b>I've Joined</b>.",
            reply_markup=sponsor_join_keyboard_for_sponsors(result.sponsor_check.missing_sponsors),
        )
    elif result.reason == "premium_required":
        await message.answer("This file requires an active premium subscription.")
    else:
        await message.answer("This file link is invalid or unavailable.")


@router.message(CommandStart())
async def start_plain(message: Message, session: AsyncSession) -> None:
    if message.from_user is None or message.bot is None:
        return
    user = await UserRepository(session).upsert_from_telegram(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
    )
    _, _, user_sponsor_service = _sponsor_services(session, message.bot)
    result = await user_sponsor_service.ensure_access(user)
    if result.passed:
        await message.answer("Welcome to Linka. Open a file deep link to receive protected content.")
        return
    await message.answer(
        "Please join all required sponsor channels to use Linka, then press <b>I've Joined</b>.",
        reply_markup=sponsor_join_keyboard_for_sponsors(result.missing_sponsors),
    )


@router.callback_query(F.data == "check_sponsors")
async def check_sponsors(callback: CallbackQuery, session: AsyncSession) -> None:
    if callback.from_user is None or callback.bot is None:
        return
    user = await UserRepository(session).upsert_from_telegram(
        telegram_id=callback.from_user.id,
        username=callback.from_user.username,
        first_name=callback.from_user.first_name,
    )
    _, _, user_sponsor_service = _sponsor_services(session, callback.bot)
    result = await user_sponsor_service.verify_joined(user)
    if result.passed:
        if isinstance(callback.message, Message):
            await callback.message.edit_text("✅ Sponsor verification complete. You can now use Linka.")
        await callback.answer("Verified")
        return
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            "You are still missing one or more sponsor channels. Join all channels, then press <b>I've Joined</b>.",
            reply_markup=sponsor_join_keyboard_for_sponsors(result.missing_sponsors),
        )
    await callback.answer("Please join all sponsors first.", show_alert=True)
