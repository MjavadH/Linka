from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DEFAULT_DATETIME_FORMAT = "%Y-%m-%d %H:%M"
DEFAULT_DATE_FORMAT = "%Y-%m-%d"


def get_zoneinfo(timezone: str) -> ZoneInfo:
    try:
        return ZoneInfo(timezone)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"Invalid TIMEZONE value: {timezone}") from exc


def validate_timezone(timezone: str) -> None:
    get_zoneinfo(timezone)


def to_local_datetime(dt: datetime | None, timezone: str) -> datetime | None:
    if dt is None:
        return None
    source = dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)
    return source.astimezone(get_zoneinfo(timezone))


def format_datetime(dt: datetime | None, timezone: str, fmt: str = DEFAULT_DATETIME_FORMAT, none: str = "—") -> str:
    local = to_local_datetime(dt, timezone)
    if local is None:
        return none
    return local.strftime(fmt)


def format_date(value: datetime | date | None, timezone: str, fmt: str = DEFAULT_DATE_FORMAT, none: str = "—") -> str:
    if value is None:
        return none
    if isinstance(value, datetime):
        local = to_local_datetime(value, timezone)
        return none if local is None else local.strftime(fmt)
    return value.strftime(fmt)
