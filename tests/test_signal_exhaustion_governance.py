#!/usr/bin/env python3
"""
Tests for signal exhaustion detection and adaptive regime classification in Planner.

Covers:
  - Legacy _check_signal_exhaustion() — backward-compat string marker detection
  - New _classify_signal_state()     — 3-state regime-aware decision
  - New _game_signal_summary()       — per-game edge health
  - New task builders                — cold_regime / saturated payloads
"""

import unittest
import sys
import os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "orchestrator"))

from planner_tick import (
    _check_signal_exhaustion,
    _classify_signal_state,
    _game_signal_summary,
    _build_cold_regime_payload,
    _build_saturated_payload,
    _compute_confidence_score,
    SIGNAL_STATE_TRUE_EXHAUSTED,
    SIGNAL_STATE_SATURATED,
    SIGNAL_STATE_COLD_REGIME,
)

_EXHAUSTED_BACKLOG = """
## [SIGNAL_EXHAUSTED_ALL] — 三彩種信號窮盡收斂（2026/04/23）

**Conclusion**: All three lottery games (BIG_LOTTO, DAILY_539, POWER_LOTTO)
have exhausted actionable research directions.

### 停止新研究分配原則 (NO_NEW_RESEARCH Policy)
"""

_NORMAL_BACKLOG = """
## 各彩種現狀與研究優先順序

### 威力彩（POWER_LOTTO）— 有待驗證方向
1. [RETRY_REQUIRED] midfreq_fourier_2bet McNemar 驗證
"""


# ─── Legacy compatibility tests ───────────────────────────────────────────────

class TestLegacySignalExhaustion(unittest.TestCase):
    """Legacy _check_signal_exhaustion() must remain backward-compatible."""

    def test_marker_detected(self):
        self.assertTrue(_check_signal_exhaustion(_EXHAUSTED_BACKLOG))

    def test_marker_not_detected_without_marker(self):
        self.assertFalse(_check_signal_exhaustion(_NORMAL_BACKLOG))

    def test_case_sensitive(self):
        self.assertFalse(_check_signal_exhaustion("[signal_exhausted_all]"))

    def test_marker_with_surrounding_text(self):
        backlog = "前言\n\n## [SIGNAL_EXHAUSTED_ALL] — 測試\n\n後續"
        self.assertTrue(_check_signal_exhaustion(backlog))

    def test_multiple_occurrences(self):
        backlog = "## [SIGNAL_EXHAUSTED_ALL]\n\n### Ref: [SIGNAL_EXHAUSTED_ALL]"
        self.assertTrue(_check_signal_exhaustion(backlog))

    def test_empty_backlog(self):
        self.assertFalse(_check_signal_exhaustion(""))


# ─── _game_signal_summary() tests ─────────────────────────────────────────────

class TestGameSignalSummary(unittest.TestCase):
    def test_empty_states(self):
        r = _game_signal_summary({})
        self.assertFalse(r["has_strategies"])
        self.assertFalse(r["has_validated"])
        self.assertIsNone(r["best_edge_long"])
        self.assertIsNone(r["best_edge_short"])
        self.assertEqual(r["cold_count"], 0)
        self.assertEqual(r["total"], 0)

    def test_single_validated_strategy(self):
        states = {
            "my_strat": {
                "validated_status": "validated",
                "edge_1500p": 0.05,
                "edge_30p": 0.03,
                "consecutive_neg_30p": 0,
            }
        }
        r = _game_signal_summary(states)
        self.assertTrue(r["has_strategies"])
        self.assertTrue(r["has_validated"])
        self.assertAlmostEqual(r["best_edge_long"], 0.05)
        self.assertAlmostEqual(r["best_edge_short"], 0.03)
        self.assertEqual(r["cold_count"], 0)

    def test_cold_streak_counted(self):
        states = {
            "strat_a": {"consecutive_neg_30p": 5, "edge_30p": -0.02},
            "strat_b": {"consecutive_neg_30p": 1, "edge_30p":  0.01},
        }
        r = _game_signal_summary(states)
        self.assertEqual(r["cold_count"], 1)  # only strat_a >= 3

    def test_edge_fallback_order(self):
        # edge_1500p None → falls back to edge_500p
        states = {
            "strat_x": {"edge_1500p": None, "edge_500p": 0.07, "edge_30p": 0.02}
        }
        r = _game_signal_summary(states)
        self.assertAlmostEqual(r["best_edge_long"], 0.07)


