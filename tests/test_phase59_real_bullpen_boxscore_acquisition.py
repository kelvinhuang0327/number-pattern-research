"""
tests/test_phase59_real_bullpen_boxscore_acquisition.py
=========================================================
Phase 59 — Real Bullpen Boxscore Acquisition Test Suite

Test classes:
  TestSafetyConstants        — frozen safety flags and gate validity
  TestPITNoLookaheadGuard    — forbidden features raise; PIT validation logic
  TestBullpenFeatureSchema   — derived features correct & PIT-safe
  TestArtifactAlignment      — match rate, fallback, no-duplicate guarantees
  TestMissingDataHandling    — 0% coverage → BLOCKED gate; null handling
  TestGateRecommendation     — correct gate from synthetic data
  TestEndToEnd               — real-data integration (skipped if files missing)
"""
from __future__ import annotations

import math
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ── Ensure project root is on path ────────────────────────────────────────────
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from orchestrator.phase59_real_bullpen_boxscore_acquisition import (
    ALPHA,
    BULLPEN_DATA_GAP_BLOCKED,
    BULLPEN_FEATURE_NOT_PROMISING,
    CANDIDATE_PATCH_CREATED,
    DIAGNOSTIC_ONLY,
    ALPHA_MODIFIED,
    PRODUCTION_MODIFIED,
    REAL_BULLPEN_FEATURE_PROMISING,
    INCONCLUSIVE,
    HEAVY_FAV_THRESHOLD,
    HIGH_CONF_THRESHOLD,
    MIN_HEAVY_FAV_WITH_BULL,
    MIN_COVERAGE_FOR_GATE,
    PHASE_VERSION,
    _VALID_GATES,
    AlignmentReport,
    BullpenDataSourceReport,
    Phase59AcquisitionResult,
    _blend_prob,
    _compute_ece_comparison,
    _compute_signal,
    _fav_prob,
    _is_home_favorite,
    _norm_team,
    _parse_bull_game_id,
    _recommend_gate,
    assert_no_forbidden_feature,
    load_and_align,
    run_phase59_acquisition,
    validate_pit_safety_of_bullpen_source,
    _FORBIDDEN_FEATURE_FIELDS,
)


# ═══════════════════════════════════════════════════════════════════════════════
# § 1  Safety Constants
# ═══════════════════════════════════════════════════════════════════════════════

class TestSafetyConstants:
    """Verify all safety flags are set to their required values."""

    def test_candidate_patch_created_is_false(self):
        assert CANDIDATE_PATCH_CREATED is False

    def test_production_modified_is_false(self):
        assert PRODUCTION_MODIFIED is False

    def test_alpha_modified_is_false(self):
        assert ALPHA_MODIFIED is False

    def test_diagnostic_only_is_true(self):
        assert DIAGNOSTIC_ONLY is True

    def test_alpha_frozen_at_0_40(self):
        assert ALPHA == 0.40

    def test_phase_version_format(self):
        assert "phase59" in PHASE_VERSION

    def test_valid_gates_contains_all_four(self):
        assert REAL_BULLPEN_FEATURE_PROMISING in _VALID_GATES
        assert BULLPEN_DATA_GAP_BLOCKED in _VALID_GATES
        assert BULLPEN_FEATURE_NOT_PROMISING in _VALID_GATES
        assert INCONCLUSIVE in _VALID_GATES
        assert len(_VALID_GATES) == 4

    def test_heavy_fav_threshold(self):
        assert HEAVY_FAV_THRESHOLD == 0.70

    def test_high_conf_threshold(self):
        assert HIGH_CONF_THRESHOLD == 0.65

    def test_blend_formula_matches_alpha(self):
        """Blend must follow (1 - ALPHA) * model + ALPHA * market."""
        result = _blend_prob(0.60, 0.50)
        expected = (1 - ALPHA) * 0.60 + ALPHA * 0.50
        assert abs(result - expected) < 1e-9

    def test_fav_prob_is_max(self):
        assert abs(_fav_prob(0.75) - 0.75) < 1e-9
        assert abs(_fav_prob(0.25) - 0.75) < 1e-9
        assert abs(_fav_prob(0.50) - 0.50) < 1e-9


# ═══════════════════════════════════════════════════════════════════════════════
# § 2  PIT No-Lookahead Guard
# ═══════════════════════════════════════════════════════════════════════════════

