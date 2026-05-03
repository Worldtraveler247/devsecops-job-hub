from devsecops_job_hub.classify import (
    classify_career_stage,
    classify_clearance,
    classify_country,
    classify_oconus,
    classify_remote,
    classify_role_family,
)
from devsecops_job_hub.models import CareerStage, ClearanceLevel, RemoteEligibility, RoleFamily


class TestRoleFamily:
    def test_devsecops_match(self):
        assert classify_role_family("Senior DevSecOps Engineer") == RoleFamily.DEVSECOPS_ENG

    def test_appsec_match(self):
        assert classify_role_family("Application Security Engineer") == RoleFamily.APPSEC_ENG

    def test_cloud_security_takes_precedence_over_devops(self):
        assert classify_role_family("Cloud Security Engineer II") == RoleFamily.CLOUD_SECURITY_ENG

    def test_sre(self):
        assert classify_role_family("Site Reliability Engineer") == RoleFamily.SRE

    def test_unknown_returns_none(self):
        assert classify_role_family("Sales Account Executive") is None

    def test_isso(self):
        assert classify_role_family("Information Systems Security Officer (ISSO)") == RoleFamily.SECURITY_OFFICER

    def test_issm(self):
        assert classify_role_family("Information Systems Security Manager") == RoleFamily.SECURITY_OFFICER

    def test_csso(self):
        assert classify_role_family("Contractor Special Security Officer") == RoleFamily.SECURITY_OFFICER

    def test_cybersecurity_engineer(self):
        assert classify_role_family("Cybersecurity Engineer") == RoleFamily.SYS_SECURITY_ENG


class TestCareerStage:
    def test_senior(self):
        assert classify_career_stage("Senior Security Engineer") == CareerStage.SENIOR

    def test_junior(self):
        assert classify_career_stage("Junior Linux Administrator") == CareerStage.ENTRY

    def test_no_signal(self):
        assert classify_career_stage("Cloud Engineer") is None


class TestClearance:
    def test_ts_sci_poly(self):
        assert classify_clearance("Engineer - TS/SCI with Poly") == ClearanceLevel.TS_SCI_POLY

    def test_ts_sci(self):
        assert classify_clearance("Engineer - TS/SCI Required") == ClearanceLevel.TS_SCI

    def test_secret(self):
        assert classify_clearance("DevSecOps - Active Secret") == ClearanceLevel.SECRET

    def test_no_clearance(self):
        assert classify_clearance("Software Engineer") == ClearanceLevel.NONE


class TestRemote:
    def test_remote(self):
        assert classify_remote("Remote - United States") == RemoteEligibility.REMOTE

    def test_hybrid(self):
        assert classify_remote("Hybrid - Reston, VA") == RemoteEligibility.HYBRID

    def test_onsite_default(self):
        assert classify_remote("Costa Mesa, CA") == RemoteEligibility.ONSITE

    def test_none_is_onsite(self):
        assert classify_remote(None) == RemoteEligibility.ONSITE


class TestOconus:
    # Eddie's audience cares about OCONUS — Aomori, Bahrain, Ramstein, Al Udeid.
    # These tests guarantee those don't get filtered out.

    def test_japan_city(self):
        assert classify_oconus("Aomori, Japan") is True
        assert classify_country("Aomori, Japan") == "Japan"

    def test_japan_base_only(self):
        assert classify_oconus("Misawa Air Base") is True
        assert classify_country("Misawa Air Base") == "Japan"

    def test_qatar_base(self):
        assert classify_oconus("Al Udeid Air Base") is True
        assert classify_country("Al Udeid Air Base") == "Qatar"

    def test_germany_base(self):
        assert classify_oconus("Ramstein Air Base, Germany") is True

    def test_apac_marker(self):
        assert classify_oconus("APAC - Hub") is True

    def test_emea_marker(self):
        assert classify_oconus("EMEA region") is True

    def test_us_state_is_not_oconus(self):
        assert classify_oconus("Costa Mesa, CA") is False
        assert classify_oconus("Reston, VA") is False
        assert classify_oconus("Washington, DC") is False
        assert classify_country("Costa Mesa, CA") is None

    def test_remote_us_is_not_oconus(self):
        assert classify_oconus("Remote - United States") is False

    def test_none_is_not_oconus(self):
        assert classify_oconus(None) is False
        assert classify_country(None) is None
