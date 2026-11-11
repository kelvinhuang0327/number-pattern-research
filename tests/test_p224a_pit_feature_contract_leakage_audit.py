from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "build_pit_feature_contract_leakage_audit.py"


def _load_script_module():
    spec = importlib.util.spec_from_file_location("p224a_script", SCRIPT_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _write_fixture_artifacts(tmp_path: Path, script) -> dict[str, Path]:
    files = {
        "SOURCE_P223_JSON": tmp_path / "p223.json",
        "SOURCE_P223_HTML": tmp_path / "p223.html",
        "SOURCE_P218_CSV": tmp_path / "p218.csv",
        "SOURCE_P218_JSON": tmp_path / "p218.json",
        "SOURCE_P218_MD": tmp_path / "p218.md",
        "SOURCE_P221_CSV": tmp_path / "p221.csv",
        "SOURCE_P221_JSON": tmp_path / "p221.json",
        "SOURCE_P221_MD": tmp_path / "p221.md",
        "OUT_JSON": tmp_path / "p224.json",
        "OUT_MD": tmp_path / "p224.md",
    }

    p218_rows = [
        {
            "source_row_id": 1,
            "game_date": "2024-04-01",
            "game_pk": 1,
            "home_team": "SEA",
            "away_team": "CLE",
            "inning": 1,
            "inning_topbot": "Top",
            "pitcher": "Pitcher A",
            "batter": "Batter 1",
            "pitch_type": "FF",
            "event_category": "strike_like",
            "is_in_play": "False",
            "is_strike_like": "True",
            "is_ball_like": "False",
            "release_speed": 94.2,
            "release_speed_bucket": "90_to_94_9",
            "zone": 5,
            "zone_bucket": "in_zone",
        },
        {
            "source_row_id": 2,
            "game_date": "2024-04-01",
            "game_pk": 1,
            "home_team": "SEA",
            "away_team": "CLE",
            "inning": 1,
            "inning_topbot": "Top",
            "pitcher": "Pitcher A",
            "batter": "Batter 2",
            "pitch_type": "CH",
            "event_category": "ball_like",
            "is_in_play": "False",
            "is_strike_like": "False",
            "is_ball_like": "True",
            "release_speed": 87.1,
            "release_speed_bucket": "85_to_89_9",
            "zone": 13,
            "zone_bucket": "out_of_zone",
        },
        {
            "source_row_id": 3,
            "game_date": "2024-04-02",
            "game_pk": 2,
            "home_team": "SEA",
            "away_team": "CLE",
            "inning": 1,
            "inning_topbot": "Top",
            "pitcher": "Pitcher B",
            "batter": "Batter 3",
            "pitch_type": "FF",
            "event_category": "strike_like",
            "is_in_play": "False",
            "is_strike_like": "True",
            "is_ball_like": "False",
            "release_speed": 95.2,
            "release_speed_bucket": "95_plus",
            "zone": 7,
            "zone_bucket": "in_zone",
        },
        {
            "source_row_id": 4,
            "game_date": "2024-04-02",
            "game_pk": 2,
            "home_team": "SEA",
            "away_team": "CLE",
            "inning": 1,
            "inning_topbot": "Top",
            "pitcher": "Pitcher B",
            "batter": "Batter 4",
            "pitch_type": "SI",
            "event_category": "in_play_out",
            "is_in_play": "True",
            "is_strike_like": "False",
            "is_ball_like": "False",
            "release_speed": 93.4,
            "release_speed_bucket": "90_to_94_9",
            "zone": 3,
            "zone_bucket": "in_zone",
        },
        {
            "source_row_id": 5,
            "game_date": "2024-04-03",
            "game_pk": 3,
            "home_team": "SEA",
            "away_team": "CLE",
            "inning": 1,
            "inning_topbot": "Top",
            "pitcher": "Pitcher C",
            "batter": "Batter 5",
            "pitch_type": "FF",
            "event_category": "strike_like",
            "is_in_play": "False",
            "is_strike_like": "True",
            "is_ball_like": "False",
            "release_speed": 96.0,
            "release_speed_bucket": "95_plus",
            "zone": 5,
            "zone_bucket": "in_zone",
        },
        {
            "source_row_id": 6,
            "game_date": "2024-04-03",
            "game_pk": 3,
            "home_team": "SEA",
            "away_team": "CLE",
            "inning": 1,
            "inning_topbot": "Top",
            "pitcher": "Pitcher C",
            "batter": "Batter 6",
            "pitch_type": "CU",
            "event_category": "ball_like",
            "is_in_play": "False",
            "is_strike_like": "False",
            "is_ball_like": "True",
            "release_speed": 80.4,
            "release_speed_bucket": "lt_85",
            "zone": 12,
            "zone_bucket": "out_of_zone",
        },
    ]

    with files["SOURCE_P218_CSV"].open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=script.P218_REQUIRED_COLUMNS)
        writer.writeheader()
        for row in p218_rows:
            writer.writerow(row)

    files["SOURCE_P218_JSON"].write_text(
        json.dumps(
            {
                "task": "P218-A Historical Sample Feature Table Prototype",
                "status": "PASS_P218",
                "disclaimer": "Historical sample feature table prototype only. Not live predictions, not betting advice.",
                "historical_only_disclaimer": "Historical sample feature table prototype only. Not live predictions, not betting advice.",
                "row_count": len(p218_rows),
                "column_count": len(script.P218_REQUIRED_COLUMNS),
                "feature_columns": script.P218_REQUIRED_COLUMNS,
                "derived_feature_definitions": {
                    "source_row_id": "1-based lineage back to the original source row",
                    "game_date": "Historical game date copied from the sample artifact",
                    "game_pk": "Historical game identifier copied from the sample artifact",
                    "home_team": "Home team code copied from the sample artifact",
                    "away_team": "Away team code copied from the sample artifact",
                    "inning": "Inning number copied from the sample artifact",
                    "inning_topbot": "Half-inning label copied from the sample artifact",
                    "pitcher": "Pitcher identifier copied from the sample artifact",
                    "batter": "Batter identifier copied from the sample artifact",
                    "pitch_type": "Pitch type code copied from the sample artifact",
                    "event_category": "Heuristic categorical label derived from the sample artifact",
                    "is_in_play": "Boolean flag derived from realized in-play outcomes",
                    "is_strike_like": "Boolean flag derived from realized strike-like outcomes",
                    "is_ball_like": "Boolean flag derived from realized ball-like outcomes",
                    "release_speed": "Numeric release speed copied from the sample artifact",
                    "release_speed_bucket": "Velocity bucket derived from release speed",
                    "zone": "Zone value copied from the sample artifact",
                    "zone_bucket": "Zone bucket derived from zone",
                },
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    files["SOURCE_P218_MD"].write_text(
        "# P218\n\nHistorical sample feature table prototype only. Not live predictions, not betting advice.\n",
        encoding="utf-8",
    )

    committed_rows = [
        {
            "split_id": 1,
            "train_date_range": "2024-04-01 to 2024-04-01",
            "eval_date": "2024-04-02",
            "source_row_id": 3,
            "pitch_type": "FF",
            "actual_event_category": "strike_like",
            "baseline_a_prediction": "ball_like",
            "baseline_a_correct": False,
            "baseline_b_prediction": "strike_like",
            "baseline_b_correct": True,
            "baseline_b_prediction_source": "pitch_type_majority",
        },
        {
            "split_id": 1,
            "train_date_range": "2024-04-01 to 2024-04-01",
            "eval_date": "2024-04-02",
            "source_row_id": 4,
            "pitch_type": "SI",
            "actual_event_category": "in_play_out",
            "baseline_a_prediction": "ball_like",
            "baseline_a_correct": False,
            "baseline_b_prediction": "ball_like",
            "baseline_b_correct": False,
            "baseline_b_prediction_source": "global_fallback_missing_pitch_type",
        },
        {
            "split_id": 2,
            "train_date_range": "2024-04-01 to 2024-04-02",
            "eval_date": "2024-04-03",
            "source_row_id": 5,
            "pitch_type": "FF",
            "actual_event_category": "strike_like",
            "baseline_a_prediction": "strike_like",
            "baseline_a_correct": True,
            "baseline_b_prediction": "strike_like",
            "baseline_b_correct": True,
            "baseline_b_prediction_source": "pitch_type_majority",
        },
        {
            "split_id": 2,
            "train_date_range": "2024-04-01 to 2024-04-02",
            "eval_date": "2024-04-03",
            "source_row_id": 6,
            "pitch_type": "CU",
            "actual_event_category": "ball_like",
            "baseline_a_prediction": "strike_like",
            "baseline_a_correct": False,
            "baseline_b_prediction": "strike_like",
            "baseline_b_correct": False,
            "baseline_b_prediction_source": "global_fallback_missing_pitch_type",
        },
    ]

    with files["SOURCE_P221_CSV"].open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=script.P221_REQUIRED_COLUMNS)
        writer.writeheader()
        for row in committed_rows:
            writer.writerow(row)

    files["SOURCE_P221_JSON"].write_text(
        json.dumps(
            {
                "task": "P221-A Historical Time-Split Baseline Evaluation Prototype",
                "status": "PASS_P221",
                "disclaimer": "Historical time-split baseline evaluation prototype only. Not live predictions, not betting advice.",
                "historical_only_disclaimer": "Historical time-split baseline evaluation prototype only. Not live predictions, not betting advice.",
                "row_count": 4,
                "overall_holdout_metrics": {
                    script.BASELINE_A_KEY: {
                        "row_count": 4,
                        "correct_count": 1,
                        "accuracy": 0.25,
                        "coverage_rows": 4,
                        "coverage_fraction": 1.0,
                    },
                    script.BASELINE_B_KEY: {
                        "row_count": 4,
                        "correct_count": 2,
                        "accuracy": 0.5,
                        "coverage_rows": 4,
                        "coverage_fraction": 1.0,
                    },
                },
                "per_split_metrics": [
                    {
                        "split_id": 1,
                        "eval_date": "2024-04-02",
                        script.BASELINE_A_KEY: {
                            "row_count": 2,
                            "correct_count": 0,
                            "accuracy": 0.0,
                            "coverage_rows": 2,
                            "coverage_fraction": 1.0,
                        },
                        script.BASELINE_B_KEY: {
                            "row_count": 2,
                            "correct_count": 1,
                            "accuracy": 0.5,
                            "coverage_rows": 2,
                            "coverage_fraction": 1.0,
                        },
                    },
                    {
                        "split_id": 2,
                        "eval_date": "2024-04-03",
                        script.BASELINE_A_KEY: {
                            "row_count": 2,
                            "correct_count": 1,
                            "accuracy": 0.5,
                            "coverage_rows": 2,
                            "coverage_fraction": 1.0,
                        },
                        script.BASELINE_B_KEY: {
                            "row_count": 2,
                            "correct_count": 1,
                            "accuracy": 0.5,
                            "coverage_rows": 2,
                            "coverage_fraction": 1.0,
                        },
                    },
                ],
                "time_split_definitions": [
                    {"split_id": 1, "eval_date": "2024-04-02"},
                    {"split_id": 2, "eval_date": "2024-04-03"},
                ],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    files["SOURCE_P221_MD"].write_text(
        "# P221\n\nHistorical time-split baseline evaluation prototype only. Not live predictions, not betting advice.\n",
        encoding="utf-8",
    )

    files["SOURCE_P223_HTML"].write_text("<html><body>P223</body></html>\n", encoding="utf-8")
    p223_source_hashes = {
        "p218.csv": script._sha256(files["SOURCE_P218_CSV"]),
        "p218.json": script._sha256(files["SOURCE_P218_JSON"]),
        "p218.md": script._sha256(files["SOURCE_P218_MD"]),
        "p221.csv": script._sha256(files["SOURCE_P221_CSV"]),
        "p221.json": script._sha256(files["SOURCE_P221_JSON"]),
        "p221.md": script._sha256(files["SOURCE_P221_MD"]),
    }
    files["SOURCE_P223_JSON"].write_text(
        json.dumps(
            {
                "task": "P223-A Historical Evaluation Evidence Index",
                "status": "PASS_P223",
                "source_hash_validation": "PASS_ALL_FIXED_P216_P222_SOURCE_HASHES_MATCH",
                "source_hashes": p223_source_hashes,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return files


def _patch_paths(monkeypatch, script, files: dict[str, Path]) -> None:
    monkeypatch.setattr(script, "ROOT", files["SOURCE_P223_JSON"].parent)
    monkeypatch.setattr(script, "REPORT_DIR", files["SOURCE_P223_JSON"].parent)
    for name, path in files.items():
        monkeypatch.setattr(script, name, path)
    monkeypatch.setattr(
        script,
        "SOURCE_ARTIFACTS",
        [
            files["SOURCE_P223_JSON"],
            files["SOURCE_P223_HTML"],
            files["SOURCE_P218_CSV"],
            files["SOURCE_P218_JSON"],
            files["SOURCE_P218_MD"],
            files["SOURCE_P221_CSV"],
            files["SOURCE_P221_JSON"],
            files["SOURCE_P221_MD"],
        ],
    )
    monkeypatch.setattr(
        script,
        "P223_HASH_REQUIRED_ARTIFACTS",
        [
            files["SOURCE_P218_CSV"],
            files["SOURCE_P218_JSON"],
            files["SOURCE_P218_MD"],
            files["SOURCE_P221_CSV"],
            files["SOURCE_P221_JSON"],
            files["SOURCE_P221_MD"],
        ],
    )


def test_build_payload_classifies_all_columns_and_detects_no_leakage(tmp_path, monkeypatch):
    script = _load_script_module()
    files = _write_fixture_artifacts(tmp_path, script)
    _patch_paths(monkeypatch, script, files)

    payload = script.build_payload()

    assert payload["disclaimer"] == script.DISCLAIMER
    assert payload["source_hash_verification"]["status"] == "PASS_P218A_P221A_SOURCE_HASHES_MATCH_P223_INDEX"
    assert len(payload["pit_feature_contract"]) == len(script.P218_REQUIRED_COLUMNS)
    assert payload["pit_feature_contract"][0]["column_name"] == "source_row_id"
    assert payload["pit_feature_contract"][9]["pit_category"] == "in_play_measured"

    leakage = payload["leakage_audit_results"]
    assert leakage["committed_reference_metrics"] == {
        "split_count": 2,
        "evaluated_rows": 4,
        "baseline_a_overall_accuracy": 0.25,
        "baseline_b_overall_accuracy": 0.5,
    }
    assert leakage["recomputed_reference_metrics"] == leakage["committed_reference_metrics"]
    assert leakage["comparison_summary"]["metrics_match"] is True
    assert leakage["comparison_summary"]["predictions_match"] is True
    assert leakage["comparison_summary"]["row_prediction_mismatch_count"] == 0
    assert leakage["leakage_conclusion"] == "NO_DERIVATION_WINDOW_LEAKAGE_DETECTED"
    assert all(row["accuracy_delta"] == 0.0 for row in leakage["metrics_delta_table"])
    assert all(row["all_prediction_fields_match"] for row in leakage["row_comparison_table"])
    assert "Historical PIT contract and leakage audit only. Not live predictions, not betting advice." in script.render_markdown(payload)


def test_main_writes_deterministic_outputs(tmp_path, monkeypatch, capsys):
    script = _load_script_module()
    files = _write_fixture_artifacts(tmp_path, script)
    _patch_paths(monkeypatch, script, files)

    script.main()
    first_json = files["OUT_JSON"].read_text(encoding="utf-8")
    first_md = files["OUT_MD"].read_text(encoding="utf-8")
    captured = capsys.readouterr().out

    script.main()
    second_json = files["OUT_JSON"].read_text(encoding="utf-8")
    second_md = files["OUT_MD"].read_text(encoding="utf-8")

    assert first_json == second_json
    assert first_md == second_md
    assert script.SUCCESS_BANNER in captured
