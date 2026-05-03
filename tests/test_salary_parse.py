"""Unit tests for parse_salary_from_text. Pure-function logic."""

from __future__ import annotations

from devsecops_job_hub.services.salary_parse import parse_salary_from_text


class TestParseSalary:
    def test_explicit_anchor_dollar_range(self):
        text = "The base salary range for this role is $140,000 — $190,000 per year."
        assert parse_salary_from_text(text) == (140_000, 190_000)

    def test_k_suffix(self):
        text = "Salary range: $120K-$160K plus equity."
        assert parse_salary_from_text(text) == (120_000, 160_000)

    def test_lowercase_k_suffix(self):
        text = "Compensation Range: $90k - $130k"
        assert parse_salary_from_text(text) == (90_000, 130_000)

    def test_em_dash(self):
        text = "Annual salary $110,000—$150,000"
        assert parse_salary_from_text(text) == (110_000, 150_000)

    def test_word_to(self):
        text = "Base compensation $130,000 to $170,000 annually."
        assert parse_salary_from_text(text) == (130_000, 170_000)

    def test_no_anchor_with_keyword_context_passes(self):
        # No anchor regex hit, but "salary" sits within the 50-char context window
        # before the range — counts as a soft anchor.
        text = "Reasonable salary expectation: $140,000 - $180,000."
        assert parse_salary_from_text(text) == (140_000, 180_000)

    def test_dollar_range_without_anchor_is_rejected(self):
        # Equity grant numbers, benefits, etc. — must not be picked up.
        text = "Stock options worth $50,000 - $100,000 over 4 years."
        assert parse_salary_from_text(text) == (None, None)

    def test_implausibly_low_is_rejected(self):
        # $20K-$25K is too low to be a real salary; almost always a parse error.
        text = "The base salary range for this role is $20,000 - $25,000."
        assert parse_salary_from_text(text) == (None, None)

    def test_implausibly_high_is_rejected(self):
        text = "The base salary range for this role is $1,500,000 - $2,000,000."
        assert parse_salary_from_text(text) == (None, None)

    def test_reversed_range_is_normalized(self):
        text = "Salary range: $190,000 - $140,000"
        # Probably a typo; we sort it min <= max.
        assert parse_salary_from_text(text) == (140_000, 190_000)

    def test_none_input(self):
        assert parse_salary_from_text(None) == (None, None)

    def test_empty_input(self):
        assert parse_salary_from_text("") == (None, None)

    def test_no_dollar_amounts(self):
        text = "Competitive salary commensurate with experience."
        assert parse_salary_from_text(text) == (None, None)

    def test_anchor_window_caps_search(self):
        # Anchor at start, real range much later — the window cuts off before
        # we reach it. Avoids picking up unrelated dollar amounts further down.
        text = (
            "Annual salary commensurate with experience. "
            + "x" * 300
            + " Stock options $300,000 - $500,000."
        )
        assert parse_salary_from_text(text) == (None, None)

    def test_picks_first_anchored_range_only(self):
        text = (
            "The base salary range for this role is $140,000 - $180,000. "
            "We also offer equity worth $50,000 - $100,000."
        )
        assert parse_salary_from_text(text) == (140_000, 180_000)

    def test_datadog_style_anchor(self):
        # Real format observed on Datadog Greenhouse postings.
        text = (
            "fitness reimbursements, and a discounted employee stock purchase plan. "
            "The reasonably estimated yearly salary for this role at Datadog is: "
            "$102,000 — $130,000 USD About Datadog: ..."
        )
        assert parse_salary_from_text(text) == (102_000, 130_000)

    def test_salary_for_this_role_anchor(self):
        text = "The salary for this role is $145,000 to $185,000 plus bonus."
        assert parse_salary_from_text(text) == (145_000, 185_000)
