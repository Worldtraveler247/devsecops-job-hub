from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from devsecops_job_hub.config import settings
from devsecops_job_hub.db import engine, get_session, init_db
from devsecops_job_hub.models import (
    CareerStage,
    ClearanceLevel,
    Company,
    Job,
    RemoteEligibility,
    RoleFamily,
)
from devsecops_job_hub.seed.companies import seed_companies
from devsecops_job_hub.services.refresh import refresh_all

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)

_PKG_DIR = Path(__file__).parent
_TEMPLATES_DIR = _PKG_DIR / "templates"
_STATIC_DIR = _PKG_DIR / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    inserted = seed_companies()
    logger.info("seeded %d companies", inserted)
    yield


app = FastAPI(title="DevSecOps Job Hub", version="0.1.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")
templates = Jinja2Templates(directory=_TEMPLATES_DIR)


@app.get("/healthz")
def healthz() -> dict[str, bool]:
    return {"ok": True}


@app.get("/", response_class=HTMLResponse)
def index(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    role: list[RoleFamily] | None = Query(default=None),
    stage: CareerStage | None = None,
    clearance: ClearanceLevel | None = None,
    remote: RemoteEligibility | None = None,
    location_scope: str | None = Query(default=None, description="conus | oconus | any"),
    min_salary: int | None = None,
) -> HTMLResponse:
    stmt = select(Job, Company).join(Company).where(Job.is_active)
    if role:
        stmt = stmt.where(Job.role_family.in_(role))  # type: ignore[union-attr]
    if stage:
        stmt = stmt.where(Job.career_stage == stage)
    if clearance:
        stmt = stmt.where(Job.clearance_required == clearance)
    if remote:
        stmt = stmt.where(Job.remote_eligible == remote)
    if location_scope == "oconus":
        stmt = stmt.where(Job.is_oconus)
    elif location_scope == "conus":
        stmt = stmt.where(Job.is_oconus.is_(False))  # type: ignore[union-attr]
    if min_salary:
        stmt = stmt.where(Job.salary_min >= min_salary)  # type: ignore[operator]
    rows = session.exec(stmt).all()

    last_seen = max((j.last_seen_at for j, _ in rows), default=None)

    return templates.TemplateResponse(
        request,
        "jobs.html",
        {
            "rows": rows,
            "role_families": list(RoleFamily),
            "stages": list(CareerStage),
            "clearances": list(ClearanceLevel),
            "remotes": list(RemoteEligibility),
            "selected": {
                "role": [r.value for r in role] if role else [],
                "stage": stage.value if stage else "",
                "clearance": clearance.value if clearance else "",
                "remote": remote.value if remote else "",
                "location_scope": location_scope or "",
                "min_salary": min_salary or "",
            },
            "last_seen": last_seen,
            "total": len(rows),
        },
    )


@app.post("/admin/refresh")
async def refresh() -> JSONResponse:
    count = await refresh_all()
    return JSONResponse({"ingested": count})