# ─── _classify_signal_state() — 3-state tests ─────────────────────────────────

_EMPTY_POLICY = {
    "runs_analyzed": 0, "policy_confidence": "low",
    "retry_merge_rate": 0.0, "overall_merge_rate": 0.0,
}

_BASE_STATES = {
    "BIG_LOTTO": {
        "strat_a": {"validated_status": None, "edge_1500p": None, "edge_30p": 0.03,
                    "consecutive_neg_30p": 0}
    },
    "DAILY_539": {
        "strat_b": {"validated_status": None, "edge_1500p": None, "edge_30p": 0.05,
                    "consecutive_neg_30p": 0}
    },
    "POWER_LOTTO": {
        "strat_c": {"validated_status": None, "edge_1500p": None, "edge_30p": -0.01,
                    "consecutive_neg_30p": 0}
    },
}


class TestClassifySignalState(unittest.TestCase):

    def test_no_marker_returns_none_state(self):
        result = _classify_signal_state(_NORMAL_BACKLOG)
        self.assertIsNone(result["state"])

    @patch("planner_tick.db.get_adaptive_policy", return_value=_EMPTY_POLICY)
    @patch("planner_tick._load_strategy_states_all", return_value={"BIG_LOTTO": {}, "DAILY_539": {}, "POWER_LOTTO": {}})
    def test_true_exhausted_when_no_data(self, mock_states, mock_policy):
        result = _classify_signal_state(_EXHAUSTED_BACKLOG)
        self.assertEqual(result["state"], SIGNAL_STATE_TRUE_EXHAUSTED)

    @patch("planner_tick.db.get_adaptive_policy", return_value=_EMPTY_POLICY)
    @patch("planner_tick._load_strategy_states_all", return_value={
        "BIG_LOTTO": {
            "strat_a": {"validated_status": None, "edge_1500p": 0.08,
                        "edge_30p": -0.06, "consecutive_neg_30p": 4}
        },
        "DAILY_539": {},
        "POWER_LOTTO": {},
    })
    def test_cold_regime_when_long_positive_short_negative(self, mock_states, mock_policy):
        """Long-term edge > 0 but short-term < 0 → COLD_REGIME."""
        result = _classify_signal_state(_EXHAUSTED_BACKLOG)
        self.assertEqual(result["state"], SIGNAL_STATE_COLD_REGIME)
        self.assertIn("BIG_LOTTO", result["reason"])

    @patch("planner_tick.db.get_adaptive_policy", return_value=_EMPTY_POLICY)
    @patch("planner_tick._load_strategy_states_all", return_value={
        "BIG_LOTTO": {
            "s1": {"edge_30p": -0.07, "consecutive_neg_30p": 5, "edge_1500p": None, "validated_status": None},
            "s2": {"edge_30p": -0.04, "consecutive_neg_30p": 4, "edge_1500p": None, "validated_status": None},
            "s3": {"edge_30p":  0.01, "consecutive_neg_30p": 0, "edge_1500p": None, "validated_status": None},
        },
        "DAILY_539": {},
        "POWER_LOTTO": {},
    })
    def test_cold_regime_majority_negative_streak(self, mock_states, mock_policy):
        """2/3 strategies in cold streak → COLD_REGIME."""
        result = _classify_signal_state(_EXHAUSTED_BACKLOG)
        self.assertEqual(result["state"], SIGNAL_STATE_COLD_REGIME)

    @patch("planner_tick.db.get_adaptive_policy", return_value=_EMPTY_POLICY)
    @patch("planner_tick._load_strategy_states_all", return_value=_BASE_STATES)
    def test_signal_saturated_default(self, mock_states, mock_policy):
        """Has strategies with positive short edge but no exhaustion triggers → SATURATED."""
        result = _classify_signal_state(_EXHAUSTED_BACKLOG)
        self.assertEqual(result["state"], SIGNAL_STATE_SATURATED)

    @patch("planner_tick.db.get_adaptive_policy", return_value={
        "runs_analyzed": 15, "policy_confidence": "high",
        "retry_merge_rate": 0.45, "overall_merge_rate": 0.60,
    })
    @patch("planner_tick._load_strategy_states_all", return_value=_BASE_STATES)
    def test_saturated_with_high_confidence_policy(self, mock_states, mock_policy):
        result = _classify_signal_state(_EXHAUSTED_BACKLOG)
        self.assertEqual(result["state"], SIGNAL_STATE_SATURATED)
        self.assertEqual(result["policy"]["confidence"], "high")
        self.assertAlmostEqual(result["policy"]["retry_merge_rate"], 0.45)


