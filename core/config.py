from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Database
    database_url: str = "postgresql+asyncpg://kaiserclaim:secret@localhost:5432/kaiserclaim"

    # Redis / Celery
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    # Google Gemini
    gemini_api_key: str = ""

    # File storage — NAS mount path inside the pod
    storage_root: str = "/mnt/nas/kaiserclaim"

    # Portal credentials (used by Playwright bots)
    merkur_username: str = ""
    merkur_password: str = ""

    # App
    app_name: str = "KaiserClaim"
    debug: bool = False
    secret_key: str = "change-me-in-production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
