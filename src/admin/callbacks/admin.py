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
    USERS = "users"


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
    ADD_MOVIE = "add_movie"
    ADD_SERIES = "add_series"
    LIST = "list"
    LIST_MOVIES = "list_movies"
    LIST_SERIES = "list_series"
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
    SERIES_PAGE = "series_page"
    VIEW_SERIES = "view_series"
    EDIT_SERIES = "edit_series"
    DELETE_SERIES = "delete_series"
    ADD_EPISODE = "add_episode"
    EPISODES = "episodes"
    EPISODES_PAGE = "episodes_page"
    VIEW_EPISODE = "view_episode"
    EDIT_EPISODE = "edit_episode"
    DELETE_EPISODE = "delete_episode"
    EPISODE_VARIANTS = "episode_variants"


class AdminFileCallback(CallbackData, prefix="admin_file"):
    action: AdminFileAction
    file_id: int = 0
    variant_id: int = 0
    series_id: int = 0
    episode_id: int = 0
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


class AdminPremiumAction(StrEnum):
    PLANS = "plans"
    PLAN_ADD = "plan_add"
    PLAN_VIEW = "plan_view"
    PLAN_EDIT = "plan_edit"
    PLAN_TOGGLE = "plan_toggle"
    PLAN_DELETE = "plan_delete"
    GRANT = "grant"
    GRANT_PLAN = "grant_plan"
    STATS = "stats"
    SETTINGS = "settings"
    SETTING_EDIT = "setting_edit"


class AdminPremiumCallback(CallbackData, prefix="admin_prem"):
    action: AdminPremiumAction
    plan_id: int = 0
    key: str = ""


class AdminBroadcastAction(StrEnum):
    TARGET = "target"
    START = "start"
    CANCEL = "cancel"
    STOP = "stop"
    HISTORY = "history"
    VIEW = "view"


class AdminBroadcastCallback(CallbackData, prefix="admin_bc"):
    action: AdminBroadcastAction
    target: str = ""
    job_id: int = 0


class AdminUserAction(StrEnum):
    SEARCH = "search"
    VIEW = "view"
    GRANT_PREMIUM = "grant_premium"
    GRANT_PLAN = "grant_plan"
    CUSTOM_PREMIUM = "custom_premium"
    REMOVE_PREMIUM = "remove_premium"
    BAN = "ban"
    BAN_PERMANENT = "ban_permanent"
    BAN_TEMPORARY = "ban_temporary"
    UNBAN = "unban"
    MESSAGE = "message"


class AdminUserCallback(CallbackData, prefix="admin_user"):
    action: AdminUserAction
    user_id: int = 0
    plan_id: int = 0
