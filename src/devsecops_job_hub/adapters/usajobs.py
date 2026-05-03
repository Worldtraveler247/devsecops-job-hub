"""USAJobs Search API adapter (data.usajobs.gov).

Endpoint: https://data.usajobs.gov/api/search

Public, JSON. Free Authorization-Key from https://developer.usajobs.gov
(set USAJOBS_API_KEY in .env). User-Agent header must be a real contact
email per their docs (set USAJOBS_CONTACT_EMAIL).

Unlike Greenhouse/Lever — which are per-company boards — USAJobs is a
search API across the entire federal civilian space. We model it as a
single seed Company ("U.S. Federal Government") whose ats_company_slug
encodes a query filter. The adapter applies the audience rule
(no senior, only IT/security categories at GS-12 or below) directly in
the search query so we download less data we'd just throw away.

The federal-civilian space is a fit for the hub's audience: clearance
sponsorship is common, veteran preference is real, and many GS-9 to GS-12
postings explicitly welcome transitioning service members.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from devsecops_job_hub.classify import (
    classify_career_stage,
    classify_clearance,
    classify_country,
    classify_oconus,
    classify_remote,
    classify_role_family,
)
from devsecops_job_hub.config import settings
from devsecops_job_hub.models import (
    ClearanceLevel,
    Company,
    Job,
    SalarySource,
)
from devsecops_job_hub.services.breakers import (
    CircuitOpenError,
    is_open,
    record_failure,
    record_success,
)

logger = logging.getLogger(__name__)

_BASE_URL = "https://data.usajobs.gov/api/search"
_BREAKER_NAME = "usajobs"

# Audience filter applied at query time:
#   - JobCategoryCode 2210 (Information Technology)
#   - JobCategoryCode 0080 (Security Administration)
#   - JobCategoryCode 1550 (Computer Science)
#   - PayGradeHigh GS-12 — caps at mid-career equivalent ($87K-$114K base
#     before locality). Anything GS-13+ is senior per our hub rule.
_DEFAULT_QUERY = {
    "JobCategoryCode": "2210;0080;1550",
    "PayGradeHigh": "GS-12",
    "ResultsPerPage": "100",
}

# Map USAJobs `SecurityClearanceRequired` strings to our ClearanceLevel.
# Source: data.usajobs.gov code list. Strings from the wild are case-
# inconsistent so we lowercase before matching.
_USAJOBS_CLEARANCE: dict[str, ClearanceLevel] = {
    "not required": ClearanceLevel.NONE,
    "public trust - background investigation": ClearanceLevel.PUBLIC_TRUST,
    "public trust": ClearanceLevel.PUBLIC_TRUST,
    "confidential": ClearanceLevel.SECRET,  # USAJobs lumps Confidential under low; treat as Secret-band
    "secret": ClearanceLevel.SECRET,
    "top secret": ClearanceLevel.TOP_SECRET,
    "top secret/sci": ClearanceLevel.TS_SCI,
    "ts/sci": ClearanceLevel.TS_SCI,
    "sensitive compartmented information": ClearanceLevel.TS_SCI,
    "q sensitive": ClearanceLevel.TS_SCI,
    "q access authorization": ClearanceLevel.TS_SCI,
    "l access authorization": ClearanceLevel.SECRET,
    "other": ClearanceLevel.NONE,
}


class _LocationItem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    LocationName: str | None = None
    CountryCode: str | None = None
    CountrySubDivisionCode: str | None = None


class _Remuneration(BaseModel):
    model_config = ConfigDict(extra="ignore")
    MinimumRange: str | None = None
    MaximumRange: str | None = None
    RateIntervalCode: str | None = None  # PA = per annum


class _Descriptor(BaseModel):
    model_config = ConfigDict(extra="ignore")
    PositionID: str
    PositionTitle: str
    PositionURI: str | None = None
    ApplyURI: list[str] | None = None
    PositionLocation: list[_LocationItem] | None = None
    OrganizationName: str | None = None
    DepartmentName: str | None = None
    QualificationSummary: str | None = None
    PositionRemuneration: list[_Remuneration] | None = None
    PublicationStartDate: str | None = None
    SecurityClearanceRequired: str | None = None


class _ResultItem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    MatchedObjectDescriptor: _Descriptor


class _SearchResult(BaseModel):
    model_config = ConfigDict(extra="ignore")
    SearchResultItems: list[_ResultItem] = []


class _Envelope(BaseModel):
    model_config = ConfigDict(extra="ignore")
    SearchResult: _SearchResult


def _classify_clearance_from_field(raw: str | None) -> ClearanceLevel | None:
    if not raw:
        return None
    return _USAJOBS_CLEARANCE.get(raw.strip().lower())


def _annual_salary(rem: list[_Remuneration] | None) -> tuple[int | None, int | None]:
    if not rem:
        return None, None
    first = rem[0]
    if (first.RateIntervalCode or "").upper() != "PA":
        return None, None
    try:
        lo = int(float(first.MinimumRange)) if first.MinimumRange else None
        hi = int(float(first.MaximumRange)) if first.MaximumRange else None
    except (TypeError, ValueError):
        return None, None
    return lo, hi


def _headers() -> dict[str, str]:
    contact = settings.usajobs_contact_email or "contact-not-set@example.invalid"
    return {
        "Host": "data.usajobs.gov",
        "User-Agent": contact,
        "Authorization-Key": settings.usajobs_api_key,
    }


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
    retry=retry_if_exception_type((httpx.TransportError, httpx.HTTPStatusError)),
)
async def _get(client: httpx.AsyncClient, params: dict[str, str]) -> dict[str, Any]:
    resp = await client.get(_BASE_URL, params=params, headers=_headers(), timeout=20.0)
    resp.raise_for_status()
    payload: dict[str, Any] = resp.json()
    return payload


async def fetch_jobs(company: Company, client: httpx.AsyncClient) -> list[Job]:
    if not settings.usajobs_api_key:
        logger.info("USAJOBS_API_KEY unset; skipping %s", company.name)
        return []
    if is_open(_BREAKER_NAME):
        raise CircuitOpenError(_BREAKER_NAME)

    try:
        payload = await _get(client, _DEFAULT_QUERY)
    except (httpx.TransportError, httpx.HTTPStatusError):
        record_failure(_BREAKER_NAME)
        raise
    record_success(_BREAKER_NAME)

    parsed = _Envelope.model_validate(payload)
    now = datetime.now(UTC)
    jobs: list[Job] = []
    # USAJobs's CountryCode field is misnamed — it returns the full country
    # name ("United States", "Japan", etc.), not the ISO code. Treat any of
    # these strings as US.
    _us_aliases = {"us", "usa", "united states", "united states of america"}
    for item in parsed.SearchResult.SearchResultItems:
        d = item.MatchedObjectDescriptor
        location_name = d.PositionLocation[0].LocationName if d.PositionLocation else None
        country_code = d.PositionLocation[0].CountryCode if d.PositionLocation else None
        is_oconus = bool(country_code and country_code.strip().lower() not in _us_aliases)
        if not is_oconus and location_name:
            is_oconus = classify_oconus(location_name)
        country = classify_country(location_name) if is_oconus else None

        # Prefer the structured SecurityClearanceRequired field; fall back
        # to text-classifying title + qualifications if it's missing.
        clearance = _classify_clearance_from_field(d.SecurityClearanceRequired)
        if clearance is None:
            clearance = classify_clearance(d.PositionTitle, d.QualificationSummary)

        salary_min, salary_max = _annual_salary(d.PositionRemuneration)
        salary_source = SalarySource.POSTING if salary_min and salary_max else SalarySource.UNKNOWN

        apply_url = d.ApplyURI[0] if d.ApplyURI else d.PositionURI
        if not apply_url:
            continue

        try:
            posted_at = (
                datetime.fromisoformat(d.PublicationStartDate) if d.PublicationStartDate else None
            )
        except ValueError:
            posted_at = None
        if posted_at and posted_at.tzinfo is None:
            posted_at = posted_at.replace(tzinfo=UTC)

        jobs.append(
            Job(
                company_id=company.id or 0,
                title=d.PositionTitle,
                role_family=classify_role_family(d.PositionTitle, d.QualificationSummary),
                career_stage=classify_career_stage(d.PositionTitle, d.QualificationSummary),
                clearance_required=clearance,
                clearance_sponsorship_available=clearance != ClearanceLevel.NONE,
                remote_eligible=classify_remote(location_name),
                location=location_name,
                salary_min=salary_min,
                salary_max=salary_max,
                salary_source=salary_source,
                apply_url=apply_url,
                posted_at=posted_at,
                last_seen_at=now,
                is_active=True,
                is_oconus=is_oconus,
                country=country,
            )
        )
    return jobs
