"""Tests for p34_prediction_source_planner.py"""

from __future__ import annotations

import os
import tempfile

import pandas as pd
import pytest

from wbc_backend.recommendation.p34_dual_source_acquisition_contract import (
    LEAKAGE_CONFIRMED,
    LEAKAGE_NONE,
    OPTION_BLOCKED_PROVENANCE,
    OPTION_READY_FOR_IMPLEMENTATION_PLAN,
    OPTION_REJECTED_FAKE_OR_LEAKAGE,
    OPTION_REQUIRES_MANUAL_APPROVAL,
    PREDICTION_TEMPLATE_COLUMNS,
)
from wbc_backend.recommendation.p34_prediction_source_planner import (
    MIN_GAME_ROWS_FOR_OOF,
    build_prediction_acquisition_options,
    evaluate_existing_prediction_candidate,
    evaluate_oof_rebuild_feasibility,
    load_p32_game_logs,
    load_p33_prediction_candidates,
    rank_prediction_options,
    summarize_prediction_plan,
)


class TestLoadP32GameLogs:
    def test_returns_empty_if_file_missing(self):
        df = load_p32_game_logs("/nonexistent/path/file.csv")
        assert df.empty

    def test_loads_csv(self, tmp_path):
        csv_file = tmp_path / "game_logs.csv"
        csv_file.write_text("game_id,home_team,away_team\ng001,NYY,BOS\ng002,LAD,SFG\n")
        df = load_p32_game_logs(str(csv_file))
        assert len(df) == 2
        assert "game_id" in df.columns


class TestLoadP33PredictionCandidates:
    def test_returns_empty_if_missing(self):
        df = load_p33_prediction_candidates("/no/such/file.csv")
        assert df.empty

    def test_loads_csv(self, tmp_path):
        csv_file = tmp_path / "pred_candidates.csv"
        csv_file.write_text("candidate_id,file_path,status\n1,/some/path,SOURCE_BLOCKED\n")
        df = load_p33_prediction_candidates(str(csv_file))
        assert len(df) == 1


class TestEvaluateOofRebuildFeasibility:
    def test_empty_df_not_feasible(self):
        result = evaluate_oof_rebuild_feasibility(pd.DataFrame())
        assert result["feasible"] is False
        assert result["row_count"] == 0

    def test_small_df_not_feasible(self):
        df = pd.DataFrame({"game_id": range(10), "home_score": range(10)})
        result = evaluate_oof_rebuild_feasibility(df)
        assert result["feasible"] is False
        assert result["row_count"] == 10

    def test_large_df_with_game_id_feasible(self):
        n = MIN_GAME_ROWS_FOR_OOF + 100
        df = pd.DataFrame({"game_id": range(n), "home_score": range(n), "away_score": range(n)})
        result = evaluate_oof_rebuild_feasibility(df)
        assert result["feasible"] is True
        assert result["row_count"] == n
        assert result["has_game_id"] is True
        assert result["coverage_fraction"] > 0.0

    def test_large_df_without_game_id_not_feasible(self):
        n = MIN_GAME_ROWS_FOR_OOF + 100
        df = pd.DataFrame({"home_team": ["NYY"] * n, "away_team": ["BOS"] * n})
        result = evaluate_oof_rebuild_feasibility(df)
        assert result["feasible"] is False
        assert result["has_game_id"] is False

    def test_exactly_min_rows_feasible(self):
        df = pd.DataFrame({"game_id": range(MIN_GAME_ROWS_FOR_OOF)})
        result = evaluate_oof_rebuild_feasibility(df)
        assert result["feasible"] is True

    def test_coverage_fraction_capped_at_1(self):
        n = 5000  # More than 2430 full season
        df = pd.DataFrame({"game_id": range(n)})
        result = evaluate_oof_rebuild_feasibility(df)
        assert result["coverage_fraction"] <= 1.0


class TestEvaluateExistingPredictionCandidate:
    def _make_candidate(self, **kwargs) -> pd.Series:
        defaults = {
            "candidate_id": "test_01",
            "file_path": "/data/some_pred_2024.csv",
            "status": "SOURCE_BLOCKED",
            "is_dry_run": "False",
            "year_verified": "True",
        }
        defaults.update(kwargs)
        return pd.Series(defaults)

    def test_dry_run_rejected(self):
        cand = self._make_candidate(is_dry_run="True")
        opt = evaluate_existing_prediction_candidate(cand)
        assert opt.status == OPTION_REJECTED_FAKE_OR_LEAKAGE
        assert opt.leakage_risk == LEAKAGE_CONFIRMED

    def test_year_unverified_blocked(self):
        cand = self._make_candidate(year_verified="False", is_dry_run="False")
        opt = evaluate_existing_prediction_candidate(cand)
        assert opt.status == OPTION_BLOCKED_PROVENANCE

    def test_y_true_inferred_via_dry_run_flag(self):
        """Dry-run flag is the P34 proxy for outcome-derived predictions."""
        cand = self._make_candidate(is_dry_run="True", year_verified="True")
        opt = evaluate_existing_prediction_candidate(cand)
        assert opt.status == OPTION_REJECTED_FAKE_OR_LEAKAGE

    def test_legitimate_candidate(self):
        cand = self._make_candidate(is_dry_run="False", year_verified="True")
        opt = evaluate_existing_prediction_candidate(cand)
        assert opt.status == OPTION_REQUIRES_MANUAL_APPROVAL

    def test_paper_only_enforced(self):
        cand = self._make_candidate()
        opt = evaluate_existing_prediction_candidate(cand)
        assert opt.paper_only is True
        assert opt.production_ready is False


