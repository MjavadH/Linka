from aiogram.types import User as TelegramUser

from models.audit_log import AuditLog
from repositories.audit_logs import AuditLogPage, AuditLogRepository

TRACKED_AUDIT_ACTIONS = (
    "Create Movie", "Edit Movie", "Delete Movie",
    "Create Series", "Edit Series", "Delete Series",
    "Create Episode", "Edit Episode", "Delete Episode",
    "Create Variant", "Edit Variant", "Delete Variant",
    "Create Sponsor", "Edit Sponsor", "Delete Sponsor",
    "Create Premium Plan", "Edit Premium Plan", "Delete Premium Plan",
    "Grant Premium", "Remove Premium",
    "Ban User", "Unban User",
    "Admin Message",
    "Broadcast Start", "Broadcast Cancel",
    "Settings Change",
)


class AuditLogService:
    def __init__(self, repository: AuditLogRepository) -> None:
        self.repository = repository

    async def record(self, *, admin: TelegramUser | None, action: str, target_type: str, target_id: int | None = None, details: str | None = None) -> AuditLog:
        if action not in TRACKED_AUDIT_ACTIONS:
            raise ValueError(f"Unsupported audit action: {action}")
        return await self.repository.create(
            admin_user_id=admin.id if admin else None,
            admin_username=admin.username if admin else None,
            admin_full_name=admin.full_name if admin else None,
            action=action,
            target_type=target_type,
            target_id=target_id,
            details=details,
        )

    async def list_logs(self, **kwargs: object) -> AuditLogPage:
        return await self.repository.list_page(**kwargs)

    async def get(self, log_id: int) -> AuditLog | None:
        return await self.repository.get(log_id)

    async def list_admins(self) -> list[tuple[int, str]]:
        return await self.repository.list_admins()
