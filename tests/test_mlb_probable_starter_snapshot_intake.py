"""
tests/test_mlb_probable_starter_snapshot_intake.py
==================================================
P202D — tests for the fixture-only, no-network, append-only probable-starter
snapshot intake skeleton (``data/mlb_probable_starter_snapshots.py``).

Covers (per P202D Phase 9):
  A. schema & normalization        B. timestamp safety        C. identity & joins
  D. fingerprinting & idempotency  E. append-only persistence F. snapshot selection
  G. leakage prevention            H. no-network boundary

All writes use pytest tmp_path. No network, no real runtime data file.
"""
from __future__ import annotations

import inspect
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import data.mlb_probable_starter_snapshots as mod
from data.mlb_probable_starter_snapshots import (
    AppendResult,
    CANONICAL_RUNTIME_OUTPUT_PATH_HINT,
    CONTRACT_VERSION,
    GAME_STATUS_VALUES,
    PARSER_VERSION,
    PITCHER_STATUS_VALUES,
    ProbableStarterSnapshot,
    SNAPSHOT_STATUS_VALUES,
    SelectionResult,
    SnapshotStoreError,
    SnapshotValidationError,
    append_snapshot,
    compute_payload_fingerprint,
    load_snapshots,
    normalize_snapshot,
    select_canonical_snapshot,
    snapshot_dedup_key,
)

FIXTURES_PATH = Path(__file__).parent / "fixtures" / "probable_starter_snapshot_fixtures.json"


def _all_fixtures() -> dict:
    return json.loads(FIXTURES_PATH.read_text(encoding="utf-8"))["fixtures"]


def raw(name: str) -> dict:
    return dict(_all_fixtures()[name]["raw"])


# Common selection thresholds for trusted/valid scenarios.
_STALE_MAX = 86_400.0  # 24h
_MIN_LEAD = 1_800.0    # 30 min


# ════════════════════════════════════════════════════════════════════════════
# Fixture sanity
# ════════════════════════════════════════════════════════════════════════════
def test_fixture_file_is_synthetic_and_complete():
    data = json.loads(FIXTURES_PATH.read_text(encoding="utf-8"))
    assert data["schema_version"] == "p202d_probable_snapshot_fixture_v1"
    assert "SYNTHETIC" in data["description"].upper()
    fx = data["fixtures"]
    required = {
        "valid_both_side", "exact_duplicate", "starter_change", "post_cutoff_update",
        "scratched_starter", "one_side_missing", "both_sides_tbd",
        "doubleheader_game_1", "doubleheader_game_2",
        "postponed_reschedule_original", "postponed_marker", "postponed_reschedule_new",
        "cancelled_game", "stale_snapshot", "opener_bullpen_game",
        "malformed_timestamp", "malformed_identity", "actual_starter_substitution",
    }
    assert required.issubset(set(fx))
    # No fixture payload may carry secrets/tokens or claim official authorization.
    # (Scan only the fixture data, not the human-readable description.)
    blob = json.dumps(fx).lower()
    for banned in ("token", "secret", "password", "api_key", "apikey", "authorization", "bearer"):
        assert banned not in blob


@pytest.mark.parametrize("name", [
    n for n, v in _all_fixtures().items() if v["expect"] == "valid"
])
def test_valid_fixtures_normalize(name):
    snap = normalize_snapshot(raw(name))
    assert isinstance(snap, ProbableStarterSnapshot)
    assert snap.diagnostic_only is True
    assert snap.production_ready is False
    assert snap.contract_version == CONTRACT_VERSION
    assert snap.parser_version == PARSER_VERSION
    assert snap.snapshot_status in SNAPSHOT_STATUS_VALUES
    assert snap.home_pitcher_status in PITCHER_STATUS_VALUES
    assert snap.game_status in GAME_STATUS_VALUES


@pytest.mark.parametrize("name", [
    n for n, v in _all_fixtures().items() if v["expect"] == "reject"
])
def test_reject_fixtures_fail_closed(name):
    with pytest.raises(SnapshotValidationError):
        normalize_snapshot(raw(name))


