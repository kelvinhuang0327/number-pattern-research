from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

from scripts import biglotto_16_draw_staged_import as staged
from scripts import biglotto_official_membership_projection as membership


def _records():
    first_date = date(2026, 8, 18)
    records = []
    for index, draw in enumerate(staged.TARGET_DRAW_IDS):
        records.append(
            staged.DrawRecord(
                draw=draw,
                date=(first_date + timedelta(days=index * 3)).isoformat(),
                numbers=(1, 4, 9, 16, 24, 30 + index),
                special=49,
                source_sha256=hashlib.sha256(draw.encode("ascii")).hexdigest(),
            )
        )
    return tuple(records)


def _database():
    connection = sqlite3.connect(":memory:")
    connection.execute(
        """
        CREATE TABLE draws (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            draw TEXT NOT NULL,
            date TEXT NOT NULL,
            lottery_type TEXT NOT NULL,
            numbers TEXT NOT NULL,
            special INTEGER NOT NULL DEFAULT 0,
            UNIQUE (lottery_type, draw)
        )
        """
    )
    connection.execute(
        "CREATE TABLE strategy_prediction_replays (id INTEGER PRIMARY KEY, marker TEXT)"
    )
    connection.execute(
        "CREATE TABLE prediction_runs (id INTEGER PRIMARY KEY, marker TEXT)"
    )
    connection.execute(
        "INSERT INTO strategy_prediction_replays(marker) VALUES ('replay-sentinel')"
    )
    connection.execute(
        "INSERT INTO prediction_runs(marker) VALUES ('prediction-sentinel')"
    )
    connection.commit()
    return connection


def _official_records():
    return tuple(
        staged.DrawRecord(
            draw=official.period,
            date=official.draw_date,
            numbers=official.numbers,
            special=official.special,
            source_sha256=hashlib.sha256(
                ("synthetic-official-response:" + official.period).encode("ascii")
            ).hexdigest(),
        )
        for official in membership.OFFICIAL_IDENTITIES
        if official.period in staged.TARGET_DRAW_IDS
    )


def _synthetic_atomic_database(path: Path):
    connection = sqlite3.connect(str(path))
    connection.execute(
        """
        CREATE TABLE draws (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            draw TEXT NOT NULL,
            date TEXT NOT NULL,
            lottery_type TEXT NOT NULL,
            numbers TEXT NOT NULL,
            special INTEGER NOT NULL DEFAULT 0,
            UNIQUE (lottery_type, draw)
        )
        """
    )
    connection.execute(
        "CREATE TABLE strategy_prediction_replays (id INTEGER PRIMARY KEY, marker TEXT)"
    )
    connection.execute(
        "CREATE TABLE prediction_runs (id INTEGER PRIMARY KEY, marker TEXT)"
    )
    connection.execute(
        "INSERT INTO strategy_prediction_replays(marker) VALUES ('replay-sentinel')"
    )
    connection.execute(
        "INSERT INTO prediction_runs(marker) VALUES ('prediction-sentinel')"
    )

    prior_official = membership.OFFICIAL_IDENTITIES[:-len(staged.TARGET_DRAW_IDS)]
    assert len(prior_official) == 2161
    assert sum(max(draw.numbers) <= 25 for draw in prior_official) == 27
    for draw in prior_official:
        connection.execute(
            "INSERT INTO draws(draw, date, lottery_type, numbers, special) "
            "VALUES (?, ?, 'BIG_LOTTO', ?, ?)",
            (
                draw.period,
                draw.draw_date.replace("-", "/"),
                json.dumps(list(draw.numbers), separators=(",", ":")),
                draw.special,
            ),
        )

    for index in range(998):
        connection.execute(
            "INSERT INTO draws(draw, date, lottery_type, numbers, special) "
            "VALUES (?, '2026/10/10', 'BIG_LOTTO', '[1,2,3,4,5,49]', 7)",
            ("{:09d}".format(120000001 + index),),
        )
    connection.execute(
        """
        CREATE VIEW draws_big_lotto_canonical_main AS
        SELECT d.*
        FROM draws AS d
        WHERE d.lottery_type = 'BIG_LOTTO'
          AND CAST(d.draw AS INTEGER) < 115000080
          AND (
              SELECT MAX(CAST(j.value AS INTEGER))
              FROM json_each(d.numbers) AS j
          ) > 25
        """
    )
    connection.commit()
    return connection


