"""Synthetic tests for the isolated P271J prospective-capture ledger.

All tests run against in-memory (``sqlite3.connect(":memory:")``) or pytest
``tmp_path`` SQLite databases. No test opens, copies, or modifies the production
database, requires the network, alters environment configuration, or invokes any
route / production service.
"""

from __future__ import annotations

import hashlib
import importlib
import inspect
import re
import sqlite3
from pathlib import Path

import pytest

import lottery_api.prospective_capture_ledger as pcl


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "lottery_api" / "prospective_capture_ledger.py"
MODULE_SRC = MODULE_PATH.read_text(encoding="utf-8")
PROD_DB = ROOT / "lottery_api" / "data" / "lottery_v2.db"

# Frozen artifact hashes (merged P271G/H/I) — integrity guard.
ARTIFACT_HASHES = {
    ROOT / "outputs/research/p271i_prospective_capture_ledger_implementation_design_20260613.json":
        "33024b09784aa66bd1a5e1995aeb1837bc174eae4d3b8f939d9a1dcee61c4a1e",
    ROOT / "outputs/research/p271i_prospective_capture_ledger_implementation_design_20260613.md":
        "3a96c4eeef7e1b7a7b992e822252f61279ea0fe99f4b306570578715ebdd903c",
    ROOT / "tests/test_p271i_prospective_capture_ledger_implementation_design.py":
        "567edfd944484c2ce26f8066999a1a170ee9303f82886068208c105d0f8fa167",
    ROOT / "outputs/research/p271h_prospective_capture_feasibility_audit_20260612.json":
        "c95f816710c47dd418a4f4a9138c993386569ff4281a3596bb8be123f3d78b57",
    ROOT / "outputs/research/p271h_prospective_capture_feasibility_audit_20260612.md":
        "b2c0eb9cb7121a181b582ea29537192d0bc8a854ac5c81b31a0e0cd617da53aa",
    ROOT / "outputs/research/p271g_prize_aware_null_prospective_preregistration_20260612.json":
        "8ff20a9969e2e4bca3ace8fc0a6899cbafda5a31be2a9201df755704cba38092",
    ROOT / "outputs/research/p271g_prize_aware_null_prospective_preregistration_20260612.md":
        "4ab9ef261303b5ac9beb11077e998977bcc9358b1bbee4fa9aea70d153f12ef9",
}

# --- synthetic timestamps (timezone-aware UTC) ----------------------------
ACT_MERGED = "2026-05-30T00:00:00+00:00"
ACT_START = "2026-06-01T00:00:00+00:00"
PRED = "2026-06-10T10:00:00+00:00"
RECORDED = "2026-06-10T10:05:00+00:00"
CLOSE = "2026-06-10T13:00:00+00:00"
SNAPSHOT = "2026-06-10T09:30:00+00:00"

DEFAULT_KNOWN = {("strat_a", "v1"), ("strat_b", "v1")}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# Factories
# ---------------------------------------------------------------------------


def make_source(**overrides):
    params = dict(
        source_type=pcl.SOURCE_OFFICIAL_MACHINE_READABLE,
        source_id="tw_lottery_machine_feed",
        source_version="2026-06-10.1",
        clock_skew_margin_seconds=300,
        provenance={
            "source_url": "synthetic://draw-close",
            "fetched_at_utc": SNAPSHOT,
            "response_hash": "deadbeef",
            "source_version": "2026-06-10.1",
        },
        snapshot_at_utc=SNAPSHOT,
        freshness_window_seconds=86400,
        manually_verified=True,
    )
    params.update(overrides)
    return pcl.DrawCloseSource(**params)


def make_ticket(**overrides):
    params = dict(
        strategy_id="strat_a",
        strategy_version="v1",
        bet_index=1,
        predicted_main_numbers=[5, 1, 38, 12, 24, 30],
        prediction_created_at_utc=PRED,
        created_by="synthetic",
        source_provenance="synthetic-live-capture",
        predicted_second_zone=4,
    )
    params.update(overrides)
    return pcl.TicketInput(**params)


def make_batch(**overrides):
    params = dict(
        activation_id="act1",
        preregistration_version="p271g.v1",
        prospective_protocol_version="p271.proto.v1",
        lottery_type="POWER_LOTTO",
        target_draw="115000099",
        draw_close_at_utc=CLOSE,
        draw_close_source=make_source(),
        capture_mode=pcl.CAPTURE_MODE_LIVE_PRE_CLOSE,
        created_by="synthetic",
        recorded_at_utc=RECORDED,
        tickets=[make_ticket()],
    )
    params.update(overrides)
    return pcl.BatchInput(**params)


def fresh_conn():
    conn = sqlite3.connect(":memory:")
    pcl.install_schema(conn)
    return conn


def register_default_activation(conn, activation_id="act1"):
    return pcl.register_activation(
        conn,
        activation_id=activation_id,
        activation_artifact_commit="synthetic-artifact-commit",
        deployed_implementation_commit="synthetic-deploy-commit",
        migration_verification_ref="synthetic-migration-ref",
        activation_merged_at_utc=ACT_MERGED,
        prospective_start_at_utc=ACT_START,
        recorded_at_utc=ACT_START,
        created_by="synthetic",
        actor="synthetic-operator",
        service_identity="prospective_capture_ledger",
        code_commit="synthetic",
    )


def ready_conn():
    conn = fresh_conn()
    register_default_activation(conn)
    return conn


