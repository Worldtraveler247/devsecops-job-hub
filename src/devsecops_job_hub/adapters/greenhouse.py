"""Greenhouse public boards API adapter.

Endpoint shape: https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true

Public, unauthenticated. Returns active postings with title, location,
absolute_url, updated_at, and (with content=true) HTML description. We strip
HTML to plain text before passing to the classifier so keyword matching works
on readable copy rather than markup.
"""

from __future__ import annotations

import html
import re
from datetime import UTC, datetime

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
from devsecops_job_hub.services.breakers import (
    CircuitOpenError,
    is_open,
    record_failure,
    record_success,
)
from devsecops_job_hub.services.salary_parse import parse_salary_from_text

_BREAKER_NAME = "greenhouse"

_BASE_URL = "https://boards-api.greenhouse.io/v1/boards"

_HTML_TAG = re.compile(r"<[^>]+>")
_WHITESPACE = re.compile(r"\s+")


def _strip_html(raw: str | None) -> str | None:
    if not raw:
        return None
    # Greenhouse double-encodes: `content` arrives as HTML-entity-escaped HTML
    # (e.g. `&lt;div&gt;` not `<div>`), and the inner content has its own
    # entities (`&amp;mdash;` not `&mdash;`). Unescape twice to fully decode,
    # then strip the real tags. unescape is idempotent on already-decoded
    # text, so the second pass is a no-op on clean strings.
    text = html.unescape(html.unescape(raw))
    text = _HTML_TAG.sub(" ", text)
    return _WHITESPACE.sub(" ", text).strip() or None


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
    content: str | None = None


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
    if is_open(_BREAKER_NAME):
        raise CircuitOpenError(_BREAKER_NAME)
    url = f"{_BASE_URL}/{company.ats_company_slug}/jobs?content=true"
    try:
        payload = await _get(client, url)
    except (httpx.TransportError, httpx.HTTPStatusError):
        record_failure(_BREAKER_NAME)
        raise
    record_success(_BREAKER_NAME)
    parsed = _GreenhouseResponse.model_validate(payload)

    now = datetime.now(UTC)
    jobs: list[Job] = []
    for g in parsed.jobs:
        location_name = g.location.name if g.location else None
        description = _strip_html(g.content)
        salary_min, salary_max = parse_salary_from_text(description)
        salary_source = SalarySource.POSTING if salary_min and salary_max else SalarySource.UNKNOWN
        jobs.append(
            Job(
                company_id=company.id or 0,
                title=g.title,
                role_family=classify_role_family(g.title, description),
                career_stage=classify_career_stage(g.title, description),
                clearance_required=classify_clearance(g.title, description),
                clearance_sponsorship_available=False,
                remote_eligible=classify_remote(location_name),
                location=location_name,
                salary_min=salary_min,
                salary_max=salary_max,
                salary_source=salary_source,
                apply_url=g.absolute_url,
                posted_at=g.updated_at,
                last_seen_at=now,
                is_active=True,
                is_oconus=classify_oconus(location_name),
                country=classify_country(location_name),
            )
        )
    return jobs
