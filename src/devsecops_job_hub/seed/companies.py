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
        # ── DevSecOps tooling vendors with significant govt business ──
        Company(
            name="Chainguard",
            careers_url="https://www.chainguard.dev/careers",
            ats_provider=ATSProvider.GREENHOUSE,
            ats_company_slug="chainguard",
            primary_agencies=["DoD", "civilian"],
            hq_location="Kirkland, WA",
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
