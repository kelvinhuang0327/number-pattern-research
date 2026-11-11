"""
tests/test_phase56_bullpen_feature_builder.py
==============================================
Phase 56 — Bullpen Feature Builder Tests

覆蓋：
  T-001  Hard rule constants (CANDIDATE_PATCH_CREATED, PRODUCTION_MODIFIED)
  T-002  Feature builder executes with no context (neutral fallback)
  T-003  Fallback is neutral and point-in-time safe
  T-004  Forbidden post-game fields blocked
  T-005  Context with real data produces available=True features
  T-006  Fatigue computation — 3-day window
  T-007  Fatigue computation — 7-day window
  T-008  PIT safety: schedule entries on/after game_date excluded
  T-009  ERA proxy computation
  T-010  Leverage proxy computation
  T-011  Back-to-back count computation
  T-012  Delta = away - home convention
  T-013  PIT validator — passes clean record
  T-014  PIT validator — fails on forbidden field
  T-015  PIT validator — fails on point_in_time_safe=False
  T-016  PIT validator — fails on missing audit_hash
  T-017  PIT validator — batch validation
  T-018  Bullpen adjustment adapter — neutral (no data)
  T-019  Bullpen adjustment adapter — cap <= 0.015
  T-020  Bullpen adjustment — adjusted_prob clamped [0.01, 0.99]
  T-021  Bullpen adjustment — candidate_patch_created=False always
  T-022  Bullpen adjustment — production_modified=False always
  T-023  Bullpen adjustment — REPORT_ONLY when no data
  T-024  Bullpen adjustment — MODEL_AFFECTING when data available
  T-025  Gate cannot be PATCH_GATE_RECHECK (invalid gate)
  T-026  Gate = DATA_GAP_REMAINS when availability < 80%
  T-027  Phase56 evaluation result hard rules
  T-028  Markdown report can be produced
  T-029  JSON serialization of evaluation result
  T-030  Backfill row structure validation
  T-031  Context injection preserves immutable fields
  T-032  Context injection preserves SP features (p0_features)
  T-033  Adjustment injection preserves original_model_home_prob
  T-034  Feature version strings correct
  T-035  All valid gates listed (4 gates only)
"""
from __future__ import annotations

import json
import math
from datetime import date, timedelta
from pathlib import Path

import pytest

# ── Imports ───────────────────────────────────────────────────────────────────
from wbc_backend.features.mlb_bullpen_feature_builder import (
    CANDIDATE_PATCH_CREATED,
    PRODUCTION_MODIFIED,
    DIAGNOSTIC_ONLY,
    FEATURE_VERSION,
    _FORBIDDEN_FIELDS,
    _LEAGUE_AVG_ERA,
    _NEUTRAL_FATIGUE,
    _NEUTRAL_B2B,
    _NEUTRAL_LEVERAGE,
    build_bullpen_features,
    _compute_fatigue_from_schedule,
    _compute_b2b_from_schedule,
    _compute_era_from_schedule,
    _compute_leverage_from_schedule,
)

from wbc_backend.features.mlb_bullpen_pit_validator import (
    validate_bullpen_features,
    validate_bullpen_batch,
    BullpenPitValidationResult,
    CANDIDATE_PATCH_CREATED as PIT_CANDIDATE_PATCH,
    PRODUCTION_MODIFIED as PIT_PRODUCTION_MODIFIED,
)

from wbc_backend.features.mlb_bullpen_feature_injection import (
    apply_bullpen_adjustment,
    BullpenAdjustmentResult,
    _MAX_TOTAL_ADJUSTMENT,
    CANDIDATE_PATCH_CREATED as ADJ_CANDIDATE_PATCH,
    PRODUCTION_MODIFIED as ADJ_PRODUCTION_MODIFIED,
    DIAGNOSTIC_ONLY as ADJ_DIAGNOSTIC_ONLY,
)

from orchestrator.phase56_bullpen_feature_evaluation import (
    CANDIDATE_PATCH_CREATED as EVAL_CANDIDATE_PATCH,
    PRODUCTION_MODIFIED as EVAL_PRODUCTION_MODIFIED,
    DIAGNOSTIC_ONLY as EVAL_DIAGNOSTIC_ONLY,
    DATA_GAP_REMAINS,
    BULLPEN_FEATURE_EFFECTIVE_PAPER_ONLY,
    BULLPEN_FEATURE_NOT_EFFECTIVE,
    COLLECT_MORE_DATA,
    _VALID_GATES,
    Phase56EvaluationResult,
    BullpenAvailabilitySummary,
    MetricsSnapshot56,
    SegmentMetrics56,
    _classify_odds_bucket,
    _classify_confidence,
    _decide_gate,
)


# ═══════════════════════════════════════════════════════════════════════════════
# § T-001  Hard rule constants
# ═══════════════════════════════════════════════════════════════════════════════

class TestHardRuleConstants:
    def test_candidate_patch_created_false_builder(self):
        assert CANDIDATE_PATCH_CREATED is False

    def test_production_modified_false_builder(self):
        assert PRODUCTION_MODIFIED is False

    def test_diagnostic_only_true_builder(self):
        assert DIAGNOSTIC_ONLY is True

    def test_candidate_patch_created_false_pit(self):
        assert PIT_CANDIDATE_PATCH is False

    def test_production_modified_false_pit(self):
        assert PIT_PRODUCTION_MODIFIED is False

    def test_candidate_patch_created_false_adj(self):
        assert ADJ_CANDIDATE_PATCH is False

    def test_production_modified_false_adj(self):
        assert ADJ_PRODUCTION_MODIFIED is False

    def test_diagnostic_only_true_adj(self):
        assert ADJ_DIAGNOSTIC_ONLY is True

    def test_candidate_patch_created_false_eval(self):
        assert EVAL_CANDIDATE_PATCH is False

    def test_production_modified_false_eval(self):
        assert EVAL_PRODUCTION_MODIFIED is False

    def test_diagnostic_only_true_eval(self):
        assert EVAL_DIAGNOSTIC_ONLY is True


