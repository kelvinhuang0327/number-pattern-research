from __future__ import annotations

import ast
import copy
import hashlib
import json
from pathlib import Path

import pytest

from lottery_api.models import replay_strategy_registry
from scripts import generate_non_online_replay_fixture as fixture_gen


EXPECTED_ELIGIBLE_STATUSES = {"REJECTED", "RETIRED", "OBSERVATION"}


def _write_and_load(path: Path) -> dict:
    rc = fixture_gen.main(["--output", str(path)])
    assert rc == 0
    return json.loads(path.read_text(encoding="utf-8"))


def _current_eligible_registry_rows() -> list[dict[str, str]]:
    metadata = replay_strategy_registry.list_strategy_lifecycle_metadata()
    non_executable = set(
        replay_strategy_registry.list_non_executable_strategy_ids()
    )
    expected = []
    for item in metadata:
        strategy_id = item["strategy_id"]
        status = item["lifecycle_status"]
        if (
            strategy_id not in non_executable
            or status not in EXPECTED_ELIGIBLE_STATUSES
        ):
            continue
        lottery_type = item.get("lottery_type")
        if not lottery_type:
            lottery_type = sorted(item["supported_lottery_types"])[0]
        expected.append(
            {
                "strategy_id": strategy_id,
                "lifecycle_status": status,
                "lottery_type": lottery_type,
            }
        )
    return sorted(
        expected,
        key=lambda row: (
            row["lifecycle_status"],
            row["lottery_type"],
            row["strategy_id"],
        ),
    )


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
    actual_ids = [record["strategy_id"] for record in records]
    expected_rows = _current_eligible_registry_rows()
    expected_ids = [row["strategy_id"] for row in expected_rows]
    assert data["strategy_count"] == len(expected_rows)
    assert len(records) == len(expected_rows)
    assert actual_ids == expected_ids
    assert len(actual_ids) == len(set(actual_ids))
    assert [
        (record["strategy_id"], record["lifecycle_status"], record["lottery_type"])
        for record in records
    ] == [
        (row["strategy_id"], row["lifecycle_status"], row["lottery_type"])
        for row in expected_rows
    ]
    row_ids = [record["fixture_row_id"] for record in records]
    assert len(row_ids) == len(set(row_ids))
    for record in records:
        token = hashlib.sha256(
            f"{record['strategy_id']}|{record['lifecycle_status']}|"
            f"{fixture_gen.FIXTURE_VERSION}".encode("utf-8")
        ).hexdigest()[:12]
        assert record["fixture_row_id"] == f"fixture-{record['strategy_id']}-{token}"
        assert record["draw_id"] == f"fixture-draw-{token[:8]}"


def test_lifecycle_status_preserved_and_online_excluded(tmp_path: Path):
    out = tmp_path / "outputs" / "replay" / "fixture.json"
    data = _write_and_load(out)
    statuses = {record["lifecycle_status"] for record in data["records"]}
    assert fixture_gen.ALLOWED_STATUSES == EXPECTED_ELIGIBLE_STATUSES
    assert statuses == {
        row["lifecycle_status"] for row in _current_eligible_registry_rows()
    }
    assert statuses <= EXPECTED_ELIGIBLE_STATUSES
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


def test_generator_ast_uses_only_lifecycle_metadata_registry_apis():
    source = Path(fixture_gen.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    registry_imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.module == "lottery_api.models.replay_strategy_registry"
        for alias in node.names
    }
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    assert registry_imports == {
        "list_non_executable_strategy_ids",
        "list_strategy_lifecycle_metadata",
    }
    assert not names.intersection({"sqlite3", "get_adapter", "get_one_bet"})


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


def test_default_output_is_a_separate_current_artifact(tmp_path: Path, monkeypatch):
    frozen = (
        tmp_path / "outputs" / "replay" / "non_online_replay_fixture_20260511.json"
    )
    out = tmp_path / "outputs" / "replay" / "non_online_replay_fixture_current.json"
    frozen.parent.mkdir(parents=True)
    frozen_bytes = b"frozen historical snapshot\n"
    frozen.write_bytes(frozen_bytes)

    assert fixture_gen.DEFAULT_OUTPUT.name == "non_online_replay_fixture_current.json"
    assert fixture_gen.DEFAULT_OUTPUT != fixture_gen.HISTORICAL_FIXTURE_PATH
    monkeypatch.setattr(fixture_gen, "HISTORICAL_FIXTURE_PATH", frozen)
    monkeypatch.setattr(fixture_gen, "DEFAULT_OUTPUT", out)

    assert fixture_gen.main([]) == 0
    assert out.exists()
    assert frozen.read_bytes() == frozen_bytes


def test_default_output_cannot_be_redirected_to_frozen_fixture(
    tmp_path: Path, monkeypatch
):
    frozen = (
        tmp_path / "outputs" / "replay" / "non_online_replay_fixture_20260511.json"
    )
    frozen.parent.mkdir(parents=True)
    frozen_bytes = b"frozen historical snapshot\n"
    frozen.write_bytes(frozen_bytes)
    monkeypatch.setattr(fixture_gen, "HISTORICAL_FIXTURE_PATH", frozen)
    monkeypatch.setattr(fixture_gen, "DEFAULT_OUTPUT", frozen)

    with pytest.raises(ValueError, match="historical 20260511 fixture is frozen"):
        fixture_gen.main([])
    assert frozen.read_bytes() == frozen_bytes


