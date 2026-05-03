"""Heuristic classifiers that map a free-text job title (and location) to our enums.

These are deliberately simple keyword rules. They will miss things — the goal is
"useful by default, easy to override" rather than perfect accuracy. v2 can swap
in embeddings or an LLM-based labeler.
"""

from __future__ import annotations

import re

from devsecops_job_hub.models import CareerStage, ClearanceLevel, RemoteEligibility, RoleFamily

_ROLE_RULES: list[tuple[re.Pattern[str], RoleFamily]] = [
    # Most specific first.
    (re.compile(r"\bdevsecops\b", re.I), RoleFamily.DEVSECOPS_ENG),
    (
        re.compile(r"\bappsec\b|\bapplication security\b|\bproduct security\b", re.I),
        RoleFamily.APPSEC_ENG,
    ),
    (re.compile(r"\bcloud security\b", re.I), RoleFamily.CLOUD_SECURITY_ENG),
    # Govcon security-officer titles — Eddie's pivot point. ISSO, ISSM, SSO, CSSO, FSO.
    (
        re.compile(
            r"\b(isso|issm|csso|fso|sso)\b|"
            r"\b(information systems? security (officer|manager))\b|"
            r"\b((contractor )?special security officer)\b|"
            r"\b(facility security officer)\b",
            re.I,
        ),
        RoleFamily.SECURITY_OFFICER,
    ),
    (re.compile(r"\bdevops\b", re.I), RoleFamily.DEVOPS_ENG),
    (re.compile(r"\bsre\b|\bsite reliability\b", re.I), RoleFamily.SRE),
    (re.compile(r"\bsoc analyst\b|\bsecurity operations center\b", re.I), RoleFamily.SOC_ANALYST),
    (re.compile(r"\bcloud engineer\b|\bcloud platform\b", re.I), RoleFamily.CLOUD_ENGINEER),
    (re.compile(r"\bcloud (ops|operations)\b", re.I), RoleFamily.CLOUD_OPS),
    (re.compile(r"\bcloud (admin|administrator)\b", re.I), RoleFamily.CLOUD_ADMIN),
    (
        re.compile(r"\bsecurity engineer.*(infra|platform|infrastructure)\b", re.I),
        RoleFamily.SECURITY_ENG_INFRA,
    ),
    # Generic systems-security-engineer / cybersecurity-engineer fall-through.
    (
        re.compile(
            r"\b(systems?|system) security\b|\bcybersecurity engineer\b|\benterprise security engineering\b",
            re.I,
        ),
        RoleFamily.SYS_SECURITY_ENG,
    ),
    (re.compile(r"\blinux\b.*\b(admin\w*|engineer\w*|sysadmin)\b", re.I), RoleFamily.LINUX_ADMIN),
]

_ENTRY_HINTS = re.compile(
    r"\b(junior|jr\.?|entry[- ]level|associate|intern|apprentice|new grad|early career|"
    r"skillbridge|returnship|rotational program|i{1,3}\b)\b",
    re.I,
)
_SENIOR_HINTS = re.compile(
    r"\b(senior|sr\.?|lead|principal|staff|manager|director|head of|"
    r"vice president|vp\b|chief|architect)\b",
    re.I,
)
_MID_HINTS = re.compile(r"\b(mid[- ]level|ii)\b", re.I)

# Description-only signals (lower-confidence, only used if title is silent).
# 6+ years experience → senior territory. Match "6+ years", "minimum 7 years",
# "8 to 10 years", etc.
_SENIOR_DESC = re.compile(
    r"\b("
    r"(?:[6-9]|1[0-9])\+?\s*(?:to|-)?\s*\d*\s*(?:years?|yrs?)\s+(?:of\s+)?(?:experience|exp\.?)|"
    r"minimum\s+(?:of\s+)?(?:[6-9]|1[0-9])\s*(?:years?|yrs?)|"
    r"at\s+least\s+(?:[6-9]|1[0-9])\s*(?:years?|yrs?)"
    r")\b",
    re.I,
)
_ENTRY_DESC = re.compile(
    r"\b("
    r"no (?:prior )?experience required|"
    r"recent (?:graduate|grad)|"
    r"new grad(?:uate)?s?|"
    r"early[- ]career|"
    r"transitioning (?:service members?|veterans?|military)|"
    r"skillbridge|"
    r"veterans? (?:are )?encouraged|"
    r"clearance sponsorship (?:available|provided)|"
    r"will sponsor clearance|"
    r"0[- ]?2\s*(?:years?|yrs?)|"
    r"1[- ]?3\s*(?:years?|yrs?)\s+(?:of\s+)?(?:experience|exp\.?)"
    r")\b",
    re.I,
)
# Mid-level description signals: "3+ years", "3-5 years", etc.
_MID_DESC = re.compile(
    r"\b((?:[2-5])\+?\s*(?:to|-)?\s*\d*\s*(?:years?|yrs?)\s+(?:of\s+)?(?:experience|exp\.?))\b",
    re.I,
)