# ════════════════════════════════════════════════════════════════════════════
# A. Schema & normalization
# ════════════════════════════════════════════════════════════════════════════
def test_normalized_record_has_exactly_contract_fields():
    snap = normalize_snapshot(raw("valid_both_side"))
    keys = set(vars(snap).keys())
    expected = {
        "contract_version", "source_provider", "source_endpoint_or_feed_id",
        "source_record_id", "payload_fingerprint", "collected_at_utc",
        "information_cutoff_utc", "game_pk", "scheduled_start_utc",
        "official_game_date", "doubleheader_game_number", "home_team_id",
        "away_team_id", "home_probable_pitcher_id", "home_probable_pitcher_name",
        "away_probable_pitcher_id", "away_probable_pitcher_name",
        "home_pitcher_status", "away_pitcher_status", "game_status",
        "snapshot_status", "source_freshness_seconds", "parser_version",
        "diagnostic_only", "production_ready",
    }
    assert keys == expected


def test_normalization_is_deterministic():
    a = normalize_snapshot(raw("valid_both_side"))
    b = normalize_snapshot(raw("valid_both_side"))
    assert a == b
    assert a.payload_fingerprint == b.payload_fingerprint


@pytest.mark.parametrize("missing", [
    "game_pk", "scheduled_start_utc", "collected_at_utc", "information_cutoff_utc",
    "home_team_id", "away_team_id", "source_provider", "source_record_id",
    "official_game_date", "doubleheader_game_number", "source_freshness_seconds",
])
def test_required_field_missing_fails_closed(missing):
    r = raw("valid_both_side")
    r.pop(missing, None)
    with pytest.raises(SnapshotValidationError):
        normalize_snapshot(r)


def test_bad_pitcher_status_rejected():
    r = raw("valid_both_side")
    r["home_pitcher_status"] = "as_played"
    with pytest.raises(SnapshotValidationError):
        normalize_snapshot(r)


def test_bad_game_status_rejected():
    r = raw("valid_both_side")
    r["game_status"] = "final"
    with pytest.raises(SnapshotValidationError):
        normalize_snapshot(r)


def test_valid_pitcher_status_set_matches_contract():
    assert PITCHER_STATUS_VALUES == frozenset({
        "announced", "probable", "confirmed", "changed", "scratched",
        "opener", "bullpen_game", "tbd", "unavailable",
    })
    assert SNAPSHOT_STATUS_VALUES == frozenset({
        "valid", "partial", "stale", "superseded", "postponed",
        "cancelled", "malformed", "source_unavailable",
    })
    assert {"scheduled", "postponed", "cancelled", "delayed", "suspended"}.issubset(GAME_STATUS_VALUES)


def test_diagnostic_invariants_forced_and_claims_rejected():
    snap = normalize_snapshot(raw("valid_both_side"))
    assert snap.diagnostic_only is True and snap.production_ready is False
    for bad in ({"production_ready": True}, {"diagnostic_only": False}, {"learning_eligible": True}):
        r = raw("valid_both_side")
        r.update(bad)
        with pytest.raises(SnapshotValidationError):
            normalize_snapshot(r)


def test_freshness_must_be_non_negative_int():
    for bad in (-1, "1800", 1800.0, True):
        r = raw("valid_both_side")
        r["source_freshness_seconds"] = bad
        with pytest.raises(SnapshotValidationError):
            normalize_snapshot(r)


def test_snapshot_status_derivation():
    assert normalize_snapshot(raw("valid_both_side")).snapshot_status == "valid"
    assert normalize_snapshot(raw("one_side_missing")).snapshot_status == "partial"
    assert normalize_snapshot(raw("both_sides_tbd")).snapshot_status == "partial"
    assert normalize_snapshot(raw("postponed_marker")).snapshot_status == "postponed"
    assert normalize_snapshot(raw("cancelled_game")).snapshot_status == "cancelled"


