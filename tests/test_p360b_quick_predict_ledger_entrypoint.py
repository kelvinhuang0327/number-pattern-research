"""
P360B: opt-in predraw ledger entrypoint integration tests.

Covers the wiring added to tools/quick_predict.py (--write-predraw-ledger /
--predraw-ledger-path / LOTTERY_PREDRAW_LEDGER_PATH) into the P360A
append-only ledger (lottery_api/engine/predraw_ledger.py).

ALL tests here use tmp_path for both the source DB and the ledger path.
`qp.DB_PATH` is monkeypatched to a synthetic temp sqlite file for every test
that runs the entrypoint -- no test opens, copies, or writes the canonical
lottery_v2.db. This mirrors the discipline in
tests/test_p360a_predraw_metadata_instrumentation.py.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import sqlite3
import sys
from pathlib import Path

import pytest

import tools.quick_predict as qp
from lottery_api.engine import predraw_ledger as pl


# ─── Synthetic DB fixture ───────────────────────────────────────────────────

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
        # offsets 0,7,14,21,28,35 are pairwise-distinct mod 49; shifting all
        # by the same amount (draw_num) preserves distinctness.
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
def synthetic_db(tmp_path, monkeypatch):
    db_path = tmp_path / "synthetic_lottery_v2.db"
    _make_synthetic_biglotto_db(db_path)
    monkeypatch.setattr(qp, "DB_PATH", str(db_path))
    monkeypatch.delenv("LOTTERY_PREDRAW_LEDGER_PATH", raising=False)
    return db_path


def _run_main(argv):
    old_argv = sys.argv
    sys.argv = ["quick_predict.py"] + argv
    try:
        qp.main()
    finally:
        sys.argv = old_argv


# ─── 1. CLI surface ─────────────────────────────────────────────────────────

def test_help_exposes_opt_in_flags():
    import subprocess

    proc = subprocess.run(
        [sys.executable, str(Path(qp.__file__)), "--help"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "--write-predraw-ledger" in proc.stdout
    assert "--predraw-ledger-path" in proc.stdout


# ─── 2. Opt-in gate helpers (no DB / no ledger involved) ───────────────────

def test_predraw_ledger_enabled_requires_explicit_opt_in(monkeypatch):
    monkeypatch.delenv("LOTTERY_PREDRAW_LEDGER_PATH", raising=False)
    assert qp.predraw_ledger_enabled(
        argparse.Namespace(write_predraw_ledger=False, predraw_ledger_path=None)
    ) is False
    assert qp.predraw_ledger_enabled(
        argparse.Namespace(write_predraw_ledger=True, predraw_ledger_path=None)
    ) is True

    monkeypatch.setenv("LOTTERY_PREDRAW_LEDGER_PATH", "/tmp/does-not-need-to-exist.jsonl")
    assert qp.predraw_ledger_enabled(
        argparse.Namespace(write_predraw_ledger=False, predraw_ledger_path=None)
    ) is True


def test_resolve_predraw_ledger_path_precedence(monkeypatch):
    monkeypatch.delenv("LOTTERY_PREDRAW_LEDGER_PATH", raising=False)
    assert qp.resolve_predraw_ledger_path(
        argparse.Namespace(predraw_ledger_path="/tmp/cli.jsonl")
    ) == "/tmp/cli.jsonl"

    monkeypatch.setenv("LOTTERY_PREDRAW_LEDGER_PATH", "/tmp/env.jsonl")
    assert qp.resolve_predraw_ledger_path(
        argparse.Namespace(predraw_ledger_path=None)
    ) == "/tmp/env.jsonl"

    monkeypatch.delenv("LOTTERY_PREDRAW_LEDGER_PATH", raising=False)
    assert qp.resolve_predraw_ledger_path(argparse.Namespace(predraw_ledger_path=None)) is None


def test_compute_next_scheduled_draw_date_advances_to_valid_weekday():
    schedule_config = {"rules": {"BIG_LOTTO": {"draw_weekdays": [1, 4]}}}  # Tue/Fri
    next_date = qp.compute_next_scheduled_draw_date("2099-01-01", "BIG_LOTTO", schedule_config)
    parsed = _dt.datetime.strptime(next_date, "%Y-%m-%d")
    assert parsed.weekday() in (1, 4)
    assert parsed > _dt.datetime.strptime("2099-01-01", "%Y-%m-%d")


def test_compute_next_scheduled_draw_date_daily_539_is_always_next_day():
    schedule_config = {"rules": {"DAILY_539": {"draw_weekdays": [0, 1, 2, 3, 4, 5, 6]}}}
    next_date = qp.compute_next_scheduled_draw_date("2099-01-01", "DAILY_539", schedule_config)
    assert next_date == "2099-01-02"


# ─── 3. No opt-in => zero behaviour change ─────────────────────────────────

def test_no_opt_in_never_invokes_ledger_writer(synthetic_db, tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(
        qp, "write_predraw_ledger_for_prediction", lambda *a, **k: calls.append((a, k))
    )
    _run_main(
        ["--dry-run", "--json-out", str(tmp_path / "out.json"), "--lottery", "BIG_LOTTO", "--bets", "2"]
    )
    assert calls == [], "ledger writer must never be called without opt-in"


def test_no_opt_in_preserves_existing_dry_run_output(synthetic_db, tmp_path):
    json_out = tmp_path / "out.json"
    before = synthetic_db.read_bytes()

    _run_main(
        ["--dry-run", "--json-out", str(json_out), "--lottery", "BIG_LOTTO", "--bets", "2"]
    )

    assert synthetic_db.read_bytes() == before, "no-opt-in run must not touch the source DB"
    payload = json.loads(json_out.read_text())
    assert payload["dry_run"] is True
    assert payload["db_written"] is False
    assert payload["final_classification"] == "P4B_QUICK_PREDICT_DRYRUN_READY"
    assert payload["predictions"][0]["lottery_type"] == "BIG_LOTTO"
    assert payload["predictions"][0]["num_bets"] == 2


# ─── 4. Opt-in writes a valid, eligible LIVE_PREDRAW record ────────────────

def test_opt_in_cli_flag_writes_valid_live_predraw_records(synthetic_db, tmp_path):
    ledger_path = tmp_path / "opt_in_ledger.jsonl"
    _run_main([
        "--dry-run", "--json-out", str(tmp_path / "out.json"),
        "--lottery", "BIG_LOTTO", "--bets", "2",
        "--write-predraw-ledger", "--predraw-ledger-path", str(ledger_path),
    ])

    assert ledger_path.exists()
    records = pl.read_all_records(ledger_path)
    assert len(records) == 2  # 2 bets requested => 2 PREDICTION records

    for rec in records:
        assert rec["generation_mode"] == "LIVE_PREDRAW"
        assert rec["lottery_type"] == "BIG_LOTTO"
        assert rec["strategy_id"] == "biglotto_p0_2bet"
        assert rec["generation_source"] == "tools/quick_predict.py"
        eligibility = pl.evaluate_oos_eligibility(rec)
        assert eligibility.eligible is True, eligibility.reason

    result = pl.verify_chain(ledger_path)
    assert result.ok is True
    assert result.total_records == 2


def test_env_var_opt_in_enables_ledger_without_cli_flag(synthetic_db, tmp_path, monkeypatch):
    ledger_path = tmp_path / "env_ledger.jsonl"
    monkeypatch.setenv("LOTTERY_PREDRAW_LEDGER_PATH", str(ledger_path))

    _run_main([
        "--dry-run", "--json-out", str(tmp_path / "out.json"),
        "--lottery", "BIG_LOTTO", "--bets", "2",
    ])

    assert ledger_path.exists()
    records = pl.read_all_records(ledger_path)
    assert len(records) == 2
    assert all(r["generation_mode"] == "LIVE_PREDRAW" for r in records)


def test_p361_audit_counts_the_opt_in_records_without_performance_fields(synthetic_db, tmp_path):
    ledger_path = tmp_path / "audit_ledger.jsonl"
    _run_main([
        "--dry-run", "--json-out", str(tmp_path / "out.json"),
        "--lottery", "BIG_LOTTO", "--bets", "2",
        "--write-predraw-ledger", "--predraw-ledger-path", str(ledger_path),
    ])

    records = pl.read_all_records(ledger_path)
    report = pl.p361_dry_run_audit(records, minimum_n_by_lottery={"BIG_LOTTO": 150})
    assert report.total_eligible == 2
    assert report.per_strategy_eligible_counts.get("biglotto_p0_2bet") == 2
    assert report.status == "ACCUMULATING"
    assert report.below_minimum is True


# ─── 5. Canonical DB / forbidden-path guards ───────────────────────────────

def test_opt_in_run_never_writes_the_synthetic_source_db(synthetic_db, tmp_path):
    before = synthetic_db.read_bytes()
    _run_main([
        "--dry-run", "--json-out", str(tmp_path / "out.json"),
        "--lottery", "BIG_LOTTO", "--bets", "2",
        "--write-predraw-ledger", "--predraw-ledger-path", str(tmp_path / "guard_ledger.jsonl"),
    ])
    assert synthetic_db.read_bytes() == before, (
        "opt-in run must not write the source DB (predraw_ledger reads it strictly read-only)"
    )


def test_ledger_path_resolving_to_canonical_db_basename_is_safely_skipped(synthetic_db, tmp_path):
    forbidden_path = tmp_path / "lottery_v2.db"
    history = [
        {"draw": "114000100", "date": "2099-01-01", "numbers": [1, 2, 3, 4, 5, 6], "special": None}
    ] * 60

    # Must not raise (LedgerPathError is caught and reported, never propagated
    # -- an opt-in misconfiguration must never crash a real prediction run)
    # and must never create a file at the forbidden canonical basename.
    qp.write_predraw_ledger_for_prediction(
        "BIG_LOTTO", [{"numbers": [1, 2, 3, 4, 5, 6]}], 2, history, "run-guard", str(forbidden_path)
    )
    assert not forbidden_path.exists()


# ─── 6. Backfill/replay paths structurally cannot emit LIVE_PREDRAW ────────

def test_quick_predict_has_no_retrospective_or_backfill_ledger_call():
    source = Path(qp.__file__).read_text(encoding="utf-8")
    assert "write_retrospective_record" not in source, (
        "quick_predict.py is a live prediction entrypoint; it must never call "
        "write_retrospective_record (BACKFILL/RETROSPECTIVE_REPLAY/REGENERATED)"
    )


def test_backfill_and_replay_writers_still_structurally_cannot_emit_live(tmp_path):
    writer = pl.PredrawLedgerWriter(ledger_path=tmp_path / "ledger.jsonl")
    with pytest.raises(ValueError):
        writer.write_retrospective_record(
            generation_mode="LIVE_PREDRAW",
            lottery_type="BIG_LOTTO",
            target_draw=500,
            strategy_id="biglotto_triple_strike",
            strategy_version="v0.1",
            predicted_numbers=[1, 2, 3, 4, 5, 6],
            predicted_special=None,
            bet_index=0,
            n_bets_total=1,
            run_id="backfill-run",
            generation_source="tools/some_future_backfill_tool.py",
        )
