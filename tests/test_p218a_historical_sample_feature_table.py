from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "build_historical_sample_feature_table.py"


def _load_script_module():
    spec = importlib.util.spec_from_file_location("p218a_script", SCRIPT_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_build_payload_derives_stable_feature_rows_from_existing_artifacts(tmp_path, monkeypatch):
    script = _load_script_module()
    source_md = tmp_path / "p216.md"
    source_json = tmp_path / "p216.json"
    source_csv = tmp_path / "p216.csv"
    dashboard_json = tmp_path / "p217.json"

    source_md.write_text(
        "# Sample\n\nHistorical pybaseball multi-date sample pack only. Not live predictions, not betting advice.\n",
        encoding="utf-8",
    )
    source_json.write_text(
        json.dumps(
            {
                "task": "P216-A pybaseball Multi-Date Historical Sample Pack",
                "status": "PASS_FIXED_MULTIDATE_HISTORICAL_SAMPLE_PACK",
                "disclaimer": "Historical pybaseball multi-date sample pack only. Not live predictions, not betting advice.",
                "limitations": [
                    "One fixed three-day historical date range and one team filter only; this is a bounded sample pack, not a season-wide study."
                ],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    source_csv.write_text(
        "\n".join(
            [
                "game_date,game_pk,home_team,away_team,inning,inning_topbot,at_bat_number,pitch_number,player_name,batter,pitcher,pitch_type,events,description,release_speed,zone",
                "2024-04-02,2,SEA,CLE,1,Bottom,1,1,\"Pitcher B\",20,200,CH,,ball,84.3,13",
                "2024-04-01,1,SEA,CLE,1,Top,1,2,\"Pitcher A\",10,100,FF,single,hit_into_play,95.2,5",
                "2024-04-01,1,SEA,CLE,1,Top,1,1,\"Pitcher A\",10,100,SI,,called_strike,94.2,7",
                "2024-04-03,3,SEA,CLE,1,Top,2,1,\"Pitcher C\",30,300,FF,hit_by_pitch,hit_by_pitch,93.4,10",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    dashboard_json.write_text(
        json.dumps(
            {
                "task": "P217-A pybaseball Multi-Date Sample Quality Dashboard",
                "status": "PASS_P216A_ARTIFACT_ONLY_MULTIDATE_QUALITY_DASHBOARD",
                "disclaimer": "Historical pybaseball multi-date quality dashboard only. Not live predictions, not betting advice.",
                "limitations": [
                    "Dashboard metrics are computed from the fixed P216-A CSV snapshot only, not from a refreshed upstream pull."
                ],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(script, "ROOT", tmp_path)
    monkeypatch.setattr(script, "REPORT_DIR", tmp_path)
    monkeypatch.setattr(script, "SOURCE_MD", source_md)
    monkeypatch.setattr(script, "SOURCE_JSON", source_json)
    monkeypatch.setattr(script, "SOURCE_CSV", source_csv)
    monkeypatch.setattr(script, "SOURCE_DASHBOARD_JSON", dashboard_json)

    payload = script.build_payload()

    assert payload["disclaimer"] == script.DISCLAIMER
    assert payload["historical_only_disclaimer"] == script.DISCLAIMER
    assert payload["row_count"] == 4
    assert payload["column_count"] == len(script.FEATURE_COLUMNS)
    assert payload["source_artifacts"] == ["p216.md", "p216.json", "p216.csv", "p217.json"]
    assert payload["source_summary"]["p216_markdown_mentions_disclaimer"] is True
    assert payload["feature_columns"] == script.FEATURE_COLUMNS
    assert payload["derived_feature_definitions"]["zone_bucket"].startswith("Zone bucket derived")
    assert payload["prohibited_claims"] == script.PROHIBITED_CLAIMS
    assert "Dashboard metrics are computed from the fixed P216-A CSV snapshot only, not from a refreshed upstream pull." in payload["limitations"]

    assert [record["source_row_id"] for record in payload["records"]] == [3, 2, 1, 4]
    assert payload["records"][0]["event_category"] == "strike_like"
    assert payload["records"][0]["is_strike_like"] is True
    assert payload["records"][0]["is_in_play"] is False
    assert payload["records"][1]["event_category"] == "in_play_hit"
    assert payload["records"][1]["release_speed_bucket"] == "95_plus"
    assert payload["records"][1]["zone_bucket"] == "in_zone"
    assert payload["records"][2]["event_category"] == "ball_like"
    assert payload["records"][2]["is_ball_like"] is True
    assert payload["records"][2]["release_speed_bucket"] == "lt_85"
    assert payload["records"][2]["zone_bucket"] == "out_of_zone"
    assert payload["records"][3]["event_category"] == "hit_by_pitch"
    assert payload["records"][3]["zone_bucket"] == "other_zone"
    assert payload["feature_distributions"]["event_category"] == [
        {"value": "ball_like", "count": 1, "fraction": 0.25},
        {"value": "hit_by_pitch", "count": 1, "fraction": 0.25},
        {"value": "in_play_hit", "count": 1, "fraction": 0.25},
        {"value": "strike_like", "count": 1, "fraction": 0.25},
    ]


def test_main_writes_deterministic_outputs(tmp_path, monkeypatch, capsys):
    script = _load_script_module()
    source_md = tmp_path / "p216.md"
    source_json = tmp_path / "p216.json"
    source_csv = tmp_path / "p216.csv"
    dashboard_json = tmp_path / "p217.json"
    out_csv = tmp_path / "p218.csv"
    out_json = tmp_path / "p218.json"
    out_md = tmp_path / "p218.md"

    source_md.write_text(
        "# Sample\n\nHistorical pybaseball multi-date sample pack only. Not live predictions, not betting advice.\n",
        encoding="utf-8",
    )
    source_json.write_text(
        json.dumps(
            {
                "task": "P216-A pybaseball Multi-Date Historical Sample Pack",
                "status": "PASS_FIXED_MULTIDATE_HISTORICAL_SAMPLE_PACK",
                "disclaimer": "Historical pybaseball multi-date sample pack only. Not live predictions, not betting advice.",
                "limitations": [],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    source_csv.write_text(
        "\n".join(
            [
                "game_date,game_pk,home_team,away_team,inning,inning_topbot,at_bat_number,pitch_number,player_name,batter,pitcher,pitch_type,events,description,release_speed,zone",
                "2024-04-01,1,SEA,CLE,1,Top,1,1,\"Pitcher A\",10,100,SI,,called_strike,94.2,7",
                "2024-04-01,1,SEA,CLE,1,Top,1,2,\"Pitcher A\",10,100,FF,single,hit_into_play,95.2,5",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    dashboard_json.write_text(
        json.dumps(
            {
                "task": "P217-A pybaseball Multi-Date Sample Quality Dashboard",
                "status": "PASS_P216A_ARTIFACT_ONLY_MULTIDATE_QUALITY_DASHBOARD",
                "disclaimer": "Historical pybaseball multi-date quality dashboard only. Not live predictions, not betting advice.",
                "limitations": [],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(script, "ROOT", tmp_path)
    monkeypatch.setattr(script, "REPORT_DIR", tmp_path)
    monkeypatch.setattr(script, "SOURCE_MD", source_md)
    monkeypatch.setattr(script, "SOURCE_JSON", source_json)
    monkeypatch.setattr(script, "SOURCE_CSV", source_csv)
    monkeypatch.setattr(script, "SOURCE_DASHBOARD_JSON", dashboard_json)
    monkeypatch.setattr(script, "OUT_CSV", out_csv)
    monkeypatch.setattr(script, "OUT_JSON", out_json)
    monkeypatch.setattr(script, "OUT_MD", out_md)

    assert script.main() == 0
    first_csv = out_csv.read_text(encoding="utf-8")
    first_json = out_json.read_text(encoding="utf-8")
    first_md = out_md.read_text(encoding="utf-8")

    assert script.main() == 0
    assert out_csv.read_text(encoding="utf-8") == first_csv
    assert out_json.read_text(encoding="utf-8") == first_json
    assert out_md.read_text(encoding="utf-8") == first_md

    assert script.DISCLAIMER in first_json
    assert script.DISCLAIMER in first_md

    payload = json.loads(first_json)
    assert payload["feature_columns"] == script.FEATURE_COLUMNS
    assert payload["sample_preview"][0]["pitcher"] == "Pitcher A"

    with out_csv.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames == script.FEATURE_COLUMNS
        rows = list(reader)
    assert rows[0]["event_category"] == "strike_like"
    assert rows[1]["event_category"] == "in_play_hit"

    captured = capsys.readouterr()
    assert "P218-A HISTORICAL SAMPLE FEATURE TABLE PROTOTYPE PASS" in captured.out