# ════════════════════════════════════════════════════════════════════════════
# B. Timestamp safety
# ════════════════════════════════════════════════════════════════════════════
def test_naive_timestamp_rejected():
    r = raw("valid_both_side")
    r["collected_at_utc"] = "2099-04-01T19:30:00"  # no tz
    with pytest.raises(SnapshotValidationError):
        normalize_snapshot(r)


def test_non_utc_offset_rejected():
    r = raw("valid_both_side")
    r["scheduled_start_utc"] = "2099-04-01T23:05:00+08:00"
    with pytest.raises(SnapshotValidationError):
        normalize_snapshot(r)


def test_cutoff_must_be_strictly_before_start():
    r = raw("valid_both_side")
    r["information_cutoff_utc"] = "2099-04-01T23:05:00+00:00"  # == start
    with pytest.raises(SnapshotValidationError):
        normalize_snapshot(r)
    r["information_cutoff_utc"] = "2099-04-01T23:30:00+00:00"  # after start
    with pytest.raises(SnapshotValidationError):
        normalize_snapshot(r)


def test_collected_not_after_cutoff():
    r = raw("valid_both_side")
    r["collected_at_utc"] = "2099-04-01T20:30:00+00:00"  # after cutoff 20:00
    with pytest.raises(SnapshotValidationError):
        normalize_snapshot(r)


def test_official_date_incompatible_rejected():
    r = raw("valid_both_side")
    r["official_game_date"] = "2099-05-15"  # far from scheduled 2099-04-01
    with pytest.raises(SnapshotValidationError):
        normalize_snapshot(r)


def test_timestamps_normalized_to_utc_iso():
    snap = normalize_snapshot(raw("valid_both_side"))
    assert snap.collected_at_utc.endswith("+00:00")
    assert snap.scheduled_start_utc == "2099-04-01T23:05:00+00:00"


# ════════════════════════════════════════════════════════════════════════════
# C. Identity & joins
# ════════════════════════════════════════════════════════════════════════════
def test_same_team_ids_rejected():
    with pytest.raises(SnapshotValidationError):
        normalize_snapshot(raw("malformed_identity"))


def test_doubleheader_number_validation():
    for bad in (-1, 3, "1", 1.0, True):
        r = raw("doubleheader_game_1")
        r["doubleheader_game_number"] = bad
        with pytest.raises(SnapshotValidationError):
            normalize_snapshot(r)


def test_doubleheader_games_remain_independent(tmp_path):
    store = tmp_path / "snap.jsonl"
    append_snapshot(normalize_snapshot(raw("doubleheader_game_1")), store)
    append_snapshot(normalize_snapshot(raw("doubleheader_game_2")), store)
    recs = load_snapshots(store)
    assert len(recs) == 2

    r1 = select_canonical_snapshot(
        recs, game_pk=990021, doubleheader_game_number=1,
        target_information_cutoff_utc="2099-04-05T17:00:00+00:00",
        stale_max_seconds=_STALE_MAX, min_lead_seconds=_MIN_LEAD,
    )
    assert r1.trusted and r1.snapshot["game_pk"] == 990021
    # Same game_pk but wrong dh number -> no match (date/team alone never substitutes).
    r_wrong = select_canonical_snapshot(
        recs, game_pk=990021, doubleheader_game_number=2,
        target_information_cutoff_utc="2099-04-05T17:00:00+00:00",
        stale_max_seconds=_STALE_MAX, min_lead_seconds=_MIN_LEAD,
    )
    assert not r_wrong.trusted and r_wrong.status == "no_matching_game"


# ════════════════════════════════════════════════════════════════════════════
# D. Fingerprinting & idempotency
# ════════════════════════════════════════════════════════════════════════════
def test_fingerprint_is_key_order_independent():
    r = raw("valid_both_side")
    reordered = {k: r[k] for k in reversed(list(r.keys()))}
    assert normalize_snapshot(r).payload_fingerprint == normalize_snapshot(reordered).payload_fingerprint


def test_fingerprint_changes_with_substantive_change():
    base = normalize_snapshot(raw("valid_both_side")).payload_fingerprint
    r = raw("valid_both_side")
    r["home_probable_pitcher_id"] = 800999
    assert normalize_snapshot(r).payload_fingerprint != base