def capture(conn, batch, known=DEFAULT_KNOWN):
    return pcl.capture_batch(conn, batch, known_strategy_versions=known)


# ---------------------------------------------------------------------------
# 1-2  Isolation / no side effects
# ---------------------------------------------------------------------------


def test_01_no_import_time_side_effect():
    mod = importlib.reload(pcl)
    # No module-level live sqlite connection.
    for name in dir(mod):
        assert not isinstance(getattr(mod, name), sqlite3.Connection)
    # Calling an entry point without a real connection fails closed.
    with pytest.raises(pcl.LedgerUsageError):
        mod.install_schema(object())


def test_02_no_production_db_path_or_forbidden_import():
    assert "lottery_v2.db" not in MODULE_SRC
    assert "lottery_api/data" not in MODULE_SRC
    import_lines = [
        ln for ln in MODULE_SRC.splitlines()
        if re.match(r"^\s*(from|import)\s", ln)
    ]
    blob = "\n".join(import_lines).lower()
    for forbidden in (
        "lottery_api.database",
        "prize_aware_scorer",
        "replay",
        "registry",
        "controlled_apply",
        "recommendation",
        "requests",
        "urllib",
        "httpx",
        "aiohttp",
        "socket",
        "flask",
        "fastapi",
    ):
        assert forbidden not in blob, forbidden


# ---------------------------------------------------------------------------
# 3-9  Schema bootstrap
# ---------------------------------------------------------------------------


def test_03_schema_install_on_in_memory_db():
    conn = sqlite3.connect(":memory:")
    version = pcl.install_schema(conn)
    assert version == pcl.SCHEMA_VERSION
    assert pcl.get_schema_version(conn) == pcl.SCHEMA_VERSION


def test_04_schema_install_is_idempotent():
    conn = sqlite3.connect(":memory:")
    pcl.install_schema(conn)
    # Second install on a same-version DB is a no-op (no error).
    pcl.install_schema(conn)
    assert pcl.get_schema_version(conn) == pcl.SCHEMA_VERSION


def test_05_incompatible_schema_rejected():
    conn = sqlite3.connect(":memory:")
    pcl.install_schema(conn)
    # Tamper with the version marker to simulate drift; UPDATE is blocked by the
    # append-only nature only on the protected tables, so meta is mutated raw.
    conn.execute(
        f"UPDATE {pcl._META_TABLE} SET value='other.v9' WHERE key='schema_version'"
    )
    with pytest.raises(pcl.SchemaVersionError):
        pcl.install_schema(conn)


def test_05b_foreign_prospective_table_without_marker_rejected():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE prospective_prediction_ledger (x INTEGER)")
    with pytest.raises(pcl.SchemaVersionError):
        pcl.install_schema(conn)


def test_06_foreign_keys_enabled():
    conn = ready_conn()
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_07_required_tables_indexes_triggers_present():
    conn = fresh_conn()
    objects = pcl.schema_objects(conn)
    for table in pcl.REQUIRED_TABLES:
        assert table in objects["tables"], table
    assert "idx_ledger_identity" in objects["indexes"]
    assert "idx_batch_cluster" in objects["indexes"]
    for table in pcl._APPEND_ONLY_TABLES:
        assert f"trg_{table}_no_update" in objects["triggers"], table
        assert f"trg_{table}_no_delete" in objects["triggers"], table


def test_08_append_only_update_rejected():
    conn = ready_conn()
    res = capture(conn, make_batch())
    assert res.accepted
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            f"UPDATE {pcl._LEDGER_TABLE} SET eligibility_status='X' WHERE ledger_id=?",
            (res.ledger_ids[0],),
        )


def test_09_append_only_delete_rejected():
    conn = ready_conn()
    res = capture(conn, make_batch())
    assert res.accepted
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            f"DELETE FROM {pcl._LEDGER_TABLE} WHERE ledger_id=?",
            (res.ledger_ids[0],),
        )
    # Batch and event tables are append-only too.
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(f"DELETE FROM {pcl._BATCH_TABLE}")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(f"DELETE FROM {pcl._EVENT_TABLE}")


# ---------------------------------------------------------------------------
# 10-12  Activation lifecycle
# ---------------------------------------------------------------------------


def test_10_activation_event_append_behavior():
    conn = fresh_conn()
    register_default_activation(conn)
    events = pcl.list_events(conn, event_type=pcl.EVENT_ACTIVATION)
    assert len(events) == 1
    assert pcl.is_activation_active(conn, "act1", RECORDED) is True


def test_11_deactivation_without_history_rewrite():
    conn = ready_conn()
    before = pcl._activation_row(conn, "act1")["status"]
    pcl.deactivate_activation(
        conn,
        activation_id="act1",
        effective_at_utc="2026-06-11T00:00:00+00:00",
        recorded_at_utc="2026-06-11T00:00:00+00:00",
        actor="op",
        service_identity="svc",
        code_commit="c",
        justification="synthetic deactivation",
    )
    after = pcl._activation_row(conn, "act1")["status"]
    assert before == after == "ACTIVE"  # registry row never rewritten
    assert pcl.is_activation_active(conn, "act1", "2026-06-10T10:05:00+00:00") is True
    assert pcl.is_activation_active(conn, "act1", "2026-06-12T00:00:00+00:00") is False
    assert pcl.list_events(conn, event_type=pcl.EVENT_DEACTIVATION)


