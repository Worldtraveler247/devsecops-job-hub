"""Hand-curated seed companies.

All `ats_company_slug` values verified live against the public ATS API on
2026-05-03. If a fetch starts returning 404, re-verify by hitting:
  - Greenhouse: https://boards-api.greenhouse.io/v1/boards/{slug}/jobs
  - Lever:      https://api.lever.co/v0/postings/{slug}?mode=json

Revenue figures are intentionally None — Slice 3 enriches public co's from
SEC EDGAR. Per spec honesty constraint, never fabricate.
"""

from sqlmodel import Session, select

from devsecops_job_hub.db import engine
from devsecops_job_hub.models import ATSProvider, Company


def _build_seed() -> list[Company]:
    return [
        # ── General IT aggregator (The Muse) ──
        # Fills the "regular IT" gap. Each Muse posting carries its own
        # employer (e.g. Stripe, Atlassian, MongoDB) — the actual employer
        # is appended to the job title so it's visible on the card.
        Company(
            name="The Muse — Tech Jobs",
            careers_url="https://www.themuse.com/jobs",
            ats_provider=ATSProvider.MUSE,
            ats_company_slug="muse-tech",
            primary_agencies=["civilian"],
            hq_location="(aggregator)",
        ),
        # ── Federal civilian (USAJobs Search API) ──
        # The hub's audience overlaps heavily with the GS-9 to GS-12 federal
        # IT/security pipeline. The USAJobs adapter pulls IT (2210), Security
        # Administration (0080), and Computer Science (1550) job series at
        # GS-12 or below, applied as a server-side filter.
        Company(
            name="U.S. Federal Government",
            careers_url="https://www.usajobs.gov/",
            ats_provider=ATSProvider.USAJOBS,
            ats_company_slug="federal-it",
            primary_agencies=["civilian", "DoD", "IC"],
            hq_location="Washington, DC",
        ),
        # ── Defense tech (the core audience for cleared candidates) ──
        Company(
            name="Anduril Industries",
            careers_url="https://www.anduril.com/careers/",
            ats_provider=ATSProvider.GREENHOUSE,
            ats_company_slug="andurilindustries",
            primary_agencies=["DoD"],
            hq_location="Costa Mesa, CA",
        ),
        Company(
            name="Palantir Technologies",
            ticker="PLTR",
            careers_url="https://www.palantir.com/careers/",
            ats_provider=ATSProvider.LEVER,
            ats_company_slug="palantir",
            primary_agencies=["DoD", "IC", "civilian"],
            hq_location="Denver, CO",
        ),
        Company(
            name="Scale AI",
            careers_url="https://scale.com/careers",
            ats_provider=ATSProvider.GREENHOUSE,
            ats_company_slug="scaleai",
            primary_agencies=["DoD"],
            hq_location="San Francisco, CA",
        ),
        Company(
            name="Applied Intuition",
            careers_url="https://www.appliedintuition.com/careers",
            ats_provider=ATSProvider.GREENHOUSE,
            ats_company_slug="appliedintuition",
            primary_agencies=["DoD"],
            hq_location="Mountain View, CA",
        ),
        Company(
            name="Two Six Technologies",
            careers_url="https://twosixtech.com/careers/",
            ats_provider=ATSProvider.GREENHOUSE,
            ats_company_slug="twosixtechnologies",
            primary_agencies=["DoD", "IC"],
            hq_location="Arlington, VA",
        ),
        Company(
            name="Vannevar Labs",
            careers_url="https://www.vannevarlabs.com/careers",
            ats_provider=ATSProvider.GREENHOUSE,
            ats_company_slug="vannevarlabs",
            primary_agencies=["DoD", "IC"],
            hq_location="Arlington, VA",
        ),
        Company(
            name="Govini",
            careers_url="https://www.govini.com/careers/",
            ats_provider=ATSProvider.GREENHOUSE,
            ats_company_slug="govini",
            primary_agencies=["DoD"],
            hq_location="Arlington, VA",
        ),
        Company(
            name="Shift5",
            careers_url="https://shift5.io/careers/",
            ats_provider=ATSProvider.GREENHOUSE,
            ats_company_slug="shift5",
            primary_agencies=["DoD"],
            hq_location="Rosslyn, VA",
        ),
        Company(
            name="Rebellion Defense",
            careers_url="https://rebelliondefense.com/careers",
            ats_provider=ATSProvider.GREENHOUSE,
            ats_company_slug="rebelliondefense",
            primary_agencies=["DoD", "IC"],
            hq_location="Washington, DC",
        ),
        Company(
            name="Shield AI",
            careers_url="https://shield.ai/careers",
            ats_provider=ATSProvider.LEVER,
            ats_company_slug="shieldai",
            primary_agencies=["DoD"],
            hq_location="San Diego, CA",
        ),
        Company(
            name="Saildrone",
            careers_url="https://www.saildrone.com/careers",
            ats_provider=ATSProvider.GREENHOUSE,
            ats_company_slug="saildroneinc",
            primary_agencies=["DoD", "NOAA"],
            hq_location="Alameda, CA",
        ),
        Company(
            name="Epirus",
            careers_url="https://www.epirusinc.com/careers",
            ats_provider=ATSProvider.GREENHOUSE,
            ats_company_slug="epirus",
            primary_agencies=["DoD"],
            hq_location="Torrance, CA",
        ),
        Company(
            name="Sayari",
            careers_url="https://sayari.com/careers/",
            ats_provider=ATSProvider.GREENHOUSE,
            ats_company_slug="sayari",
            primary_agencies=["IC", "civilian"],
            hq_location="Washington, DC",
        ),
        # ── DevSecOps tooling vendors with significant govt business ──
        Company(
            name="Chainguard",
            careers_url="https://www.chainguard.dev/careers",
            ats_provider=ATSProvider.GREENHOUSE,
            ats_company_slug="chainguard",
            primary_agencies=["DoD", "civilian"],
            hq_location="Kirkland, WA",
        ),
        Company(
            name="Wiz",
            careers_url="https://www.wiz.io/careers",
            ats_provider=ATSProvider.GREENHOUSE,
            ats_company_slug="wizinc",
            primary_agencies=["civilian", "DoD"],
            hq_location="New York, NY",
        ),
        # ── Cloud + observability vendors with FedRAMP / DoD presence ──
        Company(
            name="Datadog",
            ticker="DDOG",
            careers_url="https://careers.datadoghq.com/",
            ats_provider=ATSProvider.GREENHOUSE,
            ats_company_slug="datadog",
            primary_agencies=["civilian", "DoD"],
            hq_location="New York, NY",
        ),
        Company(
            name="Cloudflare",
            ticker="NET",
            careers_url="https://www.cloudflare.com/careers/",
            ats_provider=ATSProvider.GREENHOUSE,
            ats_company_slug="cloudflare",
            primary_agencies=["civilian", "DoD"],
            hq_location="San Francisco, CA",
        ),
        Company(
            name="Databricks",
            careers_url="https://www.databricks.com/company/careers",
            ats_provider=ATSProvider.GREENHOUSE,
            ats_company_slug="databricks",
            primary_agencies=["civilian", "DoD"],
            hq_location="San Francisco, CA",
        ),
        Company(
            name="Elastic",
            ticker="ESTC",
            careers_url="https://www.elastic.co/careers",
            ats_provider=ATSProvider.GREENHOUSE,
            ats_company_slug="elastic",
            primary_agencies=["civilian", "DoD", "IC"],
            hq_location="Mountain View, CA",
        ),
        Company(
            name="Zscaler",
            ticker="ZS",
            careers_url="https://www.zscaler.com/careers",
            ats_provider=ATSProvider.GREENHOUSE,
            ats_company_slug="zscaler",
            primary_agencies=["civilian", "DoD"],
            hq_location="San Jose, CA",
        ),
    ]


def seed_companies() -> int:
    """Insert seed companies that don't already exist. Idempotent."""
    inserted = 0
    with Session(engine) as session:
        for c in _build_seed():
            stmt = select(Company).where(Company.name == c.name)
            if session.exec(stmt).first() is None:
                session.add(c)
                inserted += 1
        session.commit()
    return inserted
