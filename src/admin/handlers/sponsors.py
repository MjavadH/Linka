from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
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

router = Router(name="admin_sponsors")


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
    await state.set_state(AdminSponsorStates.waiting_for_chat_id)
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            "Send the sponsor channel chat_id. The bot must already be an admin/member of the channel.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[navigation_row(back_to=AdminSection.SPONSORS, include_home=True)]
            ),
        )
    await callback.answer()


@router.message(AdminSponsorStates.waiting_for_chat_id)
async def receive_sponsor_chat_id(message: Message, state: FSMContext) -> None:
    try:
        chat_id = int(message.text or "")
    except ValueError:
        await message.answer("chat_id must be an integer. Try again.")
        return
    await state.update_data(chat_id=chat_id)
    await state.set_state(AdminSponsorStates.waiting_for_invite_url)
    await message.answer("Send the invite link users should use to join this sponsor channel.")


@router.message(AdminSponsorStates.waiting_for_invite_url)
async def receive_sponsor_invite_url(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if message.bot is None:
        return
    invite_url = (message.text or "").strip()
    if not invite_url.startswith("https://t.me/"):
        await message.answer("Invite link must start with https://t.me/. Try again.")
        return
    data = await state.get_data()
    chat_id = int(data["chat_id"])
    chat = await message.bot.get_chat(chat_id)
    await SponsorRepository(session).create(
        chat_id=chat_id,
        title=chat.title or str(chat_id),
        invite_url=invite_url,
        channel_username=chat.username,
    )
    await state.clear()
    await message.answer("✅ Sponsor added. It is active immediately and required for non-premium users.")


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
    await show_sponsors(callback, session)


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
    await session.delete(sponsor)
    await session.flush()
    await show_sponsors(callback, session)


async def show_sponsors(callback: CallbackQuery, session: AsyncSession) -> None:
    sponsors = await SponsorRepository(session).list_all()
    if sponsors:
        rows = [
            (
                f"{'✅' if sponsor.is_active else '⛔'} <b>{sponsor.title}</b>\n"
                f"chat_id: <code>{sponsor.chat_id}</code>\n"
                f"username: {sponsor.channel_username or '—'}\n"
                f"expiration: {sponsor.expiration_type} {sponsor.expiration_value or ''}".rstrip()
            )
            for sponsor in sponsors
        ]
        body = "\n\n".join(rows)
    else:
        body = "No sponsors configured yet."

    keyboard_rows = [
        [
            InlineKeyboardButton(
                text="➕ Add sponsor",
                callback_data=AdminSponsorCallback(action=AdminSponsorAction.ADD).pack(),
            )
        ]
    ]
    for sponsor in sponsors:
        action = AdminSponsorAction.DEACTIVATE if sponsor.is_active else AdminSponsorAction.ACTIVATE
        keyboard_rows.append(
            [
                InlineKeyboardButton(
                    text=("⛔ Deactivate " if sponsor.is_active else "✅ Activate ") + sponsor.title,
                    callback_data=AdminSponsorCallback(action=action, sponsor_id=sponsor.id).pack(),
                ),
                InlineKeyboardButton(
                    text="🗑 Delete",
                    callback_data=AdminSponsorCallback(
                        action=AdminSponsorAction.DELETE, sponsor_id=sponsor.id
                    ).pack(),
                ),
            ]
        )
    keyboard_rows.append(navigation_row(refresh=AdminSection.SPONSORS))

    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            "📢 <b>Sponsors</b>\n\n"
            "Add, delete, and activate/deactivate sponsor channels. Expiration fields are persisted and "
            "enforced by the sponsor service.\n\n"
            f"{body}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_rows),
        )
    await callback.answer()
