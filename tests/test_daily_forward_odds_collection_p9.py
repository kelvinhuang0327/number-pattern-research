"""
Tests for P9-D: Daily Forward Odds Collection Plan
scripts/plan_daily_forward_odds_collection_p9.py

硬性約束驗證：
- schedule includes pregame + closing windows
- no network call
- crawler unchanged
- manifest paper_only=true
- duplicate snapshot rule deterministic
- coverage threshold aligned with P8 projection
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.plan_daily_forward_odds_collection_p9 import (
    MIN_PAIR_COVERAGE_PCT,
    MIN_PAIRS_FOR_CLV,
    MIN_TIMESTAMP_COVERAGE_PCT,
    ForwardCollectionPlanError,
    build_daily_schedule,
    build_snapshot_filename,
    evaluate_coverage,
    load_p8_manifest,
    run_daily_schedule_plan,
)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _empty_manifest() -> dict:
    return {
        "found": False,
        "total_records": 0,
        "unique_matches": 0,
        "pregame_closing_pairs": 0,
        "pair_coverage_pct": 0.0,
    }


def _good_manifest() -> dict:
    return {
        "found": True,
        "total_records": 2731,
        "unique_matches": 657,
        "pregame_closing_pairs": 550,
        "pair_coverage_pct": 85.0,
        "date_range_start": "2026-03-13",
        "date_range_end": "2026-05-19",
    }


# ── Test: Schedule includes pregame + closing windows ────────────────────────


class TestScheduleWindows:
    def test_schedule_has_closing_final_window(self):
        schedule = build_daily_schedule(_empty_manifest())
        labels = [w["label"] for w in schedule["schedule_windows"]]
        assert "closing_final" in labels

    def test_schedule_has_pregame_d2_window(self):
        schedule = build_daily_schedule(_empty_manifest())
        labels = [w["label"] for w in schedule["schedule_windows"]]
        assert "pregame_d2" in labels

    def test_schedule_has_decision_window(self):
        schedule = build_daily_schedule(_empty_manifest())
        labels = [w["label"] for w in schedule["schedule_windows"]]
        assert "decision" in labels

    def test_closing_final_is_critical(self):
        schedule = build_daily_schedule(_empty_manifest())
        windows = {w["label"]: w for w in schedule["schedule_windows"]}
        assert windows["closing_final"]["priority"] == "CRITICAL"

    def test_pregame_d2_is_critical(self):
        schedule = build_daily_schedule(_empty_manifest())
        windows = {w["label"]: w for w in schedule["schedule_windows"]}
        assert windows["pregame_d2"]["priority"] == "CRITICAL"

    def test_moneyline_market_present(self):
        schedule = build_daily_schedule(_empty_manifest())
        markets = [m["market_code"] for m in schedule["target_markets"]]
        assert "ML" in markets

    def test_moneyline_minimum_viable(self):
        schedule = build_daily_schedule(_empty_manifest())
        ml = next(m for m in schedule["target_markets"] if m["market_code"] == "ML")
        assert ml["minimum_viable"] is True


# ── Test: No network call ─────────────────────────────────────────────────────


class TestNoNetworkCall:
    def test_network_call_false_in_schedule(self):
        schedule = build_daily_schedule(_empty_manifest())
        assert schedule["network_call"] is False

    def test_run_plan_no_network(self, tmp_path):
        out = tmp_path / "schedule.json"
        schedule = run_daily_schedule_plan(output_path=out)
        assert schedule["network_call"] is False

    def test_no_socket_import_in_script(self):
        """Verify script module does not import socket (anti-crawl test)."""
        import scripts.plan_daily_forward_odds_collection_p9 as mod
        import inspect
        src = inspect.getsource(mod)
        assert "socket.socket" not in src


# ── Test: Crawler unchanged ───────────────────────────────────────────────────


class TestCrawlerUnchanged:
    def test_crawler_modified_false_in_schedule(self):
        schedule = build_daily_schedule(_empty_manifest())
        assert schedule["crawler_modified"] is False

    def test_production_write_false(self):
        schedule = build_daily_schedule(_empty_manifest())
        assert schedule["production_write"] is False

    def test_script_does_not_import_tsl_crawler(self):
        import scripts.plan_daily_forward_odds_collection_p9 as mod
        import inspect
        src = inspect.getsource(mod)
        assert "tsl_crawler" not in src


# ── Test: paper_only=True ─────────────────────────────────────────────────────


class TestPaperOnly:
    def test_paper_only_true_in_schedule(self):
        schedule = build_daily_schedule(_empty_manifest())
        assert schedule["paper_only"] is True

    def test_paper_only_false_raises(self):
        with pytest.raises(ForwardCollectionPlanError):
            build_daily_schedule(_empty_manifest(), paper_only=False)

    def test_output_json_paper_only_true(self, tmp_path):
        out = tmp_path / "sched.json"
        run_daily_schedule_plan(output_path=out)
        with open(out) as f:
            data = json.load(f)
        assert data["paper_only"] is True


# ── Test: Duplicate snapshot rule deterministic ───────────────────────────────


class TestDuplicateSnapshotRule:
    def test_build_filename_deterministic(self):
        f1 = build_snapshot_filename("G2026031501", "ML", "closing_final",
                                     "2026-03-15T20:30:00Z")
        f2 = build_snapshot_filename("G2026031501", "ML", "closing_final",
                                     "2026-03-15T20:30:00Z")
        assert f1 == f2

    def test_build_filename_differs_by_window(self):
        f1 = build_snapshot_filename("G2026031501", "ML", "pregame_d2",
                                     "2026-03-15T14:00:00Z")
        f2 = build_snapshot_filename("G2026031501", "ML", "closing_final",
                                     "2026-03-15T20:30:00Z")
        assert f1 != f2

    def test_build_filename_differs_by_market(self):
        f1 = build_snapshot_filename("G2026031501", "ML", "closing_final",
                                     "2026-03-15T20:30:00Z")
        f2 = build_snapshot_filename("G2026031501", "RL", "closing_final",
                                     "2026-03-15T20:30:00Z")
        assert f1 != f2

    def test_replay_safe_rule_in_schedule(self):
        schedule = build_daily_schedule(_empty_manifest())
        assert schedule["replay_safety"]["append_rule"] is not None

    def test_duplicate_rule_in_file_naming(self):
        schedule = build_daily_schedule(_empty_manifest())
        assert "duplicate_rule" in schedule["file_naming"]
        assert schedule["file_naming"]["deterministic"] is True


# ── Test: Coverage thresholds aligned with P8 ────────────────────────────────


class TestCoverageThresholds:
    def test_min_pair_coverage_pct_matches_p8(self):
        assert MIN_PAIR_COVERAGE_PCT == 90.0

    def test_min_pairs_for_clv_matches_p8(self):
        assert MIN_PAIRS_FOR_CLV == 200

    def test_min_timestamp_coverage_pct_matches_p8(self):
        assert MIN_TIMESTAMP_COVERAGE_PCT == 95.0

    def test_thresholds_in_schedule_output(self):
        schedule = build_daily_schedule(_empty_manifest())
        t = schedule["thresholds"]
        assert t["min_pair_coverage_pct"] == 90.0
        assert t["min_pairs_for_clv"] == 200
        assert t["min_timestamp_coverage_pct"] == 95.0

    def test_coverage_gate_not_passed_at_85pct(self):
        cov = evaluate_coverage({"pregame_closing_pairs": 550, "pair_coverage_pct": 85.0})
        assert cov["coverage_threshold_met"] is False
        assert cov["clv_gate_passed"] is False

    def test_coverage_gate_passed_at_92pct_with_250_pairs(self):
        cov = evaluate_coverage({"pregame_closing_pairs": 250, "pair_coverage_pct": 92.0})
        assert cov["coverage_threshold_met"] is True
        assert cov["pairs_threshold_met"] is True
        assert cov["clv_gate_passed"] is True

    def test_coverage_gate_fails_if_pairs_below_min(self):
        cov = evaluate_coverage({"pregame_closing_pairs": 100, "pair_coverage_pct": 95.0})
        assert cov["pairs_threshold_met"] is False
        assert cov["clv_gate_passed"] is False


# ── Test: Manifest loading ────────────────────────────────────────────────────


class TestManifestLoading:
    def test_missing_manifest_returns_empty(self, tmp_path):
        result = load_p8_manifest(tmp_path / "nonexistent.json")
        assert result["found"] is False
        assert result["total_records"] == 0

    def test_valid_manifest_loaded(self, tmp_path):
        manifest_data = {
            "paper_only": True,
            "timeline_summary": {
                "total_records": 100,
                "unique_match_ids": 30,
                "pregame_closing_pairs": 25,
                "pair_coverage_pct": 83.3,
            }
        }
        path = tmp_path / "manifest.json"
        with open(path, "w") as f:
            json.dump(manifest_data, f)
        result = load_p8_manifest(path)
        assert result["found"] is True
        assert result["total_records"] == 100
        assert result["pregame_closing_pairs"] == 25
