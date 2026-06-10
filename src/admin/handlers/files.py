from __future__ import annotations

from html import escape
from math import ceil
from typing import Any, cast

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
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
    file_detail_keyboard,
    file_list_keyboard,
    file_management_keyboard,
    premium_choice_keyboard,
)
from admin.states.files import AdminFileStates
from core.config import Settings
from models.enums import StorageType
from repositories.files import PAGE_SIZE, DeepLinkRepository, FileRepository, FileVariantRepository
from services.files import DeepLinkService, FileListItem, FileService, FileVariantService
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
        (F.target == AdminSection.FILES) & (F.action.in_({AdminNavAction.BACK, AdminNavAction.REFRESH}))
    )
)
async def navigate_files(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await show_files(callback)


@router.callback_query(AdminFileCallback.filter(F.action == AdminFileAction.ADD))
async def add_file(callback: CallbackQuery, state: FSMContext, settings: Settings) -> None:
    if not settings.archive_chat_id:
        await callback.answer("ARCHIVE_CHAT_ID is not configured.", show_alert=True)
        return
    if callback.bot is None:
        return
    validation = await ArchiveChannelValidationService(callback.bot).validate(settings.archive_chat_id)
    if not validation.is_valid:
        await callback.answer("Archive channel is not ready.", show_alert=True)
        if isinstance(callback.message, Message):
            await callback.message.edit_text(
                "❌ <b>Archive channel validation failed</b>\n\n"
                + "\n".join(f"• {escape(error)}" for error in validation.errors),
                reply_markup=file_management_keyboard(),
            )
        return
    await state.set_state(AdminFileStates.waiting_for_upload)
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            "📁 <b>Add File</b>\n\nSend a Telegram document, video, or audio file.",
            reply_markup=file_management_keyboard(),
        )
    await callback.answer()


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
    is_premium = callback.data == "file_premium:1"
    file_service = FileService(FileRepository(session), DeepLinkRepository(session))
    variant_service = FileVariantService(
        FileVariantRepository(session), build_storage_service(callback.bot, settings.archive_chat_id)
    )
    link_service = DeepLinkService(DeepLinkRepository(session), settings.bot_username)
    file = await file_service.create_file(title=cast(str, data["title"]))
    variant = await variant_service.create_variant_from_stored(
        file_id=file.id,
        quality=cast(str, data["quality"]),
        is_premium=is_premium,
        stored=stored,
    )
    link = await link_service.get_or_create_for_variant(variant)
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


@router.callback_query(AdminFileCallback.filter(F.action.in_({AdminFileAction.LIST, AdminFileAction.PAGE})))
async def list_files(
    callback: CallbackQuery, callback_data: AdminFileCallback, session: AsyncSession
) -> None:
    await _send_file_list(callback, session, page=callback_data.page)


@router.callback_query(AdminFileCallback.filter(F.action == AdminFileAction.SEARCH))
async def search_files(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminFileStates.waiting_for_search)
    if isinstance(callback.message, Message):
        await callback.message.edit_text("🔍 Send a title or filename search query.")
    await callback.answer()


@router.message(AdminFileStates.waiting_for_search, F.text)
async def receive_search(message: Message, state: FSMContext, session: AsyncSession) -> None:
    await state.clear()
    rows, total = await FileService(FileRepository(session), DeepLinkRepository(session)).list_files(
        page=1, search=_message_text(message).strip()
    )
    await message.answer(
        _file_list_text(rows, total, 1, search=_message_text(message).strip()),
        reply_markup=file_list_keyboard([(item.file.id, item.file.title) for item in rows], 1, total > PAGE_SIZE),
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
        await callback.message.edit_text("\n".join(lines), reply_markup=file_detail_keyboard(file.id))
    await callback.answer()


@router.callback_query(AdminFileCallback.filter(F.action == AdminFileAction.DELETE))
async def delete_file(
    callback: CallbackQuery, callback_data: AdminFileCallback, session: AsyncSession
) -> None:
    await FileService(FileRepository(session), DeepLinkRepository(session)).soft_delete_file(callback_data.file_id)
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            "🗑 File deleted. Download history and statistics were preserved; deep links are disabled.",
            reply_markup=file_management_keyboard(),
        )
    await callback.answer("File deleted")


@router.callback_query(AdminFileCallback.filter(F.action == AdminFileAction.ADD_VARIANT))
async def add_variant(callback: CallbackQuery, callback_data: AdminFileCallback, state: FSMContext) -> None:
    await state.update_data(file_id=callback_data.file_id)
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
        is_premium=callback.data == "file_premium:1",
        stored=_stored_from_state(data["stored_file"]),
    )
    link = await DeepLinkService(DeepLinkRepository(session), settings.bot_username).get_or_create_for_variant(
        variant
    )
    await state.clear()
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            "✅ Variant added.\n\n"
            f"Deep link:\n<code>{escape(DeepLinkService(DeepLinkRepository(session), settings.bot_username).build_link(link.token))}</code>",
            reply_markup=file_detail_keyboard(variant.file_id),
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
            f"Created: <b>{file.created_at:%Y-%m-%d}</b>\n\n"
            f"<b>Variants</b>\n{variants}",
            reply_markup=file_detail_keyboard(file.id),
        )
    await callback.answer()


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
        "filename": stored.filename,
        "file_size": stored.file_size,
        "mime_type": stored.mime_type,
    }


def _message_text(message: Message) -> str:
    if message.text is None:
        raise ValueError("Expected text message")
    return message.text
