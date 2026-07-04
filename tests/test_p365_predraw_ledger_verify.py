"""
P365: predraw ledger verifier/inspection CLI tests.

Covers tools/predraw_ledger_verify.py, a read-only structural/chain
verifier built on the existing P360A predraw_ledger reader/chain APIs.
ALL tests use tmp_path; no test opens, copies, or writes the canonical
lottery_v2.db, and no test invokes DB-backed prediction generation.
"""
from __future__ import annotations

import datetime as _dt
import json
import sqlite3
from pathlib import Path

import pytest

import tools.predraw_capture_runner as pcr
import tools.predraw_ledger_verify as plv
from lottery_api.engine import predraw_ledger as pl


def _make_synthetic_biglotto_db(db_path: Path, n_rows: int = 60,
                                 last_draw: int = 114000100, last_date: str = "2099-01-01") -> None:
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "CREATE TABLE draws (id INTEGER PRIMARY KEY, draw TEXT, date TEXT, "
        "lottery_type TEXT, numbers TEXT, special INTEGER, jackpot_amount INTEGER)"
    )
    base_date = _dt.datetime.strptime(last_date, "%Y-%m-%d")
    rows = []
    for i in range(n_rows):
        offset = n_rows - 1 - i
        draw_num = last_draw - offset
        date_str = (base_date - _dt.timedelta(days=offset)).strftime("%Y-%m-%d")
        numbers = sorted(((draw_num + k * 7) % 49) + 1 for k in range(6))
        rows.append((str(draw_num), date_str, "BIG_LOTTO", json.dumps(numbers), None, 0))
    conn.executemany(
        "INSERT INTO draws (draw, date, lottery_type, numbers, special, jackpot_amount) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    conn.close()


@pytest.fixture
def captured_ledger(tmp_path, monkeypatch):
    """A real ledger produced end-to-end by the P364 capture runner."""
    db_path = tmp_path / "synthetic_source.db"
    _make_synthetic_biglotto_db(db_path)
    monkeypatch.setattr(pcr.qp, "DB_PATH", str(db_path))
    monkeypatch.delenv("LOTTERY_PREDRAW_LEDGER_PATH", raising=False)

    ledger_path = tmp_path / "ledger.jsonl"
    rc = pcr.main(["--lottery", "BIG_LOTTO", "--bets", "2",
                   "--write-predraw-ledger", "--predraw-ledger-path", str(ledger_path)])
    assert rc == pcr.EXIT_OK
    return ledger_path


# ─── 1. Valid ledger from the real runner passes verification ───────────────

def test_valid_ledger_from_runner_passes_verification(captured_ledger, capsys):
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