def _atomic_manifest(path: Path, database_identity, records=None):
    selected_records = _official_records() if records is None else tuple(records)
    database_check = {
        "path": database_identity["path"],
        "read_only": True,
        "identity_before": database_identity,
        "identity_after": database_identity,
        "db_copy": "NONE",
        "db_writes": "NONE",
        "target_presence": [
            {"draw": draw, "status": "MISSING"}
            for draw in staged.TARGET_DRAW_IDS
        ],
    }
    manifest = staged.build_manifest(
        selected_records,
        "2026-10-13T02:00:00+00:00",
        database_check,
    )
    return staged.write_manifest_exclusive(path, manifest), manifest


def _apply_atomic(connection, manifest_path, manifest_sha256, database_identity, **overrides):
    arguments = {
        "approved_manifest_sha256": manifest_sha256,
        "approved_official_dataset_sha256": membership.OFFICIAL_DATASET_SHA256,
        "expected_db_identity": database_identity,
        "expected_canonical_periods": tuple(
            draw.period for draw in membership.OFFICIAL_IDENTITIES
        ),
    }
    arguments.update(overrides)
    return staged.apply_staged_import_atomically(
        connection, manifest_path, **arguments
    )


def _atomic_snapshot(connection):
    objects = {
        name: kind
        for name, kind in connection.execute(
            "SELECT name, type FROM sqlite_master WHERE type IN ('table', 'view')"
        ).fetchall()
    }
    snapshot = {
        "draws": connection.execute("SELECT * FROM draws ORDER BY id").fetchall(),
        "strategy_prediction_replays": _other_table_snapshot(connection)[
            "strategy_prediction_replays"
        ],
        "prediction_runs": _other_table_snapshot(connection)["prediction_runs"],
        "view_sql": connection.execute(
            "SELECT sql FROM sqlite_master WHERE type='view' "
            "AND name='draws_big_lotto_canonical_main'"
        ).fetchone()[0],
    }
    for name, order in (
        (membership.IDENTITY_TABLE, "period"),
        (membership.MANIFEST_TABLE, "singleton"),
    ):
        snapshot[name] = (
            connection.execute("SELECT * FROM {} ORDER BY {}".format(name, order)).fetchall()
            if objects.get(name) == "table"
            else None
        )
    return snapshot


def _transaction_statements(trace):
    return [
        statement.upper()
        for statement in trace
        if statement.strip().upper().startswith(("BEGIN", "COMMIT", "ROLLBACK"))
    ]


def _prepared_atomic_apply(tmp_path, records=None):
    database_path = tmp_path / "synthetic.sqlite"
    connection = _synthetic_atomic_database(database_path)
    database_identity = staged._database_identity(database_path.resolve())
    manifest_path = tmp_path / "approved-stage.json"
    manifest_sha256, manifest = _atomic_manifest(
        manifest_path, database_identity, records
    )
    return connection, database_path, database_identity, manifest_path, manifest_sha256, manifest


def _other_table_snapshot(connection):
    return {
        "strategy_prediction_replays": connection.execute(
            "SELECT * FROM strategy_prediction_replays ORDER BY id"
        ).fetchall(),
        "prediction_runs": connection.execute(
            "SELECT * FROM prediction_runs ORDER BY id"
        ).fetchall(),
    }


def _payload(period="115000080"):
    return {
        "rtCode": 0,
        "rtMsg": None,
        "content": {
            "totalSize": 1,
            "lotto649Res": [
                {
                    "period": int(period),
                    "lotteryDate": "2026-08-18T00:00:00",
                    "drawNumberSize": [1, 14, 25, 27, 29, 43, 2],
                    "drawNumberAppear": [43, 25, 29, 27, 1, 14, 2],
                }
            ],
        },
    }