def test_12_inactive_activation_rejected():
    conn = fresh_conn()  # no activation registered
    res = capture(conn, make_batch(activation_id="ghost"))
    assert not res.accepted
    assert res.rejection_reason == pcl.REASON_INACTIVE_ACTIVATION


# ---------------------------------------------------------------------------
# 13-16  Identity / uniqueness
# ---------------------------------------------------------------------------


def test_13_deterministic_identity():
    a = pcl.derive_ledger_id("act1", "POWER_LOTTO", "115000099", "strat_a", "v1", 1)
    b = pcl.derive_ledger_id("act1", "POWER_LOTTO", "115000099", "strat_a", "v1", 1)
    c = pcl.derive_ledger_id("act1", "POWER_LOTTO", "115000099", "strat_a", "v1", 2)
    assert a == b
    assert a != c
    assert a.startswith("pl_")


def test_14_deterministic_payload_hash():
    h1 = pcl.compute_payload_hash(
        "act1", "POWER_LOTTO", "115000099", "strat_a", "v1", 1, [5, 1, 38, 12, 24, 30], 4, PRED
    )
    # Order of main numbers must not change the hash (sorted canonical form).
    h2 = pcl.compute_payload_hash(
        "act1", "POWER_LOTTO", "115000099", "strat_a", "v1", 1, [30, 24, 12, 38, 1, 5], 4, PRED
    )
    h3 = pcl.compute_payload_hash(
        "act1", "POWER_LOTTO", "115000099", "strat_a", "v1", 1, [5, 1, 38, 12, 24, 30], 5, PRED
    )
    assert h1 == h2
    assert h1 != h3
    assert len(h1) == 64


def test_15_duplicate_identity_rejected():
    conn = ready_conn()
    assert capture(conn, make_batch()).accepted
    res2 = capture(conn, make_batch())
    assert not res2.accepted
    assert res2.rejection_reason == pcl.REASON_DUPLICATE_IDENTITY


def test_16_duplicate_cannot_overwrite():
    conn = ready_conn()
    first = capture(conn, make_batch())
    original = pcl.get_ledger_row(conn, first.ledger_ids[0])
    # Re-submit same identity with different predicted numbers.
    capture(conn, make_batch(tickets=[make_ticket(predicted_main_numbers=[2, 3, 4, 5, 6, 7], predicted_second_zone=1)]))
    after = pcl.get_ledger_row(conn, first.ledger_ids[0])
    assert after["payload_hash"] == original["payload_hash"]
    assert pcl.count_eligible_rows(conn) == 1


# ---------------------------------------------------------------------------
# 17-21  Atomic batch transaction
# ---------------------------------------------------------------------------


def test_17_valid_single_ticket_capture():
    conn = ready_conn()
    res = capture(conn, make_batch())
    assert res.accepted
    assert len(res.ledger_ids) == 1
    assert pcl.count_eligible_rows(conn) == 1
    assert pcl.list_events(conn, event_type=pcl.EVENT_CAPTURE)


def test_18_valid_multi_ticket_capture():
    conn = ready_conn()
    tickets = [
        make_ticket(bet_index=1, predicted_main_numbers=[1, 2, 3, 4, 5, 6], predicted_second_zone=1),
        make_ticket(bet_index=2, predicted_main_numbers=[7, 8, 9, 10, 11, 12], predicted_second_zone=2),
        make_ticket(bet_index=3, strategy_id="strat_b", predicted_main_numbers=[13, 14, 15, 16, 17, 18], predicted_second_zone=3),
    ]
    res = capture(conn, make_batch(tickets=tickets))
    assert res.accepted
    assert len(res.ledger_ids) == 3
    assert pcl.count_eligible_rows(conn) == 3


def test_19_one_invalid_ticket_rolls_back_all():
    conn = ready_conn()
    tickets = [
        make_ticket(bet_index=1, predicted_main_numbers=[1, 2, 3, 4, 5, 6], predicted_second_zone=1),
        make_ticket(bet_index=2, predicted_main_numbers=[1, 2, 3, 4, 5, 99], predicted_second_zone=2),  # 99 out of range
    ]
    res = capture(conn, make_batch(tickets=tickets))
    assert not res.accepted
    assert res.rejection_reason == pcl.REASON_INVALID_PREDICTED_NUMBERS
    assert pcl.count_eligible_rows(conn) == 0


def test_20_duplicate_in_batch_rolls_back_all():
    conn = ready_conn()
    tickets = [
        make_ticket(bet_index=1, predicted_main_numbers=[1, 2, 3, 4, 5, 6], predicted_second_zone=1),
        make_ticket(bet_index=1, predicted_main_numbers=[7, 8, 9, 10, 11, 12], predicted_second_zone=2),  # same bet_index
    ]
    res = capture(conn, make_batch(tickets=tickets))
    assert not res.accepted
    assert res.rejection_reason == pcl.REASON_DUPLICATE_IDENTITY
    assert pcl.count_eligible_rows(conn) == 0


def test_21_rollback_leaves_no_orphan_batch():
    conn = ready_conn()
    assert capture(conn, make_batch()).accepted
    # Second identical capture is rejected by the unique key and rolled back.
    assert not capture(conn, make_batch()).accepted
    # Exactly one batch row exists; the rejected attempt left no orphan.
    n_batches = conn.execute(f"SELECT COUNT(*) FROM {pcl._BATCH_TABLE}").fetchone()[0]
    assert n_batches == 1
    assert pcl.count_eligible_rows(conn) == 1


