"""
P360A pre-draw metadata instrumentation tests.

ALL tests here use pytest's `tmp_path` fixture (or an explicit temp sqlite
DB) for every ledger/DB path. No test opens, copies, or migrates the
canonical `lottery_v2.db`. `test_ledger_path_never_canonical_db` asserts this
structurally, not just by convention.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import fields
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from lottery_api.engine import predraw_ledger as pl


# ─── Shared fixtures / helpers ──────────────────────────────────────────────

def _utc(y, mo, d, h=0, mi=0, s=0):
    return datetime(y, mo, d, h, mi, s, tzinfo=timezone.utc)


def _test_schedule_config():
    return {
        "schedule_rule_version": "test-v1",
        "timezone": "UTC",
        "rules": {
            "POWER_LOTTO": {"conservative_close_time_local": "20:00:00"},
            "BIG_LOTTO": {"conservative_close_time_local": "20:00:00"},
            "DAILY_539": {"conservative_close_time_local": "20:00:00"},
        },
    }


def _writer(tmp_path) -> pl.PredrawLedgerWriter:
    return pl.PredrawLedgerWriter(ledger_path=tmp_path / "ledger.jsonl")


def _live_kwargs(**overrides):
    kwargs = dict(
        lottery_type="POWER_LOTTO",
        target_draw=150,
        target_draw_date="2099-01-01",  # far future so predicted_at (test "now") is always before close
        strategy_id="power_precision_3bet",
        strategy_version="v0.1",
        predicted_numbers=[1, 2, 3, 4, 5, 6],
        predicted_special=7,
        bet_index=0,
        n_bets_total=3,
        run_id="run-001",
        generation_source="tools/quick_predict.py",
        max_source_draw_at_generation=149,
        schedule_config=_test_schedule_config(),
        now_fn=lambda: _utc(2026, 7, 3, 10, 0, 0),
    )
    kwargs.update(overrides)
    return kwargs


# ─── 1. Live happy path ─────────────────────────────────────────────────────

def test_live_happy_path_writes_all_fields_and_valid_chain(tmp_path):
    writer = _writer(tmp_path)
    rec = writer.write_live_prediction(**_live_kwargs())

    assert rec["generation_mode"] == "LIVE_PREDRAW"
    assert rec["schema_version"] == pl.SCHEMA_VERSION
    assert rec["record_kind"] == "PREDICTION"
    for required in (
        "record_id", "lottery_type", "predicted_at", "created_at", "target_draw",
        "target_draw_date", "scheduled_draw_close_at", "schedule_rule_version",
        "max_source_draw_at_generation", "strategy_id", "strategy_version",
        "code_git_sha", "code_dirty_flag", "predicted_numbers", "predicted_special",
        "bet_index", "n_bets_total", "run_id", "generation_source",
        "prev_record_hash", "record_hash",
    ):
        assert required in rec, f"missing field {required}"

    assert rec["target_draw"] == 150
    assert isinstance(rec["target_draw"], int)
    assert rec["prev_record_hash"] is None  # first record in a fresh ledger

    result = pl.verify_chain(writer.ledger_path)
    assert result.ok is True
    assert result.total_records == 1


def test_live_happy_path_eligible_for_oos(tmp_path):
    writer = _writer(tmp_path)
    rec = writer.write_live_prediction(**_live_kwargs())
    eligibility = pl.evaluate_oos_eligibility(rec)
    assert eligibility.eligible is True, eligibility.reason


# ─── 2. Mislabel impossibility (look-ahead witness) ────────────────────────

def test_max_source_draw_not_less_than_target_rejects_live(tmp_path):
    writer = _writer(tmp_path)
    with pytest.raises(pl.LiveEligibilityError):
        writer.write_live_prediction(**_live_kwargs(
            target_draw=150, max_source_draw_at_generation=150,  # equal, not <
        ))
    with pytest.raises(pl.LiveEligibilityError):
        writer.write_live_prediction(**_live_kwargs(
            target_draw=150, max_source_draw_at_generation=151,  # source already saw the future
        ))
    # ledger must remain untouched (no partial/garbage record written on failure)
    assert not writer.ledger_path.exists() or pl.read_all_records(writer.ledger_path) == []


# ─── 3. Outcome-already-known fixture rejects LIVE ─────────────────────────

def test_outcome_already_ingested_rejects_live(tmp_path):
    writer = _writer(tmp_path)
    predicted_at = _utc(2026, 7, 3, 10, 0, 0)
    outcome_already_known_at = predicted_at - timedelta(days=2)  # ingested BEFORE prediction => outcome already known
    with pytest.raises(pl.LiveEligibilityError):
        writer.write_live_prediction(**_live_kwargs(
            now_fn=lambda: predicted_at,
            outcome_ingested_at=outcome_already_known_at,
        ))


def test_predicted_at_after_scheduled_close_rejects_live(tmp_path):
    writer = _writer(tmp_path)
    with pytest.raises(pl.LiveEligibilityError):
        writer.write_live_prediction(**_live_kwargs(
            target_draw_date="2020-01-01",  # far in the past -> close time already elapsed
            now_fn=lambda: _utc(2026, 7, 3, 10, 0, 0),
        ))


# ─── 4. Fail-closed on missing witness fields ──────────────────────────────

def test_missing_target_draw_date_fails_closed(tmp_path):
    writer = _writer(tmp_path)
    with pytest.raises(pl.LiveEligibilityError):
        writer.write_live_prediction(**_live_kwargs(target_draw_date=None))
    with pytest.raises(pl.LiveEligibilityError):
        writer.write_live_prediction(**_live_kwargs(target_draw_date=""))


def test_missing_max_source_draw_fails_closed(tmp_path):
    writer = _writer(tmp_path)
    with pytest.raises((pl.LiveEligibilityError, TypeError)):
        writer.write_live_prediction(**_live_kwargs(max_source_draw_at_generation=None))


def test_backfill_and_replay_callers_cannot_emit_live(tmp_path):
    writer = _writer(tmp_path)
    with pytest.raises(ValueError):
        writer.write_retrospective_record(
            generation_mode="LIVE_PREDRAW",
            lottery_type="POWER_LOTTO",
            target_draw=150,
            strategy_id="power_precision_3bet",
            strategy_version="v0.1",
            predicted_numbers=[1, 2, 3, 4, 5, 6],
            predicted_special=7,
            bet_index=0,
            n_bets_total=3,
            run_id="backfill-run-1",
            generation_source="tools/backfill_batch.py",
        )


# ─── 5. Table-driven eligibility ───────────────────────────────────────────

@pytest.mark.parametrize("generation_mode", ["RETROSPECTIVE_REPLAY", "BACKFILL", "REGENERATED"])
def test_retrospective_modes_never_eligible(tmp_path, generation_mode):
    writer = _writer(tmp_path)
    kwargs = dict(
        generation_mode=generation_mode,
        lottery_type="BIG_LOTTO",
        target_draw=500,
        strategy_id="biglotto_triple_strike",
        strategy_version="v0.1",
        predicted_numbers=[1, 2, 3, 4, 5, 6],
        predicted_special=7,
        bet_index=0,
        n_bets_total=3,
        run_id="run-002",
        generation_source="tools/replay_batch.py",
    )
    if generation_mode == "REGENERATED":
        kwargs["supersedes_record_id"] = "some-earlier-record-id"
    rec = writer.write_retrospective_record(**kwargs)
    assert pl.evaluate_oos_eligibility(rec).eligible is False


def test_legacy_unlabeled_never_eligible():
    legacy_record = {
        "lottery_type": "DAILY_539",
        "target_draw": 100,
        "strategy_id": "daily539_f4cold",
        # no generation_mode key at all -- simulates a pre-P360A row
    }
    assert pl.classify_generation_mode(legacy_record) == pl.LEGACY_UNLABELED
    assert pl.evaluate_oos_eligibility(legacy_record).eligible is False


def test_live_but_inconsistent_witness_is_ineligible():
    # generation_mode says LIVE_PREDRAW but the witness fields, taken at face
    # value, do not actually satisfy no-look-ahead -- must still be rejected
    # by evaluate_oos_eligibility (it re-derives, never trusts the label alone).
    forged = {
        "record_kind": "PREDICTION",
        "generation_mode": "LIVE_PREDRAW",
        "predicted_at": "2026-07-03T10:00:00+00:00",
        "scheduled_draw_close_at": "2099-01-01T20:00:00+00:00",
        "target_draw": 150,
        "max_source_draw_at_generation": 150,  # NOT < target_draw
        "strategy_id": "x", "lottery_type": "POWER_LOTTO", "bet_index": 0,
    }
    assert pl.evaluate_oos_eligibility(forged).eligible is False


def test_predicted_at_not_before_close_is_ineligible():
    rec = {
        "record_kind": "PREDICTION",
        "generation_mode": "LIVE_PREDRAW",
        "predicted_at": "2026-07-03T21:00:00+00:00",
        "scheduled_draw_close_at": "2026-07-03T20:00:00+00:00",  # close already passed
        "target_draw": 150,
        "max_source_draw_at_generation": 149,
        "strategy_id": "x", "lottery_type": "POWER_LOTTO", "bet_index": 0,
    }
    assert pl.evaluate_oos_eligibility(rec).eligible is False


def test_duplicate_records_earliest_eligible_wins():
    base = dict(
        record_kind="PREDICTION",
        generation_mode="LIVE_PREDRAW",
        scheduled_draw_close_at="2099-01-01T20:00:00+00:00",
        target_draw=200,
        max_source_draw_at_generation=199,
        strategy_id="daily539_f4cold",
        lottery_type="DAILY_539",
        bet_index=0,
    )
    earlier = dict(base, predicted_at="2026-07-01T10:00:00+00:00")
    later = dict(base, predicted_at="2026-07-02T10:00:00+00:00")
    eligible = pl.select_eligible_records([later, earlier])
    assert len(eligible) == 1
    assert eligible[0]["predicted_at"] == "2026-07-01T10:00:00+00:00"


# ─── 6. Chain integrity: tamper + truncation ───────────────────────────────

def test_chain_detects_single_byte_tamper(tmp_path):
    writer = _writer(tmp_path)
    writer.write_live_prediction(**_live_kwargs(run_id="r1", target_draw=150, max_source_draw_at_generation=149))
    writer.write_live_prediction(**_live_kwargs(run_id="r2", target_draw=151, max_source_draw_at_generation=150))
    writer.write_live_prediction(**_live_kwargs(run_id="r3", target_draw=152, max_source_draw_at_generation=151))

    assert pl.verify_chain(writer.ledger_path).ok is True

    lines = writer.ledger_path.read_text(encoding="utf-8").splitlines()
    tampered = json.loads(lines[1])
    tampered["bet_index"] = 999  # mutate content without breaking JSON validity
    lines[1] = json.dumps(tampered)
    writer.ledger_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    result = pl.verify_chain(writer.ledger_path)
    assert result.ok is False
    assert result.first_broken_index == 1
    assert "record_hash mismatch" in result.reason


def test_chain_detects_truncation(tmp_path):
    writer = _writer(tmp_path)
    writer.write_live_prediction(**_live_kwargs(run_id="r1", target_draw=150, max_source_draw_at_generation=149))
    writer.write_live_prediction(**_live_kwargs(run_id="r2", target_draw=151, max_source_draw_at_generation=150))

    raw = writer.ledger_path.read_text(encoding="utf-8")
    lines = raw.splitlines()
    truncated = lines[0] + "\n" + lines[1][: len(lines[1]) // 2]  # cut the 2nd line mid-way
    writer.ledger_path.write_text(truncated, encoding="utf-8")

    result = pl.verify_chain(writer.ledger_path)
    assert result.ok is False
    assert "unparseable/truncated" in result.reason


def test_chain_detects_deleted_middle_record(tmp_path):
    writer = _writer(tmp_path)
    writer.write_live_prediction(**_live_kwargs(run_id="r1", target_draw=150, max_source_draw_at_generation=149))
    writer.write_live_prediction(**_live_kwargs(run_id="r2", target_draw=151, max_source_draw_at_generation=150))
    writer.write_live_prediction(**_live_kwargs(run_id="r3", target_draw=152, max_source_draw_at_generation=151))

    lines = writer.ledger_path.read_text(encoding="utf-8").splitlines()
    del lines[1]  # remove the middle record; chain of prev_record_hash should now break
    writer.ledger_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    result = pl.verify_chain(writer.ledger_path)
    assert result.ok is False
    assert "prev_record_hash mismatch" in result.reason


# ─── 7. Canonical DB untouched ──────────────────────────────────────────────

def test_ledger_path_never_canonical_db(tmp_path):
    with pytest.raises(pl.LedgerPathError):
        pl.PredrawLedgerWriter(ledger_path=tmp_path / "lottery_v2.db")
    with pytest.raises(pl.LedgerPathError):
        pl.PredrawLedgerWriter(ledger_path=tmp_path / "nested" / "lottery_v2.db")


def test_default_ledger_path_is_not_canonical_db_basename():
    assert pl.DEFAULT_LEDGER_PATH.name != "lottery_v2.db"
    assert pl.DEFAULT_LEDGER_PATH.suffix == ".jsonl"


def test_source_db_fingerprint_opens_temp_db_read_only(tmp_path):
    db_path = tmp_path / "temp_draws.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "CREATE TABLE draws (id INTEGER PRIMARY KEY, draw TEXT, date TEXT, "
        "lottery_type TEXT, numbers TEXT, special INTEGER)"
    )
    conn.executemany(
        "INSERT INTO draws (draw, date, lottery_type, numbers, special) VALUES (?, ?, ?, ?, ?)",
        [
            ("100", "2026-01-01", "POWER_LOTTO", "1,2,3,4,5,6", 7),
            ("99", "2025-12-28", "POWER_LOTTO", "2,3,4,5,6,7", 8),
            ("9", "2025-01-01", "POWER_LOTTO", "1,1,1,1,1,1".replace("1,1,1,1,1,1", "1,2,3,4,5,6"), 1),
        ],
    )
    conn.commit()
    conn.close()

    fp = pl.compute_source_db_fingerprint(str(db_path), lottery_types=("POWER_LOTTO",))
    # "100" > "99" numerically even though "99" > "100" lexicographically --
    # this is exactly the TEXT-ordering trap the project's own CLAUDE.md warns about.
    assert fp.per_lottery_max_draw["POWER_LOTTO"] == 100
    assert fp.row_count == 3

    max_draw = pl.compute_max_source_draw(str(db_path), "POWER_LOTTO")
    assert max_draw == 100

    # the read-only connection must not have left the temp DB writable-dirty in any odd way
    conn2 = sqlite3.connect(str(db_path))
    assert conn2.execute("SELECT COUNT(*) FROM draws").fetchone()[0] == 3
    conn2.close()


# ─── 8. Append-only surface ─────────────────────────────────────────────────

def test_no_update_or_delete_api_exists():
    public_methods = {
        name for name in dir(pl.PredrawLedgerWriter)
        if not name.startswith("_") and callable(getattr(pl.PredrawLedgerWriter, name))
    }
    assert public_methods == {"write_live_prediction", "write_retrospective_record", "write_settlement"}
    for forbidden in ("update", "delete", "edit", "overwrite", "rewrite"):
        assert not any(forbidden in m.lower() for m in public_methods)


def test_rerun_yields_new_record_not_overwrite(tmp_path):
    writer = _writer(tmp_path)
    rec1 = writer.write_live_prediction(**_live_kwargs(run_id="run-A"))
    rec2 = writer.write_live_prediction(**_live_kwargs(run_id="run-B"))

    assert rec1["record_id"] != rec2["record_id"]
    assert rec1["run_id"] != rec2["run_id"]
    all_records = pl.read_all_records(writer.ledger_path)
    assert len(all_records) == 2
    assert pl.verify_chain(writer.ledger_path).ok is True


# ─── 9. Settlement separation ───────────────────────────────────────────────

def test_settlement_does_not_mutate_prediction_record(tmp_path):
    writer = _writer(tmp_path)
    prediction = writer.write_live_prediction(**_live_kwargs())
    original_hash = prediction["record_hash"]

    writer.write_settlement(
        references_record_id=prediction["record_id"],
        actual_numbers=[1, 2, 3, 9, 10, 11],
        actual_special=7,
        hit_count=3,
        special_hit=True,
    )

    all_records = pl.read_all_records(writer.ledger_path)
    assert len(all_records) == 2
    reloaded_prediction = [r for r in all_records if r["record_kind"] == "PREDICTION"][0]
    assert reloaded_prediction["record_hash"] == original_hash  # byte-identical, untouched

    settlement = [r for r in all_records if r["record_kind"] == "SETTLEMENT"][0]
    assert settlement["references_record_id"] == prediction["record_id"]
    assert "generation_mode" not in settlement  # settlement never claims a generation mode
    assert pl.verify_chain(writer.ledger_path).ok is True


# ─── 10. Discipline checks ──────────────────────────────────────────────────

def test_naive_datetime_rejected_for_predicted_at(tmp_path):
    writer = _writer(tmp_path)
    with pytest.raises(pl.NaiveDatetimeError):
        writer.write_retrospective_record(
            generation_mode="BACKFILL",
            lottery_type="DAILY_539",
            target_draw=100,
            strategy_id="daily539_f4cold",
            strategy_version="v0.1",
            predicted_numbers=[1, 2, 3, 4, 5],
            predicted_special=None,
            bet_index=0,
            n_bets_total=1,
            run_id="backfill-1",
            generation_source="tools/backfill.py",
            predicted_at=datetime(2026, 1, 1, 10, 0, 0),  # naive, no tzinfo
        )


def test_naive_datetime_rejected_for_outcome_ingested_at(tmp_path):
    writer = _writer(tmp_path)
    with pytest.raises(pl.NaiveDatetimeError):
        writer.write_live_prediction(**_live_kwargs(
            outcome_ingested_at=datetime(2099, 1, 1, 10, 0, 0),  # naive
        ))


def test_draw_numbers_compare_as_integers_not_text(tmp_path):
    writer = _writer(tmp_path)
    # "99000104" > "99000055" as TEXT would still sort correctly here, but
    # a case like target="100" vs max_source="99" is the classic TEXT trap
    # ("100" < "99" lexicographically). Confirm int-cast discipline holds
    # even when both are passed in as strings.
    rec = writer.write_live_prediction(**_live_kwargs(
        target_draw="100", max_source_draw_at_generation="99",
    ))
    assert rec["target_draw"] == 100
    assert isinstance(rec["target_draw"], int)
    assert rec["max_source_draw_at_generation"] == 99
    assert isinstance(rec["max_source_draw_at_generation"], int)


def test_power_lotto_requires_predicted_special(tmp_path):
    writer = _writer(tmp_path)
    with pytest.raises(ValueError):
        writer.write_live_prediction(**_live_kwargs(predicted_special=None))


def test_daily539_forbids_predicted_special(tmp_path):
    writer = _writer(tmp_path)
    with pytest.raises(ValueError):
        writer.write_live_prediction(**_live_kwargs(
            lottery_type="DAILY_539",
            strategy_id="daily539_f4cold",
            predicted_numbers=[1, 2, 3, 4, 5],
            predicted_special=7,  # forbidden for DAILY_539
        ))


# ─── 11. Serialization round-trip + unknown-field tolerance ────────────────

def test_serialization_round_trip(tmp_path):
    writer = _writer(tmp_path)
    written = writer.write_live_prediction(**_live_kwargs())
    reloaded = pl.read_all_records(writer.ledger_path)[0]
    assert reloaded == written


def test_unknown_field_tolerance(tmp_path):
    ledger_path = tmp_path / "ledger.jsonl"
    payload = {
        "schema_version": "future-v2",
        "record_id": "abc-123",
        "record_kind": "PREDICTION",
        "lottery_type": "POWER_LOTTO",
        "generation_mode": "LIVE_PREDRAW",
        "predicted_at": "2026-07-03T10:00:00+00:00",
        "created_at": "2026-07-03T10:00:00+00:00",
        "target_draw": 150,
        "target_draw_date": "2099-01-01",
        "scheduled_draw_close_at": "2099-01-01T20:00:00+00:00",
        "schedule_rule_version": "test-v1",
        "history_cutoff_draw": None,
        "history_cutoff_date": None,
        "max_source_draw_at_generation": 149,
        "max_source_draw_date_at_generation": None,
        "source_db_fingerprint": None,
        "strategy_id": "power_precision_3bet",
        "strategy_version": "v0.1",
        "code_git_sha": None,
        "code_dirty_flag": None,
        "params_hash": None,
        "random_seed": None,
        "strategy_artifact_hash": None,
        "predicted_numbers": [1, 2, 3, 4, 5, 6],
        "predicted_special": 7,
        "bet_index": 0,
        "n_bets_total": 3,
        "run_id": "run-future",
        "generation_source": "future_tool.py",
        "supersedes_record_id": None,
        "a_field_from_a_future_schema_version": {"nested": "value", "n": 42},
    }
    prev_hash = None
    record_hash = pl.compute_record_hash(payload, prev_hash)
    full_record = dict(payload)
    full_record["prev_record_hash"] = prev_hash
    full_record["record_hash"] = record_hash
    with open(ledger_path, "w", encoding="utf-8") as f:
        f.write(json.dumps(full_record, sort_keys=True) + "\n")

    records = pl.read_all_records(ledger_path)
    assert len(records) == 1
    assert records[0]["a_field_from_a_future_schema_version"] == {"nested": "value", "n": 42}

    # chain verification must still pass -- the hash was computed over the
    # full actual payload, extra field included, so nothing looks tampered.
    assert pl.verify_chain(ledger_path).ok is True

    # and downstream readers (eligibility, mode classification) must not
    # crash just because an unrecognized field is present.
    assert pl.classify_generation_mode(records[0]) == "LIVE_PREDRAW"
    assert pl.evaluate_oos_eligibility(records[0]).eligible is True


# ─── 12. P361 dry-run audit ─────────────────────────────────────────────────

def test_p361_dry_run_never_reports_performance_fields():
    audit_field_names = {f.name for f in fields(pl.AuditReport)}
    forbidden = {"hit_rate", "edge", "roi", "p_value", "significance", "sharpe"}
    assert not (audit_field_names & forbidden)


def test_p361_dry_run_always_accumulating_and_counts_only(tmp_path):
    writer = _writer(tmp_path)
    # 2 eligible POWER_LOTTO records for power_precision_3bet
    writer.write_live_prediction(**_live_kwargs(target_draw=150, max_source_draw_at_generation=149, run_id="a"))
    writer.write_live_prediction(**_live_kwargs(target_draw=151, max_source_draw_at_generation=150, run_id="b"))
    # 1 BACKFILL record (must not count)
    writer.write_retrospective_record(
        generation_mode="BACKFILL", lottery_type="POWER_LOTTO", target_draw=140,
        strategy_id="power_precision_3bet", strategy_version="v0.1",
        predicted_numbers=[1, 2, 3, 4, 5, 6], predicted_special=7,
        bet_index=0, n_bets_total=3, run_id="bf-1", generation_source="tools/backfill.py",
    )

    records = pl.read_all_records(writer.ledger_path)
    report = pl.p361_dry_run_audit(records, minimum_n_by_lottery={"POWER_LOTTO": 150})

    assert report.status == "ACCUMULATING"
    assert report.total_eligible == 2
    assert report.per_strategy_eligible_counts == {"power_precision_3bet": 2}
    assert report.below_minimum is True  # 2 < 150


def test_p361_dry_run_below_minimum_false_when_reached():
    minimum = {"POWER_LOTTO": 1}
    eligible_record = {
        "record_kind": "PREDICTION", "generation_mode": "LIVE_PREDRAW",
        "predicted_at": "2026-07-01T10:00:00+00:00",
        "scheduled_draw_close_at": "2099-01-01T20:00:00+00:00",
        "target_draw": 150, "max_source_draw_at_generation": 149,
        "strategy_id": "power_precision_3bet", "lottery_type": "POWER_LOTTO", "bet_index": 0,
    }
    report = pl.p361_dry_run_audit([eligible_record], minimum_n_by_lottery=minimum)
    assert report.status == "ACCUMULATING"  # status is ALWAYS accumulating -- this function never promotes
    assert report.below_minimum is False
    assert report.total_eligible == 1
