from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "show_mlb_local_retrain_results.py"
OUT_MD = ROOT / "report" / "p208a_visible_scorecard_result_viewer.md"
OUT_JSON = ROOT / "report" / "p208a_visible_scorecard_result_viewer.json"


def _load_module():
    spec = importlib.util.spec_from_file_location("show_mlb_local_retrain_results", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run_cli() -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", str(SCRIPT)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )


def test_cli_runs_from_clean_checkout_and_writes_reports():
    result = _run_cli()

    assert "P208-A VISIBLE SCORECARD RESULT VIEWER" in result.stdout
    assert OUT_MD.exists() and OUT_MD.stat().st_size > 0
    assert OUT_JSON.exists() and OUT_JSON.stat().st_size > 0


def test_report_files_are_deterministic():
    _run_cli()
    first = (_sha(OUT_MD), _sha(OUT_JSON))
    _run_cli()
    second = (_sha(OUT_MD), _sha(OUT_JSON))

    assert first == second


def test_no_affirmative_live_or_edge_claims_appear():
    _run_cli()
    text = (OUT_MD.read_text(encoding="utf-8") + OUT_JSON.read_text(encoding="utf-8")).lower()

    forbidden = [
        "expected value",
        "positive edge",
        "betting edge",
        "roi",
        "payout",
        "kelly",
        "clv",
        "production ready",
        "live-market ready",
        "live market ready",
    ]
    for phrase in forbidden:
        assert phrase not in text
    assert "historical replay/backtest only" in text
    assert "not for live use and not a future betting claim" in text


def test_expected_model_metrics_are_loaded_correctly():
    _run_cli()
    payload = json.loads(OUT_JSON.read_text(encoding="utf-8"))

    assert payload["best_accuracy_model"]["model_name"] == "retrained_team_history_smooth"
    assert payload["best_accuracy_model"]["accuracy"] == 0.563786
    assert payload["best_brier_model"]["model_name"] == "calibrated_elo_recent_form"
    assert payload["best_brier_model"]["brier_score"] == 0.246033
    assert len(payload["leaderboard"]) == 5
    assert payload["leaderboard"][-1]["reference_only"] is True


def test_confidence_band_and_selected_side_summaries_are_present():
    _run_cli()
    payload = json.loads(OUT_JSON.read_text(encoding="utf-8"))

    assert payload["confidence_band_summary"] == {
        "HIGH": {"correct": 23, "n": 32},
        "LOW": {"correct": 221, "n": 442},
        "MEDIUM": {"correct": 285, "n": 498},
    }
    assert payload["selected_side_distribution"] == {"AWAY": 205, "HOME": 767}


def test_sample_predictions_are_historical_only_and_sorted_by_confidence():
    _run_cli()
    payload = json.loads(OUT_JSON.read_text(encoding="utf-8"))
    samples = payload["sample_predictions"]

    assert samples
    assert {row["label"] for row in samples} == {"historical replay / backtest only"}
    assert {row["learning_guard_status"] for row in samples} == {"LOCAL_HISTORICAL_BACKTEST_ONLY"}
    assert all(row["model_name"] == payload["best_brier_model"]["model_name"] for row in samples)
    probabilities = [row["selected_side_probability"] for row in samples]
    assert probabilities == sorted(probabilities, reverse=True)


def test_build_payload_uses_p207a_artifact_inputs():
    module = _load_module()
    scorecard = json.loads((ROOT / "report" / "p207a_local_retrain_scorecard.json").read_text(encoding="utf-8"))
    with (ROOT / "report" / "p207a_local_retrain_model_comparison.csv").open(newline="", encoding="utf-8") as f:
        model_rows = list(module.csv.DictReader(f))
    with (ROOT / "report" / "p207a_local_retrain_predictions.csv").open(newline="", encoding="utf-8") as f:
        prediction_rows = list(module.csv.DictReader(f))

    payload = module.build_viewer_payload(scorecard, model_rows, prediction_rows)

    assert payload["source_artifacts"] == [
        "p207a_local_retrain_scorecard.json",
        "p207a_local_retrain_model_comparison.csv",
        "p207a_local_retrain_predictions.csv",
    ]
    assert payload["claim_status"] == {
        "historical_only": True,
        "provider_called": False,
        "db_written": False,
        "production_enabled": False,
        "ticket_mutated": False,
    }
