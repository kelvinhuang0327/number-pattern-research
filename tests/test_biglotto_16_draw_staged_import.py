from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import replace
from datetime import date, timedelta
from urllib.parse import parse_qs, urlparse

import pytest

from scripts import biglotto_16_draw_staged_import as staged


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