# ─── Task builder smoke tests ─────────────────────────────────────────────────

class TestRegimeTaskBuilders(unittest.TestCase):

    def test_cold_regime_payload_structure(self):
        signal_state = {
            "state": SIGNAL_STATE_COLD_REGIME,
            "reason": "BIG_LOTTO: long-term edge +0.080 but short-term -0.060",
            "game_summaries": {},
            "policy": {"confidence": "low", "retry_merge_rate": 0.0, "overall_merge_rate": 0.0},
        }
        payload = _build_cold_regime_payload(signal_state, _EXHAUSTED_BACKLOG)
        self.assertIn("title", payload)
        self.assertIn("slug", payload)
        self.assertIn("prompt_markdown", payload)
        self.assertIn("_signal_state_type", payload)
        self.assertIn("Objective", payload["prompt_markdown"])
        self.assertIn("Acceptance Criteria", payload["prompt_markdown"])

    def test_cold_regime_adaptive_bet_sizing_when_retry_effective(self):
        signal_state = {
            "state": SIGNAL_STATE_COLD_REGIME,
            "reason": "BIG_LOTTO: cold",
            "game_summaries": {},
            "policy": {"confidence": "high", "retry_merge_rate": 0.50, "overall_merge_rate": 0.55},
        }
        payload = _build_cold_regime_payload(signal_state, _EXHAUSTED_BACKLOG)
        self.assertEqual(payload["_signal_state_type"], "adaptive_bet_sizing")

    def test_saturated_payload_structure(self):
        signal_state = {
            "state": SIGNAL_STATE_SATURATED,
            "reason": "12 strategies exist, no new signal",
            "game_summaries": {
                "BIG_LOTTO": {"total": 4, "has_validated": False, "best_edge_short": 0.03},
                "DAILY_539": {"total": 3, "has_validated": True,  "best_edge_short": 0.05},
                "POWER_LOTTO": {"total": 3, "has_validated": False, "best_edge_short": None},
            },
            "policy": {"confidence": "medium", "retry_merge_rate": 0.3, "overall_merge_rate": 0.25},
        }
        payload = _build_saturated_payload(signal_state, _NORMAL_BACKLOG)
        self.assertIn("title", payload)
        self.assertIn("prompt_markdown", payload)
        self.assertIn("Objective", payload["prompt_markdown"])
        self.assertIn("_signal_state_type", payload)

    def test_saturated_signal_quality_filter_when_low_merge_rate(self):
        signal_state = {
            "state": SIGNAL_STATE_SATURATED,
            "reason": "strategies exist, no new edge",
            "game_summaries": {g: {"total": 3, "has_validated": False, "best_edge_short": 0.02}
                               for g in ("BIG_LOTTO", "DAILY_539", "POWER_LOTTO")},
            "policy": {"confidence": "medium", "retry_merge_rate": 0.2, "overall_merge_rate": 0.20},
        }
        payload = _build_saturated_payload(signal_state, _NORMAL_BACKLOG)
        # overall < 0.30 + confidence medium → signal_quality_filter
        self.assertEqual(payload["_signal_state_type"], "signal_quality_filter")


