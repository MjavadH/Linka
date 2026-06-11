from dataclasses import dataclass

from core.config import Settings
from repositories.settings import SettingsRepository

PREMIUM_SETTING_KEYS = [
    "premium_admin_username",
    "premium_card_holder_name",
    "premium_card_number",
    "premium_crypto_wallet_address",
    "premium_crypto_network",
    "premium_support_instructions",
]


@dataclass(frozen=True, slots=True)
class PremiumSettings:
    admin_username: str
    card_holder_name: str
    card_number: str
    crypto_wallet_address: str
    crypto_network: str
    support_instructions: str


class PremiumSettingsService:
    def __init__(self, repository: SettingsRepository, settings: Settings) -> None:
        self.repository = repository
        self.settings = settings

    async def get(self) -> PremiumSettings:
        values = await self.repository.get_many(PREMIUM_SETTING_KEYS)
        return PremiumSettings(
            admin_username=values.get("premium_admin_username") or self.settings.premium_admin_username,
            card_holder_name=values.get("premium_card_holder_name") or self.settings.premium_card_holder_name,
            card_number=values.get("premium_card_number") or self.settings.premium_card_number,
            crypto_wallet_address=values.get("premium_crypto_wallet_address") or self.settings.premium_crypto_wallet_address,
            crypto_network=values.get("premium_crypto_network") or self.settings.premium_crypto_network,
            support_instructions=values.get("premium_support_instructions") or self.settings.premium_support_instructions,
        )

    async def set_value(self, key: str, value: str | None) -> None:
        if key not in PREMIUM_SETTING_KEYS:
            raise ValueError("Unknown premium setting")
        await self.repository.set(key, value)