# ═══════════════════════════════════════════════════════════════════════════════
# § T-002  Feature builder executes with no context (neutral fallback)
# ═══════════════════════════════════════════════════════════════════════════════

class TestFeatureBuilderNeutralFallback:
    def _make_record(self) -> dict:
        return {
            "game_id": "game_001",
            "game_date": "2025-04-15",
            "home_team": "New York Yankees",
            "away_team": "Boston Red Sox",
        }

    def test_returns_dict(self):
        result = build_bullpen_features(self._make_record(), context=None)
        assert isinstance(result, dict)

    def test_feature_version_is_phase56(self):
        result = build_bullpen_features(self._make_record(), context=None)
        assert "phase56" in result["feature_version"]

    def test_bullpen_feature_available_false_when_no_context(self):
        result = build_bullpen_features(self._make_record(), context=None)
        assert result["bullpen_feature_available"] is False

    def test_all_required_fields_present(self):
        result = build_bullpen_features(self._make_record(), context=None)
        required = [
            "feature_version", "bullpen_feature_available", "point_in_time_safe",
            "audit_hash", "candidate_patch_created", "production_modified",
            "bullpen_feature_source", "fallback_reason",
            "home_bullpen_fatigue_3d", "home_bullpen_fatigue_7d",
            "away_bullpen_fatigue_3d", "away_bullpen_fatigue_7d",
            "bullpen_fatigue_delta_3d", "bullpen_fatigue_delta_7d",
        ]
        for f in required:
            assert f in result, f"Missing field: {f}"

    def test_hard_rule_fields_in_output(self):
        result = build_bullpen_features(self._make_record(), context=None)
        assert result["candidate_patch_created"] is False
        assert result["production_modified"] is False
        assert result["diagnostic_only"] is True


# ═══════════════════════════════════════════════════════════════════════════════
# § T-003  Fallback is neutral and point-in-time safe
# ═══════════════════════════════════════════════════════════════════════════════

class TestNeutralFallback:
    def _build(self) -> dict:
        return build_bullpen_features(
            {"game_id": "g1", "game_date": "2025-05-01", "home_team": "A", "away_team": "B"},
            context=None,
        )

    def test_point_in_time_safe_always_true(self):
        result = self._build()
        assert result["point_in_time_safe"] is True

    def test_home_fatigue_3d_is_neutral(self):
        result = self._build()
        assert result["home_bullpen_fatigue_3d"] == _NEUTRAL_FATIGUE

    def test_away_fatigue_3d_is_neutral(self):
        result = self._build()
        assert result["away_bullpen_fatigue_3d"] == _NEUTRAL_FATIGUE

    def test_delta_3d_is_zero(self):
        result = self._build()
        assert result["bullpen_fatigue_delta_3d"] == 0.0

    def test_home_b2b_is_neutral(self):
        result = self._build()
        assert result["home_reliever_b2b_count"] == _NEUTRAL_B2B

    def test_fallback_reason_is_no_data(self):
        result = self._build()
        assert "no_relief_pitcher_usage_data" in result["fallback_reason"]

    def test_estimated_is_true_when_fallback(self):
        result = self._build()
        assert result["estimated"] is True

    def test_audit_hash_is_nonempty(self):
        result = self._build()
        assert len(result["audit_hash"]) > 0

    def test_source_is_neutral_fallback(self):
        result = self._build()
        assert "fallback" in result["bullpen_feature_source"]


# ═══════════════════════════════════════════════════════════════════════════════
# § T-004  Forbidden post-game fields blocked
# ═══════════════════════════════════════════════════════════════════════════════

class TestLeakageGuard:
    def test_forbidden_field_home_win_ignored(self):
        record = {
            "game_id": "g1",
            "game_date": "2025-06-01",
            "home_team": "A",
            "away_team": "B",
            "home_win": 1,  # FORBIDDEN
        }
        # Should not raise; forbidden field is ignored
        result = build_bullpen_features(record, context=None)
        assert result is not None
        # home_win must NOT appear in result
        assert "home_win" not in result

    def test_forbidden_field_final_score_ignored(self):
        record = {
            "game_id": "g2",
            "game_date": "2025-06-01",
            "home_team": "A",
            "away_team": "B",
            "final_score": "5-3",  # FORBIDDEN
        }
        result = build_bullpen_features(record, context=None)
        assert "final_score" not in result

    def test_forbidden_field_does_not_affect_features(self):
        record_clean = {
            "game_id": "g3",
            "game_date": "2025-06-01",
            "home_team": "A",
            "away_team": "B",
        }
        record_dirty = dict(record_clean)
        record_dirty["home_win"] = 1
        record_dirty["post_game_stats"] = {"era": 2.5}

        result_clean = build_bullpen_features(record_clean, context=None)
        result_dirty = build_bullpen_features(record_dirty, context=None)

        # Features should be identical (forbidden fields ignored)
        assert result_clean["bullpen_fatigue_delta_3d"] == result_dirty["bullpen_fatigue_delta_3d"]
        assert result_clean["bullpen_feature_available"] == result_dirty["bullpen_feature_available"]

    def test_all_forbidden_fields_defined(self):
        assert len(_FORBIDDEN_FIELDS) >= 6
        assert "home_win" in _FORBIDDEN_FIELDS
        assert "post_game_stats" in _FORBIDDEN_FIELDS
        assert "box_score" in _FORBIDDEN_FIELDS


# ═══════════════════════════════════════════════════════════════════════════════
# § T-005  Context with real data produces available=True features
# ═══════════════════════════════════════════════════════════════════════════════

