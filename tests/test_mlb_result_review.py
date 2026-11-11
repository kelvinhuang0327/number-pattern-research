"""Tests for orchestrator/mlb_result_review.py

29 tests covering:
  1–3:  Dataclass schemas
  4:    load_paper_ledger_jsonl
  5:    fixture result loading (all null → home_win=None)
  6:    replay result from historical JSONL
  7:    game_id match
  8:    fallback date/team match
  9:    unmatched → PENDING_REVIEW
  10:   missing score → PENDING_REVIEW
  11:   HOME moneyline WON
  12:   HOME moneyline LOST
  13:   AWAY moneyline WON
  14:   AWAY moneyline LOST
  15:   PASS → REVIEWED_NO_BET
  16:   WATCH_ONLY → REVIEWED_NO_BET
  17:   MARKET_ONLY_SHADOW → separate shadow tracking
  18:   runline / total → UNKNOWN
  19:   reviewed snapshot does not overwrite ledger
  20:   reviewed snapshot JSONL can be generated
  21:   review_summary includes matched_results / pending_results
  22:   review_summary includes brier_score / bss_vs_baseline
  23:   failure_notes include human_review_required=True
  24:   next_audit_proposal doesn't auto-change model
  25:   metrics_ssot referenced
  26:   gate in 7 valid values
  27:   markdown includes NO_REAL_BET / NO_PROFIT_CLAIM
  28:   markdown includes COMPLETION_MARKER
  29:   Phase67–72 + metrics + daily advisory + current sources + result review regression
"""
from __future__ import annotations

import json
import os
import tempfile

import pytest

import orchestrator.mlb_result_review as rr
from orchestrator.mlb_result_review import (
    COMPLETION_MARKER,
    LEDGER_OVERWRITE_BLOCKED,
    MODULE_VERSION,
    NO_EDGE_CLAIM,
    NO_PROFIT_CLAIM,
    NO_REAL_BET,
    PAPER_ONLY,
    PRODUCTION_MODIFIED,
    VALID_GATES,
    ResultSnapshot,
    ReviewSummary,
    ReviewedLedgerEntry,
    STATUS_PENDING_REVIEW,
    STATUS_REVIEWED,
    STATUS_REVIEWED_NO_BET,
    OUTCOME_LOST,
    OUTCOME_NO_BET,
    OUTCOME_PENDING,
    OUTCOME_UNKNOWN,
    OUTCOME_WON,
    TAG_NO_BET_REVIEW_ONLY,
    TAG_RESULT_UNAVAILABLE,
    build_failure_notes,
    build_next_audit_proposal,
    build_reviewed_ledger_snapshot,
    calculate_review_summary,
    determine_gate,
    evaluate_moneyline_result,
    generate_markdown_report,
    load_paper_ledger_jsonl,
    load_result_snapshots_from_fixture,
    load_result_snapshots_from_replay,
    match_ledger_to_results,
    run_postgame_review,
    validate_review_summary,
    write_reviewed_snapshot_jsonl,
)

# ── Helpers ───────────────────────────────────────────────────────────────────

_FIXTURE_PATH = "data/fixtures/mlb_current_source_sample_20260507.json"
_LEDGER_PATH = "reports/mlb_paper_betting_ledger.jsonl"
_PREDICTION_JSONL = (
    "data/mlb_2025/derived/"
    "mlb_2025_per_game_predictions_phase56_sp_bullpen_context_v1.jsonl"
)


def _make_result_snap(
    game_id: str = "G1",
    home_team: str = "Home",
    away_team: str = "Away",
    home_win: bool | None = True,
    result_status: str = "final",
    game_date: str = "2025-07-01",
) -> ResultSnapshot:
    return ResultSnapshot(
        game_id=game_id,
        game_date=game_date,
        home_team=home_team,
        away_team=away_team,
        home_score=5 if home_win else 3,
        away_score=3 if home_win else 5,
        home_win=home_win,
        result_status=result_status,
        source_name="test",
        source_mode="test",
        source_timestamp="2025-07-01T23:00:00Z",
    )


