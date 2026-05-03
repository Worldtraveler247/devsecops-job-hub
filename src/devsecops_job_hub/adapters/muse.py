"""The Muse public jobs API adapter (themuse.com).

Endpoint: https://www.themuse.com/api/public/jobs

Public, JSON, no authentication. Aggregates IT roles across hundreds of
employers — fills the "regular IT" gap between our defense-tech sources
(Greenhouse + Lever) and the federal civilian source (USAJobs).

Audience filter applied via query params (level + category) so we only
fetch postings that pass the hub's "no senior" rule. Pagination is
shallow on purpose — one page (20 results) per refresh keeps latency
predictable; bump _PAGES_PER_REFRESH if you want broader coverage.

Multi-employer modeling: The Muse aggregates many employers under one
search API. Rather than create a Company row per employer (which would
churn rapidly), we bind every Muse posting to a single seed Company
("The Muse — Tech Jobs") and embed the actual employer in the job
title: "Software Engineer — SpaceX". This keeps the Job model stable
while preserving the source-employer signal in the UI.
"""

from __future__ import annotations

import html
import logging
import re
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
from devsecops_job_hub.models import Company, Job, RemoteEligibility, SalarySource
from devsecops_job_hub.services.breakers import (
    CircuitOpenError,
    is_open,
    record_failure,
    record_success,
)

logger = logging.getLogger(__name__)

_BASE_URL = "https://www.themuse.com/api/public/jobs"
_BREAKER_NAME = "muse"

# How many pages to pull per refresh. 20 results/page. Muse's "Software
# Engineering" category is a wide bucket — many results are hardware /
# optical / mechanical "Engineer" titles that our classifier (correctly)
# drops. Pulling deeper helps surface a viable count of actual SWE postings.
_PAGES_PER_REFRESH = 10

# Audience filter applied at query time. The Muse's level taxonomy is:
#   Entry Level / Mid Level / Senior Level / Manager / etc.
# We pull only Entry + Mid to honor the hub's "no senior" rule before
# any data hits the network. Categories are restricted to the two valid
# Muse buckets that actually contain software roles ("IT" returns zero
# results — Muse doesn't expose it as a top-level category).
_DEFAULT_QUERY_PARAMS = [
    ("level", "Entry Level"),
    ("level", "Mid Level"),
    ("category", "Software Engineering"),
    ("category", "Data Science"),
    ("descending", "true"),
]


_HTML_TAG = re.compile(r"<[^>]+>")
_WHITESPACE = re.compile(r"\s+")


def _strip_html(raw: str | None) -> str | None:
    if not raw:
        return None
    text = html.unescape(html.unescape(raw))
    text = _HTML_TAG.sub(" ", text)
    return _WHITESPACE.sub(" ", text).strip() or None


class _LocationItem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str | None = None


class _CompanyItem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str | None = None


class _Refs(BaseModel):
    model_config = ConfigDict(extra="ignore")
    landing_page: str | None = None


class _MuseJob(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: int
    name: str
    publication_date: str | None = None
    contents: str | None = None
    locations: list[_LocationItem] | None = None
    company: _CompanyItem | None = None
    refs: _Refs | None = None


class _Envelope(BaseModel):
    model_config = ConfigDict(extra="ignore")
    page: int = 0
    page_count: int = 0
    results: list[_MuseJob] = []


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
    retry=retry_if_exception_type((httpx.TransportError, httpx.HTTPStatusError)),
)
async def _get_page(client: httpx.AsyncClient, page: int) -> dict[str, Any]:
    params: list[tuple[str, str | int | float | bool | None]] = [
        *_DEFAULT_QUERY_PARAMS,
        ("page", str(page)),
    ]
    resp = await client.get(_BASE_URL, params=params, timeout=20.0)
    resp.raise_for_status()
    payload: dict[str, Any] = resp.json()
    return payload


def _location_for(locations: list[_LocationItem] | None) -> tuple[str | None, RemoteEligibility]:
    """Return (display_location, remote_eligibility).

    The Muse uses 'Flexible / Remote' as a sentinel for fully-remote
    postings; classify_remote handles the keyword 'remote' but not the
    slash-separated variant, so we shortcut it here.
    """
    if not locations:
        return None, RemoteEligibility.ONSITE
    first = locations[0].name or ""
    if "remote" in first.lower() or "flexible" in first.lower():
        return first, RemoteEligibility.REMOTE
    return first, classify_remote(first)


async def fetch_jobs(company: Company, client: httpx.AsyncClient) -> list[Job]:
    if is_open(_BREAKER_NAME):
        raise CircuitOpenError(_BREAKER_NAME)

    all_jobs: list[Job] = []
    now = datetime.now(UTC)

    for page in range(_PAGES_PER_REFRESH):
        try:
            payload = await _get_page(client, page)
        except (httpx.TransportError, httpx.HTTPStatusError):
            record_failure(_BREAKER_NAME)
            raise
        record_success(_BREAKER_NAME)

        parsed = _Envelope.model_validate(payload)
        if not parsed.results:
            break

        for r in parsed.results:
            description = _strip_html(r.contents)
            location_name, remote = _location_for(r.locations)
            country = classify_country(location_name) if location_name else None
            is_oconus = bool(country) or (
                classify_oconus(location_name) if location_name else False
            )

            employer = (r.company.name if r.company else None) or "Unknown"
            # Embed the source employer in the title so the UI shows it even
            # though every Muse job's company_id points at the seed entry.
            title = f"{r.name} — {employer}"

            apply_url = r.refs.landing_page if r.refs else None
            if not apply_url:
                continue

            try:
                posted_at = (
                    datetime.fromisoformat(r.publication_date) if r.publication_date else None
                )
            except ValueError:
                posted_at = None
            if posted_at and posted_at.tzinfo is None:
                posted_at = posted_at.replace(tzinfo=UTC)

            all_jobs.append(
                Job(
                    company_id=company.id or 0,
                    title=title,
                    role_family=classify_role_family(r.name, description),
                    career_stage=classify_career_stage(r.name, description),
                    clearance_required=classify_clearance(r.name, description),
                    clearance_sponsorship_available=False,
                    remote_eligible=remote,
                    location=location_name,
                    salary_min=None,
                    salary_max=None,
                    salary_source=SalarySource.UNKNOWN,
                    apply_url=apply_url,
                    posted_at=posted_at,
                    last_seen_at=now,
                    is_active=True,
                    is_oconus=is_oconus,
                    country=country if is_oconus else None,
                )
            )

        # If we reached the last page, stop early.
        if parsed.page_count and page + 1 >= parsed.page_count:
            break

    return all_jobs