def classify_role_family(title: str, description: str | None = None) -> RoleFamily | None:
    for pattern, family in _ROLE_RULES:
        if pattern.search(title):
            return family
    # Fall back to description scan if title was silent. Description matches are
    # weaker — we only accept them for the most distinctive role families.
    if description:
        for pattern, family in _ROLE_RULES:
            if pattern.search(description):
                return family
    return None


def classify_career_stage(title: str, description: str | None = None) -> CareerStage | None:
    # Title is the strongest signal — "Senior Cloud Engineer" is unambiguous.
    if _SENIOR_HINTS.search(title):
        return CareerStage.SENIOR
    if _ENTRY_HINTS.search(title):
        return CareerStage.ENTRY
    if _MID_HINTS.search(title):
        return CareerStage.MID
    # Description fall-through. Senior signals win on conflict because
    # "8+ years required" overrides any "early career welcome" boilerplate.
    if description:
        if _SENIOR_DESC.search(description):
            return CareerStage.SENIOR
        if _ENTRY_DESC.search(description):
            return CareerStage.ENTRY
        if _MID_DESC.search(description):
            return CareerStage.MID
    return None


def classify_clearance(text: str, description: str | None = None) -> ClearanceLevel:
    t = (text + " " + (description or "")).lower()
    if "ts/sci" in t or "ts sci" in t or "tssci" in t:
        if "poly" in t:
            return ClearanceLevel.TS_SCI_POLY
        return ClearanceLevel.TS_SCI
    if "top secret" in t or re.search(r"\bts\b", t):
        return ClearanceLevel.TOP_SECRET
    if "secret" in t:
        return ClearanceLevel.SECRET
    if "public trust" in t:
        return ClearanceLevel.PUBLIC_TRUST
    return ClearanceLevel.NONE


def classify_remote(location: str | None) -> RemoteEligibility:
    if not location:
        return RemoteEligibility.ONSITE
    loc = location.lower()
    if "remote" in loc:
        return RemoteEligibility.REMOTE
    if "hybrid" in loc:
        return RemoteEligibility.HYBRID
    return RemoteEligibility.ONSITE


# Cleared candidates (Eddie's audience) often *want* OCONUS roles — Aomori,
# Bahrain, Al Udeid, Ramstein, Vicenza, etc. Don't filter them out; surface them.
# Heuristic: if the location matches any of these markers, flag as OCONUS.
_OCONUS_COUNTRIES: dict[str, str] = {
    # govcon-relevant overseas locations + common military host nations
    "japan": "Japan",
    "korea": "South Korea",
    "south korea": "South Korea",
    "singapore": "Singapore",
    "australia": "Australia",
    "philippines": "Philippines",
    "thailand": "Thailand",
    "india": "India",
    "taiwan": "Taiwan",
    "germany": "Germany",
    "uk": "United Kingdom",
    "united kingdom": "United Kingdom",
    "england": "United Kingdom",
    "scotland": "United Kingdom",
    "ireland": "Ireland",
    "france": "France",
    "italy": "Italy",
    "spain": "Spain",
    "portugal": "Portugal",
    "netherlands": "Netherlands",
    "belgium": "Belgium",
    "luxembourg": "Luxembourg",
    "poland": "Poland",
    "romania": "Romania",
    "bulgaria": "Bulgaria",
    "greece": "Greece",
    "norway": "Norway",
    "sweden": "Sweden",
    "finland": "Finland",
    "denmark": "Denmark",
    "iceland": "Iceland",
    "estonia": "Estonia",
    "latvia": "Latvia",
    "lithuania": "Lithuania",
    "czech republic": "Czechia",
    "czechia": "Czechia",
    "hungary": "Hungary",
    "austria": "Austria",
    "switzerland": "Switzerland",
    "turkey": "Turkey",
    "israel": "Israel",
    "uae": "United Arab Emirates",
    "united arab emirates": "United Arab Emirates",
    "qatar": "Qatar",
    "bahrain": "Bahrain",
    "kuwait": "Kuwait",
    "saudi arabia": "Saudi Arabia",
    "oman": "Oman",
    "jordan": "Jordan",
    "iraq": "Iraq",
    "afghanistan": "Afghanistan",
    "egypt": "Egypt",
    "djibouti": "Djibouti",
    "kenya": "Kenya",
    "south africa": "South Africa",
    "canada": "Canada",
    "mexico": "Mexico",
    "brazil": "Brazil",
    "colombia": "Colombia",
    "argentina": "Argentina",
    "chile": "Chile",
    "peru": "Peru",
    "ukraine": "Ukraine",
}

