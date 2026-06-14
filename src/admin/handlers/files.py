from __future__ import annotations

from html import escape
from math import ceil
from typing import Any, cast

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, MessageEntity
from sqlalchemy.ext.asyncio import AsyncSession

from admin.callbacks import (
    AdminFileAction,
    AdminFileCallback,
    AdminMenuCallback,
    AdminNavAction,
    AdminNavigationCallback,
    AdminSection,
)
from admin.keyboards import (
    content_type_keyboard,
    episode_detail_keyboard,
    episodes_list_keyboard,
    file_detail_keyboard,
    file_edit_keyboard,
    file_list_keyboard,
    file_management_keyboard,
    premium_choice_keyboard,
    series_detail_keyboard,
    series_list_keyboard,
    variant_edit_keyboard,
    variant_selection_keyboard,
)
from admin.states.files import AdminFileStates
from core.config import Settings
from models.enums import StorageType
from repositories.audit_logs import AuditLogRepository
from repositories.files import (
    PAGE_SIZE,
    DeepLinkRepository,
    EpisodeRepository,
    FileRepository,
    FileVariantRepository,
    SeriesRepository,
)
from services.audit_logs import AuditLogService
from services.files import (
    DeepLinkService,
    EpisodeService,
    FileListItem,
    FileService,
    FileVariantService,
    SeriesListItem,
    SeriesService,
)
from services.storage import (
    ArchiveChannelValidationService,
    StorageError,
    StoredFile,
    build_storage_service,
)

router = Router(name="admin_files")


@router.callback_query(AdminMenuCallback.filter(F.section == AdminSection.FILES))
async def open_files(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await show_files(callback)


@router.callback_query(
    AdminNavigationCallback.filter(
        (F.target == AdminSection.FILES) & (F.action.in_({AdminNavAction.BACK}))
    )
)
async def navigate_files(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await show_files(callback)


@router.callback_query(AdminFileCallback.filter(F.action == AdminFileAction.ADD))
async def add_file(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            "➕ <b>Add Content</b>\n\nChoose the content type to create.",
            reply_markup=content_type_keyboard(),
        )
    await callback.answer()


@router.callback_query(AdminFileCallback.filter(F.action == AdminFileAction.ADD_MOVIE))
async def add_movie(callback: CallbackQuery, state: FSMContext, settings: Settings) -> None:
    if not await _validate_archive(callback, settings):
        return
    await state.set_state(AdminFileStates.waiting_for_upload)
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            "📁 <b>Add Movie</b>\n\nSend a Telegram document, video, or audio file.",
            reply_markup=file_management_keyboard(),
        )
    await callback.answer()


@router.callback_query(AdminFileCallback.filter(F.action == AdminFileAction.ADD_SERIES))
async def add_series(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminFileStates.waiting_for_series_name)
    if isinstance(callback.message, Message):
        await callback.message.edit_text("📺 <b>Add Series</b>\n\nSend the series name.")
    await callback.answer()


@router.message(AdminFileStates.waiting_for_series_name, F.text)
async def receive_series_name(message: Message, state: FSMContext, session: AsyncSession) -> None:
    series = await SeriesService(
        SeriesRepository(session), EpisodeRepository(session), DeepLinkRepository(session)
    ).create_series(_message_text(message).strip())
    await state.clear()
    await _audit(session, message.from_user, "Create Series", "Series", series.id, series.name)
    await message.answer("✅ Series created.")
    await _send_series_detail_message(message, series.id, session)


@router.message(AdminFileStates.waiting_for_upload, F.document | F.video | F.audio)
async def receive_file_upload(message: Message, state: FSMContext, settings: Settings) -> None:
    if message.bot is None or settings.archive_chat_id is None:
        await message.answer("Archive channel is not configured.")
        return
    storage = build_storage_service(message.bot, settings.archive_chat_id)
    try:
        stored = await storage.save_file(StorageType.TELEGRAM, message)
    except StorageError as exc:
        await message.answer(f"Unable to archive file: {escape(str(exc))}")
        return
    await state.update_data(stored_file=_stored_to_state(stored))
    await state.set_state(AdminFileStates.waiting_for_title)
    await message.answer("✅ File archived. Now send the public title for this file.")


@router.message(AdminFileStates.waiting_for_upload)
async def reject_unsupported_upload(message: Message) -> None:
    await message.answer("Please send a supported document, video, or audio file.")


@router.message(AdminFileStates.waiting_for_title, F.text)
async def receive_file_title(message: Message, state: FSMContext) -> None:
    await state.update_data(title=_message_text(message).strip())
    await state.set_state(AdminFileStates.waiting_for_quality)
    await message.answer("Send the quality/variant label, for example: 480p, 720p, 1080p, or 4K.")


@router.message(AdminFileStates.waiting_for_quality, F.text)
async def receive_file_quality(message: Message, state: FSMContext) -> None:
    await state.update_data(quality=_message_text(message).strip())
    await state.set_state(AdminFileStates.waiting_for_premium)
    await message.answer("Should this variant require premium?", reply_markup=premium_choice_keyboard())


@router.callback_query(AdminFileStates.waiting_for_premium, F.data.startswith("file_premium:"))
async def finish_file_registration(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, settings: Settings
) -> None:
    if callback.bot is None:
        return
    data = await state.get_data()
    stored = _stored_from_state(data["stored_file"])
    is_premium = _premium_choice(callback.data)
    file_service = FileService(FileRepository(session), DeepLinkRepository(session))
    variant_service = FileVariantService(
        FileVariantRepository(session), build_storage_service(callback.bot, settings.archive_chat_id)
    )
    link_service = DeepLinkService(DeepLinkRepository(session), settings.bot_username)
    file = await file_service.create_file(
        title=cast(str, data["title"]),
        description=stored.caption,
        caption_entities=stored.caption_entities,
    )
    variant = await variant_service.create_variant_from_stored(
        file_id=file.id,
        quality=cast(str, data["quality"]),
        is_premium=is_premium,
        stored=stored,
    )
    link = await link_service.get_or_create_for_variant(variant)
    await _audit(session, callback.from_user, "Create Movie", "Movie", file.id, file.title)
    await _audit(session, callback.from_user, "Create Variant", "Variant", variant.id, f"{file.title}\n{variant.quality}{' Premium' if variant.is_premium else ''}")
    await state.clear()
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            "✅ <b>File registered</b>\n\n"
            f"Title: <b>{escape(file.title)}</b>\n"
            f"Variant: <b>{escape(variant.quality)}</b>\n"
            f"Premium: <b>{'yes' if variant.is_premium else 'no'}</b>\n"
            f"Deep link:\n<code>{escape(link_service.build_link(link.token))}</code>",
            reply_markup=file_detail_keyboard(file.id),
        )
    await callback.answer()


