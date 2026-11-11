"""
tests/test_phase29_clv_lookup_key_mismatch_fix.py
=================================================
Phase 29 — CLV Lookup Key Mismatch Fix: 9 unit tests.

Tests:
  1. extract_game_id_from_snapshot_ref returns prefix before "|".
  2. null / malformed snapshot_ref returns None.
  3. canonical lookup still works when match is in timeline.
  4. canonical miss + snapshot_ref fallback finds the closing odds.
  5. fallback does not bypass timestamp validation (closing_ts < pred_ts).
  6. same-snapshot guard still rejected via fallback path.
  7. valid fallback candidate appears in check_pending_for_upgrade preview.
  8. apply creates backup before mutating CLV file.
  9. readiness becomes LEARNING_READY after COMPUTED CLV exists.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from orchestrator.closing_odds_monitor import (
    LOOKUP_CANONICAL,
    LOOKUP_NONE,
    LOOKUP_SNAPSHOT_REF,
    _find_closing_odds_for_pending,
    check_pending_for_upgrade,
    extract_game_id_from_snapshot_ref,
)
from scripts.run_phase29_apply_clv_lookup_fix import apply_clv_upgrade, dry_run


# ── Constants used across tests ───────────────────────────────────────────────

PRED_TIME = "2026-04-30T08:35:10Z"
PRED_TS = datetime.fromisoformat(PRED_TIME.replace("Z", "+00:00"))
CLOSING_TS_VALID = "2026-04-30T16:09:33Z"        # ~7.5 h after prediction
CLOSING_TS_BEFORE = "2026-04-30T07:00:00Z"        # before prediction
CLOSING_TS_SAME_SNAP = "2026-04-30T08:35:25Z"     # 15 s after — same snapshot

SNAPSHOT_REF = (
    "MLB-2026_04_30-12_15_PM-DETROIT_TIGERS-AT-ATLANTA_BRAVES"
    "|TSL|snap@2026-04-30T05:16:54Z"
)
SNAPSHOT_GAME_ID = "MLB-2026_04_30-12_15_PM-DETROIT_TIGERS-AT-ATLANTA_BRAVES"
CANONICAL_ID = "baseball:mlb:20260430:ATL:DET"


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_clv(
    prediction_id: str = "pred_001",
    canonical_match_id: str = CANONICAL_ID,
    selection: str = "home",
    snapshot_ref: str | None = SNAPSHOT_REF,
    prediction_time_utc: str = PRED_TIME,
    clv_status: str = "PENDING_CLOSING",
    implied_probability_at_prediction: float = 0.555556,
) -> dict:
    return {
        "prediction_id": prediction_id,
        "canonical_match_id": canonical_match_id,
        "selection": selection,
        "odds_snapshot_ref": snapshot_ref,
        "prediction_time_utc": prediction_time_utc,
        "clv_status": clv_status,
        "implied_probability_at_prediction": implied_probability_at_prediction,
        "clv_record_id": f"6u-rec-{prediction_id}",
    }


def _make_tl(
    game_id: str = SNAPSHOT_GAME_ID,
    closing_home_ml: float | None = -154.0,
    closing_away_ml: float | None = 130.0,
    closing_ts: str | None = CLOSING_TS_VALID,
) -> dict:
    return {
        "game_id": game_id,
        "closing_home_ml": closing_home_ml,
        "closing_away_ml": closing_away_ml,
        "closing_ts": closing_ts,
        "external_closing_home_ml": None,
        "external_closing_ts": None,
    }


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec) + "\n")


# ── Test 1: extract_game_id_from_snapshot_ref — normal ────────────────────────

def test_extract_game_id_returns_prefix():
    result = extract_game_id_from_snapshot_ref(SNAPSHOT_REF)
    assert result == SNAPSHOT_GAME_ID, f"Got {result!r}"

    # Works with any separator position
    assert extract_game_id_from_snapshot_ref("GAME_ID|extra") == "GAME_ID"
    assert extract_game_id_from_snapshot_ref("NO_PIPE") == "NO_PIPE"


# ── Test 2: null / malformed snapshot_ref → None ──────────────────────────────

def test_extract_game_id_null_malformed():
    assert extract_game_id_from_snapshot_ref(None) is None
    assert extract_game_id_from_snapshot_ref("") is None
    assert extract_game_id_from_snapshot_ref("   ") is None
    # Pipe at start with empty prefix → should return None (empty string strip)
    assert extract_game_id_from_snapshot_ref("|TSL|...") is None


# ── Test 3: canonical lookup works when key matches timeline ───────────────────

def test_canonical_lookup_works():
    """When canonical_match_id matches a timeline entry, use it (no fallback needed)."""
    clv = _make_clv(canonical_match_id=SNAPSHOT_GAME_ID, snapshot_ref=None)
    tl = _make_tl(game_id=SNAPSHOT_GAME_ID)
    # Build index manually: same as _build_timeline_index but from a list
    idx = {SNAPSHOT_GAME_ID: tl}

    ml, ts_str, source, method = _find_closing_odds_for_pending(clv, idx, PRED_TS)

    assert ml is not None, "Expected closing odds via canonical lookup"
    assert method == LOOKUP_CANONICAL
    assert source == "tsl_closing"


# ── Test 4: canonical miss + snapshot_ref fallback resolves odds ───────────────

def test_snapshot_ref_fallback_resolves_odds():
    """
    When canonical_match_id (baseball:mlb:...) doesn't match the timeline index
    (which uses game_id MLB-...), the snapshot_ref fallback must succeed.
    """
    clv = _make_clv(canonical_match_id=CANONICAL_ID, snapshot_ref=SNAPSHOT_REF)
    tl = _make_tl(game_id=SNAPSHOT_GAME_ID)
    # Index keyed by SNAPSHOT_GAME_ID (the MLB-... format)
    idx = {SNAPSHOT_GAME_ID: tl}

    # Canonical lookup MUST fail (keys differ)
    assert idx.get(CANONICAL_ID) is None, "Test setup error: canonical should not be in index"

    ml, ts_str, source, method = _find_closing_odds_for_pending(clv, idx, PRED_TS)

    assert ml == -154.0
    assert method == LOOKUP_SNAPSHOT_REF
    assert source == "tsl_closing"


# ── Test 5: fallback does NOT bypass timestamp validation ─────────────────────

def test_fallback_does_not_bypass_timestamp_validation():
    """
    Even when snapshot_ref fallback finds a timeline entry, closing_ts must be
    strictly after prediction_time_utc. A stale closing_ts must return None.
    """
    clv = _make_clv(canonical_match_id=CANONICAL_ID, snapshot_ref=SNAPSHOT_REF)
    tl = _make_tl(game_id=SNAPSHOT_GAME_ID, closing_ts=CLOSING_TS_BEFORE)
    idx = {SNAPSHOT_GAME_ID: tl}

    ml, ts_str, source, method = _find_closing_odds_for_pending(clv, idx, PRED_TS)

    assert ml is None, "closing_ts before prediction must not return closing odds"
    assert method == LOOKUP_NONE


# ── Test 6: same-snapshot guard still rejected via fallback ───────────────────

def test_same_snapshot_rejected_via_fallback():
    """
    Fallback candidate with closing_ts only 15 s after prediction_time_utc
    must be rejected by _validate_closing_odds (same-snapshot guard ≥ 60 s).
    _find_closing_odds_for_pending pre-checks closing_ts > pred_ts, so 15 s AFTER
    is technically "after" — but _validate_closing_odds will reject it.
    We verify the apply path uses _validate_closing_odds correctly by using the
    tmp-dir apply and checking the record stays PENDING.
    """
    from scripts.run_phase29_apply_clv_lookup_fix import apply_clv_upgrade

    # Note: _find_closing_odds_for_pending only checks closing_ts > pred_ts
    # (strict). 15 s is >0 so it PASSES _find_... but then _validate_closing_odds
    # will reject (same_snapshot_too_close). The apply path calls _validate_closing_odds.
    # Verify _find_ returns the candidate (it should — 15 s > 0)
    clv = _make_clv(canonical_match_id=CANONICAL_ID, snapshot_ref=SNAPSHOT_REF)
    tl = _make_tl(game_id=SNAPSHOT_GAME_ID, closing_ts=CLOSING_TS_SAME_SNAP)
    idx = {SNAPSHOT_GAME_ID: tl}

    ml, ts_str, source, method = _find_closing_odds_for_pending(clv, idx, PRED_TS)
    # _find_ returns the candidate (pre-check: closing_ts > pred_ts — True)
    assert ml is not None, "_find_ should return candidate (closing_ts > pred_ts by 15s)"

    # But apply_clv_upgrade must reject it (same-snapshot) → record stays PENDING
    import tempfile, json
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        clv_file = tmp_path / "clv.jsonl"
        tl_file = tmp_path / "timeline.jsonl"
        bk_dir = tmp_path / "backups"
        _write_jsonl(clv_file, [clv])
        _write_jsonl(tl_file, [tl])

        result = apply_clv_upgrade(clv_file, tl_file, bk_dir)
        # No records should be upgraded (same-snapshot rejected)
        assert result.get("applied") is False or result.get("upgraded", 0) == 0, (
            "Same-snapshot candidate must not produce a COMPUTED record"
        )
        # CLV file should still show PENDING
        updated = [json.loads(l) for l in clv_file.read_text().splitlines() if l.strip()]
        assert updated[0]["clv_status"] == "PENDING_CLOSING"


# ── Test 7: valid fallback candidate appears in dry_run preview ────────────────

def test_valid_fallback_candidate_in_dry_run_preview(tmp_path):
    """
    check_pending_for_upgrade (= dry_run) must list the record as upgradeable
    with lookup_method = odds_snapshot_ref_game_id.
    """
    clv_file = tmp_path / "clv.jsonl"
    tl_file = tmp_path / "timeline.jsonl"

    clv = _make_clv(canonical_match_id=CANONICAL_ID, snapshot_ref=SNAPSHOT_REF)
    tl = _make_tl(game_id=SNAPSHOT_GAME_ID, closing_ts=CLOSING_TS_VALID)
    _write_jsonl(clv_file, [clv])
    _write_jsonl(tl_file, [tl])

    preview = dry_run(clv_file, tl_file)
    assert preview["upgradeable_count"] == 1, f"Expected 1 upgradeable, got: {preview}"
    assert preview["not_yet"] == 0

    up = preview["upgradeable"][0]
    assert up["lookup_method"] == LOOKUP_SNAPSHOT_REF
    assert up["closing_ml"] == -154.0


# ── Test 8: apply writes backup before mutating CLV file ─────────────────────

def test_apply_creates_backup_before_mutation(tmp_path):
    """
    apply_clv_upgrade must create a backup file in backup_dir BEFORE
    rewriting the original CLV JSONL.
    """
    clv_file = tmp_path / "clv.jsonl"
    tl_file = tmp_path / "timeline.jsonl"
    bk_dir = tmp_path / "backups"

    clv = _make_clv()
    tl = _make_tl()
    _write_jsonl(clv_file, [clv])
    _write_jsonl(tl_file, [tl])

    original_content = clv_file.read_text()

    result = apply_clv_upgrade(clv_file, tl_file, bk_dir)

    assert result["applied"] is True, f"Apply failed: {result}"
    assert result["upgraded"] == 1

    # Backup must exist
    backup_path = Path(result["backup_path"])
    assert backup_path.exists(), "Backup file must be created"
    # Backup must contain the ORIGINAL content
    assert backup_path.read_text() == original_content, "Backup must be identical to original"

    # Original CLV file must now have a COMPUTED record
    updated = [json.loads(l) for l in clv_file.read_text().splitlines() if l.strip()]
    assert len(updated) == 1
    assert updated[0]["clv_status"] == "COMPUTED"
    assert updated[0].get("closing_lookup_method") == LOOKUP_SNAPSHOT_REF


# ── Test 9: readiness becomes LEARNING_READY after COMPUTED CLV exists ─────────

def test_readiness_learning_ready_after_computed_clv(tmp_path, monkeypatch):
    """
    After the apply step, phase6_data_registry.get_phase6_status() must see
    clv_computed >= 1, and optimization_state._check_clv_readiness() must
    return ready=True.
    """
    from orchestrator import phase6_data_registry, optimization_state

    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()

    # Create a Phase 6T registry file (needed for discover_phase6_dates)
    date = "2026-04-30"
    reg_file = reports_dir / f"prediction_registry_6t_{date}.jsonl"
    _write_jsonl(reg_file, [
        {
            "governance_status": "VALIDATED_ML_ONLY",
            "prediction_id": "pred_001",
            "ev_percent": 3.5,
            "execution_mode": "RESEARCH_ONLY",
            "ml_predicted_probability": 0.56,
            "implied_probability": 0.52,
        }
    ])

    # Create a CLV file with one COMPUTED record (simulating post-apply state)
    clv_file = reports_dir / f"clv_validation_records_6u_{date}.jsonl"
    _write_jsonl(clv_file, [
        {
            "prediction_id": "pred_001",
            "clv_status": "COMPUTED",
            "clv_value": 0.042,
            "closing_odds": -154.0,
            "closing_ts": CLOSING_TS_VALID,
        }
    ])

    # Patch REPORTS_DIR in phase6_data_registry to point to tmp
    monkeypatch.setattr(phase6_data_registry, "REPORTS_DIR", reports_dir)

    status = phase6_data_registry.get_phase6_status(reports_dir)
    assert status["clv_computed"] >= 1, f"Expected clv_computed>=1, got: {status}"
    assert status["all_clv_pending"] is False

    # optimization_state._check_clv_readiness must return ready=True
    clv_ready = optimization_state._check_clv_readiness(reports_dir)
    assert clv_ready["computed"] >= 1
    assert clv_ready["ready"] is True, (
        f"Expected CLV readiness ready=True, got: {clv_ready}"
    )
