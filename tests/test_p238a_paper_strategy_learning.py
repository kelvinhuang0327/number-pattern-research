"""P238-A result-only paper strategy learning summary tests."""
from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from wbc_backend.recommendation import paper_strategy_learning as learning


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_mlb_paper_strategy_learning.py"
FIXED_TIME = "2026-07-08T00:00:00Z"
ROI_REASON = (
    "RESULT_ONLY_PAPER_DECISIONS_HAVE_NO_PER_BET_PRICE; "
    "P237A_CONTRACT_FORBIDS_PNL_AND_ROI; "
    "ODDS_PROVENANCE_UNVERIFIED"
)


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_decisions(path: Path, rows: list[dict[str, object]]) -> None:
    fieldnames = [
        "game_id",
        "game_date",
        "home_team",
        "away_team",
        "market",
        "line_value",
        "model_name",
        "predicted_side",
        "predicted_side_probability",
        "actual_side",
        "correct",
        "stake_units",
        "pnl_units",
        "settlement_status",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _rows() -> list[dict[str, object]]:
    base = {
        "home_team": "Home",
        "away_team": "Away",
        "market": "run_line",
        "line_value": "-1.5",
        "model_name": "poisson_team_rate_model",
        "actual_side": "HOME",
        "pnl_units": "",
        "settlement_status": "RESULT_ONLY_NO_PRICE",
    }
    return [
        {
            **base,
            "game_id": "g1",
            "game_date": "2025-05-01",
            "predicted_side": "HOME",
            "predicted_side_probability": 0.5,
            "correct": 1,
            "stake_units": 1.0,
        },
        {
            **base,
            "game_id": "g2",
            "game_date": "2025-05-02",
            "predicted_side": "AWAY",
            "predicted_side_probability": 0.6,
            "correct": 0,
            "stake_units": 1.5,
        },
        {
            **base,
            "game_id": "g3",
            "game_date": "2025-06-01",
            "predicted_side": "HOME",
            "predicted_side_probability": 0.7,
            "correct": 1,
            "stake_units": 2.0,
        },
        {
            **base,
            "game_id": "g4",
            "game_date": "2025-06-02",
            "predicted_side": "AWAY",
            "predicted_side_probability": 1.0,
            "correct": 1,
            "stake_units": 0.5,
        },
    ]


def _read_segments(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _fixture_payload(tmp_path: Path) -> tuple[Path, dict, list[dict[str, str]]]:
    fixture = tmp_path / "decisions.csv"
    output_json = tmp_path / "summary.json"
    output_csv = tmp_path / "segments.csv"
    _write_decisions(fixture, _rows())
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--decisions-csv",
            str(fixture),
            "--output-json",
            str(output_json),
            "--output-csv",
            str(output_csv),
            "--thresholds",
            "0.5,0.6,0.7",
            "--generated-at-utc",
            FIXED_TIME,
            "--quiet",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr
    return output_json, json.loads(output_json.read_text(encoding="utf-8")), _read_segments(output_csv)


def test_cli_and_module_outputs_are_deterministic_with_fixed_generated_at(tmp_path):
    fixture = tmp_path / "decisions.csv"
    _write_decisions(fixture, _rows())
    dataset = learning.load_paper_decisions(fixture)
    payload, segments = learning.build_output_payload(
        dataset,
        thresholds=(0.5, 0.6, 0.7),
        generated_at_utc=FIXED_TIME,
    )
    assert payload["generated_at_utc"] == FIXED_TIME
    assert len(segments) == payload["segments_count"]

    paths = []
    for prefix in ("a", "b"):
        output_json = tmp_path / f"{prefix}.json"
        output_csv = tmp_path / f"{prefix}.csv"
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--decisions-csv",
                str(fixture),
                "--output-json",
                str(output_json),
                "--output-csv",
                str(output_csv),
                "--thresholds",
                "0.5,0.6,0.7",
                "--generated-at-utc",
                FIXED_TIME,
                "--quiet",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        assert result.returncode == 0, result.stderr
        paths.append((output_json, output_csv))
    assert paths[0][0].read_bytes() == paths[1][0].read_bytes()
    assert paths[0][1].read_bytes() == paths[1][1].read_bytes()


def test_segment_csv_columns_and_required_segment_types(tmp_path):
    _, payload, segments = _fixture_payload(tmp_path)
    with (tmp_path / "segments.csv").open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames == learning.SEGMENT_FIELDNAMES
    assert payload["segment_types"] == [
        "GLOBAL",
        "THRESHOLD",
        "CONFIDENCE_BUCKET",
        "PREDICTED_SIDE",
        "GAME_MONTH",
    ]
    assert {row["segment_type"] for row in segments} == set(payload["segment_types"])


def test_threshold_rows_are_inclusive_at_min_confidence(tmp_path):
    _, _, segments = _fixture_payload(tmp_path)
    threshold_rows = {
        row["min_confidence"]: row for row in segments if row["segment_type"] == "THRESHOLD"
    }
    assert threshold_rows["0.5"]["decisions_count"] == "4"
    assert threshold_rows["0.6"]["decisions_count"] == "3"
    assert threshold_rows["0.7"]["decisions_count"] == "2"


def test_confidence_bucket_boundaries_include_one_in_final_bucket(tmp_path):
    _, _, segments = _fixture_payload(tmp_path)
    buckets = {row["segment_key"]: row for row in segments if row["segment_type"] == "CONFIDENCE_BUCKET"}
    assert buckets["0.50_0.60"]["decisions_count"] == "1"
    assert buckets["0.60_0.70"]["decisions_count"] == "1"
    assert buckets["0.70_0.80"]["decisions_count"] == "1"
    assert buckets["0.80_0.90"]["decisions_count"] == "0"
    assert buckets["0.90_1.00"]["decisions_count"] == "1"


def test_metrics_side_counts_and_stake_units_are_correct(tmp_path):
    _, payload, segments = _fixture_payload(tmp_path)
    global_row = next(row for row in segments if row["segment_type"] == "GLOBAL")
    assert global_row["decisions_count"] == "4"
    assert float(global_row["hit_rate"]) == pytest.approx(0.75)
    assert float(global_row["average_confidence"]) == pytest.approx(0.7)
    assert float(global_row["calibration_gap"]) == pytest.approx(-0.05)
    assert global_row["home_count"] == "2"
    assert global_row["away_count"] == "2"
    assert float(global_row["stake_units_total"]) == pytest.approx(5.0)
    assert payload["global_metrics"]["decisions_count"] == 4
    assert payload["global_metrics"]["stake_units_total"] == pytest.approx(5.0)


def test_empty_input_and_empty_segments_return_null_metrics(tmp_path):
    fixture = tmp_path / "empty.csv"
    _write_decisions(fixture, [])
    dataset = learning.load_paper_decisions(fixture)
    payload, segments = learning.build_output_payload(
        dataset,
        thresholds=(0.8,),
        generated_at_utc=FIXED_TIME,
    )
    assert payload["global_metrics"]["decisions_count"] == 0
    assert payload["global_metrics"]["hit_rate"] is None
    assert payload["global_metrics"]["average_confidence"] is None
    assert payload["global_metrics"]["calibration_gap"] is None
    assert all(row["roi"] is None for row in segments)
    assert next(row for row in segments if row["segment_type"] == "THRESHOLD")["hit_rate"] is None


def test_summary_has_result_only_roi_status_and_limitation_labels(tmp_path):
    _, payload, segments = _fixture_payload(tmp_path)
    assert payload["roi"] is None
    assert payload["roi_status"] == "ROI_UNAVAILABLE"
    assert payload["roi_unavailable_reason"] == ROI_REASON
    assert payload["generates_new_predictions"] is False
    assert payload["interpretation"] == "IN_SAMPLE_DESCRIPTIVE_ONLY"
    for label in learning.LIMITATION_LABELS:
        assert label in payload["limitation_labels"]
    assert all(row["roi"] == "" for row in segments)
    assert {row["roi_status"] for row in segments} == {"ROI_UNAVAILABLE"}


def test_output_tree_and_csv_headers_avoid_forbidden_fields(tmp_path):
    _, payload, _ = _fixture_payload(tmp_path)
    with (tmp_path / "segments.csv").open(newline="", encoding="utf-8") as handle:
        header = handle.readline().casefold()

    def keys_from(value):
        if isinstance(value, dict):
            for key, child in value.items():
                yield str(key).casefold()
                yield from keys_from(child)
        elif isinstance(value, list):
            for child in value:
                yield from keys_from(child)

    output_keys = set(keys_from(payload))
    for forbidden in (
        "ev",
        "kelly",
        "best_strategy",
        "best_threshold",
        "recommended_bet",
        "pnl",
        "profit",
        "bankroll",
    ):
        assert forbidden not in output_keys
        assert forbidden not in header


def test_segment_ordering_is_structural_not_performance_ranked(tmp_path):
    _, _, segments = _fixture_payload(tmp_path)
    assert [row["segment_type"] for row in segments[:4]] == [
        "GLOBAL",
        "THRESHOLD",
        "THRESHOLD",
        "THRESHOLD",
    ]
    assert [row["segment_key"] for row in segments if row["segment_type"] == "THRESHOLD"] == [
        ">=0.50",
        ">=0.60",
        ">=0.70",
    ]
    assert [row["segment_key"] for row in segments if row["segment_type"] == "PREDICTED_SIDE"] == [
        "HOME",
        "AWAY",
    ]
    assert [row["segment_key"] for row in segments if row["segment_type"] == "GAME_MONTH"] == [
        "2025-05",
        "2025-06",
    ]
    hit_rates = [row["hit_rate"] for row in segments[:4]]
    assert hit_rates != sorted(hit_rates, reverse=True)


def test_demo_outputs_are_byte_identical_for_fixed_generated_at(tmp_path):
    j1, c1 = tmp_path / "a.json", tmp_path / "a.csv"
    j2, c2 = tmp_path / "b.json", tmp_path / "b.csv"
    for output_json, output_csv in ((j1, c1), (j2, c2)):
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--decisions-csv",
                str(ROOT / "report" / "p237a_paper_strategy_decisions.csv"),
                "--output-json",
                str(output_json),
                "--output-csv",
                str(output_csv),
                "--generated-at-utc",
                FIXED_TIME,
                "--quiet",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        assert result.returncode == 0, result.stderr
    assert _digest(j1) == _digest(j2)
    assert _digest(c1) == _digest(c2)
