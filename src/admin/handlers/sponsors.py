import re
from datetime import UTC, datetime, time
from typing import Any, cast

from aiogram import F, Router
from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Chat, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from admin.callbacks import (
    AdminMenuCallback,
    AdminNavAction,
    AdminNavigationCallback,
    AdminSection,
    AdminSponsorAction,
    AdminSponsorCallback,
)
from admin.keyboards.navigation import navigation_row
from admin.states.sponsors import AdminSponsorStates
from repositories.sponsors import SponsorRepository
from repositories.audit_logs import AuditLogRepository
from services.audit_logs import AuditLogService

router = Router(name="admin_sponsors")
INVITE_LINK_RE = re.compile(r"^https://(?:t\.me|telegram\.me)/(?:\+[A-Za-z0-9_-]+|joinchat/[A-Za-z0-9_-]+|[A-Za-z0-9_]{5,})(?:/)?$")


@router.callback_query(AdminMenuCallback.filter(F.section == AdminSection.SPONSORS))
async def open_sponsors(callback: CallbackQuery, session: AsyncSession) -> None:
    await show_sponsors(callback, session)


@router.callback_query(
    AdminNavigationCallback.filter(
        (F.target == AdminSection.SPONSORS)
        & (F.action.in_({AdminNavAction.BACK, AdminNavAction.REFRESH}))
    )
)
async def navigate_sponsors(callback: CallbackQuery, session: AsyncSession) -> None:
    await show_sponsors(callback, session)


@router.callback_query(AdminSponsorCallback.filter(F.action == AdminSponsorAction.ADD))
async def add_sponsor(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(AdminSponsorStates.waiting_for_forwarded_message)
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            "Forward any message from the sponsor channel or group.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[navigation_row(back_to=AdminSection.SPONSORS, include_home=True)]
            ),
        )
    await callback.answer()


@router.message(AdminSponsorStates.waiting_for_forwarded_message)
async def receive_sponsor_forwarded_message(message: Message, state: FSMContext) -> None:
    if message.bot is None:
        return
    chat = _extract_forwarded_chat(message)
    if chat is None:
        await message.answer(
            "Please forward a message from the sponsor channel/group. "
            "Copied text or hidden forwards cannot be used."
        )
        return

    access_error = await _validate_bot_access(message, chat.id)
    if access_error is not None:
        await message.answer(access_error)
        return

    await state.update_data(
        chat_id=chat.id,
        title=chat.title or str(chat.id),
        channel_username=chat.username,
        chat_type=str(chat.type),
        mode="add",
    )
    await state.set_state(AdminSponsorStates.waiting_for_invite_url)
    await message.answer("Send the invite link users should use to join this sponsor channel/group.")


@router.message(AdminSponsorStates.waiting_for_invite_url)
async def receive_sponsor_invite_url(message: Message, state: FSMContext) -> None:
    invite_url = (message.text or "").strip()
    if not _valid_invite_link(invite_url):
        await message.answer(
            "Invalid invite link. Send a valid https://t.me/... invite or public username link."
        )
        return
    await state.update_data(invite_url=invite_url)
    await state.set_state(None)
    await message.answer(
        "Choose sponsor expiration:",
        reply_markup=_expiration_keyboard(),
    )


@router.callback_query(AdminSponsorCallback.filter(F.action == AdminSponsorAction.VIEW))
async def view_sponsor(
    callback: CallbackQuery, callback_data: AdminSponsorCallback, session: AsyncSession
) -> None:
    await show_sponsor_details(callback, session, callback_data.sponsor_id)


