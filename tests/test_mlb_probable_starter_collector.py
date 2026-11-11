"""
tests/test_mlb_probable_starter_collector.py
============================================
P202E — tests for the fixture-only, no-network probable-starter collector adapter
(``data/mlb_probable_starter_collector.py``) layered on the merged P202D snapshot
contract.

Covers (P202E Phase 7):
  A. import & dependency boundary   B. payload parsing      C. probable-starter mapping
  D. game status                    E. time safety          F. doubleheaders & revisions
  G. injected transport             H. persistence          I. integration guards

All writes use pytest tmp_path. No network. P202D module is reused unmodified.
"""
from __future__ import annotations

import ast
import copy
import inspect
import json
from pathlib import Path

import pytest


def _code_only(path: Path) -> str:
    """Module source with the docstring and comments stripped (code tokens only).

    Lets boundary checks scan executable code without false positives from the
    module docstring (which legitimately *names* the things it must NOT use).
    """
    src = path.read_text(encoding="utf-8")
    doc = ast.get_docstring(ast.parse(src), clean=False)
    if doc:
        src = src.replace(doc, "", 1)
    out = []
    for line in src.splitlines():
        if "#" in line:  # this module has no '#' inside string literals
            line = line[: line.index("#")]
        out.append(line)
    return "\n".join(out)

import data.mlb_probable_starter_collector as collector_mod
from data.mlb_probable_starter_collector import (
    COLLECTOR_PARSER_VERSION,
    CollectorResult,
    RejectedRecord,
    adapt_schedule_payload,
    collect_probable_starters,
)
from data.mlb_probable_starter_snapshots import (
    ProbableStarterSnapshot,
    SnapshotStoreError,
    load_snapshots,
)

FIXTURES_PATH = Path(__file__).parent / "fixtures" / "mlb_probable_starter_source_payload_fixtures.json"
_FIX = json.loads(FIXTURES_PATH.read_text(encoding="utf-8"))
CTX = _FIX["context"]


def payload(name: str) -> dict:
    return copy.deepcopy(_FIX["fixtures"][name]["payload"])


def adapt(name: str, **over):
    kw = dict(
        collected_at_utc=CTX["collected_at_utc"],
        information_cutoff_utc=CTX["information_cutoff_utc"],
        source_provider=CTX["source_provider"],
        source_endpoint_or_feed_id=CTX["source_endpoint_or_feed_id"],
    )
    kw.update(over)
    return adapt_schedule_payload(payload(name), **kw)


def fixed_transport(returning):
    def _t(request):
        return returning
    return _t


# ════════════════════════════════════════════════════════════════════════════
# A. Import & dependency boundary
# ════════════════════════════════════════════════════════════════════════════
def test_module_imports_and_is_stdlib_only():
    src = Path(collector_mod.__file__).read_text(encoding="utf-8")
    for banned in (
        "import requests", "import httpx", "import socket", "import urllib",
        "from urllib", "import aiohttp", "http.client", "import ssl",
    ):
        assert banned not in src, f"network import detected: {banned}"


def test_no_fetch_probable_starters_or_integration_imports():
    code = _code_only(Path(collector_mod.__file__))
    for banned in (
        "fetch_probable_starters", "statsapi.mlb.com", "mlb_daily_scheduler",
        "run_mlb_tsl_paper_recommendation", "mlb_paper_evaluator", "learning_eligible",
        "time.sleep", "while True", "threading", "Thread(",
    ):
        assert banned not in code, f"forbidden reference detected in code: {banned}"


def test_import_creates_no_runtime_path():
    assert not Path("data/mlb_probable_starters").exists()


def test_fixtures_are_synthetic_and_secret_free():
    blob = json.dumps(_FIX["fixtures"]).lower()
    for banned in ("token", "secret", "password", "api_key", "apikey", "authorization", "bearer"):
        assert banned not in blob
    assert "SYNTHETIC" in _FIX["description"].upper()


# ════════════════════════════════════════════════════════════════════════════
# B. Payload parsing
# ════════════════════════════════════════════════════════════════════════════
def test_valid_payload_produces_normalized_record():
    res = adapt("valid_scheduled_both")
    assert res.status == "ok"
    assert res.accepted_count == 1 and res.rejected_count == 0
    snap = res.accepted[0]
    assert isinstance(snap, ProbableStarterSnapshot)
    assert snap.game_pk == 990001
    assert snap.snapshot_status == "valid"
    assert snap.scheduled_start_utc == "2099-04-01T23:05:00+00:00"  # "Z" normalized
    assert snap.diagnostic_only is True and snap.production_ready is False
    assert snap.parser_version == COLLECTOR_PARSER_VERSION
    assert snap.home_probable_pitcher_id == 800001 and snap.away_probable_pitcher_id == 800002


