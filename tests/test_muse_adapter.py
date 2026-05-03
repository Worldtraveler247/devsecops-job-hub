"""Adapter tests for The Muse. MockTransport-based; no live API calls."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from devsecops_job_hub.adapters import muse
from devsecops_job_hub.models import (
    ATSProvider,
    CareerStage,
    Company,
    RemoteEligibility,
    RoleFamily,
)

_FIXTURE = Path(__file__).parent / "fixtures" / "muse_sample.json"


@pytest.fixture
def fixture_payload() -> dict:
    return json.loads(_FIXTURE.read_text())


@pytest.fixture
def muse_company() -> Company:
    return Company(
        id=88,
        name="The Muse — Tech Jobs",
        ats_provider=ATSProvider.MUSE,
        ats_company_slug="muse-tech",
    )


@pytest.fixture(autouse=True)
def reset_breakers():
    from devsecops_job_hub.services.breakers import reset_all

    reset_all()
    yield
    reset_all()


@pytest.fixture(autouse=True)
def single_page(monkeypatch):
    # Fixture has page_count=1; cap pagination so the test handler isn't
    # called repeatedly looking for empty pages we don't supply.
    monkeypatch.setattr(muse, "_PAGES_PER_REFRESH", 1)
    yield


async def test_fetch_jobs_parses_and_classifies(fixture_payload, muse_company):
    def handler(request: httpx.Request) -> httpx.Response:
        # Verify the audience filter was applied at query time.
        url = str(request.url)
        assert "level=Entry+Level" in url or "level=Entry%20Level" in url
        assert "level=Mid+Level" in url or "level=Mid%20Level" in url
        assert "category=" in url
        return httpx.Response(200, json=fixture_payload)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        jobs = await muse.fetch_jobs(muse_company, client)

    assert len(jobs) == 3

    stripe_job = jobs[0]
    # Source employer is appended to the title with an em-dash.
    assert stripe_job.title == "Software Engineer — Stripe"
    assert stripe_job.remote_eligible == RemoteEligibility.REMOTE
    assert stripe_job.is_oconus is False
    assert stripe_job.apply_url == "https://www.themuse.com/jobs/stripe/software-engineer"

    mongo_job = jobs[1]
    assert mongo_job.title == "Junior DevOps Engineer — MongoDB"
    assert mongo_job.role_family == RoleFamily.DEVOPS_ENG
    assert mongo_job.career_stage == CareerStage.ENTRY
    assert mongo_job.is_oconus is False

    datadog_job = jobs[2]
    assert datadog_job.title == "Cloud Security Engineer — Datadog"
    assert datadog_job.role_family == RoleFamily.CLOUD_SECURITY_ENG
    assert datadog_job.is_oconus is True
    assert datadog_job.country == "Germany"


async def test_skips_results_without_apply_url(fixture_payload, muse_company):
    fixture_payload["results"][0]["refs"] = {}
    fixture_payload["results"][1]["refs"] = None

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=fixture_payload)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        jobs = await muse.fetch_jobs(muse_company, client)
    # Only the third (Datadog) result has a landing_page; first two skipped.
    assert len(jobs) == 1
    assert jobs[0].title.startswith("Cloud Security Engineer")


async def test_circuit_breaker_trips_on_repeated_5xx(muse_company):
    from devsecops_job_hub.services.breakers import CircuitOpenError

    def always_fail(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="upstream broken")

    transport = httpx.MockTransport(always_fail)
    async with httpx.AsyncClient(transport=transport) as client:
        for _ in range(3):
            with pytest.raises(httpx.HTTPStatusError):
                await muse.fetch_jobs(muse_company, client)
        with pytest.raises(CircuitOpenError):
            await muse.fetch_jobs(muse_company, client)