def test_official_response_normalizes_main_numbers_and_hashes_source():
    raw = json.dumps(_payload(), separators=(",", ":")).encode("utf-8")

    record = staged.parse_official_response("115000080", raw)

    assert record.draw == "115000080"
    assert record.date == "2026-08-18"
    assert record.numbers == (1, 14, 25, 27, 29, 43)
    assert record.special == 2
    assert record.source_sha256 == hashlib.sha256(raw).hexdigest()


def test_official_lookup_rejects_period_mismatch_and_duplicate_json_keys():
    raw = json.dumps(_payload("115000081")).encode("utf-8")
    with pytest.raises(staged.StagingError, match="period mismatch"):
        staged.parse_official_response("115000080", raw)

    duplicated = (
        b'{"rtCode":0,"content":{"totalSize":1,"totalSize":1,'
        b'"lotto649Res":[]}}'
    )
    with pytest.raises(staged.DuplicateJSONKeyError, match="duplicate JSON key"):
        staged.parse_official_response("115000080", duplicated)


def test_fetch_draw_uses_the_requested_period_parameter(monkeypatch):
    raw = json.dumps(_payload(), separators=(",", ":")).encode("utf-8")
    requests = []

    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return raw

    def fake_urlopen(request, timeout):
        requests.append((request, timeout))
        return Response()

    monkeypatch.setattr(staged, "urlopen", fake_urlopen)
    record = staged.fetch_official_draw("115000080", timeout_seconds=7)

    assert record.draw == "115000080"
    assert len(requests) == 1
    request, timeout = requests[0]
    assert timeout == 7
    assert parse_qs(urlparse(request.full_url).query) == {
        "period": ["115000080"],
        "pageNum": ["1"],
        "pageSize": ["200"],
    }


def test_batch_validation_rejects_duplicates_and_unannounced_periods():
    records = _records()
    with pytest.raises(staged.StagingError, match="duplicate draw period"):
        staged.validate_records(records[:-1] + (records[0],))

    unexpected = replace(records[-1], draw="115000096")
    with pytest.raises(staged.StagingError, match="outside the authorized"):
        staged.validate_records(records[:-1] + (unexpected,))


@pytest.mark.parametrize(
    ("numbers", "special"),
    [
        ((0, 4, 9, 16, 24, 30), 49),
        ((1, 4, 9, 16, 24, 24), 49),
        ((1, 4, 9, 16, 24, 30), 30),
    ],
)
def test_record_validation_rejects_illegal_numbers(numbers, special):
    records = list(_records())
    records[0] = replace(records[0], numbers=numbers, special=special)

    with pytest.raises(staged.StagingError):
        staged.validate_records(records)


def test_view_risk_reports_all_sixteen_and_flags_max_at_or_below_25():
    records = list(_records())
    records[0] = replace(records[0], numbers=(1, 4, 9, 16, 20, 25))

    report = staged.view_risk_report(records)

    assert report["target_range"] == "115000080-115000095"
    assert len(report["per_draw"]) == 16
    assert report["at_risk_draw_ids"] == ["115000080"]
    assert report["per_draw"][0]["max_main_number"] == 25
    assert report["per_draw"][0]["included_by_max_gt_25"] is False


def test_first_batch_succeeds_reapply_is_idempotent_and_other_tables_stay_same():
    connection = _database()
    other_tables_before = _other_table_snapshot(connection)

    first = staged.apply_batch(connection, _records())
    second = staged.apply_batch(connection, _records())

    assert first["inserted_count"] == 16
    assert first["identical_existing_count"] == 0
    assert second["inserted_count"] == 0
    assert second["identical_existing_count"] == 16
    assert connection.execute(
        "SELECT COUNT(*) FROM draws WHERE lottery_type='BIG_LOTTO'"
    ).fetchone()[0] == 16
    assert _other_table_snapshot(connection) == other_tables_before
    connection.close()