@router.callback_query(AdminSponsorCallback.filter(F.action == AdminSponsorAction.EDIT))
async def edit_sponsor(
    callback: CallbackQuery, callback_data: AdminSponsorCallback, session: AsyncSession
) -> None:
    sponsor = await SponsorRepository(session).get(callback_data.sponsor_id)
    if sponsor is None:
        await callback.answer("Sponsor not found", show_alert=True)
        return
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            f"✏️ <b>Edit {sponsor.title}</b>\n\nChoose a field to update.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="🔗 Invite Link",
                            callback_data=AdminSponsorCallback(
                                action=AdminSponsorAction.EDIT_INVITE, sponsor_id=sponsor.id
                            ).pack(),
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text="⏳ Expiration",
                            callback_data=AdminSponsorCallback(
                                action=AdminSponsorAction.EDIT_EXPIRATION, sponsor_id=sponsor.id
                            ).pack(),
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text="⬅️ Details",
                            callback_data=AdminSponsorCallback(
                                action=AdminSponsorAction.VIEW, sponsor_id=sponsor.id
                            ).pack(),
                        )
                    ],
                ]
            ),
        )
    await callback.answer()


@router.callback_query(AdminSponsorCallback.filter(F.action == AdminSponsorAction.EDIT_INVITE))
async def edit_sponsor_invite(
    callback: CallbackQuery, callback_data: AdminSponsorCallback, state: FSMContext
) -> None:
    await state.clear()
    await state.update_data(sponsor_id=callback_data.sponsor_id)
    await state.set_state(AdminSponsorStates.waiting_for_edit_invite_url)
    if isinstance(callback.message, Message):
        await callback.message.edit_text("Send the new invite link for this sponsor.")
    await callback.answer()


@router.message(AdminSponsorStates.waiting_for_edit_invite_url)
async def receive_edit_invite_url(message: Message, state: FSMContext, session: AsyncSession) -> None:
    invite_url = (message.text or "").strip()
    if not _valid_invite_link(invite_url):
        await message.answer("Invalid invite link. Send a valid https://t.me/... link.")
        return
    data = await state.get_data()
    sponsor = await SponsorRepository(session).get(int(data["sponsor_id"]))
    if sponsor is None:
        await message.answer("Sponsor not found.")
        await state.clear()
        return
    await SponsorRepository(session).update_invite_url(sponsor, invite_url)
    await AuditLogService(AuditLogRepository(session)).record(admin=message.from_user, action="Edit Sponsor", target_type="Sponsor", target_id=sponsor.id, details=sponsor.title)
    await state.clear()
    await message.answer("✅ Invite link updated.")


@router.callback_query(AdminSponsorCallback.filter(F.action == AdminSponsorAction.EDIT_EXPIRATION))
async def edit_sponsor_expiration(
    callback: CallbackQuery, callback_data: AdminSponsorCallback, state: FSMContext
) -> None:
    await state.clear()
    await state.update_data(mode="edit", sponsor_id=callback_data.sponsor_id)
    if isinstance(callback.message, Message):
        await callback.message.edit_text("Choose new expiration:", reply_markup=_expiration_keyboard(callback_data.sponsor_id))
    await callback.answer()


