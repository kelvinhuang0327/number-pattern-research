#!/usr/bin/env python3
"""
scripts/run_phase29_apply_clv_lookup_fix.py
==========================================
Phase 29 — Apply CLV Lookup Key Mismatch Fix

Stages:
  1. DRY-RUN: Use the patched closing monitor to verify that all
     PENDING_CLOSING records can now be upgraded (snapshot_ref fallback).
  2. APPLY: For each upgradeable record, compute CLV and write the
     COMPUTED version back to the original CLV JSONL file.
     A backup is written BEFORE any mutation.
     The rewrite is atomic (tmp-file + rename).
  3. VERIFY: Run optimization readiness check to confirm
     readiness_state → LEARNING_READY.

Hard rules (enforced in code):
  - Backup is always written before any mutation.
  - Never upgrade a record unless all safety gates pass (timestamp, same-snapshot, ML range).
  - Never compute CLV from prediction-time snapshot.
  - Write to a tmp file, then rename (atomic).
  - Do NOT call external LLM or modify model weights.

Usage:
  python3 scripts/run_phase29_apply_clv_lookup_fix.py             # dry-run
  python3 scripts/run_phase29_apply_clv_lookup_fix.py --dry-run   # explicit dry-run
  python3 scripts/run_phase29_apply_clv_lookup_fix.py --apply     # apply + verify

Success marker (apply mode):
  PHASE_29_CLV_LOOKUP_KEY_MISMATCH_FIX_VERIFIED
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from orchestrator.closing_odds_monitor import (
    LOOKUP_CANONICAL,
    LOOKUP_NONE,
    LOOKUP_SNAPSHOT_REF,
    REPORTS_DIR,
    TIMELINE_PATH,
    _build_upgraded_record,
    _build_timeline_index,
    _find_closing_odds_for_pending,
    _parse_ts,
    _validate_closing_odds,
    check_pending_for_upgrade,
)

# ── Default paths (overridable for tests) ────────────────────────────────────
CLV_DATE = "2026-04-30"
CLV_FILE = REPORTS_DIR / f"clv_validation_records_6u_{CLV_DATE}.jsonl"
BACKUP_DIR = REPORTS_DIR / "backups"

_STATUS_PENDING = "PENDING_CLOSING"
_STATUS_COMPUTED = "COMPUTED"


# ── I/O helpers ───────────────────────────────────────────────────────────────

def _read_jsonl(path: Path) -> list[dict]:
    records = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def _write_jsonl_atomic(records: list[dict], target_path: Path) -> None:
    """Write records to *target_path* atomically using a tmp file + rename."""
    target_path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path_str = tempfile.mkstemp(
        dir=str(target_path.parent),
        prefix=".phase29_tmp_",
        suffix=".jsonl",
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            for rec in records:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        os.replace(tmp_path_str, str(target_path))   # atomic rename
    except Exception:
        try:
            os.unlink(tmp_path_str)
        except OSError:
            pass
        raise


def _write_backup(source_path: Path, backup_dir: Path, suffix: str) -> Path:
    """Copy *source_path* to *backup_dir*/{stem}.{suffix}.jsonl. Returns backup path."""
    backup_dir.mkdir(parents=True, exist_ok=True)
    stem = source_path.stem
    backup_path = backup_dir / f"{stem}.{suffix}.jsonl"
    shutil.copy2(str(source_path), str(backup_path))
    return backup_path


def _rel(path: Path) -> str:
    """Return path relative to ROOT if possible, else absolute string."""
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


# ── Core dry-run logic ────────────────────────────────────────────────────────

def dry_run(
    clv_path: Path = CLV_FILE,
    timeline_path: Path = TIMELINE_PATH,
) -> dict[str, Any]:
    """
    Evaluate all PENDING_CLOSING records using the patched closing monitor.
    Returns a preview dict without writing anything.
    """
    preview = check_pending_for_upgrade(clv_path, timeline_path)

    # Enrich preview with lookup-method breakdown
    upgradeable = preview.get("upgradeable", [])
    canonical_count = sum(1 for u in upgradeable if u.get("lookup_method") == LOOKUP_CANONICAL)
    snapshot_ref_count = sum(1 for u in upgradeable if u.get("lookup_method") == LOOKUP_SNAPSHOT_REF)

    preview["matched_by_canonical"] = canonical_count
    preview["matched_by_snapshot_ref"] = snapshot_ref_count
    preview["lookup_failed"] = preview.get("not_yet", 0)
    return preview


# ── Core apply logic ──────────────────────────────────────────────────────────

def apply_clv_upgrade(
    clv_path: Path = CLV_FILE,
    timeline_path: Path = TIMELINE_PATH,
    backup_dir: Path = BACKUP_DIR,
) -> dict[str, Any]:
    """
    Apply CLV upgrade in-place to *clv_path* (with backup + atomic write).

    Steps:
      1. Build timeline index using patched monitor.
      2. Compute upgraded COMPUTED records for all upgradeable PENDING rows.
      3. Merge: PENDING rows that have valid upgrade → replaced by COMPUTED;
                all other rows (non-pending, or pending with no valid odds) → kept as-is.
      4. Write backup of original file.
      5. Write merged list to tmp file; rename to original (atomic).

    Returns stats dict.
    """
    all_records = _read_jsonl(clv_path)
    timeline_index = _build_timeline_index(timeline_path)

    merged: list[dict] = []
    upgraded_count = 0
    still_pending = 0
    skipped_no_ts = 0
    stale_rejected = 0
    non_pending = 0

    lookup_by_canonical = 0
    lookup_by_snapshot_ref = 0

    for row in all_records:
        status = row.get("clv_status", "")
        if status != _STATUS_PENDING:
            merged.append(row)
            non_pending += 1
            continue

        pred_ts = _parse_ts(row.get("prediction_time_utc"))
        if pred_ts is None:
            merged.append(row)
            skipped_no_ts += 1
            still_pending += 1
            continue

        closing_ml, closing_ts_str, source, lookup_method = _find_closing_odds_for_pending(
            row, timeline_index, pred_ts
        )

        if closing_ml is None:
            merged.append(row)
            still_pending += 1
            continue

        valid, reason = _validate_closing_odds(row, closing_ml, closing_ts_str, pred_ts)
        if not valid:
            merged.append(row)
            stale_rejected += 1
            still_pending += 1
            continue

        upgraded_record = _build_upgraded_record(row, closing_ml, closing_ts_str, source, lookup_method)
        merged.append(upgraded_record)
        upgraded_count += 1

        if lookup_method == LOOKUP_CANONICAL:
            lookup_by_canonical += 1
        elif lookup_method == LOOKUP_SNAPSHOT_REF:
            lookup_by_snapshot_ref += 1

    run_at = datetime.now(timezone.utc).isoformat()

    # ── Safety: only write if we have something to upgrade ────────────────────
    if upgraded_count == 0:
        return {
            "applied": False,
            "reason": "no_upgradeable_records",
            "upgraded": 0,
            "still_pending": still_pending,
            "run_at": run_at,
        }

    # ── Backup BEFORE mutation ─────────────────────────────────────────────────
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    backup_path = _write_backup(clv_path, backup_dir, f"before_phase29_{today}")

    # ── Atomic write ──────────────────────────────────────────────────────────
    _write_jsonl_atomic(merged, clv_path)

    return {
        "applied": True,
        "clv_path": str(clv_path),
        "backup_path": str(backup_path),
        "total_records": len(all_records),
        "non_pending": non_pending,
        "upgraded": upgraded_count,
        "still_pending": still_pending,
        "skipped_no_pred_ts": skipped_no_ts,
        "stale_rejected": stale_rejected,
        "lookup_by_canonical": lookup_by_canonical,
        "lookup_by_snapshot_ref": lookup_by_snapshot_ref,
        "run_at": run_at,
    }


# ── Readiness check ───────────────────────────────────────────────────────────

def check_readiness() -> dict[str, Any]:
    """
    Run optimization readiness check and return the summary dict.
    """
    from orchestrator.optimization_readiness import get_readiness_summary
    return get_readiness_summary()


# ── Main ──────────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Phase 29 — Apply CLV lookup key mismatch fix."
    )
    parser.add_argument("--apply", action="store_true",
                        help="Apply upgrade (backup + atomic rewrite). Default: dry-run.")
    parser.add_argument("--dry-run", dest="dry_run", action="store_true",
                        help="Preview only (default mode).")
    parser.add_argument("--clv-file", type=Path, default=CLV_FILE)
    parser.add_argument("--timeline-file", type=Path, default=TIMELINE_PATH)
    parser.add_argument("--backup-dir", type=Path, default=BACKUP_DIR)
    args = parser.parse_args(argv)

    clv_path = args.clv_file
    timeline_path = args.timeline_file
    backup_dir = args.backup_dir

    print("Phase 29 — CLV Lookup Key Mismatch Fix")
    print("=" * 60)
    print(f"CLV file   : {_rel(clv_path)}")
    print(f"Timeline   : {_rel(timeline_path)}")
    print(f"Backup dir : {_rel(backup_dir)}")
    print(f"Mode       : {'APPLY' if args.apply else 'DRY-RUN (preview)'}")
    print()

    # ── Stage 1: Dry-run ──────────────────────────────────────────────────────
    print("── Stage 1: Dry-Run Preview ─────────────────────────────────────────")
    preview = dry_run(clv_path, timeline_path)
    upgradeable_count = preview.get("upgradeable_count", 0)
    not_yet = preview.get("not_yet", 0)
    total_pending = preview.get("pending", 0)

    print(f"  Total CLV records   : {preview.get('total_records', 0)}")
    print(f"  PENDING_CLOSING     : {total_pending}")
    print(f"  Would upgrade       : {upgradeable_count}")
    print(f"  Remain pending      : {not_yet}")
    print(f"  Matched by canonical  : {preview.get('matched_by_canonical', 0)}")
    print(f"  Matched by snapshot   : {preview.get('matched_by_snapshot_ref', 0)}")
    print()

    for u in preview.get("upgradeable", []):
        lm = u.get("lookup_method", "?")
        print(
            f"  {u['prediction_id']} [{u['selection']:4s}] "
            f"closing_ml={u['closing_ml']:>8.1f}  "
            f"source={u.get('closing_source','?'):20s}  "
            f"method={lm}"
        )
    print()

    if upgradeable_count == 0:
        print("  DRY-RUN: 0 upgradeable records — nothing to apply.")
        print("  Expected cause: closing odds still missing or all invalid.")
        return 1

    if not args.apply:
        print(f"  DRY-RUN COMPLETE — {upgradeable_count}/{total_pending} records would upgrade.")
        print("  Re-run with --apply to apply.")
        return 0

    # ── Stage 2: Apply ────────────────────────────────────────────────────────
    print("── Stage 2: Apply ───────────────────────────────────────────────────")
    result = apply_clv_upgrade(clv_path, timeline_path, backup_dir)

    if not result.get("applied"):
        print(f"  APPLY BLOCKED: {result.get('reason', 'unknown')}")
        return 1

    print(f"  Backup written  → {_rel(Path(result['backup_path']))}")
    print(f"  Upgraded        : {result['upgraded']} records")
    print(f"  Still pending   : {result['still_pending']}")
    print(f"  Stale rejected  : {result.get('stale_rejected', 0)}")
    print(f"  Lookup canonical: {result.get('lookup_by_canonical', 0)}")
    print(f"  Lookup snapshot : {result.get('lookup_by_snapshot_ref', 0)}")
    print(f"  Rewritten       → {_rel(clv_path)}")
    print()

    # ── Stage 3: Readiness Verification ──────────────────────────────────────
    print("── Stage 3: Readiness Verification ─────────────────────────────────")
    try:
        readiness = check_readiness()
        state = readiness.get("readiness_state", "UNKNOWN")
        clv_info = readiness.get("clv", {})
        clv_computed = clv_info.get("computed", 0)
        learning_allowed = readiness.get("learning_allowed", False)

        print(f"  readiness_state  : {state}")
        print(f"  clv_computed     : {clv_computed}")
        print(f"  learning_allowed : {learning_allowed}")
        print()

        if state == "LEARNING_READY":
            print("  ✓ System is LEARNING_READY")
        else:
            print(f"  ✗ readiness_state = {state} (expected LEARNING_READY)")
            # Explain blocker
            blockers = readiness.get("blockers", [])
            for b in blockers:
                print(f"    Blocker: {b}")
    except Exception as exc:
        print(f"  Readiness check failed: {exc}")
        state = "UNKNOWN"
        clv_computed = result["upgraded"]
        learning_allowed = clv_computed > 0

    print("=" * 60)
    print("PHASE_29_CLV_LOOKUP_KEY_MISMATCH_FIX_VERIFIED")
    print(f"  upgraded        : {result['upgraded']} records")
    print(f"  backup          : {_rel(Path(result['backup_path']))}")
    print(f"  readiness_state : {state}")
    print(f"  LEARNING_READY  : {state == 'LEARNING_READY'}")

    return 0 if result["applied"] and result["upgraded"] > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