class TestPITNoLookaheadGuard:
    """Verify that forbidden post-game features raise ValueError."""

    def test_home_win_field_raises(self):
        row = {"game_date": "2025-05-01", "home_win": 1}
        with pytest.raises(ValueError, match="PIT VIOLATION"):
            assert_no_forbidden_feature(row)

    def test_final_score_raises(self):
        row = {"game_date": "2025-05-01", "final_score": "5-3"}
        with pytest.raises(ValueError, match="PIT VIOLATION"):
            assert_no_forbidden_feature(row)

    def test_game_result_raises(self):
        row = {"game_date": "2025-05-01", "game_result": "W"}
        with pytest.raises(ValueError, match="PIT VIOLATION"):
            assert_no_forbidden_feature(row)

    def test_innings_pitched_today_raises(self):
        row = {"game_date": "2025-05-01", "innings_pitched_today": 6.2}
        with pytest.raises(ValueError, match="PIT VIOLATION"):
            assert_no_forbidden_feature(row)

    def test_era_after_game_raises(self):
        row = {"game_date": "2025-05-01", "era_after_game": 3.50}
        with pytest.raises(ValueError, match="PIT VIOLATION"):
            assert_no_forbidden_feature(row)

    def test_clean_row_does_not_raise(self):
        row = {
            "game_date": "2025-05-01",
            "bullpen_usage_last_3d_home": 7.2,
            "bullpen_usage_last_3d_away": 5.0,
            "model_home_prob": 0.55,
        }
        # Should not raise
        assert_no_forbidden_feature(row)

    def test_none_value_forbidden_field_does_not_raise(self):
        """None-valued forbidden fields are allowed (field absent in practice)."""
        row = {"game_date": "2025-05-01", "home_win": None}
        # Should not raise (value is None → harmless placeholder)
        assert_no_forbidden_feature(row)

    def test_all_forbidden_fields_known(self):
        """Check that forbidden set contains key fields."""
        must_contain = {"home_win", "final_score", "game_result",
                        "innings_pitched_today", "era_after_game"}
        assert must_contain.issubset(_FORBIDDEN_FEATURE_FIELDS)

    def test_pit_validation_of_bullpen_source_valid(self):
        """validate_pit_safety_of_bullpen_source returns True for valid rows."""
        rows = [
            {
                "game_id": "MLB-2025_04_27-1_05_PM-TORONTO-BLUE-JAYS-AT-BOSTON-RED-SOX",
                "source": "mlb_stats_api_boxscore",
                "bullpen_usage_last_3d_home": 7.2,
            }
        ]
        is_valid, explanation = validate_pit_safety_of_bullpen_source(rows)
        assert is_valid is True
        assert "D-1, D-2, D-3" in explanation

    def test_pit_validation_empty_rows_returns_false(self):
        is_valid, explanation = validate_pit_safety_of_bullpen_source([])
        assert is_valid is False

    def test_pit_validation_bad_ids_returns_false(self):
        rows = [{"game_id": "NO_DATE_HERE", "source": "mlb_stats_api_boxscore"}] * 60
        is_valid, explanation = validate_pit_safety_of_bullpen_source(rows)
        assert is_valid is False


# ═══════════════════════════════════════════════════════════════════════════════
# § 3  Bullpen Feature Schema
# ═══════════════════════════════════════════════════════════════════════════════