class TestContextWithRealData:
    def _make_schedule(self, game_date: str, days_back: int) -> list[dict]:
        """Create schedule entries before game_date."""
        d = date.fromisoformat(game_date)
        entries = []
        for i in range(1, days_back + 1):
            g = d - timedelta(days=i)
            entries.append({
                "game_date": g.isoformat(),
                "bullpen_outs": 6.0,
                "bullpen_earned_runs": 1.0,
                "bullpen_appearances": 3,
                "high_leverage_appearances": 1,
            })
        return entries

    def test_available_true_with_home_and_away_schedule(self):
        game_date = "2025-05-10"
        context = {
            "home_schedule": self._make_schedule(game_date, 3),
            "away_schedule": self._make_schedule(game_date, 3),
        }
        result = build_bullpen_features(
            {"game_id": "g1", "game_date": game_date, "home_team": "A", "away_team": "B"},
            context=context,
        )
        assert result["bullpen_feature_available"] is True

    def test_available_false_when_only_one_team_has_data(self):
        game_date = "2025-05-10"
        context = {
            "home_schedule": self._make_schedule(game_date, 3),
            "away_schedule": [],   # no away data
        }
        result = build_bullpen_features(
            {"game_id": "g1", "game_date": game_date, "home_team": "A", "away_team": "B"},
            context=context,
        )
        # Both home and away must have data for available=True
        assert result["bullpen_feature_available"] is False

    def test_fatigue_nonzero_with_data(self):
        game_date = "2025-05-10"
        context = {
            "home_schedule": self._make_schedule(game_date, 3),
            "away_schedule": self._make_schedule(game_date, 3),
        }
        result = build_bullpen_features(
            {"game_id": "g1", "game_date": game_date, "home_team": "A", "away_team": "B"},
            context=context,
        )
        assert result["home_bullpen_fatigue_3d"] > 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# § T-006  Fatigue computation — 3-day window
# ═══════════════════════════════════════════════════════════════════════════════

class TestFatigueComputation3d:
    def test_no_schedule_returns_neutral_unavailable(self):
        val, avail = _compute_fatigue_from_schedule([], "2025-05-01", 3)
        assert val == _NEUTRAL_FATIGUE
        assert avail is False

    def test_entries_within_3d_counted(self):
        game_date = "2025-05-10"
        schedule = [
            {"game_date": "2025-05-09", "bullpen_outs": 10.0},  # 1 day before
            {"game_date": "2025-05-08", "bullpen_outs": 10.0},  # 2 days before
            {"game_date": "2025-05-07", "bullpen_outs": 10.0},  # 3 days before
        ]
        val, avail = _compute_fatigue_from_schedule(schedule, game_date, 3)
        assert avail is True
        assert val > 0.0

    def test_entries_outside_3d_excluded(self):
        game_date = "2025-05-10"
        schedule = [
            {"game_date": "2025-05-06", "bullpen_outs": 99.0},  # 4 days = excluded
        ]
        val, avail = _compute_fatigue_from_schedule(schedule, game_date, 3)
        assert avail is False   # no data in window

    def test_entry_on_game_date_excluded_pit_safe(self):
        game_date = "2025-05-10"
        schedule = [
            {"game_date": "2025-05-10", "bullpen_outs": 99.0},  # same day = PIT violation
            {"game_date": "2025-05-09", "bullpen_outs": 5.0},
        ]
        # Same-day entry excluded due to PIT rule
        val_all, avail_all = _compute_fatigue_from_schedule(schedule, game_date, 3)
        schedule_clean = [{"game_date": "2025-05-09", "bullpen_outs": 5.0}]
        val_clean, avail_clean = _compute_fatigue_from_schedule(schedule_clean, game_date, 3)
        assert val_all == val_clean  # Same result — today's game excluded

    def test_fatigue_capped_at_max(self):
        game_date = "2025-05-10"
        schedule = [
            {"game_date": "2025-05-09", "bullpen_outs": 1000.0},  # huge number
        ]
        val, avail = _compute_fatigue_from_schedule(schedule, game_date, 3)
        assert val <= 1.0   # _FATIGUE_CAP = 1.0

    def test_invalid_date_returns_neutral(self):
        val, avail = _compute_fatigue_from_schedule(
            [{"game_date": "bad-date", "bullpen_outs": 10.0}],
            "2025-05-10", 3
        )
        assert avail is False


# ═══════════════════════════════════════════════════════════════════════════════
# § T-007  Fatigue computation — 7-day window
# ═══════════════════════════════════════════════════════════════════════════════

class TestFatigueComputation7d:
    def test_7d_includes_more_entries_than_3d(self):
        game_date = "2025-05-10"
        schedule = [
            {"game_date": "2025-05-09", "bullpen_outs": 5.0},  # within both
            {"game_date": "2025-05-05", "bullpen_outs": 5.0},  # within 7d, not 3d
        ]
        val_3d, _ = _compute_fatigue_from_schedule(schedule, game_date, 3)
        val_7d, _ = _compute_fatigue_from_schedule(schedule, game_date, 7)
        assert val_7d >= val_3d  # 7d should count more


# ═══════════════════════════════════════════════════════════════════════════════
# § T-008  PIT safety: schedule entries on/after game_date excluded
# ═══════════════════════════════════════════════════════════════════════════════

class TestPITSafety:
    def test_future_entry_excluded(self):
        game_date = "2025-05-10"
        schedule_future = [{"game_date": "2025-05-11", "bullpen_outs": 99.0}]
        schedule_past = [{"game_date": "2025-05-09", "bullpen_outs": 5.0}]
        val_f, avail_f = _compute_fatigue_from_schedule(schedule_future, game_date, 3)
        val_p, avail_p = _compute_fatigue_from_schedule(schedule_past, game_date, 3)
        assert avail_f is False   # future entry excluded
        assert avail_p is True    # past entry included

    def test_same_day_entry_excluded(self):
        game_date = "2025-05-10"
        schedule = [{"game_date": game_date, "bullpen_outs": 99.0}]
        val, avail = _compute_fatigue_from_schedule(schedule, game_date, 3)
        assert avail is False  # same-day entry excluded (strict <)


# ═══════════════════════════════════════════════════════════════════════════════
# § T-009  ERA proxy computation
# ═══════════════════════════════════════════════════════════════════════════════

