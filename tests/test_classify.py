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
        assert (
            classify_role_family("Information Systems Security Officer (ISSO)")
            == RoleFamily.SECURITY_OFFICER
        )

    def test_issm(self):
        assert (
            classify_role_family("Information Systems Security Manager")
            == RoleFamily.SECURITY_OFFICER
        )

    def test_csso(self):
        assert (
            classify_role_family("Contractor Special Security Officer")
            == RoleFamily.SECURITY_OFFICER
        )

    def test_cybersecurity_engineer(self):
        assert classify_role_family("Cybersecurity Engineer") == RoleFamily.SYS_SECURITY_ENG

    def test_generic_software_engineer_catch_all(self):
        # Lands in the catch-all so Muse / generic IT sources surface.
        assert classify_role_family("Software Engineer") == RoleFamily.SOFTWARE_ENGINEER
        assert classify_role_family("Senior Software Developer") == RoleFamily.SOFTWARE_ENGINEER
        assert classify_role_family("Backend Engineer, Payments") == RoleFamily.SOFTWARE_ENGINEER
        assert classify_role_family("Full-Stack Engineer") == RoleFamily.SOFTWARE_ENGINEER
        assert classify_role_family("Data Engineer") == RoleFamily.SOFTWARE_ENGINEER
        assert classify_role_family("ML Engineer") == RoleFamily.SOFTWARE_ENGINEER

    def test_specific_role_wins_over_software_engineer(self):
        # The catch-all must lose to specialized matchers.
        assert classify_role_family("DevSecOps Software Engineer") == RoleFamily.DEVSECOPS_ENG
        assert (
            classify_role_family("Cloud Security Software Engineer")
            == RoleFamily.CLOUD_SECURITY_ENG
        )

    def test_role_falls_back_to_description(self):
        # Title says "Engineer" — vague — but description names the role family.
        assert (
            classify_role_family(
                "Engineer, Platform",
                "You'll lead our DevSecOps program covering CI/CD, supply-chain security, and SBOM tooling.",
            )
            == RoleFamily.DEVSECOPS_ENG
        )

    def test_title_role_wins_over_description(self):
        # If title clearly classifies, ignore description.
        assert (
            classify_role_family(
                "Application Security Engineer",
                "You'll partner with the SRE team on incident response.",
            )
            == RoleFamily.APPSEC_ENG
        )


class TestCareerStage:
    def test_senior(self):
        assert classify_career_stage("Senior Security Engineer") == CareerStage.SENIOR

    def test_junior(self):
        assert classify_career_stage("Junior Linux Administrator") == CareerStage.ENTRY

    def test_no_signal(self):
        assert classify_career_stage("Cloud Engineer") is None

    def test_principal_is_senior(self):
        assert classify_career_stage("Principal Engineer, Cloud") == CareerStage.SENIOR

    def test_director_is_senior(self):
        assert classify_career_stage("Director of Security Engineering") == CareerStage.SENIOR

    def test_architect_is_senior(self):
        assert classify_career_stage("Cloud Security Architect") == CareerStage.SENIOR

    def test_skillbridge_in_title(self):
        assert classify_career_stage("SkillBridge Cloud Intern") == CareerStage.ENTRY

    def test_apprentice(self):
        assert classify_career_stage("DevOps Apprentice") == CareerStage.ENTRY

    def test_description_8_years_is_senior(self):
        assert (
            classify_career_stage(
                "Cloud Engineer", "Requires 8+ years of experience in production systems."
            )
            == CareerStage.SENIOR
        )

    def test_description_minimum_seven_years_is_senior(self):
        assert (
            classify_career_stage("Software Engineer", "Minimum 7 years of experience required.")
            == CareerStage.SENIOR
        )

    def test_description_skillbridge_is_entry(self):
        assert (
            classify_career_stage(
                "Cloud Engineer", "Open to SkillBridge fellows transitioning from active duty."
            )
            == CareerStage.ENTRY
        )

    def test_description_veteran_friendly_is_entry(self):
        assert (
            classify_career_stage(
                "Cloud Engineer", "Veterans are encouraged to apply. No prior experience required."
            )
            == CareerStage.ENTRY
        )

    def test_description_three_years_is_mid(self):
        assert (
            classify_career_stage(
                "Cloud Engineer", "We're looking for someone with 3+ years of experience."
            )
            == CareerStage.MID
        )

    def test_title_senior_overrides_entry_in_description(self):
        # Boilerplate "veterans encouraged" shouldn't override a clear senior title.
        assert (
            classify_career_stage(
                "Senior Cloud Engineer",
                "Veterans are encouraged to apply.",
            )
            == CareerStage.SENIOR
        )


class TestClearance:
    def test_ts_sci_poly(self):
        assert classify_clearance("Engineer - TS/SCI with Poly") == ClearanceLevel.TS_SCI_POLY

    def test_ts_sci(self):
        assert classify_clearance("Engineer - TS/SCI Required") == ClearanceLevel.TS_SCI

    def test_secret(self):
        assert classify_clearance("DevSecOps - Active Secret") == ClearanceLevel.SECRET

    def test_no_clearance(self):
        assert classify_clearance("Software Engineer") == ClearanceLevel.NONE

    def test_clearance_in_description(self):
        assert (
            classify_clearance("Cloud Engineer", "Active Secret clearance required at start date.")
            == ClearanceLevel.SECRET
        )


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