# ─── Integration: actual strategy_states edge snapshot ────────────────────────

class TestActualEdgeSnapshot(unittest.TestCase):
    """
    Runs the classifier against the real strategy_states JSON files.
    Documents the current regime state of the system (2026/04/23).
    """

    @patch("planner_tick.db.get_adaptive_policy", return_value=_EMPTY_POLICY)
    @patch("planner_tick.db.get_classifier_thresholds", return_value={
        "cold_streak_ratio": 0.5, "cold_edge_long_min": 0.0,
        "cold_edge_short_max": 0.0, "cold_edge_absolute_max": -0.05,
        "cold_min_total_strategies": 2, "exhausted_max_runs_analyzed": 0,
        "weight_cold_streak": 1.0, "weight_edge_divergence": 1.5,
        "weight_policy_support": 0.5,
    })
    @patch("planner_tick.db.record_classifier_event", return_value=1)
    def test_actual_game_classification(self, mock_record, mock_thresh, mock_policy):
        """
        With actual strategy_states, classify each game's current regime.
        The test passes as long as the classifier runs without error and
        returns a valid state string.
        """
        result = _classify_signal_state(_EXHAUSTED_BACKLOG)
        valid_states = {None, SIGNAL_STATE_TRUE_EXHAUSTED, SIGNAL_STATE_SATURATED, SIGNAL_STATE_COLD_REGIME}
        self.assertIn(result.get("state"), valid_states)
        self.assertIn("confidence_score", result)
        self.assertIn("confidence_label", result)
        # Document the current regime state
        print(
            f"\n[Regime Snapshot 2026/04/23] state={result.get('state')}, "
            f"confidence={result.get('confidence_score'):.2f} ({result.get('confidence_label')}), "
            f"reason={result.get('reason')}"
        )


# ─── Confidence Scoring tests ─────────────────────────────────────────────────

_DEFAULT_THRESHOLDS = {
    "cold_streak_ratio": 0.5, "cold_edge_long_min": 0.0,
    "cold_edge_short_max": 0.0, "cold_edge_absolute_max": -0.05,
    "cold_min_total_strategies": 2, "exhausted_max_runs_analyzed": 0,
    "weight_cold_streak": 1.0, "weight_edge_divergence": 1.5,
    "weight_policy_support": 0.5,
}


