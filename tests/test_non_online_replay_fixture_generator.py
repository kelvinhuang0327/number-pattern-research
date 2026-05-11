from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import generate_non_online_replay_fixture as fixture_gen


EXPECTED_NON_ONLINE_IDS = {
    "biglotto_ts3_acb_4bet",
    "biglotto_ts3_markov_freq_5bet",
    "power_shlc_midfreq",
    "p1_deviation_2bet_539",
    "acb_1bet",
    "acb_markov_midfreq",
    "acb_markov_midfreq_3bet",
    "midfreq_acb_2bet",
    "midfreq_fourier_2bet",
    "h6_gate_mk20_ew85",
}


def _write_and_load(path: Path) -> dict:
    rc = fixture_gen.main(["--output", str(path)])
    assert rc == 0
    return json.loads(path.read_text(encoding="utf-8"))


def test_generator_creates_json_artifact(tmp_path: Path):
    out = tmp_path / "outputs" / "replay" / "fixture.json"
    data = _write_and_load(out)
    assert out.exists()
    assert data["fixture_name"] == "non_online_lifecycle_replay_fixture"


def test_artifact_contract_flags(tmp_path: Path):
    out = tmp_path / "outputs" / "replay" / "fixture.json"
    data = _write_and_load(out)
    assert data["synthetic_only"] is True
    assert data["fixture_only"] is True
    assert data["production_db_write"] is False
    assert data["backfill"] is False
    assert data["promotion_action"] is False


def test_strategy_count_and_coverage(tmp_path: Path):
    out = tmp_path / "outputs" / "replay" / "fixture.json"
    data = _write_and_load(out)
    records = data["records"]
    strategy_ids = {r["strategy_id"] for r in records}
    assert data["strategy_count"] == 10
    assert len(records) == 10
    assert strategy_ids == EXPECTED_NON_ONLINE_IDS


def test_lifecycle_status_preserved_and_online_excluded(tmp_path: Path):
    out = tmp_path / "outputs" / "replay" / "fixture.json"
    data = _write_and_load(out)
    statuses = {r["lifecycle_status"] for r in data["records"]}
    assert statuses == {"REJECTED", "RETIRED", "OBSERVATION"}
    assert "ONLINE" not in statuses


def test_records_include_governance_marker(tmp_path: Path):
    out = tmp_path / "outputs" / "replay" / "fixture.json"
    data = _write_and_load(out)
    for record in data["records"]:
        assert record["governance_marker"] == "P21_NON_ONLINE_FIXTURE_ROW"
        assert record["synthetic_only"] is True
        assert record["fixture_only"] is True
        assert record["fixture_source"] == "non_online_lifecycle_fixture"


def test_generator_source_does_not_import_sqlite3():
    source = Path(fixture_gen.__file__).read_text(encoding="utf-8")
    assert "import sqlite3" not in source
    assert "from sqlite3" not in source


def test_sqlite_connect_not_called(monkeypatch, tmp_path: Path):
    calls = []

    class _FakeSqlite:
        @staticmethod
        def connect(*args, **kwargs):
            calls.append((args, kwargs))
            raise AssertionError("sqlite3.connect must not be called")

    monkeypatch.setitem(__import__("sys").modules, "sqlite3", _FakeSqlite)
    out = tmp_path / "outputs" / "replay" / "fixture.json"
    _write_and_load(out)
    assert calls == []


def test_output_path_must_be_under_outputs_replay(tmp_path: Path):
    bad_path = tmp_path / "outside.json"
    with pytest.raises(ValueError):
        fixture_gen.main(["--output", str(bad_path)])


def test_deterministic_output_repeated_runs(tmp_path: Path):
    out1 = tmp_path / "outputs" / "replay" / "fixture1.json"
    out2 = tmp_path / "outputs" / "replay" / "fixture2.json"
    data1 = _write_and_load(out1)
    data2 = _write_and_load(out2)
    assert data1 == data2


def test_required_markers_present(tmp_path: Path):
    out = tmp_path / "outputs" / "replay" / "fixture.json"
    data = _write_and_load(out)
    markers = set(data["markers"])
    assert "P21_NON_ONLINE_FIXTURE_ARTIFACT_READY" in markers
    assert "P21_NO_DB_WRITE_NO_BACKFILL_CONFIRMED" in markers
    assert "P21_NO_PROMOTION_ACTION_CONFIRMED" in markers
