from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file="../.env", extra="ignore")
    environment: str = "development"
    database_url: str = "sqlite:///./mama.db"
    redis_url: str = "redis://localhost:6379/0"
    app_url: str = "http://localhost:3000"
    encryption_key: str
    bot_internal_secret: str
    telegram_bot_token: str = ""
    telegram_bot_username: str = "beremen_ai_bot"
    telegram_webhook_secret: str = ""
    google_client_id: str = ""
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = ""
    vision_model: str = ""
    embedding_model: str = ""
    embedding_dimensions: int = 1536
    storage_dir: Path = Path("./storage")
    storage_backend: str = "local"
    s3_endpoint: str = ""
    s3_bucket: str = ""
    s3_access_key: str = ""
    s3_secret_key: str = ""
    yookassa_shop_id: str = ""
    yookassa_secret: str = ""
    admin_google_subjects: str = ""
    max_upload_mb: int = 15
    privacy_version: str = "2026-09-18-draft"

    @property
    def production(self):
        return self.environment == "production"


@lru_cache
def settings():
    s = Settings()
    if s.production and (
        not s.app_url.startswith("https://") or len(s.bot_internal_secret) < 32
    ):
        raise RuntimeError("Production requires HTTPS and a strong internal secret")
    return s