@router.callback_query(AdminSponsorCallback.filter(F.action == AdminSponsorAction.EXPIRE_NONE))
async def set_no_expiration(
    callback: CallbackQuery,
    callback_data: AdminSponsorCallback,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    await _save_expiration(callback, callback_data, state, session, "none", None)


@router.callback_query(AdminSponsorCallback.filter(F.action == AdminSponsorAction.EXPIRE_DATE))
async def start_date_expiration(
    callback: CallbackQuery, callback_data: AdminSponsorCallback, state: FSMContext
) -> None:
    await _prepare_expiration_state(callback_data, state)
    await state.set_state(
        AdminSponsorStates.waiting_for_edit_expiration_date
        if callback_data.sponsor_id
        else AdminSponsorStates.waiting_for_expiration_date
    )
    if isinstance(callback.message, Message):
        await callback.message.edit_text("Enter date:\n\nFormat: YYYY/MM/DD\nExample: 2026/12/31")
    await callback.answer()


@router.message(AdminSponsorStates.waiting_for_expiration_date)
@router.message(AdminSponsorStates.waiting_for_edit_expiration_date)
async def receive_expiration_date(message: Message, state: FSMContext) -> None:
    try:
        datetime.strptime(message.text or "", "%Y/%m/%d")
    except ValueError:
        await message.answer("Invalid date. Use YYYY/MM/DD, for example 2026/12/31.")
        return
    await state.update_data(expiration_date=message.text)
    current_state = await state.get_state()
    await state.set_state(
        AdminSponsorStates.waiting_for_edit_expiration_time
        if current_state == AdminSponsorStates.waiting_for_edit_expiration_date.state
        else AdminSponsorStates.waiting_for_expiration_time
    )
    await message.answer("Enter time:\n\nFormat: HH:MM\n24-hour format.\nExample: 22:45")


@router.message(AdminSponsorStates.waiting_for_expiration_time)
@router.message(AdminSponsorStates.waiting_for_edit_expiration_time)
async def receive_expiration_time(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    try:
        parsed_time = time.fromisoformat(message.text or "")
        expires_at = datetime.combine(
            datetime.strptime(str(data["expiration_date"]), "%Y/%m/%d").date(), parsed_time, tzinfo=UTC
        )
    except ValueError:
        await message.answer("Invalid time. Use HH:MM in 24-hour format, for example 22:45.")
        return
    if expires_at <= datetime.now(UTC):
        await message.answer("Expiration must be in the future. Enter a future date/time.")
        return
    await _persist_sponsor_from_state(message, state, session, "date", expires_at.isoformat())


@router.callback_query(AdminSponsorCallback.filter(F.action == AdminSponsorAction.EXPIRE_MEMBERS))
async def start_member_expiration(
    callback: CallbackQuery, callback_data: AdminSponsorCallback, state: FSMContext
) -> None:
    await _prepare_expiration_state(callback_data, state)
    await state.set_state(
        AdminSponsorStates.waiting_for_edit_join_count
        if callback_data.sponsor_id
        else AdminSponsorStates.waiting_for_join_count
    )
    if isinstance(callback.message, Message):
        await callback.message.edit_text("Enter target join count.\n\nExample: 500")
    await callback.answer()


@router.message(AdminSponsorStates.waiting_for_join_count)
@router.message(AdminSponsorStates.waiting_for_edit_join_count)
async def receive_join_count(message: Message, state: FSMContext, session: AsyncSession) -> None:
    try:
        target = int(message.text or "")
    except ValueError:
        await message.answer("Join count must be a positive integer, for example 500.")
        return
    if target <= 0:
        await message.answer("Join count must be greater than zero.")
        return
    await _persist_sponsor_from_state(message, state, session, "members", str(target))


@router.callback_query(AdminSponsorCallback.filter(F.action.in_({AdminSponsorAction.ACTIVATE, AdminSponsorAction.DEACTIVATE})))
async def toggle_sponsor(
    callback: CallbackQuery,
    callback_data: AdminSponsorCallback,
    session: AsyncSession,
) -> None:
    repository = SponsorRepository(session)
    sponsor = await repository.get(callback_data.sponsor_id)
    if sponsor is None:
        await callback.answer("Sponsor not found", show_alert=True)
        return
    sponsor.is_active = callback_data.action == AdminSponsorAction.ACTIVATE
    await session.flush()
    await AuditLogService(AuditLogRepository(session)).record(admin=callback.from_user, action="Edit Sponsor", target_type="Sponsor", target_id=sponsor.id, details=f"{sponsor.title} {'activated' if sponsor.is_active else 'deactivated'}")
    await show_sponsor_details(callback, session, sponsor.id)


@router.callback_query(AdminSponsorCallback.filter(F.action == AdminSponsorAction.DELETE))
async def delete_sponsor(
    callback: CallbackQuery,
    callback_data: AdminSponsorCallback,
    session: AsyncSession,
) -> None:
    sponsor = await SponsorRepository(session).get(callback_data.sponsor_id)
    if sponsor is None:
        await callback.answer("Sponsor not found", show_alert=True)
        return
    details = sponsor.title
    await session.delete(sponsor)
    await session.flush()
    await AuditLogService(AuditLogRepository(session)).record(admin=callback.from_user, action="Delete Sponsor", target_type="Sponsor", target_id=callback_data.sponsor_id, details=details)
    await show_sponsors(callback, session)


async def show_sponsors(callback: CallbackQuery, session: AsyncSession) -> None:
    sponsors = await SponsorRepository(session).list_all()
    body = "No sponsors configured yet." if not sponsors else "Select a sponsor to view details."
    keyboard_rows = [
        [
            InlineKeyboardButton(
                text="➕ Add sponsor",
                callback_data=AdminSponsorCallback(action=AdminSponsorAction.ADD).pack(),
            )
        ]
    ]
    for sponsor in sponsors:
        keyboard_rows.append(
            [
                InlineKeyboardButton(
                    text=f"{'✅' if sponsor.is_active else '⛔'} {sponsor.title}",
                    callback_data=AdminSponsorCallback(
                        action=AdminSponsorAction.VIEW, sponsor_id=sponsor.id
                    ).pack(),
                )
            ]
        )
    keyboard_rows.append(navigation_row(refresh=AdminSection.SPONSORS))

    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            "📢 <b>Sponsors</b>\n\n"
            "Add sponsors by forwarding a message from the target channel/group.\n\n"
            f"{body}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_rows),
        )
    await callback.answer()


async def show_sponsor_details(callback: CallbackQuery, session: AsyncSession, sponsor_id: int) -> None:
    sponsor = await SponsorRepository(session).get(sponsor_id)
    if sponsor is None:
        await callback.answer("Sponsor not found", show_alert=True)
        return
    status = "Active" if sponsor.is_active else "Inactive"
    expiration_value = sponsor.expiration_value or "—"
    if sponsor.expiration_type == "date" and sponsor.expiration_value:
        expiration_value = sponsor.expiration_value
    text = (
        f"📢 <b>{sponsor.title}</b>\n\n"
        f"<b>Chat ID:</b> <code>{sponsor.chat_id}</code>\n"
        f"<b>Type:</b> {sponsor.chat_type or '—'}\n"
        f"<b>Invite Link:</b> {sponsor.invite_url}\n"
        f"<b>Status:</b> {status}\n"
        f"<b>Expiration Type:</b> {sponsor.expiration_type}\n"
        f"<b>Expiration Value:</b> {expiration_value}\n"
        f"<b>Current Join Count:</b> {sponsor.sponsor_join_count}\n"
        f"<b>Created At:</b> {sponsor.created_at}\n"
    )
    action = AdminSponsorAction.DEACTIVATE if sponsor.is_active else AdminSponsorAction.ACTIVATE
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✏️ Edit",
                    callback_data=AdminSponsorCallback(action=AdminSponsorAction.EDIT, sponsor_id=sponsor.id).pack(),
                )
            ],
            [
                InlineKeyboardButton(
                    text="⏸ Disable" if sponsor.is_active else "▶️ Enable",
                    callback_data=AdminSponsorCallback(action=action, sponsor_id=sponsor.id).pack(),
                ),
                InlineKeyboardButton(
                    text="🗑 Delete",
                    callback_data=AdminSponsorCallback(action=AdminSponsorAction.DELETE, sponsor_id=sponsor.id).pack(),
                ),
            ],
            [InlineKeyboardButton(text="⬅️ Sponsors", callback_data=AdminMenuCallback(section=AdminSection.SPONSORS).pack())],
        ]
    )
    if isinstance(callback.message, Message):
        await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