class TestERAProxy:
    def test_no_data_returns_league_avg_unavailable(self):
        val, avail = _compute_era_from_schedule([], "2025-05-01", 14)
        assert val == _LEAGUE_AVG_ERA
        assert avail is False

    def test_era_computed_correctly(self):
        game_date = "2025-05-10"
        # 3 ER over 9 outs (3 IP) = ERA 9.0
        schedule = [{"game_date": "2025-05-09", "bullpen_outs": 9.0, "bullpen_earned_runs": 3.0}]
        val, avail = _compute_era_from_schedule(schedule, game_date, 14)
        assert avail is True
        assert abs(val - 9.0) < 0.1

    def test_era_clamped_to_reasonable_range(self):
        game_date = "2025-05-10"
        schedule = [{"game_date": "2025-05-09", "bullpen_outs": 1.0, "bullpen_earned_runs": 100.0}]
        val, avail = _compute_era_from_schedule(schedule, game_date, 14)
        assert val <= 15.0  # clamped at max

    def test_zero_outs_returns_league_avg_unavailable(self):
        game_date = "2025-05-10"
        schedule = [{"game_date": "2025-05-09", "bullpen_outs": 0.0, "bullpen_earned_runs": 1.0}]
        val, avail = _compute_era_from_schedule(schedule, game_date, 14)
        assert val == _LEAGUE_AVG_ERA
        assert avail is False


# ═══════════════════════════════════════════════════════════════════════════════
# § T-010  Leverage proxy computation
# ═══════════════════════════════════════════════════════════════════════════════

class TestLeverageProxy:
    def test_no_data_returns_neutral_unavailable(self):
        val, avail = _compute_leverage_from_schedule([], "2025-05-01", 7)
        assert val == _NEUTRAL_LEVERAGE
        assert avail is False

    def test_leverage_ratio_computed_correctly(self):
        game_date = "2025-05-10"
        # 2 high-leverage out of 4 total = 0.5 ratio
        schedule = [{
            "game_date": "2025-05-09",
            "bullpen_appearances": 4,
            "high_leverage_appearances": 2,
        }]
        val, avail = _compute_leverage_from_schedule(schedule, game_date, 7)
        assert avail is True
        assert abs(val - 0.5) < 0.01

    def test_zero_appearances_returns_neutral(self):
        game_date = "2025-05-10"
        schedule = [{"game_date": "2025-05-09", "bullpen_appearances": 0, "high_leverage_appearances": 0}]
        val, avail = _compute_leverage_from_schedule(schedule, game_date, 7)
        assert avail is False


# ═══════════════════════════════════════════════════════════════════════════════
# § T-011  Back-to-back count computation
# ═══════════════════════════════════════════════════════════════════════════════

class TestB2BCount:
    def test_no_data_returns_neutral_unavailable(self):
        val, avail = _compute_b2b_from_schedule([], "2025-05-10")
        assert val == _NEUTRAL_B2B
        assert avail is False

    def test_recent_game_with_outs_counts(self):
        game_date = "2025-05-10"
        schedule = [
            {"game_date": "2025-05-09", "bullpen_outs": 6.0},
            {"game_date": "2025-05-08", "bullpen_outs": 6.0},
        ]
        val, avail = _compute_b2b_from_schedule(schedule, game_date)
        assert avail is True
        assert val >= 1

    def test_game_3d_ago_excluded_from_b2b(self):
        game_date = "2025-05-10"
        schedule = [{"game_date": "2025-05-07", "bullpen_outs": 6.0}]  # 3 days ago
        val, avail = _compute_b2b_from_schedule(schedule, game_date)
        assert avail is False   # 3 days ago > 2-day window


# ═══════════════════════════════════════════════════════════════════════════════
# § T-012  Delta = away - home convention
# ═══════════════════════════════════════════════════════════════════════════════

class TestDeltaConvention:
    def test_positive_delta_means_away_more_fatigued(self):
        game_date = "2025-05-10"
        # Away has more fatigue (3 games in 3d) vs home (1 game)
        home_schedule = [{"game_date": "2025-05-09", "bullpen_outs": 3.0}]
        away_schedule = [
            {"game_date": "2025-05-09", "bullpen_outs": 3.0},
            {"game_date": "2025-05-08", "bullpen_outs": 3.0},
            {"game_date": "2025-05-07", "bullpen_outs": 3.0},
        ]
        context = {"home_schedule": home_schedule, "away_schedule": away_schedule}
        result = build_bullpen_features(
            {"game_id": "g1", "game_date": game_date, "home_team": "A", "away_team": "B"},
            context=context,
        )
        # delta = away - home: away more fatigued → positive delta
        assert result["bullpen_fatigue_delta_3d"] > 0.0

    def test_negative_delta_means_home_more_fatigued(self):
        game_date = "2025-05-10"
        home_schedule = [
            {"game_date": "2025-05-09", "bullpen_outs": 9.0},
            {"game_date": "2025-05-08", "bullpen_outs": 9.0},
            {"game_date": "2025-05-07", "bullpen_outs": 9.0},
        ]
        away_schedule = [{"game_date": "2025-05-09", "bullpen_outs": 3.0}]
        context = {"home_schedule": home_schedule, "away_schedule": away_schedule}
        result = build_bullpen_features(
            {"game_id": "g2", "game_date": game_date, "home_team": "A", "away_team": "B"},
            context=context,
        )
        # home more fatigued → delta negative
        assert result["bullpen_fatigue_delta_3d"] < 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# § T-013  PIT validator — passes clean record
# ═══════════════════════════════════════════════════════════════════════════════

class TestPITValidatorClean:
    def _make_valid_record(self) -> dict:
        return {
            "feature_version": "phase56_bullpen_v1",
            "bullpen_feature_available": False,
            "bullpen_feature_source": "neutral_fallback",
            "fallback_reason": "no_relief_pitcher_usage_data",
            "point_in_time_safe": True,
            "audit_hash": "sha256:abc123def456",
            "candidate_patch_created": False,
            "production_modified": False,
            "diagnostic_only": True,
        }

    def test_valid_record_passes(self):
        rec = self._make_valid_record()
        result = validate_bullpen_features(rec, "2025-05-01")
        assert result.is_safe is True

    def test_valid_record_has_no_violations(self):
        rec = self._make_valid_record()
        result = validate_bullpen_features(rec, "2025-05-01")
        assert result.violations == []

    def test_result_is_bullpen_pit_validation_result(self):
        rec = self._make_valid_record()
        result = validate_bullpen_features(rec)
        assert isinstance(result, BullpenPitValidationResult)

    def test_result_hard_rules_always_false(self):
        rec = self._make_valid_record()
        result = validate_bullpen_features(rec)
        assert result.candidate_patch_created is False
        assert result.production_modified is False


