"""Unit tests for GS grade inference. Pure-function logic."""

from __future__ import annotations

from devsecops_job_hub.services.gs_scale import infer_gs_grade


class TestInferGsGrade:
    def test_below_gs5_returns_none(self):
        # GS-5 step 1 (DC) is ~$39.5K. Below that we don't tag.
        assert infer_gs_grade(30_000) is None

    def test_none_input(self):
        assert infer_gs_grade(None) is None

    def test_gs7_floor(self):
        # GS-7 step 1 DC = $49,028.
        assert infer_gs_grade(49_028) == 7
        assert infer_gs_grade(50_000) == 7

    def test_gs9_range(self):
        # GS-9 step 1 = $59,966; GS-10 step 1 = $66,036.
        assert infer_gs_grade(60_000) == 9
        assert infer_gs_grade(65_000) == 9

    def test_gs12_typical(self):
        # GS-12 step 1 = $86,962; common cleared mid-career posting.
        assert infer_gs_grade(95_000) == 12

    def test_gs13_typical(self):
        # GS-13 step 1 DC = $103,409.
        assert infer_gs_grade(120_000) == 13

    def test_gs14_typical(self):
        # GS-14 step 1 DC = $122,198.
        assert infer_gs_grade(130_000) == 14
        assert infer_gs_grade(140_000) == 14

    def test_caps_at_gs15(self):
        # GS-15 step 1 = $143,736. Anything above that maps to 15
        # (we don't go into SES territory).
        assert infer_gs_grade(180_000) == 15
        assert infer_gs_grade(500_000) == 15

    def test_just_at_gs5_floor(self):
        # GS-5 step 1 DC = $39,576. Boundary inclusive.
        assert infer_gs_grade(39_576) == 5

    def test_just_below_gs5_floor(self):
        assert infer_gs_grade(39_575) is None