def test_fingerprint_prefixed_sha256():
    fp = normalize_snapshot(raw("valid_both_side")).payload_fingerprint
    assert fp.startswith("sha256:") and len(fp) == len("sha256:") + 64


def test_dedup_key_distinguishes_revision_from_duplicate():
    a = normalize_snapshot(raw("valid_both_side"))
    dup = normalize_snapshot(raw("exact_duplicate"))
    rev = normalize_snapshot(raw("starter_change"))
    assert snapshot_dedup_key(a) == snapshot_dedup_key(dup)
    assert snapshot_dedup_key(a) != snapshot_dedup_key(rev)


# ════════════════════════════════════════════════════════════════════════════
# E. Append-only persistence
# ════════════════════════════════════════════════════════════════════════════
def test_append_new_then_idempotent_duplicate(tmp_path):
    store = tmp_path / "snap.jsonl"
    r1 = append_snapshot(normalize_snapshot(raw("valid_both_side")), store)
    assert r1.appended and r1.status == "appended_new" and r1.total_records == 1
    r2 = append_snapshot(normalize_snapshot(raw("exact_duplicate")), store)
    assert not r2.appended and r2.status == "idempotent_duplicate" and r2.total_records == 1
    assert len(store.read_text(encoding="utf-8").strip().splitlines()) == 1


def test_revision_appends_and_preserves_prior(tmp_path):
    store = tmp_path / "snap.jsonl"
    append_snapshot(normalize_snapshot(raw("valid_both_side")), store)
    first_line = store.read_text(encoding="utf-8")
    res = append_snapshot(normalize_snapshot(raw("starter_change")), store)
    assert res.appended and res.status == "appended_revision" and res.total_records == 2
    content = store.read_text(encoding="utf-8")
    assert content.startswith(first_line)  # original line untouched
    recs = load_snapshots(store)
    assert {r["source_record_id"] for r in recs} == {"rec-990001-c1", "rec-990001-c2"}


def test_append_is_utf8_jsonl_one_object_per_line(tmp_path):
    store = tmp_path / "snap.jsonl"
    append_snapshot(normalize_snapshot(raw("valid_both_side")), store)
    append_snapshot(normalize_snapshot(raw("starter_change")), store)
    for line in store.read_text(encoding="utf-8").strip().splitlines():
        obj = json.loads(line)
        assert isinstance(obj, dict) and "game_pk" in obj


def test_append_has_no_default_path():
    sig = inspect.signature(append_snapshot)
    assert sig.parameters["path"].default is inspect.Parameter.empty


def test_append_parent_dir_must_exist(tmp_path):
    missing = tmp_path / "does_not_exist" / "snap.jsonl"
    with pytest.raises(SnapshotStoreError):
        append_snapshot(normalize_snapshot(raw("valid_both_side")), missing)


def test_malformed_existing_store_fails_closed_without_alteration(tmp_path):
    store = tmp_path / "snap.jsonl"
    store.write_text("{not valid json}\n", encoding="utf-8")
    before = store.read_text(encoding="utf-8")
    with pytest.raises(SnapshotStoreError):
        load_snapshots(store)
    with pytest.raises(SnapshotStoreError):
        append_snapshot(normalize_snapshot(raw("valid_both_side")), store)
    assert store.read_text(encoding="utf-8") == before  # file untouched


def test_append_deterministic_repeat(tmp_path):
    store_a = tmp_path / "a.jsonl"
    store_b = tmp_path / "b.jsonl"
    for store in (store_a, store_b):
        append_snapshot(normalize_snapshot(raw("valid_both_side")), store)
        append_snapshot(normalize_snapshot(raw("starter_change")), store)
    assert store_a.read_text(encoding="utf-8") == store_b.read_text(encoding="utf-8")


def test_load_missing_file_returns_empty(tmp_path):
    assert load_snapshots(tmp_path / "nope.jsonl") == []


