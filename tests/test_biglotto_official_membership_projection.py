"""Focused tests for the official BIG_LOTTO membership projection candidate."""
import json
import sqlite3
from datetime import date, timedelta

import pytest

from scripts.biglotto_official_membership_projection import (
    CANONICAL_VIEW,
    CREATE_IDENTITY_TABLE_SQL,
    CREATE_MANIFEST_TABLE_SQL,
    IDENTITY_TABLE,
    MANIFEST_TABLE,
    OFFICIAL_AS_OF_PERIOD,
    OFFICIAL_DATASET_SHA256,
    OFFICIAL_IDENTITIES,
    apply_official_membership_projection,
    identity_dataset_sha256,
)


RECOVERED_23 = {
    "100000003", "100000034",
    "102000043", "102000098",
    "103000033", "103000070",
    "104000003", "104000029", "104000106",
    "106000010",
    "107000086", "107000101",
    "110000073",
    "111000010", "111000030", "111000045",
    "112000007", "112000059",
    "114000023", "114000035", "114000101", "114000108",
    "115000033",
}
ADDITIONAL_FOUR = {
    "096000058",
    "096000090",
    "097000069",
    "098000072",
}


def _connection():
    connection = sqlite3.connect(":memory:")
    connection.execute(
        """CREATE TABLE draws (
            id INTEGER PRIMARY KEY,
            draw TEXT NOT NULL,
            date TEXT NOT NULL,
            lottery_type TEXT NOT NULL,
            numbers TEXT NOT NULL,
            special INTEGER NOT NULL
        )"""
    )
    return connection


def _insert_draw(connection, period, draw_date, numbers, special):
    connection.execute(
        "INSERT INTO draws (draw, date, lottery_type, numbers, special) "
        "VALUES (?, ?, 'BIG_LOTTO', ?, ?)",
        (
            str(period),
            str(draw_date),
            json.dumps(list(numbers), separators=(",", ":")),
            int(special),
        ),
    )


def _seed_all_official_rows(connection):
    for draw in OFFICIAL_IDENTITIES:
        # Raw historical rows may omit the leading zero in 096-099 periods.
        raw_period = (
            draw.period[1:]
            if draw.period.startswith(("096", "097", "098", "099"))
            else draw.period
        )
        # Exercise the legacy slash date representation through the view join.
        raw_date = draw.draw_date.replace("-", "/")
        _insert_draw(connection, raw_period, raw_date, draw.numbers, draw.special)


def _official_by_period():
    return {draw.period: draw for draw in OFFICIAL_IDENTITIES}


def _different_number_set(numbers):
    for replacement in range(1, 50):
        if replacement not in numbers:
            return tuple(sorted((replacement,) + tuple(numbers[1:])))
    raise AssertionError("could not create a distinct six-number set")


def test_official_projection_recovers_valid_rows_and_excludes_623_unmatched_candidates():
    connection = _connection()
    _seed_all_official_rows(connection)

    unmatched_candidates = {
        "120000{:03d}".format(index) for index in range(1, 624)
    }
    for period in sorted(unmatched_candidates):
        _insert_draw(connection, period, "2026-10-10", (1, 2, 3, 4, 5, 6), 7)
    assert len(unmatched_candidates) == 623
    connection.commit()

    result = apply_official_membership_projection(connection)
    actual_periods = {
        str(row[0]).zfill(9)
        for row in connection.execute(
            "SELECT draw FROM {}".format(CANONICAL_VIEW)
        ).fetchall()
    }
    expected_periods = {draw.period for draw in OFFICIAL_IDENTITIES}

    assert actual_periods == expected_periods
    assert actual_periods.isdisjoint(unmatched_candidates)
    assert identity_dataset_sha256() == OFFICIAL_DATASET_SHA256
    assert result.dataset_sha256 == OFFICIAL_DATASET_SHA256
    assert result.identity_rows_written == len(OFFICIAL_IDENTITIES)
    assert result.view_row_count == len(expected_periods)
    assert connection.in_transaction is False

    manifest = connection.execute(
        "SELECT source_endpoint, query_scope, as_of_period, official_record_count, normalized_sha256 "
        "FROM {}".format(MANIFEST_TABLE)
    ).fetchone()
    assert manifest[2] == OFFICIAL_AS_OF_PERIOD
    assert manifest[3] == len(OFFICIAL_IDENTITIES)
    assert manifest[4] == OFFICIAL_DATASET_SHA256

    official = _official_by_period()
    recovered = RECOVERED_23 | ADDITIONAL_FOUR
    assert recovered <= actual_periods
    assert all(max(official[period].numbers) <= 25 for period in recovered)

    target_080_095 = {
        "115000{:03d}".format(number) for number in range(80, 96)
    }
    independently_loaded_target = {
        draw.period
        for draw in OFFICIAL_IDENTITIES
        if 115000080 <= int(draw.period) <= 115000095
    }
    assert independently_loaded_target == target_080_095
    assert target_080_095 <= actual_periods

    connection.close()