@router.callback_query(AdminFileCallback.filter(F.action.in_({AdminFileAction.LIST, AdminFileAction.LIST_MOVIES, AdminFileAction.PAGE})))
async def list_files(
    callback: CallbackQuery, callback_data: AdminFileCallback, session: AsyncSession
) -> None:
    await _send_file_list(callback, session, page=callback_data.page)


@router.callback_query(AdminFileCallback.filter(F.action == AdminFileAction.SEARCH))
async def search_files(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminFileStates.waiting_for_search)
    if isinstance(callback.message, Message):
        await callback.message.edit_text("🔍 Send a movie title, series name, or filename search query.")
    await callback.answer()


@router.message(AdminFileStates.waiting_for_search, F.text)
async def receive_search(message: Message, state: FSMContext, session: AsyncSession) -> None:
    await state.clear()
    rows, total = await FileService(FileRepository(session), DeepLinkRepository(session)).list_files(
        page=1, search=_message_text(message).strip()
    )
    await message.answer(
        _search_text(rows, await SeriesService(SeriesRepository(session), EpisodeRepository(session), DeepLinkRepository(session)).list_series(page=1, search=_message_text(message).strip()), 1, _message_text(message).strip()),
        reply_markup=file_management_keyboard(),
    )


@router.callback_query(AdminFileCallback.filter(F.action == AdminFileAction.VIEW))
async def view_file(
    callback: CallbackQuery, callback_data: AdminFileCallback, session: AsyncSession
) -> None:
    await _send_file_detail(callback, callback_data.file_id, session)


@router.callback_query(AdminFileCallback.filter(F.action == AdminFileAction.LINKS))
async def show_deep_links(
    callback: CallbackQuery, callback_data: AdminFileCallback, session: AsyncSession, settings: Settings
) -> None:
    file = await FileRepository(session).get_by_id(callback_data.file_id)
    if file is None:
        await callback.answer("File not found", show_alert=True)
        return
    links_repo = DeepLinkRepository(session)
    links_service = DeepLinkService(links_repo, settings.bot_username)
    lines = [f"🔗 <b>Deep links for {escape(file.title)}</b>", ""]
    for variant in file.variants:
        link = await links_service.get_or_create_for_variant(variant)
        lines.append(f"<b>{escape(variant.quality)}</b>: <code>{escape(links_service.build_link(link.token))}</code>")
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
                "\n".join(lines),
                reply_markup=episode_detail_keyboard(callback_data.series_id, callback_data.episode_id, file.id)
                if callback_data.episode_id
                else file_detail_keyboard(file.id),
            )
    await callback.answer()


@router.callback_query(AdminFileCallback.filter(F.action == AdminFileAction.DELETE_FILE))
async def delete_file(
    callback: CallbackQuery, callback_data: AdminFileCallback, session: AsyncSession
) -> None:
    file = await FileRepository(session).get_by_id(callback_data.file_id)
    await FileService(FileRepository(session), DeepLinkRepository(session)).soft_delete_file(callback_data.file_id)
    await _audit(session, callback.from_user, "Delete Movie", "Movie", callback_data.file_id, file.title if file else str(callback_data.file_id))
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            "🗑 File deleted. Download history and statistics were preserved; deep links are disabled.",
            reply_markup=file_management_keyboard(),
        )
    await callback.answer("File deleted")


@router.callback_query(AdminFileCallback.filter(F.action == AdminFileAction.ADD_VARIANT))
async def add_variant(callback: CallbackQuery, callback_data: AdminFileCallback, state: FSMContext) -> None:
    await state.update_data(file_id=callback_data.file_id, series_id=callback_data.series_id, episode_id=callback_data.episode_id)
    await state.set_state(AdminFileStates.waiting_for_variant_upload)
    if isinstance(callback.message, Message):
        await callback.message.edit_text("➕ Send the document, video, or audio for the new variant.")
    await callback.answer()


@router.message(AdminFileStates.waiting_for_variant_upload, F.document | F.video | F.audio)
async def receive_variant_upload(message: Message, state: FSMContext, settings: Settings) -> None:
    if message.bot is None or settings.archive_chat_id is None:
        await message.answer("Archive channel is not configured.")
        return
    stored = await build_storage_service(message.bot, settings.archive_chat_id).save_file(
        StorageType.TELEGRAM, message
    )
    await state.update_data(stored_file=_stored_to_state(stored))
    await state.set_state(AdminFileStates.waiting_for_variant_quality)
    await message.answer("Send the quality/variant label for this upload.")


@router.message(AdminFileStates.waiting_for_variant_quality, F.text)
async def receive_variant_quality(message: Message, state: FSMContext) -> None:
    await state.update_data(quality=_message_text(message).strip())
    await state.set_state(AdminFileStates.waiting_for_variant_premium)
    await message.answer("Should this variant require premium?", reply_markup=premium_choice_keyboard())


