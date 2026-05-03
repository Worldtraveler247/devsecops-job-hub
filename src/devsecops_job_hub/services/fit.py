"""Compute whether a Job matches the user's "fit profile".

Pure functions, no I/O. The profile is built from settings (env-driven), and
the compute_fit verdict is rendered as a star badge in the UI plus the
optional `fit_only=true` filter on the index route.

Design notes:
- This is heuristic, not predictive. We're not trying to guess Eddie's chances
  of getting hired — we're surfacing postings that obviously match his current
  target shape (role family, stage, clearance ceiling, remote/onsite, CONUS).
- All checks are explainable: the verdict carries `reasons` so the UI can
  show *why* a posting was flagged, and the user can sanity-check.
- "Hard fail" rules (clearance ceiling, OCONUS exclusion, remote-only) make
  is_fit immediately False even if other dimensions match. Ranked clearance
  prevents "Cloud Security Engineer (TS/SCI w/ Poly)" from being flagged for
  someone with no current clearance.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from devsecops_job_hub.config import Settings
from devsecops_job_hub.models import (
    CareerStage,
    ClearanceLevel,
    Job,
    RemoteEligibility,
    RoleFamily,
)

# Lower rank = lower trust level. A profile with max_clearance=SECRET (rank 2)
# accepts jobs requiring NONE/PUBLIC_TRUST/SECRET, but not TOP_SECRET+.
_CLEARANCE_RANK: dict[ClearanceLevel, int] = {
    ClearanceLevel.NONE: 0,
    ClearanceLevel.PUBLIC_TRUST: 1,
    ClearanceLevel.SECRET: 2,
    ClearanceLevel.TOP_SECRET: 3,
    ClearanceLevel.TS_SCI: 4,
    ClearanceLevel.TS_SCI_POLY: 5,
}


@dataclass(frozen=True)
class FitProfile:
    role_families: frozenset[RoleFamily]
    career_stages: frozenset[CareerStage]
    max_clearance: ClearanceLevel
    remote_only: bool
    allow_oconus: bool


@dataclass(frozen=True)
class FitVerdict:
    is_fit: bool
    score: int
    reasons: list[str] = field(default_factory=list)


def profile_from_settings(settings: Settings) -> FitProfile:
    return FitProfile(
        role_families=frozenset(RoleFamily(v) for v in settings.fit_role_families),
        career_stages=frozenset(CareerStage(v) for v in settings.fit_career_stages),
        max_clearance=ClearanceLevel(settings.fit_max_clearance),
        remote_only=settings.fit_remote_only,
        allow_oconus=settings.fit_allow_oconus,
    )


def compute_fit(job: Job, profile: FitProfile) -> FitVerdict:
    reasons: list[str] = []

    # ── Hard fails (any one short-circuits to is_fit=False) ──
    job_rank = _CLEARANCE_RANK[job.clearance_required]
    max_rank = _CLEARANCE_RANK[profile.max_clearance]
    if job_rank > max_rank:
        return FitVerdict(False, 0, [f"clearance {job.clearance_required.value} exceeds ceiling"])

    if not profile.allow_oconus and job.is_oconus:
        return FitVerdict(False, 0, ["OCONUS"])

    if profile.remote_only and job.remote_eligible not in {
        RemoteEligibility.REMOTE,
        RemoteEligibility.REMOTE_CLEARED_FACILITY,
    }:
        return FitVerdict(False, 0, ["not remote"])

    # Unclassified postings can't be scored — they fail silently rather than
    # showing up as fits with no reasoning.
    if job.role_family is None:
        return FitVerdict(False, 0, ["unclassified role"])

    # ── Soft signals (each adds to score) ──
    score = 0
    if job.role_family in profile.role_families:
        score += 2
        reasons.append(f"role: {job.role_family.value.replace('_', ' ')}")

    if job.career_stage is not None and job.career_stage in profile.career_stages:
        score += 1
        reasons.append(f"stage: {job.career_stage.value}")

    if job.remote_eligible in {RemoteEligibility.REMOTE, RemoteEligibility.HYBRID}:
        score += 1
        reasons.append(f"flex: {job.remote_eligible.value.replace('_', ' ')}")

    # is_fit threshold: must at least match the role family. Stage/remote are
    # bonuses on top — they don't carry a posting alone.
    is_fit = job.role_family in profile.role_families
    return FitVerdict(is_fit, score, reasons)