class TestBullpenFeatureSchema:
    """Verify derived bullpen feature schema and correctness."""

    def _make_aligned_row(
        self,
        bull_home: float | None = 7.2,
        bull_away: float | None = 5.0,
        blend: float = 0.75,
        home_win: int = 1,
    ) -> dict:
        home_is_fav = _is_home_favorite(blend)
        has_bull = (bull_home is not None and bull_away is not None)
        delta = (bull_home - bull_away) if has_bull else None
        fav_fatigue = (
            (bull_home - bull_away) if (has_bull and home_is_fav)
            else (bull_away - bull_home) if has_bull
            else None
        )
        return {
            "game_date": "2025-05-01",
            "_label_home_win": home_win,
            "_model_prob": 0.80,
            "_market_prob": 0.65,
            "_blend_prob": blend,
            "_fav_prob": _fav_prob(blend),
            "_home_is_fav": home_is_fav,
            "_bull_home_3d": bull_home,
            "_bull_away_3d": bull_away,
            "_has_bull": has_bull,
            "_bull_delta": delta,
            "_fav_bull_fatigue": fav_fatigue,
            "_is_heavy_fav": _fav_prob(blend) >= HEAVY_FAV_THRESHOLD,
            "_is_high_conf": _fav_prob(blend) >= HIGH_CONF_THRESHOLD,
        }

    def test_bull_delta_is_home_minus_away(self):
        row = self._make_aligned_row(bull_home=8.0, bull_away=5.0)
        assert abs(row["_bull_delta"] - 3.0) < 1e-9

    def test_bull_delta_can_be_negative(self):
        row = self._make_aligned_row(bull_home=4.0, bull_away=9.0)
        assert row["_bull_delta"] < 0

    def test_fav_fatigue_when_home_is_fav(self):
        """When home is favorite, fav_fatigue = home_usage - away_usage."""
        row = self._make_aligned_row(bull_home=10.0, bull_away=4.0, blend=0.75)
        assert row["_home_is_fav"] is True
        assert abs(row["_fav_bull_fatigue"] - 6.0) < 1e-9

    def test_fav_fatigue_when_away_is_fav(self):
        """When away is favorite, fav_fatigue = away_usage - home_usage."""
        row = self._make_aligned_row(bull_home=3.0, bull_away=10.0, blend=0.20)
        assert row["_home_is_fav"] is False
        # away is fav, tired = away_usage > home_usage
        # fav_fatigue = away - home = 10 - 3 = 7 (positive → away fav is tired)
        assert abs(row["_fav_bull_fatigue"] - 7.0) < 1e-9

    def test_has_bull_false_when_null(self):
        row = self._make_aligned_row(bull_home=None, bull_away=None)
        assert row["_has_bull"] is False
        assert row["_bull_delta"] is None
        assert row["_fav_bull_fatigue"] is None

    def test_heavy_fav_flag_correct(self):
        row_hf = self._make_aligned_row(blend=0.75)
        row_not_hf = self._make_aligned_row(blend=0.60)
        assert row_hf["_is_heavy_fav"] is True
        assert row_not_hf["_is_heavy_fav"] is False

    def test_home_win_label_not_used_as_feature(self):
        """Label must be stored under _label_home_win, not home_win."""
        row = self._make_aligned_row()
        assert "_label_home_win" in row
        assert "home_win" not in row

    def test_bullpen_values_in_valid_range(self):
        """Valid bullpen 3d usage values should be positive and bounded."""
        row = self._make_aligned_row(bull_home=9.74, bull_away=10.12)
        assert row["_bull_home_3d"] > 0
        assert row["_bull_away_3d"] > 0
        # MLB practical max: ~27 IP over 3 days (if one bullpen pitches full 3 games)
        assert row["_bull_home_3d"] < 30
        assert row["_bull_away_3d"] < 30


# ═══════════════════════════════════════════════════════════════════════════════
# § 4  Artifact Alignment
# ═══════════════════════════════════════════════════════════════════════════════

def _build_pred_jsonl_content(rows: list[dict]) -> str:
    import json
    return "\n".join(json.dumps(r) for r in rows)


def _build_bull_jsonl_content(rows: list[dict]) -> str:
    import json
    return "\n".join(json.dumps(r) for r in rows)