def test_multi_game_deterministic_order_and_counts():
    res = adapt("multi_game_mixed")
    assert res.status == "ok"
    assert [s.game_pk for s in res.accepted] == [990101, 990102, 990103]
    assert res.accepted_count == 3 and res.rejected_count == 1
    assert res.partial_count == 1  # 990102 one-side missing
    assert res.rejected[0].reason == "missing_scheduled_start"  # 990104 has no gameDate


def test_malformed_top_level_payload_fails_closed():
    res = adapt("malformed_top_level")
    assert res.status == "malformed_payload" and res.accepted_count == 0


def test_non_dict_payload_fails_closed():
    res = adapt_schedule_payload(
        ["not", "an", "object"],
        collected_at_utc=CTX["collected_at_utc"],
        information_cutoff_utc=CTX["information_cutoff_utc"],
        source_provider=CTX["source_provider"],
        source_endpoint_or_feed_id=CTX["source_endpoint_or_feed_id"],
    )
    assert res.status == "malformed_payload" and res.accepted_count == 0


def test_malformed_game_reported_not_lost():
    res = adapt("malformed_game_record")
    assert res.accepted_count == 1 and res.accepted[0].game_pk == 990006
    assert res.rejected_count == 1 and res.rejected[0].reason == "malformed_game_record"


def test_missing_game_pk_rejected():
    res = adapt("missing_game_pk")
    assert res.accepted_count == 0 and res.rejected_count == 1
    assert res.rejected[0].reason == "missing_game_pk"


def test_missing_scheduled_start_rejected():
    res = adapt("missing_scheduled_start")
    assert res.accepted_count == 0 and res.rejected[0].reason == "missing_scheduled_start"


def test_missing_team_id_rejected():
    p = payload("valid_scheduled_both")
    p["dates"][0]["games"][0]["teams"]["home"]["team"] = {}
    res = adapt_schedule_payload(
        p, collected_at_utc=CTX["collected_at_utc"], information_cutoff_utc=CTX["information_cutoff_utc"],
        source_provider=CTX["source_provider"], source_endpoint_or_feed_id=CTX["source_endpoint_or_feed_id"],
    )
    assert res.accepted_count == 0 and "missing_home_team_id" in res.rejected[0].reason


# ════════════════════════════════════════════════════════════════════════════
# C. Probable-starter mapping
# ════════════════════════════════════════════════════════════════════════════
def test_one_side_missing_is_partial():
    res = adapt("one_side_missing")
    snap = res.accepted[0]
    assert snap.snapshot_status == "partial"
    assert snap.away_probable_pitcher_id is None and snap.away_pitcher_status == "tbd"
    assert res.partial_count == 1


def test_both_sides_tbd_is_partial():
    res = adapt("both_sides_tbd")
    snap = res.accepted[0]
    assert snap.snapshot_status == "partial"
    assert snap.home_pitcher_status == "tbd" and snap.away_pitcher_status == "tbd"


def test_changed_and_scratched_statuses_surfaced():
    assert adapt("starter_change").accepted[0].home_pitcher_status == "changed"
    assert adapt("scratched_starter").accepted[0].home_pitcher_status == "scratched"


def test_opener_status_surfaced_inline():
    p = payload("valid_scheduled_both")
    p["dates"][0]["games"][0]["teams"]["home"]["probableStatus"] = "opener"
    res = adapt_schedule_payload(
        p, collected_at_utc=CTX["collected_at_utc"], information_cutoff_utc=CTX["information_cutoff_utc"],
        source_provider=CTX["source_provider"], source_endpoint_or_feed_id=CTX["source_endpoint_or_feed_id"],
    )
    assert res.accepted[0].home_pitcher_status == "opener"


def test_actual_starter_markers_rejected():
    res = adapt("actual_starter_markers")
    assert res.accepted_count == 0 and res.rejected_count == 1
    assert "leakage_field_present" in res.rejected[0].reason


# ════════════════════════════════════════════════════════════════════════════
# D. Game status
# ════════════════════════════════════════════════════════════════════════════
def test_scheduled_accepted():
    assert adapt("valid_scheduled_both").accepted[0].game_status == "scheduled"