# ════════════════════════════════════════════════════════════════════════════
# F. Snapshot selection
# ════════════════════════════════════════════════════════════════════════════
def _store_with(tmp_path, *names):
    store = tmp_path / "snap.jsonl"
    for n in names:
        append_snapshot(normalize_snapshot(raw(n)), store)
    return load_snapshots(store)


def test_select_trusted_latest_pre_cutoff(tmp_path):
    recs = _store_with(tmp_path, "valid_both_side")
    res = select_canonical_snapshot(
        recs, game_pk=990001, doubleheader_game_number=0,
        target_information_cutoff_utc="2099-04-01T20:00:00+00:00",
        stale_max_seconds=_STALE_MAX, min_lead_seconds=_MIN_LEAD,
    )
    assert res.trusted and res.status == "trusted"
    assert res.snapshot["source_record_id"] == "rec-990001-c1"


def test_post_cutoff_update_excluded_for_earlier_cutoff(tmp_path):
    recs = _store_with(tmp_path, "valid_both_side", "post_cutoff_update")
    res = select_canonical_snapshot(
        recs, game_pk=990001, doubleheader_game_number=0,
        target_information_cutoff_utc="2099-04-01T20:00:00+00:00",
        stale_max_seconds=_STALE_MAX, min_lead_seconds=_MIN_LEAD,
    )
    assert res.trusted
    assert res.snapshot["source_record_id"] == "rec-990001-c1"  # not the 22:30 update


def test_changed_starter_surfaced(tmp_path):
    recs = _store_with(tmp_path, "valid_both_side", "starter_change")
    res = select_canonical_snapshot(
        recs, game_pk=990001, doubleheader_game_number=0,
        target_information_cutoff_utc="2099-04-01T22:00:00+00:00",
        stale_max_seconds=_STALE_MAX, min_lead_seconds=_MIN_LEAD,
    )
    assert not res.trusted and res.status == "changed"
    assert res.snapshot["source_record_id"] == "rec-990001-c2"


def test_scratched_surfaced(tmp_path):
    recs = _store_with(tmp_path, "scratched_starter")
    res = select_canonical_snapshot(
        recs, game_pk=990002, doubleheader_game_number=0,
        target_information_cutoff_utc="2099-04-02T20:00:00+00:00",
        stale_max_seconds=_STALE_MAX, min_lead_seconds=_MIN_LEAD,
    )
    assert not res.trusted and res.status == "scratched"


def test_opener_surfaced(tmp_path):
    recs = _store_with(tmp_path, "opener_bullpen_game")
    res = select_canonical_snapshot(
        recs, game_pk=990050, doubleheader_game_number=0,
        target_information_cutoff_utc="2099-06-10T20:00:00+00:00",
        stale_max_seconds=_STALE_MAX, min_lead_seconds=_MIN_LEAD,
    )
    assert not res.trusted and res.status == "opener_bullpen"


def test_one_side_missing_fails_closed(tmp_path):
    recs = _store_with(tmp_path, "one_side_missing")
    res = select_canonical_snapshot(
        recs, game_pk=990003, doubleheader_game_number=0,
        target_information_cutoff_utc="2099-04-03T20:00:00+00:00",
        stale_max_seconds=_STALE_MAX, min_lead_seconds=_MIN_LEAD,
    )
    assert not res.trusted and res.status == "one_side_missing"


def test_both_sides_tbd_fails_closed(tmp_path):
    recs = _store_with(tmp_path, "both_sides_tbd")
    res = select_canonical_snapshot(
        recs, game_pk=990004, doubleheader_game_number=0,
        target_information_cutoff_utc="2099-04-04T20:00:00+00:00",
        stale_max_seconds=_STALE_MAX, min_lead_seconds=_MIN_LEAD,
    )
    assert not res.trusted and res.status == "both_sides_tbd"