@router.callback_query(AdminFileStates.waiting_for_variant_premium, F.data.startswith("file_premium:"))
async def finish_variant_registration(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, settings: Settings
) -> None:
    if callback.bot is None:
        return
    data = await state.get_data()
    variant = await FileVariantService(
        FileVariantRepository(session), build_storage_service(callback.bot, settings.archive_chat_id)
    ).create_variant_from_stored(
        file_id=int(data["file_id"]),
        quality=cast(str, data["quality"]),
        episode_id=int(data.get("episode_id") or 0) or None,
        is_premium=_premium_choice(callback.data),
        stored=_stored_from_state(data["stored_file"]),
    )
    link = await DeepLinkService(DeepLinkRepository(session), settings.bot_username).get_or_create_for_variant(
        variant
    )
    await _audit(session, callback.from_user, "Create Variant", "Variant", variant.id, await _variant_details(session, variant.id))
    await state.clear()
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            "✅ Variant added.\n\n"
            f"Deep link:\n<code>{escape(DeepLinkService(DeepLinkRepository(session), settings.bot_username).build_link(link.token))}</code>",
            reply_markup=episode_detail_keyboard(int(data["series_id"]), int(data["episode_id"]), variant.file_id) if int(data.get("episode_id") or 0) else file_detail_keyboard(variant.file_id),
        )
    await callback.answer()


@router.callback_query(AdminFileCallback.filter(F.action == AdminFileAction.EDIT))
async def edit_file_menu(
    callback: CallbackQuery, callback_data: AdminFileCallback, session: AsyncSession
) -> None:
    file = await FileRepository(session).get_by_id(callback_data.file_id)
    if file is None or not file.is_active:
        await callback.answer("File not found", show_alert=True)
        return
    current_caption = file.description or "—"
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            "✏️ <b>Edit File</b>\n\n"
            f"Current title: <b>{escape(file.title)}</b>\n"
            f"Current description/caption:\n<blockquote>{escape(current_caption)}</blockquote>\n\n"
            "Choose the field to edit, or choose a variant to edit variant metadata.",
            reply_markup=file_edit_keyboard(file.id, file.variants),
        )
    await callback.answer()


@router.callback_query(AdminFileCallback.filter(F.action == AdminFileAction.EDIT_TITLE))
async def edit_file_title(callback: CallbackQuery, callback_data: AdminFileCallback, state: FSMContext, session: AsyncSession) -> None:
    file = await FileRepository(session).get_by_id(callback_data.file_id)
    if file is None:
        await callback.answer("File not found", show_alert=True)
        return
    await state.update_data(file_id=file.id)
    await state.set_state(AdminFileStates.waiting_for_edit_title)
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            f"Current title: <b>{escape(file.title)}</b>\n\nSend the new title."
        )
    await callback.answer()


@router.message(AdminFileStates.waiting_for_edit_title, F.text)
async def save_file_title(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    file_id = int(data["file_id"])
    file = await FileService(FileRepository(session), DeepLinkRepository(session)).update_file(
        file_id, title=_message_text(message).strip()
    )
    await _audit(session, message.from_user, "Edit Movie", "Movie", file_id, file.title if file else str(file_id))
    await state.clear()
    await message.answer("✅ Title updated.")
    await _send_file_detail_message(message, file_id, session)


@router.callback_query(AdminFileCallback.filter(F.action == AdminFileAction.EDIT_CAPTION))
async def edit_file_caption(callback: CallbackQuery, callback_data: AdminFileCallback, state: FSMContext, session: AsyncSession) -> None:
    file = await FileRepository(session).get_by_id(callback_data.file_id)
    if file is None:
        await callback.answer("File not found", show_alert=True)
        return
    await state.update_data(file_id=file.id)
    await state.set_state(AdminFileStates.waiting_for_edit_caption)
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            "Current description/caption:\n"
            f"<blockquote>{escape(file.description or '—')}</blockquote>\n\n"
            "Send the new description/caption. Formatting will be preserved. Send '-' to clear."
        )
    await callback.answer()