class TestConfidenceScoring(unittest.TestCase):
    """Tests for _compute_confidence_score()."""

    def test_true_exhausted_fixed_high_score(self):
        score, label = _compute_confidence_score(
            SIGNAL_STATE_TRUE_EXHAUSTED, [], {}, {}, _DEFAULT_THRESHOLDS
        )
        self.assertAlmostEqual(score, 0.90)
        self.assertEqual(label, "strong_exhausted")

    def test_cold_single_game_divergence_is_cold(self):
        cold_signals = ["BIG_LOTTO: long-term edge +0.080 but short-term -0.060"]
        score, label = _compute_confidence_score(
            SIGNAL_STATE_COLD_REGIME, cold_signals, {}, _EMPTY_POLICY, _DEFAULT_THRESHOLDS
        )
        # One divergence game: 1 × 1.5 × 0.20 = 0.30 + 1 × 1.0 × 0.20 = 0.20 → 0.50
        self.assertGreaterEqual(score, 0.30)
        self.assertIn(label, ("cold", "weak_cold", "strong_cold", "uncertain"))

    def test_cold_multiple_games_strong(self):
        cold_signals = [
            "BIG_LOTTO: long-term edge +0.080 but short-term -0.060",
            "POWER_LOTTO: 4/7 strategies in neg streak",
        ]
        score, label = _compute_confidence_score(
            SIGNAL_STATE_COLD_REGIME, cold_signals, {}, _EMPTY_POLICY, _DEFAULT_THRESHOLDS
        )
        # Two games + divergence → should be "cold" or "strong_cold"
        self.assertGreaterEqual(score, 0.40)

    def test_saturated_low_score_no_data(self):
        score, label = _compute_confidence_score(
            SIGNAL_STATE_SATURATED, [],
            {"BIG_LOTTO": {"has_validated": False}},
            {"runs_analyzed": 0, "confidence": "low", "overall_merge_rate": 0.0},
            _DEFAULT_THRESHOLDS,
        )
        self.assertLessEqual(score, 0.35)
        self.assertEqual(label, "uncertain")

    def test_saturated_high_score_with_data(self):
        game_summaries = {
            "BIG_LOTTO": {"has_validated": True},
            "DAILY_539": {"has_validated": False},
        }
        policy = {"runs_analyzed": 15, "confidence": "high", "overall_merge_rate": 0.55}
        score, label = _compute_confidence_score(
            SIGNAL_STATE_SATURATED, [], game_summaries, policy, _DEFAULT_THRESHOLDS
        )
        self.assertGreaterEqual(score, 0.55)
        self.assertIn(label, ("saturated", "strong_saturated"))

    def test_score_always_between_0_and_1(self):
        for state in (SIGNAL_STATE_TRUE_EXHAUSTED, SIGNAL_STATE_COLD_REGIME, SIGNAL_STATE_SATURATED):
            score, _ = _compute_confidence_score(state, [], {}, {}, _DEFAULT_THRESHOLDS)
            self.assertGreaterEqual(score, 0.0)
            self.assertLessEqual(score, 1.0)


# ─── Classifier with dynamic thresholds tests ─────────────────────────────────

_MOCK_THRESH = _DEFAULT_THRESHOLDS.copy()


