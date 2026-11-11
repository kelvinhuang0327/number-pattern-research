from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "build_historical_evaluation_evidence_index.py"


def _load_script_module():
    spec = importlib.util.spec_from_file_location("p223a_script", SCRIPT_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _write_fixture_artifacts(tmp_path: Path, script) -> dict[str, Path]:
    files = {
        "SOURCE_P216_CSV": tmp_path / "p216.csv",
        "SOURCE_P216_JSON": tmp_path / "p216.json",
        "SOURCE_P216_MD": tmp_path / "p216.md",
        "SOURCE_P217_HTML": tmp_path / "p217.html",
        "SOURCE_P217_JSON": tmp_path / "p217.json",
        "SOURCE_P218_CSV": tmp_path / "p218.csv",
        "SOURCE_P218_JSON": tmp_path / "p218.json",
        "SOURCE_P218_MD": tmp_path / "p218.md",
        "SOURCE_P219_CSV": tmp_path / "p219.csv",
        "SOURCE_P219_JSON": tmp_path / "p219.json",
        "SOURCE_P219_MD": tmp_path / "p219.md",
        "SOURCE_P220_HTML": tmp_path / "p220.html",
        "SOURCE_P220_JSON": tmp_path / "p220.json",
        "SOURCE_P221_CSV": tmp_path / "p221.csv",
        "SOURCE_P221_JSON": tmp_path / "p221.json",
        "SOURCE_P221_MD": tmp_path / "p221.md",
        "SOURCE_P222_HTML": tmp_path / "p222.html",
        "SOURCE_P222_JSON": tmp_path / "p222.json",
        "OUT_HTML": tmp_path / "p223.html",
        "OUT_JSON": tmp_path / "p223.json",
    }

    files["SOURCE_P216_CSV"].write_text(
        "\n".join(
            [
                "game_date,game_pk,home_team,away_team",
                "2024-04-01,1,SEA,CLE",
                "2024-04-02,2,SEA,CLE",
                "2024-04-03,3,SEA,CLE",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    files["SOURCE_P216_JSON"].write_text(
        json.dumps(
            {
                "task": "P216-A pybaseball Multi-Date Historical Sample Pack",
                "status": "PASS_P216",
                "disclaimer": "Historical pybaseball multi-date sample pack only. Not live predictions, not betting advice.",
                "row_count": 3,
                "column_count": 4,
                "observed_dates": ["2024-04-01", "2024-04-02", "2024-04-03"],
                "sample_size_limits": {"per_date_row_limit": 1, "total_row_limit": 3},
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    files["SOURCE_P216_MD"].write_text(
        "# P216\n\nHistorical pybaseball multi-date sample pack only. Not live predictions, not betting advice.\n",
        encoding="utf-8",
    )
    files["SOURCE_P217_HTML"].write_text("<html><body>P217</body></html>\n", encoding="utf-8")
    files["SOURCE_P217_JSON"].write_text(
        json.dumps(
            {
                "task": "P217-A pybaseball Multi-Date Sample Quality Dashboard",
                "status": "PASS_P217",
                "disclaimer": "Historical pybaseball multi-date quality dashboard only. Not live predictions, not betting advice.",
                "row_count": 3,
                "column_count": 4,
                "per_date_row_counts": {"2024-04-01": 1, "2024-04-02": 1, "2024-04-03": 1},
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    files["SOURCE_P218_CSV"].write_text(
        "\n".join(
            [
                "source_row_id,game_date,pitch_type,event_category,feature_x",
                "1,2024-04-01,FF,strike_like,1",
                "2,2024-04-02,CH,ball_like,2",
                "3,2024-04-03,SI,in_play_out,3",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    files["SOURCE_P218_JSON"].write_text(
        json.dumps(
            {
                "task": "P218-A Historical Sample Feature Table Prototype",
                "status": "PASS_P218",
                "disclaimer": "Historical sample feature table prototype only. Not live predictions, not betting advice.",
                "row_count": 3,
                "column_count": 5,
                "feature_columns": [
                    "source_row_id",
                    "game_date",
                    "pitch_type",
                    "event_category",
                    "feature_x",
                ],
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
    files["SOURCE_P219_CSV"].write_text(
        "\n".join(
            [
                "source_row_id,actual_event_category,baseline_a_prediction,baseline_b_prediction",
                "1,strike_like,strike_like,strike_like",
                "2,ball_like,strike_like,ball_like",
                "3,in_play_out,strike_like,strike_like",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    files["SOURCE_P219_JSON"].write_text(
        json.dumps(
            {
                "task": "P219-A Historical Feature Baseline Evaluation Prototype",
                "status": "PASS_P219",
                "disclaimer": "Historical feature baseline evaluation prototype only. Not live predictions, not betting advice.",
                "row_count": 3,
                "column_count": 4,
                "metric_summary": {
                    script.BASELINE_A_KEY: {
                        "row_count": 3,
                        "correct_count": 1,
                        "accuracy": 0.333333,
                        "coverage_rows": 3,
                        "coverage_fraction": 1.0,
                    },
                    script.BASELINE_B_KEY: {
                        "row_count": 3,
                        "correct_count": 2,
                        "accuracy": 0.666667,
                        "coverage_rows": 2,
                        "coverage_fraction": 0.666667,
                    },
                },
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    files["SOURCE_P219_MD"].write_text(
        "# P219\n\nHistorical feature baseline evaluation prototype only. Not live predictions, not betting advice.\n",
        encoding="utf-8",
    )
    files["SOURCE_P220_HTML"].write_text("<html><body>P220</body></html>\n", encoding="utf-8")
    files["SOURCE_P220_JSON"].write_text(
        json.dumps(
            {
                "task": "P220-A Historical Baseline Error Analysis Dashboard",
                "status": "PASS_P220",
                "disclaimer": "Historical baseline error analysis dashboard only. Not live predictions, not betting advice.",
                "metrics": {
                    script.BASELINE_A_KEY: {"accuracy": 0.333333},
                    script.BASELINE_B_KEY: {"accuracy": 0.666667},
                },
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    files["SOURCE_P221_CSV"].write_text(
        "\n".join(
            [
                "split_id,eval_date,actual_event_category,baseline_a_prediction,baseline_b_prediction",
                "1,2024-04-02,ball_like,strike_like,strike_like",
                "2,2024-04-03,strike_like,strike_like,strike_like",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    files["SOURCE_P221_JSON"].write_text(
        json.dumps(
            {
                "task": "P221-A Historical Time-Split Baseline Evaluation Prototype",
                "status": "PASS_P221",
                "disclaimer": "Historical time-split baseline evaluation prototype only. Not live predictions, not betting advice.",
                "row_count": 2,
                "column_count": 5,
                "overall_holdout_metrics": {
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
                    "baseline_b_coverage": {
                        "direct_pitch_type_majority": {"rows": 1, "fraction": 0.5, "correct_rows": 1, "accuracy": 1.0},
                        "global_fallback_due_to_tie": {"rows": 0, "fraction": 0.0, "correct_rows": 0, "accuracy": 0.0},
                        "global_fallback_missing_pitch_type": {"rows": 1, "fraction": 0.5, "correct_rows": 0, "accuracy": 0.0},
                        "all_global_fallback": {"rows": 1, "fraction": 0.5, "correct_rows": 0, "accuracy": 0.0},
                    },
                    "comparison": {"accuracy_delta_b_minus_a": 0.0, "correct_row_delta_b_minus_a": 0},
                },
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
    files["SOURCE_P222_HTML"].write_text("<html><body>P222</body></html>\n", encoding="utf-8")
    files["SOURCE_P222_JSON"].write_text(
        json.dumps(
            {
                "task": "P222-A Historical Time-Split Error Analysis Dashboard",
                "status": "PASS_P222",
                "disclaimer": "Historical time-split error analysis dashboard only. Not live predictions, not betting advice.",
                "overall_metrics": {
                    "evaluated_rows": 2,
                    "split_count": 2,
                    "comparison": {"accuracy_delta_b_minus_a": 0.0, "correct_row_delta_b_minus_a": 0},
                    "vs_p220_in_sample": {
                        script.BASELINE_A_KEY: {
                            "p220_accuracy": 0.333333,
                            "p222_time_split_accuracy": 0.5,
                            "accuracy_delta_time_split_minus_p220": 0.166667,
                        },
                        script.BASELINE_B_KEY: {
                            "p220_accuracy": 0.666667,
                            "p222_time_split_accuracy": 0.5,
                            "accuracy_delta_time_split_minus_p220": -0.166667,
                        },
                    },
                },
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    for name, path in files.items():
        setattr(script, name, path)

    script.ROOT = tmp_path
    script.REPORT_DIR = tmp_path
    script.SOURCE_REQUIRED_HASHES = {
        str(path.relative_to(tmp_path)): script._sha256(path)
        for name, path in files.items()
        if name.startswith("SOURCE_")
    }
    return files


def test_build_payload_creates_machine_readable_evidence_index(tmp_path):
    script = _load_script_module()
    _write_fixture_artifacts(tmp_path, script)

    payload = script.build_payload()

    assert payload["task"] == script.TASK_NAME
    assert payload["status"] == script.STATUS
    assert payload["disclaimer"] == script.DISCLAIMER
    assert len(payload["source_artifacts"]) == 18
    assert len(payload["source_hashes"]) == 18
    assert payload["source_hash_validation"] == "PASS_ALL_FIXED_P216_P222_SOURCE_HASHES_MATCH"
    assert [entry["artifact_id"] for entry in payload["artifact_chain"]] == [
        "P216-A",
        "P217-A",
        "P218-A",
        "P219-A",
        "P220-A",
        "P221-A",
        "P222-A",
    ]
    assert payload["metrics"]["p216_sample"]["row_count"] == 3
    assert payload["metrics"]["p218_feature_table"]["column_count"] == 5
    assert payload["metrics"]["p219_in_sample"]["comparison"] == {
        "accuracy_delta_b_minus_a": 0.333334,
        "correct_row_delta_b_minus_a": 1,
    }
    assert payload["metrics"]["p221_time_split"]["split_count"] == 2
    assert payload["metrics"]["p222_vs_p220_dashboard"][script.BASELINE_B_KEY]["accuracy_delta_time_split_minus_p220"] == -0.166667
    assert "SHA256" in payload["current_capabilities"][0]
    assert "No future predictive ability is established." in payload["not_claimed"]
    html_output = script.render_html(payload)
    assert "Current Capability Statement" in html_output
    assert script.DISCLAIMER in html_output


def test_main_writes_deterministic_outputs(tmp_path, capsys):
    script = _load_script_module()
    files = _write_fixture_artifacts(tmp_path, script)

    first_rc = script.main()
    captured = capsys.readouterr()
    first_html = files["OUT_HTML"].read_text(encoding="utf-8")
    first_json = files["OUT_JSON"].read_text(encoding="utf-8")

    second_rc = script.main()
    second_captured = capsys.readouterr()
    second_html = files["OUT_HTML"].read_text(encoding="utf-8")
    second_json = files["OUT_JSON"].read_text(encoding="utf-8")

    assert first_rc == 0
    assert second_rc == 0
    assert "P223-A HISTORICAL EVALUATION EVIDENCE INDEX PASS" in captured.out
    assert "P223-A HISTORICAL EVALUATION EVIDENCE INDEX PASS" in second_captured.out
    assert first_html == second_html
    assert first_json == second_json
