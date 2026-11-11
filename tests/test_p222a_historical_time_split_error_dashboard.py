from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "build_historical_time_split_error_dashboard.py"


def _load_script_module():
    spec = importlib.util.spec_from_file_location("p222a_script", SCRIPT_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_build_payload_creates_deterministic_time_split_dashboard(tmp_path, monkeypatch):
    script = _load_script_module()
    source_csv = tmp_path / "p221.csv"
    source_json = tmp_path / "p221.json"
    source_md = tmp_path / "p221.md"
    source_p220_json = tmp_path / "p220.json"

    source_csv.write_text(
        "\n".join(
            [
                "split_id,train_date_range,eval_date,source_row_id,pitch_type,actual_event_category,baseline_a_prediction,baseline_a_correct,baseline_b_prediction,baseline_b_correct,baseline_b_prediction_source",
                "1,2024-04-01 to 2024-04-01,2024-04-02,3,FF,strike_like,ball_like,False,strike_like,True,pitch_type_majority",
                "1,2024-04-01 to 2024-04-01,2024-04-02,4,CH,ball_like,ball_like,True,ball_like,True,global_fallback_due_to_tie",
                "2,2024-04-01 to 2024-04-02,2024-04-03,5,FF,strike_like,strike_like,True,strike_like,True,pitch_type_majority",
                "2,2024-04-01 to 2024-04-02,2024-04-03,6,FS,hit_by_pitch,strike_like,False,strike_like,False,global_fallback_missing_pitch_type",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    source_json.write_text(
        json.dumps(
            {
                "task": "P221-A Historical Time-Split Baseline Evaluation Prototype",
                "status": "PASS_P221",
                "disclaimer": "Historical time-split baseline evaluation prototype only. Not live predictions, not betting advice.",
                "historical_only_disclaimer": "Historical time-split baseline evaluation prototype only. Not live predictions, not betting advice.",
                "row_count": 4,
                "column_count": 11,
                "output_columns": script.ROW_COLUMNS,
                "target_definition": {
                    "name": "event_category",
                    "description": "Historical categorical label.",
                    "label_order": ["strike_like", "ball_like", "hit_by_pitch"],
                },
                "confusion_matrices": {
                    script.BASELINE_A_KEY: {
                        "strike_like": {"strike_like": 1, "ball_like": 1, "hit_by_pitch": 0},
                        "ball_like": {"strike_like": 0, "ball_like": 1, "hit_by_pitch": 0},
                        "hit_by_pitch": {"strike_like": 1, "ball_like": 0, "hit_by_pitch": 0},
                    },
                    script.BASELINE_B_KEY: {
                        "strike_like": {"strike_like": 2, "ball_like": 0, "hit_by_pitch": 0},
                        "ball_like": {"strike_like": 0, "ball_like": 1, "hit_by_pitch": 0},
                        "hit_by_pitch": {"strike_like": 1, "ball_like": 0, "hit_by_pitch": 0},
                    },
                },
                "overall_holdout_metrics": {
                    script.BASELINE_A_KEY: {
                        "row_count": 4,
                        "correct_count": 2,
                        "accuracy": 0.5,
                        "coverage_rows": 4,
                        "coverage_fraction": 1.0,
                        "predicted_class_distribution": [
                            {"value": "ball_like", "count": 2, "fraction": 0.5},
                            {"value": "strike_like", "count": 2, "fraction": 0.5},
                        ],
                        "confusion_matrix": {
                            "strike_like": {"strike_like": 1, "ball_like": 1, "hit_by_pitch": 0},
                            "ball_like": {"strike_like": 0, "ball_like": 1, "hit_by_pitch": 0},
                            "hit_by_pitch": {"strike_like": 1, "ball_like": 0, "hit_by_pitch": 0},
                        },
                    },
                    script.BASELINE_B_KEY: {
                        "row_count": 4,
                        "correct_count": 3,
                        "accuracy": 0.75,
                        "coverage_rows": 4,
                        "coverage_fraction": 1.0,
                        "predicted_class_distribution": [
                            {"value": "strike_like", "count": 3, "fraction": 0.75},
                            {"value": "ball_like", "count": 1, "fraction": 0.25},
                        ],
                        "confusion_matrix": {
                            "strike_like": {"strike_like": 2, "ball_like": 0, "hit_by_pitch": 0},
                            "ball_like": {"strike_like": 0, "ball_like": 1, "hit_by_pitch": 0},
                            "hit_by_pitch": {"strike_like": 1, "ball_like": 0, "hit_by_pitch": 0},
                        },
                    },
                    "baseline_b_coverage": {
                        "direct_pitch_type_majority": {"rows": 2, "fraction": 0.5, "correct_rows": 2, "accuracy": 1.0},
                        "global_fallback_due_to_tie": {"rows": 1, "fraction": 0.25, "correct_rows": 1, "accuracy": 1.0},
                        "global_fallback_missing_pitch_type": {"rows": 1, "fraction": 0.25, "correct_rows": 0, "accuracy": 0.0},
                        "all_global_fallback": {"rows": 2, "fraction": 0.5, "correct_rows": 1, "accuracy": 0.5},
                    },
                },
                "coverage": {
                    script.BASELINE_B_KEY: {
                        "direct_pitch_type_majority": {"rows": 2, "fraction": 0.5, "correct_rows": 2, "accuracy": 1.0},
                        "global_fallback_due_to_tie": {"rows": 1, "fraction": 0.25, "correct_rows": 1, "accuracy": 1.0},
                        "global_fallback_missing_pitch_type": {"rows": 1, "fraction": 0.25, "correct_rows": 0, "accuracy": 0.0},
                        "all_global_fallback": {"rows": 2, "fraction": 0.5, "correct_rows": 1, "accuracy": 0.5},
                    }
                },
                "per_split_metrics": [
                    {
                        "split_id": 1,
                        "eval_date": "2024-04-02",
                        script.BASELINE_A_KEY: {
                            "row_count": 2,
                            "correct_count": 1,
                            "accuracy": 0.5,
                            "coverage_rows": 2,
                            "coverage_fraction": 1.0,
                            "predicted_class_distribution": [{"value": "ball_like", "count": 2, "fraction": 1.0}],
                            "confusion_matrix": {
                                "strike_like": {"strike_like": 0, "ball_like": 1, "hit_by_pitch": 0},
                                "ball_like": {"strike_like": 0, "ball_like": 1, "hit_by_pitch": 0},
                                "hit_by_pitch": {"strike_like": 0, "ball_like": 0, "hit_by_pitch": 0},
                            },
                        },
                        script.BASELINE_B_KEY: {
                            "row_count": 2,
                            "correct_count": 2,
                            "accuracy": 1.0,
                            "coverage_rows": 2,
                            "coverage_fraction": 1.0,
                            "predicted_class_distribution": [
                                {"value": "ball_like", "count": 1, "fraction": 0.5},
                                {"value": "strike_like", "count": 1, "fraction": 0.5},
                            ],
                            "confusion_matrix": {
                                "strike_like": {"strike_like": 1, "ball_like": 0, "hit_by_pitch": 0},
                                "ball_like": {"strike_like": 0, "ball_like": 1, "hit_by_pitch": 0},
                                "hit_by_pitch": {"strike_like": 0, "ball_like": 0, "hit_by_pitch": 0},
                            },
                        },
                        "baseline_b_coverage": {
                            "direct_pitch_type_majority": {"rows": 1, "fraction": 0.5, "correct_rows": 1, "accuracy": 1.0},
                            "global_fallback_due_to_tie": {"rows": 1, "fraction": 0.5, "correct_rows": 1, "accuracy": 1.0},
                            "global_fallback_missing_pitch_type": {"rows": 0, "fraction": 0.0, "correct_rows": 0, "accuracy": 0.0},
                            "all_global_fallback": {"rows": 1, "fraction": 0.5, "correct_rows": 1, "accuracy": 1.0},
                        },
                        "comparison": {"accuracy_delta_b_minus_a": 0.5, "correct_row_delta_b_minus_a": 1},
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
                            "predicted_class_distribution": [{"value": "strike_like", "count": 2, "fraction": 1.0}],
                            "confusion_matrix": {
                                "strike_like": {"strike_like": 1, "ball_like": 0, "hit_by_pitch": 0},
                                "ball_like": {"strike_like": 0, "ball_like": 0, "hit_by_pitch": 0},
                                "hit_by_pitch": {"strike_like": 1, "ball_like": 0, "hit_by_pitch": 0},
                            },
                        },
                        script.BASELINE_B_KEY: {
                            "row_count": 2,
                            "correct_count": 1,
                            "accuracy": 0.5,
                            "coverage_rows": 2,
                            "coverage_fraction": 1.0,
                            "predicted_class_distribution": [{"value": "strike_like", "count": 2, "fraction": 1.0}],
                            "confusion_matrix": {
                                "strike_like": {"strike_like": 1, "ball_like": 0, "hit_by_pitch": 0},
                                "ball_like": {"strike_like": 0, "ball_like": 0, "hit_by_pitch": 0},
                                "hit_by_pitch": {"strike_like": 1, "ball_like": 0, "hit_by_pitch": 0},
                            },
                        },
                        "baseline_b_coverage": {
                            "direct_pitch_type_majority": {"rows": 1, "fraction": 0.5, "correct_rows": 1, "accuracy": 1.0},
                            "global_fallback_due_to_tie": {"rows": 0, "fraction": 0.0, "correct_rows": 0, "accuracy": 0.0},
                            "global_fallback_missing_pitch_type": {"rows": 1, "fraction": 0.5, "correct_rows": 0, "accuracy": 0.0},
                            "all_global_fallback": {"rows": 1, "fraction": 0.5, "correct_rows": 0, "accuracy": 0.0},
                        },
                        "comparison": {"accuracy_delta_b_minus_a": 0.0, "correct_row_delta_b_minus_a": 0},
                    },
                ],
                "time_split_definitions": [
                    {
                        "split_id": 1,
                        "eval_date": "2024-04-02",
                        "train_date_range": "2024-04-01 to 2024-04-01",
                        "train_row_count": 2,
                        "eval_row_count": 2,
                        "baseline_b_pitch_type_resolution_table": [
                            {
                                "pitch_type": "CH",
                                "support": 1,
                                "resolved_prediction": "ball_like",
                                "prediction_source": "global_fallback_due_to_tie",
                                "fallback_to_global_majority": True,
                            },
                            {
                                "pitch_type": "FF",
                                "support": 1,
                                "resolved_prediction": "strike_like",
                                "prediction_source": "pitch_type_majority",
                                "fallback_to_global_majority": False,
                            },
                        ],
                    },
                    {
                        "split_id": 2,
                        "eval_date": "2024-04-03",
                        "train_date_range": "2024-04-01 to 2024-04-02",
                        "train_row_count": 4,
                        "eval_row_count": 2,
                        "baseline_b_pitch_type_resolution_table": [
                            {
                                "pitch_type": "FF",
                                "support": 2,
                                "resolved_prediction": "strike_like",
                                "prediction_source": "pitch_type_majority",
                                "fallback_to_global_majority": False,
                            }
                        ],
                    },
                ],
                "limitations": ["Results are bounded historical holdout metrics only."],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    source_md.write_text(
        "# P221\n\nHistorical time-split baseline evaluation prototype only. Not live predictions, not betting advice.\n",
        encoding="utf-8",
    )
    source_p220_json.write_text(
        json.dumps(
            {
                "task": "P220-A Historical Baseline Error Analysis Dashboard",
                "status": "PASS_P220",
                "metrics": {
                    script.BASELINE_A_KEY: {"accuracy": 0.75},
                    script.BASELINE_B_KEY: {"accuracy": 0.5},
                },
                "limitations": ["This dashboard reads only fixed artifacts."],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(script, "ROOT", tmp_path)
    monkeypatch.setattr(script, "REPORT_DIR", tmp_path)
    monkeypatch.setattr(script, "SOURCE_CSV", source_csv)
    monkeypatch.setattr(script, "SOURCE_JSON", source_json)
    monkeypatch.setattr(script, "SOURCE_MD", source_md)
    monkeypatch.setattr(script, "SOURCE_P220_JSON", source_p220_json)
    monkeypatch.setattr(
        script,
        "SOURCE_REQUIRED_HASHES",
        {
            "p221.csv": script._sha256(source_csv),
            "p221.json": script._sha256(source_json),
            "p221.md": script._sha256(source_md),
            "p220.json": script._sha256(source_p220_json),
        },
    )

    payload = script.build_payload()

    assert payload["disclaimer"] == script.DISCLAIMER
    assert payload["source_artifacts"] == ["p221.csv", "p221.json", "p221.md", "p220.json"]
    assert payload["overall_metrics"]["split_count"] == 2
    assert payload["overall_metrics"]["evaluated_rows"] == 4
    assert payload["overall_metrics"][script.BASELINE_A_KEY]["accuracy"] == 0.5
    assert payload["overall_metrics"][script.BASELINE_B_KEY]["accuracy"] == 0.75
    assert payload["overall_metrics"]["comparison"] == {
        "accuracy_delta_b_minus_a": 0.25,
        "correct_row_delta_b_minus_a": 1,
    }
    assert payload["overall_metrics"]["vs_p220_in_sample"] == {
        script.BASELINE_A_KEY: {
            "p220_accuracy": 0.75,
            "p222_time_split_accuracy": 0.5,
            "accuracy_delta_time_split_minus_p220": -0.25,
        },
        script.BASELINE_B_KEY: {
            "p220_accuracy": 0.5,
            "p222_time_split_accuracy": 0.75,
            "accuracy_delta_time_split_minus_p220": 0.25,
        },
    }
    assert payload["coverage"][script.BASELINE_B_KEY + "_prediction_source_coverage"]["all_global_fallback"] == {
        "rows": 2,
        "fraction": 0.5,
        "correct_rows": 1,
        "accuracy": 0.5,
    }
    assert payload["prediction_source_breakdown"]["pitch_type_majority"]["rows"] == 2
    assert payload["prediction_source_breakdown"]["global_fallback_missing_pitch_type"]["accuracy"] == 0.0
    assert payload["per_date_metrics"][0]["eval_date"] == "2024-04-02"
    assert payload["error_rows"]["baseline_b_only_improvements"] == [
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
        }
    ]
    assert "Historical time-split error analysis dashboard only. Not live predictions, not betting advice." in script.render_html(payload)
    assert "No betting advice claim." in payload["prohibited_claims"]


def test_main_writes_deterministic_outputs(tmp_path, monkeypatch, capsys):
    script = _load_script_module()
    source_csv = tmp_path / "p221.csv"
    source_json = tmp_path / "p221.json"
    source_md = tmp_path / "p221.md"
    source_p220_json = tmp_path / "p220.json"
    out_html = tmp_path / "p222.html"
    out_json = tmp_path / "p222.json"

    source_csv.write_text(
        "\n".join(
            [
                "split_id,train_date_range,eval_date,source_row_id,pitch_type,actual_event_category,baseline_a_prediction,baseline_a_correct,baseline_b_prediction,baseline_b_correct,baseline_b_prediction_source",
                "1,2024-04-01 to 2024-04-01,2024-04-02,3,FF,strike_like,strike_like,True,strike_like,True,pitch_type_majority",
                "1,2024-04-01 to 2024-04-01,2024-04-02,4,CH,ball_like,strike_like,False,strike_like,False,global_fallback_due_to_tie",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    source_json.write_text(
        json.dumps(
            {
                "task": "P221-A",
                "status": "PASS_P221",
                "disclaimer": "Historical time-split baseline evaluation prototype only. Not live predictions, not betting advice.",
                "historical_only_disclaimer": "Historical time-split baseline evaluation prototype only. Not live predictions, not betting advice.",
                "row_count": 2,
                "column_count": 11,
                "output_columns": script.ROW_COLUMNS,
                "target_definition": {
                    "label_order": ["strike_like", "ball_like"],
                },
                "confusion_matrices": {
                    script.BASELINE_A_KEY: {
                        "strike_like": {"strike_like": 1, "ball_like": 0},
                        "ball_like": {"strike_like": 1, "ball_like": 0},
                    },
                    script.BASELINE_B_KEY: {
                        "strike_like": {"strike_like": 1, "ball_like": 0},
                        "ball_like": {"strike_like": 1, "ball_like": 0},
                    },
                },
                "overall_holdout_metrics": {
                    script.BASELINE_A_KEY: {
                        "row_count": 2,
                        "correct_count": 1,
                        "accuracy": 0.5,
                        "coverage_rows": 2,
                        "coverage_fraction": 1.0,
                        "predicted_class_distribution": [{"value": "strike_like", "count": 2, "fraction": 1.0}],
                        "confusion_matrix": {
                            "strike_like": {"strike_like": 1, "ball_like": 0},
                            "ball_like": {"strike_like": 1, "ball_like": 0},
                        },
                    },
                    script.BASELINE_B_KEY: {
                        "row_count": 2,
                        "correct_count": 1,
                        "accuracy": 0.5,
                        "coverage_rows": 2,
                        "coverage_fraction": 1.0,
                        "predicted_class_distribution": [{"value": "strike_like", "count": 2, "fraction": 1.0}],
                        "confusion_matrix": {
                            "strike_like": {"strike_like": 1, "ball_like": 0},
                            "ball_like": {"strike_like": 1, "ball_like": 0},
                        },
                    },
                    "baseline_b_coverage": {
                        "direct_pitch_type_majority": {"rows": 1, "fraction": 0.5, "correct_rows": 1, "accuracy": 1.0},
                        "global_fallback_due_to_tie": {"rows": 1, "fraction": 0.5, "correct_rows": 0, "accuracy": 0.0},
                        "global_fallback_missing_pitch_type": {"rows": 0, "fraction": 0.0, "correct_rows": 0, "accuracy": 0.0},
                        "all_global_fallback": {"rows": 1, "fraction": 0.5, "correct_rows": 0, "accuracy": 0.0},
                    },
                },
                "coverage": {
                    script.BASELINE_B_KEY: {
                        "direct_pitch_type_majority": {"rows": 1, "fraction": 0.5, "correct_rows": 1, "accuracy": 1.0},
                        "global_fallback_due_to_tie": {"rows": 1, "fraction": 0.5, "correct_rows": 0, "accuracy": 0.0},
                        "global_fallback_missing_pitch_type": {"rows": 0, "fraction": 0.0, "correct_rows": 0, "accuracy": 0.0},
                        "all_global_fallback": {"rows": 1, "fraction": 0.5, "correct_rows": 0, "accuracy": 0.0},
                    }
                },
                "per_split_metrics": [
                    {
                        "split_id": 1,
                        "eval_date": "2024-04-02",
                        script.BASELINE_A_KEY: {
                            "row_count": 2,
                            "correct_count": 1,
                            "accuracy": 0.5,
                            "coverage_rows": 2,
                            "coverage_fraction": 1.0,
                            "predicted_class_distribution": [{"value": "strike_like", "count": 2, "fraction": 1.0}],
                            "confusion_matrix": {
                                "strike_like": {"strike_like": 1, "ball_like": 0},
                                "ball_like": {"strike_like": 1, "ball_like": 0},
                            },
                        },
                        script.BASELINE_B_KEY: {
                            "row_count": 2,
                            "correct_count": 1,
                            "accuracy": 0.5,
                            "coverage_rows": 2,
                            "coverage_fraction": 1.0,
                            "predicted_class_distribution": [{"value": "strike_like", "count": 2, "fraction": 1.0}],
                            "confusion_matrix": {
                                "strike_like": {"strike_like": 1, "ball_like": 0},
                                "ball_like": {"strike_like": 1, "ball_like": 0},
                            },
                        },
                        "baseline_b_coverage": {
                            "direct_pitch_type_majority": {"rows": 1, "fraction": 0.5, "correct_rows": 1, "accuracy": 1.0},
                            "global_fallback_due_to_tie": {"rows": 1, "fraction": 0.5, "correct_rows": 0, "accuracy": 0.0},
                            "global_fallback_missing_pitch_type": {"rows": 0, "fraction": 0.0, "correct_rows": 0, "accuracy": 0.0},
                            "all_global_fallback": {"rows": 1, "fraction": 0.5, "correct_rows": 0, "accuracy": 0.0},
                        },
                        "comparison": {"accuracy_delta_b_minus_a": 0.0, "correct_row_delta_b_minus_a": 0},
                    }
                ],
                "time_split_definitions": [
                    {
                        "split_id": 1,
                        "eval_date": "2024-04-02",
                        "train_date_range": "2024-04-01 to 2024-04-01",
                        "train_row_count": 2,
                        "eval_row_count": 2,
                        "baseline_b_pitch_type_resolution_table": [],
                    }
                ],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    source_md.write_text(
        "# P221\n\nHistorical time-split baseline evaluation prototype only. Not live predictions, not betting advice.\n",
        encoding="utf-8",
    )
    source_p220_json.write_text(
        json.dumps(
            {
                "task": "P220-A",
                "status": "PASS_P220",
                "metrics": {
                    script.BASELINE_A_KEY: {"accuracy": 0.5},
                    script.BASELINE_B_KEY: {"accuracy": 0.5},
                },
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(script, "ROOT", tmp_path)
    monkeypatch.setattr(script, "REPORT_DIR", tmp_path)
    monkeypatch.setattr(script, "SOURCE_CSV", source_csv)
    monkeypatch.setattr(script, "SOURCE_JSON", source_json)
    monkeypatch.setattr(script, "SOURCE_MD", source_md)
    monkeypatch.setattr(script, "SOURCE_P220_JSON", source_p220_json)
    monkeypatch.setattr(script, "OUT_HTML", out_html)
    monkeypatch.setattr(script, "OUT_JSON", out_json)
    monkeypatch.setattr(
        script,
        "SOURCE_REQUIRED_HASHES",
        {
            "p221.csv": script._sha256(source_csv),
            "p221.json": script._sha256(source_json),
            "p221.md": script._sha256(source_md),
            "p220.json": script._sha256(source_p220_json),
        },
    )

    assert script.main() == 0
    captured = capsys.readouterr()
    assert script.SUCCESS_BANNER in captured.out
    assert out_html.exists()
    assert out_json.exists()

    first_html = out_html.read_text(encoding="utf-8")
    first_json = out_json.read_text(encoding="utf-8")
    assert script.main() == 0
    assert out_html.read_text(encoding="utf-8") == first_html
    assert out_json.read_text(encoding="utf-8") == first_json
