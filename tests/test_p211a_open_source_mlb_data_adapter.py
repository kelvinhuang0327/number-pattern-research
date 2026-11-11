from __future__ import annotations

from dataclasses import dataclass
import json
import os
import subprocess
from pathlib import Path

import pytest

from wbc_backend.recommendation import mlb_open_source_data_adapter as adapter
from wbc_backend.recommendation.mlb_open_source_data_adapter import (
    DISCLAIMER,
    AdapterUnavailableError,
    OpenSourceMlbDataAdapter,
)

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "audit_mlb_open_source_data_libraries.py"
OUT_MD = ROOT / "report" / "p211a_open_source_mlb_data_adoption.md"
OUT_JSON = ROOT / "report" / "p211a_open_source_mlb_data_adoption.json"


def _run_cli() -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    return subprocess.run(
        ["python3", str(SCRIPT)],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )


def test_missing_optional_dependency_fails_with_clear_reason(monkeypatch):
    monkeypatch.setattr(adapter, "_distribution_version", lambda package_name: None)

    client = OpenSourceMlbDataAdapter("pybaseball")

    with pytest.raises(AdapterUnavailableError) as excinfo:
        client.statcast_sample("2024-04-01", "2024-04-01")

    message = str(excinfo.value)
    assert "Optional dependency 'pybaseball' is not installed" in message
    assert "Owner authorization" in message


def test_pybaseball_statcast_adapter_delegates_and_normalizes(monkeypatch):
    class FakeFrame:
        def to_dict(self, orient=None):
            assert orient == "records"
            return [
                {"game_date": "2024-04-01", "pitch_type": "FF", "release_speed": 95.1},
                {"game_date": "2024-04-01", "pitch_type": "SL", "release_speed": 84.7},
            ]

    class FakePybaseball:
        @staticmethod
        def statcast(start_dt, end_dt):
            assert start_dt == "2024-04-01"
            assert end_dt == "2024-04-01"
            return FakeFrame()

    monkeypatch.setattr(adapter, "_distribution_version", lambda package_name: "2.2.7")
    monkeypatch.setattr(adapter, "_import_module", lambda import_name: FakePybaseball)

    result = OpenSourceMlbDataAdapter("pybaseball").statcast_sample(
        "2024-04-01",
        "2024-04-01",
        max_rows=1,
    )

    assert result == {
        "disclaimer": DISCLAIMER,
        "source_library": "pybaseball",
        "source_operation": "statcast",
        "data_kind": "statcast",
        "row_count": 2,
        "returned_rows": 1,
        "columns": ["game_date", "pitch_type", "release_speed"],
        "records": [
            {"game_date": "2024-04-01", "pitch_type": "FF", "release_speed": 95.1},
        ],
    }


def test_mlb_statsapi_schedule_adapter_delegates_without_custom_parsing(monkeypatch):
    class FakeStatsApi:
        @staticmethod
        def schedule(**kwargs):
            assert kwargs == {"start_date": "2024-04-01", "end_date": "2024-04-02", "team": 147}
            return [{"game_id": 1, "home_name": "Yankees", "away_name": "Blue Jays"}]

    monkeypatch.setattr(adapter, "_distribution_version", lambda package_name: "1.9.0")
    monkeypatch.setattr(adapter, "_import_module", lambda import_name: FakeStatsApi)

    result = OpenSourceMlbDataAdapter("mlb_statsapi").schedule(
        "2024-04-01",
        "2024-04-02",
        team_id=147,
    )

    assert result["source_library"] == "mlb_statsapi"
    assert result["source_operation"] == "schedule"
    assert result["data_kind"] == "schedule"
    assert result["records"] == [{"away_name": "Blue Jays", "game_id": 1, "home_name": "Yankees"}]


def test_python_mlb_statsapi_team_lookup_normalizes_object_models(monkeypatch):
    @dataclass
    class Team:
        id: int
        name: str

    class FakeMlbClient:
        @staticmethod
        def get_team_id(name):
            assert name == "Seattle Mariners"
            return [136]

        @staticmethod
        def get_team(team_id):
            assert team_id == 136
            return Team(id=136, name="Seattle Mariners")

    class FakeModule:
        Mlb = FakeMlbClient

    monkeypatch.setattr(adapter, "_distribution_version", lambda package_name: "0.5.0")
    monkeypatch.setattr(adapter, "_import_module", lambda import_name: FakeModule)

    result = OpenSourceMlbDataAdapter("python_mlb_statsapi").team_lookup("Seattle Mariners")

    assert result["source_library"] == "python_mlb_statsapi"
    assert result["source_operation"] == "Mlb.get_team_id/get_team"
    assert result["records"] == [{"id": 136, "name": "Seattle Mariners"}]


def test_unsupported_capability_is_clear():
    with pytest.raises(AdapterUnavailableError) as excinfo:
        OpenSourceMlbDataAdapter("pybaseball").schedule("2024-04-01", "2024-04-02")

    assert "does not expose 'schedule'" in str(excinfo.value)


def test_audit_script_writes_deterministic_reports_and_required_disclaimers():
    first = _run_cli()
    first_json = OUT_JSON.read_text(encoding="utf-8")
    first_md = OUT_MD.read_text(encoding="utf-8")
    second = _run_cli()

    assert "P211-A OPEN-SOURCE MLB DATA LIBRARY ADOPTION AUDIT PASS" in first.stdout
    assert second.returncode == 0
    assert OUT_JSON.read_text(encoding="utf-8") == first_json
    assert OUT_MD.read_text(encoding="utf-8") == first_md

    payload = json.loads(first_json)
    assert payload["audit_status"] == "PASS"
    assert payload["disclaimer"] == DISCLAIMER
    assert {item["package"] for item in payload["candidate_evaluations"]} >= {
        "pybaseball",
        "MLB-StatsAPI",
        "python-mlb-statsapi",
    }
    assert {item["provider"] for item in payload["adapter_diagnostics"]} == {
        "mlb_statsapi",
        "pybaseball",
        "python_mlb_statsapi",
    }
    assert DISCLAIMER in first_md
    lower_output = (first_json + first_md).lower()
    forbidden = [
        "expected value",
        "positive edge",
        "betting edge",
        "kelly",
        "production ready",
        "future prediction",
    ]
    for phrase in forbidden:
        assert phrase not in lower_output
    assert "roi" not in lower_output