def test_21b_transaction_failure_leaves_no_rows(monkeypatch):
    conn = ready_conn()
    real_insert = pcl._insert_event

    def flaky(c, **kw):
        if kw.get("event_type") == pcl.EVENT_CAPTURE:
            raise RuntimeError("synthetic mid-transaction failure")
        return real_insert(c, **kw)

    monkeypatch.setattr(pcl, "_insert_event", flaky)
    res = capture(conn, make_batch())
    assert not res.accepted
    assert res.rejection_reason == pcl.REASON_TRANSACTION_FAILURE
    assert pcl.count_eligible_rows(conn) == 0
    assert conn.execute(f"SELECT COUNT(*) FROM {pcl._BATCH_TABLE}").fetchone()[0] == 0


# ---------------------------------------------------------------------------
# 22-27  UTC / causality
# ---------------------------------------------------------------------------


def test_22_naive_timestamp_rejected():
    conn = ready_conn()
    res = capture(conn, make_batch(tickets=[make_ticket(prediction_created_at_utc="2026-06-10T10:00:00")]))
    assert not res.accepted
    assert res.rejection_reason == pcl.REASON_AMBIGUOUS_TIMESTAMP


def test_23_ambiguous_timestamp_rejected():
    conn = ready_conn()
    res = capture(conn, make_batch(draw_close_at_utc="next tuesday afternoon"))
    assert not res.accepted
    assert res.rejection_reason == pcl.REASON_AMBIGUOUS_TIMESTAMP


def test_23b_non_utc_offset_is_normalized():
    # A tz-aware Asia/Taipei (+08:00) instant is accepted and normalized to UTC.
    conn = ready_conn()
    res = capture(
        conn,
        make_batch(tickets=[make_ticket(prediction_created_at_utc="2026-06-10T18:00:00+08:00")]),
    )
    assert res.accepted
    row = pcl.get_ledger_row(conn, res.ledger_ids[0])
    assert row["prediction_created_at_utc"].endswith("+00:00")
    assert "10:00:00" in row["prediction_created_at_utc"]  # 18:00 +08:00 == 10:00 UTC


def test_24_missing_close_rejected():
    conn = ready_conn()
    res = capture(conn, make_batch(draw_close_at_utc=None))
    assert not res.accepted
    assert res.rejection_reason == pcl.REASON_CLOSE_TIME_MISSING


def test_25_stale_close_evidence_rejected():
    conn = ready_conn()
    stale_source = make_source(snapshot_at_utc="2026-06-01T00:00:00+00:00", freshness_window_seconds=60)
    res = capture(conn, make_batch(draw_close_source=stale_source))
    assert not res.accepted
    assert res.rejection_reason == pcl.REASON_STALE_SCHEDULE


def test_26_post_close_rejected():
    conn = ready_conn()
    # prediction at 12:59, close at 13:00, margin 300s -> close-margin = 12:55 -> after.
    res = capture(conn, make_batch(tickets=[make_ticket(prediction_created_at_utc="2026-06-10T12:59:00+00:00")]))
    assert not res.accepted
    assert res.rejection_reason == pcl.REASON_POST_CLOSE_SUBMISSION


def test_27_clock_skew_boundary_behavior():
    # margin=300, close=13:00:00 -> threshold = 12:55:00.
    conn = ready_conn()
    # Exactly at threshold -> NOT strictly earlier -> rejected.
    at_threshold = capture(
        conn, make_batch(tickets=[make_ticket(prediction_created_at_utc="2026-06-10T12:55:00+00:00")])
    )
    assert not at_threshold.accepted
    assert at_threshold.rejection_reason == pcl.REASON_POST_CLOSE_SUBMISSION
    # One second before threshold -> accepted.
    just_before = capture(
        conn,
        make_batch(
            target_draw="115000100",
            tickets=[make_ticket(prediction_created_at_utc="2026-06-10T12:54:59+00:00")],
        ),
    )
    assert just_before.accepted


def test_27b_missing_clock_skew_margin_fails_closed():
    conn = ready_conn()
    res = capture(conn, make_batch(draw_close_source=make_source(clock_skew_margin_seconds=None)))
    assert not res.accepted
    assert res.rejection_reason == pcl.REASON_SOURCE_PROVENANCE_FAILURE


# ---------------------------------------------------------------------------
# 28-30  Draw-close source classes
# ---------------------------------------------------------------------------


def test_28_official_source_contract_validation():
    conn = ready_conn()
    ok = capture(conn, make_batch(draw_close_source=make_source(source_type=pcl.SOURCE_OFFICIAL_PUBLISHED_SCHEDULE)))
    assert ok.accepted
    # Missing provenance fails closed.
    bad = capture(
        conn,
        make_batch(target_draw="115000101", draw_close_source=make_source(provenance={})),
    )
    assert not bad.accepted
    assert bad.rejection_reason == pcl.REASON_SOURCE_PROVENANCE_FAILURE