@router.message(AdminFileStates.waiting_for_edit_caption, F.text)
async def save_file_caption(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    file_id = int(data["file_id"])
    caption = None if _message_text(message).strip() == "-" else _message_text(message)
    file = await FileService(FileRepository(session), DeepLinkRepository(session)).update_file(
        file_id,
        description=caption or "",
        caption_entities=_entities_to_json(message.entities),
    )
    await _audit(session, message.from_user, "Edit Movie", "Movie", file_id, file.title if file else str(file_id))
    await state.clear()
    await message.answer("✅ Description/caption updated.")
    await _send_file_detail_message(message, file_id, session)


@router.callback_query(AdminFileCallback.filter(F.action == AdminFileAction.EDIT_VARIANT))
async def edit_variant_menu(callback: CallbackQuery, callback_data: AdminFileCallback, session: AsyncSession) -> None:
    variant = await FileVariantRepository(session).get_by_id(callback_data.variant_id)
    if variant is None or not variant.is_active:
        await callback.answer("Variant not found", show_alert=True)
        return
    text = (
        "✏️ <b>Edit Variant</b>\n\n"
        f"Quality: <b>{escape(variant.quality)}</b>\n"
        f"Premium: <b>{'yes' if variant.is_premium else 'no'}</b>\n"
        f"Storage: <b>{variant.storage_type.value}</b>\n"
        f"Storage key: <code>{escape(variant.storage_key)}</code>\n"
        f"Telegram file ID: <code>{escape(variant.telegram_file_id or '—')}</code>\n"
        f"Archive: <code>{variant.archive_chat_id or '—'} / {variant.archive_message_id or '—'}</code>\n"
        f"Caption: <blockquote>{escape(variant.caption or 'inherits parent caption')}</blockquote>"
    )
    if isinstance(callback.message, Message):
        await callback.message.edit_text(text, reply_markup=variant_edit_keyboard(variant.file_id, variant.id, callback_data.series_id, callback_data.episode_id))
    await callback.answer()


@router.callback_query(AdminFileCallback.filter(F.action == AdminFileAction.EDIT_VARIANT_QUALITY))
async def edit_variant_quality(callback: CallbackQuery, callback_data: AdminFileCallback, state: FSMContext, session: AsyncSession) -> None:
    variant = await FileVariantRepository(session).get_by_id(callback_data.variant_id)
    if variant is None:
        await callback.answer("Variant not found", show_alert=True)
        return
    await state.update_data(file_id=variant.file_id, variant_id=variant.id, series_id=callback_data.series_id, episode_id=callback_data.episode_id)
    await state.set_state(AdminFileStates.waiting_for_edit_variant_quality)
    if isinstance(callback.message, Message):
        await callback.message.edit_text(f"Current quality: <b>{escape(variant.quality)}</b>\n\nSend the new quality label.")
    await callback.answer()


@router.message(AdminFileStates.waiting_for_edit_variant_quality, F.text)
async def save_variant_quality(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    file_id = int(data["file_id"])
    await FileVariantService(FileVariantRepository(session), build_storage_service(cast(Bot, message.bot), None)).update_variant(
        int(data["variant_id"]), quality=_message_text(message).strip()
    )
    await _audit(session, message.from_user, "Edit Variant", "Variant", int(data["variant_id"]), await _variant_details(session, int(data["variant_id"])))
    await state.clear()
    await message.answer("✅ Variant quality updated.")
    if int(data.get("episode_id") or 0):
        await _send_episode_detail_message(message, int(data["episode_id"]), session)
    else:
        await _send_file_detail_message(message, file_id, session)


@router.callback_query(AdminFileCallback.filter(F.action == AdminFileAction.EDIT_VARIANT_PREMIUM))
async def edit_variant_premium(callback: CallbackQuery, callback_data: AdminFileCallback) -> None:
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            "Choose the new premium status for this variant.",
            reply_markup=premium_choice_keyboard(callback_data.file_id, callback_data.variant_id, callback_data.series_id, callback_data.episode_id),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("file_premium:"))
async def save_variant_premium(callback: CallbackQuery, session: AsyncSession) -> None:
    parts = (callback.data or "").split(":")
    if len(parts) < 4 or parts[2] == "0" or parts[3] == "0":
        return
    file_id = int(parts[2])
    variant_id = int(parts[3])
    episode_id = int(parts[5]) if len(parts) > 5 and parts[5] else 0
    await FileVariantService(FileVariantRepository(session), build_storage_service(cast(Bot, callback.bot), None)).update_variant(
        variant_id, is_premium=parts[1] == "1"
    )
    await _audit(session, callback.from_user, "Edit Variant", "Variant", variant_id, await _variant_details(session, variant_id))
    if isinstance(callback.message, Message):
        if episode_id:
            await _edit_episode_detail_message(callback.message, episode_id, session)
        else:
            await _edit_file_detail_message(callback.message, file_id, session)
    await callback.answer("Premium status updated")


@router.callback_query(AdminFileCallback.filter(F.action == AdminFileAction.EDIT_VARIANT_CAPTION))
async def edit_variant_caption(callback: CallbackQuery, callback_data: AdminFileCallback, state: FSMContext, session: AsyncSession) -> None:
    variant = await FileVariantRepository(session).get_by_id(callback_data.variant_id)
    if variant is None:
        await callback.answer("Variant not found", show_alert=True)
        return
    await state.update_data(file_id=variant.file_id, variant_id=variant.id, series_id=callback_data.series_id, episode_id=callback_data.episode_id)
    await state.set_state(AdminFileStates.waiting_for_edit_variant_caption)
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            "Current variant caption:\n"
            f"<blockquote>{escape(variant.caption or 'inherits parent caption')}</blockquote>\n\n"
            "Send the new variant caption. Formatting will be preserved. Send '-' to clear/inherit parent."
        )
    await callback.answer()


@router.message(AdminFileStates.waiting_for_edit_variant_caption, F.text)
async def save_variant_caption(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    file_id = int(data["file_id"])
    caption = None if _message_text(message).strip() == "-" else _message_text(message)
    await FileVariantService(FileVariantRepository(session), build_storage_service(cast(Bot, message.bot), None)).update_variant(
        int(data["variant_id"]), caption=caption or "", caption_entities=_entities_to_json(message.entities)
    )
    await _audit(session, message.from_user, "Edit Variant", "Variant", int(data["variant_id"]), await _variant_details(session, int(data["variant_id"])))
    await state.clear()
    await message.answer("✅ Variant caption updated.")
    if int(data.get("episode_id") or 0):
        await _send_episode_detail_message(message, int(data["episode_id"]), session)
    else:
        await _send_file_detail_message(message, file_id, session)


@router.callback_query(AdminFileCallback.filter(F.action == AdminFileAction.EDIT_VARIANT_STORAGE))
async def edit_variant_storage(callback: CallbackQuery, callback_data: AdminFileCallback, state: FSMContext, session: AsyncSession) -> None:
    variant = await FileVariantRepository(session).get_by_id(callback_data.variant_id)
    if variant is None:
        await callback.answer("Variant not found", show_alert=True)
        return
    await state.update_data(file_id=variant.file_id, variant_id=variant.id, series_id=callback_data.series_id, episode_id=callback_data.episode_id)
    await state.set_state(AdminFileStates.waiting_for_edit_variant_storage)
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            "Current storage metadata:\n"
            f"storage_key=<code>{escape(variant.storage_key)}</code>\n"
            f"telegram_file_id=<code>{escape(variant.telegram_file_id or '')}</code>\n"
            f"archive_chat_id=<code>{variant.archive_chat_id or ''}</code>\n"
            f"archive_message_id=<code>{variant.archive_message_id or ''}</code>\n\n"
            "Send replacement values as key=value lines. Omit fields you do not want to change."
        )
    await callback.answer()