# ═══════════════════════════════════════════════════════════════════════════════
# § T-014  PIT validator — fails on forbidden field
# ═══════════════════════════════════════════════════════════════════════════════

class TestPITValidatorForbiddenField:
    def _make_base_record(self) -> dict:
        return {
            "feature_version": "phase56_bullpen_v1",
            "bullpen_feature_available": False,
            "bullpen_feature_source": "neutral_fallback",
            "fallback_reason": "no_relief_pitcher_usage_data",
            "point_in_time_safe": True,
            "audit_hash": "sha256:abc123",
            "candidate_patch_created": False,
            "production_modified": False,
        }

    def test_home_win_present_fails(self):
        rec = self._make_base_record()
        rec["home_win"] = 1
        result = validate_bullpen_features(rec)
        assert result.is_safe is False
        assert any("home_win" in v for v in result.violations)

    def test_post_game_stats_present_fails(self):
        rec = self._make_base_record()
        rec["post_game_stats"] = {"era": 3.5}
        result = validate_bullpen_features(rec)
        assert result.is_safe is False

    def test_final_score_present_fails(self):
        rec = self._make_base_record()
        rec["final_score"] = "5-3"
        result = validate_bullpen_features(rec)
        assert result.is_safe is False


# ═══════════════════════════════════════════════════════════════════════════════
# § T-015  PIT validator — fails on point_in_time_safe=False
# ═══════════════════════════════════════════════════════════════════════════════

class TestPITValidatorFlagFalse:
    def test_pit_flag_false_fails(self):
        rec = {
            "feature_version": "phase56_bullpen_v1",
            "bullpen_feature_available": False,
            "bullpen_feature_source": "neutral_fallback",
            "fallback_reason": "test",
            "point_in_time_safe": False,  # VIOLATION
            "audit_hash": "sha256:abc",
            "candidate_patch_created": False,
            "production_modified": False,
        }
        result = validate_bullpen_features(rec)
        assert result.is_safe is False
        assert result.pit_flag_correct is False

    def test_pit_flag_missing_fails(self):
        rec = {
            "feature_version": "phase56_bullpen_v1",
            "bullpen_feature_available": False,
            "bullpen_feature_source": "neutral_fallback",
            "fallback_reason": "test",
            # point_in_time_safe missing → None → False
            "audit_hash": "sha256:abc",
            "candidate_patch_created": False,
            "production_modified": False,
        }
        result = validate_bullpen_features(rec)
        assert result.is_safe is False


# ═══════════════════════════════════════════════════════════════════════════════
# § T-016  PIT validator — fails on missing audit_hash
# ═══════════════════════════════════════════════════════════════════════════════

class TestPITValidatorMissingHash:
    def test_empty_audit_hash_fails(self):
        rec = {
            "feature_version": "phase56_bullpen_v1",
            "bullpen_feature_available": False,
            "bullpen_feature_source": "neutral_fallback",
            "fallback_reason": "test",
            "point_in_time_safe": True,
            "audit_hash": "",  # EMPTY
            "candidate_patch_created": False,
            "production_modified": False,
        }
        result = validate_bullpen_features(rec)
        assert result.is_safe is False
        assert result.audit_hash_present is False


# ═══════════════════════════════════════════════════════════════════════════════
# § T-017  PIT validator — batch validation
# ═══════════════════════════════════════════════════════════════════════════════

class TestBatchValidation:
    def _make_valid(self) -> dict:
        return {
            "feature_version": "phase56_bullpen_v1",
            "bullpen_feature_available": False,
            "bullpen_feature_source": "neutral_fallback",
            "fallback_reason": "no_data",
            "point_in_time_safe": True,
            "audit_hash": "sha256:abc",
            "candidate_patch_created": False,
            "production_modified": False,
        }

    def test_batch_all_valid(self):
        records = [self._make_valid() for _ in range(10)]
        result = validate_bullpen_batch(records)
        assert result["safe_count"] == 10
        assert result["violation_count"] == 0
        assert result["pit_safe_rate"] == 1.0

    def test_batch_with_one_invalid(self):
        records = [self._make_valid() for _ in range(9)]
        bad = self._make_valid()
        bad["point_in_time_safe"] = False
        records.append(bad)
        result = validate_bullpen_batch(records)
        assert result["violation_count"] == 1
        assert result["safe_count"] == 9

    def test_batch_empty_returns_zero(self):
        result = validate_bullpen_batch([])
        assert result["total"] == 0
        assert result["safe_count"] == 0

    def test_batch_hard_rules_always_false(self):
        result = validate_bullpen_batch([])
        assert result["candidate_patch_created"] is False
        assert result["production_modified"] is False


# ═══════════════════════════════════════════════════════════════════════════════
# § T-018  Bullpen adjustment adapter — neutral (no data)
# ═══════════════════════════════════════════════════════════════════════════════

class TestAdjustmentNeutral:
    def test_zero_adjustment_when_no_data(self):
        features = {"bullpen_feature_available": False}
        result = apply_bullpen_adjustment(0.6, features)
        assert result.bullpen_adjustment == 0.0

    def test_prob_unchanged_when_no_data(self):
        features = {"bullpen_feature_available": False}
        result = apply_bullpen_adjustment(0.65, features)
        assert result.adjusted_model_home_prob == result.original_model_home_prob

    def test_fallback_applied_true_when_no_data(self):
        features = {"bullpen_feature_available": False}
        result = apply_bullpen_adjustment(0.55, features)
        assert result.fallback_applied is True

    def test_returns_bullpen_adjustment_result(self):
        result = apply_bullpen_adjustment(0.5, {})
        assert isinstance(result, BullpenAdjustmentResult)