def test_cancelled_never_trusted(tmp_path):
    recs = _store_with(tmp_path, "cancelled_game")
    res = select_canonical_snapshot(
        recs, game_pk=990031, doubleheader_game_number=0,
        target_information_cutoff_utc="2099-05-03T20:00:00+00:00",
        stale_max_seconds=_STALE_MAX, min_lead_seconds=_MIN_LEAD,
    )
    assert not res.trusted and res.status == "cancelled"


def test_stale_fails_closed(tmp_path):
    recs = _store_with(tmp_path, "stale_snapshot")
    res = select_canonical_snapshot(
        recs, game_pk=990040, doubleheader_game_number=0,
        target_information_cutoff_utc="2099-06-01T22:00:00+00:00",
        stale_max_seconds=3600.0, min_lead_seconds=_MIN_LEAD,
    )
    assert not res.trusted and res.status == "stale"


def test_insufficient_lead_time(tmp_path):
    recs = _store_with(tmp_path, "valid_both_side")
    # 5 minutes before start -> below 30-min lead.
    res = select_canonical_snapshot(
        recs, game_pk=990001, doubleheader_game_number=0,
        target_information_cutoff_utc="2099-04-01T23:00:00+00:00",
        stale_max_seconds=_STALE_MAX, min_lead_seconds=_MIN_LEAD,
    )
    assert not res.trusted and res.status == "insufficient_lead_time"


def test_cutoff_after_start_rejected(tmp_path):
    recs = _store_with(tmp_path, "valid_both_side")
    res = select_canonical_snapshot(
        recs, game_pk=990001, doubleheader_game_number=0,
        target_information_cutoff_utc="2099-04-02T00:00:00+00:00",
        stale_max_seconds=_STALE_MAX, min_lead_seconds=_MIN_LEAD,
    )
    assert not res.trusted and res.status == "insufficient_lead_time"


def test_no_matching_game(tmp_path):
    recs = _store_with(tmp_path, "valid_both_side")
    res = select_canonical_snapshot(
        recs, game_pk=999999, doubleheader_game_number=0,
        target_information_cutoff_utc="2099-04-01T20:00:00+00:00",
        stale_max_seconds=_STALE_MAX, min_lead_seconds=_MIN_LEAD,
    )
    assert not res.trusted and res.status == "no_matching_game"


def test_selection_accepts_dataclass_records():
    snaps = [normalize_snapshot(raw("valid_both_side"))]
    res = select_canonical_snapshot(
        snaps, game_pk=990001, doubleheader_game_number=0,
        target_information_cutoff_utc="2099-04-01T20:00:00+00:00",
        stale_max_seconds=_STALE_MAX, min_lead_seconds=_MIN_LEAD,
    )
    assert res.trusted


def test_postponement_history_surfaced_not_mixed(tmp_path):
    recs = _store_with(
        tmp_path,
        "postponed_reschedule_original", "postponed_marker", "postponed_reschedule_new",
    )
    assert len(recs) == 3
    # Before postponement: original trusted (date 05-01).
    r_orig = select_canonical_snapshot(
        recs, game_pk=990030, doubleheader_game_number=0,
        target_information_cutoff_utc="2099-05-01T20:00:00+00:00",
        stale_max_seconds=_STALE_MAX, min_lead_seconds=_MIN_LEAD,
    )
    assert r_orig.trusted and r_orig.snapshot["scheduled_start_utc"] == "2099-05-01T23:00:00+00:00"
    # After postponement marker but before reschedule: surfaced as postponed.
    r_post = select_canonical_snapshot(
        recs, game_pk=990030, doubleheader_game_number=0,
        target_information_cutoff_utc="2099-05-01T22:30:00+00:00",
        stale_max_seconds=_STALE_MAX, min_lead_seconds=_MIN_LEAD,
    )
    assert not r_post.trusted and r_post.status == "postponed"
    # After reschedule: new scheduled_start trusted (date 05-02).
    r_new = select_canonical_snapshot(
        recs, game_pk=990030, doubleheader_game_number=0,
        target_information_cutoff_utc="2099-05-02T20:00:00+00:00",
        stale_max_seconds=_STALE_MAX, min_lead_seconds=_MIN_LEAD,
    )
    assert r_new.trusted and r_new.snapshot["scheduled_start_utc"] == "2099-05-02T23:00:00+00:00"