def test_different_existing_content_rejects_the_whole_batch():
    connection = _database()
    first = _records()[0]
    connection.execute(
        "INSERT INTO draws(draw,date,lottery_type,numbers,special) VALUES(?,?,?,?,?)",
        (
            first.draw,
            first.date,
            staged.LOTTERY_TYPE,
            "[1,4,9,16,24,31]",
            first.special,
        ),
    )
    connection.commit()
    before_draws = connection.execute("SELECT * FROM draws ORDER BY id").fetchall()
    other_tables_before = _other_table_snapshot(connection)

    with pytest.raises(staged.DrawConflictError, match="conflicts"):
        staged.apply_batch(connection, _records())

    assert connection.execute("SELECT * FROM draws ORDER BY id").fetchall() == before_draws
    assert _other_table_snapshot(connection) == other_tables_before
    connection.close()


def test_eighth_insert_failure_rolls_back_all_sixteen_and_leaves_other_tables():
    connection = _database()
    connection.execute(
        """
        CREATE TRIGGER fail_on_eighth
        BEFORE INSERT ON draws
        WHEN NEW.draw = '115000087'
        BEGIN
            SELECT RAISE(ABORT, 'deliberate eighth-row failure');
        END
        """
    )
    other_tables_before = _other_table_snapshot(connection)

    with pytest.raises(sqlite3.IntegrityError, match="deliberate eighth-row failure"):
        staged.apply_batch(connection, _records())

    assert connection.execute(
        "SELECT COUNT(*) FROM draws WHERE lottery_type='BIG_LOTTO'"
    ).fetchone()[0] == 0
    assert _other_table_snapshot(connection) == other_tables_before
    connection.close()


def test_manifest_content_digest_and_scope_are_verified(tmp_path):
    database_check = {
        "read_only": True,
        "db_copy": "NONE",
        "db_writes": "NONE",
        "target_presence": [
            {"draw": draw, "status": "MISSING"} for draw in staged.TARGET_DRAW_IDS
        ],
    }
    manifest = staged.build_manifest(
        _records(), "2026-10-13T02:00:00+00:00", database_check
    )
    manifest_path = tmp_path / "stage.json"
    manifest_path.write_text(
        json.dumps(manifest, sort_keys=True, ensure_ascii=False), encoding="utf-8"
    )

    assert staged.records_from_manifest(manifest_path) == _records()
    tampered = json.loads(manifest_path.read_text(encoding="utf-8"))
    tampered["records"][0]["special"] = 48
    manifest_path.write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(staged.StagingError, match="digest mismatch"):
        staged.records_from_manifest(manifest_path)