# ═══════════════════════════════════════════════════════════════════════════════
# § T-019  Bullpen adjustment adapter — cap <= 0.015
# ═══════════════════════════════════════════════════════════════════════════════

class TestAdjustmentCap:
    def test_adjustment_cap_constant(self):
        assert _MAX_TOTAL_ADJUSTMENT == 0.015

    def test_abs_adjustment_never_exceeds_cap(self):
        # Use very extreme fatigue delta to trigger cap
        features = {
            "bullpen_feature_available": True,
            "bullpen_fatigue_delta_3d": 100.0,   # extreme
            "home_bullpen_recent_era_proxy": 0.0,
            "away_bullpen_recent_era_proxy": 15.0,
            "home_bullpen_era_available": True,
            "away_bullpen_era_available": True,
            "home_late_game_leverage_usage_proxy": 0.9,
        }
        result = apply_bullpen_adjustment(0.5, features)
        assert abs(result.bullpen_adjustment) <= _MAX_TOTAL_ADJUSTMENT + 1e-9

    def test_normal_features_within_cap(self):
        features = {
            "bullpen_feature_available": True,
            "bullpen_fatigue_delta_3d": 0.2,
            "home_bullpen_era_available": False,
            "away_bullpen_era_available": False,
        }
        result = apply_bullpen_adjustment(0.55, features)
        assert abs(result.bullpen_adjustment) <= _MAX_TOTAL_ADJUSTMENT + 1e-9


# ═══════════════════════════════════════════════════════════════════════════════
# § T-020  Bullpen adjustment — adjusted_prob clamped [0.01, 0.99]
# ═══════════════════════════════════════════════════════════════════════════════

class TestAdjustmentClamp:
    def test_prob_never_below_001(self):
        features = {
            "bullpen_feature_available": True,
            "bullpen_fatigue_delta_3d": -100.0,  # very negative → away at home advantage → reduce home prob
            "home_bullpen_era_available": False,
            "away_bullpen_era_available": False,
        }
        result = apply_bullpen_adjustment(0.01, features)
        assert result.adjusted_model_home_prob >= 0.01

    def test_prob_never_above_099(self):
        features = {
            "bullpen_feature_available": True,
            "bullpen_fatigue_delta_3d": 100.0,
            "home_bullpen_era_available": False,
            "away_bullpen_era_available": False,
        }
        result = apply_bullpen_adjustment(0.99, features)
        assert result.adjusted_model_home_prob <= 0.99

    def test_prob_stays_in_valid_range_always(self):
        for prob in [0.01, 0.1, 0.5, 0.9, 0.99]:
            features = {"bullpen_feature_available": False}
            result = apply_bullpen_adjustment(prob, features)
            assert 0.01 <= result.adjusted_model_home_prob <= 0.99


# ═══════════════════════════════════════════════════════════════════════════════
# § T-021/022  Hard rules always enforced in adjustment result
# ═══════════════════════════════════════════════════════════════════════════════

class TestAdjustmentHardRules:
    def test_candidate_patch_created_false(self):
        result = apply_bullpen_adjustment(0.6, {})
        assert result.candidate_patch_created is False

    def test_production_modified_false(self):
        result = apply_bullpen_adjustment(0.6, {})
        assert result.production_modified is False

    def test_diagnostic_only_true(self):
        result = apply_bullpen_adjustment(0.6, {})
        assert result.diagnostic_only is True


# ═══════════════════════════════════════════════════════════════════════════════
# § T-023  Adjustment — REPORT_ONLY when no data
# ═══════════════════════════════════════════════════════════════════════════════

class TestAdjustmentEffectMode:
    def test_report_only_when_no_data(self):
        result = apply_bullpen_adjustment(0.6, {"bullpen_feature_available": False})
        assert result.feature_effect_mode == "REPORT_ONLY"

    def test_report_only_when_zero_adjustment_despite_data(self):
        # Data available but zero fatigue delta → no adjustment
        features = {
            "bullpen_feature_available": True,
            "bullpen_fatigue_delta_3d": 0.0,  # zero → no adj from fatigue
            "home_bullpen_era_available": False,
            "away_bullpen_era_available": False,
            "home_late_game_leverage_usage_proxy": 0.0,
        }
        result = apply_bullpen_adjustment(0.5, features)
        assert result.feature_effect_mode == "REPORT_ONLY"


# § T-024  MODEL_AFFECTING when data produces nonzero adjustment
class TestModelAffecting:
    def test_model_affecting_when_fatigue_delta_large(self):
        features = {
            "bullpen_feature_available": True,
            "bullpen_fatigue_delta_3d": 0.5,   # > threshold → adjustment
            "home_bullpen_era_available": False,
            "away_bullpen_era_available": False,
        }
        result = apply_bullpen_adjustment(0.5, features)
        assert result.feature_effect_mode == "MODEL_AFFECTING"
        assert abs(result.bullpen_adjustment) > 0


# ═══════════════════════════════════════════════════════════════════════════════
# § T-025  Gate cannot be PATCH_GATE_RECHECK (invalid gate)
# ═══════════════════════════════════════════════════════════════════════════════

class TestGateValidity:
    def test_valid_gates_exactly_four(self):
        assert len(_VALID_GATES) == 4

    def test_patch_gate_not_valid(self):
        assert "PATCH_GATE_RECHECK" not in _VALID_GATES

    def test_all_valid_gates_defined(self):
        expected = {
            "BULLPEN_FEATURE_EFFECTIVE_PAPER_ONLY",
            "BULLPEN_FEATURE_NOT_EFFECTIVE",
            "DATA_GAP_REMAINS",
            "COLLECT_MORE_DATA",
        }
        assert _VALID_GATES == expected


# ═══════════════════════════════════════════════════════════════════════════════
# § T-026  Gate = DATA_GAP_REMAINS when availability < 80%
# ═══════════════════════════════════════════════════════════════════════════════

