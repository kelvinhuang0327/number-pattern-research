import ast
import csv
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "p2_controlled_replay_backfill_dryrun.py"
SANDBOX = (
    ROOT
    / "_integration_reports"
    / "P2_CONTROLLED_REPLAY_BACKFILL_DRYRUN_MIGRATION_R5"
    / "runtime_sandbox"
    / "focused_tests"
)
MUTATION_SQL = re.compile(
    r"\b(?:INSERT|UPDATE|DELETE|REPLACE|CREATE\s+TABLE|ALTER\s+TABLE|"
    r"DROP\s+TABLE|VACUUM|ATTACH|BEGIN|COMMIT|ROLLBACK)\b",
    re.IGNORECASE,
)


def _load_script():
    spec = importlib.util.spec_from_file_location("p2_controlled_replay_dryrun", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _fresh_case(name: str) -> Path:
    case = SANDBOX / name
    case.mkdir(parents=True, exist_ok=True)
    for path in case.iterdir():
        if path.is_file():
            path.unlink()
    return case


def _create_fixture(path: Path, *, with_schema: bool = True) -> None:
    connection = sqlite3.connect(path)
    if with_schema:
        connection.executescript(
            """
            CREATE TABLE prediction_runs (
                id INTEGER PRIMARY KEY,
                latest_known_draw TEXT NOT NULL,
                snapshot_source TEXT NOT NULL,
                strategy_name TEXT NOT NULL
            );
            CREATE TABLE prediction_items (
                id INTEGER PRIMARY KEY,
                run_id INTEGER NOT NULL,
                numbers TEXT NOT NULL
            );
            CREATE TABLE draws (
                draw TEXT PRIMARY KEY,
                date TEXT NOT NULL,
                numbers TEXT NOT NULL,
                special INTEGER,
                lottery_type TEXT NOT NULL
            );
            CREATE TABLE strategy_prediction_replays (
                strategy_id TEXT NOT NULL,
                target_draw TEXT NOT NULL
            );
            INSERT INTO prediction_runs
                (id, latest_known_draw, snapshot_source, strategy_name)
            VALUES
                (10, '115000001', 'GENERATED', 'ts3_regime_3bet');
            INSERT INTO prediction_items (id, run_id, numbers)
            VALUES (101, 10, '[1, 2, 3, 4, 5, 6]');
            INSERT INTO draws (draw, date, numbers, special, lottery_type)
            VALUES
                ('115000002', '2026-01-02', '[1, 2, 7, 8, 9, 10]', 11, 'BIG_LOTTO');
            """
        )
    connection.commit()
    connection.close()


def _db_snapshot(path: Path) -> tuple[str, int, int]:
    stat = path.stat()
    return hashlib.sha256(path.read_bytes()).hexdigest(), stat.st_size, stat.st_mtime_ns


def _run_cli(*arguments: str) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [sys.executable, str(SCRIPT), *arguments],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def _functional_arguments(
    db_path: Path,
    json_path: Path,
    csv_path: Path,
    *,
    strategy_id: str = "ts3_regime_3bet",
) -> tuple[str, ...]:
    return (
        "--db",
        str(db_path),
        "--strategy-id",
        strategy_id,
        "--prediction-item-ids",
        "101",
        "--json-out",
        str(json_path),
        "--csv-out",
        str(csv_path),
    )


def test_cli_help_exposes_required_flags_without_opening_db(monkeypatch, capsys):
    module = _load_script()

    def fail_if_opened(*_args, **_kwargs):
        pytest.fail("--help must not open SQLite")

    monkeypatch.setattr(module.sqlite3, "connect", fail_if_opened)
    monkeypatch.setattr(sys, "argv", [str(SCRIPT), "--help"])

    with pytest.raises(SystemExit) as exit_info:
        module.main()

    assert exit_info.value.code == 0
    help_text = capsys.readouterr().out
    for flag in (
        "--db",
        "--strategy-id",
        "--prediction-item-ids",
        "--json-out",
        "--csv-out",
    ):
        assert flag in help_text
    assert "Dry-run" in help_text


def test_open_db_ro_rejects_nonexistent_db_without_creating_it():
    module = _load_script()
    case = _fresh_case("missing_db")
    missing_db = case / "does_not_exist.sqlite"

    with pytest.raises(sqlite3.OperationalError):
        module._open_db_ro(str(missing_db))

    assert not missing_db.exists()


def test_open_db_ro_forces_sqlite_read_only_uri(monkeypatch):
    module = _load_script()
    observed = {}

    class FakeConnection:
        row_factory = None

    def fake_connect(database, **kwargs):
        observed["database"] = database
        observed["kwargs"] = kwargs
        return FakeConnection()

    monkeypatch.setattr(module.sqlite3, "connect", fake_connect)
    module._open_db_ro("/task/sandbox/fixture.sqlite")

    assert observed == {
        "database": "file:/task/sandbox/fixture.sqlite?mode=ro",
        "kwargs": {"uri": True},
    }


def test_non_read_only_uri_request_fails_closed_without_db_change():
    module = _load_script()
    case = _fresh_case("non_read_only_request")
    db_path = case / "fixture.sqlite"
    _create_fixture(db_path)
    before = _db_snapshot(db_path)

    with pytest.raises(sqlite3.OperationalError):
        module._open_db_ro(f"{db_path}?mode=rw")

    assert _db_snapshot(db_path) == before


def test_functional_dryrun_preserves_db_and_writes_only_sandbox_outputs():
    case = _fresh_case("ready")
    db_path = case / "fixture.sqlite"
    json_path = case / "preview.json"
    csv_path = case / "preview.csv"
    _create_fixture(db_path)
    before = _db_snapshot(db_path)

    result = _run_cli(*_functional_arguments(db_path, json_path, csv_path))

    assert result.returncode == 0, result.stderr
    assert _db_snapshot(db_path) == before
    assert not list(case.glob("fixture.sqlite-*"))
    assert json_path.is_relative_to(SANDBOX)
    assert csv_path.is_relative_to(SANDBOX)
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    with csv_path.open(newline="", encoding="utf-8") as file_handle:
        csv_rows = list(csv.DictReader(file_handle))
    assert payload["dry_run"] is True
    assert payload["final_classification"] == "P2_TS3_REGIME_BACKFILL_DRYRUN_READY"
    assert payload["eligible_count"] == 1
    assert payload["preview_rows"][0]["would_insert_replay_row"] is True
    assert payload["safety"]["db_written"] is False
    assert len(csv_rows) == 1
    assert csv_rows[0]["prediction_item_id"] == "101"


def test_adapter_missing_emits_blocked_classification_without_preview_rows():
    case = _fresh_case("adapter_missing")
    db_path = case / "fixture.sqlite"
    json_path = case / "blocked.json"
    csv_path = case / "blocked.csv"
    _create_fixture(db_path)
    before = _db_snapshot(db_path)

    result = _run_cli(
        *_functional_arguments(
            db_path,
            json_path,
            csv_path,
            strategy_id="missing_test_adapter",
        )
    )

    assert result.returncode == 0, result.stderr
    assert _db_snapshot(db_path) == before
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["final_classification"] == "P2_TS3_REGIME_BACKFILL_DRYRUN_BLOCKED"
    assert payload["preview_rows"] == []
    assert payload["adapter_bound"] is False
    assert "get_adapter raised" in payload["blocked_reason"]


def test_repeat_runs_are_normalized_reproducible_and_db_invariant():
    case = _fresh_case("repeatability")
    db_path = case / "fixture.sqlite"
    first_json = case / "first.json"
    first_csv = case / "first.csv"
    second_json = case / "second.json"
    second_csv = case / "second.csv"
    _create_fixture(db_path)
    before = _db_snapshot(db_path)

    first = _run_cli(*_functional_arguments(db_path, first_json, first_csv))
    second = _run_cli(*_functional_arguments(db_path, second_json, second_csv))

    assert first.returncode == second.returncode == 0
    assert _db_snapshot(db_path) == before
    first_payload = json.loads(first_json.read_text(encoding="utf-8"))
    second_payload = json.loads(second_json.read_text(encoding="utf-8"))
    first_payload.pop("generated_at")
    second_payload.pop("generated_at")
    assert first_payload == second_payload
    assert first_csv.read_bytes() == second_csv.read_bytes()


def test_missing_schema_fails_closed_without_outputs_or_db_change():
    case = _fresh_case("missing_schema")
    db_path = case / "fixture.sqlite"
    json_path = case / "preview.json"
    csv_path = case / "preview.csv"
    _create_fixture(db_path, with_schema=False)
    before = _db_snapshot(db_path)

    result = _run_cli(*_functional_arguments(db_path, json_path, csv_path))

    assert result.returncode != 0
    assert "no such table" in result.stderr
    assert "backfill completed" not in (result.stdout + result.stderr).lower()
    assert not json_path.exists()
    assert not csv_path.exists()
    assert _db_snapshot(db_path) == before


def test_invalid_json_output_path_fails_closed_without_db_change():
    case = _fresh_case("invalid_json_output")
    db_path = case / "fixture.sqlite"
    json_path = case / "missing_directory" / "preview.json"
    csv_path = case / "preview.csv"
    _create_fixture(db_path)
    before = _db_snapshot(db_path)

    result = _run_cli(*_functional_arguments(db_path, json_path, csv_path))

    assert result.returncode != 0
    assert "backfill completed" not in (result.stdout + result.stderr).lower()
    assert not json_path.exists()
    assert not csv_path.exists()
    assert _db_snapshot(db_path) == before


def test_invalid_csv_output_path_leaves_no_partial_json_or_csv():
    case = _fresh_case("invalid_csv_output")
    db_path = case / "fixture.sqlite"
    json_path = case / "preview.json"
    csv_path = case / "missing_directory" / "preview.csv"
    _create_fixture(db_path)
    before = _db_snapshot(db_path)

    result = _run_cli(*_functional_arguments(db_path, json_path, csv_path))

    assert result.returncode != 0
    assert "backfill completed" not in (result.stdout + result.stderr).lower()
    assert not json_path.exists()
    assert not csv_path.exists()
    assert _db_snapshot(db_path) == before


def test_invalid_cli_arguments_fail_before_db_or_output_access():
    case = _fresh_case("invalid_cli")
    missing_db = case / "must_not_exist.sqlite"

    result = _run_cli("--db", str(missing_db), "--definitely-invalid")

    assert result.returncode == 2
    assert "error:" in result.stderr
    assert "backfill completed" not in (result.stdout + result.stderr).lower()
    assert not missing_db.exists()
    assert list(case.iterdir()) == []


def test_implementation_has_no_mutating_sql_or_production_db_default():
    source = SCRIPT.read_text(encoding="utf-8")
    tree = ast.parse(source)
    string_literals = [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    ]
    imported_modules = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    db_argument_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "add_argument"
        and any(
            isinstance(argument, ast.Constant) and argument.value == "--db"
            for argument in node.args
        )
    ]

    assert ast.parse(source)
    assert not any(MUTATION_SQL.search(value) for value in string_literals)
    assert not {
        name for name in imported_modules if "migration" in name or "backfill" in name
    }
    assert len(db_argument_calls) == 1
    db_keywords = {keyword.arg: keyword.value for keyword in db_argument_calls[0].keywords}
    assert isinstance(db_keywords["required"], ast.Constant)
    assert db_keywords["required"].value is True
    assert "default" not in db_keywords