def test_delayed_surfaced():
    assert adapt("delayed_game").accepted[0].game_status == "delayed"


def test_postponed_surfaced():
    snap = adapt("postponed_game").accepted[0]
    assert snap.game_status == "postponed" and snap.snapshot_status == "postponed"


def test_cancelled_excluded_from_trusted_intake():
    snap = adapt("cancelled_game").accepted[0]
    assert snap.game_status == "cancelled" and snap.snapshot_status == "cancelled"


def test_final_game_rejected():
    res = adapt("completed_final_game")
    assert res.accepted_count == 0 and res.rejected_count == 1
    # rejected either by final-status or by leakage scan; both are valid fail-closed reasons
    assert res.rejected[0].reason in ("final_or_live_not_pregame",) or "leakage" in res.rejected[0].reason


def test_no_outcome_fields_in_normalized_record():
    snap = adapt("valid_scheduled_both").accepted[0]
    keys = set(vars(snap).keys())
    for forbidden in ("home_score", "away_score", "final_score", "result", "actual_winner", "learning_eligible"):
        assert forbidden not in keys


def test_unknown_status_rejected_inline():
    p = payload("valid_scheduled_both")
    p["dates"][0]["games"][0]["status"] = {"abstractGameState": "Other", "detailedState": "Mystery"}
    res = adapt_schedule_payload(
        p, collected_at_utc=CTX["collected_at_utc"], information_cutoff_utc=CTX["information_cutoff_utc"],
        source_provider=CTX["source_provider"], source_endpoint_or_feed_id=CTX["source_endpoint_or_feed_id"],
    )
    assert res.accepted_count == 0 and "unknown_game_status" in res.rejected[0].reason


# ════════════════════════════════════════════════════════════════════════════
# E. Time safety
# ════════════════════════════════════════════════════════════════════════════
def test_caller_cutoff_used():
    snap = adapt("valid_scheduled_both").accepted[0]
    assert snap.information_cutoff_utc == "2099-04-01T20:00:00+00:00"
    assert snap.collected_at_utc == "2099-04-01T19:30:00+00:00"


def test_cutoff_after_start_rejected():
    res = adapt("valid_scheduled_both", information_cutoff_utc="2099-04-02T00:00:00+00:00")
    assert res.accepted_count == 0 and "normalize_rejected" in res.rejected[0].reason


def test_collected_after_cutoff_rejected():
    res = adapt("valid_scheduled_both", collected_at_utc="2099-04-01T20:30:00+00:00")
    assert res.accepted_count == 0 and "normalize_rejected" in res.rejected[0].reason


def test_freshness_default_zero_and_explicit():
    assert adapt("valid_scheduled_both").accepted[0].source_freshness_seconds == 0
    p = payload("valid_scheduled_both")
    p["dates"][0]["games"][0]["sourceFreshnessSeconds"] = 1200
    res = adapt_schedule_payload(
        p, collected_at_utc=CTX["collected_at_utc"], information_cutoff_utc=CTX["information_cutoff_utc"],
        source_provider=CTX["source_provider"], source_endpoint_or_feed_id=CTX["source_endpoint_or_feed_id"],
    )
    assert res.accepted[0].source_freshness_seconds == 1200


def test_adapt_is_deterministic():
    a = adapt("valid_scheduled_both").accepted[0]
    b = adapt("valid_scheduled_both").accepted[0]
    assert a == b and a.payload_fingerprint == b.payload_fingerprint


# ════════════════════════════════════════════════════════════════════════════
# F. Doubleheaders & revisions
# ════════════════════════════════════════════════════════════════════════════
def test_doubleheader_games_distinct():
    g1 = adapt("doubleheader_game_1").accepted[0]
    g2 = adapt("doubleheader_game_2").accepted[0]
    assert g1.game_pk == 990021 and g1.doubleheader_game_number == 1
    assert g2.game_pk == 990022 and g2.doubleheader_game_number == 2


def test_single_game_doubleheader_number_zero():
    assert adapt("valid_scheduled_both").accepted[0].doubleheader_game_number == 0


def test_duplicate_in_payload_normalizes_twice():
    res = adapt("duplicate_game_record")
    assert res.accepted_count == 2
    assert res.accepted[0].payload_fingerprint == res.accepted[1].payload_fingerprint


