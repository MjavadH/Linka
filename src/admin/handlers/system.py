from datetime import UTC, datetime

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from admin.callbacks import AdminMenuCallback, AdminSection, AdminSystemAction, AdminSystemCallback
from admin.keyboards.navigation import home_button
from admin.states.system import AdminSystemStates
from core.config import Settings
from models.file import DeepLink
from models.subscription import Subscription
from repositories.audit_logs import AuditLogRepository
from services.audit_logs import TRACKED_AUDIT_ACTIONS, AuditLogService
from services.system import HealthService

router = Router(name="admin_system")

@router.callback_query(AdminMenuCallback.filter(F.section == AdminSection.SYSTEM))
async def open_system(callback: CallbackQuery) -> None:
    await _edit(callback, "🛠 <b>System</b>", _system_keyboard())

@router.callback_query(AdminSystemCallback.filter(F.action == AdminSystemAction.MENU))
async def system_menu(callback: CallbackQuery) -> None:
    await open_system(callback)

@router.callback_query(AdminSystemCallback.filter(F.action == AdminSystemAction.AUDIT_LOGS))
async def audit_logs(callback: CallbackQuery, session: AsyncSession, callback_data: AdminSystemCallback) -> None:
    await _show_logs(callback, session, page=callback_data.page)

@router.callback_query(AdminSystemCallback.filter(F.action == AdminSystemAction.AUDIT_VIEW))
async def audit_detail(callback: CallbackQuery, session: AsyncSession, callback_data: AdminSystemCallback) -> None:
    log = await AuditLogService(AuditLogRepository(session)).get(callback_data.log_id)
    if log is None:
        await callback.answer("Audit log not found", show_alert=True); return
    text = ("📜 <b>Audit Log Details</b>\n\n" f"ID:\n#{log.id}\n\nDate:\n{log.created_at:%Y-%m-%d %H:%M}\n\n" f"Admin:\n{log.admin_full_name or 'Unknown'}\n\nUsername:\n@{log.admin_username or '-'}\n\n" f"Admin ID:\n{log.admin_user_id or '-'}\n\nAction:\n{log.action}\n\n" f"Target:\n{log.target_type} {log.target_id or '-'}\n\nDetails:\n{log.details or '-'}")
    await _edit(callback, text, InlineKeyboardMarkup(inline_keyboard=[[_btn("⬅️ Back To Logs", AdminSystemAction.AUDIT_LOGS)], [home_button()]]))

@router.callback_query(AdminSystemCallback.filter(F.action == AdminSystemAction.AUDIT_SEARCH))
async def audit_search(callback: CallbackQuery) -> None:
    rows = [[_btn("📅 Date", AdminSystemAction.AUDIT_SEARCH_DATE)], [_btn("🆔 Log ID", AdminSystemAction.AUDIT_SEARCH_LOG_ID)], [_btn("👤 Admin", AdminSystemAction.AUDIT_SEARCH_ADMIN)], [home_button(), _btn("⬅️ Back To Logs", AdminSystemAction.AUDIT_LOGS)]]
    await _edit(callback, "🔍 <b>Audit Log Search</b>\n\nChoose a search method.", InlineKeyboardMarkup(inline_keyboard=rows))

@router.callback_query(AdminSystemCallback.filter(F.action == AdminSystemAction.AUDIT_SEARCH_DATE))
async def audit_search_date(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminSystemStates.waiting_for_search_date)
    await _edit(callback, "📅 <b>Search by Date</b>\n\nSend date in YYYY/MM/DD format.\nExample: 2026/06/13", InlineKeyboardMarkup(inline_keyboard=[[home_button(), _btn("⬅️ Back To Logs", AdminSystemAction.AUDIT_LOGS)]]))

@router.message(AdminSystemStates.waiting_for_search_date, F.text)
async def receive_search_date(message: Message, state: FSMContext, session: AsyncSession) -> None:
    try:
        day = datetime.strptime(message.text or "", "%Y/%m/%d").replace(tzinfo=UTC)
    except ValueError:
        await message.answer("Invalid date. Use YYYY/MM/DD, for example 2026/06/13."); return
    await state.clear()
    data = await AuditLogService(AuditLogRepository(session)).list_logs(page=1, per_page=8, day=day)
    await message.answer(_logs_text(data), reply_markup=_logs_keyboard(data, day=day))

