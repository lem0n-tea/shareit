from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    storage_dir: str = "./storage"
    storage_limit: int | None = None

    model_config = SettingsConfigDict(env_file=".env")

settings = Settings()
