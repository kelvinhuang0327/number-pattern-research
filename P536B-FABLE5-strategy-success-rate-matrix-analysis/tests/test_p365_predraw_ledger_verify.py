"""
P365: predraw ledger verifier/inspection CLI tests.

Covers tools/predraw_ledger_verify.py, a read-only structural/chain
verifier built on the existing P360A predraw_ledger reader/chain APIs.
ALL tests use tmp_path; no test opens, copies, or writes the canonical
lottery_v2.db, and no test invokes DB-backed prediction generation.
"""
from __future__ import annotations

import ast
import datetime as _dt
import json
from pathlib import Path

import pytest

import tools.predraw_ledger_verify as plv
from lottery_api.engine import predraw_ledger as pl

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_FOCUSED_VERIFIER_SOURCES = (
    Path(__file__),
    _PROJECT_ROOT / "tools" / "predraw_ledger_verify.py",
)
_FORBIDDEN_DB_BACKED_IMPORTS = (
    "tools.predraw_capture_runner",
    "tools.quick_predict",
)
_DB_MANAGER_SYMBOL = "DatabaseManager"


@pytest.fixture
def captured_ledger(tmp_path):
    """A chain-valid ledger produced by the P360A writer without DB imports."""
    ledger_path = tmp_path / "ledger.jsonl"
    writer = pl.PredrawLedgerWriter(ledger_path)
    predicted_at = _dt.datetime(2020, 1, 1, tzinfo=_dt.timezone.utc)
    for bet_index, numbers in enumerate(([1, 2, 3, 4, 5, 6], [7, 8, 9, 10, 11, 12])):
        writer.write_retrospective_record(
            generation_mode="BACKFILL",
            lottery_type="BIG_LOTTO",
            target_draw=114000101,
            strategy_id="test-strategy",
            strategy_version="v1",
            predicted_numbers=numbers,
            predicted_special=None,
            bet_index=bet_index,
            n_bets_total=2,
            run_id="test-run",
            generation_source="tests/test_p365_predraw_ledger_verify.py",
            predicted_at=predicted_at,
        )
    return ledger_path


# ─── 0. Regression guard: focused verifier path stays DB-free ───────────────

def _imported_module_names(tree: ast.AST) -> set[str]:
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            imported.add(module)
            imported.update(f"{module}.{alias.name}" if module else alias.name for alias in node.names)
    return imported


def test_focused_verifier_path_has_no_db_backed_imports_or_db_manager_usage():
    for source_path in _FOCUSED_VERIFIER_SOURCES:
        tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))

        imported = _imported_module_names(tree)
        forbidden_imports = {
            name
            for name in imported
            for forbidden in _FORBIDDEN_DB_BACKED_IMPORTS
            if name == forbidden or name.startswith(f"{forbidden}.")
        }
        assert not forbidden_imports, f"{source_path} imports DB-backed prediction path(s): {sorted(forbidden_imports)}"

        db_manager_refs = [
            (node.lineno, node.col_offset)
            for node in ast.walk(tree)
            if (
                (isinstance(node, ast.Name) and node.id == _DB_MANAGER_SYMBOL)
                or (isinstance(node, ast.Attribute) and node.attr == _DB_MANAGER_SYMBOL)
            )
        ]
        assert not db_manager_refs, f"{source_path} directly references {_DB_MANAGER_SYMBOL}: {db_manager_refs}"


# ─── 1. Valid ledger from the writer passes verification ───────────────────

def test_valid_writer_ledger_passes_verification(captured_ledger, capsys):
    rc = plv.main([str(captured_ledger)])
    assert rc == plv.EXIT_OK
    out = capsys.readouterr().out
    assert "validation_status=VALID" in out
    assert "chain_ok=True" in out
    assert "record_count=2" in out


# ─── 2. Missing file fails clearly ───────────────────────────────────────────

def test_missing_file_fails_clearly(tmp_path, capsys):
    missing = tmp_path / "does_not_exist.jsonl"
    rc = plv.main([str(missing)])
    assert rc == plv.EXIT_FILE_NOT_FOUND
    err = capsys.readouterr().err
    assert "does not exist" in err
    assert str(missing) in err


# ─── 3. Malformed JSON fails non-zero ────────────────────────────────────────

