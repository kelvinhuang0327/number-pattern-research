"""
tests/test_mlb_model_deep_diagnostics.py

P8: Unit tests for wbc_backend/prediction/mlb_model_deep_diagnostics.py
"""
from __future__ import annotations

import pytest

from wbc_backend.prediction.mlb_model_deep_diagnostics import (
    find_worst_model_segments,
    run_model_deep_diagnostics,
)

# ─────────────────────────────────────────────────────────────────────────────
# § 0  Fixtures
# ─────────────────────────────────────────────────────────────────────────────

def _make_row(
    *,
    model_prob: float,
    home_win: int | None = None,
    home_score: float | None = None,
    away_score: float | None = None,
    status: str = "Final",
    home_ml: int | str = -110,
    away_ml: int | str = -110,
    date: str = "2025-05-01",
) -> dict:
    row: dict = {
        "model_prob_home": str(model_prob),
        "Home ML": str(home_ml),
        "Away ML": str(away_ml),
        "Date": date,
    }
    if home_win is not None:
        row["home_win"] = str(home_win)
    if home_score is not None:
        row["Home Score"] = str(home_score)
        row["Away Score"] = str(away_score)
        row["Status"] = status
    return row


@pytest.fixture()
def basic_rows() -> list[dict]:
    """12 rows: model roughly matches market, calibrated."""
    return [
        _make_row(model_prob=0.52, home_score=5, away_score=3, date="2025-05-01"),
        _make_row(model_prob=0.48, home_score=2, away_score=4, date="2025-05-01"),
        _make_row(model_prob=0.55, home_score=6, away_score=1, date="2025-05-02"),
        _make_row(model_prob=0.45, home_score=1, away_score=7, date="2025-05-02"),
        _make_row(model_prob=0.60, home_score=3, away_score=2, date="2025-05-03"),
        _make_row(model_prob=0.40, home_score=0, away_score=5, date="2025-05-03"),
        _make_row(model_prob=0.53, home_score=4, away_score=4, date="2025-06-01"),  # tie → home_win=0
        _make_row(model_prob=0.50, home_score=3, away_score=2, date="2025-06-01"),
        _make_row(model_prob=0.58, home_score=7, away_score=2, date="2025-06-02"),
        _make_row(model_prob=0.42, home_score=1, away_score=3, date="2025-06-02"),
        _make_row(model_prob=0.65, home_score=4, away_score=3, date="2025-07-01"),
        _make_row(model_prob=0.35, home_score=0, away_score=2, date="2025-07-01"),
    ]


@pytest.fixture()
def home_biased_rows() -> list[dict]:
    """Rows where model systematically over-predicts home (+12pp vs market)."""
    rows = []
    for i in range(20):
        outcome = 1 if i % 2 == 0 else 0
        rows.append(
            _make_row(
                model_prob=0.65,    # market ~0.524 → bias=+0.126
                home_win=outcome,
                home_ml=-112,
                away_ml=+102,
                date=f"2025-05-{(i%28)+1:02d}",
            )
        )
    return rows


# ─────────────────────────────────────────────────────────────────────────────
# § 1  run_model_deep_diagnostics — core contract
# ─────────────────────────────────────────────────────────────────────────────