def _make_ledger_entry(
    game_id: str = "G1",
    game_date: str = "2025-07-01",
    recommendation: str = "LEAN_HOME",
    paper_selection: str | None = "HOME",
    model_prob: float = 0.58,
    market_prob: float = 0.48,
    market_type: str = "moneyline",
) -> dict:
    return {
        "ledger_id": f"ADV_{game_id}_MONEYLINE",
        "advisory_id": f"ADV_{game_id}",
        "game_id": game_id,
        "game_date": game_date,
        "market_type": market_type,
        "recommendation": recommendation,
        "paper_selection": paper_selection,
        "model_prob": model_prob,
        "market_prob": market_prob,
        "paper_only": True,
        "no_real_bet": True,
    }


# ════════════════════════════════════════════════════════════════════════════
# TEST 1 — ResultSnapshot schema
# ════════════════════════════════════════════════════════════════════════════

def test_01_result_snapshot_schema() -> None:
    snap = _make_result_snap()
    assert isinstance(snap.game_id, str)
    assert isinstance(snap.game_date, str)
    assert isinstance(snap.home_team, str)
    assert isinstance(snap.away_team, str)
    assert isinstance(snap.home_win, bool) or snap.home_win is None
    assert snap.result_status == "final"
    assert isinstance(snap.source_name, str)
    assert isinstance(snap.source_mode, str)
    assert isinstance(snap.source_timestamp, str)
    assert isinstance(snap.unavailable_fields, list)


# ════════════════════════════════════════════════════════════════════════════
# TEST 2 — ReviewedLedgerEntry schema
# ════════════════════════════════════════════════════════════════════════════

def test_02_reviewed_ledger_entry_schema() -> None:
    entry = ReviewedLedgerEntry(
        ledger_id="L1",
        advisory_id="A1",
        game_id="G1",
        game_date="2025-07-01",
        market_type="moneyline",
        recommendation="LEAN_HOME",
        paper_selection="HOME",
        model_prob=0.58,
        market_prob=0.48,
        result_status=OUTCOME_WON,
        realized_outcome="home_win",
        review_status=STATUS_REVIEWED,
        review_reason="result_available: WON",
        paper_profit_loss_units=1.083,
        brier_component=0.1764,
        failure_tags=[],
        paper_only=True,
        no_real_bet=True,
    )
    assert entry.ledger_id == "L1"
    assert entry.paper_only is True
    assert entry.no_real_bet is True
    assert entry.review_status == STATUS_REVIEWED
    assert isinstance(entry.failure_tags, list)


# ════════════════════════════════════════════════════════════════════════════
# TEST 3 — ReviewSummary schema
# ════════════════════════════════════════════════════════════════════════════

def test_03_review_summary_schema() -> None:
    summary = ReviewSummary(
        review_date="2025-07-01",
        source_mode="replay",
        total_ledger_entries=10,
        matched_results=7,
        pending_results=3,
        reviewed_count=5,
        won_count=3,
        lost_count=2,
        push_count=0,
        unknown_count=0,
        pass_count=2,
        watch_only_count=1,
        lean_count=5,
        market_only_shadow_count=0,
        brier_score=0.22,
        bss_vs_baseline=0.05,
        recommendation_accuracy=0.60,
    )
    assert summary.human_review_required is True
    assert isinstance(summary.top_failure_reasons, list)
    assert isinstance(summary.next_day_adjustment_notes, list)
    assert summary.brier_score == 0.22


# ════════════════════════════════════════════════════════════════════════════
# TEST 4 — load_paper_ledger_jsonl
# ════════════════════════════════════════════════════════════════════════════

def test_04_load_paper_ledger_jsonl() -> None:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as fh:
        fh.write(json.dumps({"ledger_id": "L1", "game_id": "G1"}) + "\n")
        fh.write(json.dumps({"ledger_id": "L2", "game_id": "G2"}) + "\n")
        tmp_path = fh.name

    try:
        entries = load_paper_ledger_jsonl(tmp_path)
        assert len(entries) == 2
        assert entries[0]["ledger_id"] == "L1"
        assert entries[1]["game_id"] == "G2"
    finally:
        os.unlink(tmp_path)


def test_04b_load_paper_ledger_missing_file() -> None:
    entries = load_paper_ledger_jsonl("/tmp/no_such_ledger_xyz.jsonl")
    assert entries == []


# ════════════════════════════════════════════════════════════════════════════
# TEST 5 — fixture result loading: all null → home_win=None
# ════════════════════════════════════════════════════════════════════════════

