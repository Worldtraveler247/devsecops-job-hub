"""VCR-recorded integration test for the Greenhouse adapter.

Hits the live Greenhouse API once, records the response to
`tests/cassettes/test_greenhouse_recorded/test_fetch_jobs_against_real_api.yaml`,
and replays it on subsequent runs. Re-record on demand:

    pytest tests/test_greenhouse_recorded.py --record-mode=rewrite

We intentionally pick a small-board company (Shift5) so the cassette stays
under a few hundred KB.
"""

from __future__ import annotations

import httpx
import pytest

from devsecops_job_hub.adapters import greenhouse
from devsecops_job_hub.models import ATSProvider, Company, Job


@pytest.fixture
def shift5() -> Company:
    return Company(
        id=1,
        name="Shift5",
        ats_provider=ATSProvider.GREENHOUSE,
        ats_company_slug="shift5",
    )


@pytest.mark.vcr
async def test_fetch_jobs_against_real_api(shift5: Company) -> None:
    async with httpx.AsyncClient() as client:
        jobs = await greenhouse.fetch_jobs(shift5, client)

    # Loose assertions — counts shift as the company posts/unposts roles. We're
    # really verifying that the live response shape still parses cleanly into
    # our model and that the classifier doesn't choke on real-world titles.
    assert isinstance(jobs, list)
    assert all(isinstance(j, Job) for j in jobs)
    if jobs:
        assert all(j.title for j in jobs)
        assert all(j.apply_url.startswith("https://") for j in jobs)
        assert all(j.company_id == 1 for j in jobs)
