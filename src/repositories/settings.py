from datetime import UTC, datetime

from sqlalchemy import select

from models.setting import AppSetting
from repositories.base import BaseRepository


class SettingsRepository(BaseRepository[AppSetting]):
    async def get(self, key: str) -> str | None:
        setting = await self.session.get(AppSetting, key)
        return setting.value if setting else None

    async def set(self, key: str, value: str | None) -> AppSetting:
        setting = await self.session.get(AppSetting, key)
        if setting is None:
            setting = AppSetting(key=key, value=value)
            self.session.add(setting)
        else:
            setting.value = value
            setting.updated_at = datetime.now(UTC)
        await self.session.flush()
        return setting

    async def get_many(self, keys: list[str]) -> dict[str, str | None]:
        result = await self.session.execute(select(AppSetting).where(AppSetting.key.in_(keys)))
        return {setting.key: setting.value for setting in result.scalars()}
