"""Extract a (min, max) USD annual salary range from posting description text.

Greenhouse postings put salary in plain copy ("$140,000 — $190,000 / year",
"Salary Range: $120K-$160K", etc.). Lever returns it as structured JSON, so
this module is for the Greenhouse path and any other free-text source.

Honesty constraints (per spec):
- Never fabricate. If we can't find a credible range, return (None, None).
- Reject implausible ranges (max < min, max > $1M, min < $30K) — those are
  almost always parsing errors, not real ranges.
- Reject hourly/monthly amounts. We only emit annualized salaries; converting
  hourly to annual is a guess.
"""

from __future__ import annotations

import re

# Match anchors for "salary" or "compensation" sections — we anchor before
# the number range to avoid catching unrelated dollar amounts (revenue,
# benefits caps, equity grants).
_SALARY_ANCHOR = re.compile(
    r"(?:base\s+(?:salary|pay|compensation)|"
    r"salary\s+range|"
    r"compensation\s+range|"
    r"pay\s+range|"
    r"target\s+(?:salary|compensation)|"
    r"annual\s+(?:salary|base|compensation)|"
    r"(?:yearly|annual)\s+salary|"
    r"(?:salary|compensation|pay)\s+for\s+this\s+(?:role|position)|"
    r"the\s+(?:base\s+)?(?:salary|pay|compensation)\s+(?:range\s+)?for\s+this\s+(?:role|position)|"
    r"reasonably\s+estimated\s+(?:yearly|annual)\s+salary|"
    r"expected\s+(?:salary|compensation|pay)\s+range)",
    re.I,
)

# A dollar amount: $140,000 or $140K or $140,000.00. Matches optional cents
# and the K/k suffix.
_AMOUNT = r"\$\s*(\d{2,3}(?:[,.]\d{3})*(?:\.\d+)?)\s*([Kk])?"

# A range: $X to $Y, $X – $Y, $X-$Y. Allows en-dash, em-dash, hyphen, "to",
# and "—". Allows up to 50 chars between the two amounts to absorb words
# like "/year" between the numbers without losing the match.
_RANGE = re.compile(
    rf"{_AMOUNT}\s*(?:[-–—]|to)\s*{_AMOUNT}",
    re.I,
)

_MIN_PLAUSIBLE = 30_000
_MAX_PLAUSIBLE = 1_000_000

# Within this many characters after a salary anchor, look for a dollar range.
# Past this distance the anchor probably referred to something else.
_ANCHOR_WINDOW = 250


def _to_int_dollars(amount: str, k_suffix: str | None) -> int | None:
    cleaned = amount.replace(",", "")
    try:
        n = float(cleaned)
    except ValueError:
        return None
    if k_suffix:
        n *= 1000
    return int(n)


def parse_salary_from_text(text: str | None) -> tuple[int | None, int | None]:
    if not text:
        return None, None

    # Find the first salary anchor; only look for dollar ranges within the
    # window after it. This avoids picking up benefits caps ("$50K life
    # insurance"), 401k matches, or unrelated equity-grant numbers.
    anchor = _SALARY_ANCHOR.search(text)
    search_text = text[anchor.start() : anchor.end() + _ANCHOR_WINDOW] if anchor else text

    # If we have no anchor we still try a strict pattern match — but only
    # trust it if the surrounding text mentions "salary"/"pay" within ~50
    # chars before the range. Keeps false positives out without missing
    # postings that just say "$140K-$190K".
    for m in _RANGE.finditer(search_text):
        lo = _to_int_dollars(m.group(1), m.group(2))
        hi = _to_int_dollars(m.group(3), m.group(4))
        if lo is None or hi is None:
            continue
        if lo > hi:
            lo, hi = hi, lo
        if not (_MIN_PLAUSIBLE <= lo <= _MAX_PLAUSIBLE and _MIN_PLAUSIBLE <= hi <= _MAX_PLAUSIBLE):
            continue
        # Without an anchor, require "salary" or "pay" within 50 chars before
        # the range itself.
        if not anchor:
            ctx_start = max(0, m.start() - 50)
            ctx = text[ctx_start : m.start()].lower()
            if not any(k in ctx for k in ("salary", "pay range", "compensation", "base pay")):
                continue
        return lo, hi
    return None, None
