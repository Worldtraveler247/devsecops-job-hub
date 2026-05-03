from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "sqlite:///./jobs.db"
    log_level: str = "INFO"
    http_timeout_seconds: float = 15.0
    enable_scheduler: bool = False  # default off so tests + CI don't hit live APIs
    scheduler_interval_hours: int = 6


settings = Settings()