def _extract_forwarded_chat(message: Message) -> Chat | None:
    origin = message.forward_origin
    chat = getattr(origin, "chat", None) or getattr(origin, "sender_chat", None)
    if chat is not None:
        return cast(Chat, chat)
    return message.forward_from_chat


async def _validate_bot_access(message: Message, chat_id: int) -> str | None:
    if message.bot is None:
        return "❌ Unable to verify bot access right now."
    try:
        bot_user = await message.bot.get_me()
        member = await message.bot.get_chat_member(chat_id, bot_user.id)
    except TelegramAPIError:
        return "❌ The bot is not a member of this channel/group."
    if member.status in {ChatMemberStatus.LEFT, ChatMemberStatus.KICKED}:
        return "❌ The bot is not a member of this channel/group."
    if member.status not in {ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR}:
        return "❌ The bot must be an administrator of this sponsor channel/group."
    return None


def _valid_invite_link(value: str) -> bool:
    return INVITE_LINK_RE.fullmatch(value) is not None


def _expiration_keyboard(sponsor_id: int = 0) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📅 Expire By Date",
                    callback_data=AdminSponsorCallback(
                        action=AdminSponsorAction.EXPIRE_DATE, sponsor_id=sponsor_id
                    ).pack(),
                )
            ],
            [
                InlineKeyboardButton(
                    text="👥 Expire By Join Count",
                    callback_data=AdminSponsorCallback(
                        action=AdminSponsorAction.EXPIRE_MEMBERS, sponsor_id=sponsor_id
                    ).pack(),
                )
            ],
            [
                InlineKeyboardButton(
                    text="♾ No Expiration",
                    callback_data=AdminSponsorCallback(
                        action=AdminSponsorAction.EXPIRE_NONE, sponsor_id=sponsor_id
                    ).pack(),
                )
            ],
        ]
    )