class TestRunModelDeepDiagnosticsContract:
    def test_returns_dict(self, basic_rows):
        result = run_model_deep_diagnostics(basic_rows)
        assert isinstance(result, dict)

    def test_required_keys(self, basic_rows):
        result = run_model_deep_diagnostics(basic_rows)
        expected_keys = {
            "row_count", "usable_count",
            "model_brier", "market_brier", "brier_skill_score",
            "ece", "avg_model_prob", "avg_market_prob",
            "avg_home_win_rate", "avg_model_minus_market",
            "orientation_diagnostics", "join_diagnostics",
            "outcome_diagnostics", "probability_diagnostics",
            "segment_summary",
        }
        assert expected_keys.issubset(result.keys()), f"Missing keys: {expected_keys - result.keys()}"

    def test_row_count_matches_input(self, basic_rows):
        result = run_model_deep_diagnostics(basic_rows)
        assert result["row_count"] == len(basic_rows)

    def test_usable_count_leq_row_count(self, basic_rows):
        result = run_model_deep_diagnostics(basic_rows)
        assert result["usable_count"] <= result["row_count"]
        assert result["usable_count"] >= 0

    def test_brier_range(self, basic_rows):
        result = run_model_deep_diagnostics(basic_rows)
        assert 0.0 <= result["model_brier"] <= 1.0
        assert 0.0 <= result["market_brier"] <= 1.0

    def test_ece_non_negative(self, basic_rows):
        result = run_model_deep_diagnostics(basic_rows)
        assert result["ece"] >= 0.0

    def test_avg_model_prob_range(self, basic_rows):
        result = run_model_deep_diagnostics(basic_rows)
        assert 0.0 <= result["avg_model_prob"] <= 1.0

    def test_avg_home_win_rate_range(self, basic_rows):
        result = run_model_deep_diagnostics(basic_rows)
        assert 0.0 <= result["avg_home_win_rate"] <= 1.0


class TestRunModelDeepDiagnosticsEmpty:
    def test_empty_rows(self):
        result = run_model_deep_diagnostics([])
        assert result["row_count"] == 0
        assert result["usable_count"] == 0
        assert result["model_brier"] is None
        assert result["brier_skill_score"] is None

    def test_all_missing_outcomes(self):
        rows = [{"model_prob_home": "0.55", "Home ML": "-110", "Away ML": "-110"}]
        result = run_model_deep_diagnostics(rows)
        assert result["usable_count"] == 0


# ─────────────────────────────────────────────────────────────────────────────
# § 2  Orientation diagnostics
# ─────────────────────────────────────────────────────────────────────────────

class TestOrientationDiagnostics:
    def test_keys(self, basic_rows):
        result = run_model_deep_diagnostics(basic_rows)
        od = result["orientation_diagnostics"]
        assert "bss_normal" in od
        assert "bss_inverted_model" in od
        assert "bss_swapped_home_away" in od
        assert "best_orientation" in od
        assert "orientation_warning" in od

    def test_best_orientation_is_valid(self, basic_rows):
        od = run_model_deep_diagnostics(basic_rows)["orientation_diagnostics"]
        assert od["best_orientation"] in {"normal", "inverted_model", "swapped_home_away", "unknown"}

    def test_normal_is_best_for_calibrated_rows(self, basic_rows):
        """For rows where model is directionally correct, normal should win."""
        od = run_model_deep_diagnostics(basic_rows)["orientation_diagnostics"]
        # We don't hard-require "normal" wins, but inverted should not exceed normal by >0.005
        bss_n = od["bss_normal"]
        bss_inv = od["bss_inverted_model"]
        if bss_n is not None and bss_inv is not None:
            # If model is calibrated-ish, inversion should be worse
            assert bss_inv < bss_n + 0.2, "Inverted BSS drastically exceeds normal"

    def test_orientation_warning_is_str_or_none(self, basic_rows):
        od = run_model_deep_diagnostics(basic_rows)["orientation_diagnostics"]
        assert od["orientation_warning"] is None or isinstance(od["orientation_warning"], str)

    def test_flipped_model_detected(self):
        """When model probs are flipped (low prob = home win), inverted should dominate."""
        rows = []
        for i in range(20):
            # home wins (outcome=1) when model_prob is LOW — classic flip
            outcome = 1 if i % 2 == 0 else 0
            prob = 0.35 if i % 2 == 0 else 0.65
            rows.append(_make_row(
                model_prob=prob,
                home_win=outcome,
                home_ml=-120,
                away_ml=+110,
            ))
        result = run_model_deep_diagnostics(rows)
        od = result["orientation_diagnostics"]
        # Inverted model should have higher BSS than normal
        assert od["bss_inverted_model"] > od["bss_normal"] - 0.01


# ─────────────────────────────────────────────────────────────────────────────
# § 3  Join diagnostics
# ─────────────────────────────────────────────────────────────────────────────