def test_explicit_frozen_fixture_path_is_rejected(tmp_path: Path, monkeypatch):
    frozen = (
        tmp_path / "outputs" / "replay" / "non_online_replay_fixture_20260511.json"
    )
    frozen.parent.mkdir(parents=True)
    frozen_bytes = b"frozen historical snapshot\n"
    frozen.write_bytes(frozen_bytes)
    monkeypatch.setattr(fixture_gen, "HISTORICAL_FIXTURE_PATH", frozen)

    with pytest.raises(ValueError, match="historical 20260511 fixture is frozen"):
        fixture_gen.main(["--output", str(frozen)])
    assert frozen.read_bytes() == frozen_bytes


def test_symlink_to_frozen_fixture_is_rejected(tmp_path: Path, monkeypatch):
    frozen = (
        tmp_path / "outputs" / "replay" / "non_online_replay_fixture_20260511.json"
    )
    alias = tmp_path / "outputs" / "replay" / "current.json"
    frozen.parent.mkdir(parents=True)
    frozen_bytes = b"frozen historical snapshot\n"
    frozen.write_bytes(frozen_bytes)
    alias.symlink_to(frozen)
    monkeypatch.setattr(fixture_gen, "HISTORICAL_FIXTURE_PATH", frozen)

    with pytest.raises(ValueError, match="historical 20260511 fixture is frozen"):
        fixture_gen.main(["--output", str(alias)])
    assert frozen.read_bytes() == frozen_bytes
    assert alias.is_symlink()


def test_invalid_registry_metadata_is_rejected(monkeypatch):
    metadata = copy.deepcopy(
        replay_strategy_registry.list_strategy_lifecycle_metadata()
    )
    non_executable = replay_strategy_registry.list_non_executable_strategy_ids()
    metadata[0]["lifecycle_status"] = "UNKNOWN_STATE"
    monkeypatch.setattr(fixture_gen, "list_strategy_lifecycle_metadata", lambda: metadata)
    monkeypatch.setattr(
        fixture_gen, "list_non_executable_strategy_ids", lambda: non_executable
    )

    with pytest.raises(ValueError, match="Invalid lifecycle status"):
        fixture_gen.build_fixture()


def test_missing_registry_metadata_is_rejected(monkeypatch):
    metadata = copy.deepcopy(
        replay_strategy_registry.list_strategy_lifecycle_metadata()
    )
    non_executable = replay_strategy_registry.list_non_executable_strategy_ids()
    metadata[0].pop("supported_lottery_types")
    monkeypatch.setattr(fixture_gen, "list_strategy_lifecycle_metadata", lambda: metadata)
    monkeypatch.setattr(
        fixture_gen, "list_non_executable_strategy_ids", lambda: non_executable
    )

    with pytest.raises(ValueError, match="Invalid supported_lottery_types"):
        fixture_gen.build_fixture()


def test_unhashable_registry_metadata_is_rejected(monkeypatch):
    metadata = copy.deepcopy(
        replay_strategy_registry.list_strategy_lifecycle_metadata()
    )
    non_executable = replay_strategy_registry.list_non_executable_strategy_ids()
    metadata[0]["lifecycle_status"] = []
    monkeypatch.setattr(fixture_gen, "list_strategy_lifecycle_metadata", lambda: metadata)
    monkeypatch.setattr(
        fixture_gen, "list_non_executable_strategy_ids", lambda: non_executable
    )

    with pytest.raises(ValueError, match="Invalid lifecycle status"):
        fixture_gen.build_fixture()


def test_duplicate_strategy_identity_is_rejected(monkeypatch):
    metadata = copy.deepcopy(
        replay_strategy_registry.list_strategy_lifecycle_metadata()
    )
    non_executable = replay_strategy_registry.list_non_executable_strategy_ids()
    metadata.append(copy.deepcopy(metadata[0]))
    monkeypatch.setattr(fixture_gen, "list_strategy_lifecycle_metadata", lambda: metadata)
    monkeypatch.setattr(
        fixture_gen, "list_non_executable_strategy_ids", lambda: non_executable
    )

    with pytest.raises(ValueError, match="Duplicate strategy ID"):
        fixture_gen.build_fixture()


def test_duplicate_non_executable_identity_is_rejected(monkeypatch):
    metadata = replay_strategy_registry.list_strategy_lifecycle_metadata()
    non_executable = replay_strategy_registry.list_non_executable_strategy_ids()
    monkeypatch.setattr(fixture_gen, "list_strategy_lifecycle_metadata", lambda: metadata)
    monkeypatch.setattr(
        fixture_gen,
        "list_non_executable_strategy_ids",
        lambda: [*non_executable, non_executable[0]],
    )

    with pytest.raises(ValueError, match="Duplicate non-executable strategy ID"):
        fixture_gen.build_fixture()


def test_duplicate_fixture_row_identity_is_rejected(monkeypatch):
    monkeypatch.setattr(
        fixture_gen,
        "_build_record",
        lambda strategy_id, lottery_type, lifecycle_status: {
            "strategy_id": strategy_id,
            "fixture_row_id": "duplicate-row-id",
        },
    )

    with pytest.raises(ValueError, match="Duplicate fixture_row_id"):
        fixture_gen.build_fixture()


def test_deterministic_output_repeated_runs(tmp_path: Path):
    out1 = tmp_path / "outputs" / "replay" / "fixture1.json"
    out2 = tmp_path / "outputs" / "replay" / "fixture2.json"
    _write_and_load(out1)
    _write_and_load(out2)
    assert out1.read_bytes() == out2.read_bytes()


def test_required_markers_present(tmp_path: Path):
    out = tmp_path / "outputs" / "replay" / "fixture.json"
    data = _write_and_load(out)
    markers = set(data["markers"])
    assert "P21_NON_ONLINE_FIXTURE_ARTIFACT_READY" in markers
    assert "P21_NO_DB_WRITE_NO_BACKFILL_CONFIRMED" in markers
    assert "P21_NO_PROMOTION_ACTION_CONFIRMED" in markers
