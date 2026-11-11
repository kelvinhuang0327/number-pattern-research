from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "build_historical_time_split_baseline_evaluation.py"


def _load_script_module():
    spec = importlib.util.spec_from_file_location("p221a_script", SCRIPT_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_build_payload_computes_deterministic_time_split_holdout_metrics(tmp_path, monkeypatch):
    script = _load_script_module()
    source_csv = tmp_path / "p218.csv"
    source_json = tmp_path / "p218.json"
    source_md = tmp_path / "p218.md"
    source_p219_json = tmp_path / "p219.json"
    source_p220_json = tmp_path / "p220.json"

    source_csv.write_text(
        "\n".join(
            [
                "source_row_id,game_date,game_pk,home_team,away_team,inning,inning_topbot,pitcher,batter,pitch_type,event_category,is_in_play,is_strike_like,is_ball_like,release_speed,release_speed_bucket,zone,zone_bucket",
                "1,2024-04-01,1,SEA,CLE,1,Top,Pitcher A,10,FF,strike_like,False,True,False,94.2,90_to_94_9,5,in_zone",
                "2,2024-04-01,1,SEA,CLE,1,Top,Pitcher A,10,CH,ball_like,False,False,True,87.8,85_to_89_9,13,out_of_zone",
                "3,2024-04-01,1,SEA,CLE,1,Top,Pitcher A,10,SI,in_play_out,True,False,False,93.1,90_to_94_9,7,in_zone",
                "4,2024-04-02,2,SEA,CLE,1,Top,Pitcher B,10,FF,strike_like,False,True,False,95.1,95_plus,1,in_zone",
                "5,2024-04-02,2,SEA,CLE,1,Top,Pitcher B,10,SI,ball_like,False,False,True,94.4,90_to_94_9,13,out_of_zone",
                "6,2024-04-02,2,SEA,CLE,1,Top,Pitcher B,10,CH,in_play_out,True,False,False,87.6,85_to_89_9,4,in_zone",
                "7,2024-04-03,3,SEA,CLE,1,Top,Pitcher C,10,SI,strike_like,False,True,False,95.5,95_plus,5,in_zone",
                "8,2024-04-03,3,SEA,CLE,1,Top,Pitcher C,10,FS,hit_by_pitch,False,False,False,84.2,lt_85,14,out_of_zone",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    source_json.write_text(
        json.dumps(
            {
                "task": "P218-A Historical Sample Feature Table Prototype",
                "status": "PASS_P216A_P217A_ARTIFACT_ONLY_HISTORICAL_SAMPLE_FEATURE_TABLE_PROTOTYPE",
                "disclaimer": "Historical sample feature table prototype only. Not live predictions, not betting advice.",
                "historical_only_disclaimer": "Historical sample feature table prototype only. Not live predictions, not betting advice.",
                "row_count": 8,
                "column_count": 18,
                "feature_columns": ["source_row_id", "pitch_type", "event_category"],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    source_md.write_text(
        "# P218\n\nHistorical sample feature table prototype only. Not live predictions, not betting advice.\n",
        encoding="utf-8",
    )
    source_p219_json.write_text(
        json.dumps(
            {
                "task": "P219-A Historical Feature Baseline Evaluation Prototype",
                "status": "PASS_P218A_ARTIFACT_ONLY_HISTORICAL_FEATURE_BASELINE_EVALUATION_PROTOTYPE",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    source_p220_json.write_text(
        json.dumps(
            {
                "task": "P220-A Historical Baseline Error Analysis Dashboard",
                "status": "PASS_P219A_ARTIFACT_ONLY_HISTORICAL_BASELINE_ERROR_ANALYSIS_DASHBOARD",
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
    monkeypatch.setattr(script, "SOURCE_P219_JSON", source_p219_json)
    monkeypatch.setattr(script, "SOURCE_P220_JSON", source_p220_json)
    monkeypatch.setattr(
        script,
        "SOURCE_REQUIRED_HASHES",
        {
            "p218.csv": script._sha256(source_csv),
            "p218.json": script._sha256(source_json),
            "p218.md": script._sha256(source_md),
            "p219.json": script._sha256(source_p219_json),
            "p220.json": script._sha256(source_p220_json),
        },
    )

    payload = script.build_payload()

    assert payload["disclaimer"] == script.DISCLAIMER
    assert payload["source_artifacts"] == [
        "p218.csv",
        "p218.json",
        "p218.md",
        "p219.json",
        "p220.json",
    ]
    assert payload["row_count"] == 5
    assert payload["column_count"] == len(script.OUTPUT_COLUMNS)
    assert payload["target_definition"]["label_order"] == [
        "strike_like",
        "ball_like",
        "in_play_out",
        "hit_by_pitch",
    ]

    split_one = payload["time_split_definitions"][0]
    split_two = payload["time_split_definitions"][1]
    assert split_one["train_date_range"] == "2024-04-01 to 2024-04-01"
    assert split_one["baseline_a_global_majority_prediction"] == "ball_like"
    assert split_two["baseline_a_global_majority_prediction"] == "ball_like"
    assert split_two["baseline_b_pitch_type_resolution_table"] == [
        {
            "pitch_type": "CH",
            "support": 2,
            "event_category_distribution": [
                {"value": "ball_like", "count": 1, "fraction": 0.5},
                {"value": "in_play_out", "count": 1, "fraction": 0.5},
            ],
            "resolved_prediction": "ball_like",
            "prediction_source": "global_fallback_due_to_tie",
            "fallback_to_global_majority": True,
        },
        {
            "pitch_type": "FF",
            "support": 2,
            "event_category_distribution": [
                {"value": "strike_like", "count": 2, "fraction": 1.0},
            ],
            "resolved_prediction": "strike_like",
            "prediction_source": "pitch_type_majority",
            "fallback_to_global_majority": False,
        },
        {
            "pitch_type": "SI",
            "support": 2,
            "event_category_distribution": [
                {"value": "ball_like", "count": 1, "fraction": 0.5},
                {"value": "in_play_out", "count": 1, "fraction": 0.5},
            ],
            "resolved_prediction": "ball_like",
            "prediction_source": "global_fallback_due_to_tie",
            "fallback_to_global_majority": True,
        },
    ]

    overall = payload["overall_holdout_metrics"]
    assert overall["baseline_a_global_majority"]["accuracy"] == 0.2
    assert overall["baseline_a_global_majority"]["correct_count"] == 1
    assert overall["baseline_b_pitch_type_majority_with_global_fallback"]["accuracy"] == 0.2
    assert overall["baseline_b_pitch_type_majority_with_global_fallback"]["correct_count"] == 1
    assert overall["baseline_b_coverage"] == {
        "direct_pitch_type_majority": {
            "rows": 3,
            "fraction": 0.6,
            "correct_rows": 1,
            "accuracy": 0.333333,
        },
        "global_fallback_due_to_tie": {
            "rows": 1,
            "fraction": 0.2,
            "correct_rows": 0,
            "accuracy": 0.0,
        },
        "global_fallback_missing_pitch_type": {
            "rows": 1,
            "fraction": 0.2,
            "correct_rows": 0,
            "accuracy": 0.0,
        },
        "all_global_fallback": {
            "rows": 2,
            "fraction": 0.4,
            "correct_rows": 0,
            "accuracy": 0.0,
        },
    }
    assert payload["source_summary"]["p218_markdown_mentions_disclaimer"] is True
    assert payload["records"][-1]["baseline_b_prediction_source"] == "global_fallback_missing_pitch_type"
    assert "Historical time-split baseline evaluation prototype only. Not live predictions, not betting advice." in script.render_markdown(payload)
    assert "No betting advice claim." in payload["prohibited_claims"]


def test_main_writes_deterministic_outputs(tmp_path, monkeypatch, capsys):
    script = _load_script_module()
    source_csv = tmp_path / "p218.csv"
    source_json = tmp_path / "p218.json"
    source_md = tmp_path / "p218.md"
    source_p219_json = tmp_path / "p219.json"
    source_p220_json = tmp_path / "p220.json"
    out_csv = tmp_path / "p221.csv"
    out_json = tmp_path / "p221.json"
    out_md = tmp_path / "p221.md"

    source_csv.write_text(
        "\n".join(
            [
                "source_row_id,game_date,game_pk,home_team,away_team,inning,inning_topbot,pitcher,batter,pitch_type,event_category,is_in_play,is_strike_like,is_ball_like,release_speed,release_speed_bucket,zone,zone_bucket",
                "1,2024-04-01,1,SEA,CLE,1,Top,Pitcher A,10,FF,strike_like,False,True,False,94.2,90_to_94_9,5,in_zone",
                "2,2024-04-01,1,SEA,CLE,1,Top,Pitcher A,10,CH,ball_like,False,False,True,87.8,85_to_89_9,13,out_of_zone",
                "3,2024-04-02,2,SEA,CLE,1,Top,Pitcher B,10,FF,strike_like,False,True,False,95.1,95_plus,1,in_zone",
                "4,2024-04-02,2,SEA,CLE,1,Top,Pitcher B,10,FS,hit_by_pitch,False,False,False,84.2,lt_85,14,out_of_zone",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    source_json.write_text(
        json.dumps(
            {
                "task": "P218-A Historical Sample Feature Table Prototype",
                "status": "PASS_P216A_P217A_ARTIFACT_ONLY_HISTORICAL_SAMPLE_FEATURE_TABLE_PROTOTYPE",
                "disclaimer": "Historical sample feature table prototype only. Not live predictions, not betting advice.",
                "historical_only_disclaimer": "Historical sample feature table prototype only. Not live predictions, not betting advice.",
                "row_count": 4,
                "column_count": 18,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    source_md.write_text(
        "# P218\n\nHistorical sample feature table prototype only. Not live predictions, not betting advice.\n",
        encoding="utf-8",
    )
    source_p219_json.write_text(
        json.dumps({"task": "P219-A", "status": "PASS_P219"}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    source_p220_json.write_text(
        json.dumps({"task": "P220-A", "status": "PASS_P220"}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(script, "ROOT", tmp_path)
    monkeypatch.setattr(script, "REPORT_DIR", tmp_path)
    monkeypatch.setattr(script, "SOURCE_CSV", source_csv)
    monkeypatch.setattr(script, "SOURCE_JSON", source_json)
    monkeypatch.setattr(script, "SOURCE_MD", source_md)
    monkeypatch.setattr(script, "SOURCE_P219_JSON", source_p219_json)
    monkeypatch.setattr(script, "SOURCE_P220_JSON", source_p220_json)
    monkeypatch.setattr(script, "OUT_CSV", out_csv)
    monkeypatch.setattr(script, "OUT_JSON", out_json)
    monkeypatch.setattr(script, "OUT_MD", out_md)
    monkeypatch.setattr(
        script,
        "SOURCE_REQUIRED_HASHES",
        {
            "p218.csv": script._sha256(source_csv),
            "p218.json": script._sha256(source_json),
            "p218.md": script._sha256(source_md),
            "p219.json": script._sha256(source_p219_json),
            "p220.json": script._sha256(source_p220_json),
        },
    )

    assert script.main() == 0
    first_csv = out_csv.read_text(encoding="utf-8")
    first_json = out_json.read_text(encoding="utf-8")
    first_md = out_md.read_text(encoding="utf-8")

    assert script.main() == 0
    assert out_csv.read_text(encoding="utf-8") == first_csv
    assert out_json.read_text(encoding="utf-8") == first_json
    assert out_md.read_text(encoding="utf-8") == first_md

    payload = json.loads(first_json)
    assert payload["row_count"] == 2
    assert payload["overall_holdout_metrics"]["baseline_a_global_majority"]["accuracy"] == 0.0
    assert payload["overall_holdout_metrics"]["baseline_b_pitch_type_majority_with_global_fallback"]["accuracy"] == 0.5
    assert script.DISCLAIMER in first_json
    assert script.DISCLAIMER in first_md

    with out_csv.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames == script.OUTPUT_COLUMNS
        rows = list(reader)
    assert rows[0]["split_id"] == "1"
    assert rows[1]["baseline_b_prediction_source"] == "global_fallback_missing_pitch_type"

    captured = capsys.readouterr()
    assert script.SUCCESS_BANNER in captured.out