@router.message(AdminFileStates.waiting_for_edit_variant_storage, F.text)
async def save_variant_storage(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    file_id = int(data["file_id"])
    values = _parse_key_value_lines(_message_text(message))
    await FileVariantService(FileVariantRepository(session), build_storage_service(cast(Bot, message.bot), None)).update_variant(
        int(data["variant_id"]),
        storage_key=values.get("storage_key"),
        telegram_file_id=values.get("telegram_file_id"),
        archive_chat_id=_optional_int(values.get("archive_chat_id")),
        archive_message_id=_optional_int(values.get("archive_message_id")),
    )
    await _audit(session, message.from_user, "Edit Variant", "Variant", int(data["variant_id"]), await _variant_details(session, int(data["variant_id"])))
    await state.clear()
    await message.answer("✅ Storage metadata updated.")
    if int(data.get("episode_id") or 0):
        await _send_episode_detail_message(message, int(data["episode_id"]), session)
    else:
        await _send_file_detail_message(message, file_id, session)


@router.callback_query(AdminFileCallback.filter(F.action == AdminFileAction.DELETE_VARIANT))
async def delete_variant_menu(callback: CallbackQuery, callback_data: AdminFileCallback, session: AsyncSession) -> None:
    file = await FileRepository(session).get_by_id(callback_data.file_id)
    if file is None:
        await callback.answer("File not found", show_alert=True)
        return
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            "❌ Select the variant to delete. Other variants will remain available.",
            reply_markup=variant_selection_keyboard(file.id, file.variants, AdminFileAction.DELETE_VARIANT_SELECT, callback_data.series_id, callback_data.episode_id),
        )
    await callback.answer()


@router.callback_query(AdminFileCallback.filter(F.action == AdminFileAction.DELETE_VARIANT_SELECT))
async def delete_variant(callback: CallbackQuery, callback_data: AdminFileCallback, session: AsyncSession) -> None:
    variant = await FileVariantService(
        FileVariantRepository(session), build_storage_service(cast(Bot, callback.bot), None)
    ).delete_variant(callback_data.variant_id, DeepLinkRepository(session))
    if variant is None:
        await callback.answer("Variant not found", show_alert=True)
        return
    await _audit(session, callback.from_user, "Delete Variant", "Variant", variant.id, await _variant_details_from_obj(variant))
    if isinstance(callback.message, Message):
        if callback_data.episode_id:
            await _edit_episode_detail_message(callback.message, callback_data.episode_id, session)
        else:
            await _edit_file_detail_message(callback.message, variant.file_id, session)
    await callback.answer("Variant deleted")


@router.callback_query(AdminFileCallback.filter(F.action.in_({AdminFileAction.LIST_SERIES, AdminFileAction.SERIES_PAGE})))
async def list_series(callback: CallbackQuery, callback_data: AdminFileCallback, session: AsyncSession) -> None:
    rows, total = await SeriesService(
        SeriesRepository(session), EpisodeRepository(session), DeepLinkRepository(session)
    ).list_series(page=callback_data.page)
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            _series_list_text(rows, total, callback_data.page),
            reply_markup=series_list_keyboard(
                [(item.series.id, item.series.name) for item in rows], callback_data.page, callback_data.page * PAGE_SIZE < total
            ),
        )
    await callback.answer()


@router.callback_query(AdminFileCallback.filter(F.action == AdminFileAction.VIEW_SERIES))
async def view_series(callback: CallbackQuery, callback_data: AdminFileCallback, session: AsyncSession) -> None:
    await _send_series_detail(callback, callback_data.series_id, session)


@router.callback_query(AdminFileCallback.filter(F.action == AdminFileAction.EDIT_SERIES))
async def edit_series(callback: CallbackQuery, callback_data: AdminFileCallback, state: FSMContext, session: AsyncSession) -> None:
    series = await SeriesRepository(session).get_by_id(callback_data.series_id)
    if series is None:
        await callback.answer("Series not found", show_alert=True)
        return
    await state.update_data(series_id=series.id)
    await state.set_state(AdminFileStates.waiting_for_edit_series_name)
    if isinstance(callback.message, Message):
        await callback.message.edit_text(f"Current series name: <b>{escape(series.name)}</b>\n\nSend the new series name.")
    await callback.answer()


@router.message(AdminFileStates.waiting_for_edit_series_name, F.text)
async def save_series_name(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    series_id = int(data["series_id"])
    series = await SeriesService(SeriesRepository(session), EpisodeRepository(session), DeepLinkRepository(session)).update_series_name(
        series_id, _message_text(message).strip()
    )
    await _audit(session, message.from_user, "Edit Series", "Series", series_id, series.name if series else str(series_id))
    await state.clear()
    await message.answer("✅ Series renamed.")
    await _send_series_detail_message(message, series_id, session)


@router.callback_query(AdminFileCallback.filter(F.action == AdminFileAction.DELETE_SERIES))
async def delete_series(callback: CallbackQuery, callback_data: AdminFileCallback, session: AsyncSession) -> None:
    series = await SeriesRepository(session).get_by_id(callback_data.series_id)
    await SeriesService(SeriesRepository(session), EpisodeRepository(session), DeepLinkRepository(session)).soft_delete_series(
        callback_data.series_id
    )
    await _audit(session, callback.from_user, "Delete Series", "Series", callback_data.series_id, series.name if series else str(callback_data.series_id))
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            "🗑 Series deleted. Episodes and variants were disabled; download history was preserved.",
            reply_markup=file_management_keyboard(),
        )
    await callback.answer("Series deleted")


@router.callback_query(AdminFileCallback.filter(F.action == AdminFileAction.ADD_EPISODE))
async def add_episode(callback: CallbackQuery, callback_data: AdminFileCallback, state: FSMContext, settings: Settings) -> None:
    if not await _validate_archive(callback, settings):
        return
    await state.update_data(series_id=callback_data.series_id)
    await state.set_state(AdminFileStates.waiting_for_episode_number)
    if isinstance(callback.message, Message):
        await callback.message.edit_text("➕ <b>Add Episode</b>\n\nEnter episode number, for example: 5, 6.1, or 55.")
    await callback.answer()


