"""VCR-recorded integration test for the Lever adapter.

Hits the live Lever public-postings API once, records to
`tests/cassettes/test_lever_recorded/test_fetch_jobs_against_real_api.yaml`,
and replays on subsequent runs. Re-record on demand:

    pytest tests/test_lever_recorded.py --record-mode=rewrite

Shield AI is a small-to-mid Lever board — small enough to keep the cassette
compact, defense-tech enough to exercise our clearance/role classifiers.
"""

from __future__ import annotations

import httpx
import pytest

from devsecops_job_hub.adapters import lever
from devsecops_job_hub.models import ATSProvider, Company, Job


@pytest.fixture
def shield_ai() -> Company:
    return Company(
        id=2,
        name="Shield AI",
        ats_provider=ATSProvider.LEVER,
        ats_company_slug="shieldai",
    )


@pytest.mark.vcr
async def test_fetch_jobs_against_real_api(shield_ai: Company) -> None:
    async with httpx.AsyncClient() as client:
        jobs = await lever.fetch_jobs(shield_ai, client)

    assert isinstance(jobs, list)
    assert all(isinstance(j, Job) for j in jobs)
    if jobs:
        assert all(j.title for j in jobs)
        assert all(j.apply_url.startswith("https://") for j in jobs)
        assert all(j.company_id == 2 for j in jobs)