class TestDynamicThresholds(unittest.TestCase):
    """Verify that classifier respects dynamic threshold values."""

    @patch("planner_tick.db.get_adaptive_policy", return_value=_EMPTY_POLICY)
    @patch("planner_tick.db.record_classifier_event", return_value=42)
    @patch("planner_tick.db.get_classifier_thresholds")
    def test_raised_streak_ratio_prevents_cold_detection(self, mock_thresh, mock_record, mock_policy):
        """With cold_streak_ratio raised to 0.80, 4/7 cold strategies should NOT trigger."""
        high_thresh = _MOCK_THRESH.copy()
        high_thresh["cold_streak_ratio"] = 0.80  # 4/7 = 57% < 80%
        mock_thresh.return_value = high_thresh

        with patch("planner_tick._load_strategy_states_all", return_value={
            "BIG_LOTTO":   {},
            "DAILY_539":   {},
            "POWER_LOTTO": {
                f"s{i}": {"edge_30p": -0.03, "consecutive_neg_30p": 4,
                          "edge_1500p": None, "validated_status": None}
                for i in range(4)
            } | {
                f"h{i}": {"edge_30p": 0.02, "consecutive_neg_30p": 0,
                          "edge_1500p": None, "validated_status": None}
                for i in range(3)
            },
        }):
            result = _classify_signal_state(_EXHAUSTED_BACKLOG)
            # 4/7 = 57% < 80% threshold → should NOT be COLD_REGIME
            self.assertNotEqual(result["state"], SIGNAL_STATE_COLD_REGIME)

    @patch("planner_tick.db.get_adaptive_policy", return_value=_EMPTY_POLICY)
    @patch("planner_tick.db.record_classifier_event", return_value=42)
    @patch("planner_tick.db.get_classifier_thresholds")
    def test_lowered_streak_ratio_triggers_cold_detection(self, mock_thresh, mock_record, mock_policy):
        """With cold_streak_ratio lowered to 0.30, 2/5 cold strategies should trigger."""
        low_thresh = _MOCK_THRESH.copy()
        low_thresh["cold_streak_ratio"] = 0.30
        low_thresh["cold_min_total_strategies"] = 2
        mock_thresh.return_value = low_thresh

        with patch("planner_tick._load_strategy_states_all", return_value={
            "BIG_LOTTO": {
                "s1": {"edge_30p": -0.04, "consecutive_neg_30p": 5, "edge_1500p": None, "validated_status": None},
                "s2": {"edge_30p": -0.02, "consecutive_neg_30p": 4, "edge_1500p": None, "validated_status": None},
                "s3": {"edge_30p":  0.01, "consecutive_neg_30p": 0, "edge_1500p": None, "validated_status": None},
                "s4": {"edge_30p":  0.02, "consecutive_neg_30p": 0, "edge_1500p": None, "validated_status": None},
                "s5": {"edge_30p":  0.01, "consecutive_neg_30p": 0, "edge_1500p": None, "validated_status": None},
            },
            "DAILY_539": {}, "POWER_LOTTO": {},
        }):
            result = _classify_signal_state(_EXHAUSTED_BACKLOG)
            # 2/5 = 40% > 30% threshold → should be COLD_REGIME
            self.assertEqual(result["state"], SIGNAL_STATE_COLD_REGIME)

    @patch("planner_tick.db.get_adaptive_policy", return_value=_EMPTY_POLICY)
    @patch("planner_tick.db.record_classifier_event", return_value=42)
    @patch("planner_tick.db.get_classifier_thresholds")
    def test_calibration_id_returned_in_result(self, mock_thresh, mock_record, mock_policy):
        """classify_signal_state() must include calibration_id in result."""
        mock_thresh.return_value = _MOCK_THRESH
        result = _classify_signal_state(_EXHAUSTED_BACKLOG)
        self.assertIn("calibration_id", result)

    @patch("planner_tick.db.get_adaptive_policy", return_value=_EMPTY_POLICY)
    @patch("planner_tick.db.record_classifier_event", return_value=99)
    @patch("planner_tick.db.get_classifier_thresholds", return_value=_MOCK_THRESH)
    @patch("planner_tick._load_strategy_states_all", return_value={"BIG_LOTTO": {}, "DAILY_539": {}, "POWER_LOTTO": {}})
    def test_calibration_id_matches_mock(self, mock_states, mock_thresh, mock_record, mock_policy):
        """calibration_id in result must match the value returned by record_classifier_event."""
        result = _classify_signal_state(_EXHAUSTED_BACKLOG)
        # TRUE_EXHAUSTED (no strategies) → calibration_id should be 99
        self.assertEqual(result.get("calibration_id"), 99)


# ─── DB: classifier_thresholds compute tests ─────────────────────────────────

import orchestrator.db as orch_db