def test_29_deterministic_schedule_source_validation():
    conn = ready_conn()
    verified = capture(
        conn,
        make_batch(
            draw_close_source=make_source(
                source_type=pcl.SOURCE_REPOSITORY_DETERMINISTIC,
                provenance={"config_path": "config/x.json", "config_version": "1", "config_hash": "abc"},
                manually_verified=True,
            )
        ),
    )
    assert verified.accepted
    unverified = capture(
        conn,
        make_batch(
            target_draw="115000102",
            draw_close_source=make_source(
                source_type=pcl.SOURCE_REPOSITORY_DETERMINISTIC,
                provenance={"config_path": "config/x.json", "config_version": "1", "config_hash": "abc"},
                manually_verified=False,
            ),
        ),
    )
    assert not unverified.accepted
    assert unverified.rejection_reason == pcl.REASON_SOURCE_PENDING_MANUAL_VERIFICATION


def test_30_manual_source_non_confirmatory():
    conn = ready_conn()
    res = capture(
        conn,
        make_batch(
            draw_close_source=make_source(
                source_type=pcl.SOURCE_MANUAL,
                provenance={"entered_by": "human", "entered_at_utc": SNAPSHOT, "justification": "synthetic"},
                manually_verified=True,  # even if asserted, manual can never be confirmatory
            )
        ),
    )
    assert not res.accepted
    assert res.rejection_reason == pcl.REASON_MANUAL_SOURCE_NOT_CONFIRMATORY


# ---------------------------------------------------------------------------
# 31-39  Lottery validation
# ---------------------------------------------------------------------------


def test_31_power_valid_ticket():
    conn = ready_conn()
    res = capture(conn, make_batch())
    assert res.accepted
    row = pcl.get_ledger_row(conn, res.ledger_ids[0])
    assert row["predicted_second_zone"] == 4


def test_32_power_missing_second_zone_rejected():
    conn = ready_conn()
    res = capture(conn, make_batch(tickets=[make_ticket(predicted_second_zone=None)]))
    assert not res.accepted
    assert res.rejection_reason == pcl.REASON_MISSING_OR_INVALID_SECOND_ZONE


def test_33_power_invalid_second_zone_rejected():
    conn = ready_conn()
    res = capture(conn, make_batch(tickets=[make_ticket(predicted_second_zone=99)]))
    assert not res.accepted
    assert res.rejection_reason == pcl.REASON_MISSING_OR_INVALID_SECOND_ZONE


def test_34_big_valid_ticket():
    conn = ready_conn()
    res = capture(
        conn,
        make_batch(
            lottery_type="BIG_LOTTO",
            tickets=[make_ticket(predicted_main_numbers=[1, 2, 3, 4, 5, 49], predicted_second_zone=None)],
        ),
    )
    assert res.accepted
    row = pcl.get_ledger_row(conn, res.ledger_ids[0])
    assert row["predicted_second_zone"] is None


def test_35_big_second_zone_field_rejected():
    conn = ready_conn()
    res = capture(
        conn,
        make_batch(
            lottery_type="BIG_LOTTO",
            tickets=[make_ticket(predicted_main_numbers=[1, 2, 3, 4, 5, 49], predicted_second_zone=3)],
        ),
    )
    assert not res.accepted
    assert res.rejection_reason == pcl.REASON_SECOND_ZONE_NOT_PERMITTED


def test_36_daily539_valid_ticket():
    conn = ready_conn()
    res = capture(
        conn,
        make_batch(
            lottery_type="DAILY_539",
            tickets=[make_ticket(predicted_main_numbers=[1, 2, 3, 4, 39], predicted_second_zone=None)],
        ),
    )
    assert res.accepted


def test_37_daily539_second_zone_field_rejected():
    conn = ready_conn()
    res = capture(
        conn,
        make_batch(
            lottery_type="DAILY_539",
            tickets=[make_ticket(predicted_main_numbers=[1, 2, 3, 4, 39], predicted_second_zone=2)],
        ),
    )
    assert not res.accepted
    assert res.rejection_reason == pcl.REASON_SECOND_ZONE_NOT_PERMITTED


def test_38_duplicate_and_boolean_numbers_rejected():
    conn = ready_conn()
    dup = capture(conn, make_batch(tickets=[make_ticket(predicted_main_numbers=[1, 1, 2, 3, 4, 5])]))
    assert not dup.accepted and dup.rejection_reason == pcl.REASON_INVALID_PREDICTED_NUMBERS
    # Booleans must not be accepted as integers.
    boolean = capture(
        conn,
        make_batch(target_draw="115000103", tickets=[make_ticket(predicted_main_numbers=[True, 2, 3, 4, 5, 6])]),
    )
    assert not boolean.accepted and boolean.rejection_reason == pcl.REASON_INVALID_PREDICTED_NUMBERS


def test_39_unsupported_lottery_rejected():
    conn = ready_conn()
    res = capture(conn, make_batch(lottery_type="MEGA_MILLIONS"))
    assert not res.accepted
    assert res.rejection_reason == pcl.REASON_UNSUPPORTED_LOTTERY


def test_40_caller_input_not_mutated():
    conn = ready_conn()
    original_numbers = [30, 24, 12, 38, 1, 5]
    ticket = make_ticket(predicted_main_numbers=list(original_numbers))
    capture(conn, make_batch(tickets=[ticket]))
    # The caller's list object is unchanged (module sorts a copy internally).
    assert ticket.predicted_main_numbers == original_numbers


# ---------------------------------------------------------------------------
# 41-43  Membership / provenance
# ---------------------------------------------------------------------------


