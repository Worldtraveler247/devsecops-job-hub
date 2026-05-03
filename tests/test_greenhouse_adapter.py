import json
from pathlib import Path

import httpx
import pytest

from devsecops_job_hub.adapters import greenhouse
from devsecops_job_hub.models import (
    ATSProvider,
    CareerStage,
    ClearanceLevel,
    Company,
    RemoteEligibility,
    RoleFamily,
)

_FIXTURE = Path(__file__).parent / "fixtures" / "greenhouse_sample.json"


@pytest.fixture
def fixture_payload() -> dict:
    return json.loads(_FIXTURE.read_text())


@pytest.fixture
def fake_company() -> Company:
    return Company(
        id=42,
        name="Acme Defense",
        ats_provider=ATSProvider.GREENHOUSE,
        ats_company_slug="acme",
    )


async def test_fetch_jobs_parses_and_classifies(fixture_payload, fake_company):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/boards/acme/jobs")
        return httpx.Response(200, json=fixture_payload)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        jobs = await greenhouse.fetch_jobs(fake_company, client)

    assert len(jobs) == 4

    devsecops = jobs[0]
    assert devsecops.role_family == RoleFamily.DEVSECOPS_ENG
    assert devsecops.career_stage == CareerStage.SENIOR
    assert devsecops.clearance_required == ClearanceLevel.SECRET
    assert devsecops.company_id == 42

    cloud_sec = jobs[1]
    assert cloud_sec.role_family == RoleFamily.CLOUD_SECURITY_ENG
    assert cloud_sec.remote_eligible == RemoteEligibility.REMOTE

    junior = jobs[2]
    assert junior.role_family == RoleFamily.LINUX_ADMIN
    assert junior.career_stage == CareerStage.ENTRY

    sre = jobs[3]
    assert sre.role_family == RoleFamily.SRE
    assert sre.clearance_required == ClearanceLevel.TS_SCI
    assert sre.remote_eligible == RemoteEligibility.HYBRID


async def test_fetch_jobs_skips_when_no_slug():
    company = Company(name="No Slug Co", ats_provider=ATSProvider.GREENHOUSE)
    async with httpx.AsyncClient() as client:
        jobs = await greenhouse.fetch_jobs(company, client)
    assert jobs == []
