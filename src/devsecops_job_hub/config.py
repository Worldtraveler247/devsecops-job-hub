from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "sqlite:///./jobs.db"
    log_level: str = "INFO"
    http_timeout_seconds: float = 15.0
    enable_scheduler: bool = False  # default off so tests + CI don't hit live APIs
    scheduler_interval_hours: int = 6

    # ── "My fit" profile (env-driven) ──
    # Defaults aim at the project owner's reality: RHCSA + Sec+ + military
    # operations background, B.S. 2023, no production tech job yet, clearable
    # to Secret. Roles a candidate with that exact resume could plausibly
    # land *now* — Linux Admin (RHCSA), ISSO/ISSM (Sec+ + military bg
    # checks the DoDD 8570 box), SOC Analyst, generic systems-security-
    # engineer, plus the cloud-security target the candidate is studying
    # toward. Fork the env vars to retune.
    fit_role_families: list[str] = [
        "linux_admin",
        "security_officer",
        "soc_analyst",
        "sys_security_eng",
        "cloud_security_eng",
        "devsecops_eng",
        "security_eng_infra",
        "cloud_engineer",
    ]
    # Entry-only is intentional: most "Mid" cleared roles ask for 3-5 years
    # of production tech. Set FIT_CAREER_STAGES=entry,mid in .env if you
    # want the looser net.
    fit_career_stages: list[str] = ["entry"]
    fit_max_clearance: str = "secret"  # clearable, but TS/SCI without active is a non-starter
    fit_remote_only: bool = False
    fit_allow_oconus: bool = False

    # SEC EDGAR enrichment. Their fair-use policy requires a real contact
    # email in the User-Agent header; without one, requests may be rate-
    # limited or 403'd. Set EDGAR_CONTACT_EMAIL in .env.
    edgar_contact_email: str = ""

    # USAJobs Search API (data.usajobs.gov). Free; register an email at
    # https://developer.usajobs.gov to get an Authorization-Key. The
    # adapter sends User-Agent: <usajobs_contact_email>. If the key is
    # blank the USAJobs adapter logs a warning and skips its companies.
    usajobs_api_key: str = ""
    usajobs_contact_email: str = ""

    # OpenTelemetry tracing. Off by default — when on, FastAPI / SQLAlchemy /
    # httpx are auto-instrumented and span trees print to stdout via the
    # console exporter. See services/telemetry.py.
    otel_enabled: bool = False
    otel_service_name: str = "devsecops-job-hub"


settings = Settings()
