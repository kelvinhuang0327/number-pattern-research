"""P236-A local historical Run Line explorer tests."""
from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from wbc_backend.recommendation import run_line_backtest_explorer as explorer


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_mlb_run_line_backtest_explorer.py"
UPSTREAM = tuple(
    path
    for pattern in ("p226*", "p227*", "p228*", "p229*", "p230*", "p232*", "p235*")
    for path in sorted((ROOT / "report").glob(pattern))
    if path.is_file()
)


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_module_loads_p226_rows_and_p235_metadata():
    dataset = explorer.load_explorer_dataset()
    assert len(dataset.rows) == 972
    assert dataset.source_ledger.endswith("p226a_run_line_total_predictions.csv")
    assert dataset.package_path.endswith("p235a_final_2025_runline_backtest_package.json")
    assert set(explorer.LIMITATION_LABELS) <= set(dataset.package_limitation_labels)
    assert all(row["model_name"] == "poisson_team_rate_model" for row in dataset.rows)


def test_cli_default_run_writes_json_and_csv(tmp_path):
    json_path, csv_path = tmp_path / "result.json", tmp_path / "rows.csv"
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--output-json", str(json_path), "--output-csv", str(csv_path), "--quiet"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    with csv_path.open(newline="", encoding="utf-8") as handle:
        csv_rows = list(csv.DictReader(handle))
    assert payload["summary"]["row_count"] == len(csv_rows) == 25


def test_date_and_team_filters_work():
    dataset = explorer.load_explorer_dataset()
    rows = explorer.filter_rows(
        dataset.rows, date_from="2025-07-18", date_to="2025-07-19", team="rangers", top_n=None
    )
    assert rows
    assert all("2025-07-18" <= row["game_date"] <= "2025-07-19" for row in rows)
    assert all(
        "rangers" in row["home_team"].casefold() or "rangers" in row["away_team"].casefold()
        for row in rows
    )


def test_top_n_is_highest_confidence_and_deterministic():
    dataset = explorer.load_explorer_dataset()
    first = explorer.filter_rows(dataset.rows, top_n=17)
    second = explorer.filter_rows(reversed(dataset.rows), top_n=17)
    assert first == second
    assert len(first) == 17
    assert [row["predicted_side_probability"] for row in first] == sorted(
        (row["predicted_side_probability"] for row in first), reverse=True
    )


def test_min_confidence_works_and_invalid_value_is_clear():
    dataset = explorer.load_explorer_dataset()
    rows = explorer.filter_rows(dataset.rows, min_confidence=0.75, top_n=None)
    assert rows and all(row["predicted_side_probability"] >= 0.75 for row in rows)
    with pytest.raises(explorer.ExplorerError, match="min-confidence"):
        explorer.filter_rows(dataset.rows, min_confidence=0.49)


def test_summary_metrics_are_internally_consistent():
    rows = explorer.filter_rows(explorer.load_explorer_dataset().rows, top_n=31)
    summary = explorer.summarize_rows(rows)
    assert summary["row_count"] == 31
    assert summary["accuracy"] == pytest.approx(sum(row["correct"] for row in rows) / 31)
    expected_brier = sum(
        (row["predicted_home_probability"] - (row["actual_side"] == "HOME")) ** 2
        for row in rows
    ) / 31
    assert summary["brier_score"] == pytest.approx(expected_brier)
    assert summary["home_cover_rate"] + summary["away_cover_rate"] == pytest.approx(1.0)


def test_limitation_labels_and_no_prediction_flag_present():
    dataset = explorer.load_explorer_dataset()
    payload = explorer.build_output_payload(dataset, [], {"top_n": 0})
    labels = set(payload["metadata"]["limitation_labels"])
    for label in (
        "NOT_BETTING_EDGE", "NOT_FUTURE_PREDICTION", "NOT_LIVE", "NOT_PRODUCTION",
        "NOT_TRUE_PIT", "NOT_MULTI_SEASON_VALIDATION", "ODDS_PROVENANCE_UNVERIFIED",
        "2025-ONLY", "HISTORICAL_PAPER_ONLY",
    ):
        assert label in labels
    assert payload["metadata"]["generates_new_predictions"] is False


def test_unknown_schema_stops_clearly(tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text("game_id,game_date\ng1,2025-01-01\n", encoding="utf-8")
    with pytest.raises(explorer.ExplorerError, match="UNSUPPORTED_SCHEMA"):
        explorer.load_explorer_dataset(bad)


def test_outputs_deterministic_and_upstream_artifacts_unchanged(tmp_path):
    before = {path: _digest(path) for path in UPSTREAM}
    dataset = explorer.load_explorer_dataset()
    rows = explorer.filter_rows(dataset.rows, top_n=25)
    payload = explorer.build_output_payload(dataset, rows, {"top_n": 25})
    j1, c1, j2, c2 = (tmp_path / name for name in ("a.json", "a.csv", "b.json", "b.csv"))
    explorer.write_outputs(payload, j1, c1)
    explorer.write_outputs(payload, j2, c2)
    assert j1.read_bytes() == j2.read_bytes()
    assert c1.read_bytes() == c2.read_bytes()
    assert before == {path: _digest(path) for path in UPSTREAM}
