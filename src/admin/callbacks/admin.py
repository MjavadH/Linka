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
    EDIT = "edit"
    EDIT_TITLE = "edit_title"
    EDIT_CAPTION = "edit_caption"
    EDIT_VARIANT = "edit_variant"
    EDIT_VARIANT_QUALITY = "edit_variant_quality"
    EDIT_VARIANT_PREMIUM = "edit_variant_premium"
    EDIT_VARIANT_CAPTION = "edit_variant_caption"
    EDIT_VARIANT_STORAGE = "edit_variant_storage"
    DELETE_FILE = "delete_file"
    DELETE_VARIANT = "delete_variant"
    DELETE_VARIANT_SELECT = "delete_variant_select"
    LINKS = "links"
    PAGE = "page"


class AdminFileCallback(CallbackData, prefix="admin_file"):
    action: AdminFileAction
    file_id: int = 0
    variant_id: int = 0
    page: int = 1


class AdminSponsorAction(StrEnum):
    ADD = "add"
    VIEW = "view"
    EDIT = "edit"
    EDIT_INVITE = "edit_invite"
    EDIT_EXPIRATION = "edit_expiration"
    DEACTIVATE = "deactivate"
    ACTIVATE = "activate"
    DELETE = "delete"
    EXPIRE_DATE = "expire_date"
    EXPIRE_MEMBERS = "expire_members"
    EXPIRE_NONE = "expire_none"


class AdminSponsorCallback(CallbackData, prefix="admin_sponsor"):
    action: AdminSponsorAction
    sponsor_id: int = 0