class TestArtifactAlignment:
    """Verify alignment produces correct match rates and fallback behavior."""

    def _make_pred_row(self, game_date, away, home,
                       model_prob=0.55, market_prob=0.52,
                       home_win=1, game_id=None) -> dict:
        return {
            "game_date": game_date,
            "away_team": away,
            "home_team": home,
            "model_home_prob": model_prob,
            "market_home_prob_no_vig": market_prob,
            "home_win": home_win,
            "game_id": game_id or f"MLB2025_0001_{game_date}_{away}_{home}",
        }

    def _make_bull_row(self, game_date, away, home,
                       home_3d=8.0, away_3d=6.0) -> dict:
        # Format: MLB-YYYY_MM_DD-H_MM_PM-AWAY-AT-HOME
        dt = game_date.replace("-", "_")
        away_id = away.upper().replace(" ", "_")
        home_id = home.upper().replace(" ", "_")
        return {
            "game_id": f"MLB-{dt}-1_05_PM-{away_id}-AT-{home_id}",
            "bullpen_usage_last_3d_home": home_3d,
            "bullpen_usage_last_3d_away": away_3d,
            "source": "mlb_stats_api_boxscore",
            "fetched_at": "2026-03-18T17:56:56Z",
            "unavailable_fields": [],
        }

    def test_perfect_match_rate(self, tmp_path):
        """All rows should match when data is consistent."""
        import json
        pred_rows = [
            self._make_pred_row("2025-05-01", "New York Yankees", "Boston Red Sox"),
            self._make_pred_row("2025-05-01", "Houston Astros", "Texas Rangers"),
        ]
        bull_rows = [
            self._make_bull_row("2025-05-01", "New York Yankees", "Boston Red Sox"),
            self._make_bull_row("2025-05-01", "Houston Astros", "Texas Rangers"),
        ]
        pred_p = tmp_path / "pred.jsonl"
        bull_p = tmp_path / "bull.jsonl"
        pred_p.write_text("\n".join(json.dumps(r) for r in pred_rows))
        bull_p.write_text("\n".join(json.dumps(r) for r in bull_rows))

        aligned, src_report, al_report = load_and_align(pred_p, bull_p)
        assert al_report.match_rate == 1.0
        assert al_report.matched_rows == 2

    def test_unmatched_rows_get_null_bullpen(self, tmp_path):
        """Rows without a bullpen match should have _has_bull=False."""
        import json
        pred_rows = [
            self._make_pred_row("2025-05-01", "Unmatched Team", "Another Team"),
        ]
        bull_rows = [
            self._make_bull_row("2025-05-01", "Completely Different", "Teams Here"),
        ]
        pred_p = tmp_path / "pred.jsonl"
        bull_p = tmp_path / "bull.jsonl"
        pred_p.write_text(json.dumps(pred_rows[0]))
        bull_p.write_text(json.dumps(bull_rows[0]))

        aligned, _, al_report = load_and_align(pred_p, bull_p)
        assert aligned[0]["_has_bull"] is False
        assert aligned[0]["_bull_delta"] is None
        assert al_report.match_rate == 0.0

    def test_no_duplicate_game_dates_in_alignment(self, tmp_path):
        """Each prediction row should produce exactly one aligned row."""
        import json
        pred_rows = [
            self._make_pred_row("2025-05-01", "Yankees", "Red Sox"),
            self._make_pred_row("2025-05-02", "Yankees", "Red Sox"),
            self._make_pred_row("2025-05-03", "Yankees", "Red Sox"),
        ]
        bull_rows = [
            self._make_bull_row("2025-05-01", "Yankees", "Red Sox"),
            self._make_bull_row("2025-05-02", "Yankees", "Red Sox"),
        ]
        pred_p = tmp_path / "pred.jsonl"
        bull_p = tmp_path / "bull.jsonl"
        pred_p.write_text("\n".join(json.dumps(r) for r in pred_rows))
        bull_p.write_text("\n".join(json.dumps(r) for r in bull_rows))

        aligned, _, _ = load_and_align(pred_p, bull_p)
        assert len(aligned) == len(pred_rows)  # No duplicates

    def test_match_rate_at_least_50_pct_on_consistent_data(self, tmp_path):
        """Aligned dataset should achieve >= 50% when teams match."""
        import json
        games = [
            ("2025-05-01", "Chicago Cubs", "St. Louis Cardinals"),
            ("2025-05-02", "Chicago Cubs", "St. Louis Cardinals"),
            ("2025-05-03", "Chicago Cubs", "St. Louis Cardinals"),
            ("2025-05-04", "NO MATCH", "NOBODY"),
        ]
        pred_rows = [self._make_pred_row(d, a, h) for d, a, h in games]
        bull_rows = [self._make_bull_row(d, a, h) for d, a, h in games[:3]]

        pred_p = tmp_path / "pred.jsonl"
        bull_p = tmp_path / "bull.jsonl"
        pred_p.write_text("\n".join(json.dumps(r) for r in pred_rows))
        bull_p.write_text("\n".join(json.dumps(r) for r in bull_rows))

        _, _, al_report = load_and_align(pred_p, bull_p)
        assert al_report.match_rate >= 0.50

    def test_norm_team_strips_underscores(self):
        assert _norm_team("BOSTON_RED_SOX") == "boston red sox"
        assert _norm_team("Boston Red Sox") == "boston red sox"
        assert _norm_team("boston red sox") == "boston red sox"

    def test_parse_bull_game_id_valid(self):
        gid = "MLB-2025_04_27-1_05_PM-TORONTO-BLUE-JAYS-AT-BOSTON-RED-SOX"
        dt, away, home = _parse_bull_game_id(gid)
        assert dt == "2025-04-27"
        assert "toronto" in away
        assert "boston" in home

    def test_parse_bull_game_id_invalid(self):
        dt, away, home = _parse_bull_game_id("INVALID_ID")
        assert dt is None
        assert away is None
        assert home is None


