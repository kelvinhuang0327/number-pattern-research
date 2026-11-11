from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "build_pybaseball_sample_quality_dashboard.py"


def _load_script_module():
    spec = importlib.util.spec_from_file_location("p215a_script", SCRIPT_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_build_payload_summarizes_existing_p214a_artifacts(tmp_path, monkeypatch):
    script = _load_script_module()
    source_md = tmp_path / "p214.md"
    source_json = tmp_path / "p214.json"
    source_csv = tmp_path / "p214.csv"

    source_md.write_text(
        "# Sample\n\nHistorical pybaseball read-only sample smoke only. Not live predictions, not betting advice.\n",
        encoding="utf-8",
    )
    source_json.write_text(
        json.dumps(
            {
                "task": "P214-A pybaseball Historical Sample Smoke",
                "status": "PASS_FIXED_HISTORICAL_READ_ONLY_SAMPLE",
                "disclaimer": "Historical pybaseball read-only sample smoke only. Not live predictions, not betting advice.",
                "request": {"start_date": "2024-04-01", "end_date": "2024-04-01", "team": "SEA"},
                "result_summary": {
                    "fetched_row_count": 121,
                    "snapshot_row_count": 3,
                },
                "limitations": [
                    "One fixed historical date and one team filter only; this is a bounded smoke sample, not a season-wide study."
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
                "game_date,game_pk,home_team,away_team,inning,inning_topbot,at_bat_number,pitch_number,batter,pitcher,pitch_type,events,description,release_speed,zone",
                "2024-04-01,745277,SEA,CLE,1,Top,1,1,680757,676106,SI,,called_strike,94.2,5",
                "2024-04-01,745277,SEA,CLE,1,Top,1,2,680757,676106,FF,single,hit_into_play,94.5,8",
                "2024-04-01,745277,SEA,CLE,1,Bottom,2,1,665926,555555,FF,,ball,93.7,7",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(script, "ROOT", tmp_path)
    monkeypatch.setattr(script, "REPORT_DIR", tmp_path)
    monkeypatch.setattr(script, "SOURCE_MD", source_md)
    monkeypatch.setattr(script, "SOURCE_JSON", source_json)
    monkeypatch.setattr(script, "SOURCE_CSV", source_csv)

    payload = script.build_payload()

    assert payload["disclaimer"] == script.DISCLAIMER
    assert payload["historical_only_disclaimer"] == script.DISCLAIMER
    assert payload["row_count"] == 3
    assert payload["column_count"] == 15
    assert payload["source_artifacts"] == ["p214.md", "p214.json", "p214.csv"]
    assert payload["source_summary"]["p214_result_summary"]["fetched_row_count"] == 121
    assert payload["missingness"]["events"] == {
        "missing_count": 2,
        "missing_fraction": 0.666667,
    }
    assert payload["distributions"]["pitch_type"] == [
        {"value": "FF", "count": 2, "fraction": 0.666667},
        {"value": "SI", "count": 1, "fraction": 0.333333},
    ]
    assert payload["distributions"]["events"] == [
        {"value": "(missing)", "count": 2, "fraction": 0.666667},
        {"value": "single", "count": 1, "fraction": 0.333333},
    ]
    assert payload["sample_preview"][0]["game_date"] == "2024-04-01"
    assert "No live prediction claim." in payload["prohibited_claims"]


def test_main_writes_deterministic_dashboard_outputs(tmp_path, monkeypatch, capsys):
    script = _load_script_module()
    source_md = tmp_path / "p214.md"
    source_json = tmp_path / "p214.json"
    source_csv = tmp_path / "p214.csv"
    out_html = tmp_path / "p215.html"
    out_json = tmp_path / "p215.json"

    source_md.write_text(
        "# Sample\n\nHistorical pybaseball read-only sample smoke only. Not live predictions, not betting advice.\n",
        encoding="utf-8",
    )
    source_json.write_text(
        json.dumps(
            {
                "task": "P214-A pybaseball Historical Sample Smoke",
                "status": "PASS_FIXED_HISTORICAL_READ_ONLY_SAMPLE",
                "disclaimer": "Historical pybaseball read-only sample smoke only. Not live predictions, not betting advice.",
                "request": {"start_date": "2024-04-01", "end_date": "2024-04-01", "team": "SEA"},
                "result_summary": {
                    "fetched_row_count": 121,
                    "snapshot_row_count": 2,
                },
                "limitations": [
                    "Snapshot records are normalized to a small deterministic subset for inspection and are not production-ready data contracts."
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
                "game_date,game_pk,home_team,away_team,inning,inning_topbot,at_bat_number,pitch_number,batter,pitcher,pitch_type,events,description,release_speed,zone",
                "2024-04-01,745277,SEA,CLE,1,Top,1,1,680757,676106,SI,,called_strike,94.2,5",
                "2024-04-01,745277,SEA,CLE,1,Top,1,2,680757,676106,FF,single,hit_into_play,94.5,8",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(script, "ROOT", tmp_path)
    monkeypatch.setattr(script, "REPORT_DIR", tmp_path)
    monkeypatch.setattr(script, "SOURCE_MD", source_md)
    monkeypatch.setattr(script, "SOURCE_JSON", source_json)
    monkeypatch.setattr(script, "SOURCE_CSV", source_csv)
    monkeypatch.setattr(script, "OUT_HTML", out_html)
    monkeypatch.setattr(script, "OUT_JSON", out_json)

    assert script.main() == 0
    first_html = out_html.read_text(encoding="utf-8")
    first_json = out_json.read_text(encoding="utf-8")

    assert script.main() == 0
    assert out_html.read_text(encoding="utf-8") == first_html
    assert out_json.read_text(encoding="utf-8") == first_json
    assert script.DISCLAIMER in first_html
    assert script.DISCLAIMER in first_json

    combined = (first_html + "\n" + first_json).lower()
    for forbidden in ("kelly", "roi", "clv", "edge", "future prediction", "production readiness"):
        assert forbidden not in combined

    payload = json.loads(first_json)
    assert payload["source_hashes"]["p214.csv"]
    assert payload["sample_preview"][0]["pitch_type"] == "SI"

    captured = capsys.readouterr()
    assert "P215-A PYBASEBALL SAMPLE QUALITY DASHBOARD PASS" in captured.out