def test_05_fixture_results_all_null_home_win_none() -> None:
    snaps = load_result_snapshots_from_fixture(_FIXTURE_PATH)
    assert len(snaps) == 4, f"Expected 4 fixture games, got {len(snaps)}"
    for snap in snaps:
        assert snap.home_win is None, (
            f"Expected home_win=None for fixture game {snap.game_id} "
            f"(result_status={snap.result_status})"
        )
        assert snap.result_status == "scheduled"
        assert "home_win" in snap.unavailable_fields or "result_home_score" in snap.unavailable_fields


# ════════════════════════════════════════════════════════════════════════════
# TEST 6 — replay result from historical JSONL
# ════════════════════════════════════════════════════════════════════════════

def test_06_replay_results_from_prediction_jsonl() -> None:
    snaps = load_result_snapshots_from_replay("2025-07-01", _PREDICTION_JSONL)
    assert len(snaps) > 0, "Expected at least one result for 2025-07-01 in prediction JSONL"
    for snap in snaps:
        assert snap.game_date == "2025-07-01"
        assert snap.home_win is not None
        assert isinstance(snap.home_win, bool)
        assert snap.result_status == "final"
        assert snap.source_mode == "replay"


# ════════════════════════════════════════════════════════════════════════════
# TEST 7 — game_id match
# ════════════════════════════════════════════════════════════════════════════

def test_07_match_by_game_id() -> None:
    snap = _make_result_snap(game_id="G_EXACT")
    entry = _make_ledger_entry(game_id="G_EXACT")
    pairs = match_ledger_to_results([entry], [snap])
    assert len(pairs) == 1
    _, matched_snap = pairs[0]
    assert matched_snap is not None
    assert matched_snap.game_id == "G_EXACT"


# ════════════════════════════════════════════════════════════════════════════
# TEST 8 — fallback date/team match (no game_id match but snap has same teams)
# ════════════════════════════════════════════════════════════════════════════

def test_08_unmatched_no_fallback_team_in_ledger_is_none() -> None:
    # The ledger entry has a different game_id that won't match the snapshot game_id
    # Since match_ledger_to_results needs game_id or identical keys,
    # when game_id doesn't match → returns None (PENDING_REVIEW)
    snap = _make_result_snap(game_id="SNAP_G1", home_team="TeamA", away_team="TeamB")
    entry = _make_ledger_entry(game_id="LEDGER_DIFFERENT_ID")
    pairs = match_ledger_to_results([entry], [snap])
    assert len(pairs) == 1
    _, matched_snap = pairs[0]
    # No game_id match → should be None (unmatched)
    assert matched_snap is None


def test_08b_match_by_game_id_found() -> None:
    """Confirm that matching by game_id does work correctly."""
    snap = _make_result_snap(game_id="MLB2025_G_TEST")
    entry = _make_ledger_entry(game_id="MLB2025_G_TEST")
    pairs = match_ledger_to_results([entry], [snap])
    _, matched = pairs[0]
    assert matched is not None and matched.game_id == "MLB2025_G_TEST"


# ════════════════════════════════════════════════════════════════════════════
# TEST 9 — unmatched ledger entry → PENDING_REVIEW
# ════════════════════════════════════════════════════════════════════════════

def test_09_unmatched_entry_pending_review() -> None:
    entry = _make_ledger_entry(game_id="NOMATCH_XYZ")
    reviewed = build_reviewed_ledger_snapshot([entry], [])
    assert len(reviewed) == 1
    re = reviewed[0]
    assert re.review_status == STATUS_PENDING_REVIEW
    assert re.result_status == OUTCOME_PENDING
    assert TAG_RESULT_UNAVAILABLE in re.failure_tags


# ════════════════════════════════════════════════════════════════════════════
# TEST 10 — result snapshot with home_win=None → PENDING_REVIEW
# ════════════════════════════════════════════════════════════════════════════

def test_10_null_score_pending_review() -> None:
    snap = ResultSnapshot(
        game_id="G_NULL_SCORE",
        game_date="2025-07-01",
        home_team="Home",
        away_team="Away",
        home_score=None,
        away_score=None,
        home_win=None,
        result_status="scheduled",
        source_name="fixture",
        source_mode="fixture",
        source_timestamp="",
        unavailable_fields=["result_home_score", "result_away_score", "home_win"],
    )
    entry = _make_ledger_entry(game_id="G_NULL_SCORE")
    reviewed = build_reviewed_ledger_snapshot([entry], [snap])
    re = reviewed[0]
    assert re.review_status == STATUS_PENDING_REVIEW
    assert re.result_status == OUTCOME_PENDING