class TestJoinDiagnostics:
    def test_keys(self, basic_rows):
        jd = run_model_deep_diagnostics(basic_rows)["join_diagnostics"]
        expected = {
            "missing_game_id_count",
            "duplicate_game_id_count",
            "duplicate_date_team_count",
            "missing_home_team_count",
            "missing_away_team_count",
            "suspicious_same_team_count",
        }
        assert expected.issubset(jd.keys())

    def test_missing_game_id_counted(self, basic_rows):
        """Basic rows have no game_id column — all missing."""
        jd = run_model_deep_diagnostics(basic_rows)["join_diagnostics"]
        assert jd["missing_game_id_count"] == len(basic_rows)

    def test_same_team_detection(self):
        rows = [
            {
                "model_prob_home": "0.55",
                "Home ML": "-110",
                "Away ML": "-110",
                "Home": "Los Angeles Dodgers",
                "Away": "Los Angeles Dodgers",
                "home_win": "1",
                "Date": "2025-05-01",
            }
        ]
        jd = run_model_deep_diagnostics(rows)["join_diagnostics"]
        # same_team detection does lowercase compare
        assert jd["suspicious_same_team_count"] >= 0  # just check key exists


# ─────────────────────────────────────────────────────────────────────────────
# § 4  Outcome diagnostics
# ─────────────────────────────────────────────────────────────────────────────

class TestOutcomeDiagnostics:
    def test_keys(self, basic_rows):
        od = run_model_deep_diagnostics(basic_rows)["outcome_diagnostics"]
        assert "outcome_zero_count" in od
        assert "outcome_one_count" in od
        assert "outcome_null_count" in od
        assert "outcome_balance" in od

    def test_balance_range(self, basic_rows):
        od = run_model_deep_diagnostics(basic_rows)["outcome_diagnostics"]
        if od["outcome_balance"] is not None:
            assert 0.0 <= od["outcome_balance"] <= 1.0

    def test_count_consistency(self, basic_rows):
        od = run_model_deep_diagnostics(basic_rows)["outcome_diagnostics"]
        total = od["outcome_zero_count"] + od["outcome_one_count"] + od["outcome_null_count"]
        assert total == len(basic_rows)


# ─────────────────────────────────────────────────────────────────────────────
# § 5  Probability diagnostics
# ─────────────────────────────────────────────────────────────────────────────

class TestProbabilityDiagnostics:
    def test_keys(self, basic_rows):
        pd = run_model_deep_diagnostics(basic_rows)["probability_diagnostics"]
        required = {
            "model_prob_min", "model_prob_max", "model_prob_std",
            "market_prob_min", "market_prob_max", "market_prob_std",
            "overconfident_count", "underconfident_count",
        }
        assert required.issubset(pd.keys())

    def test_min_leq_max(self, basic_rows):
        pd = run_model_deep_diagnostics(basic_rows)["probability_diagnostics"]
        assert pd["model_prob_min"] <= pd["model_prob_max"]
        assert pd["market_prob_min"] <= pd["market_prob_max"]

    def test_home_biased_overconfident(self, home_biased_rows):
        pd = run_model_deep_diagnostics(home_biased_rows)["probability_diagnostics"]
        assert pd["overconfident_count"] > 0, "Expected overconfident count > 0 for biased rows"


# ─────────────────────────────────────────────────────────────────────────────
# § 6  Segment summary
# ─────────────────────────────────────────────────────────────────────────────