@router.message(AdminFileStates.waiting_for_episode_number, F.text)
async def receive_episode_number(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    episode = await EpisodeService(EpisodeRepository(session), SeriesRepository(session), DeepLinkRepository(session)).create_episode(
        int(data["series_id"]), _message_text(message).strip()
    )
    if episode is None:
        await state.clear()
        await message.answer("Series not found.")
        return
    await _audit(session, message.from_user, "Create Episode", "Episode", episode.id, await _episode_details(session, episode.id))
    await state.update_data(file_id=episode.file_id, episode_id=episode.id)
    await state.set_state(AdminFileStates.waiting_for_variant_upload)
    await message.answer("Episode created. Now upload the document, video, or audio for this episode variant.")


@router.callback_query(AdminFileCallback.filter(F.action.in_({AdminFileAction.EPISODES, AdminFileAction.EPISODES_PAGE})))
async def episodes_list(callback: CallbackQuery, callback_data: AdminFileCallback, session: AsyncSession) -> None:
    episodes, total = await EpisodeService(EpisodeRepository(session), SeriesRepository(session), DeepLinkRepository(session)).list_episodes(
        callback_data.series_id, page=callback_data.page
    )
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            _episodes_list_text(episodes, total, callback_data.page),
            reply_markup=episodes_list_keyboard(callback_data.series_id, episodes, callback_data.page, callback_data.page * PAGE_SIZE < total),
        )
    await callback.answer()


@router.callback_query(AdminFileCallback.filter(F.action == AdminFileAction.VIEW_EPISODE))
async def view_episode(callback: CallbackQuery, callback_data: AdminFileCallback, session: AsyncSession) -> None:
    await _send_episode_detail(callback, callback_data.episode_id, session)


@router.callback_query(AdminFileCallback.filter(F.action == AdminFileAction.EDIT_EPISODE))
async def edit_episode(callback: CallbackQuery, callback_data: AdminFileCallback, state: FSMContext, session: AsyncSession) -> None:
    episode = await EpisodeRepository(session).get_by_id(callback_data.episode_id)
    if episode is None:
        await callback.answer("Episode not found", show_alert=True)
        return
    await state.update_data(episode_id=episode.id)
    await state.set_state(AdminFileStates.waiting_for_edit_episode_number)
    if isinstance(callback.message, Message):
        await callback.message.edit_text(f"Current episode number: <b>{escape(episode.number)}</b>\n\nSend the new episode number.")
    await callback.answer()


@router.message(AdminFileStates.waiting_for_edit_episode_number, F.text)
async def save_episode_number(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    episode = await EpisodeService(EpisodeRepository(session), SeriesRepository(session), DeepLinkRepository(session)).update_episode_number(
        int(data["episode_id"]), _message_text(message).strip()
    )
    await state.clear()
    if episode is None:
        await message.answer("Episode not found.")
        return
    await _audit(session, message.from_user, "Edit Episode", "Episode", episode.id, await _episode_details(session, episode.id))
    await message.answer("✅ Episode number updated.")
    await _send_episode_detail_message(message, episode.id, session)


@router.callback_query(AdminFileCallback.filter(F.action == AdminFileAction.DELETE_EPISODE))
async def delete_episode(callback: CallbackQuery, callback_data: AdminFileCallback, session: AsyncSession) -> None:
    details = await _episode_details(session, callback_data.episode_id)
    await EpisodeService(EpisodeRepository(session), SeriesRepository(session), DeepLinkRepository(session)).soft_delete_episode(
        callback_data.episode_id
    )
    await _audit(session, callback.from_user, "Delete Episode", "Episode", callback_data.episode_id, details)
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            "🗑 Episode deleted. Episode variants were disabled; download history was preserved.",
            reply_markup=series_detail_keyboard(callback_data.series_id),
        )
    await callback.answer("Episode deleted")


@router.callback_query(AdminFileCallback.filter(F.action == AdminFileAction.EPISODE_VARIANTS))
async def episode_variants(callback: CallbackQuery, callback_data: AdminFileCallback, session: AsyncSession) -> None:
    episode = await EpisodeRepository(session).get_by_id(callback_data.episode_id)
    if episode is None:
        await callback.answer("Episode not found", show_alert=True)
        return
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            _episode_detail_text(episode),
            reply_markup=variant_selection_keyboard(
                episode.file_id, episode.variants, AdminFileAction.EDIT_VARIANT, episode.series_id, episode.id
            ),
        )
    await callback.answer()


async def show_files(callback: CallbackQuery) -> None:
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            "📁 <b>File Management</b>\n\n"
            "Manage uploaded files, variants, and deep links.",
            reply_markup=file_management_keyboard(),
        )
    await callback.answer()


async def _send_file_list(callback: CallbackQuery, session: AsyncSession, page: int) -> None:
    rows, total = await FileService(FileRepository(session), DeepLinkRepository(session)).list_files(page=page)
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            _file_list_text(rows, total, page),
            reply_markup=file_list_keyboard(
                [(item.file.id, item.file.title) for item in rows], page, page * PAGE_SIZE < total
            ),
        )
    await callback.answer()


async def _send_file_detail(callback: CallbackQuery, file_id: int, session: AsyncSession) -> None:
    file = await FileRepository(session).get_by_id(file_id)
    if file is None or not file.is_active:
        await callback.answer("File not found", show_alert=True)
        return
    download_count = await _download_count(session, file.id)
    variants = "\n".join(
        "• "
        f"{escape(variant.quality)} | premium: {'yes' if variant.is_premium else 'no'} | "
        f"archive msg: {variant.archive_message_id or '-'} | storage: {variant.storage_type.value}"
        for variant in file.variants
        if variant.is_active
    ) or "No active variants."
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            f"📄 <b>{escape(file.title)}</b>\n\n"
            f"Download count: <b>{download_count}</b>\n"
            f"Description/caption: <blockquote>{escape(file.description or '—')}</blockquote>\n"
            f"Created: <b>{file.created_at:%Y-%m-%d}</b>\n\n"
            f"<b>Variants</b>\n{variants}",
            reply_markup=file_detail_keyboard(file.id),
        )
    await callback.answer()