def test_atomic_projection_and_staged_import_commit_once_and_reapply_idempotently(
    tmp_path,
):
    connection, database_path, database_identity, manifest_path, manifest_sha, _ = (
        _prepared_atomic_apply(tmp_path)
    )
    assert connection.execute(
        "SELECT COUNT(*) FROM draws_big_lotto_canonical_main"
    ).fetchone()[0] == 2134
    other_tables_before = _other_table_snapshot(connection)
    trace = []
    connection.set_trace_callback(trace.append)

    first = _apply_atomic(
        connection, manifest_path, manifest_sha, database_identity
    )

    assert _transaction_statements(trace) == ["BEGIN IMMEDIATE", "COMMIT"]
    assert first["official_record_count"] == 2177
    assert first["identity_rows_written"] == 2177
    assert first["official_dataset_sha256"] == membership.OFFICIAL_DATASET_SHA256
    assert first["canonical_count_before_staged_rows"] == 2161
    assert first["inserted_count"] == 16
    assert first["identical_existing_count"] == 0
    assert first["canonical_period_count"] == 2177
    assert len(first["canonical_periods"]) == len(set(first["canonical_periods"]))
    assert first["manifest_file_sha256"] == manifest_sha
    assert connection.execute(
        "SELECT COUNT(*) FROM {}".format(membership.IDENTITY_TABLE)
    ).fetchone()[0] == 2177
    assert connection.execute(
        "SELECT official_record_count, normalized_sha256 FROM {}".format(
            membership.MANIFEST_TABLE
        )
    ).fetchone() == (2177, membership.OFFICIAL_DATASET_SHA256)

    canonical_periods = {
        str(row[0]).zfill(9)
        for row in connection.execute(
            "SELECT draw FROM draws_big_lotto_canonical_main"
        ).fetchall()
    }
    recovered = {
        draw.period
        for draw in membership.OFFICIAL_IDENTITIES[:-16]
        if max(draw.numbers) <= 25
    }
    assert len(recovered) == 27
    assert recovered <= canonical_periods
    unmatched_periods = {
        "{:09d}".format(120000001 + index) for index in range(998)
    }
    assert connection.execute(
        "SELECT COUNT(*) FROM draws WHERE draw BETWEEN '120000001' AND '120000998'"
    ).fetchone()[0] == 998
    assert canonical_periods.isdisjoint(unmatched_periods)
    assert _other_table_snapshot(connection) == other_tables_before
    after_first = _atomic_snapshot(connection)

    trace.clear()
    current_database_identity = staged._database_identity(database_path.resolve())
    second = _apply_atomic(
        connection, manifest_path, manifest_sha, current_database_identity
    )

    assert _transaction_statements(trace) == ["BEGIN IMMEDIATE", "COMMIT"]
    assert second["canonical_period_count"] == first["canonical_period_count"]
    assert second["canonical_periods"] == first["canonical_periods"]
    assert second["inserted_count"] == 0
    assert second["identical_existing_count"] == 16
    assert _atomic_snapshot(connection) == after_first
    assert connection.execute(
        "SELECT COUNT(*) FROM draws_big_lotto_canonical_main "
        "WHERE CAST(draw AS INTEGER) BETWEEN 120000001 AND 120000998"
    ).fetchone()[0] == 0
    connection.close()


def test_eighth_insert_failure_rolls_back_raw_identity_manifest_and_view(tmp_path):
    (
        connection,
        _database_path,
        database_identity,
        manifest_path,
        manifest_sha,
        _manifest,
    ) = _prepared_atomic_apply(tmp_path)
    connection.execute(
        """
        CREATE TRIGGER fail_on_eighth_atomic
        BEFORE INSERT ON draws
        WHEN NEW.draw = '115000087'
        BEGIN
            SELECT RAISE(ABORT, 'deliberate atomic eighth-row failure');
        END
        """
    )
    connection.commit()
    database_identity = staged._database_identity(
        Path(connection.execute("PRAGMA database_list").fetchone()[2]).resolve()
    )
    before = _atomic_snapshot(connection)
    trace = []
    connection.set_trace_callback(trace.append)

    with pytest.raises(sqlite3.IntegrityError, match="deliberate atomic eighth-row failure"):
        _apply_atomic(connection, manifest_path, manifest_sha, database_identity)

    assert _transaction_statements(trace) == ["BEGIN IMMEDIATE", "ROLLBACK"]
    assert connection.in_transaction is False
    assert _atomic_snapshot(connection) == before
    assert connection.execute(
        "SELECT COUNT(*) FROM draws WHERE draw BETWEEN '115000080' AND '115000095'"
    ).fetchone()[0] == 0
    connection.close()


def test_view_replacement_failure_rolls_back_the_entire_atomic_apply(tmp_path):
    (
        connection,
        _database_path,
        database_identity,
        manifest_path,
        manifest_sha,
        _manifest,
    ) = _prepared_atomic_apply(tmp_path)
    before = _atomic_snapshot(connection)
    trace = []
    connection.set_trace_callback(trace.append)

    def deny_canonical_view_creation(action, argument1, _argument2, _database, _trigger):
        if (
            action == sqlite3.SQLITE_CREATE_VIEW
            and argument1 == membership.CANONICAL_VIEW
        ):
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK

    connection.set_authorizer(deny_canonical_view_creation)
    try:
        with pytest.raises(sqlite3.DatabaseError, match="not authorized"):
            _apply_atomic(connection, manifest_path, manifest_sha, database_identity)
    finally:
        connection.set_authorizer(None)

    assert _transaction_statements(trace) == ["BEGIN IMMEDIATE", "ROLLBACK"]
    assert connection.in_transaction is False
    assert _atomic_snapshot(connection) == before
    connection.close()