@router.callback_query(AdminSystemCallback.filter(F.action == AdminSystemAction.AUDIT_SEARCH_DATE_RESULTS))
async def audit_search_date_results(callback: CallbackQuery, session: AsyncSession, callback_data: AdminSystemCallback) -> None:
    try:
        day = datetime.strptime(callback_data.value, "%Y/%m/%d").replace(tzinfo=UTC)
    except ValueError:
        await callback.answer("Invalid saved date", show_alert=True); return
    await _show_logs(callback, session, page=callback_data.page, day=day)

@router.callback_query(AdminSystemCallback.filter(F.action == AdminSystemAction.AUDIT_SEARCH_LOG_ID))
async def audit_search_log_id(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminSystemStates.waiting_for_search_log_id)
    await _edit(callback, "🆔 <b>Search by Log ID</b>\n\nSend log id.\nExample: 1452", InlineKeyboardMarkup(inline_keyboard=[[home_button(), _btn("⬅️ Back To Logs", AdminSystemAction.AUDIT_LOGS)]]))

@router.message(AdminSystemStates.waiting_for_search_log_id, F.text)
async def receive_search_log_id(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not (message.text or "").strip().isdigit():
        await message.answer("Log ID must be numeric."); return
    await state.clear()
    log = await AuditLogService(AuditLogRepository(session)).get(int((message.text or "").strip()))
    if log is None:
        await message.answer("Audit log not found."); return
    await message.answer(("📜 <b>Audit Log Details</b>\n\n" f"ID:\n#{log.id}\n\nDate:\n{log.created_at:%Y-%m-%d %H:%M}\n\n" f"Admin:\n{log.admin_full_name or 'Unknown'}\n\nAction:\n{log.action}\n\nTarget:\n{log.target_type} {log.target_id or '-'}\n\nDetails:\n{log.details or '-'}"), reply_markup=InlineKeyboardMarkup(inline_keyboard=[[_btn("⬅️ Back To Logs", AdminSystemAction.AUDIT_LOGS)], [home_button()]]))

@router.callback_query(AdminSystemCallback.filter(F.action == AdminSystemAction.AUDIT_SEARCH_ADMIN))
async def audit_search_admin(callback: CallbackQuery, session: AsyncSession) -> None:
    admins = await AuditLogService(AuditLogRepository(session)).list_admins()
    rows = [[InlineKeyboardButton(text=name, callback_data=AdminSystemCallback(action=AdminSystemAction.AUDIT_FILTER_ADMIN, admin_id=admin_id).pack())] for admin_id, name in admins]
    rows.append([home_button(), _btn("⬅️ Back To Logs", AdminSystemAction.AUDIT_LOGS)])
    await _edit(callback, "👤 <b>Select Admin</b>", InlineKeyboardMarkup(inline_keyboard=rows))

@router.callback_query(AdminSystemCallback.filter(F.action == AdminSystemAction.AUDIT_FILTER))
async def audit_filter(callback: CallbackQuery) -> None:
    rows = [[_btn("👤 By Admin", AdminSystemAction.AUDIT_FILTER_ADMIN_MENU)], [_btn("⚡ By Action", AdminSystemAction.AUDIT_FILTER_ACTION_MENU)], [_btn("❌ Clear Filter", AdminSystemAction.AUDIT_CLEAR_FILTER)], [home_button(), _btn("⬅️ Back To Logs", AdminSystemAction.AUDIT_LOGS)]]
    await _edit(callback, "🎯 <b>Filter</b>", InlineKeyboardMarkup(inline_keyboard=rows))

@router.callback_query(AdminSystemCallback.filter(F.action == AdminSystemAction.AUDIT_FILTER_ADMIN_MENU))
async def audit_filter_admin_menu(callback: CallbackQuery, session: AsyncSession) -> None:
    admins = await AuditLogService(AuditLogRepository(session)).list_admins()
    rows = [[InlineKeyboardButton(text=name, callback_data=AdminSystemCallback(action=AdminSystemAction.AUDIT_FILTER_ADMIN, admin_id=admin_id).pack())] for admin_id, name in admins]
    rows.append([home_button(), _btn("⬅️ Back To Logs", AdminSystemAction.AUDIT_LOGS)])
    await _edit(callback, "👤 <b>Filter By Admin</b>", InlineKeyboardMarkup(inline_keyboard=rows))

@router.callback_query(AdminSystemCallback.filter(F.action == AdminSystemAction.AUDIT_FILTER_ACTION_MENU))
async def audit_filter_action_menu(callback: CallbackQuery) -> None:
    buttons = [
        InlineKeyboardButton(
            text=action,
            callback_data=AdminSystemCallback(
                action=AdminSystemAction.AUDIT_FILTER_ACTION,
                value=action,
            ).pack(),
        )
        for action in TRACKED_AUDIT_ACTIONS
    ]

    rows = [
        buttons[i:i + 2]
        for i in range(0, len(buttons), 2)
    ]
    rows.append([home_button(), _btn("⬅️ Back To Logs", AdminSystemAction.AUDIT_LOGS)])
    await _edit(callback, "⚡ <b>Filter By Action</b>", InlineKeyboardMarkup(inline_keyboard=rows))

@router.callback_query(AdminSystemCallback.filter(F.action == AdminSystemAction.AUDIT_CLEAR_FILTER))
async def audit_clear_filter(callback: CallbackQuery, session: AsyncSession) -> None:
    await _show_logs(callback, session)

@router.callback_query(AdminSystemCallback.filter(F.action == AdminSystemAction.AUDIT_FILTER_ACTION))
async def audit_filter_action(callback: CallbackQuery, session: AsyncSession, callback_data: AdminSystemCallback) -> None:
    await _show_logs(callback, session, page=callback_data.page, action=callback_data.value)

@router.callback_query(AdminSystemCallback.filter(F.action == AdminSystemAction.AUDIT_FILTER_ADMIN))
async def audit_filter_admin(callback: CallbackQuery, session: AsyncSession, callback_data: AdminSystemCallback) -> None:
    await _show_logs(callback, session, page=callback_data.page, admin_user_id=callback_data.admin_id)

@router.callback_query(AdminSystemCallback.filter(F.action == AdminSystemAction.HEALTH))
async def health(callback: CallbackQuery, session: AsyncSession, settings: Settings, bot: Bot, scheduler: object | None = None) -> None:
    report = await HealthService(bot=bot, settings=settings, session=session, scheduler=scheduler).check()
    text = ("❤️ <b>Health Status</b>\n\n" + "\n".join([f"{s.name}: {'✅' if s.healthy else '❌'} {s.detail}" for s in [report.database, report.scheduler, report.archive_channel, report.broadcast_worker, report.bot_api]]) + f"\n\nLast Health Check Time: <b>{report.checked_at:%Y-%m-%d %H:%M:%S}</b>")
    await _edit(callback, text, InlineKeyboardMarkup(inline_keyboard=[[_btn("🔄 Run Health Check", AdminSystemAction.HEALTH)], [home_button()]]))

@router.callback_query(AdminSystemCallback.filter(F.action == AdminSystemAction.MAINTENANCE))
async def maintenance(callback: CallbackQuery) -> None:
    rows = [[_btn("🔄 Run Health Check", AdminSystemAction.HEALTH)], [_btn("📊 Recalculate Statistics", AdminSystemAction.RECALC_STATS)], [_btn("🔗 Validate Deep Links", AdminSystemAction.VALIDATE_LINKS)], [_btn("🧹 Cleanup Expired Records", AdminSystemAction.CLEANUP_EXPIRED)], [home_button()]]
    await _edit(callback, "🔄 <b>Maintenance</b>", InlineKeyboardMarkup(inline_keyboard=rows))

@router.callback_query(AdminSystemCallback.filter(F.action.in_({AdminSystemAction.RECALC_STATS, AdminSystemAction.VALIDATE_LINKS, AdminSystemAction.CLEANUP_EXPIRED})))
async def maintenance_action(callback: CallbackQuery, session: AsyncSession, callback_data: AdminSystemCallback) -> None:
    await callback.answer("Running...")
    if callback_data.action == AdminSystemAction.VALIDATE_LINKS:
        total = int(await session.scalar(select(func.count(DeepLink.id))) or 0); result = f"Validated {total} deep links."
    elif callback_data.action == AdminSystemAction.CLEANUP_EXPIRED:
        res = await session.execute(delete(Subscription).where(Subscription.is_active.is_(True), Subscription.expires_at <= datetime.now(UTC)).returning(Subscription.id)); result = f"Cleaned {len(res.all())} expired subscriptions."
    else:
        result = "Statistics recalculated successfully."
    await session.commit()
    await _edit(callback, f"✅ <b>Maintenance Complete</b>\n\n{result}", InlineKeyboardMarkup(inline_keyboard=[[_btn("⬅️ Back", AdminSystemAction.MAINTENANCE), home_button()]]))

async def _show_logs(callback: CallbackQuery, session: AsyncSession, *, page: int = 1, admin_user_id: int | None = None, action: str | None = None, day: datetime | None = None) -> None:
    data = await AuditLogService(AuditLogRepository(session)).list_logs(page=page, per_page=8, admin_user_id=admin_user_id, action=action, day=day)
    await _edit(callback, _logs_text(data), _logs_keyboard(data, admin_user_id=admin_user_id, action=action, day=day))

def _logs_text(data) -> str:
    if not data.items:
        return "📜 <b>Latest Audit Logs</b>\n\nNo logs found."

    lines = ["📜 <b>Latest Audit Logs</b>", ""]

    for log in data.items:
        admin = log.admin_full_name or log.admin_username or "Unknown"

        lines.append(
            f"#{log.id} - "
            f"[{log.created_at:%Y-%m-%d %H:%M}] - "
            f"{log.action} - "
            f"{admin}"
        )

    return "\n".join(lines)
    
def _logs_keyboard(data, *, admin_user_id: int | None = None, action: str | None = None, day: datetime | None = None) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=f"#{l.id}", callback_data=AdminSystemCallback(action=AdminSystemAction.AUDIT_VIEW, log_id=l.id).pack()) for l in data.items[i:i+4]] for i in range(0, len(data.items), 4)]
    start = 0 if data.total == 0 else (data.page - 1) * data.per_page + 1; end = min(data.total, data.page * data.per_page)
    rows.append([InlineKeyboardButton(text=f"Showing {start}-{end} of {data.total} logs", callback_data=AdminSystemCallback(action=AdminSystemAction.AUDIT_NOOP).pack())])
    nav=[]
    cb_action = AdminSystemAction.AUDIT_SEARCH_DATE_RESULTS if day else AdminSystemAction.AUDIT_FILTER_ACTION if action else AdminSystemAction.AUDIT_FILTER_ADMIN if admin_user_id else AdminSystemAction.AUDIT_LOGS
    value = day.strftime("%Y/%m/%d") if day else action or ""
    if data.page > 1:
        nav.append(InlineKeyboardButton(text="⬅️ Previous", callback_data=AdminSystemCallback(action=cb_action, page=data.page-1, admin_id=admin_user_id or 0, value=value).pack()))
    nav.append(InlineKeyboardButton(text=f"Page {data.page} / {data.pages}", callback_data=AdminSystemCallback(action=AdminSystemAction.AUDIT_NOOP).pack()))
    if data.page < data.pages:
        nav.append(InlineKeyboardButton(text="➡️ Next", callback_data=AdminSystemCallback(action=cb_action, page=data.page+1, admin_id=admin_user_id or 0, value=value).pack()))
    rows.append(nav)
    rows += [[_btn("🔍 Search", AdminSystemAction.AUDIT_SEARCH), _btn("🎯 Filter", AdminSystemAction.AUDIT_FILTER)], [home_button()]]
    return InlineKeyboardMarkup(inline_keyboard=rows)

@router.callback_query(AdminSystemCallback.filter(F.action == AdminSystemAction.AUDIT_NOOP))
async def audit_noop(callback: CallbackQuery) -> None:
    await callback.answer()

def _system_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[_btn("📜 Audit Logs", AdminSystemAction.AUDIT_LOGS), _btn("❤️ Health Status", AdminSystemAction.HEALTH)], [_btn("🔄 Maintenance", AdminSystemAction.MAINTENANCE)], [home_button()]])

def _btn(text: str, action: AdminSystemAction) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=AdminSystemCallback(action=action).pack())

async def _edit(callback: CallbackQuery, text: str, reply_markup: InlineKeyboardMarkup) -> None:
    if isinstance(callback.message, Message): await callback.message.edit_text(text, reply_markup=reply_markup)
    await callback.answer()
