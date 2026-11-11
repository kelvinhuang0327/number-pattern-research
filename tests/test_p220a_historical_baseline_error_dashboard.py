from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "build_historical_baseline_error_dashboard.py"


def _load_script_module():
    spec = importlib.util.spec_from_file_location("p220a_script", SCRIPT_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_build_payload_computes_historical_dashboard_from_p219_artifacts(tmp_path, monkeypatch):
    script = _load_script_module()
    source_csv = tmp_path / "p219.csv"
    source_json = tmp_path / "p219.json"
    source_md = tmp_path / "p219.md"

    source_csv.write_text(
        "\n".join(
            [
                "source_row_id,game_date,game_pk,pitcher,pitch_type,actual_event_category,baseline_a_global_prediction,baseline_a_correct,baseline_b_pitch_type_prediction,baseline_b_correct,baseline_b_prediction_source",
                "1,2024-04-01,1,Pitcher A,FF,strike_like,strike_like,True,strike_like,True,pitch_type_majority",
                "2,2024-04-01,1,Pitcher A,FF,ball_like,strike_like,False,strike_like,False,pitch_type_majority",
                "3,2024-04-01,1,Pitcher A,CH,in_play_out,strike_like,False,strike_like,False,global_fallback_due_to_tie",
                "4,2024-04-01,1,Pitcher A,SI,in_play_hit,strike_like,False,in_play_hit,True,pitch_type_majority",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    source_json.write_text(
        json.dumps(
            {
                "task": "P219-A Historical Feature Baseline Evaluation Prototype",
                "status": "PASS_P218A_ARTIFACT_ONLY_HISTORICAL_FEATURE_BASELINE_EVALUATION_PROTOTYPE",
                "disclaimer": "Historical feature baseline evaluation prototype only. Not live predictions, not betting advice.",
                "historical_only_disclaimer": "Historical feature baseline evaluation prototype only. Not live predictions, not betting advice.",
                "row_count": 4,
                "column_count": 11,
                "output_columns": [
                    "source_row_id",
                    "game_date",
                    "game_pk",
                    "pitcher",
                    "pitch_type",
                    "actual_event_category",
                    "baseline_a_global_prediction",
                    "baseline_a_correct",
                    "baseline_b_pitch_type_prediction",
                    "baseline_b_correct",
                    "baseline_b_prediction_source",
                ],
                "target_definition": {
                    "name": "event_category",
                    "description": "Historical categorical label copied from the fixed P218 feature table event_category column.",
                    "class_support": [
                        {"value": "ball_like", "count": 1, "fraction": 0.25},
                        {"value": "in_play_hit", "count": 1, "fraction": 0.25},
                        {"value": "in_play_out", "count": 1, "fraction": 0.25},
                        {"value": "strike_like", "count": 1, "fraction": 0.25},
                    ],
                    "label_order": ["ball_like", "in_play_hit", "in_play_out", "strike_like"],
                },
                "metric_summary": {
                    "baseline_a_global_majority": {
                        "accuracy": 0.25,
                        "confusion_matrix": {
                            "ball_like": {"ball_like": 0, "in_play_hit": 0, "in_play_out": 0, "strike_like": 1},
                            "in_play_hit": {"ball_like": 0, "in_play_hit": 0, "in_play_out": 0, "strike_like": 1},
                            "in_play_out": {"ball_like": 0, "in_play_hit": 0, "in_play_out": 0, "strike_like": 1},
                            "strike_like": {"ball_like": 0, "in_play_hit": 0, "in_play_out": 0, "strike_like": 1},
                        },
                        "correct_count": 1,
                        "coverage_fraction": 1.0,
                        "coverage_rows": 4,
                        "predicted_class_distribution": [{"value": "strike_like", "count": 4, "fraction": 1.0}],
                        "row_count": 4,
                    },
                    "baseline_b_pitch_type_majority_with_global_fallback": {
                        "accuracy": 0.5,
                        "confusion_matrix": {
                            "ball_like": {"ball_like": 0, "in_play_hit": 0, "in_play_out": 0, "strike_like": 1},
                            "in_play_hit": {"ball_like": 0, "in_play_hit": 1, "in_play_out": 0, "strike_like": 0},
                            "in_play_out": {"ball_like": 0, "in_play_hit": 0, "in_play_out": 0, "strike_like": 1},
                            "strike_like": {"ball_like": 0, "in_play_hit": 0, "in_play_out": 0, "strike_like": 1},
                        },
                        "correct_count": 2,
                        "coverage_fraction": 0.75,
                        "coverage_rows": 3,
                        "predicted_class_distribution": [
                            {"value": "strike_like", "count": 3, "fraction": 0.75},
                            {"value": "in_play_hit", "count": 1, "fraction": 0.25},
                        ],
                        "row_count": 4,
                    },
                },
                "baseline_definitions": {
                    "baseline_a_global_majority": {
                        "prediction_rule": "Predict the most frequent event_category across all P218 rows for every row.",
                        "resolved_prediction": "strike_like",
                    },
                    "baseline_b_pitch_type_majority_with_global_fallback": {
                        "prediction_rule": "Predict the most frequent event_category within each pitch_type when the pitch_type has a unique majority; otherwise it falls back to the global majority event_category.",
                        "global_fallback_prediction": "strike_like",
                        "pitch_type_resolution_table": [
                            {
                                "pitch_type": "CH",
                                "support": 1,
                                "event_category_distribution": [{"value": "in_play_out", "count": 1, "fraction": 1.0}],
                                "resolved_prediction": "strike_like",
                                "prediction_source": "global_fallback_due_to_tie",
                                "fallback_to_global_majority": True,
                            },
                            {
                                "pitch_type": "FF",
                                "support": 2,
                                "event_category_distribution": [
                                    {"value": "ball_like", "count": 1, "fraction": 0.5},
                                    {"value": "strike_like", "count": 1, "fraction": 0.5},
                                ],
                                "resolved_prediction": "strike_like",
                                "prediction_source": "pitch_type_majority",
                                "fallback_to_global_majority": False,
                            },
                            {
                                "pitch_type": "SI",
                                "support": 1,
                                "event_category_distribution": [{"value": "in_play_hit", "count": 1, "fraction": 1.0}],
                                "resolved_prediction": "in_play_hit",
                                "prediction_source": "pitch_type_majority",
                                "fallback_to_global_majority": False,
                            },
                        ],
                    },
                },
                "limitations": [
                    "Results are in-sample on a bounded historical snapshot and must not be interpreted as future predictive ability."
                ],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    source_md.write_text(
        "# P219\n\nHistorical feature baseline evaluation prototype only. Not live predictions, not betting advice.\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(script, "ROOT", tmp_path)
    monkeypatch.setattr(script, "REPORT_DIR", tmp_path)
    monkeypatch.setattr(script, "SOURCE_CSV", source_csv)
    monkeypatch.setattr(script, "SOURCE_JSON", source_json)
    monkeypatch.setattr(script, "SOURCE_MD", source_md)
    monkeypatch.setattr(
        script,
        "SOURCE_REQUIRED_HASHES",
        {
            "p219.csv": script._sha256(source_csv),
            "p219.json": script._sha256(source_json),
            "p219.md": script._sha256(source_md),
        },
    )

    payload = script.build_payload()

    assert payload["disclaimer"] == script.DISCLAIMER
    assert payload["source_artifacts"] == ["p219.csv", "p219.json", "p219.md"]
    assert payload["source_summary"]["p219_markdown_mentions_disclaimer"] is True
    assert payload["row_count"] == 4
    assert payload["class_support"] == [
        {"value": "ball_like", "count": 1, "fraction": 0.25},
        {"value": "in_play_hit", "count": 1, "fraction": 0.25},
        {"value": "in_play_out", "count": 1, "fraction": 0.25},
        {"value": "strike_like", "count": 1, "fraction": 0.25},
    ]

    baseline_a = payload["metrics"]["baseline_a_global_majority"]
    baseline_b = payload["metrics"]["baseline_b_pitch_type_majority_with_global_fallback"]
    assert baseline_a["accuracy"] == 0.25
    assert baseline_b["accuracy"] == 0.5
    assert baseline_b["direct_coverage"] == {
        "rows": 3,
        "fraction": 0.75,
        "correct_rows": 2,
        "accuracy": 0.666667,
    }
    assert baseline_b["fallback_coverage"] == {
        "rows": 1,
        "fraction": 0.25,
        "correct_rows": 0,
        "accuracy": 0.0,
    }
    assert baseline_b["per_class_errors"][1] == {
        "class_label": "in_play_hit",
        "support": 1,
        "correct_count": 1,
        "misclassified_count": 0,
        "predicted_count": 1,
        "false_positive_count": 0,
        "recall": 1.0,
        "precision": 1.0,
    }
    assert payload["pitch_type_resolution"]["fallback_pitch_types"] == ["CH"]
    assert payload["pitch_type_resolution"]["direct_pitch_types"] == ["FF", "SI"]
    assert len(payload["error_rows"]["baseline_b_incorrect"]) == 2
    assert payload["error_rows"]["baseline_b_incorrect"][0]["source_row_id"] == 2
    assert payload["error_rows"]["any_incorrect"][-1]["source_row_id"] == 4
    assert payload["metrics"]["comparison"] == {
        "accuracy_delta_b_minus_a": 0.25,
        "correct_row_delta_b_minus_a": 1,
    }
    assert "No betting advice claim." in payload["prohibited_claims"]


def test_main_writes_deterministic_outputs(tmp_path, monkeypatch, capsys):
    script = _load_script_module()
    source_csv = tmp_path / "p219.csv"
    source_json = tmp_path / "p219.json"
    source_md = tmp_path / "p219.md"
    out_html = tmp_path / "p220.html"
    out_json = tmp_path / "p220.json"

    source_csv.write_text(
        "\n".join(
            [
                "source_row_id,game_date,game_pk,pitcher,pitch_type,actual_event_category,baseline_a_global_prediction,baseline_a_correct,baseline_b_pitch_type_prediction,baseline_b_correct,baseline_b_prediction_source",
                "1,2024-04-01,1,Pitcher A,FF,strike_like,strike_like,True,strike_like,True,pitch_type_majority",
                "2,2024-04-01,1,Pitcher A,CH,ball_like,strike_like,False,strike_like,False,global_fallback_due_to_tie",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    source_json.write_text(
        json.dumps(
            {
                "task": "P219-A Historical Feature Baseline Evaluation Prototype",
                "status": "PASS_P218A_ARTIFACT_ONLY_HISTORICAL_FEATURE_BASELINE_EVALUATION_PROTOTYPE",
                "disclaimer": "Historical feature baseline evaluation prototype only. Not live predictions, not betting advice.",
                "historical_only_disclaimer": "Historical feature baseline evaluation prototype only. Not live predictions, not betting advice.",
                "row_count": 2,
                "column_count": 11,
                "output_columns": script.ROW_COLUMNS,
                "target_definition": {
                    "name": "event_category",
                    "description": "Historical categorical label copied from the fixed P218 feature table event_category column.",
                    "class_support": [
                        {"value": "ball_like", "count": 1, "fraction": 0.5},
                        {"value": "strike_like", "count": 1, "fraction": 0.5},
                    ],
                    "label_order": ["ball_like", "strike_like"],
                },
                "metric_summary": {
                    "baseline_a_global_majority": {
                        "accuracy": 0.5,
                        "confusion_matrix": {
                            "ball_like": {"ball_like": 0, "strike_like": 1},
                            "strike_like": {"ball_like": 0, "strike_like": 1},
                        },
                        "correct_count": 1,
                        "coverage_fraction": 1.0,
                        "coverage_rows": 2,
                        "predicted_class_distribution": [{"value": "strike_like", "count": 2, "fraction": 1.0}],
                        "row_count": 2,
                    },
                    "baseline_b_pitch_type_majority_with_global_fallback": {
                        "accuracy": 0.5,
                        "confusion_matrix": {
                            "ball_like": {"ball_like": 0, "strike_like": 1},
                            "strike_like": {"ball_like": 0, "strike_like": 1},
                        },
                        "correct_count": 1,
                        "coverage_fraction": 0.5,
                        "coverage_rows": 1,
                        "predicted_class_distribution": [{"value": "strike_like", "count": 2, "fraction": 1.0}],
                        "row_count": 2,
                    },
                },
                "baseline_definitions": {
                    "baseline_a_global_majority": {
                        "prediction_rule": "Predict the most frequent event_category across all P218 rows for every row.",
                        "resolved_prediction": "strike_like",
                    },
                    "baseline_b_pitch_type_majority_with_global_fallback": {
                        "prediction_rule": "Predict the most frequent event_category within each pitch_type when the pitch_type has a unique majority; otherwise it falls back to the global majority event_category.",
                        "global_fallback_prediction": "strike_like",
                        "pitch_type_resolution_table": [
                            {
                                "pitch_type": "CH",
                                "support": 1,
                                "event_category_distribution": [{"value": "ball_like", "count": 1, "fraction": 1.0}],
                                "resolved_prediction": "strike_like",
                                "prediction_source": "global_fallback_due_to_tie",
                                "fallback_to_global_majority": True,
                            },
                            {
                                "pitch_type": "FF",
                                "support": 1,
                                "event_category_distribution": [{"value": "strike_like", "count": 1, "fraction": 1.0}],
                                "resolved_prediction": "strike_like",
                                "prediction_source": "pitch_type_majority",
                                "fallback_to_global_majority": False,
                            },
                        ],
                    },
                },
                "limitations": [],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    source_md.write_text(
        "# P219\n\nHistorical feature baseline evaluation prototype only. Not live predictions, not betting advice.\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(script, "ROOT", tmp_path)
    monkeypatch.setattr(script, "REPORT_DIR", tmp_path)
    monkeypatch.setattr(script, "SOURCE_CSV", source_csv)
    monkeypatch.setattr(script, "SOURCE_JSON", source_json)
    monkeypatch.setattr(script, "SOURCE_MD", source_md)
    monkeypatch.setattr(script, "OUT_HTML", out_html)
    monkeypatch.setattr(script, "OUT_JSON", out_json)
    monkeypatch.setattr(
        script,
        "SOURCE_REQUIRED_HASHES",
        {
            "p219.csv": script._sha256(source_csv),
            "p219.json": script._sha256(source_json),
            "p219.md": script._sha256(source_md),
        },
    )

    assert script.main() == 0
    first_html = out_html.read_text(encoding="utf-8")
    first_json = out_json.read_text(encoding="utf-8")

    assert script.main() == 0
    assert out_html.read_text(encoding="utf-8") == first_html
    assert out_json.read_text(encoding="utf-8") == first_json

    payload = json.loads(first_json)
    assert payload["disclaimer"] == script.DISCLAIMER
    assert payload["metrics"]["baseline_b_pitch_type_majority_with_global_fallback"]["direct_coverage"]["rows"] == 1
    assert "Baseline B Incorrect Rows" in first_html
    assert "Historical baseline error analysis dashboard only. Not live predictions, not betting advice." in first_html

    captured = capsys.readouterr()
    assert "P220-A HISTORICAL BASELINE ERROR ANALYSIS DASHBOARD PASS" in captured.out
