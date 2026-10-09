from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    database_url: str = "sqlite+aiosqlite:///./utilitybot.db"
    bot_token: str = ""
    discord_client_id: str = ""
    discord_client_secret: str = ""
    discord_redirect_uri: str = "http://localhost:8000/auth/discord/callback"
    session_secret: str = "development-only-change-me"
    dev_auth_enabled: bool = True
    dev_discord_user_id: str = "100000000000000001"
    dev_guild_id: str = "100000000000000001"
    allowed_origins: str = "http://localhost:8000"
    cookie_secure: bool = False
    session_ttl_seconds: int = 3600
    mc_server_address: str = ""
    mc_server_timeout_seconds: int = 5

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def origins(self) -> list[str]:
        return [item.strip() for item in self.allowed_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