# ════════════════════════════════════════════════════════════════════════════
# G. Injected transport
# ════════════════════════════════════════════════════════════════════════════
def test_transport_receives_expected_request():
    seen = {}

    def rec_transport(req):
        seen["req"] = req
        return payload("valid_scheduled_both")

    res = collect_probable_starters(
        transport=rec_transport, request={"date": "2099-04-01"},
        source_provider=CTX["source_provider"], source_endpoint_or_feed_id=CTX["source_endpoint_or_feed_id"],
        information_cutoff_utc=CTX["information_cutoff_utc"], collected_at_utc=CTX["collected_at_utc"],
    )
    assert seen["req"] == {"date": "2099-04-01"}
    assert res.status == "ok" and res.accepted_count == 1


def test_no_default_transport():
    sig = inspect.signature(collect_probable_starters)
    assert sig.parameters["transport"].default is inspect.Parameter.empty
    with pytest.raises(ValueError):
        collect_probable_starters(
            transport=None, request=None,
            source_provider=CTX["source_provider"], source_endpoint_or_feed_id=CTX["source_endpoint_or_feed_id"],
            information_cutoff_utc=CTX["information_cutoff_utc"], collected_at_utc=CTX["collected_at_utc"],
        )


def test_transport_exception_is_source_unavailable():
    def boom(req):
        raise RuntimeError("net down")

    res = collect_probable_starters(
        transport=boom, request=None,
        source_provider=CTX["source_provider"], source_endpoint_or_feed_id=CTX["source_endpoint_or_feed_id"],
        information_cutoff_utc=CTX["information_cutoff_utc"], collected_at_utc=CTX["collected_at_utc"],
    )
    assert res.status == "source_unavailable" and res.accepted_count == 0
    assert "transport_exception" in res.rejected[0].reason


def test_transport_returns_none_is_source_unavailable():
    res = collect_probable_starters(
        transport=fixed_transport(None), request=None,
        source_provider=CTX["source_provider"], source_endpoint_or_feed_id=CTX["source_endpoint_or_feed_id"],
        information_cutoff_utc=CTX["information_cutoff_utc"], collected_at_utc=CTX["collected_at_utc"],
    )
    assert res.status == "source_unavailable"


def test_malformed_transport_result_fails_closed():
    res = collect_probable_starters(
        transport=fixed_transport("garbage"), request=None,
        source_provider=CTX["source_provider"], source_endpoint_or_feed_id=CTX["source_endpoint_or_feed_id"],
        information_cutoff_utc=CTX["information_cutoff_utc"], collected_at_utc=CTX["collected_at_utc"],
    )
    assert res.status == "malformed_payload"


def test_explicit_source_unavailable_payload():
    res = collect_probable_starters(
        transport=fixed_transport(payload("source_unavailable")), request=None,
        source_provider=CTX["source_provider"], source_endpoint_or_feed_id=CTX["source_endpoint_or_feed_id"],
        information_cutoff_utc=CTX["information_cutoff_utc"], collected_at_utc=CTX["collected_at_utc"],
    )
    assert res.status == "source_unavailable"


def test_injected_clock_used_when_no_explicit_collected_at():
    res = collect_probable_starters(
        transport=fixed_transport(payload("valid_scheduled_both")), request=None,
        source_provider=CTX["source_provider"], source_endpoint_or_feed_id=CTX["source_endpoint_or_feed_id"],
        information_cutoff_utc=CTX["information_cutoff_utc"],
        clock=lambda: CTX["collected_at_utc"],
    )
    assert res.accepted[0].collected_at_utc == "2099-04-01T19:30:00+00:00"


def test_requires_collected_at_or_clock():
    with pytest.raises(ValueError):
        collect_probable_starters(
            transport=fixed_transport(payload("valid_scheduled_both")), request=None,
            source_provider=CTX["source_provider"], source_endpoint_or_feed_id=CTX["source_endpoint_or_feed_id"],
            information_cutoff_utc=CTX["information_cutoff_utc"],
        )


# ════════════════════════════════════════════════════════════════════════════
# H. Persistence
# ════════════════════════════════════════════════════════════════════════════
def test_no_output_path_means_no_write(tmp_path):
    res = collect_probable_starters(
        transport=fixed_transport(payload("valid_scheduled_both")), request=None,
        source_provider=CTX["source_provider"], source_endpoint_or_feed_id=CTX["source_endpoint_or_feed_id"],
        information_cutoff_utc=CTX["information_cutoff_utc"], collected_at_utc=CTX["collected_at_utc"],
    )
    assert res.appended_count == 0 and res.duplicate_count == 0
    assert list(tmp_path.iterdir()) == []