# Common overseas military bases / cities (substring match).
_OCONUS_CITIES: dict[str, str] = {
    "ramstein": "Germany",
    "kaiserslautern": "Germany",
    "stuttgart": "Germany",
    "wiesbaden": "Germany",
    "grafenwoehr": "Germany",
    "vilseck": "Germany",
    "spangdahlem": "Germany",
    "frankfurt": "Germany",
    "berlin": "Germany",
    "munich": "Germany",
    "hamburg": "Germany",
    "aviano": "Italy",
    "vicenza": "Italy",
    "naples": "Italy",
    "rome": "Italy",
    "milan": "Italy",
    "sigonella": "Italy",
    "rota": "Spain",
    "moron": "Spain",
    "madrid": "Spain",
    "barcelona": "Spain",
    "lakenheath": "United Kingdom",
    "mildenhall": "United Kingdom",
    "menwith hill": "United Kingdom",
    "london": "United Kingdom",
    "fairford": "United Kingdom",
    "alconbury": "United Kingdom",
    "incirlik": "Turkey",
    "istanbul": "Turkey",
    "ankara": "Turkey",
    "tel aviv": "Israel",
    "jerusalem": "Israel",
    "doha": "Qatar",
    "al udeid": "Qatar",
    "manama": "Bahrain",
    "kuwait city": "Kuwait",
    "ali al salem": "Kuwait",
    "dubai": "United Arab Emirates",
    "abu dhabi": "United Arab Emirates",
    "kabul": "Afghanistan",
    "bagram": "Afghanistan",
    "baghdad": "Iraq",
    "erbil": "Iraq",
    "yokosuka": "Japan",
    "yokota": "Japan",
    "misawa": "Japan",
    "iwakuni": "Japan",
    "okinawa": "Japan",
    "kadena": "Japan",
    "futenma": "Japan",
    "atsugi": "Japan",
    "tokyo": "Japan",
    "aomori": "Japan",
    "sasebo": "Japan",
    "osan": "South Korea",
    "kunsan": "South Korea",
    "pyeongtaek": "South Korea",
    "humphreys": "South Korea",
    "yongsan": "South Korea",
    "seoul": "South Korea",
    "diego garcia": "British Indian Ocean Territory",
    "guam": "Guam (US territory)",
    "hagatna": "Guam (US territory)",
    "andersen": "Guam (US territory)",
    "sydney": "Australia",
    "canberra": "Australia",
    "melbourne": "Australia",
    "perth": "Australia",
    "darwin": "Australia",
    "ottawa": "Canada",
    "toronto": "Canada",
    "vancouver": "Canada",
    "tel-aviv": "Israel",
}

_OCONUS_MARKERS = re.compile(
    r"\b(oconus|overseas|international|emea|apac|asia[- ]pacific|middle east|"
    r"europe|asia|africa|latin america)\b",
    re.I,
)
_US_MARKERS = re.compile(
    r"\b(united states|usa|u\.s\.a\.|u\.s\.|conus)\b",
    re.I,
)
# Common US state abbreviations seen in postings ("Reston, VA").
_US_STATE_ABBR = re.compile(
    r",\s*(AL|AK|AZ|AR|CA|CO|CT|DE|DC|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|"
    r"MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|"
    r"VT|VA|WA|WV|WI|WY)\b"
)


def classify_country(location: str | None) -> str | None:
    """Best-effort: return canonical country name if location is OCONUS, else None.

    Returns None for US locations (caller should treat None + flagged-not-oconus
    as "United States"). Returning None for unknowns is intentional — never
    fabricate a country.
    """
    if not location:
        return None
    loc_lower = location.lower()
    for marker, canonical in _OCONUS_CITIES.items():
        if marker in loc_lower:
            return canonical
    for marker, canonical in _OCONUS_COUNTRIES.items():
        # Use a word-boundary check so "iceland" doesn't match "Riceland".
        if re.search(rf"\b{re.escape(marker)}\b", loc_lower):
            return canonical
    return None


def classify_oconus(location: str | None) -> bool:
    if not location:
        return False
    if classify_country(location) is not None:
        return True
    # _OCONUS_MARKERS catches "EMEA" / "APAC" / "International" etc. when
    # no specific country resolves but the locale is clearly overseas.
    return bool(_OCONUS_MARKERS.search(location))
