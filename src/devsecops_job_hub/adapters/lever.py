"""Lever public postings API adapter.

Endpoint: https://api.lever.co/v0/postings/{slug}?mode=json

Public, unauthenticated. Returns a top-level JSON ARRAY (not wrapped in `jobs`).
Each posting has: id, text (= title), categories.{location, team, commitment},
hostedUrl, applyUrl, createdAt (ms epoch), workplaceType, country.
"""

from __future__ import annotations

from datetime import datetime, timezone

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
from devsecops_job_hub.models import Company, Job, RemoteEligibility, SalarySource

_BASE_URL = "https://api.lever.co/v0/postings"


class _LeverCategories(BaseModel):
    model_config = ConfigDict(extra="ignore")
    location: str | None = None
    team: str | None = None
    commitment: str | None = None


class _LeverPosting(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    text: str
    categories: _LeverCategories | None = None
    hostedUrl: str
    createdAt: int | None = None
    workplaceType: str | None = None
    country: str | None = None


def _workplace_to_remote(workplace: str | None, location: str | None) -> RemoteEligibility:
    if workplace == "remote":
        return RemoteEligibility.REMOTE
    if workplace == "hybrid":
        return RemoteEligibility.HYBRID
    if workplace == "on-site":
        return RemoteEligibility.ONSITE
    return classify_remote(location)


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
    retry=retry_if_exception_type((httpx.TransportError, httpx.HTTPStatusError)),
)
async def _get(client: httpx.AsyncClient, url: str) -> list[dict]:
    resp = await client.get(url, timeout=15.0)
    resp.raise_for_status()
    payload = resp.json()
    if not isinstance(payload, list):
        return []
    return payload


async def fetch_jobs(company: Company, client: httpx.AsyncClient) -> list[Job]:
    if not company.ats_company_slug:
        return []
    url = f"{_BASE_URL}/{company.ats_company_slug}?mode=json"
    payload = await _get(client, url)
    parsed = [_LeverPosting.model_validate(p) for p in payload]

    now = datetime.now(timezone.utc)
    jobs: list[Job] = []
    for p in parsed:
        location = p.categories.location if p.categories else None
        # Lever's `country` field is canonical and trumps location-string parsing.
        country = p.country or classify_country(location)
        is_oconus = bool(country and country.lower() not in {"united states", "usa", "us"})
        if not is_oconus:
            is_oconus = classify_oconus(location)

        posted_at = (
            datetime.fromtimestamp(p.createdAt / 1000, tz=timezone.utc) if p.createdAt else None
        )

        jobs.append(
            Job(
                company_id=company.id or 0,
                title=p.text,
                role_family=classify_role_family(p.text),
                career_stage=classify_career_stage(p.text),
                clearance_required=classify_clearance(p.text),
                clearance_sponsorship_available=False,
                remote_eligible=_workplace_to_remote(p.workplaceType, location),
                location=location,
                salary_min=None,
                salary_max=None,
                salary_source=SalarySource.UNKNOWN,
                apply_url=p.hostedUrl,
                posted_at=posted_at,
                last_seen_at=now,
                is_active=True,
                is_oconus=is_oconus,
                country=country if is_oconus else None,
            )
        )
    return jobs
