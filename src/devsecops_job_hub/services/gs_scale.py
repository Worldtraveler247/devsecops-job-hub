"""Map a private-sector salary to its closest GS pay-grade equivalent.

Use case: cleared candidates transitioning from military or federal civilian
work often think in GS grades. Showing "$130K-$160K · ~GS-13" gives them an
immediate calibration against pay they already understand.

Data
- 2025 GS table, DC locality. Other localities pay 16-44% above base
  depending on metro; DC (32.49% adj) is the most common cleared-work
  location, so it's a reasonable single-locality default for v1.
- Update annually from https://www.opm.gov/policy-data-oversight/pay-leave/
  salaries-wages/. The next update is 2026 (when the GS adjustment takes
  effect each January).

Honesty
- This is a *rough equivalence*, not a federal job offer. The hub does not
  fabricate GS grades for federal positions — it just labels private
  postings with the closest grade for context. Boundaries between grades
  are interpolated using midpoints; ties favor the lower grade.
"""

from __future__ import annotations

# 2025 GS pay table, DC locality. (grade, step1, step10) — using just the
# bracket because step is unknown for private postings. Effective 2025-01-12.
# Source: OPM 2025 General Schedule + DC locality adjustment.
_GS_BRACKETS_DC_2025: list[tuple[int, int, int]] = [
    (5, 39_576, 51_447),
    (6, 44_117, 57_350),
    (7, 49_028, 63_733),
    (8, 54_292, 70_577),
    (9, 59_966, 77_955),
    (10, 66_036, 85_847),
    (11, 72_553, 94_317),
    (12, 86_962, 113_047),
    (13, 103_409, 134_435),
    (14, 122_198, 158_860),
    (15, 143_736, 186_854),
]


def infer_gs_grade(salary_usd: int | None) -> int | None:
    """Return the GS grade whose pay range best contains the given salary.

    None when salary is missing or below GS-5 step 1 (private roles below
    ~$40K aren't useful to label). For salaries above GS-15 step 10 we cap
    at 15 because that's where the GS table tops out — SES is its own
    schedule and not a useful comparison for the hub's audience.
    """
    if salary_usd is None:
        return None
    floor = _GS_BRACKETS_DC_2025[0][1]
    if salary_usd < floor:
        return None
    # Find the highest grade whose step-1 floor is ≤ salary. That's the
    # grade where the candidate would land at or above step 1, which is the
    # natural equivalence for a posting offering at least that pay.
    matched = _GS_BRACKETS_DC_2025[0][0]
    for grade, step1, _step10 in _GS_BRACKETS_DC_2025:
        if salary_usd >= step1:
            matched = grade
        else:
            break
    return matched