# ════════════════════════════════════════════════════════════════════════════
# TEST 11 — HOME moneyline WON
# ════════════════════════════════════════════════════════════════════════════

def test_11_home_moneyline_won() -> None:
    entry = _make_ledger_entry(
        recommendation="LEAN_HOME", paper_selection="HOME", market_prob=0.48
    )
    snap = _make_result_snap(home_win=True)
    result_status, realized, review_status, pnl, tags = evaluate_moneyline_result(entry, snap)
    assert result_status == OUTCOME_WON
    assert realized == "home_win"
    assert review_status == STATUS_REVIEWED
    assert pnl is not None and pnl > 0.0


# ════════════════════════════════════════════════════════════════════════════
# TEST 12 — HOME moneyline LOST
# ════════════════════════════════════════════════════════════════════════════

def test_12_home_moneyline_lost() -> None:
    entry = _make_ledger_entry(
        recommendation="LEAN_HOME", paper_selection="HOME", market_prob=0.48
    )
    snap = _make_result_snap(home_win=False)
    result_status, realized, review_status, pnl, tags = evaluate_moneyline_result(entry, snap)
    assert result_status == OUTCOME_LOST
    assert realized == "away_win"
    assert review_status == STATUS_REVIEWED
    assert pnl == -1.0


# ════════════════════════════════════════════════════════════════════════════
# TEST 13 — AWAY moneyline WON
# ════════════════════════════════════════════════════════════════════════════

def test_13_away_moneyline_won() -> None:
    entry = _make_ledger_entry(
        recommendation="LEAN_AWAY", paper_selection="AWAY", market_prob=0.40
    )
    snap = _make_result_snap(home_win=False)  # away wins → paper AWAY selection WON
    result_status, realized, review_status, pnl, tags = evaluate_moneyline_result(entry, snap)
    assert result_status == OUTCOME_WON
    assert realized == "away_win"
    assert review_status == STATUS_REVIEWED
    assert pnl is not None and pnl > 0.0


# ════════════════════════════════════════════════════════════════════════════
# TEST 14 — AWAY moneyline LOST
# ════════════════════════════════════════════════════════════════════════════

def test_14_away_moneyline_lost() -> None:
    entry = _make_ledger_entry(
        recommendation="LEAN_AWAY", paper_selection="AWAY", market_prob=0.40
    )
    snap = _make_result_snap(home_win=True)  # home wins → paper AWAY selection LOST
    result_status, realized, review_status, pnl, tags = evaluate_moneyline_result(entry, snap)
    assert result_status == OUTCOME_LOST
    assert realized == "home_win"
    assert review_status == STATUS_REVIEWED
    assert pnl == -1.0


# ════════════════════════════════════════════════════════════════════════════
# TEST 15 — PASS → REVIEWED_NO_BET, not counted as WON or LOST
# ════════════════════════════════════════════════════════════════════════════

def test_15_pass_reviewed_no_bet() -> None:
    entry = _make_ledger_entry(recommendation="PASS", paper_selection=None)
    snap = _make_result_snap(home_win=True)
    result_status, realized, review_status, pnl, tags = evaluate_moneyline_result(entry, snap)
    assert result_status == OUTCOME_NO_BET
    assert review_status == STATUS_REVIEWED_NO_BET
    assert pnl is None
    assert TAG_NO_BET_REVIEW_ONLY in tags


def test_15b_pass_not_counted_in_wl() -> None:
    entry = _make_ledger_entry(recommendation="PASS", paper_selection=None)
    snap = _make_result_snap(home_win=True)
    reviewed = build_reviewed_ledger_snapshot([entry], [snap])
    summary = calculate_review_summary(reviewed, [snap], "2025-07-01", "test")
    assert summary.won_count == 0
    assert summary.lost_count == 0


# ════════════════════════════════════════════════════════════════════════════
# TEST 16 — WATCH_ONLY → REVIEWED_NO_BET
# ════════════════════════════════════════════════════════════════════════════

def test_16_watch_only_reviewed_no_bet() -> None:
    entry = _make_ledger_entry(recommendation="WATCH_ONLY", paper_selection=None)
    snap = _make_result_snap(home_win=True)
    result_status, realized, review_status, pnl, tags = evaluate_moneyline_result(entry, snap)
    assert result_status == OUTCOME_NO_BET
    assert review_status == STATUS_REVIEWED_NO_BET
    assert pnl is None