async def _prepare_expiration_state(callback_data: AdminSponsorCallback, state: FSMContext) -> None:
    data = await state.get_data()
    if callback_data.sponsor_id and data.get("sponsor_id") != callback_data.sponsor_id:
        await state.clear()
        await state.update_data(mode="edit", sponsor_id=callback_data.sponsor_id)


async def _save_expiration(
    callback: CallbackQuery,
    callback_data: AdminSponsorCallback,
    state: FSMContext,
    session: AsyncSession,
    expiration_type: str,
    expiration_value: str | None,
) -> None:
    data = await state.get_data()
    if callback_data.sponsor_id:
        await state.update_data(mode="edit", sponsor_id=callback_data.sponsor_id)
    elif not data:
        await callback.answer("Start by adding or editing a sponsor first.", show_alert=True)
        return
    if isinstance(callback.message, Message):
        await _persist_sponsor_from_state(callback.message, state, session, expiration_type, expiration_value)
    await callback.answer()


async def _persist_sponsor_from_state(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    expiration_type: str,
    expiration_value: str | None,
) -> None:
    data: dict[str, Any] = await state.get_data()
    repository = SponsorRepository(session)
    if data.get("mode") == "edit":
        sponsor = await repository.get(int(data["sponsor_id"]))
        if sponsor is None:
            await message.answer("Sponsor not found.")
        else:
            await repository.update_expiration(sponsor, expiration_type, expiration_value)
            await AuditLogService(AuditLogRepository(session)).record(admin=message.from_user, action="Edit Sponsor", target_type="Sponsor", target_id=sponsor.id, details=sponsor.title)
            await message.answer("✅ Sponsor expiration updated.")
        await state.clear()
        return

    sponsor = await repository.create(
        chat_id=int(data["chat_id"]),
        title=str(data["title"]),
        invite_url=str(data["invite_url"]),
        channel_username=data.get("channel_username"),
        chat_type=data.get("chat_type"),
        expiration_type=expiration_type,
        expiration_value=expiration_value,
    )
    await AuditLogService(AuditLogRepository(session)).record(admin=message.from_user, action="Create Sponsor", target_type="Sponsor", target_id=sponsor.id, details=sponsor.title)
    await state.clear()
    await message.answer("✅ Sponsor added. It is active immediately and required for non-premium users.")
