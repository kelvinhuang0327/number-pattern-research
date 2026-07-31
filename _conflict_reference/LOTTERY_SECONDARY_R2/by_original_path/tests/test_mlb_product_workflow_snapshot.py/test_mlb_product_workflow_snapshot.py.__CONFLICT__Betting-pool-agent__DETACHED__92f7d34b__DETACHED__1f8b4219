from __future__ import annotations

import csv
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import _p275_prospective_availability_consumer_gate as p275
from wbc_backend.recommendation import mlb_product_workflow_snapshot as wf


GAME_ID = "mlb_2026_825108"
OBSERVED_AT = "2026-07-13T07:17:10.769880Z"
BEFORE = "2026-07-13T07:17:10.769879Z"
AFTER = "2026-07-13T07:17:10.769881Z"


def _write_eval_csv(path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            [
                "Date",
                "Away",
                "Away Score",
                "Home",
                "Home Score",
                "Status",
                "Away ML",
                "Home ML",
                "Home RL Spread",
                "RL Away",
                "RL Home",
                "O/U",
                "Over",
                "Under",
            ]
        )
        writer.writerow(
            [
                "2025-08-01",
                "Away A",
                "3",
                "Home A",
                "5",
                "Final",
                "+120",
                "-130",
                "-1.5",
                "-105",
                "-115",
                "8.5",
                "-110",
                "-110",
            ]
        )
        writer.writerow(
            [
                "2025-08-02",
                "Away B",
                "6",
                "Home B",
                "2",
                "Final",
                "-140",
                "+125",
                "+1.5",
                "-120",
                "+100",
                "9.0",
                "+100",
                "-120",
            ]
        )


def test_american_to_decimal_and_ev_kelly():
    assert wf.american_to_decimal("-150") == pytest.approx(1.666667)
    assert wf.american_to_decimal("+125") == pytest.approx(2.25)
    assert wf.american_to_decimal("0") is None

    result = wf.calculate_ev_kelly(probability=0.6, decimal_odds=2.0)
    assert result["expected_value_per_unit"] == pytest.approx(0.2)
    assert result["full_kelly_fraction"] == pytest.approx(0.2)
    assert result["used_kelly_fraction"] == pytest.approx(0.015)


def test_build_moneyline_backtest_scores_candidates(tmp_path: Path):
    eval_csv = tmp_path / "eval.csv"
    _write_eval_csv(eval_csv)
    predictions = [
        {
            "game_date": "2025-08-01",
            "away_team": "Away A",
            "home_team": "Home A",
            "model_name": "model_x",
            "predicted_home_win_probability": 0.66,
            "selected_side": "HOME",
            "confidence_band": "HIGH",
            "actual_home_win": 1,
            "correct": 1,
        },
        {
            "game_date": "2025-08-02",
            "away_team": "Away B",
            "home_team": "Home B",
            "model_name": "model_x",
            "predicted_home_win_probability": 0.44,
            "selected_side": "AWAY",
            "confidence_band": "MEDIUM",
            "actual_home_win": 0,
            "correct": 1,
        },
    ]

    result = wf.build_moneyline_backtest(
        scorecard_predictions=predictions,
        eval_path=eval_csv,
        model_name="model_x",
        min_ev=0.0,
        min_edge=0.0,
    )

    assert result["summary"]["prediction_rows_scored"] == 2
    assert result["summary"]["paper_candidate_count"] >= 1
    assert result["summary"]["hit_rate"] == pytest.approx(1.0)
    assert all(row["guard_status"] == "PAPER_ONLY_LOCAL_REPLAY" for row in result["rows"])


def test_market_coverage_reports_supported_and_pending_markets(tmp_path: Path):
    eval_csv = tmp_path / "eval.csv"
    _write_eval_csv(eval_csv)

    coverage = wf.build_market_coverage(eval_csv)

    assert coverage["markets"]["moneyline"]["status"] == "EVALUATED_IN_WORKFLOW"
    assert coverage["markets"]["moneyline"]["rows_with_lines"] == 2
    assert coverage["markets"]["run_line"]["rows_with_lines"] == 2
    assert coverage["markets"]["total_runs"]["rows_with_lines"] == 2
    assert coverage["markets"]["first_five"]["status"] == "NO_LOCAL_F5_LINES_OR_F5_RESULTS_IN_SOURCE"