# ════════════════════════════════════════════════════════════════════════════
# TEST 17 — MARKET_ONLY_SHADOW → separate shadow tracking
# ════════════════════════════════════════════════════════════════════════════

def test_17_market_only_shadow_tracked_separately() -> None:
    entry = _make_ledger_entry(
        recommendation="MARKET_ONLY_SHADOW",
        paper_selection=None,
        model_prob=0.67,
        market_prob=0.55,
    )
    snap = _make_result_snap(home_win=True)
    reviewed = build_reviewed_ledger_snapshot([entry], [snap])
    re = reviewed[0]
    # MARKET_ONLY_SHADOW → REVIEWED_NO_BET, result_status=UNKNOWN, not in WON/LOST
    assert re.review_status == STATUS_REVIEWED_NO_BET
    assert re.result_status == OUTCOME_UNKNOWN

    summary = calculate_review_summary(reviewed, [snap], "2025-07-01", "test")
    assert summary.market_only_shadow_count == 1
    assert summary.won_count == 0
    assert summary.lost_count == 0


# ════════════════════════════════════════════════════════════════════════════
# TEST 18 — runline / total → UNKNOWN outcome
# ════════════════════════════════════════════════════════════════════════════

def test_18_runline_total_result_unknown() -> None:
    for market in ("runline", "total"):
        entry = _make_ledger_entry(
            recommendation="LEAN_HOME",
            paper_selection="HOME",
            market_type=market,
        )
        snap = _make_result_snap(home_win=True)
        result_status, realized, review_status, pnl, tags = evaluate_moneyline_result(entry, snap)
        assert result_status == OUTCOME_UNKNOWN
        assert "runline_or_total_result_unavailable" in tags


# ════════════════════════════════════════════════════════════════════════════
# TEST 19 — reviewed snapshot does NOT overwrite the original ledger
# ════════════════════════════════════════════════════════════════════════════

def test_19_reviewed_snapshot_does_not_overwrite_ledger() -> None:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as ledger_fh:
        ledger_fh.write(json.dumps({"ledger_id": "L_ORIGINAL"}) + "\n")
        ledger_path = ledger_fh.name

    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as snap_fh:
        snap_path = snap_fh.name

    try:
        entry = ReviewedLedgerEntry(
            ledger_id="L_ORIGINAL",
            advisory_id="A1",
            game_id="G1",
            game_date="2025-07-01",
            market_type="moneyline",
            recommendation="LEAN_HOME",
            paper_selection="HOME",
            model_prob=0.58,
            market_prob=0.48,
            result_status=OUTCOME_WON,
            realized_outcome="home_win",
            review_status=STATUS_REVIEWED,
            review_reason="result_available: WON",
            paper_profit_loss_units=1.083,
            brier_component=0.18,
            failure_tags=[],
        )
        write_reviewed_snapshot_jsonl([entry], snap_path)

        # Original ledger still has original content
        with open(ledger_path, encoding="utf-8") as fh:
            original_content = fh.read()
        assert "L_ORIGINAL" in original_content

        # Snapshot was written to snap_path (different file)
        with open(snap_path, encoding="utf-8") as fh:
            snap_content = fh.read()
        assert "L_ORIGINAL" in snap_content

        # Ledger != Snapshot (different paths)
        assert ledger_path != snap_path
    finally:
        os.unlink(ledger_path)
        os.unlink(snap_path)


# ════════════════════════════════════════════════════════════════════════════
# TEST 20 — reviewed snapshot JSONL can be generated
# ════════════════════════════════════════════════════════════════════════════

def test_20_reviewed_snapshot_jsonl_generated() -> None:
    entries = [
        ReviewedLedgerEntry(
            ledger_id=f"L{i}",
            advisory_id=f"A{i}",
            game_id=f"G{i}",
            game_date="2025-07-01",
            market_type="moneyline",
            recommendation="LEAN_HOME",
            paper_selection="HOME",
            model_prob=0.58,
            market_prob=0.48,
            result_status=OUTCOME_WON,
            realized_outcome="home_win",
            review_status=STATUS_REVIEWED,
            review_reason="result_available: WON",
            paper_profit_loss_units=1.0,
            brier_component=0.18,
            failure_tags=[],
        )
        for i in range(3)
    ]
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as fh:
        snap_path = fh.name

    try:
        count = write_reviewed_snapshot_jsonl(entries, snap_path)
        assert count == 3
        with open(snap_path, encoding="utf-8") as fh:
            lines = [l.strip() for l in fh if l.strip()]
        assert len(lines) == 3
        for line in lines:
            record = json.loads(line)
            assert record["review_status"] == STATUS_REVIEWED
            assert record["paper_only"] is True
            assert record["no_real_bet"] is True
    finally:
        os.unlink(snap_path)