def test_rehashed_manifest_tamper_still_fails_the_external_file_pin(tmp_path):
    (
        connection,
        _database_path,
        database_identity,
        manifest_path,
        approved_manifest_sha,
        _manifest,
    ) = _prepared_atomic_apply(tmp_path)
    before = _atomic_snapshot(connection)
    tampered = json.loads(manifest_path.read_text(encoding="utf-8"))
    record = tampered["records"][0]
    record["special"] = next(
        number
        for number in range(1, 50)
        if number not in record["numbers"] and number != record["special"]
    )
    unsigned = dict(tampered)
    unsigned.pop("content_sha256", None)
    tampered["content_sha256"] = hashlib.sha256(
        json.dumps(
            unsigned,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    manifest_path.write_text(
        json.dumps(tampered, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    assert staged.records_from_manifest(manifest_path)[0].special == record["special"]
    trace = []
    connection.set_trace_callback(trace.append)

    with pytest.raises(staged.StagingError, match="external manifest file SHA-256"):
        _apply_atomic(connection, manifest_path, approved_manifest_sha, database_identity)

    assert _transaction_statements(trace) == []
    assert _atomic_snapshot(connection) == before
    connection.close()


def test_database_identity_mismatch_rejects_before_begin(tmp_path):
    (
        connection,
        _database_path,
        database_identity,
        manifest_path,
        manifest_sha,
        _manifest,
    ) = _prepared_atomic_apply(tmp_path)
    before = _atomic_snapshot(connection)
    wrong_identity = dict(database_identity)
    wrong_identity["sha256"] = "0" * 64
    trace = []
    connection.set_trace_callback(trace.append)

    with pytest.raises(staged.StagingError, match="expected identity"):
        _apply_atomic(
            connection,
            manifest_path,
            manifest_sha,
            wrong_identity,
        )

    assert _transaction_statements(trace) == []
    assert _atomic_snapshot(connection) == before
    connection.close()


def test_official_dataset_digest_mismatch_rejects_before_begin(tmp_path):
    (
        connection,
        _database_path,
        database_identity,
        manifest_path,
        manifest_sha,
        _manifest,
    ) = _prepared_atomic_apply(tmp_path)
    before = _atomic_snapshot(connection)
    trace = []
    connection.set_trace_callback(trace.append)

    with pytest.raises(staged.StagingError, match="official identity dataset"):
        _apply_atomic(
            connection,
            manifest_path,
            manifest_sha,
            database_identity,
            approved_official_dataset_sha256="0" * 64,
        )

    assert _transaction_statements(trace) == []
    assert _atomic_snapshot(connection) == before
    connection.close()


def test_staged_record_must_match_the_fixed_official_identity_snapshot(tmp_path):
    records = list(_official_records())
    records[0] = replace(records[0], date="2026-08-19")
    (
        connection,
        _database_path,
        database_identity,
        manifest_path,
        manifest_sha,
        _manifest,
    ) = _prepared_atomic_apply(tmp_path, records)
    before = _atomic_snapshot(connection)
    trace = []
    connection.set_trace_callback(trace.append)

    with pytest.raises(staged.StagingError, match="fixed official identity snapshot"):
        _apply_atomic(connection, manifest_path, manifest_sha, database_identity)

    assert _transaction_statements(trace) == []
    assert _atomic_snapshot(connection) == before
    connection.close()


def test_cli_has_no_database_apply_command_without_owner_authorization(capsys):
    parser = staged.build_argument_parser()

    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["apply", "--database", "/tmp/production.sqlite"])

    assert exc_info.value.code == 2
    assert "invalid choice" in capsys.readouterr().err
