from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from admin.handlers.analytics import _broadcasts_text
from admin.handlers.system import _logs_text
from admin.handlers.users import _ban_status, _premium_status
from core.config import Settings
from core.timezone import format_datetime, to_local_datetime
from models.audit_log import AuditLog
from models.subscription import Subscription
from models.user_ban import UserBan
from repositories.analytics import BroadcastStatisticsRow
from repositories.audit_logs import AuditLogPage


def _settings(**overrides: object) -> Settings:
    values = {
        "bot_token": "1234567890:test-token",
        "bot_username": "linka_bot",
        "database_url": "postgresql+asyncpg://user:pass@localhost/db",
        "admin_telegram_ids": "1",
        "archive_chat_id": -1001234567890,
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


def test_valid_timezone_loading() -> None:
    assert _settings(timezone="Asia/Tehran").timezone == "Asia/Tehran"


def test_invalid_timezone_startup_failure() -> None:
    with pytest.raises(ValidationError, match="Invalid TIMEZONE value: ABCDEF"):
        _settings(timezone="ABCDEF")


def test_utc_to_local_conversion() -> None:
    value = datetime(2026, 6, 15, 14, 30, tzinfo=UTC)
    assert to_local_datetime(value, "Asia/Tehran") == datetime(2026, 6, 15, 18, 0, tzinfo=to_local_datetime(value, "Asia/Tehran").tzinfo)
    assert format_datetime(value, "Asia/Tehran") == "2026-06-15 18:00"


def test_audit_log_formatting_uses_configured_timezone() -> None:
    log = AuditLog(id=1452, action="Grant Premium", admin_full_name="Admin", created_at=datetime(2026, 6, 15, 14, 30, tzinfo=UTC))
    page = AuditLogPage(items=(log,), total=1, page=1, per_page=8)
    assert "#1452 - [2026-06-15 18:00] - Grant Premium - Admin" in _logs_text(page, "Asia/Tehran")


def test_premium_expiration_formatting_uses_configured_timezone() -> None:
    subscription = Subscription(expires_at=datetime(2026, 6, 15, 14, 30, tzinfo=UTC), is_active=True)
    assert "Expires: 2026-06-15 18:00" in _premium_status(subscription, "Asia/Tehran")


def test_ban_expiration_formatting_uses_configured_timezone() -> None:
    ban = UserBan(is_active=True, is_permanent=False, banned_until=datetime(2026, 6, 15, 14, 30, tzinfo=UTC), reason="test")
    assert "Until: 2026-06-15 18:00" in _ban_status(ban, "Asia/Tehran")


def test_analytics_timestamp_formatting_uses_configured_timezone() -> None:
    report = BroadcastStatisticsRow(1, 1, 0, datetime(2026, 6, 15, 14, 30, tzinfo=UTC), 1, 1)
    assert "Last Broadcast Date: <b>2026-06-15 18:00</b>" in _broadcasts_text(report, "Asia/Tehran")
