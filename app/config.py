from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    storage_dir: str = "./data/storage"
    storage_limit: int | None = None

    database_url: str = "sqlite:///./data/shareit.db"

    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    model_config = SettingsConfigDict(env_file=".env")

settings = Settings()
