from datetime import UTC, datetime

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from admin.callbacks import AdminMenuCallback, AdminSection, AdminSystemAction, AdminSystemCallback
from admin.keyboards.navigation import home_button
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
    text = (
        "📜 <b>Audit Log Details</b>\n\n"
        f"ID:\n#{log.id}\n\nDate:\n{log.created_at:%Y-%m-%d %H:%M}\n\n"
        f"Admin:\n{log.admin_full_name or 'Unknown'}\n\nUsername:\n@{log.admin_username or '-'}\n\n"
        f"Admin ID:\n{log.admin_user_id or '-'}\n\nAction:\n{log.action}\n\n"
        f"Target:\n{log.target_type} {log.target_id or '-'}\n\nDetails:\n{log.details or '-'}"
    )
    await _edit(callback, text, InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="⬅️ Back To Logs", callback_data=AdminSystemCallback(action=AdminSystemAction.AUDIT_LOGS).pack()), home_button()]]))

@router.callback_query(AdminSystemCallback.filter(F.action == AdminSystemAction.AUDIT_SEARCH))
async def audit_search(callback: CallbackQuery) -> None:
    await _edit(callback, "🔍 <b>Audit Log Search</b>\n\nSend a date as YYYY/MM/DD, a log ID, or an admin name in the next version UI.", InlineKeyboardMarkup(inline_keyboard=[[_btn("📅 Date", AdminSystemAction.AUDIT_LOGS)], [_btn("🆔 Log ID", AdminSystemAction.AUDIT_LOGS)], [_btn("👤 Admin", AdminSystemAction.AUDIT_LOGS)], [home_button()]]))

@router.callback_query(AdminSystemCallback.filter(F.action == AdminSystemAction.AUDIT_FILTER))
async def audit_filter(callback: CallbackQuery, session: AsyncSession) -> None:
    admins = await AuditLogService(AuditLogRepository(session)).list_admins()
    rows = [[InlineKeyboardButton(text="👤 By Admin", callback_data=AdminSystemCallback(action=AdminSystemAction.AUDIT_FILTER_ADMIN, admin_id=admin_id).pack())] for admin_id, _ in admins[:5]]
    rows += [[InlineKeyboardButton(text=a, callback_data=AdminSystemCallback(action=AdminSystemAction.AUDIT_FILTER_ACTION, value=a).pack())] for a in TRACKED_AUDIT_ACTIONS]
    rows.append([_btn("❌ Clear Filter", AdminSystemAction.AUDIT_LOGS), home_button()])
    await _edit(callback, "🎯 <b>Audit Log Filters</b>", InlineKeyboardMarkup(inline_keyboard=rows))

@router.callback_query(AdminSystemCallback.filter(F.action == AdminSystemAction.AUDIT_FILTER_ACTION))
async def audit_filter_action(callback: CallbackQuery, session: AsyncSession, callback_data: AdminSystemCallback) -> None:
    await _show_logs(callback, session, action=callback_data.value)

@router.callback_query(AdminSystemCallback.filter(F.action == AdminSystemAction.AUDIT_FILTER_ADMIN))
async def audit_filter_admin(callback: CallbackQuery, session: AsyncSession, callback_data: AdminSystemCallback) -> None:
    await _show_logs(callback, session, admin_user_id=callback_data.admin_id)

@router.callback_query(AdminSystemCallback.filter(F.action == AdminSystemAction.HEALTH))
async def health(callback: CallbackQuery, session: AsyncSession, settings: Settings, bot: Bot) -> None:
    report = await HealthService(bot=bot, settings=settings, session=session).check()
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

async def _show_logs(callback: CallbackQuery, session: AsyncSession, *, page: int = 1, admin_user_id: int | None = None, action: str | None = None) -> None:
    data = await AuditLogService(AuditLogRepository(session)).list_logs(page=page, per_page=8, admin_user_id=admin_user_id, action=action)
    start = 0 if data.total == 0 else (data.page - 1) * data.per_page + 1; end = min(data.total, data.page * data.per_page)
    text = "📜 <b>Latest Audit Logs</b>\n\n" + "\n".join(f"#{l.id} - [{l.created_at:%Y-%m-%d %H:%M}] - {l.action} - {l.admin_username or l.admin_full_name or 'system'}" for l in data.items)
    text += f"\n\nShowing {start}-{end} of {data.total} logs"
    rows = [[InlineKeyboardButton(text=f"#{l.id}", callback_data=AdminSystemCallback(action=AdminSystemAction.AUDIT_VIEW, log_id=l.id).pack()) for l in data.items[i:i+4]] for i in range(0, len(data.items), 4)]
    nav=[]
    if page > 1: nav.append(InlineKeyboardButton(text="⬅️ Previous", callback_data=AdminSystemCallback(action=AdminSystemAction.AUDIT_LOGS, page=page-1).pack()))
    nav.append(InlineKeyboardButton(text=f"Page {page} / {data.pages}", callback_data=AdminSystemCallback(action=AdminSystemAction.AUDIT_LOGS, page=page).pack()))
    if page < data.pages: nav.append(InlineKeyboardButton(text="➡️ Next", callback_data=AdminSystemCallback(action=AdminSystemAction.AUDIT_LOGS, page=page+1).pack()))
    rows += [nav, [_btn("🔍 Search", AdminSystemAction.AUDIT_SEARCH), _btn("🎯 Filter", AdminSystemAction.AUDIT_FILTER)], [home_button()]]
    await _edit(callback, text, InlineKeyboardMarkup(inline_keyboard=rows))

def _system_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[_btn("📜 Audit Logs", AdminSystemAction.AUDIT_LOGS), _btn("❤️ Health Status", AdminSystemAction.HEALTH)], [_btn("🔄 Maintenance", AdminSystemAction.MAINTENANCE), _btn("⚙️ System Settings", AdminSystemAction.SETTINGS)], [home_button()]])

def _btn(text: str, action: AdminSystemAction) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=AdminSystemCallback(action=action).pack())

async def _edit(callback: CallbackQuery, text: str, reply_markup: InlineKeyboardMarkup) -> None:
    if isinstance(callback.message, Message): await callback.message.edit_text(text, reply_markup=reply_markup)
    await callback.answer()
