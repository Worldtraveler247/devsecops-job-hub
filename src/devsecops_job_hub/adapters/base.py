from typing import Protocol

import httpx

from devsecops_job_hub.models import Company, Job


class ATSAdapter(Protocol):
    """Protocol every ATS adapter implements.

    Adapters are pure functions: given a Company and a shared httpx client,
    return Job rows ready to upsert. They do not write to the DB themselves —
    the refresh service owns persistence.
    """

    async def fetch_jobs(self, company: Company, client: httpx.AsyncClient) -> list[Job]: ...
