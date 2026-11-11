from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "build_pybaseball_multidate_quality_dashboard.py"


def _load_script_module():
    spec = importlib.util.spec_from_file_location("p217a_script", SCRIPT_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_build_payload_summarizes_existing_p216a_artifacts(tmp_path, monkeypatch):
    script = _load_script_module()
    source_md = tmp_path / "p216.md"
    source_json = tmp_path / "p216.json"
    source_csv = tmp_path / "p216.csv"

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
                "source_request": {"start_date": "2024-04-01", "end_date": "2024-04-03", "team": "SEA"},
                "observed_dates": ["2024-04-01", "2024-04-02"],
                "sample_size_limits": {"per_date_row_limit": 8, "total_row_limit": 24},
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
                "2024-04-01,745277,SEA,CLE,1,Top,1,1,\"Hancock, Emerson\",680757,676106,SI,,called_strike,94.2,5",
                "2024-04-01,745277,SEA,CLE,1,Top,1,2,\"Hancock, Emerson\",680757,676106,FF,single,hit_into_play,94.5,8",
                "2024-04-02,745273,SEA,CLE,1,Bottom,2,1,\"Castillo, Luis\",665926,622491,FF,,ball,93.7,7",
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
    assert payload["column_count"] == 16
    assert payload["source_artifacts"] == ["p216.md", "p216.json", "p216.csv"]
    assert payload["per_date_row_counts"] == {"2024-04-01": 2, "2024-04-02": 1}
    assert payload["source_summary"]["p216_observed_dates"] == ["2024-04-01", "2024-04-02"]
    assert payload["missingness"]["events"] == {
        "missing_count": 2,
        "missing_fraction": 0.666667,
    }
    assert payload["distributions"]["pitch_type"] == [
        {"value": "FF", "count": 2, "fraction": 0.666667},
        {"value": "SI", "count": 1, "fraction": 0.333333},
    ]
    assert payload["distributions"]["game_date"] == [
        {"value": "2024-04-01", "count": 2, "fraction": 0.666667},
        {"value": "2024-04-02", "count": 1, "fraction": 0.333333},
    ]
    assert payload["sample_preview"][0]["game_date"] == "2024-04-01"
    assert "No future prediction claim." in payload["prohibited_claims"]


def test_main_writes_deterministic_dashboard_outputs(tmp_path, monkeypatch, capsys):
    script = _load_script_module()
    source_md = tmp_path / "p216.md"
    source_json = tmp_path / "p216.json"
    source_csv = tmp_path / "p216.csv"
    out_html = tmp_path / "p217.html"
    out_json = tmp_path / "p217.json"

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
                "source_request": {"start_date": "2024-04-01", "end_date": "2024-04-03", "team": "SEA"},
                "observed_dates": ["2024-04-01"],
                "sample_size_limits": {"per_date_row_limit": 8, "total_row_limit": 24},
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
                "game_date,game_pk,home_team,away_team,inning,inning_topbot,at_bat_number,pitch_number,player_name,batter,pitcher,pitch_type,events,description,release_speed,zone",
                "2024-04-01,745277,SEA,CLE,1,Top,1,1,\"Hancock, Emerson\",680757,676106,SI,,called_strike,94.2,5",
                "2024-04-01,745277,SEA,CLE,1,Top,1,2,\"Hancock, Emerson\",680757,676106,FF,single,hit_into_play,94.5,8",
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
    assert "you should bet" not in combined
    assert "recommended stake" not in combined

    payload = json.loads(first_json)
    assert payload["source_hashes"]["p216.csv"]
    assert payload["sample_preview"][0]["pitch_type"] == "SI"
    assert payload["per_date_row_counts"] == {"2024-04-01": 2}

    captured = capsys.readouterr()
    assert "P217-A PYBASEBALL MULTIDATE QUALITY DASHBOARD PASS" in captured.out