class TestClassifierThresholdsDB(unittest.TestCase):
    """Unit tests for DB threshold calibration helpers."""

    def setUp(self):
        import tempfile
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp.close()
        self._orig_db_path = orch_db.DB_PATH
        orch_db.DB_PATH = self._tmp.name
        orch_db.init_db()

    def tearDown(self):
        orch_db.DB_PATH = self._orig_db_path
        try:
            os.unlink(self._tmp.name)
        except OSError:
            pass

    def test_default_thresholds_returned_on_fresh_db(self):
        thresholds = orch_db.get_classifier_thresholds(max_age_seconds=0)
        self.assertAlmostEqual(thresholds["cold_streak_ratio"], 0.5)
        self.assertAlmostEqual(thresholds["cold_edge_absolute_max"], -0.05)

    def test_record_classifier_event_returns_id(self):
        import json
        cal_id = orch_db.record_classifier_event(
            state="COLD_REGIME",
            confidence_score=0.72,
            confidence_label="cold",
            reason="BIG_LOTTO cold",
            features_json=json.dumps({}),
            thresholds_json=json.dumps({}),
        )
        self.assertIsInstance(cal_id, int)
        self.assertGreater(cal_id, 0)

    def test_record_outcome_updates_counters(self):
        import json
        cal_id = orch_db.record_classifier_event(
            state="COLD_REGIME", confidence_score=0.6, confidence_label="cold",
            reason="test", features_json="{}", thresholds_json="{}",
        )
        orch_db.record_classifier_outcome(cal_id, "SIGNAL_SATURATED", 50, False, "FP")

        conn = orch_db.get_conn()
        try:
            row = conn.execute("SELECT * FROM classifier_thresholds WHERE id = 1").fetchone()
            self.assertEqual(row["cold_fp_count"], 1)
            self.assertEqual(row["total_classifications"], 1)
            self.assertEqual(row["correct_classifications"], 0)
        finally:
            conn.close()

    def test_correct_outcome_increments_correct_count(self):
        import json
        cal_id = orch_db.record_classifier_event(
            state="COLD_REGIME", confidence_score=0.8, confidence_label="strong_cold",
            reason="test", features_json="{}", thresholds_json="{}",
        )
        orch_db.record_classifier_outcome(cal_id, "COLD_REGIME", 100, True, "TP")
        conn = orch_db.get_conn()
        try:
            row = conn.execute("SELECT * FROM classifier_thresholds WHERE id = 1").fetchone()
            self.assertEqual(row["correct_classifications"], 1)
            self.assertEqual(row["cold_fp_count"], 0)
        finally:
            conn.close()

    def test_accuracy_report_empty_db(self):
        report = orch_db.get_classifier_accuracy_report()
        self.assertEqual(report["total_verified"], 0)
        self.assertIsNone(report["accuracy"])

    def test_fp_triggers_threshold_adjustment(self):
        """After 10+ events with >20% FP rate, cold_streak_ratio should be raised."""
        import json
        for i in range(12):
            cal_id = orch_db.record_classifier_event(
                state="COLD_REGIME", confidence_score=0.5, confidence_label="cold",
                reason=f"test_{i}", features_json="{}", thresholds_json="{}",
            )
            # Make ~40% of them FP (5/12)
            fp_fn = "FP" if i < 5 else "TP"
            correct = fp_fn == "TP"
            orch_db.record_classifier_outcome(cal_id, "SIGNAL_SATURATED" if fp_fn == "FP" else "COLD_REGIME",
                                             50, correct, fp_fn)
        thresholds = orch_db.compute_classifier_thresholds()
        # 5/12 ≈ 42% FP rate > 20% → threshold should have been raised above 0.5
        self.assertGreater(thresholds["cold_streak_ratio"], 0.5)


if __name__ == "__main__":
    unittest.main()



