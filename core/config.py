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

    # IBAN to select on the Überweisungskonto step; leave empty to use the pre-selected account
    merkur_bank_iban: str = ""

    # Set to True to skip real Merkur portal submission (for local testing)
    merkur_dry_run: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
