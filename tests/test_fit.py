"""Unit tests for the fit-scoring service. Pure-function logic, no DB or HTTP."""

from __future__ import annotations

import pytest

from devsecops_job_hub.models import (
    CareerStage,
    ClearanceLevel,
    Job,
    RemoteEligibility,
    RoleFamily,
    SalarySource,
)
from devsecops_job_hub.services.fit import FitProfile, compute_fit


def _job(**overrides) -> Job:
    base: dict = {
        "company_id": 1,
        "title": "Test job",
        "role_family": RoleFamily.CLOUD_SECURITY_ENG,
        "career_stage": CareerStage.MID,
        "clearance_required": ClearanceLevel.NONE,
        "remote_eligible": RemoteEligibility.REMOTE,
        "salary_source": SalarySource.UNKNOWN,
        "apply_url": "https://example.com/apply",
        "is_oconus": False,
    }
    base.update(overrides)
    return Job(**base)


@pytest.fixture
def junior_cloud_sec_profile() -> FitProfile:
    return FitProfile(
        role_families=frozenset(
            {RoleFamily.CLOUD_SECURITY_ENG, RoleFamily.DEVSECOPS_ENG, RoleFamily.LINUX_ADMIN}
        ),
        career_stages=frozenset({CareerStage.ENTRY, CareerStage.MID}),
        max_clearance=ClearanceLevel.SECRET,
        remote_only=False,
        allow_oconus=False,
    )


def test_matching_role_family_is_fit(junior_cloud_sec_profile):
    verdict = compute_fit(_job(), junior_cloud_sec_profile)
    assert verdict.is_fit is True
    assert verdict.score >= 2  # role family alone = 2 points
    assert any("role:" in r for r in verdict.reasons)


def test_off_target_role_is_not_fit(junior_cloud_sec_profile):
    verdict = compute_fit(_job(role_family=RoleFamily.SOC_ANALYST), junior_cloud_sec_profile)
    assert verdict.is_fit is False


def test_clearance_above_ceiling_hard_fails(junior_cloud_sec_profile):
    verdict = compute_fit(
        _job(clearance_required=ClearanceLevel.TS_SCI_POLY), junior_cloud_sec_profile
    )
    assert verdict.is_fit is False
    assert verdict.score == 0
    assert "exceeds ceiling" in verdict.reasons[0]


def test_clearance_at_ceiling_passes(junior_cloud_sec_profile):
    verdict = compute_fit(
        _job(clearance_required=ClearanceLevel.SECRET), junior_cloud_sec_profile
    )
    assert verdict.is_fit is True


def test_oconus_hard_fails_when_disallowed(junior_cloud_sec_profile):
    verdict = compute_fit(_job(is_oconus=True, country="Japan"), junior_cloud_sec_profile)
    assert verdict.is_fit is False
    assert verdict.reasons == ["OCONUS"]


def test_oconus_passes_when_allowed():
    profile = FitProfile(
        role_families=frozenset({RoleFamily.CLOUD_SECURITY_ENG}),
        career_stages=frozenset({CareerStage.MID}),
        max_clearance=ClearanceLevel.SECRET,
        remote_only=False,
        allow_oconus=True,
    )
    verdict = compute_fit(_job(is_oconus=True, country="Japan"), profile)
    assert verdict.is_fit is True


def test_remote_only_hard_fails_for_onsite():
    profile = FitProfile(
        role_families=frozenset({RoleFamily.CLOUD_SECURITY_ENG}),
        career_stages=frozenset({CareerStage.MID}),
        max_clearance=ClearanceLevel.SECRET,
        remote_only=True,
        allow_oconus=False,
    )
    verdict = compute_fit(_job(remote_eligible=RemoteEligibility.ONSITE), profile)
    assert verdict.is_fit is False
    assert verdict.reasons == ["not remote"]


def test_unclassified_role_is_not_fit(junior_cloud_sec_profile):
    verdict = compute_fit(_job(role_family=None), junior_cloud_sec_profile)
    assert verdict.is_fit is False
    assert "unclassified" in verdict.reasons[0]


def test_score_accumulates_role_stage_remote(junior_cloud_sec_profile):
    # Match role (+2), match stage (+1), match remote-flex (+1) → 4
    verdict = compute_fit(_job(), junior_cloud_sec_profile)
    assert verdict.score == 4
    assert len(verdict.reasons) == 3


def test_off_stage_still_fit_if_role_matches(junior_cloud_sec_profile):
    # Senior posting, but role family matches → still a fit (stage is a bonus, not a gate)
    verdict = compute_fit(_job(career_stage=CareerStage.SENIOR), junior_cloud_sec_profile)
    assert verdict.is_fit is True
    assert verdict.score == 3  # role(+2) + remote(+1), stage didn't match
