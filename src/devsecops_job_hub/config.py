from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "sqlite:///./jobs.db"
    log_level: str = "INFO"
    http_timeout_seconds: float = 15.0
    enable_scheduler: bool = False  # default off so tests + CI don't hit live APIs
    scheduler_interval_hours: int = 6

    # ── "My fit" profile (env-driven; defaults match a junior cloud-security pivot) ──
    fit_role_families: list[str] = [
        "cloud_security_eng",
        "devsecops_eng",
        "cloud_engineer",
        "linux_admin",
        "security_eng_infra",
        "sys_security_eng",
    ]
    fit_career_stages: list[str] = ["entry", "mid"]
    fit_max_clearance: str = "secret"  # accept jobs requiring up to SECRET
    fit_remote_only: bool = False
    fit_allow_oconus: bool = False

    # SEC EDGAR enrichment. Their fair-use policy requires a real contact
    # email in the User-Agent header; without one, requests may be rate-
    # limited or 403'd. Set EDGAR_CONTACT_EMAIL in .env.
    edgar_contact_email: str = ""


settings = Settings()