class TestSignalExhaustionDetection(unittest.TestCase):
    """Test signal exhaustion detection logic."""

    def test_exhaustion_marker_detected(self):
        """Test that [SIGNAL_EXHAUSTED_ALL] marker is detected in backlog."""
        backlog_with_marker = """
## [SIGNAL_EXHAUSTED_ALL] — 三彩種信號窮盡收斂（2026/04/23）

**Conclusion**: All three lottery games (BIG_LOTTO, DAILY_539, POWER_LOTTO) 
have exhausted actionable research directions.

### 停止新研究分配原則 (NO_NEW_RESEARCH Policy)
"""
        self.assertTrue(_check_signal_exhaustion(backlog_with_marker))

    def test_exhaustion_not_detected_without_marker(self):
        """Test that exhaustion is not detected without the marker."""
        backlog_without_marker = """
## 各彩種現狀與研究優先順序

### 今彩539（DAILY_539）— 信號高度飽和
現役策略（RSM 監控）：
- 1注 `acb_1bet`
- 2注 `midfreq_acb_2bet`

優先研究：
1. H011 起的新假說
"""
        self.assertFalse(_check_signal_exhaustion(backlog_without_marker))

    def test_exhaustion_case_sensitive(self):
        """Test that marker detection is case-sensitive."""
        backlog_wrong_case = """
[signal_exhausted_all]
"""
        self.assertFalse(_check_signal_exhaustion(backlog_wrong_case))

    def test_exhaustion_with_surrounding_text(self):
        """Test that marker is detected even with surrounding text."""
        backlog = """
前言段落...

<!-- AUTO_STATUS_END -->

---

## [SIGNAL_EXHAUSTED_ALL] — 三彩種信號窮盡收斂（2026/04/23）

Conclusion: All three...

後續段落...
"""
        self.assertTrue(_check_signal_exhaustion(backlog))

    def test_exhaustion_multiple_occurrences(self):
        """Test detection with multiple marker occurrences."""
        backlog = """
## [SIGNAL_EXHAUSTED_ALL] — First mention

Some content...

### Reference: [SIGNAL_EXHAUSTED_ALL] again
"""
        self.assertTrue(_check_signal_exhaustion(backlog))

    def test_exhaustion_empty_backlog(self):
        """Test that empty backlog is handled correctly."""
        self.assertFalse(_check_signal_exhaustion(""))

    def test_exhaustion_none_backlog(self):
        """Test that None-like input doesn't crash."""
        try:
            result = _check_signal_exhaustion(None)
            # If we get here, function should have returned False or handled gracefully
            self.assertFalse(result)
        except (TypeError, AttributeError):
            # This is acceptable behavior for None input
            pass


class TestSignalExhaustionIntegration(unittest.TestCase):
    """Integration test simulating planner behavior when exhaustion detected."""

    def test_backlog_with_exhaustion_blocks_research(self):
        """
        Simulate Planner's backlog reading and task generation decision.
        When [SIGNAL_EXHAUSTED_ALL] is detected, task generation should be skipped.
        """
        # Simulate a realistic exhausted backlog from runtime/agent_orchestrator/backlog.md
        exhausted_backlog = """
## [SIGNAL_EXHAUSTED_ALL] — 三彩種信號窮盡收斂（2026/04/23）

**Conclusion**: All three lottery games (BIG_LOTTO, DAILY_539, POWER_LOTTO) 
have exhausted actionable research directions within the established validation framework.

### 停止新研究分配原則 (NO_NEW_RESEARCH Policy)

**Effective Immediately**: Planner MUST NOT generate new strategy research tasks.

**Allowed Activities**:
✅ RSM health monitoring
✅ Drift/PSI monitoring
✅ Dashboard maintenance
✅ DB governance repairs

**Forbidden Activities**:
❌ New strategy research
❌ Hypothesis reopening
❌ Parameter micro-tuning
"""
        
        # Should detect exhaustion
        self.assertTrue(_check_signal_exhaustion(exhausted_backlog))
        
        # This is the condition that blocks research task generation in planner_tick.run()
        if _check_signal_exhaustion(exhausted_backlog):
            # Task generation should be skipped
            task_generation_skipped = True
        else:
            task_generation_skipped = False
        
        self.assertTrue(task_generation_skipped)

    def test_backlog_without_exhaustion_allows_research(self):
        """
        Verify that normal (non-exhausted) backlog allows research task generation.
        """
        normal_backlog = """
## 各彩種現狀與研究優先順序

### 威力彩（POWER_LOTTO）— 有待驗證方向

優先研究：
1. [RETRY_REQUIRED] midfreq_fourier_2bet McNemar 驗證
2. [RETRY_REQUIRED] fourier_rhythm_3bet 500期 OOS 驗證
"""
        
        # Should NOT detect exhaustion
        self.assertFalse(_check_signal_exhaustion(normal_backlog))
        
        # Task generation should proceed
        if _check_signal_exhaustion(normal_backlog):
            task_generation_allowed = False
        else:
            task_generation_allowed = True
        
        self.assertTrue(task_generation_allowed)


if __name__ == "__main__":
    unittest.main()