async def _validate_archive(callback: CallbackQuery, settings: Settings) -> bool:
    if not settings.archive_chat_id:
        await callback.answer("ARCHIVE_CHAT_ID is not configured.", show_alert=True)
        return False
    if callback.bot is None:
        return False
    validation = await ArchiveChannelValidationService(callback.bot).validate(settings.archive_chat_id)
    if not validation.is_valid:
        await callback.answer("Archive channel is not ready.", show_alert=True)
        if isinstance(callback.message, Message):
            await callback.message.edit_text(
                "❌ <b>Archive channel validation failed</b>\n\n"
                + "\n".join(f"• {escape(error)}" for error in validation.errors),
                reply_markup=file_management_keyboard(),
            )
        return False
    return True


def _series_list_text(rows: list[SeriesListItem], total: int, page: int, search: str | None = None) -> str:
    total_pages = max(ceil(total / PAGE_SIZE), 1)
    header = "📺 <b>Series List</b>"
    if search:
        header += f" — search: <code>{escape(search)}</code>"
    lines = [header, f"Page {page}/{total_pages} • Total: {total}", ""]
    if not rows:
        lines.append("No series found.")
        return "\n".join(lines)
    for item in rows:
        lines.extend([
            f"<b>{escape(item.series.name)}</b>",
            f"Episodes: {item.episode_count} • Created: {item.series.created_at:%Y-%m-%d}",
            "",
        ])
    return "\n".join(lines)


def _search_text(movie_rows: list[FileListItem], series_result: tuple[list[SeriesListItem], int], page: int, search: str) -> str:
    series_rows, series_total = series_result
    lines = [f"🔍 <b>Search results</b> — <code>{escape(search)}</code>", ""]
    lines.append("<b>Movies</b>")
    if movie_rows:
        lines.extend(f"• {escape(item.file.title)} (Movie)" for item in movie_rows)
    else:
        lines.append("No matching movies.")
    lines.append("")
    lines.append("<b>Series</b>")
    if series_rows:
        lines.extend(f"• {escape(item.series.name)} (Series)" for item in series_rows)
    else:
        lines.append("No matching series.")
    lines.append("")
    lines.append(f"Showing page {page}. Series total: {series_total}")
    return "\n".join(lines)


def _episodes_list_text(episodes: list[Any], total: int, page: int) -> str:
    total_pages = max(ceil(total / PAGE_SIZE), 1)
    lines = ["📋 <b>Episodes List</b>", f"Page {page}/{total_pages} • Total: {total}", ""]
    if not episodes:
        lines.append("No episodes found.")
    else:
        lines.extend(f"Episode {escape(episode.number)}" for episode in episodes)
    return "\n".join(lines)


async def _send_series_detail(callback: CallbackQuery, series_id: int, session: AsyncSession) -> None:
    series = await SeriesRepository(session).get_by_id(series_id)
    if series is None or not series.is_active:
        await callback.answer("Series not found", show_alert=True)
        return
    if isinstance(callback.message, Message):
        await callback.message.edit_text(_series_detail_text(series), reply_markup=series_detail_keyboard(series.id))
    await callback.answer()


async def _send_series_detail_message(message: Message, series_id: int, session: AsyncSession) -> None:
    series = await SeriesRepository(session).get_by_id(series_id)
    if series is None:
        await message.answer("Series not found.")
        return
    await message.answer(_series_detail_text(series), reply_markup=series_detail_keyboard(series.id))


def _series_detail_text(series: Any) -> str:
    episode_count = len([episode for episode in series.episodes if episode.is_active])
    return (
        f"📺 <b>{escape(series.name)}</b>\n\n"
        f"Episode Count: <b>{episode_count}</b>\n"
        f"Created Date: <b>{series.created_at:%Y-%m-%d}</b>"
    )


async def _send_episode_detail(callback: CallbackQuery, episode_id: int, session: AsyncSession) -> None:
    episode = await EpisodeRepository(session).get_by_id(episode_id)
    if episode is None or not episode.is_active:
        await callback.answer("Episode not found", show_alert=True)
        return
    if isinstance(callback.message, Message):
        await callback.message.edit_text(_episode_detail_text(episode), reply_markup=episode_detail_keyboard(episode.series_id, episode.id, episode.file_id))
    await callback.answer()


async def _send_episode_detail_message(message: Message, episode_id: int, session: AsyncSession) -> None:
    episode = await EpisodeRepository(session).get_by_id(episode_id)
    if episode is None:
        await message.answer("Episode not found.")
        return
    await message.answer(_episode_detail_text(episode), reply_markup=episode_detail_keyboard(episode.series_id, episode.id, episode.file_id))


async def _edit_episode_detail_message(message: Message, episode_id: int, session: AsyncSession) -> None:
    episode = await EpisodeRepository(session).get_by_id(episode_id)
    if episode is None:
        await message.edit_text("Episode not found.")
        return
    await message.edit_text(_episode_detail_text(episode), reply_markup=episode_detail_keyboard(episode.series_id, episode.id, episode.file_id))


def _episode_detail_text(episode: Any) -> str:
    variant_count = len([variant for variant in episode.variants if variant.is_active])
    return (
        f"📺 <b>{escape(episode.series.name)}</b>\n\n"
        f"Episode Number: <b>{escape(episode.number)}</b>\n"
        f"Variant Count: <b>{variant_count}</b>"
    )


