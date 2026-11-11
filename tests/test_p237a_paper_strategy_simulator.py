"""P237-A result-only paper strategy simulator tests."""
from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from wbc_backend.recommendation import paper_strategy_simulator as simulator


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_mlb_paper_strategy_simulator.py"
UPSTREAM = tuple(
    path
    for pattern in ("p226*", "p228*", "p232*", "p235*", "p236*")
    for path in sorted((ROOT / "report").glob(pattern))
    if path.is_file()
)
ROI_REASON = (
    "NO_PER_BET_PRICE_IN_INPUT_LEDGER; "
    "ONLY_LOCAL_PRICE_SOURCE_IS_POST_GAME_UNVERIFIED_SNAPSHOT(is_verified_real=False); "
    "FLAT_PRICE_ASSUMPTION_REJECTED_AS_SYSTEMATICALLY_WRONG_FOR_RUN_LINE"
)


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_normalized_fixture(path: Path, rows: list[dict[str, object]]) -> None:
    fieldnames = [
        "game_id",
        "game_date",
        "home_team",
        "away_team",
        "line_value",
        "model_name",
        "predicted_home_probability",
        "predicted_side",
        "predicted_side_probability",
        "actual_side",
        "correct",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _synthetic_rows() -> list[dict[str, object]]:
    return [
        {
            "game_id": "g1",
            "game_date": "2025-07-01",
            "home_team": "Home A",
            "away_team": "Away A",
            "line_value": "-1.5",
            "model_name": "poisson_team_rate_model",
            "predicted_home_probability": 0.6,
            "predicted_side": "HOME",
            "predicted_side_probability": 0.6,
            "actual_side": "HOME",
            "correct": 1,
        },
        {
            "game_id": "g2",
            "game_date": "2025-07-02",
            "home_team": "Home B",
            "away_team": "Away B",
            "line_value": "1.5",
            "model_name": "poisson_team_rate_model",
            "predicted_home_probability": 0.3,
            "predicted_side": "AWAY",
            "predicted_side_probability": 0.7,
            "actual_side": "HOME",
            "correct": 0,
        },
        {
            "game_id": "g3",
            "game_date": "2025-07-03",
            "home_team": "Home C",
            "away_team": "Away C",
            "line_value": "-1.5",
            "model_name": "poisson_team_rate_model",
            "predicted_home_probability": 0.8,
            "predicted_side": "HOME",
            "predicted_side_probability": 0.8,
            "actual_side": "AWAY",
            "correct": 0,
        },
    ]


def test_gate_0_anchor_full_ledger_metrics():
    dataset = simulator.load_paper_strategy_dataset(ROOT / "report" / "p226a_run_line_total_predictions.csv")
    payload, decisions = simulator.build_output_payload(dataset, min_confidence=0.5)
    assert payload["decisions_count"] == len(decisions) == 972
    assert payload["hit_rate"] == pytest.approx(0.6008, abs=1e-3)
    assert payload["brier_score"] == pytest.approx(0.2395, abs=1e-3)


def test_threshold_inclusivity_and_result_only_decision_rows(tmp_path):
    fixture = tmp_path / "rows.csv"
    _write_normalized_fixture(
        fixture,
        [
            {
                "game_id": "edge",
                "game_date": "2025-07-01",
                "home_team": "Home",
                "away_team": "Away",
                "line_value": "-1.5",
                "model_name": "poisson_team_rate_model",
                "predicted_home_probability": 0.5,
                "predicted_side": "HOME",
                "predicted_side_probability": 0.5,
                "actual_side": "HOME",
                "correct": 1,
            }
        ],
    )
    payload, decisions = simulator.build_output_payload(
        simulator.load_paper_strategy_dataset(fixture), min_confidence=0.5
    )
    assert payload["decisions_count"] == 1
    assert decisions[0]["stake_units"] == 1.0
    assert decisions[0]["pnl_units"] is None
    assert decisions[0]["settlement_status"] == "RESULT_ONLY_NO_PRICE"


def test_synthetic_fixture_metrics_and_side_distribution(tmp_path):
    fixture = tmp_path / "rows.csv"
    _write_normalized_fixture(fixture, _synthetic_rows())
    payload, _ = simulator.build_output_payload(
        simulator.load_paper_strategy_dataset(fixture), min_confidence=0.6
    )
    assert payload["decisions_count"] == 3
    assert payload["hit_rate"] == pytest.approx(1 / 3)
    assert payload["brier_score"] == pytest.approx(((0.6 - 1) ** 2 + (0.3 - 1) ** 2 + 0.8**2) / 3)
    assert payload["average_confidence"] == pytest.approx(0.7)
    assert payload["side_distribution"] == {"HOME": 2, "AWAY": 1}
    assert payload["stake_units_total"] == payload["decisions_count"]


def test_roi_is_unavailable_and_forbidden_keys_absent(tmp_path):
    fixture = tmp_path / "rows.csv"
    _write_normalized_fixture(fixture, _synthetic_rows())
    payload, _ = simulator.build_output_payload(
        simulator.load_paper_strategy_dataset(fixture), min_confidence=0.6
    )
    assert payload["roi"] is None
    assert payload["roi_status"] == "ROI_UNAVAILABLE"
    assert payload["roi_unavailable_reason"] == ROI_REASON
    serialized = json.dumps(payload).casefold()
    for forbidden in ("ev", "kelly", "best_threshold", "recommended_bet"):
        assert forbidden not in serialized
    assert isinstance(payload["roi"], type(None))


def test_empty_decision_set_returns_null_metrics(tmp_path):
    fixture = tmp_path / "rows.csv"
    _write_normalized_fixture(fixture, _synthetic_rows())
    payload, decisions = simulator.build_output_payload(
        simulator.load_paper_strategy_dataset(fixture),
        min_confidence=0.8,
        date_from="2025-08-01",
        date_to="2025-08-02",
    )
    assert decisions == []
    assert payload["decisions_count"] == 0
    assert payload["hit_rate"] is None
    assert payload["brier_score"] is None
    assert payload["average_confidence"] is None
    assert payload["stake_units_total"] == 0.0


def test_output_csv_columns_and_deterministic_rerun(tmp_path):
    fixture = tmp_path / "rows.csv"
    _write_normalized_fixture(fixture, _synthetic_rows())
    j1, c1, j2, c2 = (tmp_path / name for name in ("a.json", "a.csv", "b.json", "b.csv"))
    for json_path, csv_path in ((j1, c1), (j2, c2)):
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--source-csv",
                str(fixture),
                "--min-confidence",
                "0.6",
                "--output-json",
                str(json_path),
                "--output-csv",
                str(csv_path),
                "--quiet",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        assert result.returncode == 0, result.stderr
    assert j1.read_bytes() == j2.read_bytes()
    assert c1.read_bytes() == c2.read_bytes()
    with c1.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
    assert reader.fieldnames == simulator.DECISION_FIELDNAMES
    assert all(row["stake_units"] == "1.0" for row in rows)
    assert all(row["pnl_units"] == "" for row in rows)
    assert all(row["settlement_status"] == "RESULT_ONLY_NO_PRICE" for row in rows)


def test_limitation_labels_and_no_prediction_flag_present(tmp_path):
    fixture = tmp_path / "rows.csv"
    _write_normalized_fixture(fixture, _synthetic_rows())
    payload, _ = simulator.build_output_payload(
        simulator.load_paper_strategy_dataset(fixture), min_confidence=0.6
    )
    for label in (
        "2025-only",
        "historical paper-only",
        "odds provenance unverified",
        "not true-PIT",
        "not betting edge",
        "not future prediction",
        "not live",
        "not production",
        "not real betting",
        "not multi-season validation",
    ):
        assert label in payload["metadata"]["limitation_labels"]
    assert payload["metadata"]["generates_new_predictions"] is False
    assert {item["status"] for item in payload["threshold_sweep"]} == {
        "IN_SAMPLE_DESCRIPTIVE_ONLY"
    }


def test_invalid_thresholds_and_reversed_dates_fail(tmp_path):
    fixture = tmp_path / "rows.csv"
    _write_normalized_fixture(fixture, _synthetic_rows())
    dataset = simulator.load_paper_strategy_dataset(fixture)
    for threshold in (0.49, 1.01):
        with pytest.raises(simulator.ExplorerError, match="min-confidence"):
            simulator.build_output_payload(dataset, min_confidence=threshold)
    with pytest.raises(simulator.ExplorerError, match="date-from"):
        simulator.build_output_payload(
            dataset, min_confidence=0.6, date_from="2025-08-02", date_to="2025-08-01"
        )


def test_upstream_artifacts_are_not_modified(tmp_path):
    before = {path: _digest(path) for path in UPSTREAM}
    json_path, csv_path = tmp_path / "summary.json", tmp_path / "decisions.csv"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--source-csv",
            str(ROOT / "report" / "p226a_run_line_total_predictions.csv"),
            "--min-confidence",
            "0.5",
            "--output-json",
            str(json_path),
            "--output-csv",
            str(csv_path),
            "--quiet",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr
    assert before == {path: _digest(path) for path in UPSTREAM}
