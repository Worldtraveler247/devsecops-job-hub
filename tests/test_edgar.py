"""Unit tests for the EDGAR client. Uses httpx.MockTransport for the parsing
paths and a vcrpy cassette for one live-API integration check.
"""

from __future__ import annotations

import httpx
import pytest

from devsecops_job_hub.services import edgar


@pytest.fixture(autouse=True)
def reset_cik_cache():
    """Cache is module-level; clear it between tests so each test sees a
    fresh mocked load."""
    edgar._cik_cache = None
    yield
    edgar._cik_cache = None


_TICKER_PAYLOAD = {
    "0": {"cik_str": 1321655, "ticker": "PLTR", "title": "Palantir Technologies Inc."},
    "1": {"cik_str": 1561550, "ticker": "DDOG", "title": "Datadog, Inc."},
}


def _concept_payload_three_year() -> dict:
    """Mimic the SEC shape: a 10-K reports current FY plus two comparatives."""
    return {
        "cik": 1321655,
        "taxonomy": "us-gaap",
        "tag": "RevenueFromContractWithCustomerExcludingAssessedTax",
        "label": "Revenues",
        "units": {
            "USD": [
                # Current 10-K filing — three comparative years.
                {
                    "end": "2023-12-31",
                    "fy": 2025,
                    "fp": "FY",
                    "form": "10-K",
                    "filed": "2026-02-17",
                    "val": 2_230_000_000,
                    "accn": "0001321655-26-000011",
                },
                {
                    "end": "2024-12-31",
                    "fy": 2025,
                    "fp": "FY",
                    "form": "10-K",
                    "filed": "2026-02-17",
                    "val": 2_870_000_000,
                    "accn": "0001321655-26-000011",
                },
                {
                    "end": "2025-12-31",
                    "fy": 2025,
                    "fp": "FY",
                    "form": "10-K",
                    "filed": "2026-02-17",
                    "val": 4_480_000_000,
                    "accn": "0001321655-26-000011",
                },
                # Older 10-K filing.
                {
                    "end": "2024-12-31",
                    "fy": 2024,
                    "fp": "FY",
                    "form": "10-K",
                    "filed": "2025-02-18",
                    "val": 2_870_000_000,
                    "accn": "0001321655-25-000022",
                },
                # Quarterly entry — must be ignored.
                {
                    "end": "2025-09-30",
                    "fy": 2025,
                    "fp": "Q3",
                    "form": "10-Q",
                    "filed": "2025-10-30",
                    "val": 1_100_000_000,
                    "accn": "irrelevant",
                },
            ]
        },
    }


def _make_handler(concept_payload: dict | None = None, ticker_payload: dict = _TICKER_PAYLOAD):
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "company_tickers.json" in url:
            return httpx.Response(200, json=ticker_payload)
        if "companyconcept" in url:
            if concept_payload is None:
                return httpx.Response(404)
            return httpx.Response(200, json=concept_payload)
        return httpx.Response(404)

    return handler


class TestPickLatestAnnual:
    def test_picks_current_year_from_latest_filing(self):
        result = edgar._pick_latest_annual(_concept_payload_three_year())
        assert result is not None
        assert result.fiscal_year == 2025
        assert result.amount_usd == 4_480_000_000
        assert result.accession_number == "0001321655-26-000011"

    def test_returns_none_when_no_annual_entries(self):
        payload = {"units": {"USD": [{"form": "10-Q", "fp": "Q3"}]}}
        assert edgar._pick_latest_annual(payload) is None

    def test_returns_none_when_no_units(self):
        assert edgar._pick_latest_annual({"units": {}}) is None
        assert edgar._pick_latest_annual({}) is None

    def test_skips_comparative_entries_in_latest_filing(self):
        # All three entries from latest filing have the same fy=2025; only one
        # has end-year matching fy. We must pick that one.
        result = edgar._pick_latest_annual(_concept_payload_three_year())
        # 2025 end => $4.48B current year, not $2.23B (2023) or $2.87B (2024).
        assert result.amount_usd == 4_480_000_000


class TestFetchAnnualRevenue:
    @pytest.mark.asyncio
    async def test_fetches_revenue_for_known_ticker(self):
        transport = httpx.MockTransport(_make_handler(_concept_payload_three_year()))
        async with httpx.AsyncClient(transport=transport) as client:
            result = await edgar.fetch_annual_revenue("PLTR", client)
        assert result is not None
        assert result.amount_usd == 4_480_000_000
        assert result.fiscal_year == 2025

    @pytest.mark.asyncio
    async def test_unknown_ticker_returns_none(self):
        transport = httpx.MockTransport(_make_handler(_concept_payload_three_year()))
        async with httpx.AsyncClient(transport=transport) as client:
            assert await edgar.fetch_annual_revenue("NOTREAL", client) is None

    @pytest.mark.asyncio
    async def test_falls_through_to_next_concept_on_404(self):
        # First concept 404s; second concept returns the data.
        responses = iter([
            httpx.Response(200, json=_TICKER_PAYLOAD),
            httpx.Response(404),  # RevenueFromContractWithCustomerExcludingAssessedTax
            httpx.Response(200, json=_concept_payload_three_year()),  # Revenues
        ])

        def handler(request: httpx.Request) -> httpx.Response:
            return next(responses)

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            result = await edgar.fetch_annual_revenue("PLTR", client)
        assert result is not None
        assert result.amount_usd == 4_480_000_000


@pytest.mark.vcr
@pytest.mark.asyncio
async def test_fetch_palantir_revenue_against_real_api():
    """Live integration check against SEC EDGAR. Replays from cassette on
    re-runs; re-record with `--record-mode=rewrite` if SEC drops/renames the
    concept."""
    async with httpx.AsyncClient() as client:
        result = await edgar.fetch_annual_revenue("PLTR", client)

    assert result is not None
    # Loose assertions — the actual value drifts as PLTR files new 10-Ks.
    # Floor: $1B (Palantir crossed that in 2021 and won't go below).
    # Ceiling: $50B (sanity bound; if PLTR reports more we have bigger
    # things to celebrate than test breakage).
    assert 1_000_000_000 < result.amount_usd < 50_000_000_000
    assert result.fiscal_year >= 2023
    assert result.accession_number  # non-empty
