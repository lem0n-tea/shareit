from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    storage_dir: str = "./data/storage"
    storage_limit: int | None = None
    max_upload_size: int = 5 * 1024**3  # per-file cap (5 GiB)

    pending_uploads_dir: str = "./data/uploads"
    upload_stale_after_seconds: int = 3600

    database_url: str = "sqlite:///./data/shareit.db"

    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    model_config = SettingsConfigDict(env_file=".env")

settings = Settings()
