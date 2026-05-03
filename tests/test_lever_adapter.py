import json
from pathlib import Path

import httpx
import pytest

from devsecops_job_hub.adapters import lever
from devsecops_job_hub.models import (
    ATSProvider,
    ClearanceLevel,
    Company,
    RemoteEligibility,
    RoleFamily,
)

_FIXTURE = Path(__file__).parent / "fixtures" / "lever_sample.json"


@pytest.fixture
def fixture_payload() -> list:
    return json.loads(_FIXTURE.read_text())


@pytest.fixture
def fake_company() -> Company:
    return Company(
        id=99,
        name="Acme Lever Co",
        ats_provider=ATSProvider.LEVER,
        ats_company_slug="acme",
    )


async def test_fetch_jobs_parses_and_classifies(fixture_payload, fake_company):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/postings/acme")
        return httpx.Response(200, json=fixture_payload)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        jobs = await lever.fetch_jobs(fake_company, client)

    assert len(jobs) == 3

    devops = jobs[0]
    assert devops.role_family == RoleFamily.DEVOPS_ENG
    assert devops.remote_eligible == RemoteEligibility.HYBRID
    assert devops.is_oconus is False
    assert devops.country is None

    isso = jobs[1]
    assert isso.role_family == RoleFamily.SECURITY_OFFICER
    assert isso.is_oconus is True
    assert isso.country == "Japan"
    assert isso.location == "Aomori, Japan"

    cloud_sec = jobs[2]
    assert cloud_sec.role_family == RoleFamily.CLOUD_SECURITY_ENG
    assert cloud_sec.remote_eligible == RemoteEligibility.REMOTE
    assert cloud_sec.clearance_required == ClearanceLevel.NONE
    assert cloud_sec.is_oconus is False


async def test_fetch_jobs_skips_when_no_slug():
    company = Company(name="No Slug", ats_provider=ATSProvider.LEVER)
    async with httpx.AsyncClient() as client:
        jobs = await lever.fetch_jobs(company, client)
    assert jobs == []


async def test_fetch_jobs_handles_non_array_response(fake_company):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"error": "not an array"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        jobs = await lever.fetch_jobs(fake_company, client)
    assert jobs == []
