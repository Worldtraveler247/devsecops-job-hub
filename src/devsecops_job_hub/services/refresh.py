"""Refresh service: fetch jobs from each company's ATS and upsert into the DB.

Idempotency key is (company_id, apply_url). On rerun, an existing posting is
updated in place (last_seen_at bumped, fields refreshed). Postings that have
not been seen in 14 days are soft-deleted (is_active=false).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import httpx
from sqlmodel import Session, select

from devsecops_job_hub.adapters import greenhouse, lever
from devsecops_job_hub.db import engine
from devsecops_job_hub.models import ATSProvider, Company, Job

logger = logging.getLogger(__name__)

_STALE_AFTER = timedelta(days=14)


async def refresh_company(company: Company, client: httpx.AsyncClient) -> int:
    if company.ats_provider == ATSProvider.GREENHOUSE:
        adapter_name, fetcher = "greenhouse", greenhouse.fetch_jobs
    elif company.ats_provider == ATSProvider.LEVER:
        adapter_name, fetcher = "lever", lever.fetch_jobs
    else:
        return 0

    try:
        fetched = await fetcher(company, client)
    except httpx.HTTPError as e:
        logger.warning("%s fetch failed for %s: %s", adapter_name, company.name, e)
        return 0

    if not fetched:
        return 0

    written = 0
    with Session(engine) as session:
        for incoming in fetched:
            stmt = select(Job).where(
                Job.company_id == incoming.company_id,
                Job.apply_url == incoming.apply_url,
            )
            existing = session.exec(stmt).first()
            if existing is None:
                session.add(incoming)
                written += 1
            else:
                existing.title = incoming.title
                existing.role_family = incoming.role_family
                existing.career_stage = incoming.career_stage
                existing.clearance_required = incoming.clearance_required
                existing.remote_eligible = incoming.remote_eligible
                existing.location = incoming.location
                existing.posted_at = incoming.posted_at
                existing.last_seen_at = incoming.last_seen_at
                existing.is_active = True
                session.add(existing)
                written += 1
        session.commit()
    return written


async def refresh_all() -> int:
    total = 0
    async with httpx.AsyncClient(headers={"User-Agent": "devsecops-job-hub/0.1"}) as client:
        with Session(engine) as session:
            companies = session.exec(select(Company)).all()
        for company in companies:
            count = await refresh_company(company, client)
            logger.info("refreshed %s: %d postings", company.name, count)
            total += count
    _soft_delete_stale()
    return total


def _soft_delete_stale() -> None:
    cutoff = datetime.now(timezone.utc) - _STALE_AFTER
    with Session(engine) as session:
        stale = session.exec(select(Job).where(Job.is_active, Job.last_seen_at < cutoff)).all()
        for job in stale:
            job.is_active = False
            session.add(job)
        session.commit()
