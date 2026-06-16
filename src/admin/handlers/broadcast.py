import asyncio
from typing import Any

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from admin.callbacks import (
    AdminBroadcastAction,
    AdminBroadcastCallback,
    AdminMenuCallback,
    AdminNavAction,
    AdminNavigationCallback,
    AdminSection,
)
from admin.keyboards.broadcast import (
    broadcast_menu_keyboard,
    broadcast_preview_keyboard,
    history_keyboard,
    stop_broadcast_keyboard,
)
from admin.states import AdminBroadcastStates
from core.config import Settings
from core.timezone import format_datetime
from models.enums import BroadcastStatus, BroadcastTargetType
from repositories.broadcasts import BroadcastRepository
from repositories.audit_logs import AuditLogRepository
from services.audit_logs import AuditLogService
from services.broadcasts import (
    BroadcastPayload,
    broadcast_cancellations,
    format_cancelled_report,
    format_final_report,
    format_progress,
    start_broadcast_background,
    target_label,
)

router = Router(name="admin_broadcast")


@router.callback_query(AdminMenuCallback.filter(F.section == AdminSection.BROADCAST))
async def open_broadcast(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await show_broadcast(callback)


@router.callback_query(
    AdminNavigationCallback.filter(
        (F.target == AdminSection.BROADCAST)
        & (F.action.in_({AdminNavAction.BACK}))
    )
)
async def navigate_broadcast(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await show_broadcast(callback)


async def show_broadcast(callback: CallbackQuery) -> None:
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            "📢 <b>Broadcast</b>\n\n"
            "Choose the audience before composing your broadcast message.",
            reply_markup=broadcast_menu_keyboard(),
        )
    await callback.answer()


@router.callback_query(AdminBroadcastCallback.filter(F.action == AdminBroadcastAction.TARGET))
async def select_audience(
    callback: CallbackQuery,
    callback_data: AdminBroadcastCallback,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    target = BroadcastTargetType(callback_data.target)
    total = await BroadcastRepository(session).count_recipients(target)
    await state.set_state(AdminBroadcastStates.waiting_for_message)
    await state.update_data(target_type=target.value, total_recipients=total)
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            f"📢 <b>{target_label(target)}</b> Broadcast\n\n"
            "Send the message you want to broadcast. Any Telegram message type is supported and will be delivered with copyMessage().\n\n"
            f"Estimated users: <b>{total}</b>",
        )
    await callback.answer()


@router.message(AdminBroadcastStates.waiting_for_message)
async def receive_broadcast_message(message: Message, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    target = BroadcastTargetType(str(data["target_type"]))
    total = int(data["total_recipients"])
    await state.update_data(from_chat_id=message.chat.id, message_id=message.message_id)
    await state.set_state(AdminBroadcastStates.waiting_for_confirmation)

    await bot.copy_message(chat_id=message.chat.id, from_chat_id=message.chat.id, message_id=message.message_id)
    await message.answer(
        "📢 <b>Broadcast Preview</b>\n\n"
        f"Target Audience:\n<b>{target_label(target)}</b>\n\n"
        f"Total Estimated Users:\n<b>{total}</b>\n\n"
        "Confirm to start the background broadcast.",
        reply_markup=broadcast_preview_keyboard(),
    )


@router.callback_query(AdminBroadcastCallback.filter(F.action == AdminBroadcastAction.CANCEL))
async def cancel_preview(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    if isinstance(callback.message, Message):
        await callback.message.edit_text("❌ Broadcast creation cancelled.", reply_markup=broadcast_menu_keyboard())
    await callback.answer("Cancelled")


@router.callback_query(AdminBroadcastCallback.filter(F.action == AdminBroadcastAction.START), AdminBroadcastStates.waiting_for_confirmation)
async def start_broadcast(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    bot: Bot,
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    background_tasks: set[asyncio.Task[Any]] | None = None,
) -> None:
    data = await state.get_data()
    target = BroadcastTargetType(str(data["target_type"]))
    payload = BroadcastPayload.copy_message(from_chat_id=int(data["from_chat_id"]), message_id=int(data["message_id"]))
    repo = BroadcastRepository(session)
    total = await repo.count_recipients(target)
    admin_id = callback.from_user.id
    job = await repo.create_job(target_type=target, payload={"kind": payload.kind, **payload.data}, admin_telegram_id=admin_id, total_recipients=total)
    await session.flush()
    await AuditLogService(AuditLogRepository(session)).record(admin=callback.from_user, action="Broadcast Start", target_type="Broadcast", target_id=job.id, details=f"Target: {target_label(target)}; Recipients: {total}")

    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            format_progress(job),
            reply_markup=stop_broadcast_keyboard(job.id),
        )
        await repo.set_progress_message(job, chat_id=callback.message.chat.id, message_id=callback.message.message_id)
    await session.commit()
    await state.clear()

    task = start_broadcast_background(
        bot=bot,
        session_factory=session_factory,
        job_id=job.id,
        rate_limit_per_second=settings.broadcast_rate_limit_per_second,
        batch_size=settings.broadcast_batch_size,
    )
    if background_tasks is not None:
        background_tasks.add(task)
        task.add_done_callback(background_tasks.discard)
    await callback.answer("Broadcast started")


@router.callback_query(AdminBroadcastCallback.filter(F.action == AdminBroadcastAction.STOP))
async def stop_broadcast(callback: CallbackQuery, callback_data: AdminBroadcastCallback, session: AsyncSession) -> None:
    repo = BroadcastRepository(session)
    job = await repo.get(callback_data.job_id)
    if job is None:
        await callback.answer("Broadcast not found", show_alert=True)
        return
    broadcast_cancellations.cancel(job.id)
    await repo.request_cancel(job)
    await AuditLogService(AuditLogRepository(session)).record(admin=callback.from_user, action="Broadcast Cancel", target_type="Broadcast", target_id=job.id, details="Cancellation requested")
    await session.commit()
    if isinstance(callback.message, Message):
        await callback.message.edit_text(format_progress(job))
    await callback.answer("Broadcast cancellation requested")


@router.callback_query(AdminBroadcastCallback.filter(F.action == AdminBroadcastAction.HISTORY))
async def broadcast_history(callback: CallbackQuery, session: AsyncSession, settings: Settings) -> None:
    jobs = await BroadcastRepository(session).list_recent(10)
    if not jobs:
        text = "📜 <b>Broadcast History</b>\n\nNo broadcasts yet."
    else:
        lines = ["📜 <b>Broadcast History</b>", ""]
        for job in jobs:
            delivered = job.delivered_count or 0
            date = format_datetime(job.created_at, settings.timezone) if job.created_at else "—"
            lines.append(f"#{job.id} • {date} • {target_label(job.target_type)} • {job.status.value} • Delivered: {delivered}")
        text = "\n".join(lines)
    if isinstance(callback.message, Message):
        await callback.message.edit_text(text, reply_markup=history_keyboard([job.id for job in jobs]))
    await callback.answer()


@router.callback_query(AdminBroadcastCallback.filter(F.action == AdminBroadcastAction.VIEW))
async def view_broadcast(callback: CallbackQuery, callback_data: AdminBroadcastCallback, session: AsyncSession) -> None:
    job = await BroadcastRepository(session).get(callback_data.job_id)
    if job is None:
        await callback.answer("Broadcast not found", show_alert=True)
        return
    if job.status == BroadcastStatus.CANCELLED:
        text = format_cancelled_report(job)
    elif job.status == BroadcastStatus.RUNNING:
        text = format_progress(job)
    else:
        text = format_final_report(job)
    if isinstance(callback.message, Message):
        await callback.message.edit_text(text, reply_markup=history_keyboard([job.id]))
    await callback.answer()