def test_41_backfill_import_replay_rejected():
    conn = ready_conn()
    for mode in ("BACKFILL", "IMPORT", "RECONSTRUCTED", "MANUAL"):
        res = capture(conn, make_batch(capture_mode=mode))
        assert not res.accepted, mode
        assert res.rejection_reason == pcl.REASON_BACKFILL_EXCLUDED, mode
    assert pcl.count_eligible_rows(conn) == 0


def test_42_unknown_strategy_version_rejected():
    conn = ready_conn()
    res = capture(conn, make_batch(tickets=[make_ticket(strategy_version="v999")]))
    assert not res.accepted
    assert res.rejection_reason == pcl.REASON_UNKNOWN_STRATEGY_VERSION
    # Empty known set => everything unknown => fail closed.
    res2 = capture(conn, make_batch(target_draw="115000104"), known=set())
    assert not res2.accepted
    assert res2.rejection_reason == pcl.REASON_UNKNOWN_STRATEGY_VERSION


def test_43_provenance_failure_rejected():
    conn = ready_conn()
    res = capture(conn, make_batch(tickets=[make_ticket(source_provenance="")]))
    assert not res.accepted
    assert res.rejection_reason == pcl.REASON_SOURCE_PROVENANCE_FAILURE


# ---------------------------------------------------------------------------
# 44-47  Amendment / membership freeze
# ---------------------------------------------------------------------------


def test_44_amendment_appends_and_preserves_original():
    conn = ready_conn()
    res = capture(conn, make_batch())
    ledger_id = res.ledger_ids[0]
    before = pcl.get_ledger_row(conn, ledger_id)
    out = pcl.append_amendment(
        conn,
        original_ledger_id=ledger_id,
        reason="synthetic correction note",
        amended_payload={"note": "operator correction"},
        effective_at_utc="2026-06-10T11:00:00+00:00",
        recorded_at_utc="2026-06-10T11:00:00+00:00",
        actor="op",
        service_identity="svc",
        code_commit="c",
    )
    assert out.accepted
    after = pcl.get_ledger_row(conn, ledger_id)
    assert after == before  # original ledger row untouched
    assert pcl.list_events(conn, event_type=pcl.EVENT_AMENDMENT)


def test_45_post_close_amendment_rejected():
    conn = ready_conn()
    res = capture(conn, make_batch())
    out = pcl.append_amendment(
        conn,
        original_ledger_id=res.ledger_ids[0],
        reason="late",
        amended_payload={"note": "too late"},
        effective_at_utc="2026-06-10T14:00:00+00:00",  # after 13:00 close
        recorded_at_utc="2026-06-10T14:00:00+00:00",
        actor="op",
        service_identity="svc",
        code_commit="c",
    )
    assert not out.accepted
    assert out.rejection_reason == pcl.REASON_POST_CLOSE_AMENDMENT


def test_45b_amendment_altering_identity_rejected():
    conn = ready_conn()
    res = capture(conn, make_batch())
    out = pcl.append_amendment(
        conn,
        original_ledger_id=res.ledger_ids[0],
        reason="identity tamper",
        amended_payload={"strategy_id": "strat_b"},
        effective_at_utc="2026-06-10T11:00:00+00:00",
        recorded_at_utc="2026-06-10T11:00:00+00:00",
        actor="op",
        service_identity="svc",
        code_commit="c",
    )
    assert not out.accepted
    assert out.rejection_reason == pcl.REASON_AMENDMENT_ALTERS_IDENTITY


def test_46_ineligible_record_cannot_become_prospective():
    conn = ready_conn()
    # A backfill attempt creates no eligible row.
    assert not capture(conn, make_batch(capture_mode="BACKFILL")).accepted
    assert pcl.count_eligible_rows(conn) == 0
    # There is no public function that upgrades eligibility.
    public = {n for n in dir(pcl) if not n.startswith("_")}
    for forbidden in ("upgrade", "promote", "set_eligible", "make_prospective", "mark_eligible"):
        assert forbidden not in public
    # eligibility_status is frozen by the append-only UPDATE trigger.
    res = capture(conn, make_batch())
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            f"UPDATE {pcl._LEDGER_TABLE} SET eligibility_status='ELIGIBLE' WHERE ledger_id=?",
            (res.ledger_ids[0],),
        )


def test_47_payload_hash_verification():
    conn = ready_conn()
    res = capture(conn, make_batch())
    assert pcl.verify_payload_hash(conn, res.ledger_ids[0]) is True
    assert pcl.verify_payload_hash(conn, "pl_does_not_exist") is False


# ---------------------------------------------------------------------------
# 48-50  Outcome separation / no scoring / no runtime
# ---------------------------------------------------------------------------


def test_48_no_outcome_or_scoring_imports_or_methods():
    public = {n for n in dir(pcl) if not n.startswith("_")}
    for forbidden in ("score", "classify_tier", "calculate_hits", "hit_count", "is_m3_plus", "prize"):
        assert forbidden not in public
    # The ledger schema carries no actual-result columns.
    conn = fresh_conn()
    ledger_cols = {
        r[1] for r in conn.execute(f"PRAGMA table_info({pcl._LEDGER_TABLE})").fetchall()
    }
    for forbidden_col in ("actual_main_numbers", "actual_second_zone", "hit_count", "special_hit", "prize_tier"):
        assert forbidden_col not in ledger_cols


def test_49_no_hit_prize_m3_calculation():
    # No callable in the module computes hits/prizes/M3+.
    for name, obj in inspect.getmembers(pcl, inspect.isfunction):
        lname = name.lower()
        assert "hit" not in lname
        assert "prize" not in lname
        assert "m3" not in lname
        assert "score" not in lname