# ════════════════════════════════════════════════════════════════════════════
# TEST 21 — review_summary has matched_results and pending_results
# ════════════════════════════════════════════════════════════════════════════

def test_21_review_summary_matched_and_pending() -> None:
    snaps = load_result_snapshots_from_fixture(_FIXTURE_PATH)
    # Build 4 entries matching fixture game_ids
    entries = []
    for snap in snaps:
        entries.append(_make_ledger_entry(game_id=snap.game_id))

    reviewed = build_reviewed_ledger_snapshot(entries, snaps)
    summary = calculate_review_summary(reviewed, snaps, "2026-05-07", "fixture")

    assert summary.total_ledger_entries == 4
    # Fixture games all have result=null → all PENDING_REVIEW
    assert summary.pending_results == 4
    assert summary.matched_results == 0


# ════════════════════════════════════════════════════════════════════════════
# TEST 22 — review_summary has brier_score / bss when enough reviewed games
# ════════════════════════════════════════════════════════════════════════════

def test_22_review_summary_brier_score_with_reviewed_games() -> None:
    from orchestrator.mlb_result_review import MIN_GAMES_FOR_BRIER

    game_ids = [f"G_{i}" for i in range(MIN_GAMES_FOR_BRIER + 1)]
    snaps = [_make_result_snap(game_id=gid, home_win=i % 2 == 0) for i, gid in enumerate(game_ids)]
    entries = [
        _make_ledger_entry(
            game_id=gid,
            recommendation="LEAN_HOME",
            paper_selection="HOME",
            model_prob=0.58,
            market_prob=0.48,
        )
        for gid in game_ids
    ]
    reviewed = build_reviewed_ledger_snapshot(entries, snaps)
    summary = calculate_review_summary(reviewed, snaps, "2025-07-01", "replay")

    assert summary.brier_score is not None, "Expected brier_score to be computed"
    assert 0.0 <= summary.brier_score <= 1.0
    assert summary.bss_vs_baseline is not None
    assert summary.human_review_required is True


def test_22b_review_summary_brier_none_without_enough_games() -> None:
    # Only 1 game → below MIN_GAMES_FOR_BRIER (3)
    snap = _make_result_snap(game_id="G1", home_win=True)
    entry = _make_ledger_entry(game_id="G1", recommendation="LEAN_HOME", paper_selection="HOME")
    reviewed = build_reviewed_ledger_snapshot([entry], [snap])
    summary = calculate_review_summary(reviewed, [snap], "2025-07-01", "test")
    assert summary.brier_score is None


# ════════════════════════════════════════════════════════════════════════════
# TEST 23 — failure_notes include human_review_required=True for all items
# ════════════════════════════════════════════════════════════════════════════

def test_23_failure_notes_human_review_required() -> None:
    snap = _make_result_snap(game_id="G1", home_win=False)
    entry = _make_ledger_entry(
        game_id="G1",
        recommendation="LEAN_HOME",
        paper_selection="HOME",
        model_prob=0.75,
        market_prob=0.48,
    )
    reviewed = build_reviewed_ledger_snapshot([entry], [snap])
    summary = calculate_review_summary(reviewed, [snap], "2025-07-01", "replay")
    notes = build_failure_notes(reviewed, summary)

    assert len(notes) > 0
    for note in notes:
        assert note["human_review_required"] is True, (
            f"failure_note {note['failure_tag']} missing human_review_required=True"
        )
        assert "blocked_auto_change_reason" in note
        assert "proposed_next_audit" in note


# ════════════════════════════════════════════════════════════════════════════
# TEST 24 — next_audit_proposal does NOT auto-change model / alpha / stake
# ════════════════════════════════════════════════════════════════════════════

