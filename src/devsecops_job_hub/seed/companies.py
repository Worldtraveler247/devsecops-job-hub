"""Hand-curated seed companies for Slice 1.

Each entry's `ats_company_slug` was verified against the public Greenhouse API
on 2026-05-03. Slugs change occasionally — if a fetch starts returning 404,
re-verify by hitting https://boards-api.greenhouse.io/v1/boards/{slug}/jobs
in a browser.

Revenue figures are intentionally None — Slice 3 will enrich from SEC EDGAR
(public co's) or mark ESTIMATED. Per spec honesty constraint, never fabricate.
"""

from sqlmodel import Session, select

from devsecops_job_hub.db import engine
from devsecops_job_hub.models import ATSProvider, Company

def _build_seed() -> list[Company]:
    """Rebuild fresh Company instances each call so they aren't detached
    from a prior session (which would raise on attribute access).
    """
    return [
        Company(
            name="Anduril Industries",
            ticker=None,
            careers_url="https://www.anduril.com/careers/",
            ats_provider=ATSProvider.GREENHOUSE,
            ats_company_slug="andurilindustries",
            primary_agencies=["DoD"],
            hq_location="Costa Mesa, CA",
        ),
        Company(
            name="Chainguard",
            ticker=None,
            careers_url="https://www.chainguard.dev/careers",
            ats_provider=ATSProvider.GREENHOUSE,
            ats_company_slug="chainguard",
            primary_agencies=["DoD", "civilian"],
            hq_location="Kirkland, WA",
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