def test_50_no_runtime_or_route_integration():
    assert "@app.route" not in MODULE_SRC
    assert "add_url_rule" not in MODULE_SRC
    assert "APIRouter" not in MODULE_SRC
    assert "FastAPI" not in MODULE_SRC
    for bad in ("fastapi", "flask", "uvicorn", "starlette"):
        assert not re.search(rf"^\s*(from|import)\s+.*{bad}", MODULE_SRC, re.MULTILINE | re.IGNORECASE)


# ---------------------------------------------------------------------------
# 51-52  Production DB / artifact integrity
# ---------------------------------------------------------------------------


def test_51_production_db_hash_unchanged():
    if not PROD_DB.exists():
        pytest.skip("production DB not present in this environment")
    before = _sha256(PROD_DB)
    # Exercise the full capture flow against a synthetic file DB in tmp space.
    conn = sqlite3.connect(":memory:")
    pcl.install_schema(conn)
    register_default_activation(conn)
    capture(conn, make_batch())
    after = _sha256(PROD_DB)
    assert before == after  # tests never touch the production DB


def test_51b_tmp_path_file_db(tmp_path):
    db = tmp_path / "synthetic_prospective.db"
    conn = sqlite3.connect(str(db))
    pcl.install_schema(conn)
    register_default_activation(conn)
    res = capture(conn, make_batch())
    assert res.accepted
    conn.close()
    # Confirm the synthetic DB lives strictly under tmp_path, not the repo.
    assert str(tmp_path) in str(db)
    assert ROOT not in db.parents


def test_51c_concurrent_duplicate_cannot_both_commit(tmp_path):
    db = tmp_path / "concurrent.db"
    setup = sqlite3.connect(str(db))
    pcl.install_schema(setup)
    register_default_activation(setup)
    setup.close()
    c1 = sqlite3.connect(str(db))
    c2 = sqlite3.connect(str(db))
    r1 = capture(c1, make_batch())
    r2 = capture(c2, make_batch())
    c1.close()
    c2.close()
    assert r1.accepted != r2.accepted  # exactly one wins
    assert r2.rejection_reason == pcl.REASON_DUPLICATE_IDENTITY or r1.rejection_reason == pcl.REASON_DUPLICATE_IDENTITY


def test_52_p271g_h_i_artifacts_unchanged():
    for path, expected in ARTIFACT_HASHES.items():
        assert path.exists(), path
        assert _sha256(path) == expected, path


# ===========================================================================
# Transaction-ownership hardening (P271J corrective fix)
# AMBIENT_TRANSACTION_NOT_ALLOWED: the module must never commit or roll back a
# caller's pre-existing open transaction. All write entry points fail closed.
# ===========================================================================


def _file_db_with_schema(tmp_path, name="ambient.db"):
    """A committed tmp_path file DB with schema, an active activation, and an
    unrelated caller-owned table. Strictly under tmp_path, never the repo."""
    db = tmp_path / name
    setup = sqlite3.connect(str(db))
    pcl.install_schema(setup)
    register_default_activation(setup)
    setup.execute("CREATE TABLE caller_unrelated (x)")
    setup.close()
    assert str(tmp_path) in str(db) and ROOT not in db.parents
    return db


def test_60_capture_batch_rejects_ambient_transaction(tmp_path):
    # A — two-connection decisive proof that the module does not commit caller work.
    db = _file_db_with_schema(tmp_path)
    caller = sqlite3.connect(str(db))                      # default (deferred) isolation
    caller.execute("INSERT INTO caller_unrelated VALUES (99)")  # opens ambient tx
    assert caller.in_transaction is True
    with pytest.raises(pcl.AmbientTransactionError):
        capture(caller, make_batch(target_draw="999"))
    assert caller.in_transaction is True                   # caller still owns its tx
    chk = sqlite3.connect(str(db))
    assert chk.execute("SELECT COUNT(*) FROM caller_unrelated").fetchone()[0] == 0
    assert chk.execute("SELECT COUNT(*) FROM prospective_prediction_ledger").fetchone()[0] == 0
    assert chk.execute("SELECT COUNT(*) FROM prospective_capture_batches").fetchone()[0] == 0
    caller.rollback()                                      # caller-owned rollback
    assert chk.execute("SELECT COUNT(*) FROM caller_unrelated").fetchone()[0] == 0
    chk.close(); caller.close()


def test_61_caller_commit_remains_caller_owned(tmp_path):
    # B — module rejects without committing; caller's own commit later applies.
    db = _file_db_with_schema(tmp_path, "commit.db")
    caller = sqlite3.connect(str(db))
    caller.execute("INSERT INTO caller_unrelated VALUES (7)")
    with pytest.raises(pcl.AmbientTransactionError):
        capture(caller, make_batch(target_draw="999"))
    chk = sqlite3.connect(str(db))
    assert chk.execute("SELECT COUNT(*) FROM caller_unrelated").fetchone()[0] == 0
    caller.commit()                                        # caller explicitly commits
    assert chk.execute("SELECT COUNT(*) FROM caller_unrelated").fetchone()[0] == 1
    assert chk.execute("SELECT COUNT(*) FROM prospective_prediction_ledger").fetchone()[0] == 0
    chk.close(); caller.close()