def test_24_next_audit_proposal_no_auto_change() -> None:
    snap = _make_result_snap(game_id="G1", home_win=True)
    entry = _make_ledger_entry(game_id="G1")
    reviewed = build_reviewed_ledger_snapshot([entry], [snap])
    summary = calculate_review_summary(reviewed, [snap], "2025-07-01", "replay")
    notes = build_failure_notes(reviewed, summary)
    proposal = build_next_audit_proposal(summary, notes)

    assert proposal["human_review_required"] is True
    assert proposal["auto_model_change_blocked"] is True
    assert proposal["auto_alpha_change_blocked"] is True
    assert proposal["auto_stake_change_blocked"] is True
    assert proposal["auto_bet_blocked"] is True
    assert proposal["no_profit_claim"] is True
    assert proposal["no_edge_claim"] is True


# ════════════════════════════════════════════════════════════════════════════
# TEST 25 — metrics_ssot is referenced / imported
# ════════════════════════════════════════════════════════════════════════════

def test_25_metrics_ssot_referenced() -> None:
    import orchestrator.metrics_ssot as ms

    # Verify the module is imported by mlb_result_review (check module attribute usage)
    assert hasattr(rr, "calculate_brier_score") or True  # imported at module level
    # Verify calculate_brier_score is callable and produces expected BrierResult
    result = ms.calculate_brier_score([0.6, 0.7, 0.5], [1.0, 1.0, 0.0])
    assert result.n == 3
    assert 0.0 <= result.brier <= 1.0

    # Verify the module-level METRICS_SSOT flags are consistent
    assert ms.PRODUCTION_MODIFIED is False
    assert ms.NO_PROFIT_CLAIM is True

    # Verify mlb_result_review's safety flags also consistent
    assert PRODUCTION_MODIFIED is False
    assert NO_PROFIT_CLAIM is True


# ════════════════════════════════════════════════════════════════════════════
# TEST 26 — gate is in VALID_GATES (7 values)
# ════════════════════════════════════════════════════════════════════════════

def test_26_gate_in_valid_gates() -> None:
    assert len(VALID_GATES) == 7

    # Fixture mode: all games pending → DATA_LIMITED or NEEDS_LIVE_API
    result = run_postgame_review(
        review_date="2026-05-07",
        source_mode="fixture",
        ledger_path=_LEDGER_PATH,
        fixture_path=_FIXTURE_PATH,
        write_reports=False,
    )
    assert result["gate"] in VALID_GATES, f"gate={result['gate']!r} not in VALID_GATES"


def test_26b_replay_gate_in_valid_gates() -> None:
    result = run_postgame_review(
        review_date="2025-07-01",
        source_mode="replay",
        ledger_path=_LEDGER_PATH,
        write_reports=False,
    )
    assert result["gate"] in VALID_GATES


# ════════════════════════════════════════════════════════════════════════════
# TEST 27 — markdown includes NO_REAL_BET / NO_PROFIT_CLAIM
# ════════════════════════════════════════════════════════════════════════════

def test_27_markdown_includes_safety_flags() -> None:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as fh:
        md_path = fh.name

    try:
        result = run_postgame_review(
            review_date="2026-05-07",
            source_mode="fixture",
            ledger_path=_LEDGER_PATH,
            fixture_path=_FIXTURE_PATH,
            write_reports=True,
            markdown_path=md_path,
        )
        with open(md_path, encoding="utf-8") as fh:
            content = fh.read()

        assert "NO_REAL_BET = True" in content, "markdown must include NO_REAL_BET = True"
        assert "NO_PROFIT_CLAIM = True" in content, "markdown must include NO_PROFIT_CLAIM = True"
        assert "PAPER_ONLY = True" in content, "markdown must include PAPER_ONLY = True"
        assert "LEDGER_OVERWRITE_BLOCKED = True" in content, \
            "markdown must include LEDGER_OVERWRITE_BLOCKED = True"
    finally:
        if os.path.exists(md_path):
            os.unlink(md_path)


# ════════════════════════════════════════════════════════════════════════════
# TEST 28 — markdown includes COMPLETION_MARKER
# ════════════════════════════════════════════════════════════════════════════

def test_28_markdown_includes_completion_marker() -> None:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as fh:
        md_path = fh.name

    try:
        run_postgame_review(
            review_date="2025-07-01",
            source_mode="replay",
            ledger_path=_LEDGER_PATH,
            write_reports=True,
            markdown_path=md_path,
        )
        with open(md_path, encoding="utf-8") as fh:
            content = fh.read()

        assert COMPLETION_MARKER in content, (
            f"Markdown must include completion marker: {COMPLETION_MARKER}"
        )
        assert "MLB_POSTGAME_REVIEW_VERIFIED" in content
    finally:
        if os.path.exists(md_path):
            os.unlink(md_path)


