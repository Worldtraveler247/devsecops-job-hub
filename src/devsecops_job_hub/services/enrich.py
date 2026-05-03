"""Populate Company.annual_revenue_usd from SEC EDGAR for public filers.

Idempotent: companies that already have a revenue figure are skipped.
Revenue rarely changes mid-year — refreshing every 6h would burn SEC
politeness budget for no gain. To force re-enrichment, null the field
manually before running refresh.
"""

from __future__ import annotations

import asyncio
import logging

import httpx
from sqlmodel import Session, select

from devsecops_job_hub.db import engine
from devsecops_job_hub.models import Company, RevenueSource
from devsecops_job_hub.services.edgar import fetch_annual_revenue

logger = logging.getLogger(__name__)

# Pause between SEC requests. Their fair-use limit is ~10/sec; 0.2s gives us
# a conservative 5/sec. Sequential, not concurrent, to avoid burst limits.
_RATE_LIMIT_DELAY = 0.2


async def enrich_companies() -> int:
    with Session(engine) as session:
        candidates = session.exec(
            select(Company).where(
                Company.ticker.is_not(None),  # type: ignore[union-attr]
                Company.annual_revenue_usd.is_(None),  # type: ignore[union-attr]
            )
        ).all()
        # Detach by reading attributes we need before the session closes.
        targets = [(c.id, c.name, c.ticker) for c in candidates]

    if not targets:
        return 0

    enriched = 0
    async with httpx.AsyncClient() as client:
        for company_id, name, ticker in targets:
            if not ticker:
                continue
            try:
                revenue = await fetch_annual_revenue(ticker, client)
            except httpx.HTTPError as e:
                logger.warning("EDGAR fetch failed for %s (%s): %s", name, ticker, e)
                await asyncio.sleep(_RATE_LIMIT_DELAY)
                continue
            await asyncio.sleep(_RATE_LIMIT_DELAY)
            if revenue is None:
                logger.info("no annual revenue found for %s (%s)", name, ticker)
                continue
            with Session(engine) as session:
                fresh = session.get(Company, company_id)
                if fresh is None:
                    continue
                fresh.annual_revenue_usd = revenue.amount_usd
                fresh.revenue_fiscal_year = revenue.fiscal_year
                fresh.revenue_source = RevenueSource.SEC_10K
                session.add(fresh)
                session.commit()
            enriched += 1
            logger.info(
                "enriched %s: $%dM FY%d (10-K %s)",
                name,
                revenue.amount_usd // 1_000_000,
                revenue.fiscal_year,
                revenue.accession_number,
            )
    return enriched