# ═══════════════════════════════════════════════════════════════════════════════
# § 5  Missing Data Handling
# ═══════════════════════════════════════════════════════════════════════════════

class TestMissingDataHandling:
    """Verify handling of zero-coverage and null bullpen values."""

    def _make_null_alignment() -> AlignmentReport:
        return AlignmentReport(
            total_prediction_rows=100,
            matched_rows=0,
            match_rate=0.0,
            unmatched_rows=100,
            null_bull_rows=0,
            usable_rows=0,
            usable_rate=0.0,
            heavy_fav_total=10,
            heavy_fav_matched=0,
            heavy_fav_usable=0,
            heavy_fav_coverage=0.0,
            high_conf_usable=0,
            high_conf_coverage=0.0,
            alignment_method="test",
        )

    def test_zero_coverage_triggers_blocked_gate(self):
        """0% bullpen coverage must produce BULLPEN_DATA_GAP_BLOCKED."""
        al = self._make_null_alignment()
        hf_sig = _compute_signal([], "heavy_fav", "_is_heavy_fav")
        hc_sig = _compute_signal([], "high_conf", "_is_high_conf")
        hf_ece = _compute_ece_comparison([], "heavy_fav", HEAVY_FAV_THRESHOLD)
        gate, rationale, _ = _recommend_gate(al, hf_sig, hc_sig, hf_ece)
        assert gate == BULLPEN_DATA_GAP_BLOCKED

    def test_insufficient_heavy_fav_triggers_blocked_gate(self):
        """Too few heavy_fav usable rows → BLOCKED."""
        al = AlignmentReport(
            total_prediction_rows=1000,
            matched_rows=900,
            match_rate=0.90,
            unmatched_rows=100,
            null_bull_rows=0,
            usable_rows=900,
            usable_rate=0.90,
            heavy_fav_total=10,
            heavy_fav_matched=3,
            heavy_fav_usable=3,   # < MIN_HEAVY_FAV_WITH_BULL
            heavy_fav_coverage=0.30,
            high_conf_usable=10,
            high_conf_coverage=0.50,
            alignment_method="test",
        )
        hf_sig = _compute_signal([], "heavy_fav", "_is_heavy_fav")
        hc_sig = _compute_signal([], "high_conf", "_is_high_conf")
        hf_ece = _compute_ece_comparison([], "heavy_fav", HEAVY_FAV_THRESHOLD)
        gate, _, _ = _recommend_gate(al, hf_sig, hc_sig, hf_ece)
        assert gate == BULLPEN_DATA_GAP_BLOCKED

    def test_null_bull_rows_have_false_has_bull(self, tmp_path):
        """Rows with None bullpen values should have _has_bull=False."""
        import json
        pred_rows = [
            {
                "game_date": "2025-05-01",
                "away_team": "Yankees",
                "home_team": "Red Sox",
                "model_home_prob": 0.55,
                "market_home_prob_no_vig": 0.52,
                "home_win": 1,
                "game_id": "MLB2025_0001",
            }
        ]
        bull_rows = [
            {
                "game_id": "MLB-2025_05_01-1_05_PM-YANKEES-AT-RED_SOX",
                "bullpen_usage_last_3d_home": None,
                "bullpen_usage_last_3d_away": None,
                "source": "mlb_stats_api_boxscore",
            }
        ]
        pred_p = tmp_path / "pred.jsonl"
        bull_p = tmp_path / "bull.jsonl"
        pred_p.write_text(json.dumps(pred_rows[0]))
        bull_p.write_text(json.dumps(bull_rows[0]))

        aligned, _, al_report = load_and_align(pred_p, bull_p)
        assert aligned[0]["_has_bull"] is False
        assert aligned[0]["_bull_delta"] is None
        assert al_report.null_bull_rows == 1

    def test_empty_signal_returns_nan_stats(self):
        """Empty segment returns NaN stats and has_signal=False."""
        signal = _compute_signal([], "heavy_fav", "_is_heavy_fav")
        assert signal.n == 0
        assert signal.has_signal is False
        assert math.isnan(signal.mean_bull_delta)

    def test_empty_ece_comparison_returns_nan(self):
        """Empty ECE comparison returns NaN values."""
        ece = _compute_ece_comparison([], "heavy_fav", HEAVY_FAV_THRESHOLD)
        assert ece.n == 0
        assert math.isnan(ece.baseline_ece)

    # Allow static method invocation
    _make_null_alignment = staticmethod(_make_null_alignment)


