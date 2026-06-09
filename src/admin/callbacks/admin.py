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