def test_local_2026_snapshot_includes_outcome_accuracy(tmp_path: Path):
    pred = tmp_path / "pred.jsonl"
    out = tmp_path / "out.jsonl"
    rows = [
        {
            "game_id": GAME_ID,
            "game_date": "2026-05-20",
            "away_team": "Away",
            "home_team": "Home",
            "model_probability": 0.62,
            "predicted_side": "home",
            "source_prediction_version": "v1",
            "paper_only": True,
            "production_ready": False,
        }
    ]
    pred.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    out.write_text(
        json.dumps(
            {
                **rows[0],
                "outcome_available": True,
                "is_correct": True,
                "rule_primary_125_flag": True,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    snapshot = wf.build_local_2026_prediction_snapshot(
        prediction_path=pred,
        outcome_path=out,
        feature_as_of_utc=OBSERVED_AT,
    )

    assert snapshot["rows"] == 1
    assert snapshot["latest_local_prediction_date"] == "2026-05-20"
    assert snapshot["outcome_attached_summary"]["all_outcome_attached"]["accuracy"] == pytest.approx(1.0)
    coverage = snapshot["availability_gate_coverage"]
    assert coverage["total_outcome_rows"] == 1
    assert coverage["raw_outcome_available_true_rows"] == 1
    assert coverage["gate_available_rows"] == 1
    assert coverage["unavailable_before_observation_rows"] == 0
    assert coverage["missing_or_invalid_evidence_rows"] == 0
    assert snapshot["top_latest_predictions"][0]["selected_side_probability"] == pytest.approx(0.62)
    assert snapshot["generated_by_corrected_retrained_model"] is False
    assert snapshot["corrected_model_handoff_status"] == "NOT_PERFORMED"


@pytest.mark.parametrize(
    ("game_id", "feature_as_of_utc", "unavailable", "missing_invalid", "reason"),
    [
        (GAME_ID, BEFORE, 1, 0, p275.RESULT_NOT_YET_AVAILABLE),
        ("mlb_2026_999999", AFTER, 0, 1, p275.MISSING_AVAILABILITY_EVIDENCE),
        (GAME_ID, None, 0, 1, p275.INVALID_FEATURE_AS_OF_UTC),
    ],
)
def test_raw_outcome_flag_cannot_bypass_availability_gate(
    tmp_path: Path,
    game_id: str,
    feature_as_of_utc: str | None,
    unavailable: int,
    missing_invalid: int,
    reason: str,
) -> None:
    pred = tmp_path / "pred.jsonl"
    out = tmp_path / "out.jsonl"
    row = {
        "game_id": game_id,
        "game_date": "2026-05-20",
        "away_team": "Away",
        "home_team": "Home",
        "model_probability": 0.62,
        "predicted_side": "home",
        "source_prediction_version": "p84b_diagnostic_baseline_v1",
        "paper_only": True,
        "production_ready": False,
    }
    pred.write_text(json.dumps(row) + "\n", encoding="utf-8")
    out.write_text(
        json.dumps({**row, "outcome_available": True, "is_correct": True}) + "\n",
        encoding="utf-8",
    )

    snapshot = wf.build_local_2026_prediction_snapshot(
        prediction_path=pred,
        outcome_path=out,
        feature_as_of_utc=feature_as_of_utc,
    )

    coverage = snapshot["availability_gate_coverage"]
    assert coverage["raw_outcome_available_true_rows"] == 1
    assert coverage["gate_available_rows"] == 0
    assert coverage["result_metric_rows"] == 0
    assert coverage["unavailable_before_observation_rows"] == unavailable
    assert coverage["missing_or_invalid_evidence_rows"] == missing_invalid
    assert coverage["block_reason_counts"] == {reason: 1}
    assert snapshot["outcome_attached_summary"]["all_outcome_attached"] == {
        "n": 0,
        "correct": 0,
        "accuracy": None,
    }


def test_existing_consumer_invokes_p275_with_explicit_evidence_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pred = tmp_path / "pred.jsonl"
    out = tmp_path / "out.jsonl"
    index_path = tmp_path / "index.json"
    manifest_path = tmp_path / "SHA256SUMS"
    row = {
        "game_id": GAME_ID,
        "game_date": "2026-05-20",
        "away_team": "Away",
        "home_team": "Home",
        "model_probability": 0.62,
        "predicted_side": "home",
        "source_prediction_version": "p84b_diagnostic_baseline_v1",
    }
    pred.write_text(json.dumps(row) + "\n", encoding="utf-8")
    out.write_text(
        json.dumps({**row, "outcome_available": True, "is_correct": True}) + "\n",
        encoding="utf-8",
    )
    calls = []

    def fake_gate(**kwargs):
        calls.append(kwargs)
        return p275.AvailabilityGateDecision(
            result_usage_allowed=False,
            block_reason=p275.MISSING_AVAILABILITY_EVIDENCE,
            game_id=kwargs["game_id"],
            feature_as_of_utc=kwargs["feature_as_of_utc"],
            result_available_at_utc=None,
        )

    monkeypatch.setattr(wf.p275, "evaluate_result_availability", fake_gate)

    snapshot = wf.build_local_2026_prediction_snapshot(
        prediction_path=pred,
        outcome_path=out,
        feature_as_of_utc=AFTER,
        availability_index_path=index_path,
        availability_manifest_path=manifest_path,
    )

    assert calls == [
        {
            "game_id": GAME_ID,
            "feature_as_of_utc": AFTER,
            "index_path": index_path,
            "manifest_path": manifest_path,
        }
    ]
    assert snapshot["availability_gate_coverage"]["gate_available_rows"] == 0


def test_availability_gated_snapshot_is_deterministic(tmp_path: Path) -> None:
    pred = tmp_path / "pred.jsonl"
    out = tmp_path / "out.jsonl"
    row = {
        "game_id": GAME_ID,
        "game_date": "2026-05-20",
        "away_team": "Away",
        "home_team": "Home",
        "model_probability": 0.62,
        "predicted_side": "home",
        "source_prediction_version": "p84b_diagnostic_baseline_v1",
    }
    pred.write_text(json.dumps(row) + "\n", encoding="utf-8")
    out.write_text(
        json.dumps({**row, "outcome_available": True, "is_correct": True}) + "\n",
        encoding="utf-8",
    )

    first = wf.build_local_2026_prediction_snapshot(
        prediction_path=pred,
        outcome_path=out,
        feature_as_of_utc=AFTER,
    )
    second = wf.build_local_2026_prediction_snapshot(
        prediction_path=pred,
        outcome_path=out,
        feature_as_of_utc=AFTER,
    )

    assert first == second


def test_visible_reports_separate_corrected_2025_from_baseline_2026(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    eval_csv = tmp_path / "eval.csv"
    _write_eval_csv(eval_csv)
    prediction_path = tmp_path / "predictions_2026.jsonl"
    prediction_path.write_text(
        json.dumps(
            {
                "game_date": "2026-05-31",
                "away_team": "Away 2026",
                "home_team": "Home 2026",
                "model_probability": 0.57,
                "predicted_side": "home",
                "source_prediction_version": "p84b_diagnostic_baseline_v1",
                "paper_only": True,
                "production_ready": False,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    shadow_prediction_path = tmp_path / "corrected_shadow.csv"
    shadow_prediction_path.write_text(
        "game_id,game_date,away_team,home_team,predicted_side,"
        "shadow_home_win_probability,state_mode\n"
        "shadow-1,2026-05-31,Away 2026,Home 2026,HOME,0.61,"
        "frozen_final_2025_state\n",
        encoding="utf-8",
    )
    shadow_manifest_path = tmp_path / "corrected_shadow_manifest.json"
    shadow_manifest_path.write_text(
        json.dumps(
            {
                "artifact_version": "p278a_corrected_moneyline_shadow_v1",
                "source_git_commit": "source-commit",
                "state_mode": "frozen_final_2025_state",
                "model": {
                    "algorithm": "retrained_team_history_smooth",
                    "model_code_config_fingerprint": "model-fingerprint",
                },
                "training": {"training_input_fingerprint": "training-fingerprint"},
                "prediction_input": {
                    "prediction_input_fingerprint": "input-fingerprint"
                },
                "p275_state_updates": {
                    "attempted": 0,
                    "allowed": 0,
                    "denied": 0,
                    "applied": 0,
                },
                "outcome_evaluation": {
                    "outcome_evaluation_denominator": 0,
                    "accuracy": None,
                    "brier_score": None,
                    "roi": None,
                    "expected_value": None,
                    "kelly": None,
                },
                "artifacts": {
                    "prediction_row_count": 1,
                    "predictions_csv_sha256": wf._sha256_file(shadow_prediction_path),
                },
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    divergence_summary_path = tmp_path / "moneyline_divergence_summary.json"
    divergence_summary_path.write_text(
        json.dumps(
            {
                "status": "AVAILABLE_OUTCOME_FREE_DIVERGENCE_BASELINE",
                "comparison_version": "p279a.moneyline_shadow_divergence.v1",
                "comparison_contract": {
                    "outcome_fields_used": "NONE",
                    "odds_fields_used": "NONE",
                    "evaluation_denominator": 0,
                },
                "alignment": {"shared_game_count": 828},
                "source_artifacts": {
                    "p84b": {"model_version": "p84b_diagnostic_baseline_v1"},
                    "p278": {
                        "model_version": "p278a_corrected_moneyline_shadow_v1"
                    },
                },
                "output_artifacts": {
                    "ledger_csv": "report/mlb_2026_moneyline_shadow_divergence.csv"
                },
                "claims": {
                    "model_winner_declared": False,
                    "champion_activated": False,
                    "future_outcome_evaluation_requires_prospective_availability": True,
                },
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    predictions = [
        {
            "game_date": "2025-08-01",
            "away_team": "Away A",
            "home_team": "Home A",
            "model_name": "corrected_model",
            "predicted_home_win_probability": 0.66,
            "selected_side": "HOME",
            "confidence_band": "HIGH",
            "actual_home_win": 1,
            "correct": 1,
        },
        {
            "game_date": "2025-08-02",
            "away_team": "Away B",
            "home_team": "Home B",
            "model_name": "corrected_model",
            "predicted_home_win_probability": 0.44,
            "selected_side": "AWAY",
            "confidence_band": "MEDIUM",
            "actual_home_win": 0,
            "correct": 1,
        },
    ]
    scorecard = SimpleNamespace(
        warmup_rows=10,
        eval_rows=20,
        split={
            "train_period": ["2025-04-01", "2025-07-31"],
            "test_period": ["2025-08-01", "2025-09-30"],
            "train_rows": 12,
            "test_rows": 8,
            "train_date_count": 10,
            "test_date_count": 8,
            "requested_train_frac": 0.6,
            "effective_train_frac": 0.6,
            "split_strategy": "complete_date_boundary_nearest_requested_row_fraction",
            "tie_rule": "earlier boundary (smaller train partition) wins equal-distance ties",
            "selected_boundary_date": "2025-07-31",
            "selected_test_start_date": "2025-08-01",
        },
        best_by_brier="corrected_model",
        train_home_win_prior=0.55,
        platt={"A": 1.0, "B": 0.0},
        comparison=[
            {
                "model_name": "corrected_model",
                "accuracy": 0.625,
                "brier_score": 0.24,
                "log_loss": 0.68,
                "calibration_error": 0.04,
                "coverage": 1.0,
            }
        ],
        confidence_band_breakdown={"MEDIUM": {"n": 8, "correct": 5}},
        selected_side_distribution={"HOME": 4, "AWAY": 4},
        predictions=predictions,
    )
    monkeypatch.setattr(wf, "run_scorecard", lambda *_args, **_kwargs: scorecard)

    payload = wf.run_workflow_snapshot(
        warmup_path=tmp_path / "warmup.csv",
        eval_path=eval_csv,
        prediction_2026_path=prediction_path,
        corrected_shadow_manifest_path=shadow_manifest_path,
        corrected_shadow_prediction_path=shadow_prediction_path,
        moneyline_divergence_summary_path=divergence_summary_path,
    )
    paths = wf.write_workflow_reports(payload, tmp_path / "report")
    markdown = paths["markdown"].read_text(encoding="utf-8")
    json_payload = json.loads(paths["json"].read_text(encoding="utf-8"))

    assert "Corrected 2025 Local Retrain and Evaluation" in markdown
    assert "Existing 2026 Prediction Snapshot (Separate and Stale)" in markdown
    assert "Corrected 2026 Moneyline Shadow (Separate and Retrospective)" in markdown
    assert "P279-A Outcome-Free Moneyline Prediction Divergence" in markdown
    assert "p84b_diagnostic_baseline_v1" in markdown
    assert "Corrected 2025 retrained model generated these 2026 predictions: `False`" in markdown
    assert "not a verified betting edge" in markdown
    assert "This measures prediction divergence, not model performance." in markdown
    assert "Neither model is activated or declared superior." in markdown
    snapshot = json_payload["local_2026_prediction_snapshot"]
    assert snapshot["source_prediction_version"] == "p84b_diagnostic_baseline_v1"
    assert snapshot["generated_by_corrected_retrained_model"] is False
    shadow_snapshot = json_payload["corrected_moneyline_shadow"]
    assert shadow_snapshot["artifact_version"] == "p278a_corrected_moneyline_shadow_v1"
    assert shadow_snapshot["algorithm"] == "retrained_team_history_smooth"
    assert shadow_snapshot["separate_from_p84b"] is True
    assert shadow_snapshot["p84b_replaced"] is False
    assert shadow_snapshot["outcome_evaluation"]["denominator"] == 0
    divergence = json_payload["moneyline_shadow_divergence"]
    assert divergence["shared_game_count"] == 828
    assert divergence["outcome_fields_used"] == "NONE"
    assert divergence["odds_fields_used"] == "NONE"
    assert divergence["evaluation_denominator"] == 0
    assert divergence["divergence_not_performance"] is True
    assert divergence["model_winner_declared"] is False
    assert divergence["champion_activated"] is False
    assert json_payload["claim_status"]["verified_betting_edge_established"] is False
    assert json_payload["claim_status"]["corrected_model_to_2026_handoff_performed"] is True
    assert json_payload["claim_status"]["p84b_baseline_replaced"] is False
    assert (
        json_payload["claim_status"]["moneyline_divergence_uses_outcomes_or_odds"]
        is False
    )
    assert (
        json_payload["claim_status"]["moneyline_divergence_is_performance_evaluation"]
        is False
    )
    assert json_payload["claim_status"]["moneyline_model_superiority_declared"] is False


def test_snapshot_only_regeneration_does_not_rewrite_tabular_outputs(
    tmp_path: Path,
) -> None:
    out_dir = tmp_path / "report"
    out_dir.mkdir()
    moneyline = out_dir / "mlb_prediction_workflow_moneyline_backtest.csv"
    latest = out_dir / "mlb_prediction_workflow_latest_2026_predictions.csv"
    moneyline.write_bytes(b"moneyline-sentinel\n")
    latest.write_bytes(b"p84b-sentinel\n")
    payload = {
        "moneyline_backtest_rows": [{"x": 1}],
        "local_2026_prediction_snapshot": {"top_latest_predictions": []},
        "corrected_moneyline_shadow": {"status": "NOT_SUPPLIED"},
        "retrain_scorecard": {
            "result_context": "x",
            "state_transition_contract": "x",
            "warmup_rows": 0,
            "eval_rows": 0,
            "split": {
                "train_period": ["a", "b"],
                "test_period": ["c", "d"],
                "train_rows": 0,
                "test_rows": 0,
                "train_date_count": 0,
                "test_date_count": 0,
                "requested_train_frac": 0.6,
                "effective_train_frac": 0.6,
                "split_strategy": "x",
                "tie_rule": "x",
                "selected_boundary_date": "b",
                "selected_test_start_date": "c",
            },
            "best_by_brier": "x",
            "model_comparison": [],
        },
        "moneyline_strategy": {
            "summary": {
                "odds_timing_status": "x",
                "claim_status": "x",
                "prediction_rows_scored": 0,
                "paper_candidate_count": 0,
                "paper_candidate_rate": 0.0,
                "hit_rate": None,
                "net_result_units": 0,
                "roi_on_staked_units": None,
                "avg_expected_value_per_unit": None,
                "avg_used_kelly_fraction": None,
            },
            "top_candidates": [],
        },
        "market_coverage": {"markets": {}},
        "scope": "x",
        "disclaimer": "x",
    }

    wf.write_workflow_reports(payload, out_dir, write_tabular_outputs=False)

    assert moneyline.read_bytes() == b"moneyline-sentinel\n"
    assert latest.read_bytes() == b"p84b-sentinel\n"
