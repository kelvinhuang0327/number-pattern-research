from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pandas as pd
import pytest

from wbc_backend.recommendation import pybaseball_historical_sample_adapter as adapter
from wbc_backend.recommendation.pybaseball_historical_sample_adapter import (
    DISCLAIMER,
    HistoricalSampleConfig,
    HistoricalSampleError,
)

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "build_pybaseball_historical_sample_smoke.py"


def _load_script_module():
    spec = importlib.util.spec_from_file_location("p214a_script", SCRIPT_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_build_payload_delegates_to_pybaseball_and_normalizes_deterministic_snapshot(monkeypatch):
    class FakePybaseball:
        @staticmethod
        def statcast(*, start_dt, end_dt, team, verbose, parallel):
            assert start_dt == "2024-04-01"
            assert end_dt == "2024-04-01"
            assert team == "SEA"
            assert verbose is False
            assert parallel is False
            return pd.DataFrame(
                [
                    {
                        "game_date": "2024-04-01",
                        "game_pk": 745277,
                        "home_team": "SEA",
                        "away_team": "CLE",
                        "inning": 1,
                        "inning_topbot": "Bottom",
                        "at_bat_number": 2,
                        "pitch_number": 2,
                        "batter": 111111,
                        "pitcher": 222222,
                        "pitch_type": "SL",
                        "events": None,
                        "description": "called_strike",
                        "release_speed": 85.4,
                        "zone": 9,
                    },
                    {
                        "game_date": "2024-04-01",
                        "game_pk": 745277,
                        "home_team": "SEA",
                        "away_team": "CLE",
                        "inning": 1,
                        "inning_topbot": "Top",
                        "at_bat_number": 1,
                        "pitch_number": 1,
                        "batter": 333333,
                        "pitcher": 444444,
                        "pitch_type": "FF",
                        "events": "single",
                        "description": "hit_into_play",
                        "release_speed": 96.2,
                        "zone": 5,
                    },
                ]
            )

    monkeypatch.setattr(adapter, "_distribution_version", lambda package_name: "2.2.7")

    payload = adapter.build_historical_sample_payload(pybaseball_module=FakePybaseball)

    assert payload["status"] == "PASS_FIXED_HISTORICAL_READ_ONLY_SAMPLE"
    assert payload["disclaimer"] == DISCLAIMER
    assert payload["source_function"] == "pybaseball.statcast"
    assert payload["source_version"] == "2.2.7"
    assert payload["result_summary"]["fetched_row_count"] == 2
    assert payload["result_summary"]["snapshot_row_count"] == 2
    assert payload["result_summary"]["observed_date_range"] == {
        "start": "2024-04-01",
        "end": "2024-04-01",
    }
    assert payload["records"] == [
        {
            "game_date": "2024-04-01",
            "game_pk": 745277,
            "home_team": "SEA",
            "away_team": "CLE",
            "inning": 1,
            "inning_topbot": "Top",
            "at_bat_number": 1,
            "pitch_number": 1,
            "batter": 333333,
            "pitcher": 444444,
            "pitch_type": "FF",
            "events": "single",
            "description": "hit_into_play",
            "release_speed": 96.2,
            "zone": 5,
        },
        {
            "game_date": "2024-04-01",
            "game_pk": 745277,
            "home_team": "SEA",
            "away_team": "CLE",
            "inning": 1,
            "inning_topbot": "Bottom",
            "at_bat_number": 2,
            "pitch_number": 2,
            "batter": 111111,
            "pitcher": 222222,
            "pitch_type": "SL",
            "events": None,
            "description": "called_strike",
            "release_speed": 85.4,
            "zone": 9,
        },
    ]


def test_build_payload_raises_clear_error_when_historical_fetch_fails():
    class FakePybaseball:
        @staticmethod
        def statcast(**kwargs):
            raise RuntimeError("429 Too Many Requests")

    with pytest.raises(HistoricalSampleError) as excinfo:
        adapter.build_historical_sample_payload(pybaseball_module=FakePybaseball)

    message = str(excinfo.value)
    assert "Historical pybaseball sample fetch failed" in message
    assert "RuntimeError: 429 Too Many Requests" in message


def test_build_payload_rejects_missing_required_columns():
    class FakePybaseball:
        @staticmethod
        def statcast(**kwargs):
            return pd.DataFrame([{"game_date": "2024-04-01", "game_pk": 1}])

    with pytest.raises(HistoricalSampleError) as excinfo:
        adapter.build_historical_sample_payload(pybaseball_module=FakePybaseball)

    assert "missing required columns" in str(excinfo.value)


def test_script_main_writes_deterministic_outputs_and_required_disclaimer(tmp_path, monkeypatch, capsys):
    script = _load_script_module()
    monkeypatch.setattr(script, "REPORT_DIR", tmp_path)
    monkeypatch.setattr(script, "OUT_MD", tmp_path / "sample.md")
    monkeypatch.setattr(script, "OUT_JSON", tmp_path / "sample.json")
    monkeypatch.setattr(script, "OUT_CSV", tmp_path / "sample.csv")

    payload = {
        "task": "P214-A pybaseball Historical Sample Smoke",
        "status": "PASS_FIXED_HISTORICAL_READ_ONLY_SAMPLE",
        "disclaimer": DISCLAIMER,
        "source_library": "pybaseball",
        "source_function": "pybaseball.statcast",
        "source_version": "2.2.7",
        "request": {
            "start_date": "2024-04-01",
            "end_date": "2024-04-01",
            "team": "SEA",
            "parallel": False,
            "verbose": False,
        },
        "result_summary": {
            "fetched_row_count": 2,
            "fetched_column_count": 15,
            "snapshot_row_count": 1,
            "snapshot_columns": list(HistoricalSampleConfig().snapshot_columns),
            "observed_date_range": {"start": "2024-04-01", "end": "2024-04-01"},
        },
        "limitations": [
            "One fixed historical date and one team filter only; this is a bounded smoke sample, not a season-wide study."
        ],
        "guardrails": [
            DISCLAIMER,
            "No custom MLB scraper or parser was implemented; data access is delegated to pybaseball.",
        ],
        "records": [
            {
                "game_date": "2024-04-01",
                "game_pk": 745277,
                "home_team": "SEA",
                "away_team": "CLE",
                "inning": 1,
                "inning_topbot": "Top",
                "at_bat_number": 1,
                "pitch_number": 1,
                "batter": 333333,
                "pitcher": 444444,
                "pitch_type": "FF",
                "events": "single",
                "description": "hit_into_play",
                "release_speed": 96.2,
                "zone": 5,
            }
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
    assert parsed["request"]["team"] == "SEA"
    assert parsed["result_summary"]["snapshot_row_count"] == 1

    captured = capsys.readouterr()
    assert "P214-A PYBASEBALL HISTORICAL SAMPLE SMOKE PASS" in captured.out
