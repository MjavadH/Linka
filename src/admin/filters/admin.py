from collections.abc import Iterable

from aiogram.filters import BaseFilter
from aiogram.types import CallbackQuery, Message, TelegramObject, User


class AdminFilter(BaseFilter):
    """Allow updates only from configured Telegram admin IDs."""

    def __init__(self, admin_ids: Iterable[int]) -> None:
        self.admin_ids = frozenset(admin_ids)

    async def __call__(self, event: TelegramObject, event_from_user: User | None = None) -> bool:
        user = event_from_user or self._extract_user(event)
        return user is not None and user.id in self.admin_ids

    @staticmethod
    def _extract_user(event: TelegramObject) -> User | None:
        if isinstance(event, Message):
            return event.from_user
        if isinstance(event, CallbackQuery):
            return event.from_user
        from_user = getattr(event, "from_user", None)
        return from_user if isinstance(from_user, User) else None
