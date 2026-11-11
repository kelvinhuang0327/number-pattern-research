from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path

import pandas as pd
import pytest

from wbc_backend.recommendation import pybaseball_multidate_sample_adapter as adapter
from wbc_backend.recommendation.pybaseball_multidate_sample_adapter import (
    DISCLAIMER,
    MultiDateSampleError,
)

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "build_pybaseball_multidate_sample_pack.py"


def _load_script_module():
    spec = importlib.util.spec_from_file_location("p216a_script", SCRIPT_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_build_payload_delegates_to_pybaseball_and_builds_multidate_pack(monkeypatch):
    class FakePybaseball:
        @staticmethod
        def statcast(*, start_dt, end_dt, team, verbose, parallel):
            assert start_dt == "2024-04-01"
            assert end_dt == "2024-04-03"
            assert team == "SEA"
            assert verbose is False
            assert parallel is False
            return pd.DataFrame(
                [
                    {
                        "game_date": "2024-04-03",
                        "game_pk": 3,
                        "home_team": "SEA",
                        "away_team": "CLE",
                        "inning": 2,
                        "inning_topbot": "Bottom",
                        "at_bat_number": 8,
                        "pitch_number": 3,
                        "player_name": "Pitcher C",
                        "batter": 30,
                        "pitcher": 300,
                        "pitch_type": "SL",
                        "events": None,
                        "description": "ball",
                        "release_speed": 85.1,
                        "zone": 9,
                    },
                    {
                        "game_date": "2024-04-01",
                        "game_pk": 1,
                        "home_team": "SEA",
                        "away_team": "CLE",
                        "inning": 1,
                        "inning_topbot": "Top",
                        "at_bat_number": 1,
                        "pitch_number": 2,
                        "player_name": "Pitcher A",
                        "batter": 10,
                        "pitcher": 100,
                        "pitch_type": "FF",
                        "events": "single",
                        "description": "hit_into_play",
                        "release_speed": 96.2,
                        "zone": 5,
                    },
                    {
                        "game_date": "2024-04-02",
                        "game_pk": 2,
                        "home_team": "SEA",
                        "away_team": "CLE",
                        "inning": 1,
                        "inning_topbot": "Bottom",
                        "at_bat_number": 4,
                        "pitch_number": 1,
                        "player_name": "Pitcher B",
                        "batter": 20,
                        "pitcher": 200,
                        "pitch_type": "CH",
                        "events": "field_out",
                        "description": "hit_into_play",
                        "release_speed": 82.3,
                        "zone": 6,
                    },
                    {
                        "game_date": "2024-04-01",
                        "game_pk": 1,
                        "home_team": "SEA",
                        "away_team": "CLE",
                        "inning": 1,
                        "inning_topbot": "Top",
                        "at_bat_number": 1,
                        "pitch_number": 1,
                        "player_name": "Pitcher A",
                        "batter": 10,
                        "pitcher": 100,
                        "pitch_type": "SI",
                        "events": None,
                        "description": "called_strike",
                        "release_speed": 95.1,
                        "zone": 7,
                    },
                ]
            )

    monkeypatch.setattr(adapter, "_distribution_version", lambda package_name: "2.2.7")

    payload = adapter.build_multidate_sample_payload(pybaseball_module=FakePybaseball)

    assert payload["status"] == "PASS_FIXED_MULTIDATE_HISTORICAL_SAMPLE_PACK"
    assert payload["disclaimer"] == DISCLAIMER
    assert payload["source_function"] == "pybaseball.statcast"
    assert payload["source_version"] == "2.2.7"
    assert payload["fetched_row_count"] == 4
    assert payload["row_count"] == 4
    assert payload["column_count"] == 16
    assert payload["observed_dates"] == ["2024-04-01", "2024-04-02", "2024-04-03"]
    assert payload["sample_size_limits"]["requested_date_count"] == 3
    assert payload["sample_preview"][0]["game_date"] == "2024-04-01"
    assert payload["records"] == [
        {
            "game_date": "2024-04-01",
            "game_pk": 1,
            "home_team": "SEA",
            "away_team": "CLE",
            "inning": 1,
            "inning_topbot": "Top",
            "at_bat_number": 1,
            "pitch_number": 1,
            "player_name": "Pitcher A",
            "batter": 10,
            "pitcher": 100,
            "pitch_type": "SI",
            "events": None,
            "description": "called_strike",
            "release_speed": 95.1,
            "zone": 7,
        },
        {
            "game_date": "2024-04-01",
            "game_pk": 1,
            "home_team": "SEA",
            "away_team": "CLE",
            "inning": 1,
            "inning_topbot": "Top",
            "at_bat_number": 1,
            "pitch_number": 2,
            "player_name": "Pitcher A",
            "batter": 10,
            "pitcher": 100,
            "pitch_type": "FF",
            "events": "single",
            "description": "hit_into_play",
            "release_speed": 96.2,
            "zone": 5,
        },
        {
            "game_date": "2024-04-02",
            "game_pk": 2,
            "home_team": "SEA",
            "away_team": "CLE",
            "inning": 1,
            "inning_topbot": "Bottom",
            "at_bat_number": 4,
            "pitch_number": 1,
            "player_name": "Pitcher B",
            "batter": 20,
            "pitcher": 200,
            "pitch_type": "CH",
            "events": "field_out",
            "description": "hit_into_play",
            "release_speed": 82.3,
            "zone": 6,
        },
        {
            "game_date": "2024-04-03",
            "game_pk": 3,
            "home_team": "SEA",
            "away_team": "CLE",
            "inning": 2,
            "inning_topbot": "Bottom",
            "at_bat_number": 8,
            "pitch_number": 3,
            "player_name": "Pitcher C",
            "batter": 30,
            "pitcher": 300,
            "pitch_type": "SL",
            "events": None,
            "description": "ball",
            "release_speed": 85.1,
            "zone": 9,
        },
    ]


def test_build_payload_raises_clear_error_when_fetch_fails():
    class FakePybaseball:
        @staticmethod
        def statcast(**kwargs):
            raise RuntimeError("network timeout")

    with pytest.raises(MultiDateSampleError) as excinfo:
        adapter.build_multidate_sample_payload(pybaseball_module=FakePybaseball)

    message = str(excinfo.value)
    assert "Historical pybaseball multi-date sample pack fetch failed" in message
    assert "RuntimeError: network timeout" in message


def test_build_payload_rejects_single_date_result():
    class FakePybaseball:
        @staticmethod
        def statcast(**kwargs):
            return pd.DataFrame(
                [
                    {
                        "game_date": "2024-04-01",
                        "game_pk": 1,
                        "home_team": "SEA",
                        "away_team": "CLE",
                        "inning": 1,
                        "inning_topbot": "Top",
                        "at_bat_number": 1,
                        "pitch_number": 1,
                        "player_name": "Pitcher A",
                        "batter": 10,
                        "pitcher": 100,
                        "pitch_type": "FF",
                        "events": None,
                        "description": "called_strike",
                        "release_speed": 95.1,
                        "zone": 7,
                    }
                ]
            )

    with pytest.raises(MultiDateSampleError) as excinfo:
        adapter.build_multidate_sample_payload(pybaseball_module=FakePybaseball)

    assert "did not return multiple dates" in str(excinfo.value)


def test_script_main_writes_deterministic_outputs_and_required_disclaimer(tmp_path, monkeypatch, capsys):
    script = _load_script_module()
    monkeypatch.setattr(script, "REPORT_DIR", tmp_path)
    monkeypatch.setattr(script, "OUT_MD", tmp_path / "sample.md")
    monkeypatch.setattr(script, "OUT_JSON", tmp_path / "sample.json")
    monkeypatch.setattr(script, "OUT_CSV", tmp_path / "sample.csv")

    payload = {
        "task": "P216-A pybaseball Multi-Date Historical Sample Pack",
        "status": "PASS_FIXED_MULTIDATE_HISTORICAL_SAMPLE_PACK",
        "disclaimer": DISCLAIMER,
        "historical_only_disclaimer": DISCLAIMER,
        "source_library": "pybaseball",
        "source_function": "pybaseball.statcast",
        "source_version": "2.2.7",
        "source_request": {
            "start_date": "2024-04-01",
            "end_date": "2024-04-03",
            "team": "SEA",
            "parallel": False,
            "verbose": False,
        },
        "sample_size_limits": {
            "per_date_row_limit": 8,
            "total_row_limit": 24,
            "preview_row_limit": 5,
            "requested_date_count": 3,
        },
        "fetched_row_count": 12,
        "fetched_column_count": 119,
        "row_count": 3,
        "column_count": 16,
        "columns": [
            "game_date",
            "game_pk",
            "home_team",
            "away_team",
            "inning",
            "inning_topbot",
            "at_bat_number",
            "pitch_number",
            "player_name",
            "batter",
            "pitcher",
            "pitch_type",
            "events",
            "description",
            "release_speed",
            "zone",
        ],
        "observed_dates": ["2024-04-01", "2024-04-02", "2024-04-03"],
        "sample_preview": [
            {
                "game_date": "2024-04-01",
                "game_pk": 1,
                "home_team": "SEA",
                "away_team": "CLE",
                "inning": 1,
                "inning_topbot": "Top",
                "at_bat_number": 1,
                "pitch_number": 1,
                "player_name": "Pitcher A",
                "batter": 10,
                "pitcher": 100,
                "pitch_type": "FF",
                "events": "single",
                "description": "hit_into_play",
                "release_speed": 96.2,
                "zone": 5,
            }
        ],
        "limitations": [
            "One fixed three-day historical date range and one team filter only; this is a bounded sample pack, not a season-wide study."
        ],
        "guardrails": [
            DISCLAIMER,
            "No custom MLB scraper or parser was implemented; data access is delegated to pybaseball.",
        ],
        "prohibited_claims": [
            "No future prediction claim.",
            "No betting advice claim.",
        ],
        "records": [
            {
                "game_date": "2024-04-01",
                "game_pk": 1,
                "home_team": "SEA",
                "away_team": "CLE",
                "inning": 1,
                "inning_topbot": "Top",
                "at_bat_number": 1,
                "pitch_number": 1,
                "player_name": "Pitcher A",
                "batter": 10,
                "pitcher": 100,
                "pitch_type": "FF",
                "events": "single",
                "description": "hit_into_play",
                "release_speed": 96.2,
                "zone": 5,
            },
            {
                "game_date": "2024-04-02",
                "game_pk": 2,
                "home_team": "SEA",
                "away_team": "CLE",
                "inning": 1,
                "inning_topbot": "Bottom",
                "at_bat_number": 4,
                "pitch_number": 1,
                "player_name": "Pitcher B",
                "batter": 20,
                "pitcher": 200,
                "pitch_type": "CH",
                "events": "field_out",
                "description": "hit_into_play",
                "release_speed": 82.3,
                "zone": 6,
            },
            {
                "game_date": "2024-04-03",
                "game_pk": 3,
                "home_team": "SEA",
                "away_team": "CLE",
                "inning": 2,
                "inning_topbot": "Top",
                "at_bat_number": 8,
                "pitch_number": 3,
                "player_name": "Pitcher C",
                "batter": 30,
                "pitcher": 300,
                "pitch_type": "SL",
                "events": None,
                "description": "ball",
                "release_speed": 85.1,
                "zone": 9,
            },
        ],
    }
    monkeypatch.setattr(script, "build_payload", lambda: payload)

    assert script.main() == 0
    first_json = script.OUT_JSON.read_text(encoding="utf-8")
    first_md = script.OUT_MD.read_text(encoding="utf-8")
    first_csv = script.OUT_CSV.read_text(encoding="utf-8")
    assert script.main() == 0

    assert script.OUT_JSON.read_text(encoding="utf-8") == first_json
    assert script.OUT_MD.read_text(encoding="utf-8") == first_md
    assert script.OUT_CSV.read_text(encoding="utf-8") == first_csv
    assert DISCLAIMER in first_md
    assert DISCLAIMER in first_json
    assert "betting advice" in first_md.lower()
    assert "kelly" not in (first_json + first_md).lower()

    parsed = json.loads(first_json)
    assert parsed["source_library"] == "pybaseball"
    assert parsed["source_request"]["team"] == "SEA"
    assert parsed["row_count"] == 3
    assert parsed["artifact_hashes"]["sample.csv"]

    with script.OUT_CSV.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 3

    captured = capsys.readouterr()
    assert "P216-A PYBASEBALL MULTI-DATE SAMPLE PACK PASS" in captured.out
