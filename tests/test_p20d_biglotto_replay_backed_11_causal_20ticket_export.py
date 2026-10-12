"""Hermetic contract tests for the P20D BIG_LOTTO replay-backed export.

These tests build a small synthetic SQLite fixture matching the production
schema and view (never the real canonical DB), so they run identically in
CI and locally with no external data dependency.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from analysis.p20d_biglotto_replay_backed_11_causal_20ticket_export import (
    NONCAUSAL_HISTORY_CUTOFF,
    SOURCE_DRAW_REFERENCE_UNAVAILABLE,
    ClosedGroup,
    PortfolioGroup,
    build_census,
    build_outcomes,
    canonical_json_bytes,
    canonical_view_present,
    classify_group,
    database_identity,
    load_canonical_draws,
    load_raw_rows,
    open_database_readonly,
    run_export,
    write_export,
)

LOTTERY_TYPE = "BIG_LOTTO"

SCHEMA_SQL = """
CREATE TABLE draws (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    draw TEXT NOT NULL,
    date TEXT NOT NULL,
    lottery_type TEXT NOT NULL,
    numbers TEXT NOT NULL,
    special INTEGER DEFAULT 0,
    UNIQUE(draw, lottery_type)
);

CREATE VIEW draws_big_lotto_canonical_main AS
SELECT d.* FROM draws d
WHERE d.lottery_type = 'BIG_LOTTO' AND d.draw NOT LIKE 'NONCANON%';

