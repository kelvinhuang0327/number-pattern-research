"""
tests/test_mlb_model_probability_audit.py

P6 tests for wbc_backend/prediction/mlb_model_probability_audit.py
"""
from __future__ import annotations

import pytest

from wbc_backend.prediction.mlb_model_probability_audit import (
    audit_model_probability_rows,
    segment_model_probability_audit,
)


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

def _make_row(
    date: str = "2025-05-01",
    home: str = "KC",
    away: str = "HOU",
    home_score: str = "5",
    away_score: str = "3",
    status: str = "Final",
    home_ml: str = "+100",
    away_ml: str = "-120",
    model_prob_home: str = "0.52",
    probability_source: str = "calibrated_model",
) -> dict:
    return {
        "Date": date,
        "Home": home,
        "Away": away,
        "Home Score": home_score,
        "Away Score": away_score,
        "Status": status,
        "Home ML": home_ml,
        "Away ML": away_ml,
        "model_prob_home": model_prob_home,
        "probability_source": probability_source,
    }


def _make_rows(n: int = 50) -> list[dict]:
    rows = []
    for i in range(n):
        # Alternate home win / away win
        hs, as_ = ("5", "2") if i % 2 == 0 else ("1", "3")
        prob = str(round(0.4 + (i % 5) * 0.05, 2))  # 0.40 to 0.60
        rows.append(_make_row(
            date=f"2025-{(i // 28) + 4:02d}-{(i % 28) + 1:02d}",
            home_score=hs,
            away_score=as_,
            model_prob_home=prob,
        ))
    return rows


# ─────────────────────────────────────────────────────────────────────────────
# Tests: basic audit
# ─────────────────────────────────────────────────────────────────────────────

class TestAuditBasic:
    def test_row_count_and_usable_count(self):
        rows = _make_rows(50)
        result = audit_model_probability_rows(rows)
        assert result["row_count"] == 50
        assert result["usable_count"] == 50

    def test_missing_model_prob_counted(self):
        rows = _make_rows(10)
        # Remove model_prob_home from 3 rows
        for r in rows[:3]:
            r["model_prob_home"] = ""
        result = audit_model_probability_rows(rows)
        assert result["missing_model_prob_count"] == 3
        assert result["usable_count"] == 7

    def test_missing_market_prob_counted(self):
        rows = _make_rows(10)
        # Remove moneyline from 2 rows
        for r in rows[:2]:
            r["Home ML"] = ""
            r["Away ML"] = ""
        result = audit_model_probability_rows(rows)
        assert result["missing_market_prob_count"] == 2
        assert result["usable_count"] == 8

    def test_missing_outcome_counted(self):
        rows = _make_rows(10)
        # Change status to non-final
        for r in rows[:4]:
            r["Status"] = "Scheduled"
        result = audit_model_probability_rows(rows)
        assert result["missing_outcome_count"] == 4
        assert result["usable_count"] == 6

    def test_invalid_prob_counted(self):
        rows = _make_rows(10)
        # Set invalid prob in one row (won't be counted in usable but should be flagged)
        rows[0]["model_prob_home"] = "1.5"
        result = audit_model_probability_rows(rows)
        assert result["probability_range"]["invalid_prob_count"] == 1


class TestAuditMetrics:
    def test_brier_and_bss_computed(self):
        rows = _make_rows(50)
        result = audit_model_probability_rows(rows)
        assert result["model_brier"] is not None
        assert result["market_brier"] is not None
        assert result["brier_skill_score"] is not None

    def test_ece_computed(self):
        rows = _make_rows(50)
        result = audit_model_probability_rows(rows)
        assert result["ece"] is not None
        assert 0.0 <= result["ece"] <= 1.0

    def test_model_brier_is_float(self):
        rows = _make_rows(50)
        result = audit_model_probability_rows(rows)
        assert isinstance(result["model_brier"], float)

    def test_orientation_checks_present(self):
        rows = _make_rows(50)
        result = audit_model_probability_rows(rows)
        oc = result["orientation_checks"]
        assert "home_win_rate_when_model_gt_0_5" in oc
        assert "home_win_rate_when_model_lt_0_5" in oc
        assert "avg_model_prob_when_home_wins" in oc
        assert "avg_model_prob_when_home_loses" in oc

    def test_source_counts_present(self):
        rows = _make_rows(10)
        result = audit_model_probability_rows(rows)
        sc = result["source_counts"]
        assert "calibrated_model" in sc
        assert sc["calibrated_model"] == 10


# ─────────────────────────────────────────────────────────────────────────────
# Tests: segmentation
# ─────────────────────────────────────────────────────────────────────────────

class TestSegmentAudit:
    def test_segment_by_month(self):
        rows = _make_rows(50)
        segments = segment_model_probability_audit(rows, "month")
        assert isinstance(segments, list)
        assert len(segments) >= 1
        for seg in segments:
            assert "segment" in seg
            assert "row_count" in seg
            assert "bss" in seg

    def test_segment_by_confidence_bucket(self):
        rows = _make_rows(50)
        segments = segment_model_probability_audit(rows, "confidence_bucket")
        assert isinstance(segments, list)
        labels = {s["segment"] for s in segments}
        # Should have at least one bucket
        assert len(labels) >= 1

    def test_segment_by_market_prob_bucket(self):
        rows = _make_rows(50)
        segments = segment_model_probability_audit(rows, "market_prob_bucket")
        assert isinstance(segments, list)
        assert len(segments) >= 1

    def test_segment_by_favorite_side(self):
        rows = _make_rows(50)
        segments = segment_model_probability_audit(rows, "favorite_side")
        labels = {s["segment"] for s in segments}
        assert "home_fav" in labels or "away_fav" in labels

    def test_segment_by_probability_source(self):
        rows = _make_rows(10)
        segments = segment_model_probability_audit(rows, "probability_source")
        assert len(segments) >= 1

    def test_invalid_segment_raises(self):
        rows = _make_rows(5)
        with pytest.raises(ValueError, match="Unsupported segment_by"):
            segment_model_probability_audit(rows, "nonexistent_segment")

    def test_segment_row_count_matches(self):
        rows = _make_rows(20)
        segments = segment_model_probability_audit(rows, "month")
        total = sum(s["row_count"] for s in segments)
        assert total == 20

    def test_empty_rows_audit(self):
        result = audit_model_probability_rows([])
        assert result["row_count"] == 0
        assert result["usable_count"] == 0
        assert result["model_brier"] is None