def test_malformed_json_line_fails_nonzero(captured_ledger, capsys):
    lines = captured_ledger.read_text(encoding="utf-8").splitlines()
    truncated = lines[0] + "\n" + lines[1][: len(lines[1]) // 2]
    captured_ledger.write_text(truncated, encoding="utf-8")

    rc = plv.main([str(captured_ledger)])
    assert rc == plv.EXIT_INVALID
    out = capsys.readouterr().out
    assert "validation_status=INVALID" in out
    assert "chain_ok=False" in out
    assert "unparseable/truncated" in out


def test_tampered_record_fails_nonzero(captured_ledger, capsys):
    lines = captured_ledger.read_text(encoding="utf-8").splitlines()
    tampered = json.loads(lines[1])
    tampered["bet_index"] = 999  # mutate content without breaking JSON validity
    lines[1] = json.dumps(tampered)
    captured_ledger.write_text("\n".join(lines) + "\n", encoding="utf-8")

    rc = plv.main([str(captured_ledger)])
    assert rc == plv.EXIT_INVALID
    out = capsys.readouterr().out
    assert "validation_status=INVALID" in out
    assert "record_hash mismatch" in out


# ─── 4. Schema-incomplete (but chain-consistent) record is flagged malformed ─

def test_schema_incomplete_record_flagged_malformed(tmp_path, capsys):
    payload = {
        "schema_version": "p360a-v1",
        "record_id": "rec-1",
        "record_kind": "PREDICTION",
        "lottery_type": "BIG_LOTTO",
        "generation_mode": "BACKFILL",
        "predicted_at": "2020-01-01T00:00:00+00:00",
        "created_at": "2020-01-01T00:00:00+00:00",
        "target_draw": 114000101,
        # strategy_id deliberately omitted -- malformed record
        "strategy_version": "v1",
        "predicted_numbers": [1, 2, 3, 4, 5, 6],
        "bet_index": 0,
        "n_bets_total": 1,
        "run_id": "run-1",
        "generation_source": "test",
    }
    record_hash = pl.compute_record_hash(payload, None)
    full_record = dict(payload)
    full_record["prev_record_hash"] = None
    full_record["record_hash"] = record_hash

    ledger_path = tmp_path / "schema_ledger.jsonl"
    ledger_path.write_text(json.dumps(full_record) + "\n", encoding="utf-8")

    rc = plv.main([str(ledger_path)])
    assert rc == plv.EXIT_INVALID
    out = capsys.readouterr().out
    assert "chain_ok=True" in out  # hash chain itself is self-consistent
    assert "validation_status=INVALID" in out
    assert "malformed_record_count=1" in out
    assert "strategy_id" in out


# ─── 5. Canonical DB basename ledger path is refused, not silently accepted ─

def test_canonical_db_basename_path_is_refused(tmp_path, capsys):
    forbidden = tmp_path / "lottery_v2.db"
    forbidden.write_text("not actually a db", encoding="utf-8")
    rc = plv.main([str(forbidden)])
    assert rc == plv.EXIT_REFUSED_PATH
    err = capsys.readouterr().err
    assert "REFUSED" in err


# ─── 6. Safe summary: no predicted numbers, no prediction/betting claims ────

def test_summary_contains_no_predicted_numbers_or_claims(captured_ledger, capsys):
    rc = plv.main([str(captured_ledger)])
    assert rc == plv.EXIT_OK
    out = capsys.readouterr().out

    records = pl.read_all_records(captured_ledger)
    assert records, "precondition: records exist"
    for rec in records:
        assert str(sorted(rec["predicted_numbers"])) not in out
        assert "predicted_numbers" not in out
        assert "predicted_special" not in out

    for banned in ("預測號碼", "預測報告", "Edge", "隨機基準", "獲利", "中獎"):
        assert banned not in out
    assert "NOT a prediction" in out
    assert "OOS" in out


# ─── 7. Empty ledger (0 records) is valid, not an error ─────────────────────

def test_empty_ledger_file_is_valid(tmp_path, capsys):
    empty = tmp_path / "empty.jsonl"
    empty.write_text("", encoding="utf-8")
    rc = plv.main([str(empty)])
    assert rc == plv.EXIT_OK
    out = capsys.readouterr().out
    assert "validation_status=VALID" in out
    assert "record_count=0" in out