class TestBuildPredictionAcquisitionOptions:
    def _large_game_logs(self) -> pd.DataFrame:
        n = 2430
        return pd.DataFrame({"game_id": [f"g{i}" for i in range(n)]})

    def test_returns_list(self):
        options = build_prediction_acquisition_options(pd.DataFrame(), pd.DataFrame())
        assert isinstance(options, list)
        assert len(options) >= 1

    def test_always_has_blocker_option(self):
        options = build_prediction_acquisition_options(pd.DataFrame(), pd.DataFrame())
        statuses = [o.status for o in options]
        assert OPTION_BLOCKED_PROVENANCE in statuses

    def test_oof_rebuild_ready_if_large_game_logs(self):
        options = build_prediction_acquisition_options(self._large_game_logs(), pd.DataFrame())
        ready = [o for o in options if o.status == OPTION_READY_FOR_IMPLEMENTATION_PLAN]
        assert len(ready) >= 1
        assert any(o.option_id == "pred_r01" for o in ready)

    def test_oof_rebuild_blocked_if_empty_game_logs(self):
        options = build_prediction_acquisition_options(pd.DataFrame(), pd.DataFrame())
        pred_r01 = next((o for o in options if o.option_id == "pred_r01"), None)
        assert pred_r01 is not None
        assert pred_r01.status == OPTION_BLOCKED_PROVENANCE

    def test_pred_r03_always_present(self):
        options = build_prediction_acquisition_options(self._large_game_logs(), pd.DataFrame())
        pred_r03 = next((o for o in options if o.option_id == "pred_r03"), None)
        assert pred_r03 is not None
        assert pred_r03.status == OPTION_BLOCKED_PROVENANCE

    def test_all_options_have_paper_only_true(self):
        options = build_prediction_acquisition_options(self._large_game_logs(), pd.DataFrame())
        for opt in options:
            assert opt.paper_only is True
            assert opt.production_ready is False

    def test_no_oof_inferred_from_y_true(self):
        """No option should describe y_true-based generation."""
        options = build_prediction_acquisition_options(self._large_game_logs(), pd.DataFrame())
        for opt in options:
            assert "y_true" not in opt.acquisition_method.lower() or "NEVER" in opt.acquisition_method.upper() or "not" in opt.acquisition_method.lower()


class TestRankPredictionOptions:
    def test_ready_comes_first(self):
        from wbc_backend.recommendation.p34_dual_source_acquisition_contract import (
            OPTION_BLOCKED_PROVENANCE,
            OPTION_READY_FOR_IMPLEMENTATION_PLAN,
            P34PredictionAcquisitionOption,
            LEAKAGE_NONE,
            RISK_MEDIUM,
            PREDICTION_TEMPLATE_COLUMNS,
        )

        def make_opt(option_id, status):
            return P34PredictionAcquisitionOption(
                option_id=option_id,
                source_name="test",
                source_type="oof_rebuild",
                acquisition_method="test",
                expected_columns=PREDICTION_TEMPLATE_COLUMNS,
                missing_columns=(),
                provenance_status="ok",
                license_status="internal",
                leakage_risk=LEAKAGE_NONE,
                implementation_risk=RISK_MEDIUM,
                estimated_coverage=0.9,
                status=status,
            )

        blocked = make_opt("block_opt", OPTION_BLOCKED_PROVENANCE)
        ready = make_opt("ready_opt", OPTION_READY_FOR_IMPLEMENTATION_PLAN)
        ranked = rank_prediction_options([blocked, ready])
        assert ranked[0].status == OPTION_READY_FOR_IMPLEMENTATION_PLAN

    def test_rejected_comes_last(self):
        from wbc_backend.recommendation.p34_dual_source_acquisition_contract import (
            OPTION_REJECTED_FAKE_OR_LEAKAGE,
            OPTION_REQUIRES_MANUAL_APPROVAL,
            P34PredictionAcquisitionOption,
            LEAKAGE_NONE,
            RISK_MEDIUM,
            PREDICTION_TEMPLATE_COLUMNS,
        )

        def make_opt(option_id, status):
            return P34PredictionAcquisitionOption(
                option_id=option_id,
                source_name="test",
                source_type="oof_rebuild",
                acquisition_method="test",
                expected_columns=PREDICTION_TEMPLATE_COLUMNS,
                missing_columns=(),
                provenance_status="ok",
                license_status="internal",
                leakage_risk=LEAKAGE_NONE,
                implementation_risk=RISK_MEDIUM,
                estimated_coverage=0.9,
                status=status,
            )

        rejected = make_opt("rej_opt", OPTION_REJECTED_FAKE_OR_LEAKAGE)
        manual = make_opt("man_opt", OPTION_REQUIRES_MANUAL_APPROVAL)
        ranked = rank_prediction_options([rejected, manual])
        assert ranked[-1].status == OPTION_REJECTED_FAKE_OR_LEAKAGE


class TestSummarizePredictionPlan:
    def test_returns_string(self):
        options = build_prediction_acquisition_options(pd.DataFrame(), pd.DataFrame())
        s = summarize_prediction_plan(options)
        assert isinstance(s, str)
        assert "PAPER_ONLY=True" in s

    def test_empty_options(self):
        s = summarize_prediction_plan([])
        assert "No" in s

    def test_contains_option_count(self):
        n = 2430
        game_logs = pd.DataFrame({"game_id": range(n)})
        options = build_prediction_acquisition_options(game_logs, pd.DataFrame())
        s = summarize_prediction_plan(options)
        assert str(len(options)) in s
