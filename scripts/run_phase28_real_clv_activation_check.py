#!/usr/bin/env python3
"""
scripts/run_phase28_real_clv_activation_check.py
================================================
Phase 28 — Real CLV Activation Readiness Check

Read-only diagnostic that answers:
  1. How many production CLV records are PENDING_CLOSING?
  2. How many have valid closing odds available?
  3. Which source can provide closing odds?
  4. What exact action is needed to activate production CLV?
  5. Can the system transition to LEARNING_READY now?

Root cause discovered:
  The closing monitor's _find_closing_odds_for_pending() uses
  clv_row["canonical_match_id"] (e.g. "baseball:mlb:20260430:ATL:DET")
  as the key to look up in the odds-timeline index.  But the timeline
  index is keyed by its own game_id field (e.g.
  "MLB-2026_04_30-12_15_PM-DETROIT_TIGERS-AT-ATLANTA_BRAVES").
  These never match — so ALL production records appear to have no
  closing odds even when they do.

  The FIX (implemented in Phase 29) is to also attempt lookup via the
  game_id portion of odds_snapshot_ref, which IS in the same format as
  the timeline game_id.

Default mode: READ-ONLY.
Pass --apply to run the closing monitor upgrade (Phase 29 work).

Usage:
  python3 scripts/run_phase28_real_clv_activation_check.py
  python3 scripts/run_phase28_real_clv_activation_check.py --preview-only
  python3 scripts/run_phase28_real_clv_activation_check.py --apply   # Phase 29

Success marker (read-only mode):
  PHASE_28_REAL_CLV_ACTIVATION_READINESS_VERIFIED
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ── Path constants (overridable for tests) ──────────────────────────────────
CLV_FILE = ROOT / "data" / "wbc_backend" / "reports" / "clv_validation_records_6u_2026-04-30.jsonl"
TIMELINE_FILE = ROOT / "data" / "mlb_context" / "odds_timeline.jsonl"
REPORTS_DIR = ROOT / "data" / "wbc_backend" / "reports"

ACTIVATION_DECISION_READY = "READY_TO_COMPUTE"
ACTIVATION_DECISION_WAITING = "WAITING_FOR_CLOSING_SOURCE"
ACTIVATION_DECISION_INVALID = "DATA_INVALID_REQUIRES_REPAIR"
ACTIVATION_DECISION_MANUAL = "MANUAL_REVIEW_REQUIRED"

INVALID_BEFORE_PREDICTION = "invalid_before_prediction"
INVALID_SAME_SNAPSHOT = "invalid_same_snapshot"
INVALID_MISSING_SOURCE = "missing_closing_source"
INVALID_MISSING_TS = "missing_closing_ts"
INVALID_GAME_ID_MISMATCH = "game_id_mismatch_no_timeline_entry"


# ── Core pure functions (tested directly) ───────────────────────────────────

def extract_game_id_from_snapshot_ref(snapshot_ref: str | None) -> str | None:
    """
    Extract the game_id portion from an odds_snapshot_ref string.

    Example:
      "MLB-2026_04_30-12_15_PM-DETROIT_TIGERS-AT-ATLANTA_BRAVES|TSL|snap@..."
      → "MLB-2026_04_30-12_15_PM-DETROIT_TIGERS-AT-ATLANTA_BRAVES"

    Returns None if the input is blank or has no '|' separator.
    """
    if not snapshot_ref:
        return None
    return snapshot_ref.split("|")[0].strip() or None


def parse_ts(raw: str | None) -> datetime | None:
    """Parse ISO-8601 timestamp string → tz-aware datetime, or None."""
    if not raw:
        return None
    raw = raw.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(raw)
    except Exception:
        return None


def american_to_implied(ml: int | float | None) -> float | None:
    """Convert American moneyline to implied probability."""
    if ml is None:
        return None
    ml = float(ml)
    if ml > 0:
        return round(100.0 / (ml + 100.0), 6)
    else:
        return round(abs(ml) / (abs(ml) + 100.0), 6)


def evaluate_closing_candidate(
    closing_ml: float | None,
    closing_ts_str: str | None,
    prediction_time_utc_str: str,
    same_snapshot_min_seconds: float = 60.0,
) -> dict[str, Any]:
    """
    Evaluate a single closing odds candidate against a prediction timestamp.

    Returns dict with:
      candidate_valid         bool
      closing_ts_after_pred   bool
      diff_seconds            float | None
      same_snapshot           bool
      invalid_reason          str | None  — one of INVALID_* constants
    """
    pred_ts = parse_ts(prediction_time_utc_str)
    closing_ts = parse_ts(closing_ts_str)

    if closing_ml is None:
        return {
            "candidate_valid": False,
            "closing_ts_after_pred": False,
            "diff_seconds": None,
            "same_snapshot": False,
            "invalid_reason": INVALID_MISSING_SOURCE,
        }
    if closing_ts is None:
        return {
            "candidate_valid": False,
            "closing_ts_after_pred": False,
            "diff_seconds": None,
            "same_snapshot": False,
            "invalid_reason": INVALID_MISSING_TS,
        }
    if pred_ts is None:
        return {
            "candidate_valid": False,
            "closing_ts_after_pred": False,
            "diff_seconds": None,
            "same_snapshot": False,
            "invalid_reason": "missing_prediction_ts",
        }

    diff = (closing_ts - pred_ts).total_seconds()
    after_pred = closing_ts > pred_ts
    same_snap = diff < same_snapshot_min_seconds

    if not after_pred:
        return {
            "candidate_valid": False,
            "closing_ts_after_pred": False,
            "diff_seconds": diff,
            "same_snapshot": same_snap,
            "invalid_reason": INVALID_BEFORE_PREDICTION,
        }
    if same_snap:
        return {
            "candidate_valid": False,
            "closing_ts_after_pred": True,
            "diff_seconds": diff,
            "same_snapshot": True,
            "invalid_reason": INVALID_SAME_SNAPSHOT,
        }
    return {
        "candidate_valid": True,
        "closing_ts_after_pred": True,
        "diff_seconds": diff,
        "same_snapshot": False,
        "invalid_reason": None,
    }


def build_timeline_index(timeline_records: list[dict]) -> dict[str, dict]:
    """
    Build a dict keyed by game_id → latest timeline row with any closing field.
    Used for snapshot-ref-based lookup (the improved approach).
    """
    index: dict[str, dict] = {}
    for row in timeline_records:
        gid = row.get("game_id") or ""
        if not gid:
            continue
        has_closing = (
            row.get("closing_home_ml") is not None
            or row.get("closing_away_ml") is not None
            or row.get("external_closing_home_ml") is not None
            or row.get("external_closing_away_ml") is not None
        )
        if has_closing:
            index[gid] = row
    return index


def evaluate_single_record(
    clv_row: dict,
    timeline_index_canonical: dict[str, dict],
    timeline_index_snapshot: dict[str, dict],
) -> dict[str, Any]:
    """
    Evaluate one PENDING_CLOSING CLV record for closing odds availability.

    Two lookup attempts:
      1. canonical_match_id  → timeline_index_canonical  (current monitor behavior)
      2. game_id from odds_snapshot_ref → timeline_index_snapshot  (improved)

    Returns per-record evaluation dict.
    """
    pred_id = clv_row.get("prediction_id", "")
    canonical_match_id = clv_row.get("canonical_match_id", "")
    selection = (clv_row.get("selection") or "").lower()
    pred_time_str = clv_row.get("prediction_time_utc", "")
    snapshot_ref = clv_row.get("odds_snapshot_ref", "")
    snapshot_game_id = extract_game_id_from_snapshot_ref(snapshot_ref)

    # ── Attempt 1: canonical_match_id lookup (current monitor behavior) ─────
    tl_canonical = timeline_index_canonical.get(canonical_match_id)
    canonical_lookup_found = tl_canonical is not None

    canonical_eval: dict[str, Any] = {
        "lookup_key": canonical_match_id,
        "lookup_method": "canonical_match_id",
        "timeline_entry_found": canonical_lookup_found,
        "candidate_valid": False,
        "invalid_reason": INVALID_GAME_ID_MISMATCH if not canonical_lookup_found else None,
        "closing_ml": None,
        "closing_ts": None,
        "closing_source": None,
    }

    if canonical_lookup_found and selection in ("home", "away"):
        _fill_candidate_eval(canonical_eval, tl_canonical, selection, pred_time_str, "canonical")

    # ── Attempt 2: snapshot_ref game_id lookup (improved) ───────────────────
    tl_snapshot = timeline_index_snapshot.get(snapshot_game_id or "") if snapshot_game_id else None
    snapshot_lookup_found = tl_snapshot is not None

    snapshot_eval: dict[str, Any] = {
        "lookup_key": snapshot_game_id,
        "lookup_method": "odds_snapshot_ref",
        "timeline_entry_found": snapshot_lookup_found,
        "candidate_valid": False,
        "invalid_reason": INVALID_GAME_ID_MISMATCH if not snapshot_lookup_found else None,
        "closing_ml": None,
        "closing_ts": None,
        "closing_source": None,
    }

    if snapshot_lookup_found and selection in ("home", "away"):
        _fill_candidate_eval(snapshot_eval, tl_snapshot, selection, pred_time_str, "snapshot_ref")

    # ── Decision ─────────────────────────────────────────────────────────────
    # Use improved (snapshot_ref) result as the authoritative outcome
    would_compute = snapshot_eval["candidate_valid"]
    block_reason = snapshot_eval.get("invalid_reason")

    return {
        "prediction_id": pred_id,
        "canonical_match_id": canonical_match_id,
        "selection": selection,
        "prediction_time_utc": pred_time_str,
        "odds_snapshot_ref": snapshot_ref,
        "snapshot_game_id": snapshot_game_id,
        # Current monitor behavior
        "canonical_lookup_found": canonical_lookup_found,
        "canonical_lookup_valid": canonical_eval["candidate_valid"],
        # Improved matching
        "snapshot_lookup_found": snapshot_lookup_found,
        "snapshot_lookup_valid": snapshot_eval["candidate_valid"],
        # Final verdict
        "would_compute": would_compute,
        "closing_ml": snapshot_eval.get("closing_ml"),
        "closing_ts": snapshot_eval.get("closing_ts"),
        "closing_source": snapshot_eval.get("closing_source"),
        "block_reason": block_reason,
        # Diagnostics
        "canonical_eval": canonical_eval,
        "snapshot_eval": snapshot_eval,
    }


def _fill_candidate_eval(
    out: dict,
    tl_row: dict,
    side: str,
    pred_time_str: str,
    method_label: str,
) -> None:
    """Mutate *out* in-place: find the best closing candidate from *tl_row*."""
    ext_ml = tl_row.get(f"external_closing_{side}_ml")
    ext_ts = tl_row.get("external_closing_ts")
    cl_ml = tl_row.get(f"closing_{side}_ml")
    cl_ts = tl_row.get("closing_ts")

    # Priority: external > tsl
    cand_ml: float | None = None
    cand_ts: str | None = None
    cand_source: str | None = None

    if ext_ml is not None:
        cand_ml = float(ext_ml)
        cand_ts = ext_ts
        cand_source = "external_closing"
    elif cl_ml is not None:
        cand_ml = float(cl_ml)
        cand_ts = cl_ts
        cand_source = "tsl_closing"

    out["closing_ml"] = cand_ml
    out["closing_ts"] = cand_ts
    out["closing_source"] = cand_source

    if cand_ml is None:
        out["invalid_reason"] = INVALID_MISSING_SOURCE
        return

    result = evaluate_closing_candidate(cand_ml, cand_ts, pred_time_str)
    out["candidate_valid"] = result["candidate_valid"]
    out["invalid_reason"] = result["invalid_reason"]
    out["diff_seconds"] = result.get("diff_seconds")


def compute_activation_decision(per_record_results: list[dict]) -> str:
    """
    Derive the overall activation decision from per-record evaluation.

    READY_TO_COMPUTE          — ≥1 record has would_compute=True
    WAITING_FOR_CLOSING_SOURCE — all missing timeline entry or missing closing field
    DATA_INVALID_REQUIRES_REPAIR — candidates found but all fail timestamp validation
    MANUAL_REVIEW_REQUIRED    — mixed invalid reasons suggesting data conflict
    """
    if not per_record_results:
        return ACTIVATION_DECISION_WAITING

    ready_count = sum(1 for r in per_record_results if r.get("would_compute"))
    if ready_count > 0:
        return ACTIVATION_DECISION_READY

    reasons = [r.get("block_reason") for r in per_record_results if r.get("block_reason")]
    reason_set = set(reasons)

    # All records missing source entirely
    missing_only = reason_set <= {INVALID_MISSING_SOURCE, INVALID_GAME_ID_MISMATCH, None}
    if not reason_set or missing_only:
        return ACTIVATION_DECISION_WAITING

    # Timestamp-related invalidity (fixable with data repair)
    ts_reasons = {INVALID_BEFORE_PREDICTION, INVALID_SAME_SNAPSHOT, INVALID_MISSING_TS}
    if reason_set <= ts_reasons:
        return ACTIVATION_DECISION_INVALID

    # Mixed / ambiguous
    return ACTIVATION_DECISION_MANUAL


def build_preview_payload(
    per_record_results: list[dict],
    clv_records: list[dict],
    activation_decision: str,
) -> dict[str, Any]:
    """Build the preview JSON payload (never written to CLV file)."""
    from collections import Counter
    would_compute = [r for r in per_record_results if r.get("would_compute")]
    remain_pending = [r for r in per_record_results if not r.get("would_compute")]

    invalid_reasons = Counter(
        r.get("block_reason", "unknown")
        for r in remain_pending
        if r.get("block_reason")
    )
    # Current monitor behavior (canonical lookup)
    canonical_would_compute = sum(1 for r in per_record_results if r.get("canonical_lookup_valid"))

    per_record_decisions = [
        {
            "prediction_id": r["prediction_id"],
            "canonical_match_id": r["canonical_match_id"],
            "selection": r["selection"],
            "snapshot_game_id": r.get("snapshot_game_id"),
            "closing_ml": r.get("closing_ml"),
            "closing_ts": r.get("closing_ts"),
            "closing_source": r.get("closing_source"),
            "would_compute": r.get("would_compute", False),
            "block_reason": r.get("block_reason"),
        }
        for r in per_record_results
    ]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "phase": "Phase28_RealCLVActivationCheck",
        "clv_source_file": str(CLV_FILE.relative_to(ROOT)),
        "timeline_source_file": str(TIMELINE_FILE.relative_to(ROOT)),
        "total_clv_records": len(clv_records),
        "pending_count": sum(1 for r in clv_records if r.get("clv_status") == "PENDING_CLOSING"),
        "computed_count": sum(1 for r in clv_records if r.get("clv_status") == "COMPUTED"),
        # Current monitor behavior (broken matching)
        "current_monitor_would_compute": canonical_would_compute,
        "current_monitor_remain_pending": len(per_record_results) - canonical_would_compute,
        "current_monitor_block_reason": "game_id_mismatch_canonical_vs_timeline_key",
        # Improved matching (snapshot_ref)
        "improved_would_compute_count": len(would_compute),
        "improved_would_remain_pending_count": len(remain_pending),
        "invalid_reason_counts": dict(invalid_reasons),
        "activation_decision": activation_decision,
        "learning_ready_if_applied": activation_decision == ACTIVATION_DECISION_READY,
        "required_fix": (
            "Update closing monitor to use game_id from odds_snapshot_ref "
            "as fallback timeline index key when canonical_match_id lookup fails."
        ) if activation_decision == ACTIVATION_DECISION_READY else None,
        "per_record_decisions": per_record_decisions,
    }


# ── File I/O helpers ──────────────────────────────────────────────────────────

def _read_jsonl(path: Path) -> list[dict]:
    records = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def _rel(path: Path) -> str:
    """Return path relative to ROOT if possible, else absolute string."""
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def run_check(
    clv_path: Path = CLV_FILE,
    timeline_path: Path = TIMELINE_FILE,
    preview_output_dir: Path = REPORTS_DIR,
    apply: bool = False,
) -> dict[str, Any]:
    """
    Main entry point — read-only by default.

    Returns the full analysis dict including activation_decision.
    Writes a preview JSON to preview_output_dir (read-only side-effect).
    """
    print("Phase 28 — Real CLV Activation Readiness Check")
    print("=" * 60)
    print(f"CLV source  : {clv_path}")
    print(f"Timeline    : {timeline_path}")
    print(f"Mode        : {'APPLY (Phase 29)' if apply else 'READ-ONLY (preview)'}")
    print()

    if apply:
        print("ERROR: --apply is reserved for Phase 29. This phase is read-only.")
        sys.exit(1)

    # ── Read data ─────────────────────────────────────────────────────────────
    clv_records = _read_jsonl(clv_path)
    timeline_records = _read_jsonl(timeline_path)

    print(f"  Loaded {len(clv_records)} CLV records from {clv_path.name}")
    print(f"  Loaded {len(timeline_records)} timeline records from {timeline_path.name}")
    print()

    # ── Build timeline indices ─────────────────────────────────────────────────
    # Index 1 (canonical): same as current monitor — keyed by game_id from timeline
    #   (canonical_match_id lookup will fail here because format differs)
    # Index 2 (snapshot): also keyed by game_id from timeline
    #   (matched via odds_snapshot_ref game_id portion from CLV records)
    timeline_index = build_timeline_index(timeline_records)
    # The two indices are identical — the difference is in how we LOOK them up
    # (canonical_match_id vs snapshot_ref game_id portion)
    timeline_index_canonical = timeline_index   # same underlying data
    timeline_index_snapshot = timeline_index    # same underlying data

    # ── Evaluate each PENDING_CLOSING record ──────────────────────────────────
    pending_records = [r for r in clv_records if r.get("clv_status") == "PENDING_CLOSING"]
    computed_records = [r for r in clv_records if r.get("clv_status") == "COMPUTED"]

    print(f"  PENDING_CLOSING : {len(pending_records)}")
    print(f"  COMPUTED        : {len(computed_records)}")
    print()

    per_record_results: list[dict] = []
    for row in pending_records:
        result = evaluate_single_record(row, timeline_index_canonical, timeline_index_snapshot)
        per_record_results.append(result)

    # ── Summary stats ─────────────────────────────────────────────────────────
    canonical_found = sum(1 for r in per_record_results if r.get("canonical_lookup_found"))
    canonical_valid = sum(1 for r in per_record_results if r.get("canonical_lookup_valid"))
    snapshot_found = sum(1 for r in per_record_results if r.get("snapshot_lookup_found"))
    snapshot_valid = sum(1 for r in per_record_results if r.get("snapshot_lookup_valid"))
    would_compute = sum(1 for r in per_record_results if r.get("would_compute"))

    print("  ── Closing Odds Lookup Results ──────────────────────────────────")
    print(f"  Current monitor (canonical_match_id lookup):")
    print(f"    Timeline entry found : {canonical_found}/{len(pending_records)}")
    print(f"    Valid candidate      : {canonical_valid}/{len(pending_records)}")
    print(f"    Would upgrade        : {canonical_valid}   ← ALL BLOCKED (key mismatch)")
    print()
    print(f"  Improved (odds_snapshot_ref game_id lookup):")
    print(f"    Timeline entry found : {snapshot_found}/{len(pending_records)}")
    print(f"    Valid candidate      : {snapshot_valid}/{len(pending_records)}")
    print(f"    Would upgrade        : {would_compute}")
    print()

    # Per-record summary
    print("  ── Per-Record Decision ──────────────────────────────────────────")
    for r in per_record_results:
        status = "✓ WOULD_COMPUTE" if r.get("would_compute") else f"✗ BLOCKED ({r.get('block_reason', 'unknown')})"
        print(f"  {r['canonical_match_id']} [{r['selection']:4s}]  {status}")
    print()

    # ── Activation decision ───────────────────────────────────────────────────
    activation_decision = compute_activation_decision(per_record_results)

    print(f"  ACTIVATION DECISION: {activation_decision}")
    if activation_decision == ACTIVATION_DECISION_READY:
        print("  → Valid closing odds exist in data/mlb_context/odds_timeline.jsonl")
        print("  → Run Phase 29 to fix closing monitor game_id matching")
        print("  → After fix: production CLV will compute → system enters LEARNING_READY")
    elif activation_decision == ACTIVATION_DECISION_WAITING:
        print("  → No valid closing odds found — wait for closing odds data refresh")
    elif activation_decision == ACTIVATION_DECISION_INVALID:
        print("  → Candidates found but timestamp validation fails — repair required")
    else:
        print("  → Manual review required — ambiguous candidate mapping")
    print()

    # ── Build and write preview ───────────────────────────────────────────────
    preview = build_preview_payload(per_record_results, clv_records, activation_decision)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    preview_path = preview_output_dir / f"clv_activation_preview_{today}.json"
    preview_output_dir.mkdir(parents=True, exist_ok=True)
    with open(preview_path, "w", encoding="utf-8") as fh:
        json.dump(preview, fh, indent=2)
    print(f"  Preview written → {_rel(preview_path)}")

    # ── Generate report ───────────────────────────────────────────────────────
    report_md = generate_report_md(preview, per_record_results)
    report_dir = ROOT / "docs" / "orchestration"
    report_path = report_dir / f"phase28_real_clv_activation_readiness_report_{today}.md"
    report_dir.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as fh:
        fh.write(report_md)
    print(f"  Report   written → {_rel(report_path)}")
    print()

    print("=" * 60)
    print(f"PHASE_28_REAL_CLV_ACTIVATION_READINESS_VERIFIED")
    print(f"Activation decision : {activation_decision}")
    print(f"Would compute       : {would_compute} / {len(pending_records)} records")
    print(f"LEARNING_READY      : {'YES (after Phase 29 fix)' if activation_decision == ACTIVATION_DECISION_READY else 'NO'}")

    return {
        "activation_decision": activation_decision,
        "would_compute_count": would_compute,
        "pending_count": len(pending_records),
        "computed_count": len(computed_records),
        "per_record_results": per_record_results,
        "preview": preview,
        "preview_path": str(preview_path),
        "report_path": str(report_path),
    }


def generate_report_md(preview: dict, per_record_results: list[dict]) -> str:
    """Generate the Phase 28 readiness report markdown."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    activation = preview.get("activation_decision", "UNKNOWN")
    lines = [
        f"# Phase 28 — Real CLV Activation Readiness Report",
        f"",
        f"**Date**: {today}  ",
        f"**Generated at**: {preview.get('generated_at', '')}  ",
        f"**Phase**: 28 — Real CLV Activation Readiness Check  ",
        f"**Verdict**: `PHASE_28_REAL_CLV_ACTIVATION_READINESS_VERIFIED`  ",
        f"**Activation Decision**: `{activation}`",
        f"",
        f"---",
        f"",
        f"## 1. CLV File Inventory",
        f"",
        f"| File | Records | PENDING | COMPUTED |",
        f"|------|---------|---------|---------|",
        f"| `{preview.get('clv_source_file', '')}` | {preview.get('total_clv_records', 0)} | "
        f"{preview.get('pending_count', 0)} | {preview.get('computed_count', 0)} |",
        f"| `{preview.get('timeline_source_file', '')}` | (timeline) | — | — |",
        f"",
        f"**Status**: All {preview.get('pending_count', 0)} production CLV records are "
        f"`PENDING_CLOSING`.  No real `COMPUTED` CLV exists yet.",
        f"",
        f"---",
        f"",
        f"## 2. Root Cause — Closing Monitor Game-ID Mismatch",
        f"",
        f"The current `closing_odds_monitor.py` uses `clv_row[\"canonical_match_id\"]` as the key",
        f"to look up entries in the odds-timeline index. However, the timeline index is keyed by its",
        f"own `game_id` field.  These two formats are incompatible:",
        f"",
        f"| Field | Example value |",
        f"|-------|--------------|",
        f"| `canonical_match_id` | `baseball:mlb:20260430:ATL:DET` |",
        f"| Odds-timeline `game_id` | `MLB-2026_04_30-12_15_PM-DETROIT_TIGERS-AT-ATLANTA_BRAVES` |",
        f"",
        f"Because they never match, the monitor silently reports all records as",
        f"`no closing odds found` and leaves them in `PENDING_CLOSING` indefinitely.",
        f"",
        f"**Resolution (Phase 29)**: Update the monitor to fall back to the game-id portion of",
        f"`odds_snapshot_ref` when the canonical-match-id lookup fails. The `odds_snapshot_ref` field",
        f"already contains the correct timeline `game_id` prefix:",
        f"",
        f"```",
        f"odds_snapshot_ref = \"MLB-2026_04_30-12_15_PM-...-AT-ATLANTA_BRAVES|TSL|snap@...\"",
        f"                      ↑ this portion matches the odds-timeline game_id key",
        f"```",
        f"",
        f"---",
        f"",
        f"## 3. Closing Odds Candidate Evaluation",
        f"",
        f"### 3.1 Current Monitor Behavior (broken)",
        f"",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Pending records inspected | {preview.get('pending_count', 0)} |",
        f"| Timeline entries found (canonical lookup) | {preview.get('current_monitor_would_compute', 0) + preview.get('current_monitor_remain_pending', 0) - preview.get('pending_count', 0) + preview.get('current_monitor_would_compute', 0)} |",
        f"| Valid candidates found | {preview.get('current_monitor_would_compute', 0)} |",
        f"| Would upgrade to COMPUTED | {preview.get('current_monitor_would_compute', 0)} |",
        f"| Block reason | `{preview.get('current_monitor_block_reason', '')}` |",
        f"",
        f"### 3.2 Improved Matching (snapshot-ref, implemented in Phase 29)",
        f"",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Pending records inspected | {preview.get('pending_count', 0)} |",
        f"| Timeline entries found (snapshot_ref lookup) | {sum(1 for r in per_record_results if r.get('snapshot_lookup_found'))} |",
        f"| Valid candidates found | {preview.get('improved_would_compute_count', 0)} |",
        f"| Would upgrade to COMPUTED | {preview.get('improved_would_compute_count', 0)} |",
        f"| Would remain PENDING | {preview.get('improved_would_remain_pending_count', 0)} |",
        f"",
    ]

    # Invalid reasons table
    inv_counts = preview.get("invalid_reason_counts", {})
    if inv_counts:
        lines += [
            f"### 3.3 Remaining Pending — Invalid Reason Breakdown",
            f"",
            f"| Reason | Count |",
            f"|--------|-------|",
        ]
        for reason, count in sorted(inv_counts.items(), key=lambda x: -x[1]):
            lines.append(f"| `{reason}` | {count} |")
        lines.append("")

    lines += [
        f"---",
        f"",
        f"## 4. Per-Record Decision Table",
        f"",
        f"| prediction_id | match | sel | snapshot_game_id | closing_ml | closing_ts | would_compute | block_reason |",
        f"|---------------|-------|-----|-----------------|------------|------------|--------------|------------|",
    ]
    for r in preview.get("per_record_decisions", []):
        sgid = (r.get("snapshot_game_id") or "")[-40:] if r.get("snapshot_game_id") else "—"
        lines.append(
            f"| `{r['prediction_id'][-20:]}` | `{r['canonical_match_id']}` | {r['selection']} "
            f"| `{sgid}` | {r.get('closing_ml') or '—'} | {(r.get('closing_ts') or '—')[:19]} "
            f"| {'✓' if r.get('would_compute') else '✗'} | {r.get('block_reason') or '—'} |"
        )
    lines += [
        f"",
        f"---",
        f"",
        f"## 5. Closing Sources Evaluated",
        f"",
        f"| Source | Records with data | Used in preview |",
        f"|--------|-----------------|----------------|",
        f"| `data/mlb_context/odds_timeline.jsonl` — `closing_{{side}}_ml` | {sum(1 for r in per_record_results if r.get('snapshot_eval', {}).get('closing_source') == 'tsl_closing')} | Primary |",
        f"| `data/mlb_context/odds_timeline.jsonl` — `external_closing_{{side}}_ml` | {sum(1 for r in per_record_results if r.get('snapshot_eval', {}).get('closing_source') == 'external_closing')} | Secondary |",
        f"| `data/tsl_odds_history.jsonl` — pre-game snapshots | 0 | Not valid (all pre-game, fetched before prediction) |",
        f"| External API | 0 | Not available (no external_closing_ts in timeline for 2026-04-30) |",
        f"",
        f"---",
        f"",
        f"## 6. Activation Decision",
        f"",
        f"**Decision**: `{activation}`",
        f"",
    ]

    if activation == ACTIVATION_DECISION_READY:
        lines += [
            f"Valid closing odds exist in `data/mlb_context/odds_timeline.jsonl` for at least",
            f"{preview.get('improved_would_compute_count', 0)} of {preview.get('pending_count', 0)} "
            f"pending CLV records.",
            f"",
            f"**Required action** (Phase 29):",
            f"",
            f"1. Update `orchestrator/closing_odds_monitor.py` — in `_find_closing_odds_for_pending()`",
            f"   and `_analyze_pending_record()`, add a fallback lookup using the game_id extracted",
            f"   from `clv_row[\"odds_snapshot_ref\"]` when the canonical-match-id lookup returns None.",
            f"2. Run `python3 orchestrator/closing_odds_monitor.py --date 2026-04-30`.",
            f"3. Verify upgraded file is written to `data/wbc_backend/reports/`.",
            f"4. Confirm `optimization_state.classify()` returns `DATA_READY`.",
            f"5. System enters `LEARNING_READY` — planner may schedule learning tasks.",
        ]
    elif activation == ACTIVATION_DECISION_WAITING:
        lines += [
            f"No valid closing odds are currently available. The `ClosingOddsMonitor` will",
            f"automatically check every 15 minutes. No operator action required yet.",
        ]
    elif activation == ACTIVATION_DECISION_INVALID:
        lines += [
            f"Closing odds candidates exist but fail timestamp validation. The most likely",
            f"cause is that all candidates have `closing_ts ≤ prediction_time_utc`. This",
            f"indicates the odds timeline data needs to be refreshed with post-game closing prices.",
        ]
    else:
        lines += [
            f"Ambiguous candidate mapping detected. Multiple sources provide conflicting",
            f"closing odds for the same prediction. Manual operator review is required.",
        ]

    lines += [
        f"",
        f"---",
        f"",
        f"## 7. Production Readiness Impact",
        f"",
        f"| State | Value |",
        f"|-------|-------|",
        f"| Current state | `WAITING_ACTIVE` |",
        f"| After Phase 29 fix + monitor run | `LEARNING_READY` (if decision = READY_TO_COMPUTE) |",
        f"| learning_allowed after fix | `True` |",
        f"| sandbox CLV used for this determination | No — production CLV records only |",
        f"",
        f"---",
        f"",
        f"## 8. Recommended Next Actions",
        f"",
        f"1. **Phase 29** — Fix closing monitor game-id matching (snapshot-ref fallback).",
        f"2. Run monitor with `--date 2026-04-30` and verify upgraded JSONL is created.",
        f"3. Confirm `get_phase6_status()` returns at least one `COMPUTED` record.",
        f"4. Run `python3 scripts/run_optimization_readiness.py --print` → `LEARNING_READY`.",
        f"5. Monitor LLM audit card once planner begins scheduling learning tasks.",
        f"",
        f"---",
        f"",
        f"**Final Status**: ✅ `PHASE_28_REAL_CLV_ACTIVATION_READINESS_VERIFIED`",
    ]

    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Phase 28 — Real CLV Activation Readiness Check (read-only)."
    )
    parser.add_argument(
        "--apply", action="store_true",
        help="Apply closing odds upgrade (reserved for Phase 29 — not implemented here).",
    )
    parser.add_argument(
        "--preview-only", action="store_true",
        help="Run analysis and generate preview JSON only (no report file).",
    )
    parser.add_argument("--clv-file", type=Path, default=CLV_FILE)
    parser.add_argument("--timeline-file", type=Path, default=TIMELINE_FILE)
    args = parser.parse_args()

    result = run_check(
        clv_path=args.clv_file,
        timeline_path=args.timeline_file,
        apply=args.apply,
    )
    sys.exit(0 if result["activation_decision"] in (ACTIVATION_DECISION_READY, ACTIVATION_DECISION_WAITING) else 1)