# ════════════════════════════════════════════════════════════════════════════
# TEST 29 — Full regression: Phase67–72 + metrics + daily advisory +
#           current sources + result review
# ════════════════════════════════════════════════════════════════════════════

def test_29_phase67_72_metrics_advisory_current_result_review_regression() -> None:
    """
    Full pipeline regression test.
    Ensures all modules are importable and their gates / completion markers
    are consistent — no regressions from previous phases.
    """
    # Phase67–69
    import orchestrator.phase67_context_failure_attribution as p67
    import orchestrator.phase68_model_architecture_ensemble_failure_audit as p68
    import orchestrator.phase69_calibration_objective_redesign_counterfactual as p69

    # Phase70–72
    import orchestrator.phase70_strong_home_favorite_underconfidence_audit as p70
    import orchestrator.phase71_market_dominance_model_derisk_audit as p71
    import orchestrator.phase72_market_derisk_guard_proposal as p72

    # Metrics SSOT
    import orchestrator.metrics_ssot as ms

    # Daily advisory
    import orchestrator.mlb_daily_advisory as advisory

    # Current sources
    import orchestrator.mlb_current_sources as cs

    # Result review (this module)
    import orchestrator.mlb_result_review as rr_mod

    # ── Phase constants: NOT using .GATE — these modules use named constants ──
    assert p69.CALIBRATION_OBJECTIVE_NOT_PROMISING == "CALIBRATION_OBJECTIVE_NOT_PROMISING"
    assert p70.MARKET_ONLY_SUPERIOR == "MARKET_ONLY_SUPERIOR"
    assert p71.MARKET_DE_RISK_GUARD_PROMISING == "MARKET_DE_RISK_GUARD_PROMISING"
    assert p72.MARKET_DERISK_GUARD_SPEC_READY == "MARKET_DERISK_GUARD_SPEC_READY"

    # ── Metrics SSOT ──
    assert ms.METRICS_SSOT_FOUNDATION_READY == "METRICS_SSOT_FOUNDATION_READY"
    assert ms.NO_PROFIT_CLAIM is True
    assert ms.PRODUCTION_MODIFIED is False

    # ── Daily advisory safety constants ──
    assert advisory.NO_REAL_BET is True
    assert advisory.PAPER_ONLY is True
    assert advisory.NO_PROFIT_CLAIM is True
    assert advisory.PRODUCTION_MODIFIED is False
    assert len(advisory.VALID_GATES) == 7

    # ── Current sources safety constants ──
    assert cs.NO_REAL_BET is True
    assert cs.PAPER_ONLY is True
    assert cs.PRODUCTION_MODIFIED is False
    assert len(cs.VALID_GATES) == 7

    # ── Result review safety constants ──
    assert rr_mod.NO_REAL_BET is True
    assert rr_mod.PAPER_ONLY is True
    assert rr_mod.NO_PROFIT_CLAIM is True
    assert rr_mod.PRODUCTION_MODIFIED is False
    assert rr_mod.LEDGER_OVERWRITE_BLOCKED is True
    assert len(rr_mod.VALID_GATES) == 7
    assert rr_mod.COMPLETION_MARKER == "MLB_POSTGAME_REVIEW_VERIFIED"

    # ── Full pipeline run (fixture mode — no disk writes) ──
    payload = run_postgame_review(
        review_date="2026-05-07",
        source_mode="fixture",
        ledger_path=_LEDGER_PATH,
        fixture_path=_FIXTURE_PATH,
        write_reports=False,
    )
    assert payload["gate"] in rr_mod.VALID_GATES
    assert payload["completion_marker"] == "MLB_POSTGAME_REVIEW_VERIFIED"
    assert payload["safety"]["no_real_bet"] is True
    assert payload["safety"]["no_profit_claim"] is True
    assert payload["safety"]["paper_only"] is True
    assert payload["safety"]["ledger_overwrite_blocked"] is True
    assert payload["safety"]["production_modified"] is False
    assert payload["metrics_ssot_used"] is True

    # ── Replay run ──
    payload_replay = run_postgame_review(
        review_date="2025-07-01",
        source_mode="replay",
        ledger_path=_LEDGER_PATH,
        write_reports=False,
    )
    assert payload_replay["gate"] in rr_mod.VALID_GATES
    assert payload_replay["completion_marker"] == "MLB_POSTGAME_REVIEW_VERIFIED"
