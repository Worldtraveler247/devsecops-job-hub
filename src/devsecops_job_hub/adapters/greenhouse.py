"""Greenhouse public boards API adapter.

Endpoint shape: https://boards-api.greenhouse.io/v1/boards/{slug}/jobs

Public, unauthenticated. Returns active postings with title, location, absolute_url,
and updated_at. We do NOT request `?content=true` — the HTML descriptions are heavy
and v1 only needs titles for classification.
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
from devsecops_job_hub.models import Company, Job, SalarySource

_BASE_URL = "https://boards-api.greenhouse.io/v1/boards"


class _Location(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str | None = None


class _GreenhouseJob(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: int
    title: str
    location: _Location | None = None
    absolute_url: str
    updated_at: datetime


class _GreenhouseResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    jobs: list[_GreenhouseJob]


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
    retry=retry_if_exception_type((httpx.TransportError, httpx.HTTPStatusError)),
)
async def _get(client: httpx.AsyncClient, url: str) -> dict:
    resp = await client.get(url, timeout=15.0)
    resp.raise_for_status()
    return resp.json()


async def fetch_jobs(company: Company, client: httpx.AsyncClient) -> list[Job]:
    if not company.ats_company_slug:
        return []
    url = f"{_BASE_URL}/{company.ats_company_slug}/jobs"
    payload = await _get(client, url)
    parsed = _GreenhouseResponse.model_validate(payload)

    now = datetime.now(timezone.utc)
    jobs: list[Job] = []
    for g in parsed.jobs:
        location_name = g.location.name if g.location else None
        # Classify against title (primary) and location (for remote detection).
        # Clearance is classified against title here; description-aware classification
        # is a Slice 2 enhancement.
        jobs.append(
            Job(
                company_id=company.id or 0,
                title=g.title,
                role_family=classify_role_family(g.title),
                career_stage=classify_career_stage(g.title),
                clearance_required=classify_clearance(g.title),
                clearance_sponsorship_available=False,
                remote_eligible=classify_remote(location_name),
                location=location_name,
                salary_min=None,
                salary_max=None,
                salary_source=SalarySource.UNKNOWN,
                apply_url=g.absolute_url,
                posted_at=g.updated_at,
                last_seen_at=now,
                is_active=True,
                is_oconus=classify_oconus(location_name),
                country=classify_country(location_name),
            )
        )
    return jobs
