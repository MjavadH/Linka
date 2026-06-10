from enum import StrEnum

from aiogram.filters.callback_data import CallbackData


class AdminSection(StrEnum):
    DASHBOARD = "dashboard"
    FILES = "files"
    SPONSORS = "sponsors"
    PREMIUM = "premium"
    BROADCAST = "broadcast"
    STATISTICS = "statistics"
    SETTINGS = "settings"


class AdminAction(StrEnum):
    OPEN = "open"


class AdminNavAction(StrEnum):
    HOME = "home"
    BACK = "back"
    REFRESH = "refresh"


class AdminMenuCallback(CallbackData, prefix="admin"):
    section: AdminSection


class AdminNavigationCallback(CallbackData, prefix="admin_nav"):
    action: AdminNavAction
    target: AdminSection


class AdminFileAction(StrEnum):
    ADD = "add"
    LIST = "list"
    SEARCH = "search"
    VIEW = "view"
    ADD_VARIANT = "add_variant"
    DELETE = "delete"
    LINKS = "links"
    PAGE = "page"


class AdminFileCallback(CallbackData, prefix="admin_file"):
    action: AdminFileAction
    file_id: int = 0
    page: int = 1