def test_explicit_tmp_path_persists(tmp_path):
    store = tmp_path / "snap.jsonl"
    res = collect_probable_starters(
        transport=fixed_transport(payload("valid_scheduled_both")), request=None,
        source_provider=CTX["source_provider"], source_endpoint_or_feed_id=CTX["source_endpoint_or_feed_id"],
        information_cutoff_utc=CTX["information_cutoff_utc"], collected_at_utc=CTX["collected_at_utc"],
        output_path=store,
    )
    assert res.appended_count == 1 and res.duplicate_count == 0
    assert len(load_snapshots(store)) == 1


def test_exact_duplicate_in_payload_not_appended_twice(tmp_path):
    store = tmp_path / "snap.jsonl"
    res = collect_probable_starters(
        transport=fixed_transport(payload("duplicate_game_record")), request=None,
        source_provider=CTX["source_provider"], source_endpoint_or_feed_id=CTX["source_endpoint_or_feed_id"],
        information_cutoff_utc=CTX["information_cutoff_utc"], collected_at_utc=CTX["collected_at_utc"],
        output_path=store,
    )
    assert res.accepted_count == 2
    assert res.appended_count == 1 and res.duplicate_count == 1
    assert len(load_snapshots(store)) == 1


def test_revision_appends(tmp_path):
    store = tmp_path / "snap.jsonl"
    collect_probable_starters(
        transport=fixed_transport(payload("valid_scheduled_both")), request=None,
        source_provider=CTX["source_provider"], source_endpoint_or_feed_id=CTX["source_endpoint_or_feed_id"],
        information_cutoff_utc=CTX["information_cutoff_utc"], collected_at_utc=CTX["collected_at_utc"],
        output_path=store,
    )
    # later observation with changed starter -> revision
    res2 = collect_probable_starters(
        transport=fixed_transport(payload("starter_change")), request=None,
        source_provider=CTX["source_provider"], source_endpoint_or_feed_id=CTX["source_endpoint_or_feed_id"],
        information_cutoff_utc="2099-04-01T21:30:00+00:00", collected_at_utc="2099-04-01T21:00:00+00:00",
        output_path=store,
    )
    assert res2.appended_count == 1
    recs = load_snapshots(store)
    assert len(recs) == 2
    assert {r["source_record_id"] for r in recs} == {"990001:0"}  # same game, two revisions


def test_malformed_existing_store_fails_closed(tmp_path):
    store = tmp_path / "snap.jsonl"
    store.write_text("{bad json}\n", encoding="utf-8")
    before = store.read_text(encoding="utf-8")
    with pytest.raises(SnapshotStoreError):
        collect_probable_starters(
            transport=fixed_transport(payload("valid_scheduled_both")), request=None,
            source_provider=CTX["source_provider"], source_endpoint_or_feed_id=CTX["source_endpoint_or_feed_id"],
            information_cutoff_utc=CTX["information_cutoff_utc"], collected_at_utc=CTX["collected_at_utc"],
            output_path=store,
        )
    assert store.read_text(encoding="utf-8") == before


def test_no_runtime_directory_created_during_persistence(tmp_path):
    store = tmp_path / "snap.jsonl"
    collect_probable_starters(
        transport=fixed_transport(payload("valid_scheduled_both")), request=None,
        source_provider=CTX["source_provider"], source_endpoint_or_feed_id=CTX["source_endpoint_or_feed_id"],
        information_cutoff_utc=CTX["information_cutoff_utc"], collected_at_utc=CTX["collected_at_utc"],
        output_path=store,
    )
    assert not Path("data/mlb_probable_starters").exists()


# ════════════════════════════════════════════════════════════════════════════
# I. Integration guards
# ════════════════════════════════════════════════════════════════════════════
def test_no_scheduler_recommendation_evaluator_imports():
    code = _code_only(Path(collector_mod.__file__))
    for banned in ("orchestrator.mlb_daily_scheduler", "run_mlb_tsl_paper_recommendation", "mlb_paper_evaluator"):
        assert banned not in code


def test_accepted_records_are_diagnostic_only():
    for snap in adapt("multi_game_mixed").accepted:
        assert snap.diagnostic_only is True and snap.production_ready is False
        assert not hasattr(snap, "learning_eligible")


def test_result_types_are_frozen_dataclasses():
    res = adapt("valid_scheduled_both")
    assert isinstance(res, CollectorResult)
    assert isinstance(res.rejected, tuple)
    with pytest.raises(Exception):
        res.accepted_count = 99  # frozen