CREATE TABLE strategy_prediction_replays (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lottery_type TEXT NOT NULL,
    target_draw TEXT NOT NULL,
    target_date TEXT,
    strategy_id TEXT NOT NULL,
    strategy_name TEXT NOT NULL,
    strategy_version TEXT NOT NULL DEFAULT 'v0.1',
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
    generated_at TEXT
);
"""


def _make_db(path: Path, *, with_bet_index: bool = False) -> None:
    connection = sqlite3.connect(str(path))
    try:
        connection.executescript(SCHEMA_SQL)
        if with_bet_index:
            connection.execute(
                "ALTER TABLE strategy_prediction_replays ADD COLUMN bet_index INTEGER"
            )
        connection.commit()
    finally:
        connection.close()


def _insert_draw(
    path: Path, draw: str, date: str, numbers: list[int], special: int
) -> None:
    connection = sqlite3.connect(str(path))
    try:
        connection.execute(
            "INSERT INTO draws (draw, date, lottery_type, numbers, special) "
            "VALUES (?, ?, ?, ?, ?)",
            (draw, date, LOTTERY_TYPE, json.dumps(numbers), special),
        )
        connection.commit()
    finally:
        connection.close()


def _insert_replay(
    path: Path,
    *,
    target_draw: str,
    strategy_id: str,
    strategy_name: str = "Test Strategy",
    strategy_version: str = "v0.1-test",
    history_cutoff_draw: str | None,
    predicted_numbers: list[int],
    bet_index: int | None = None,
) -> None:
    connection = sqlite3.connect(str(path))
    try:
        columns = [
            "lottery_type",
            "target_draw",
            "strategy_id",
            "strategy_name",
            "strategy_version",
            "history_cutoff_draw",
            "replay_status",
            "predicted_numbers",
        ]
        values: list[object] = [
            LOTTERY_TYPE,
            target_draw,
            strategy_id,
            strategy_name,
            strategy_version,
            history_cutoff_draw,
            "PREDICTED",
            json.dumps(predicted_numbers),
        ]
        if bet_index is not None:
            columns.append("bet_index")
            values.append(bet_index)
        placeholders = ",".join("?" for _ in columns)
        connection.execute(
            f"INSERT INTO strategy_prediction_replays ({', '.join(columns)}) "
            f"VALUES ({placeholders})",
            values,
        )
        connection.commit()
    finally:
        connection.close()


@pytest.fixture
def basic_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "fixture.db"
    _make_db(db_path)
    _insert_draw(db_path, "100000001", "2020/01/01", [1, 2, 3, 4, 5, 6], 7)
    _insert_draw(db_path, "100000002", "2020/01/08", [10, 20, 30, 40, 41, 42], 8)
    _insert_draw(db_path, "NONCANON01", "2020/01/15", [1, 2, 3, 4, 5, 6], 7)
    return db_path


def test_canonical_view_present(basic_db: Path) -> None:
    connection = open_database_readonly(basic_db)
    try:
        assert canonical_view_present(connection)
    finally:
        connection.close()


def test_load_raw_rows_preserves_native_order_and_derives_bet_index(
    basic_db: Path,
) -> None:
    _insert_replay(
        basic_db,
        target_draw="100000002",
        strategy_id="s_multi",
        history_cutoff_draw="100000001",
        predicted_numbers=[1, 2, 3, 4, 5, 6],
    )
    _insert_replay(
        basic_db,
        target_draw="100000002",
        strategy_id="s_multi",
        history_cutoff_draw="100000001",
        predicted_numbers=[7, 8, 9, 10, 11, 12],
    )
    connection = open_database_readonly(basic_db)
    try:
        rows = load_raw_rows(connection, ["s_multi"])
    finally:
        connection.close()
    assert [row.bet_index for row in rows] == [0, 1]
    assert all(row.bet_index_source == "derived_native_order" for row in rows)
    assert rows[0].predicted_numbers == [1, 2, 3, 4, 5, 6]
    assert rows[1].predicted_numbers == [7, 8, 9, 10, 11, 12]


def test_load_raw_rows_prefers_stored_bet_index(tmp_path: Path) -> None:
    db_path = tmp_path / "stored.db"
    _make_db(db_path, with_bet_index=True)
    _insert_draw(db_path, "100000001", "2020/01/01", [1, 2, 3, 4, 5, 6], 7)
    _insert_draw(db_path, "100000002", "2020/01/08", [10, 20, 30, 40, 41, 42], 8)
    _insert_replay(
        db_path,
        target_draw="100000002",
        strategy_id="s_stored",
        history_cutoff_draw="100000001",
        predicted_numbers=[1, 2, 3, 4, 5, 6],
        bet_index=5,
    )
    connection = open_database_readonly(db_path)
    try:
        rows = load_raw_rows(connection, ["s_stored"])
    finally:
        connection.close()
    assert rows[0].bet_index == 5
    assert rows[0].bet_index_source == "stored_column"


def test_duplicate_raw_rows_are_preserved_in_census(basic_db: Path) -> None:
    for _ in range(2):
        _insert_replay(
            basic_db,
            target_draw="100000002",
            strategy_id="s_dup",
            history_cutoff_draw="100000001",
            predicted_numbers=[1, 2, 3, 4, 5, 6],
        )
    connection = open_database_readonly(basic_db)
    try:
        rows = load_raw_rows(connection, ["s_dup"])
        census = build_census(rows)
    finally:
        connection.close()
    assert len(census) == 2
    assert census[0]["predicted_numbers"] == census[1]["predicted_numbers"]
    assert census[0]["id"] != census[1]["id"]


def test_classify_group_resolved_causal_produces_20_ticket_portfolio(
    basic_db: Path,
) -> None:
    _insert_replay(
        basic_db,
        target_draw="100000002",
        strategy_id="s_ok",
        history_cutoff_draw="100000001",
        predicted_numbers=[1, 2, 3, 4, 5, 6],
    )
    connection = open_database_readonly(basic_db)
    try:
        rows = load_raw_rows(connection, ["s_ok"])
        canonical_draws = load_canonical_draws(connection)
    finally:
        connection.close()
    outcome = classify_group("s_ok", "100000002", rows, canonical_draws)
    assert isinstance(outcome, PortfolioGroup)
    assert len(outcome.tickets) == 20
    assert len(set(outcome.tickets)) == 20
    assert outcome.replicate_id == 0
    assert outcome.replicate_observed is False


def test_classify_group_unresolved_target_is_closed(basic_db: Path) -> None:
    _insert_replay(
        basic_db,
        target_draw="NONCANON01",
        strategy_id="s_unresolved",
        history_cutoff_draw="100000001",
        predicted_numbers=[1, 2, 3, 4, 5, 6],
    )
    connection = open_database_readonly(basic_db)
    try:
        rows = load_raw_rows(connection, ["s_unresolved"])
        canonical_draws = load_canonical_draws(connection)
    finally:
        connection.close()
    outcome = classify_group("s_unresolved", "NONCANON01", rows, canonical_draws)
    assert isinstance(outcome, ClosedGroup)
    assert outcome.closure_reason == SOURCE_DRAW_REFERENCE_UNAVAILABLE


def test_classify_group_unresolved_cutoff_is_closed(basic_db: Path) -> None:
    _insert_replay(
        basic_db,
        target_draw="100000002",
        strategy_id="s_bad_cutoff",
        history_cutoff_draw="NONCANON01",
        predicted_numbers=[1, 2, 3, 4, 5, 6],
    )
    connection = open_database_readonly(basic_db)
    try:
        rows = load_raw_rows(connection, ["s_bad_cutoff"])
        canonical_draws = load_canonical_draws(connection)
    finally:
        connection.close()
    outcome = classify_group("s_bad_cutoff", "100000002", rows, canonical_draws)
    assert isinstance(outcome, ClosedGroup)
    assert outcome.closure_reason == SOURCE_DRAW_REFERENCE_UNAVAILABLE


def test_classify_group_noncausal_cutoff_is_closed(basic_db: Path) -> None:
    _insert_replay(
        basic_db,
        target_draw="100000001",
        strategy_id="s_noncausal",
        history_cutoff_draw="100000002",
        predicted_numbers=[1, 2, 3, 4, 5, 6],
    )
    connection = open_database_readonly(basic_db)
    try:
        rows = load_raw_rows(connection, ["s_noncausal"])
        canonical_draws = load_canonical_draws(connection)
    finally:
        connection.close()
    outcome = classify_group("s_noncausal", "100000001", rows, canonical_draws)
    assert isinstance(outcome, ClosedGroup)
    assert outcome.closure_reason == NONCAUSAL_HISTORY_CUTOFF


def test_multi_bet_group_still_yields_one_20_ticket_portfolio(basic_db: Path) -> None:
    for numbers in (
        [1, 2, 3, 4, 5, 6],
        [7, 8, 9, 10, 11, 12],
        [13, 14, 15, 16, 17, 18],
    ):
        _insert_replay(
            basic_db,
            target_draw="100000002",
            strategy_id="s_3bet",
            history_cutoff_draw="100000001",
            predicted_numbers=numbers,
        )
    connection = open_database_readonly(basic_db)
    try:
        rows = load_raw_rows(connection, ["s_3bet"])
        canonical_draws = load_canonical_draws(connection)
    finally:
        connection.close()
    outcome = classify_group("s_3bet", "100000002", rows, canonical_draws)
    assert isinstance(outcome, PortfolioGroup)
    assert len(outcome.tickets) == 20
    native = {(1, 2, 3, 4, 5, 6), (7, 8, 9, 10, 11, 12), (13, 14, 15, 16, 17, 18)}
    assert native.issubset(set(outcome.tickets))
    assert len(outcome.raw_row_ids) == 3


def test_outcomes_are_computed_after_and_independent_of_construction(
    basic_db: Path,
) -> None:
    _insert_replay(
        basic_db,
        target_draw="100000002",
        strategy_id="s_score",
        history_cutoff_draw="100000001",
        predicted_numbers=[10, 20, 30, 40, 7, 8],
    )
    connection = open_database_readonly(basic_db)
    try:
        rows = load_raw_rows(connection, ["s_score"])
        canonical_draws = load_canonical_draws(connection)
    finally:
        connection.close()
    outcome = classify_group("s_score", "100000002", rows, canonical_draws)
    assert isinstance(outcome, PortfolioGroup)
    portfolio_before = outcome.tickets
    outcomes = build_outcomes([outcome], canonical_draws)
    assert outcome.tickets == portfolio_before  # construction untouched by scoring
    assert len(outcomes) == 1
    record = outcomes[0]
    assert record["actual_numbers"] == [10, 20, 30, 40, 41, 42]
    native_ticket_hits = record["ticket_hit_counts"][
        outcome.tickets.index((7, 8, 10, 20, 30, 40))
    ]
    assert native_ticket_hits == 4
    assert record["max_hit_count"] >= 4
    assert record["m4plus"] == 1


def test_construction_is_deterministic_across_repeated_runs(basic_db: Path) -> None:
    _insert_replay(
        basic_db,
        target_draw="100000002",
        strategy_id="s_det",
        history_cutoff_draw="100000001",
        predicted_numbers=[2, 4, 6, 8, 10, 12],
    )
    connection = open_database_readonly(basic_db)
    try:
        rows = load_raw_rows(connection, ["s_det"])
        canonical_draws = load_canonical_draws(connection)
    finally:
        connection.close()
    first = classify_group("s_det", "100000002", rows, canonical_draws)
    second = classify_group("s_det", "100000002", rows, canonical_draws)
    assert isinstance(first, PortfolioGroup) and isinstance(second, PortfolioGroup)
    assert first.tickets == second.tickets
    assert first.metadata["portfolio_sha256"] == second.metadata["portfolio_sha256"]


def test_database_identity_unchanged_by_read_only_export(basic_db: Path) -> None:
    before = database_identity(basic_db)
    open_database_readonly(basic_db).close()
    after = database_identity(basic_db)
    assert before == after


def test_run_export_end_to_end_manifest_and_gzip_determinism(
    tmp_path: Path, basic_db: Path
) -> None:
    _insert_replay(
        basic_db,
        target_draw="100000002",
        strategy_id="strategy_a",
        history_cutoff_draw="100000001",
        predicted_numbers=[1, 2, 3, 4, 5, 6],
    )
    _insert_replay(
        basic_db,
        target_draw="NONCANON01",
        strategy_id="strategy_a",
        history_cutoff_draw="100000001",
        predicted_numbers=[1, 2, 3, 4, 5, 6],
    )

    result = run_export(basic_db, strategy_ids=["strategy_a"])
    assert result.manifest["observed_census_row_count"] == 2
    assert result.manifest["portfolio_group_count"] == 1
    assert result.manifest["closed_group_count"] == 1

    out1 = tmp_path / "run1"
    out2 = tmp_path / "run2"
    write_export(result, out1)
    result_again = run_export(basic_db, strategy_ids=["strategy_a"])
    write_export(result_again, out2)

    for name in ("census", "portfolios", "closed_rows", "outcomes", "manifest_data"):
        filename = "manifest.json" if name == "manifest_data" else f"{name}.json.gz"
        first_bytes = (out1 / filename).read_bytes()
        second_bytes = (out2 / filename).read_bytes()
        if name == "manifest_data":
            first_payload = json.loads(first_bytes)
            second_payload = json.loads(second_bytes)
            assert first_payload == second_payload
        else:
            assert first_bytes == second_bytes


def test_expected_strategy_ids_are_frozen_and_sorted() -> None:
    from analysis.p20d_biglotto_replay_backed_11_causal_20ticket_export import (
        EXPECTED_STRATEGY_IDS,
    )

    assert len(EXPECTED_STRATEGY_IDS) == 11
    assert len(set(EXPECTED_STRATEGY_IDS)) == 11
    assert list(EXPECTED_STRATEGY_IDS) == sorted(EXPECTED_STRATEGY_IDS)


def test_canonical_json_bytes_is_order_independent() -> None:
    left = canonical_json_bytes({"b": 1, "a": 2})
    right = canonical_json_bytes({"a": 2, "b": 1})
    assert left == right