class TestGateDataGap:
    def _make_availability(self, rate: float, total: int = 1000) -> BullpenAvailabilitySummary:
        count = int(rate * total)
        return BullpenAvailabilitySummary(
            total_rows=total,
            available_count=count,
            availability_rate=rate,
        )

    def _make_metrics(self) -> MetricsSnapshot56:
        return MetricsSnapshot56(
            source="baseline", n=500, brier=0.25, bss_vs_market=0.01, ece=0.05
        )

    def test_zero_availability_gives_data_gap(self):
        gate, _ = _decide_gate(
            availability=self._make_availability(0.0),
            baseline_metrics=self._make_metrics(),
            phase56_metrics=self._make_metrics(),
            segment_metrics=[],
            failure_count_delta=0,
        )
        assert gate == DATA_GAP_REMAINS

    def test_79_pct_availability_gives_data_gap(self):
        gate, _ = _decide_gate(
            availability=self._make_availability(0.79),
            baseline_metrics=self._make_metrics(),
            phase56_metrics=self._make_metrics(),
            segment_metrics=[],
            failure_count_delta=0,
        )
        assert gate == DATA_GAP_REMAINS

    def test_80_pct_availability_does_not_give_data_gap(self):
        gate, _ = _decide_gate(
            availability=self._make_availability(0.80),
            baseline_metrics=self._make_metrics(),
            phase56_metrics=self._make_metrics(),
            segment_metrics=[],
            failure_count_delta=0,
        )
        assert gate != DATA_GAP_REMAINS


# ═══════════════════════════════════════════════════════════════════════════════
# § T-027  Phase56 evaluation result hard rules
# ═══════════════════════════════════════════════════════════════════════════════

class TestEvaluationResultHardRules:
    def _make_result(self, gate: str) -> Phase56EvaluationResult:
        return Phase56EvaluationResult(
            run_id="test123",
            generated_at="2026-05-05T00:00:00Z",
            gate_recommendation=gate,
            candidate_patch_created=False,
            production_modified=False,
            diagnostic_only=True,
        )

    def test_post_init_validates_gate(self):
        with pytest.raises(AssertionError):
            Phase56EvaluationResult(
                run_id="x",
                generated_at="2026-05-05T00:00:00Z",
                gate_recommendation="INVALID_GATE",
                candidate_patch_created=False,
                production_modified=False,
                diagnostic_only=True,
            )

    def test_post_init_rejects_candidate_patch(self):
        with pytest.raises(AssertionError):
            Phase56EvaluationResult(
                run_id="x",
                generated_at="2026-05-05T00:00:00Z",
                gate_recommendation=DATA_GAP_REMAINS,
                candidate_patch_created=True,   # VIOLATION
                production_modified=False,
                diagnostic_only=True,
            )

    def test_post_init_rejects_production_modified(self):
        with pytest.raises(AssertionError):
            Phase56EvaluationResult(
                run_id="x",
                generated_at="2026-05-05T00:00:00Z",
                gate_recommendation=DATA_GAP_REMAINS,
                candidate_patch_created=False,
                production_modified=True,   # VIOLATION
                diagnostic_only=True,
            )

    def test_valid_result_creates_without_error(self):
        result = self._make_result(DATA_GAP_REMAINS)
        assert result.gate_recommendation == DATA_GAP_REMAINS
        assert result.candidate_patch_created is False
        assert result.production_modified is False

    @pytest.mark.parametrize("gate", [
        DATA_GAP_REMAINS,
        BULLPEN_FEATURE_EFFECTIVE_PAPER_ONLY,
        BULLPEN_FEATURE_NOT_EFFECTIVE,
        COLLECT_MORE_DATA,
    ])
    def test_all_valid_gates_accepted(self, gate: str):
        result = self._make_result(gate)
        assert result.gate_recommendation == gate


# ═══════════════════════════════════════════════════════════════════════════════
# § T-028  Markdown report can be produced (integration-lite)
# ═══════════════════════════════════════════════════════════════════════════════

class TestMarkdownReport:
    def test_result_to_dict_is_serializable(self):
        result = Phase56EvaluationResult(
            run_id="test",
            generated_at="2026-05-05T00:00:00Z",
            gate_recommendation=DATA_GAP_REMAINS,
            candidate_patch_created=False,
            production_modified=False,
            diagnostic_only=True,
        )
        d = result.to_dict()
        # Should be JSON-serializable
        json_str = json.dumps(d, default=str)
        assert isinstance(json_str, str)
        assert "DATA_GAP_REMAINS" in json_str

    def test_to_dict_contains_hard_rule_fields(self):
        result = Phase56EvaluationResult(
            run_id="test",
            generated_at="2026-05-05T00:00:00Z",
            gate_recommendation=DATA_GAP_REMAINS,
            candidate_patch_created=False,
            production_modified=False,
            diagnostic_only=True,
        )
        d = result.to_dict()
        assert d["candidate_patch_created"] is False
        assert d["production_modified"] is False
        assert d["diagnostic_only"] is True


# ═══════════════════════════════════════════════════════════════════════════════
# § T-029  JSON serialization of evaluation result
# ═══════════════════════════════════════════════════════════════════════════════

class TestJSONSerialization:
    def test_segment_metrics_serializable(self):
        seg = SegmentMetrics56(
            segment_key="odds_bucket:heavy_favorite",
            segment_type="odds_bucket",
            segment_label="heavy_favorite",
            n=100,
            baseline_bss=-0.05,
            phase56_bss=-0.03,
            delta_bss=0.02,
            baseline_ece=0.09,
            phase56_ece=0.08,
            delta_ece=-0.01,
            is_failure_segment=True,
            improvement_label="IMPROVED",
        )
        d = {
            "segment_key": seg.segment_key,
            "delta_bss": seg.delta_bss,
            "is_failure_segment": seg.is_failure_segment,
        }
        json_str = json.dumps(d)
        assert "heavy_favorite" in json_str


# ═══════════════════════════════════════════════════════════════════════════════
# § T-030  Backfill row structure validation
# ═══════════════════════════════════════════════════════════════════════════════

