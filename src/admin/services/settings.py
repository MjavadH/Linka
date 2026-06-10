from dataclasses import dataclass

from core.config import Settings


@dataclass(frozen=True, slots=True)
class AdminSettingsView:
    delete_timeout_seconds: int
    premium_default_duration_days: int
    broadcast_batch_size: int
    archive_chat_id: int | None


class AdminSettingsService:
    """Provides admin-visible configuration values.

    The service isolates handlers from the current config source so database-backed
    settings can replace environment values later without changing UI handlers.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def get_settings(self) -> AdminSettingsView:
        return AdminSettingsView(
            delete_timeout_seconds=self.settings.file_delete_after_seconds,
            premium_default_duration_days=self.settings.premium_default_duration_days,
            broadcast_batch_size=self.settings.broadcast_batch_size,
            archive_chat_id=self.settings.archive_chat_id,
        )