def test_62_caller_rollback_remains_caller_owned(tmp_path):
    # C — module rejects; caller's own rollback removes its row; no module row.
    db = _file_db_with_schema(tmp_path, "rollback.db")
    caller = sqlite3.connect(str(db))
    caller.execute("INSERT INTO caller_unrelated VALUES (5)")
    with pytest.raises(pcl.AmbientTransactionError):
        capture(caller, make_batch(target_draw="999"))
    caller.rollback()                                      # caller explicitly rolls back
    chk = sqlite3.connect(str(db))
    assert chk.execute("SELECT COUNT(*) FROM caller_unrelated").fetchone()[0] == 0
    assert chk.execute("SELECT COUNT(*) FROM prospective_prediction_ledger").fetchone()[0] == 0
    chk.close(); caller.close()


def test_63_connection_attributes_unchanged_on_rejection(tmp_path):
    # D — isolation_level / row_factory / in_transaction unchanged by rejection.
    db = _file_db_with_schema(tmp_path, "attrs.db")
    caller = sqlite3.connect(str(db))
    caller.row_factory = sqlite3.Row
    iso_before, rf_before = caller.isolation_level, caller.row_factory
    caller.execute("INSERT INTO caller_unrelated VALUES (1)")
    with pytest.raises(pcl.AmbientTransactionError):
        capture(caller, make_batch(target_draw="999"))
    assert caller.isolation_level == iso_before
    assert caller.row_factory is rf_before
    assert caller.in_transaction is True
    caller.rollback(); caller.close()


@pytest.mark.parametrize(
    "entry", ["install_schema", "register_activation", "lifecycle", "deactivate", "capture", "amendment"]
)
def test_64_every_write_entry_point_guarded(tmp_path, entry):
    # E — every public write entry point fails closed before owning caller's tx.
    db = _file_db_with_schema(tmp_path, f"wp_{entry}.db")
    led_id = None
    if entry == "amendment":
        clean = sqlite3.connect(str(db))                   # no ambient tx
        led_id = capture(clean, make_batch(target_draw="555")).ledger_ids[0]
        clean.close()
    caller = sqlite3.connect(str(db))
    caller.execute("INSERT INTO caller_unrelated VALUES (1)")  # ambient tx
    assert caller.in_transaction is True
    with pytest.raises(pcl.AmbientTransactionError):
        if entry == "install_schema":
            pcl.install_schema(caller)
        elif entry == "register_activation":
            register_default_activation(caller, activation_id="act2")
        elif entry == "lifecycle":
            pcl.append_activation_lifecycle_event(
                caller, activation_id="act1", lifecycle=pcl.EVENT_DEACTIVATION,
                effective_at_utc="2026-06-11T00:00:00+00:00",
                recorded_at_utc="2026-06-11T00:00:00+00:00",
                actor="o", service_identity="s", code_commit="c")
        elif entry == "deactivate":
            pcl.deactivate_activation(
                caller, activation_id="act1",
                effective_at_utc="2026-06-11T00:00:00+00:00",
                recorded_at_utc="2026-06-11T00:00:00+00:00",
                actor="o", service_identity="s", code_commit="c", justification="j")
        elif entry == "capture":
            capture(caller, make_batch(target_draw="999"))
        elif entry == "amendment":
            pcl.append_amendment(
                caller, original_ledger_id=led_id, reason="r",
                amended_payload={"note": "x"},
                effective_at_utc="2026-06-10T11:00:00+00:00",
                recorded_at_utc="2026-06-10T11:00:00+00:00",
                actor="o", service_identity="s", code_commit="c")
    assert caller.in_transaction is True                   # caller tx untouched
    caller.rollback(); caller.close()


def test_65_no_false_positive_without_ambient_transaction():
    # F — a connection with no ambient transaction still works normally.
    conn = ready_conn()
    assert conn.in_transaction is False
    res = capture(conn, make_batch())
    assert res.accepted
    assert pcl.count_eligible_rows(conn) == 1


def test_66_module_owned_rollback_still_works(monkeypatch):
    # G — when the MODULE owns the transaction, an injected failure rolls back
    # only module work. (No caller transaction exists; the guard is not bypassed.)
    conn = ready_conn()
    assert conn.in_transaction is False
    real = pcl._insert_event

    def flaky(c, **kw):
        if kw.get("event_type") == pcl.EVENT_CAPTURE:
            raise RuntimeError("synthetic module-owned failure")
        return real(c, **kw)

    monkeypatch.setattr(pcl, "_insert_event", flaky)
    res = capture(conn, make_batch())
    assert not res.accepted
    assert res.rejection_reason == pcl.REASON_TRANSACTION_FAILURE
    assert pcl.count_eligible_rows(conn) == 0
    assert conn.execute(f"SELECT COUNT(*) FROM {pcl._BATCH_TABLE}").fetchone()[0] == 0


def test_67_ambient_transaction_error_is_distinct_type():
    # The dedicated exception is distinguishable from other failure modes.
    assert issubclass(pcl.AmbientTransactionError, pcl.ProspectiveCaptureError)
    assert not issubclass(pcl.AmbientTransactionError, pcl.SchemaVersionError)
    assert not issubclass(pcl.AmbientTransactionError, pcl.LedgerUsageError)
    assert pcl.REASON_AMBIENT_TRANSACTION_NOT_ALLOWED == "AMBIENT_TRANSACTION_NOT_ALLOWED"