class TestBackfillRowStructure:
    def test_build_bullpen_features_has_all_per_spec_fields(self):
        record = {
            "game_id": "2025_001",
            "game_date": "2025-04-01",
            "home_team": "New York Yankees",
            "away_team": "Boston Red Sox",
        }
        result = build_bullpen_features(record, context=None)
        required_per_spec = [
            "home_bullpen_fatigue_3d", "away_bullpen_fatigue_3d",
            "home_bullpen_fatigue_7d", "away_bullpen_fatigue_7d",
            "home_reliever_b2b_count", "away_reliever_b2b_count",
            "home_bullpen_recent_era_proxy", "away_bullpen_recent_era_proxy",
            "home_late_game_leverage_usage_proxy", "away_late_game_leverage_usage_proxy",
            "bullpen_fatigue_delta_3d", "bullpen_fatigue_delta_7d",
            "bullpen_feature_available", "bullpen_feature_source",
            "point_in_time_safe", "fallback_reason", "audit_hash",
            "candidate_patch_created", "production_modified",
        ]
        for field in required_per_spec:
            assert field in result, f"Missing spec field: {field}"


# ═══════════════════════════════════════════════════════════════════════════════
# § T-031  Context injection preserves immutable fields
# ═══════════════════════════════════════════════════════════════════════════════

class TestContextInjectionPreservesImmutable:
    def test_immutable_fields_unchanged(self):
        from scripts.run_phase56_inject_bullpen_to_phase52 import inject_bullpen_to_phase52_row

        phase52_row = {
            "game_id": "g001",
            "game_date": "2025-04-15",
            "home_team": "NYY",
            "away_team": "BOS",
            "home_win": 1,
            "model_home_prob": 0.62,
            "market_home_prob_no_vig": 0.58,
            "schema_version": "v1",
        }
        bullpen_rec = None  # no match → fallback

        out = inject_bullpen_to_phase52_row(phase52_row, bullpen_rec)

        # Immutable fields must be unchanged
        assert out["game_id"] == "g001"
        assert out["home_win"] == 1
        assert out["model_home_prob"] == 0.62  # context injection doesn't change prob
        assert out["market_home_prob_no_vig"] == 0.58


# ═══════════════════════════════════════════════════════════════════════════════
# § T-032  Context injection preserves SP features (p0_features)
# ═══════════════════════════════════════════════════════════════════════════════

class TestContextInjectionPreservesSP:
    def test_p0_features_preserved(self):
        from scripts.run_phase56_inject_bullpen_to_phase52 import inject_bullpen_to_phase52_row

        phase52_row = {
            "game_id": "g002",
            "game_date": "2025-04-16",
            "home_team": "A",
            "away_team": "B",
            "home_win": 0,
            "model_home_prob": 0.45,
            "market_home_prob_no_vig": 0.50,
            "p0_features": {
                "sp_fip_delta": 0.5,
                "sp_fip_delta_available": True,
                "park_run_factor": 1.02,
            },
        }
        out = inject_bullpen_to_phase52_row(phase52_row, None)
        assert "p0_features" in out
        assert out["p0_features"]["sp_fip_delta"] == 0.5

    def test_bullpen_features_added(self):
        from scripts.run_phase56_inject_bullpen_to_phase52 import inject_bullpen_to_phase52_row

        phase52_row = {
            "game_id": "g003",
            "game_date": "2025-04-17",
            "home_team": "A",
            "away_team": "B",
            "home_win": 1,
            "model_home_prob": 0.58,
            "market_home_prob_no_vig": 0.55,
        }
        out = inject_bullpen_to_phase52_row(phase52_row, None)
        assert "bullpen_features" in out
        assert out["bullpen_features"]["point_in_time_safe"] is True


# ═══════════════════════════════════════════════════════════════════════════════
# § T-033  Adjustment injection preserves original_model_home_prob
# ═══════════════════════════════════════════════════════════════════════════════

class TestAdjInjectionPreservesOriginal:
    def test_original_prob_preserved(self):
        from scripts.run_phase56_bullpen_feature_injection import inject_bullpen_adjustment_to_row

        row = {
            "game_id": "g1",
            "model_home_prob": 0.65,
            "bullpen_features": {"bullpen_feature_available": False},
        }
        out = inject_bullpen_adjustment_to_row(row)
        assert out["original_model_home_prob"] == 0.65

    def test_hard_rules_in_output(self):
        from scripts.run_phase56_bullpen_feature_injection import inject_bullpen_adjustment_to_row

        row = {
            "game_id": "g2",
            "model_home_prob": 0.55,
            "bullpen_features": {"bullpen_feature_available": False},
        }
        out = inject_bullpen_adjustment_to_row(row)
        assert out["candidate_patch_created"] is False
        assert out["production_modified"] is False
        assert out["diagnostic_only"] is True


# ═══════════════════════════════════════════════════════════════════════════════
# § T-034  Feature version strings correct
# ═══════════════════════════════════════════════════════════════════════════════

class TestFeatureVersions:
    def test_builder_version_contains_phase56(self):
        assert "phase56" in FEATURE_VERSION

    def test_output_version_matches_constant(self):
        result = build_bullpen_features(
            {"game_id": "g1", "game_date": "2025-05-01", "home_team": "A", "away_team": "B"},
            context=None,
        )
        assert result["feature_version"] == FEATURE_VERSION


# ═══════════════════════════════════════════════════════════════════════════════
# § T-035  All valid gates listed (4 gates only)
# ═══════════════════════════════════════════════════════════════════════════════

class TestGateList:
    def test_exactly_four_valid_gates(self):
        assert len(_VALID_GATES) == 4

    def test_all_gate_constants_valid(self):
        assert DATA_GAP_REMAINS in _VALID_GATES
        assert BULLPEN_FEATURE_EFFECTIVE_PAPER_ONLY in _VALID_GATES
        assert BULLPEN_FEATURE_NOT_EFFECTIVE in _VALID_GATES
        assert COLLECT_MORE_DATA in _VALID_GATES

    def test_no_patch_gate_in_valid_set(self):
        for gate in _VALID_GATES:
            assert "PATCH" not in gate
