from core.config import Settings


def test_admin_ids_are_parsed_from_comma_separated_env() -> None:
    settings = Settings(
        bot_token="1234567890:test-token",
        bot_username="linka_bot",
        database_url="postgresql+asyncpg://user:pass@localhost/db",
        admin_telegram_ids="1, 2,3",
    )

    assert settings.admin_telegram_ids == (1, 2, 3)
    assert settings.bot_deep_link_base == "https://t.me/linka_bot?start="
