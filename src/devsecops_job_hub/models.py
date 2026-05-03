from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


class ATSProvider(str, Enum):
    GREENHOUSE = "greenhouse"
    LEVER = "lever"
    WORKDAY = "workday"
    ICIMS = "icims"
    USAJOBS = "usajobs"
    CUSTOM = "custom"
    UNKNOWN = "unknown"


class RevenueSource(str, Enum):
    SEC_10K = "sec_10k"
    WASHINGTON_TECHNOLOGY_TOP100 = "washington_tech_top100"
    BGOV200 = "bgov200"
    ESTIMATED = "estimated"


class CareerStage(str, Enum):
    ENTRY = "entry"
    MID = "mid"
    SENIOR = "senior"
    TARGET = "target"


class RoleFamily(str, Enum):
    CLOUD_ADMIN = "cloud_admin"
    JUNIOR_DEVOPS = "junior_devops"
    SYS_SECURITY_ENG = "sys_security_eng"
    SRE = "sre"
    LINUX_ADMIN = "linux_admin"
    SOC_ANALYST = "soc_analyst"
    CLOUD_OPS = "cloud_ops"
    CLOUD_SECURITY_ENG = "cloud_security_eng"
    APPSEC_ENG = "appsec_eng"
    CLOUD_ENGINEER = "cloud_engineer"
    SECURITY_ENG_INFRA = "security_eng_infra"
    DEVOPS_ENG = "devops_eng"
    DEVSECOPS_ENG = "devsecops_eng"
    SECURITY_OFFICER = "security_officer"  # ISSO/ISSM/SSO/CSSO/FSO — Eddie's pivot point


class ClearanceLevel(str, Enum):
    NONE = "none"
    PUBLIC_TRUST = "public_trust"
    SECRET = "secret"
    TOP_SECRET = "top_secret"
    TS_SCI = "ts_sci"
    TS_SCI_POLY = "ts_sci_poly"


class RemoteEligibility(str, Enum):
    ONSITE = "onsite"
    HYBRID = "hybrid"
    REMOTE = "remote"
    REMOTE_CLEARED_FACILITY = "remote_cleared_facility"


class SalarySource(str, Enum):
    POSTING = "posting"
    GLASSDOOR = "glassdoor"
    LEVELS_FYI = "levels_fyi"
    GS_SCALE = "gs_scale"
    ESTIMATED = "estimated"
    UNKNOWN = "unknown"


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Company(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    ticker: str | None = None
    annual_revenue_usd: int | None = None
    revenue_fiscal_year: int | None = None
    revenue_source: RevenueSource | None = None
    careers_url: str | None = None
    ats_provider: ATSProvider = ATSProvider.UNKNOWN
    ats_company_slug: str | None = None
    primary_agencies: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    hq_location: str | None = None
    employee_count_estimate: int | None = None


class Job(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    company_id: int = Field(foreign_key="company.id", index=True)
    title: str
    role_family: RoleFamily | None = Field(default=None, index=True)
    career_stage: CareerStage | None = Field(default=None, index=True)
    clearance_required: ClearanceLevel = Field(default=ClearanceLevel.NONE, index=True)
    clearance_sponsorship_available: bool = False
    remote_eligible: RemoteEligibility = Field(default=RemoteEligibility.ONSITE, index=True)
    location: str | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    salary_source: SalarySource = SalarySource.UNKNOWN
    apply_url: str = Field(index=True)
    posted_at: datetime | None = None
    last_seen_at: datetime = Field(default_factory=_utcnow)
    is_active: bool = Field(default=True, index=True)
    is_oconus: bool = Field(default=False, index=True)
    country: str | None = None