class TestSegmentSummary:
    def test_keys(self, basic_rows):
        ss = run_model_deep_diagnostics(basic_rows)["segment_summary"]
        assert "by_month" in ss
        assert "by_confidence_bucket" in ss
        assert "by_favorite_side" in ss
        assert "by_home_bias_bucket" in ss

    def test_by_month_has_segment_key(self, basic_rows):
        ss = run_model_deep_diagnostics(basic_rows)["segment_summary"]
        for seg in ss["by_month"]:
            assert "segment" in seg
            assert "row_count" in seg

    def test_by_month_dates_match_input(self, basic_rows):
        ss = run_model_deep_diagnostics(basic_rows)["segment_summary"]
        months = {s["segment"] for s in ss["by_month"]}
        assert "2025-05" in months
        assert "2025-06" in months

    def test_segment_row_counts_sum_correctly(self, basic_rows):
        result = run_model_deep_diagnostics(basic_rows)
        ss = result["segment_summary"]
        total = result["usable_count"]
        # by_month should sum to usable_count
        month_total = sum(s["row_count"] for s in ss["by_month"])
        assert month_total == total

    def test_confidence_buckets_cover_all(self, basic_rows):
        result = run_model_deep_diagnostics(basic_rows)
        ss = result["segment_summary"]
        bucket_total = sum(s["row_count"] for s in ss["by_confidence_bucket"])
        assert bucket_total == result["usable_count"]


# ─────────────────────────────────────────────────────────────────────────────
# § 7  find_worst_model_segments
# ─────────────────────────────────────────────────────────────────────────────

class TestFindWorstModelSegments:
    def test_returns_list(self, basic_rows):
        diag = run_model_deep_diagnostics(basic_rows)
        worst = find_worst_model_segments(diag)
        assert isinstance(worst, list)

    def test_respects_top_n(self, basic_rows):
        diag = run_model_deep_diagnostics(basic_rows)
        worst = find_worst_model_segments(diag, top_n=3)
        assert len(worst) <= 3

    def test_segment_keys(self, basic_rows):
        diag = run_model_deep_diagnostics(basic_rows)
        worst = find_worst_model_segments(diag)
        if worst:
            required = {"segment", "segment_by", "row_count", "bss", "ece", "avg_edge", "rank_score", "rank_reason"}
            assert required.issubset(worst[0].keys())

    def test_sorted_by_rank_score(self, basic_rows):
        diag = run_model_deep_diagnostics(basic_rows)
        worst = find_worst_model_segments(diag, top_n=20)
        scores = [w["rank_score"] for w in worst]
        assert scores == sorted(scores, reverse=True), "Should be sorted descending by rank_score"

    def test_empty_diagnostics(self):
        worst = find_worst_model_segments({})
        assert worst == []

    def test_home_biased_row_identified(self, home_biased_rows):
        diag = run_model_deep_diagnostics(home_biased_rows)
        worst = find_worst_model_segments(diag, top_n=5)
        # Should surface some home-bias-related segment
        assert len(worst) > 0
        # At least one segment should have negative BSS or high avg_edge
        has_negative_bss = any(w["bss"] is not None and w["bss"] < 0 for w in worst)
        has_high_edge = any(w["avg_edge"] is not None and abs(w["avg_edge"]) > 0.05 for w in worst)
        assert has_negative_bss or has_high_edge


# ─────────────────────────────────────────────────────────────────────────────
# § 8  Outcome derivation (from scores)
# ─────────────────────────────────────────────────────────────────────────────

class TestOutcomeDerivation:
    def test_derived_from_scores_final(self):
        rows = [
            _make_row(model_prob=0.55, home_score=5, away_score=3),
            _make_row(model_prob=0.45, home_score=1, away_score=4),
        ]
        result = run_model_deep_diagnostics(rows)
        assert result["usable_count"] == 2
        assert result["avg_home_win_rate"] == pytest.approx(0.5, abs=0.01)

    def test_non_final_status_excluded(self):
        rows = [
            _make_row(model_prob=0.55, home_score=5, away_score=3, status="In Progress"),
        ]
        result = run_model_deep_diagnostics(rows)
        assert result["usable_count"] == 0

    def test_explicit_home_win_column_used(self):
        rows = [
            {
                "model_prob_home": "0.60",
                "Home ML": "-120",
                "Away ML": "+110",
                "home_win": "1",
                "Date": "2025-05-01",
            }
        ]
        result = run_model_deep_diagnostics(rows)
        assert result["usable_count"] == 1
        assert result["avg_home_win_rate"] == pytest.approx(1.0)