async def _download_count(session: AsyncSession, file_id: int) -> int:
    from sqlalchemy import func, select

    from models.download import Download

    return int(await session.scalar(select(func.count(Download.id)).where(Download.file_id == file_id)) or 0)


def _file_list_text(rows: list[FileListItem], total: int, page: int, search: str | None = None) -> str:
    total_pages = max(ceil(total / PAGE_SIZE), 1)
    header = "📋 <b>File List</b>"
    if search:
        header += f" — search: <code>{escape(search)}</code>"
    lines = [header, f"Page {page}/{total_pages} • Total: {total}", ""]
    if not rows:
        lines.append("No files found.")
        return "\n".join(lines)
    for item in rows:
        lines.extend(
            [
                f"<b>{escape(item.file.title)}</b>",
                f"Variants: {item.variant_count} • Downloads: {item.download_count} • Created: {item.file.created_at:%Y-%m-%d}",
                "",
            ]
        )
    return "\n".join(lines)


def _stored_from_state(data: dict[str, Any]) -> StoredFile:
    return StoredFile(
        storage_type=StorageType(cast(str, data["storage_type"])),
        storage_key=cast(str, data["storage_key"]),
        file_id=cast(str, data["file_id"]),
        file_unique_id=cast(str | None, data.get("file_unique_id")),
        archive_chat_id=int(data["archive_chat_id"]),
        archive_message_id=int(data["archive_message_id"]),
        media_type=cast(str, data.get("media_type", "document")),
        caption=cast(str | None, data.get("caption")),
        caption_entities=cast(list[dict[str, object]] | None, data.get("caption_entities")),
        filename=cast(str | None, data.get("filename")),
        file_size=cast(int | None, data.get("file_size")),
        mime_type=cast(str | None, data.get("mime_type")),
    )


def _stored_to_state(stored: StoredFile) -> dict[str, object]:
    return {
        "storage_type": stored.storage_type.value,
        "storage_key": stored.storage_key,
        "file_id": stored.file_id,
        "file_unique_id": stored.file_unique_id,
        "archive_chat_id": stored.archive_chat_id,
        "archive_message_id": stored.archive_message_id,
        "media_type": stored.media_type,
        "caption": stored.caption,
        "caption_entities": stored.caption_entities,
        "filename": stored.filename,
        "file_size": stored.file_size,
        "mime_type": stored.mime_type,
    }


def _message_text(message: Message) -> str:
    if message.text is None:
        raise ValueError("Expected text message")
    return message.text


async def _send_file_detail_message(message: Message, file_id: int, session: AsyncSession) -> None:
    file = await FileRepository(session).get_by_id(file_id)
    if file is None:
        await message.answer("File not found.")
        return
    download_count = await _download_count(session, file.id)
    await message.answer(
        _file_detail_text(file, download_count),
        reply_markup=file_detail_keyboard(file.id),
    )


async def _edit_file_detail_message(message: Message, file_id: int, session: AsyncSession) -> None:
    file = await FileRepository(session).get_by_id(file_id)
    if file is None:
        await message.edit_text("File not found.")
        return
    download_count = await _download_count(session, file.id)
    await message.edit_text(
        _file_detail_text(file, download_count),
        reply_markup=file_detail_keyboard(file.id),
    )


def _file_detail_text(file: Any, download_count: int) -> str:
    variants = "\n".join(
        "• "
        f"{escape(variant.quality)} | premium: {'yes' if variant.is_premium else 'no'} | "
        f"archive msg: {variant.archive_message_id or '-'} | storage: {variant.storage_type.value}"
        for variant in file.variants
        if variant.is_active
    ) or "No active variants."
    return (
        f"📄 <b>{escape(file.title)}</b>\n\n"
        f"Download count: <b>{download_count}</b>\n"
        f"Description/caption: <blockquote>{escape(file.description or '—')}</blockquote>\n"
        f"Created: <b>{file.created_at:%Y-%m-%d}</b>\n\n"
        f"<b>Variants</b>\n{variants}"
    )


def _premium_choice(data: str | None) -> bool:
    parts = (data or "").split(":")
    return len(parts) > 1 and parts[1] == "1"


def _entities_to_json(entities: list[MessageEntity] | None) -> list[dict[str, object]] | None:
    if not entities:
        return None
    return [entity.model_dump(mode="json", exclude_none=True) for entity in entities]


def _parse_key_value_lines(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in text.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key in {"storage_key", "telegram_file_id", "archive_chat_id", "archive_message_id"}:
            values[key] = value.strip()
    return values


def _optional_int(value: str | None) -> int | None:
    if value is None or value == "":
        return None
    return int(value)


async def _audit(session: AsyncSession, admin: Any, action: str, target_type: str, target_id: int | None, details: str | None) -> None:
    await AuditLogService(AuditLogRepository(session)).record(admin=admin, action=action, target_type=target_type, target_id=target_id, details=details)

async def _variant_details(session: AsyncSession, variant_id: int) -> str:
    variant = await FileVariantRepository(session).get_by_id(variant_id)
    return await _variant_details_from_obj(variant) if variant is not None else str(variant_id)

async def _variant_details_from_obj(variant: Any) -> str:
    title = getattr(getattr(variant, "file", None), "title", None) or f"File {getattr(variant, 'file_id', '')}"
    episode = getattr(variant, "episode", None)
    if episode is not None:
        series = getattr(episode, "series", None)
        title = f"{getattr(series, 'name', title)} Episode {getattr(episode, 'number', '')}"
    return f"{title}\n{getattr(variant, 'quality', '')}{' Premium' if getattr(variant, 'is_premium', False) else ''}"

async def _episode_details(session: AsyncSession, episode_id: int) -> str:
    episode = await EpisodeRepository(session).get_by_id(episode_id)
    if episode is None:
        return str(episode_id)
    series = getattr(episode, "series", None)
    return f"{getattr(series, 'name', 'Series')} Episode {episode.number}"