def test_selection_requires_caller_thresholds():
    snaps = [normalize_snapshot(raw("valid_both_side"))]
    for bad in (-1, "x", True):
        with pytest.raises(SnapshotValidationError):
            select_canonical_snapshot(
                snaps, game_pk=990001, doubleheader_game_number=0,
                target_information_cutoff_utc="2099-04-01T20:00:00+00:00",
                stale_max_seconds=bad, min_lead_seconds=_MIN_LEAD,
            )


# ════════════════════════════════════════════════════════════════════════════
# G. Leakage prevention
# ════════════════════════════════════════════════════════════════════════════
def test_actual_starter_substitution_rejected():
    with pytest.raises(SnapshotValidationError):
        normalize_snapshot(raw("actual_starter_substitution"))


@pytest.mark.parametrize("field,value", [
    ("home_score", 5), ("away_score", 3), ("final_score", "5-3"),
    ("actual_winner", "home"), ("result", "home_win"), ("box_score", {}),
    ("home_actual_starter_id", 1), ("as_played", True),
])
def test_postgame_and_actual_fields_rejected(field, value):
    r = raw("valid_both_side")
    r[field] = value
    with pytest.raises(SnapshotValidationError):
        normalize_snapshot(r)


def test_asplayed_provider_rejected():
    for marker in ("mlb_2025_asplayed", "as_played_feed", "actual_starters_api", "postgame_scrape"):
        r = raw("valid_both_side")
        r["source_provider"] = marker
        with pytest.raises(SnapshotValidationError):
            normalize_snapshot(r)


def test_normalized_schema_has_no_outcome_or_actual_fields():
    snap = normalize_snapshot(raw("valid_both_side"))
    keys = set(vars(snap).keys())
    for forbidden in ("home_win", "final_score", "actual_winner", "home_actual_starter_id",
                      "result", "box_score", "learning_eligible"):
        assert forbidden not in keys


def test_postgame_collected_update_not_selected_for_pregame_cutoff(tmp_path):
    # A snapshot collected after the game start can never be selected for a pregame cutoff.
    recs = _store_with(tmp_path, "valid_both_side", "post_cutoff_update")
    res = select_canonical_snapshot(
        recs, game_pk=990001, doubleheader_game_number=0,
        target_information_cutoff_utc="2099-04-01T20:00:00+00:00",
        stale_max_seconds=_STALE_MAX, min_lead_seconds=_MIN_LEAD,
    )
    assert res.snapshot["collected_at_utc"] <= "2099-04-01T20:00:00+00:00"


# ════════════════════════════════════════════════════════════════════════════
# H. No-network boundary
# ════════════════════════════════════════════════════════════════════════════
def test_module_has_no_network_imports():
    src = Path(mod.__file__).read_text(encoding="utf-8")
    for banned in (
        "import requests", "import httpx", "import socket", "import urllib",
        "from urllib", "import aiohttp", "http.client", "import ssl",
    ):
        assert banned not in src, f"network import detected: {banned}"


def test_module_import_creates_no_runtime_file():
    # The canonical runtime path is a documentation hint only; nothing is written on import.
    assert isinstance(CANONICAL_RUNTIME_OUTPUT_PATH_HINT, str)
    assert not Path(CANONICAL_RUNTIME_OUTPUT_PATH_HINT).exists()


def test_normalize_and_select_touch_no_filesystem(tmp_path, monkeypatch):
    # normalize + select must not open files; chdir into an empty dir and ensure none appear.
    monkeypatch.chdir(tmp_path)
    snaps = [normalize_snapshot(raw("valid_both_side"))]
    select_canonical_snapshot(
        snaps, game_pk=990001, doubleheader_game_number=0,
        target_information_cutoff_utc="2099-04-01T20:00:00+00:00",
        stale_max_seconds=_STALE_MAX, min_lead_seconds=_MIN_LEAD,
    )
    assert list(tmp_path.iterdir()) == []