def test_projection_rejects_unmatched_periods_and_date_number_or_special_conflicts():
    connection = _connection()
    official = _official_by_period()

    date_conflict = official["115000095"]
    wrong_date = (
        date.fromisoformat(date_conflict.draw_date) + timedelta(days=1)
    ).isoformat()
    _insert_draw(
        connection,
        date_conflict.period,
        wrong_date,
        date_conflict.numbers,
        date_conflict.special,
    )

    numbers_conflict = official["115000094"]
    _insert_draw(
        connection,
        numbers_conflict.period,
        numbers_conflict.draw_date,
        _different_number_set(numbers_conflict.numbers),
        numbers_conflict.special,
    )

    special_conflict = official["115000093"]
    wrong_special = next(
        number
        for number in range(1, 50)
        if number not in special_conflict.numbers
        and number != special_conflict.special
    )
    _insert_draw(
        connection,
        special_conflict.period,
        special_conflict.draw_date,
        special_conflict.numbers,
        wrong_special,
    )

    _insert_draw(
        connection,
        "120000001",
        official["115000095"].draw_date,
        official["115000095"].numbers,
        official["115000095"].special,
    )
    connection.commit()

    apply_official_membership_projection(connection)
    rows = connection.execute(
        "SELECT draw FROM {}".format(CANONICAL_VIEW)
    ).fetchall()
    assert rows == []
    connection.close()


def test_view_fails_closed_when_manifest_digest_is_changed():
    connection = _connection()
    official = OFFICIAL_IDENTITIES[-1]
    _insert_draw(
        connection,
        official.period,
        official.draw_date,
        official.numbers,
        official.special,
    )
    connection.commit()

    apply_official_membership_projection(connection)
    assert connection.execute(
        "SELECT COUNT(*) FROM {}".format(CANONICAL_VIEW)
    ).fetchone()[0] == 1

    connection.execute(
        "UPDATE {} SET normalized_sha256 = 'tampered'".format(MANIFEST_TABLE)
    )
    assert connection.execute(
        "SELECT COUNT(*) FROM {}".format(CANONICAL_VIEW)
    ).fetchone()[0] == 0
    connection.close()


def test_failed_identity_update_rolls_back_manifest_and_existing_view():
    connection = _connection()
    _insert_draw(connection, "old-sentinel", "2026-10-10", (1, 2, 3, 4, 5, 6), 7)
    connection.execute(CREATE_IDENTITY_TABLE_SQL)
    connection.execute(CREATE_MANIFEST_TABLE_SQL)
    connection.execute(
        "INSERT INTO {} "
        "(period, draw_date, numbers_json, numbers_csv, special, dataset_sha256) "
        "VALUES (?, ?, ?, ?, ?, ?)".format(IDENTITY_TABLE),
        ("000000001", "2000-01-01", "[1,2,3,4,5,6]", "1,2,3,4,5,6", 7, "old"),
    )
    connection.execute(
        "INSERT INTO {} "
        "(singleton, source_page, source_endpoint, query_scope, as_of_period, "
        "official_record_count, normalized_sha256) "
        "VALUES (1, 'old-page', 'old-endpoint', 'old-query', '000000001', 1, 'old')"
        .format(MANIFEST_TABLE)
    )
    connection.execute(
        "CREATE VIEW {} AS SELECT * FROM draws WHERE draw = 'old-sentinel'".format(
            CANONICAL_VIEW
        )
    )
    connection.execute(
        """CREATE TRIGGER force_identity_insert_failure
        BEFORE INSERT ON biglotto_official_draw_identity
        BEGIN
            SELECT RAISE(ABORT, 'synthetic identity insert failure');
        END"""
    )
    connection.commit()

    old_view_sql = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type='view' AND name=?",
        (CANONICAL_VIEW,),
    ).fetchone()[0]
    old_identity_rows = connection.execute(
        "SELECT period, draw_date, numbers_json, numbers_csv, special, dataset_sha256 "
        "FROM {} ORDER BY period".format(IDENTITY_TABLE)
    ).fetchall()
    old_manifest_rows = connection.execute(
        "SELECT singleton, source_page, source_endpoint, query_scope, as_of_period, "
        "official_record_count, normalized_sha256 FROM {}".format(MANIFEST_TABLE)
    ).fetchall()

    with pytest.raises(sqlite3.IntegrityError, match="synthetic identity insert failure"):
        apply_official_membership_projection(connection)

    assert connection.in_transaction is False
    assert connection.execute(
        "SELECT sql FROM sqlite_master WHERE type='view' AND name=?",
        (CANONICAL_VIEW,),
    ).fetchone()[0] == old_view_sql
    assert connection.execute(
        "SELECT draw FROM {}".format(CANONICAL_VIEW)
    ).fetchall() == [("old-sentinel",)]
    assert connection.execute(
        "SELECT period, draw_date, numbers_json, numbers_csv, special, dataset_sha256 "
        "FROM {} ORDER BY period".format(IDENTITY_TABLE)
    ).fetchall() == old_identity_rows
    assert connection.execute(
        "SELECT singleton, source_page, source_endpoint, query_scope, as_of_period, "
        "official_record_count, normalized_sha256 FROM {}".format(MANIFEST_TABLE)
    ).fetchall() == old_manifest_rows
    assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"

    connection.close()
