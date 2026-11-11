"""
tests/test_p27_true_date_range_planner.py

Unit tests for p27_true_date_range_planner.py.
"""
import pytest

from wbc_backend.recommendation.p27_true_date_range_planner import (
    build_true_date_segments,
    estimate_runtime_risk,
    summarize_segment_plan,
    validate_segment_plan,
)


class TestBuildTrueDateSegments:
    def test_single_day_produces_one_segment(self):
        segs = build_true_date_segments("2025-05-08", "2025-05-08", segment_days=14)
        assert len(segs) == 1
        assert segs[0].date_start == "2025-05-08"
        assert segs[0].date_end == "2025-05-08"
        assert segs[0].date_count == 1

    def test_14_days_produces_one_segment(self):
        segs = build_true_date_segments("2025-05-08", "2025-05-21", segment_days=14)
        assert len(segs) == 1
        assert segs[0].date_count == 14

    def test_15_days_produces_two_segments(self):
        segs = build_true_date_segments("2025-05-08", "2025-05-22", segment_days=14)
        assert len(segs) == 2
        assert segs[0].date_count == 14
        assert segs[1].date_count == 1

    def test_full_range_produces_correct_count(self):
        # 2025-05-08 to 2025-09-28 = 144 days → ceil(144/14) = 11 segments (10x14 + 4)
        segs = build_true_date_segments("2025-05-08", "2025-09-28", segment_days=14)
        assert len(segs) > 0
        total_days = sum(s.date_count for s in segs)
        # Verify total coverage: 2025-05-08 to 2025-09-28
        from datetime import date
        expected = (date(2025, 9, 28) - date(2025, 5, 8)).days + 1
        assert total_days == expected

    def test_start_after_end_returns_empty(self):
        segs = build_true_date_segments("2025-05-10", "2025-05-08")
        assert segs == []

    def test_segment_days_less_than_one_raises(self):
        with pytest.raises(ValueError, match="segment_days"):
            build_true_date_segments("2025-05-08", "2025-05-21", segment_days=0)

    def test_segments_have_sequential_indices(self):
        segs = build_true_date_segments("2025-05-08", "2025-06-04", segment_days=14)
        for i, s in enumerate(segs):
            assert s.segment_index == i

    def test_no_dates_skipped(self):
        """Verify sum of date_count equals total calendar days."""
        from datetime import date
        segs = build_true_date_segments("2025-05-08", "2025-06-30", segment_days=14)
        total = sum(s.date_count for s in segs)
        expected = (date(2025, 6, 30) - date(2025, 5, 8)).days + 1
        assert total == expected

    def test_output_dirs_contain_dates(self):
        segs = build_true_date_segments("2025-05-08", "2025-05-21")
        assert "2025-05-08" in segs[0].p25_output_dir
        assert "2025-05-21" in segs[0].p26_output_dir


class TestValidateSegmentPlan:
    def test_valid_contiguous_segments(self):
        segs = build_true_date_segments("2025-05-08", "2025-05-22", segment_days=14)
        assert validate_segment_plan(segs) is True

    def test_empty_plan_is_valid(self):
        assert validate_segment_plan([]) is True

    def test_gap_between_segments_raises(self):
        segs = build_true_date_segments("2025-05-08", "2025-05-22", segment_days=14)
        # Corrupt second segment start date to create a gap
        from wbc_backend.recommendation.p27_full_true_date_backfill_contract import P27ExpansionSegment
        bad_seg = P27ExpansionSegment(
            segment_index=1,
            date_start="2025-05-23",  # gap: expected 2025-05-22
            date_end="2025-05-29",
            date_count=7,
            p25_output_dir="/tmp/p25",
            p26_output_dir="/tmp/p26",
        )
        with pytest.raises(ValueError, match="Gap"):
            validate_segment_plan([segs[0], bad_seg])

    def test_wrong_index_raises(self):
        segs = build_true_date_segments("2025-05-08", "2025-05-22", segment_days=14)
        from wbc_backend.recommendation.p27_full_true_date_backfill_contract import P27ExpansionSegment
        bad = P27ExpansionSegment(
            segment_index=99,  # wrong
            date_start=segs[1].date_start,
            date_end=segs[1].date_end,
            date_count=segs[1].date_count,
            p25_output_dir=segs[1].p25_output_dir,
            p26_output_dir=segs[1].p26_output_dir,
        )
        with pytest.raises(ValueError, match="segment_index"):
            validate_segment_plan([segs[0], bad])


class TestSummarizeSegmentPlan:
    def test_summary_has_correct_total_dates(self):
        segs = build_true_date_segments("2025-05-08", "2025-05-21", segment_days=14)
        s = summarize_segment_plan(segs)
        assert s["total_dates"] == 14
        assert s["n_segments"] == 1

    def test_empty_segments_summary(self):
        s = summarize_segment_plan([])
        assert s["n_segments"] == 0
        assert s["date_start"] is None

    def test_summary_segments_list_length(self):
        segs = build_true_date_segments("2025-05-08", "2025-05-22", segment_days=14)
        s = summarize_segment_plan(segs)
        assert len(s["segments"]) == len(segs)


class TestEstimateRuntimeRisk:
    def test_small_range_is_low_risk(self):
        segs = build_true_date_segments("2025-05-08", "2025-05-14", segment_days=14)
        risk = estimate_runtime_risk(segs)
        assert risk["risk_level"] == "LOW"

    def test_full_range_has_n_segments_and_dates(self):
        segs = build_true_date_segments("2025-05-08", "2025-09-28", segment_days=14)
        risk = estimate_runtime_risk(segs)
        assert risk["n_segments"] == len(segs)
        assert risk["total_dates"] > 0

    def test_custom_rows_per_day(self):
        segs = build_true_date_segments("2025-05-08", "2025-05-21", segment_days=14)
        risk = estimate_runtime_risk(segs, expected_rows_per_day=20.0)
        assert risk["estimated_rows"] == 14 * 20
