"""Adapter tests for USAJobs. MockTransport-based; no live API calls."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from devsecops_job_hub.adapters import usajobs
from devsecops_job_hub.config import settings
from devsecops_job_hub.models import (
    ATSProvider,
    ClearanceLevel,
    Company,
    RemoteEligibility,
    RoleFamily,
    SalarySource,
)

_FIXTURE = Path(__file__).parent / "fixtures" / "usajobs_sample.json"


@pytest.fixture
def fixture_payload() -> dict:
    return json.loads(_FIXTURE.read_text())


@pytest.fixture
def fed_company() -> Company:
    return Company(
        id=77,
        name="U.S. Federal Government",
        ats_provider=ATSProvider.USAJOBS,
        ats_company_slug="federal-it",
    )


@pytest.fixture(autouse=True)
def stub_api_key(monkeypatch):
    # The adapter short-circuits when the API key is unset. Stub a value
    # for the duration of each test so the fetch path runs.
    monkeypatch.setattr(settings, "usajobs_api_key", "test-key")
    monkeypatch.setattr(settings, "usajobs_contact_email", "test@example.com")
    yield


@pytest.fixture(autouse=True)
def reset_breakers():
    from devsecops_job_hub.services.breakers import reset_all

    reset_all()
    yield
    reset_all()


async def test_fetch_jobs_parses_and_classifies(fixture_payload, fed_company):
    def handler(request: httpx.Request) -> httpx.Response:
        # Verify the audience filter was applied at query time.
        assert "JobCategoryCode=" in str(request.url)
        assert "PayGradeHigh=GS-12" in str(request.url)
        assert request.headers["Authorization-Key"] == "test-key"
        assert request.headers["User-Agent"] == "test@example.com"
        return httpx.Response(200, json=fixture_payload)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        jobs = await usajobs.fetch_jobs(fed_company, client)

    assert len(jobs) == 3

    # First posting — TS/SCI cleared, CONUS, salary disclosed
    cyber_md = jobs[0]
    assert cyber_md.title == "IT Specialist (INFOSEC)"
    assert cyber_md.clearance_required == ClearanceLevel.TS_SCI
    assert cyber_md.clearance_sponsorship_available is True
    assert cyber_md.salary_min == 62107
    assert cyber_md.salary_max == 97950
    assert cyber_md.salary_source == SalarySource.POSTING
    assert cyber_md.is_oconus is False
    assert cyber_md.country is None

    # Second — overseas base, structured country flag
    yokota = jobs[1]
    assert yokota.is_oconus is True
    assert yokota.country == "Japan"
    assert yokota.clearance_required == ClearanceLevel.SECRET

    # Third — remote, public-trust, entry-level signal in description
    cisa = jobs[2]
    assert cisa.remote_eligible == RemoteEligibility.REMOTE
    assert cisa.clearance_required == ClearanceLevel.PUBLIC_TRUST
    assert cisa.role_family in {
        RoleFamily.SYS_SECURITY_ENG,
        RoleFamily.CLOUD_SECURITY_ENG,
        RoleFamily.DEVSECOPS_ENG,
    }


async def test_fetch_skips_when_api_key_missing(fed_company, monkeypatch):
    monkeypatch.setattr(settings, "usajobs_api_key", "")

    async with httpx.AsyncClient() as client:
        # No request should be made — would 422 if the handler was reached.
        jobs = await usajobs.fetch_jobs(fed_company, client)
    assert jobs == []


async def test_clearance_field_takes_precedence_over_text(fixture_payload, fed_company):
    # The first posting's title alone has no clearance keyword, but the
    # SecurityClearanceRequired field says "Top Secret/SCI" — the structured
    # field must win.
    fixture_payload["SearchResult"]["SearchResultItems"][0]["MatchedObjectDescriptor"][
        "QualificationSummary"
    ] = "No clearance words in this string at all."

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=fixture_payload)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        jobs = await usajobs.fetch_jobs(fed_company, client)
    assert jobs[0].clearance_required == ClearanceLevel.TS_SCI


async def test_circuit_breaker_trips_on_repeated_5xx(fed_company):
    from devsecops_job_hub.services.breakers import CircuitOpenError

    def always_fail(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="upstream broken")

    transport = httpx.MockTransport(always_fail)
    async with httpx.AsyncClient(transport=transport) as client:
        for _ in range(3):
            with pytest.raises(httpx.HTTPStatusError):
                await usajobs.fetch_jobs(fed_company, client)
        with pytest.raises(CircuitOpenError):
            await usajobs.fetch_jobs(fed_company, client)
