"""SEC EDGAR client for annual-revenue enrichment.

Pulls fiscal-year revenue from public-company 10-K filings via the EDGAR XBRL
API. Honesty constraint (per spec): revenue is never fabricated. If we can't
find a 10-K FY entry under any known revenue concept, the function returns
None and the company's revenue stays unset.

Compliance notes
- Public, unauthenticated. SEC fair-use limit is ~10 req/sec.
- SEC requires a User-Agent identifying the requester. Set
  EDGAR_CONTACT_EMAIL in .env (or the env directly) to comply. If unset, we
  log a warning and use a placeholder — SEC may rate-limit or 403 the call.
- We use the per-concept endpoint (companyconcept) rather than full
  companyfacts so each request is ~30-200KB instead of 5-15MB.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from devsecops_job_hub.config import settings

logger = logging.getLogger(__name__)

_TICKER_URL = "https://www.sec.gov/files/company_tickers.json"
_CONCEPT_URL = "https://data.sec.gov/api/xbrl/companyconcept/CIK{cik:010d}/us-gaap/{concept}.json"

# Try concepts in priority order. Modern SaaS companies file under
# RevenueFromContractWithCustomerExcludingAssessedTax (ASC 606); older /
# diversified filers use Revenues; some use SalesRevenueNet.
_REVENUE_CONCEPTS = (
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "Revenues",
    "SalesRevenueNet",
)


@dataclass(frozen=True)
class AnnualRevenue:
    amount_usd: int
    fiscal_year: int
    accession_number: str  # links to the source 10-K filing for traceability


# Process-lifetime cache. The ticker-to-CIK map is ~600KB and rarely changes —
# loading once per process is plenty.
_cik_cache: dict[str, int] | None = None


def _user_agent() -> str:
    contact = settings.edgar_contact_email
    if not contact:
        logger.warning(
            "edgar_contact_email is unset — SEC requires a real contact in the User-Agent. "
            "Set EDGAR_CONTACT_EMAIL in .env."
        )
        contact = "contact-not-set@example.invalid"
    return f"DevSecOps Job Hub {contact}"


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
    retry=retry_if_exception_type((httpx.TransportError, httpx.HTTPStatusError)),
)
async def _get_json(client: httpx.AsyncClient, url: str) -> Any:
    resp = await client.get(url, timeout=20.0, headers={"User-Agent": _user_agent()})
    resp.raise_for_status()
    return resp.json()


async def _load_cik_map(client: httpx.AsyncClient) -> dict[str, int]:
    global _cik_cache
    if _cik_cache is not None:
        return _cik_cache
    payload = await _get_json(client, _TICKER_URL)
    # Format: {"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}, ...}
    _cik_cache = {
        str(entry["ticker"]).upper(): int(entry["cik_str"])
        for entry in payload.values()
        if isinstance(entry, dict) and "ticker" in entry and "cik_str" in entry
    }
    return _cik_cache


async def _fetch_concept(client: httpx.AsyncClient, cik: int, concept: str) -> dict | None:
    url = _CONCEPT_URL.format(cik=cik, concept=concept)
    try:
        return await _get_json(client, url)
    except httpx.HTTPStatusError as e:
        # 404 means this filer doesn't tag under this concept — try the next one.
        if e.response.status_code == 404:
            return None
        raise


def _pick_latest_annual(payload: dict) -> AnnualRevenue | None:
    """Pick the most-recently-filed *current-year* annual revenue entry.

    Each 10-K usually reports three years of comparatives — the current fiscal
    year plus two priors. We want only the current year, identified by the
    `end` date's year matching the `fy` field.
    """
    units = payload.get("units", {}).get("USD", [])
    current_year_entries = []
    for u in units:
        if u.get("form") != "10-K" or u.get("fp") != "FY":
            continue
        end = str(u.get("end", ""))
        if len(end) < 4:
            continue
        try:
            end_year = int(end[:4])
        except ValueError:
            continue
        if end_year != u.get("fy"):
            # Skip comparative-period entries; we only want the year that
            # matches the fiscal-year label.
            continue
        current_year_entries.append(u)
    if not current_year_entries:
        return None
    latest = max(current_year_entries, key=lambda u: str(u.get("filed", "")))
    return AnnualRevenue(
        amount_usd=int(latest["val"]),
        fiscal_year=int(latest["fy"]),
        accession_number=str(latest.get("accn", "")),
    )


async def fetch_annual_revenue(ticker: str, client: httpx.AsyncClient) -> AnnualRevenue | None:
    cik_map = await _load_cik_map(client)
    cik = cik_map.get(ticker.upper())
    if cik is None:
        logger.info("ticker %s not found in EDGAR ticker map", ticker)
        return None
    for concept in _REVENUE_CONCEPTS:
        payload = await _fetch_concept(client, cik, concept)
        if not payload:
            continue
        annual = _pick_latest_annual(payload)
        if annual:
            return annual
    return None