# ═══════════════════════════════════════════════════════════════════════════════
# § 6  Gate Recommendation
# ═══════════════════════════════════════════════════════════════════════════════

class TestGateRecommendation:
    """Verify gate logic under various synthetic scenarios."""

    def _make_good_alignment(
        self,
        heavy_fav_usable: int = 30,
        heavy_fav_total: int = 32,
        heavy_fav_coverage: float = 0.94,
    ) -> AlignmentReport:
        return AlignmentReport(
            total_prediction_rows=1890,
            matched_rows=1800,
            match_rate=0.95,
            unmatched_rows=90,
            null_bull_rows=10,
            usable_rows=1790,
            usable_rate=0.947,
            heavy_fav_total=heavy_fav_total,
            heavy_fav_matched=heavy_fav_usable,
            heavy_fav_usable=heavy_fav_usable,
            heavy_fav_coverage=heavy_fav_coverage,
            high_conf_usable=100,
            high_conf_coverage=0.90,
            alignment_method="test",
        )

    def _make_signal(self, has_signal: bool, delta: float = 0.10) -> MagicMock:
        sig = MagicMock()
        sig.has_signal = has_signal
        sig.tired_fav_n = 10
        sig.tired_fav_win_rate = 0.60
        sig.rested_fav_n = 10
        sig.rested_fav_win_rate = 0.60 + delta if has_signal else 0.60
        sig.fatigue_win_rate_delta = delta if has_signal else 0.001
        sig.n = 30
        return sig

    def _make_ece(self, ece_delta: float) -> MagicMock:
        ece = MagicMock()
        ece.ece_delta = ece_delta
        ece.baseline_ece = 0.08
        ece.bullpen_adjusted_ece = 0.08 - ece_delta
        return ece

    def test_signal_plus_ece_improvement_gives_promising(self):
        al = self._make_good_alignment()
        hf_sig = self._make_signal(has_signal=True, delta=0.10)
        hc_sig = self._make_signal(has_signal=False)
        hf_ece = self._make_ece(ece_delta=0.010)   # improved
        gate, _, _ = _recommend_gate(al, hf_sig, hc_sig, hf_ece)
        assert gate == REAL_BULLPEN_FEATURE_PROMISING

    def test_signal_without_ece_improvement_gives_inconclusive(self):
        al = self._make_good_alignment()
        hf_sig = self._make_signal(has_signal=True, delta=0.10)
        hc_sig = self._make_signal(has_signal=False)
        hf_ece = self._make_ece(ece_delta=0.002)   # not improved enough
        gate, _, _ = _recommend_gate(al, hf_sig, hc_sig, hf_ece)
        assert gate == INCONCLUSIVE

    def test_no_signal_gives_not_promising(self):
        al = self._make_good_alignment()
        hf_sig = self._make_signal(has_signal=False)
        hc_sig = self._make_signal(has_signal=False)
        hf_ece = self._make_ece(ece_delta=0.001)   # flat
        gate, _, _ = _recommend_gate(al, hf_sig, hc_sig, hf_ece)
        assert gate == BULLPEN_FEATURE_NOT_PROMISING

    def test_low_coverage_gives_blocked(self):
        al = self._make_good_alignment(
            heavy_fav_usable=3,
            heavy_fav_total=30,
            heavy_fav_coverage=0.10,
        )
        hf_sig = self._make_signal(has_signal=True)
        hc_sig = self._make_signal(has_signal=False)
        hf_ece = self._make_ece(ece_delta=0.015)
        gate, _, _ = _recommend_gate(al, hf_sig, hc_sig, hf_ece)
        assert gate == BULLPEN_DATA_GAP_BLOCKED

    def test_gate_always_in_valid_set(self):
        """All gate recommendations must be in _VALID_GATES."""
        al = self._make_good_alignment()
        for has_sig in [True, False]:
            for delta in [0.0, 0.005, 0.015]:
                hf_sig = self._make_signal(has_sig, delta)
                hc_sig = self._make_signal(False)
                hf_ece = self._make_ece(delta)
                gate, _, _ = _recommend_gate(al, hf_sig, hc_sig, hf_ece)
                assert gate in _VALID_GATES, f"Gate {gate!r} not in _VALID_GATES"

    def test_gate_rationale_is_non_empty(self):
        al = self._make_good_alignment()
        hf_sig = self._make_signal(has_signal=False)
        hc_sig = self._make_signal(has_signal=False)
        hf_ece = self._make_ece(ece_delta=0.001)
        _, rationale, next_step = _recommend_gate(al, hf_sig, hc_sig, hf_ece)
        assert len(rationale) > 20
        assert len(next_step) > 20


