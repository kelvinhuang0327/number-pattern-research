"""Tests for P540B DAILY_539 incremental replay generation (manifested DB write)."""

from __future__ import annotations

import json
import sqlite3
from datetime import date, timedelta
from pathlib import Path

import pytest

import analysis.p540b_daily539_incremental_replay_generation as G


def _build_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE draws (
            id INTEGER PRIMARY KEY,
            draw TEXT NOT NULL,
            date TEXT NOT NULL,
            lottery_type TEXT NOT NULL,
            numbers TEXT NOT NULL,
            special INTEGER DEFAULT 0
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE strategy_prediction_replays (
            id INTEGER PRIMARY KEY,
            lottery_type TEXT NOT NULL,
            target_draw TEXT NOT NULL,
            target_date TEXT,
            strategy_id TEXT NOT NULL,
            strategy_name TEXT,
            strategy_version TEXT,
            history_cutoff_draw TEXT,
            replay_status TEXT NOT NULL,
            reject_reason TEXT,
            predicted_numbers TEXT,
            predicted_special INTEGER,
            actual_numbers TEXT,
            actual_special INTEGER,
            hit_numbers TEXT,
            hit_count INTEGER DEFAULT 0,
            special_hit INTEGER DEFAULT 0,
            replay_run_id TEXT,
            generated_at TEXT,
            truth_level TEXT,
            controlled_apply_id TEXT,
            source TEXT,
            provenance_hash TEXT,
            provenance_source TEXT,
            dry_run INTEGER DEFAULT 0,
            prediction_cutoff_date TEXT,
            prediction_generated_at TEXT,
            bet_index INTEGER NOT NULL DEFAULT 1,
            UNIQUE(lottery_type, target_draw, strategy_id, bet_index)
        )
        """
    )
    # DAILY_539: 120 historical draws, replayed up to draw 110 (strategy_x only).
    # Dates increase monotonically with i (matches real production data, where
    # date ASC and draw-number ASC always agree) -- a wrapping day-of-month
    # formula would desync the two sort keys and is not representative.
    base_date = date(2026, 1, 1)
    for i in range(1, 121):
        draw = f"{100000000 + i}"
        draw_date = (base_date + timedelta(days=i)).strftime("%Y/%m/%d")
        conn.execute(
            "INSERT INTO draws (draw, date, lottery_type, numbers) VALUES (?,?,?,?)",
            (draw, draw_date, "DAILY_539", json.dumps([1, 2, 3, 4, 5])),
        )
        if i <= 110:
            # Real production data has existing rows with controlled_apply_id IS NULL
            # (pre-dating the controlled-apply convention) -- reproduce that here so
            # any NULL-unsafe SQL (`!= ?` instead of `IS NOT ?`) gets caught.
            conn.execute(
                "INSERT INTO strategy_prediction_replays "
                "(lottery_type, target_draw, strategy_id, replay_status, bet_index, dry_run, controlled_apply_id) "
                "VALUES ('DAILY_539', ?, 'strategy_x', 'PREDICTED', 1, 0, NULL)",
                (draw,),
            )
    # BIG_LOTTO / POWER_LOTTO: a few untouched rows to verify isolation.
    for lt, sid in (("BIG_LOTTO", "big_x"), ("POWER_LOTTO", "power_x")):
        conn.execute(
            "INSERT INTO draws (draw, date, lottery_type, numbers) VALUES (?,?,?,?)",
            ("200000001", "2026/01/01", lt, json.dumps([1, 2, 3, 4, 5, 6])),
        )
        conn.execute(
            "INSERT INTO strategy_prediction_replays "
            "(lottery_type, target_draw, strategy_id, replay_status, bet_index, dry_run) "
            "VALUES (?, '200000001', ?, 'PREDICTED', 1, 0)",
            (lt, sid),
        )
    conn.commit()
    conn.close()


class _StubAdapter:
    """Deterministic stand-in adapter: always predicts [1,2,3,4,5]."""

    class _Meta:
        strategy_id = "stub_strategy"
        strategy_name = "Stub Strategy"
        strategy_version = "v0-test"

    meta = _Meta()

    def get_one_bet(self, history, lottery_type):
        return [1, 2, 3, 4, 5], None


class _FailingAdapter:
    class _Meta:
        strategy_id = "stub_failing_strategy"
        strategy_name = "Stub Failing Strategy"
        strategy_version = "v0-test"

    meta = _Meta()

    def get_one_bet(self, history, lottery_type):
        raise ValueError("not enough history")


def test_build_pre_write_snapshot_finds_missing_target_draws(tmp_path):
    db = tmp_path / "synthetic.db"
    _build_db(db)
    conn = G._open_ro(db)
    try:
        snapshot = G.build_pre_write_snapshot(conn)
    finally:
        conn.close()

    assert snapshot["daily539_latest_replayed_target_draw"] == "100000110"
    assert snapshot["daily539_missing_target_draw_count"] == 10
    assert snapshot["daily539_missing_target_draws"] == [f"{100000000 + i}" for i in range(111, 121)]
    assert snapshot["strategy_prediction_replays_count_by_lottery"]["DAILY_539"] == 110
    assert snapshot["strategy_prediction_replays_count_by_lottery"]["BIG_LOTTO"] == 1
    assert snapshot["strategy_prediction_replays_count_by_lottery"]["POWER_LOTTO"] == 1


def test_build_manifest_is_daily539_only_and_consistent(tmp_path):
    db = tmp_path / "synthetic.db"
    _build_db(db)
    conn = G._open_ro(db)
    try:
        snapshot = G.build_pre_write_snapshot(conn)
    finally:
        conn.close()

    manifest = G.build_manifest(snapshot, [_StubAdapter()])
    assert manifest["target_lottery"] == "DAILY_539"
    assert manifest["target_draw_count"] == 10
    assert manifest["in_scope_strategy_ids"] == ["stub_strategy"]
    assert manifest["expected_inserted_rows"] == 10

    ok, problems = G.is_manifest_internally_consistent(manifest)
    assert ok is True
    assert problems == []


def test_manifest_rejects_leaked_excluded_strategy_id():
    bad_manifest = {
        "target_lottery": "DAILY_539",
        "target_draw_count": 5,
        "in_scope_strategy_ids": ["daily539_f4cold_3bet"],  # excluded, should never appear
        "in_scope_strategy_id_count": 1,
        "expected_inserted_rows": 5,
    }
    ok, problems = G.is_manifest_internally_consistent(bad_manifest)
    assert ok is False
    assert any("excluded strategy_id" in p for p in problems)


def test_generate_rows_uses_only_causal_history_no_leakage(tmp_path):
    db = tmp_path / "synthetic.db"
    _build_db(db)
    conn = G._open_ro(db)
    try:
        all_draws = G.load_lottery_draws(conn, "DAILY_539")
    finally:
        conn.close()

    target_draws = [f"{100000000 + i}" for i in range(111, 116)]
    rows = G.generate_rows(all_draws, target_draws, [_StubAdapter()])

    assert len(rows) == 5
    for row, target_draw in zip(rows, target_draws):
        assert row["target_draw"] == target_draw
        assert row["strategy_id"] == "stub_strategy"
        assert row["bet_index"] == 1
        assert row["dry_run"] == 0
        # history_cutoff_draw must be the immediate predecessor, never the target itself or later.
        assert int(row["history_cutoff_draw"]) < int(target_draw)
        assert row["replay_status"] == "PREDICTED"
        assert row["hit_count"] == 5  # stub always predicts [1,2,3,4,5], actual is also [1,2,3,4,5]


def test_generate_rows_handles_adapter_error_as_non_predicted_status(tmp_path):
    db = tmp_path / "synthetic.db"
    _build_db(db)
    conn = G._open_ro(db)
    try:
        all_draws = G.load_lottery_draws(conn, "DAILY_539")
    finally:
        conn.close()

    rows = G.generate_rows(all_draws, ["100000111"], [_FailingAdapter()])
    assert len(rows) == 1
    assert rows[0]["replay_status"] == "INSUFFICIENT_HISTORY"
    assert rows[0]["predicted_numbers"] is None
    assert rows[0]["hit_count"] == 0


def test_apply_rows_transactional_inserts_exactly_expected_rows(tmp_path):
    db = tmp_path / "synthetic.db"
    _build_db(db)

    conn_ro = G._open_ro(db)
    try:
        all_draws = G.load_lottery_draws(conn_ro, "DAILY_539")
        pre_snapshot = G.build_pre_write_snapshot(conn_ro)
    finally:
        conn_ro.close()

    target_draws = pre_snapshot["daily539_missing_target_draws"]
    rows = G.generate_rows(all_draws, target_draws, [_StubAdapter()])

    result = G.apply_rows_transactional(
        db, rows, expected_pre_count_daily539=pre_snapshot["strategy_prediction_replays_count_by_lottery"]["DAILY_539"]
    )
    assert result["inserted"] == 10
    assert result["duplicates"] == 0
    assert result["committed"] is True

    conn = sqlite3.connect(db)
    daily539_count = conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE lottery_type='DAILY_539'"
    ).fetchone()[0]
    big_lotto_count = conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE lottery_type='BIG_LOTTO'"
    ).fetchone()[0]
    power_lotto_count = conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE lottery_type='POWER_LOTTO'"
    ).fetchone()[0]
    conn.close()

    assert daily539_count == 120  # 110 existing + 10 new
    assert big_lotto_count == 1  # untouched
    assert power_lotto_count == 1  # untouched


def test_apply_rows_transactional_rolls_back_on_pre_count_drift(tmp_path):
    db = tmp_path / "synthetic.db"
    _build_db(db)

    conn_ro = G._open_ro(db)
    try:
        all_draws = G.load_lottery_draws(conn_ro, "DAILY_539")
        pre_snapshot = G.build_pre_write_snapshot(conn_ro)
    finally:
        conn_ro.close()

    target_draws = pre_snapshot["daily539_missing_target_draws"]
    rows = G.generate_rows(all_draws, target_draws, [_StubAdapter()])

    before_bytes = db.read_bytes()
    with pytest.raises(RuntimeError, match="PRE-COUNT DRIFT"):
        G.apply_rows_transactional(db, rows, expected_pre_count_daily539=99999)
    after_bytes = db.read_bytes()

    assert before_bytes == after_bytes  # rolled back, DB untouched


def test_apply_rows_transactional_rolls_back_on_duplicate(tmp_path):
    db = tmp_path / "synthetic.db"
    _build_db(db)

    conn_ro = G._open_ro(db)
    try:
        all_draws = G.load_lottery_draws(conn_ro, "DAILY_539")
        pre_snapshot = G.build_pre_write_snapshot(conn_ro)
    finally:
        conn_ro.close()

    target_draws = pre_snapshot["daily539_missing_target_draws"]
    rows = G.generate_rows(all_draws, target_draws, [_StubAdapter()])

    # First apply succeeds.
    G.apply_rows_transactional(
        db, rows, expected_pre_count_daily539=pre_snapshot["strategy_prediction_replays_count_by_lottery"]["DAILY_539"]
    )

    conn = sqlite3.connect(db)
    count_after_first = conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE lottery_type='DAILY_539'"
    ).fetchone()[0]
    conn.close()

    # Second apply of the SAME rows must not silently overwrite/duplicate; it must roll back.
    with pytest.raises(RuntimeError, match="UNEXPECTED DUPLICATES"):
        G.apply_rows_transactional(db, rows, expected_pre_count_daily539=count_after_first)

    conn = sqlite3.connect(db)
    count_after_second_attempt = conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE lottery_type='DAILY_539'"
    ).fetchone()[0]
    conn.close()
    assert count_after_second_attempt == count_after_first  # unchanged, rolled back


def test_build_adapters_returns_twelve_in_scope_strategies():
    adapters = G._build_adapters()
    strategy_ids = sorted(a.meta.strategy_id for a in adapters)
    assert len(strategy_ids) == 12
    for excluded in G.EXCLUDED_STRATEGY_IDS:
        assert excluded not in strategy_ids
    assert "daily539_f4cold" in strategy_ids
    assert "daily539_markov_cold" not in strategy_ids
    assert "acb_markov_midfreq_3bet" in strategy_ids


def test_module_disclaimer_present():
    assert "not a prediction" in G.DISCLAIMER_EN
    assert "betting edge" in G.DISCLAIMER_EN


def test_module_source_never_deletes_or_updates_existing_rows():
    source = Path(G.__file__).read_text(encoding="utf-8")
    assert 'conn.execute("DELETE' not in source
    assert "conn.execute('DELETE" not in source
    assert 'conn.execute("UPDATE' not in source
    assert "conn.execute('UPDATE" not in source


def test_run_write_invariants_pass_with_null_controlled_apply_id_existing_rows(tmp_path):
    """Regression: existing rows with controlled_apply_id IS NULL (real production
    shape) must not be miscounted as 'touched' by a NULL-unsafe `!= ?` comparison."""
    db = tmp_path / "synthetic.db"
    _build_db(db)

    orig = G._build_adapters
    G._build_adapters = lambda: [_StubAdapter()]
    try:
        result = G.run_write(db)
    finally:
        G._build_adapters = orig

    assert result["invariants_checked"]["no_existing_daily539_rows_touched"] is True
    assert result["all_invariants_pass"] is True
    assert result["classification"] == "P540B_DB_WRITE_COMPLETE_PR_OPENED_WAITING_OWNER_MERGE_AUTHORIZATION"


def test_run_write_raises_before_writing_when_manifest_inconsistent(tmp_path, monkeypatch):
    db = tmp_path / "synthetic.db"
    _build_db(db)

    def _fake_preview(_db_path):
        return {"manifest_consistent": False, "problems": ["forced test failure"], "rows": []}

    monkeypatch.setattr(G, "build_dry_run_preview", _fake_preview)
    before_bytes = db.read_bytes()
    with pytest.raises(RuntimeError, match="Manifest inconsistent"):
        G.run_write(db)
    after_bytes = db.read_bytes()
    assert before_bytes == after_bytes
