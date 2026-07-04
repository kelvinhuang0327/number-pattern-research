"""
P364: explicit opt-in predraw ledger capture runner tests.

Covers tools/predraw_capture_runner.py, the deliberate operator-invoked
capture command that wraps the P360B quick_predict opt-in ledger write path
(which in turn is the only caller of the P360A live-prediction writer).

ALL tests use tmp_path for both the source DB and the ledger path; qp.DB_PATH
is monkeypatched to a synthetic temp sqlite file for every test that touches
a DB -- no test opens, copies, or writes the canonical lottery_v2.db. No test
prints or asserts on specific predicted numbers; stdout is explicitly checked
to contain none. Mirrors the discipline in
tests/test_p360b_quick_predict_ledger_entrypoint.py.
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import sqlite3
from pathlib import Path

import pytest

import tools.predraw_capture_runner as pcr
import tools.quick_predict as qp
from lottery_api.engine import predraw_ledger as pl


# Same synthetic-DB shape as tests/test_p360b_quick_predict_ledger_entrypoint.py.
def _make_synthetic_biglotto_db(
    db_path: Path, n_rows: int = 60, last_draw: int = 114000100, last_date: str = "2099-01-01"
) -> None:
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
def fresh_db(tmp_path, monkeypatch):
    """Synthetic BIG_LOTTO DB whose derived next-draw close time is in the future."""
    db_path = tmp_path / "synthetic_source.db"
    _make_synthetic_biglotto_db(db_path)  # last_date=2099-01-01
    monkeypatch.setattr(qp, "DB_PATH", str(db_path))
    monkeypatch.delenv("LOTTERY_PREDRAW_LEDGER_PATH", raising=False)
    return db_path


@pytest.fixture
def stale_db(tmp_path, monkeypatch):
    """Synthetic DB frozen in the past: a backfill/replay-era snapshot whose
    derived next-draw close time has long passed."""
    db_path = tmp_path / "synthetic_stale_source.db"
    _make_synthetic_biglotto_db(db_path, last_date="2020-01-01")
    monkeypatch.setattr(qp, "DB_PATH", str(db_path))
    monkeypatch.delenv("LOTTERY_PREDRAW_LEDGER_PATH", raising=False)
    return db_path


# ─── 1. No opt-in => the runner does nothing at all ─────────────────────────

def test_no_opt_in_writes_nothing_reads_nothing_exits_2(fresh_db, tmp_path, monkeypatch):
    ledger_path = tmp_path / "ledger.jsonl"
    monkeypatch.setattr(
        qp, "load_history_readonly",
        lambda *a, **k: pytest.fail("runner must not read the DB without opt-in"),
    )
    monkeypatch.setattr(
        qp, "write_predraw_ledger_for_prediction",
        lambda *a, **k: pytest.fail("runner must not write the ledger without opt-in"),
    )
    rc = pcr.main(["--lottery", "BIG_LOTTO", "--bets", "2",
                   "--predraw-ledger-path", str(ledger_path)])
    assert rc == pcr.EXIT_NO_OPT_IN
    assert not ledger_path.exists()


def test_env_var_alone_is_not_opt_in_for_the_runner(fresh_db, tmp_path, monkeypatch):
    env_ledger = tmp_path / "env_ledger.jsonl"
    monkeypatch.setenv("LOTTERY_PREDRAW_LEDGER_PATH", str(env_ledger))
    rc = pcr.main(["--lottery", "BIG_LOTTO", "--bets", "2"])
    assert rc == pcr.EXIT_NO_OPT_IN
    assert not env_ledger.exists()


# ─── 2. Opt-in writes valid, eligible, append-only LIVE_PREDRAW records ─────

def test_opt_in_writes_valid_live_predraw_records(fresh_db, tmp_path):
    ledger_path = tmp_path / "capture_ledger.jsonl"
    rc = pcr.main(["--lottery", "BIG_LOTTO", "--bets", "2",
                   "--write-predraw-ledger", "--predraw-ledger-path", str(ledger_path)])
    assert rc == pcr.EXIT_OK
    records = pl.read_all_records(ledger_path)
    assert len(records) == 2  # 2 bets requested => 2 PREDICTION records
    for rec in records:
        assert rec["record_kind"] == "PREDICTION"
        assert rec["generation_mode"] == "LIVE_PREDRAW"
        assert rec["lottery_type"] == "BIG_LOTTO"
        assert rec["generation_source"] == "tools/predraw_capture_runner.py"
        assert rec["run_id"].startswith("predraw_capture-")
        eligibility = pl.evaluate_oos_eligibility(rec)
        assert eligibility.eligible is True, eligibility.reason
    chain = pl.verify_chain(ledger_path)
    assert chain.ok is True
    assert chain.total_records == 2


def test_second_run_appends_without_rewriting_prior_records(fresh_db, tmp_path):
    ledger_path = tmp_path / "append_ledger.jsonl"
    args = ["--lottery", "BIG_LOTTO", "--bets", "2",
            "--write-predraw-ledger", "--predraw-ledger-path", str(ledger_path)]
    assert pcr.main(args) == pcr.EXIT_OK
    first_two_lines = ledger_path.read_text(encoding="utf-8").splitlines()[:2]

    assert pcr.main(args) == pcr.EXIT_OK
    lines_after = ledger_path.read_text(encoding="utf-8").splitlines()
    assert len(lines_after) == 4
    assert lines_after[:2] == first_two_lines, "append-only: prior records must be byte-identical"
    chain = pl.verify_chain(ledger_path)
    assert chain.ok is True
    assert chain.total_records == 4


# ─── 3. Replay/backfill context is refused / has no surface ─────────────────

def test_stale_backfill_era_db_captures_nothing_and_exits_nonzero(stale_db, tmp_path):
    ledger_path = tmp_path / "stale_ledger.jsonl"
    rc = pcr.main(["--lottery", "BIG_LOTTO", "--bets", "2",
                   "--write-predraw-ledger", "--predraw-ledger-path", str(ledger_path)])
    assert rc == pcr.EXIT_CAPTURE_INCOMPLETE
    assert pl.read_all_records(ledger_path) == [], (
        "a stale/backfill-era source DB must never yield LIVE_PREDRAW records"
    )


def test_runner_exposes_no_replay_or_backfill_surface():
    parser = pcr.build_parser()
    option_strings = set()
    for action in parser._actions:
        option_strings.update(action.option_strings)
    assert option_strings == {
        "-h", "--help", "--lottery", "--bets",
        "--write-predraw-ledger", "--predraw-ledger-path",
    }, "no argument may exist to target past draws, backdate, or select a generation mode"

    source = Path(pcr.__file__).read_text(encoding="utf-8")
    assert "write_retrospective_record" not in source
    assert "DatabaseManager" not in source  # read-only history loader only
    assert "load_history_readonly" in source
    assert "print_prediction" not in source  # number display path never invoked


# ─── 4. Canonical/source DB is never opened for write ───────────────────────

def test_readonly_chmod_source_db_still_captures_and_bytes_unchanged(fresh_db, tmp_path):
    before = fresh_db.read_bytes()
    os.chmod(fresh_db, 0o444)  # any write-open of the source DB would now fail loudly
    try:
        ledger_path = tmp_path / "romode_ledger.jsonl"
        rc = pcr.main(["--lottery", "BIG_LOTTO", "--bets", "2",
                       "--write-predraw-ledger", "--predraw-ledger-path", str(ledger_path)])
        assert rc == pcr.EXIT_OK
        assert len(pl.read_all_records(ledger_path)) == 2
    finally:
        os.chmod(fresh_db, 0o644)
    assert fresh_db.read_bytes() == before, "source DB must be byte-invariant"


def test_ledger_path_with_canonical_db_basename_is_refused(fresh_db, tmp_path):
    forbidden = tmp_path / "lottery_v2.db"
    rc = pcr.main(["--lottery", "BIG_LOTTO", "--bets", "2",
                   "--write-predraw-ledger", "--predraw-ledger-path", str(forbidden)])
    assert rc == pcr.EXIT_CAPTURE_INCOMPLETE
    assert not forbidden.exists()


# ─── 5. Safe output: no numbers, no predictive/betting claims ────────────────

def test_stdout_contains_no_predicted_numbers_and_carries_disclaimer(fresh_db, tmp_path, capsys):
    ledger_path = tmp_path / "output_ledger.jsonl"
    rc = pcr.main(["--lottery", "BIG_LOTTO", "--bets", "2",
                   "--write-predraw-ledger", "--predraw-ledger-path", str(ledger_path)])
    assert rc == pcr.EXIT_OK
    out = capsys.readouterr().out

    records = pl.read_all_records(ledger_path)
    assert records, "precondition: records were written"
    for rec in records:
        assert qp.format_numbers(rec["predicted_numbers"]) not in out
        assert str(sorted(rec["predicted_numbers"])) not in out

    for banned in ("預測號碼", "預測報告", "Edge", "隨機基準"):
        assert banned not in out
    assert "not a prediction" in out