# ═══════════════════════════════════════════════════════════════════════════════
# § 7  End-to-End Integration
# ═══════════════════════════════════════════════════════════════════════════════

_PRED_PATH = Path(_ROOT / "data/mlb_2025/derived/mlb_2025_per_game_predictions.jsonl")
_BULL_PATH = Path(_ROOT / "data/mlb_context/bullpen_usage_3d.jsonl")
_REAL_DATA_AVAILABLE = _PRED_PATH.exists() and _BULL_PATH.exists()


@pytest.mark.skipif(not _REAL_DATA_AVAILABLE, reason="Real data files not available")
class TestEndToEnd:
    """Integration tests using real data files."""

    @pytest.fixture(scope="class")
    def result(self) -> Phase59AcquisitionResult:
        return run_phase59_acquisition(_PRED_PATH, _BULL_PATH)

    def test_result_has_valid_gate(self, result):
        assert result.gate in _VALID_GATES

    def test_safety_flags_unchanged(self, result):
        assert result.candidate_patch_created is False
        assert result.production_modified is False
        assert result.alpha_modified is False
        assert result.diagnostic_only is True

    def test_match_rate_above_90_pct(self, result):
        """With real data, should achieve >= 90% match rate."""
        assert result.alignment.match_rate >= 0.90, (
            f"Match rate {result.alignment.match_rate:.1%} < 90%"
        )

    def test_heavy_fav_usable_above_threshold(self, result):
        """Should have at least MIN_HEAVY_FAV_WITH_BULL usable heavy_fav rows."""
        assert result.alignment.heavy_fav_usable >= MIN_HEAVY_FAV_WITH_BULL, (
            f"heavy_fav_usable={result.alignment.heavy_fav_usable} < {MIN_HEAVY_FAV_WITH_BULL}"
        )

    def test_pit_validated_is_true(self, result):
        assert result.bullpen_source_report.pit_validated is True

    def test_total_sample_size_matches_predictions(self, result):
        """Sample size should match total prediction rows."""
        assert result.sample_size == result.alignment.total_prediction_rows

    def test_audit_hash_non_empty(self, result):
        assert len(result.audit_hash) > 8

    def test_heavy_fav_ece_is_finite(self, result):
        """ECE for heavy_fav with real data should be a finite number."""
        ece = result.heavy_fav_ece_comparison.baseline_ece
        assert not math.isnan(ece), "heavy_fav baseline_ece is NaN"
        assert ece >= 0.0
        assert ece <= 1.0

    def test_bullpen_delta_values_in_realistic_range(self, result):
        """Mean bullpen delta should be near 0 (symmetric distribution)."""
        delta = result.heavy_fav_signal.mean_bull_delta
        if not math.isnan(delta):
            assert -20 < delta < 20, f"Mean bull delta {delta:.2f} out of range"

    def test_phase_version_in_result(self, result):
        assert result.phase_version == PHASE_VERSION

    def test_date_range_nonempty(self, result):
        assert result.date_range_start != ""
        assert result.date_range_end != ""
        assert result.date_range_start <= result.date_range_end

    def test_historical_context_populated(self, result):
        assert result.phase55_gate == "BULLPEN_FEATURE_INVESTIGATION"
        assert result.phase56_gate == "DATA_GAP_REMAINS"
        assert result.phase56_bullpen_available_rate == 0.0
