"""
p48_powerlotto_wave4_production_apply.py
=========================================
P48 Wave 4 — POWER_LOTTO Production Apply

Applies 4500 replay rows for the 3 Wave 4 POWER_LOTTO strategies
(verified by P47 dry-run rehearsal) to the production database.

This script is the authorized production-apply companion to P47. It:
  1. Validates pre-flight: production rows == 37960 (P47 baseline)
  2. Runs pre-apply duplicate check: expects 0 existing P48 rows
  3. Regenerates the same 4500 rows as P47 (deterministic, same algorithm)
  4. Applies Policy A for actual_special is NULL: skips such rows, records count
  5. Applies rows to production inside a single atomic transaction
  6. Verifies post-apply: production rows == 37960 + inserted_count
  7. Validates POWER_LOTTO two-zone semantics in inserted rows
  8. Saves apply manifest to outputs/replay/p48_powerlotto_wave4_production_apply_20260524.json

Row semantics:
  - dry_run = 0                       (production row, not a rehearsal)
  - lifecycle = DRY_RUN               (strategy lifecycle; NOT promoted to ONLINE)
  - controlled_apply_id = "P48_POWERLOTTO_WAVE4_4500_PROD_20260524"
  - truth_level = "POWERLOTTO_WAVE4_STRATEGY_BACKFILL_VERIFIED"
  - source = "P48_WAVE4_PRODUCTION_APPLY"
  - replay_run_id = "p48_wave4_prod_20260524"

POWER_LOTTO two-zone semantics:
  - predicted_numbers / actual_numbers: exactly 6 unique ints in [1, 38]
  - predicted_special / actual_special: exactly 1 int in [1, 8]
  - hit_count: first-zone hits ONLY (NEVER includes special)
  - special_hit: 1 if predicted_special == actual_special, else 0

actual_special is NULL — Policy A:
  - Skip rows where actual_special (from draw data) is NULL.
  - Record skip_count in apply manifest.
  - Expected skip_count = 0 (all POWER_LOTTO draws have non-null specials).
  - Inserted rows = 4500 - skip_count.

LIFECYCLE: All 3 strategies remain DRY_RUN.
           No lifecycle promotion. No registry mutation.

GOVERNANCE:
  - Must be run on branch p48-powerlotto-wave4-production-apply
  - Production DB write is one-way; rollback requires explicit intervention
  - Authorized by user phrase: YES apply P48 production wave4 powerlotto

STRATEGIES (3):
  pp3_freqort_4bet, midfreq_fourier_mk_3bet, midfreq_fourier_2bet

Usage:
  python3 scripts/p48_powerlotto_wave4_production_apply.py
  python3 scripts/p48_powerlotto_wave4_production_apply.py \\
      --json-out outputs/replay/p48_powerlotto_wave4_production_apply_20260524.json
  python3 scripts/p48_powerlotto_wave4_production_apply.py --dry-run-check
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple

# ─── Path setup ──────────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(REPO_ROOT))

PROD_DB_PATH = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
OUTPUT_DIR   = REPO_ROOT / "outputs" / "replay"

# ─── Constants ────────────────────────────────────────────────────────────────

PRE_APPLY_PROD_ROWS   = 37960
WINDOW_PERIODS        = 1500
STRATEGIES_COUNT      = 3
EXPECTED_APPLIED_ROWS = WINDOW_PERIODS * STRATEGIES_COUNT  # 4500

CONTROLLED_APPLY_ID = "P48_POWERLOTTO_WAVE4_4500_PROD_20260524"
TRUTH_LEVEL         = "POWERLOTTO_WAVE4_STRATEGY_BACKFILL_VERIFIED"
SOURCE              = "P48_WAVE4_PRODUCTION_APPLY"
RUN_ID              = "p48_wave4_prod_20260524"

WAVE4_STRATEGY_IDS = [
    "pp3_freqort_4bet",
    "midfreq_fourier_mk_3bet",
    "midfreq_fourier_2bet",
]

# actual_special NULL policy
SPECIAL_NULL_POLICY = "A"  # skip rows where actual_special is NULL

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


# ─── Pre-flight check ─────────────────────────────────────────────────────────

def _check_prod_rows(expected: int) -> int:
    """Assert production replay row count is exactly `expected`. Returns count."""
    conn = sqlite3.connect(str(PROD_DB_PATH))
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays"
        ).fetchone()[0]
    finally:
        conn.close()
    if count != expected:
        raise AssertionError(
            f"PRODUCTION ROW COUNT MISMATCH: expected {expected}, got {count}."
        )
    return count


# ─── Pre-apply duplicate check ────────────────────────────────────────────────

def _duplicate_check() -> dict:
    """
    Check production DB for existing P48 rows.
    Looks for any rows matching (lottery_type=POWER_LOTTO, strategy_id in Wave4,
    truth_level = P48 or P47 dry-run label, or controlled_apply_id = P48 id).
    Expected: 0 existing P48 rows.
    """
    conn = sqlite3.connect(str(PROD_DB_PATH))
    try:
        # Check by controlled_apply_id
        by_apply_id = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE controlled_apply_id = ?",
            (CONTROLLED_APPLY_ID,),
        ).fetchone()[0]

        # Check by truth_level
        by_truth_level = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE truth_level = ?",
            (TRUTH_LEVEL,),
        ).fetchone()[0]

        # Check by run_id
        by_run_id = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE replay_run_id = ?",
            (RUN_ID,),
        ).fetchone()[0]

        # Check P47 dry-run label (should be 0 — P47 never wrote to production)
        p47_dryrun = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE truth_level = 'P47_WAVE4_POWERLOTTO_DRY_RUN'",
        ).fetchone()[0]

        per_strategy = {}
        for sid in WAVE4_STRATEGY_IDS:
            n = conn.execute(
                "SELECT COUNT(*) FROM strategy_prediction_replays "
                "WHERE lottery_type='POWER_LOTTO' AND strategy_id=? "
                "AND truth_level=?",
                (sid, TRUTH_LEVEL),
            ).fetchone()[0]
            per_strategy[sid] = n

    finally:
        conn.close()

    existing_p48 = max(by_apply_id, by_truth_level, by_run_id)
    return {
        "by_controlled_apply_id": by_apply_id,
        "by_truth_level": by_truth_level,
        "by_run_id": by_run_id,
        "p47_dryrun_in_production": p47_dryrun,
        "per_strategy_existing": per_strategy,
        "existing_p48_rows": existing_p48,
        "duplicate_check_pass": existing_p48 == 0 and p47_dryrun == 0,
    }


# ─── Draw loader ──────────────────────────────────────────────────────────────

def _load_powerlotto_draws() -> List[dict]:
    """
    Load all POWER_LOTTO draws from production DB, sorted chronologically.
    Returns list of dicts: [{draw, date, numbers, special}, ...]
    READ-ONLY — no writes.
    """
    conn = sqlite3.connect(str(PROD_DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT draw, date, numbers, special FROM draws "
            "WHERE lottery_type = 'POWER_LOTTO' "
            "ORDER BY CAST(draw AS INTEGER) ASC"
        ).fetchall()
    finally:
        conn.close()

    draws = []
    for row in rows:
        nums = json.loads(row["numbers"]) if isinstance(row["numbers"], str) else row["numbers"]
        draws.append({
            "draw":    row["draw"],
            "date":    row["date"],
            "numbers": [int(n) for n in nums],
            "special": int(row["special"]) if row["special"] is not None else None,
        })
    return draws


# ─── Provenance hash ──────────────────────────────────────────────────────────

def _provenance_hash(strategy_id: str, target_draw: str, numbers: List[int]) -> str:
    payload = f"{strategy_id}|{target_draw}|{sorted(numbers)}"
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


# ─── Row builder ──────────────────────────────────────────────────────────────

def _build_production_row(raw: dict, now_str: str) -> Optional[dict]:
    """
    Convert a generate_dryrun_rows() raw row to a production DB insert dict.

    Policy A: returns None if actual_special is NULL (row is skipped).
    Sets dry_run=0 (production), TRUTH_LEVEL, CONTROLLED_APPLY_ID, etc.
    """
    actual_special = raw.get("actual_special")

    # Policy A: skip rows where actual_special is NULL
    if actual_special is None:
        return None

    predicted_numbers = raw.get("predicted_numbers")
    predicted_special = raw.get("predicted_special")
    hit_numbers = raw.get("hit_numbers", [])
    hit_count = raw.get("hit_count", 0)
    special_hit = raw.get("special_hit", 0)

    prov_hash = (
        _provenance_hash(
            raw["strategy_id"],
            str(raw["target_draw"]),
            predicted_numbers if predicted_numbers else [],
        )
        if predicted_numbers
        else None
    )

    predicted_numbers_json = (
        json.dumps(sorted(predicted_numbers)) if predicted_numbers is not None else None
    )
    actual_numbers_json = json.dumps(raw.get("actual_numbers", []))
    hit_numbers_json = json.dumps(hit_numbers if hit_numbers else [])

    return {
        "lottery_type":             "POWER_LOTTO",
        "target_draw":              str(raw["target_draw"]),
        "target_date":              raw.get("draw_date"),
        "strategy_id":              raw["strategy_id"],
        "strategy_name":            raw.get("strategy_name"),
        "strategy_version":         raw.get("strategy_version"),
        "history_cutoff_draw":      raw.get("history_cutoff_draw"),
        "replay_status":            raw.get("replay_status", "PREDICTED"),
        "reject_reason":            raw.get("reject_reason"),
        "predicted_numbers":        predicted_numbers_json,
        "predicted_special":        predicted_special,
        "actual_numbers":           actual_numbers_json,
        "actual_special":           actual_special,
        "hit_numbers":              hit_numbers_json,
        "hit_count":                hit_count,
        "special_hit":              special_hit,
        "replay_run_id":            RUN_ID,
        "generated_at":             now_str,
        "truth_level":              TRUTH_LEVEL,
        "controlled_apply_id":      CONTROLLED_APPLY_ID,
        "source":                   SOURCE,
        "provenance_hash":          prov_hash,
        "provenance_source":        "p47_wave4_powerlotto_adapters.py",
        "dry_run":                  0,               # PRODUCTION ROW
        "prediction_cutoff_date":   raw.get("prediction_cutoff_date"),
        "prediction_generated_at":  raw.get("prediction_generated_at", now_str),
    }


# ─── POWER_LOTTO semantics validation ────────────────────────────────────────

def _validate_powerlotto_semantics(prod_rows: List[dict]) -> dict:
    """
    Validate POWER_LOTTO two-zone semantics for all production rows.
    Checks:
      - lottery_type = POWER_LOTTO
      - predicted_numbers: 6 unique ints in [1, 38]
      - actual_numbers: 6 unique ints in [1, 38]
      - predicted_special: 1 int in [1, 8]
      - actual_special: 1 int in [1, 8] (non-null, per Policy A)
      - hit_count: first-zone only (== len(intersection of predicted ∩ actual))
      - special_hit: 0 or 1, based on predicted_special == actual_special
    """
    errors = []
    for i, row in enumerate(prod_rows):
        sid = row.get("strategy_id", "?")

        if row.get("lottery_type") != "POWER_LOTTO":
            errors.append(f"Row {i} ({sid}): lottery_type={row.get('lottery_type')} expected POWER_LOTTO")

        if row.get("replay_status") == "PREDICTED":
            # Parse predicted numbers
            pred_raw = row.get("predicted_numbers")
            pred = json.loads(pred_raw) if isinstance(pred_raw, str) else pred_raw
            if pred is not None:
                if len(pred) != 6:
                    errors.append(f"Row {i} ({sid}): predicted_numbers len={len(pred)} expected 6")
                elif len(set(pred)) != 6:
                    errors.append(f"Row {i} ({sid}): duplicate predicted_numbers {pred}")
                elif not all(1 <= n <= 38 for n in pred):
                    errors.append(f"Row {i} ({sid}): predicted_numbers out of [1,38]: {pred}")

                # Parse actual numbers
                actual_raw = row.get("actual_numbers")
                actual = json.loads(actual_raw) if isinstance(actual_raw, str) else actual_raw
                if actual is not None:
                    # Verify hit_count = first-zone intersection
                    hits = set(pred) & set(actual)
                    expected_hit_count = len(hits)
                    if row.get("hit_count") != expected_hit_count:
                        errors.append(
                            f"Row {i} ({sid}): hit_count={row.get('hit_count')} "
                            f"expected {expected_hit_count} (first-zone only)"
                        )

                # predicted_special in [1, 8]
                pred_sp = row.get("predicted_special")
                if pred_sp is not None and not (1 <= int(pred_sp) <= 8):
                    errors.append(f"Row {i} ({sid}): predicted_special={pred_sp} not in [1,8]")

                # actual_special non-null (Policy A guarantees this)
                actual_sp = row.get("actual_special")
                if actual_sp is None:
                    errors.append(f"Row {i} ({sid}): actual_special is NULL (Policy A should have skipped)")
                elif not (1 <= int(actual_sp) <= 8):
                    errors.append(f"Row {i} ({sid}): actual_special={actual_sp} not in [1,8]")

                # special_hit = 0 or 1
                sh = row.get("special_hit")
                if sh not in (0, 1):
                    errors.append(f"Row {i} ({sid}): special_hit={sh} must be 0 or 1")
                elif pred_sp is not None and actual_sp is not None:
                    expected_sh = 1 if int(pred_sp) == int(actual_sp) else 0
                    if sh != expected_sh:
                        errors.append(
                            f"Row {i} ({sid}): special_hit={sh} expected {expected_sh} "
                            f"(pred_sp={pred_sp}, actual_sp={actual_sp})"
                        )

        # dry_run must be 0 (production)
        if row.get("dry_run") != 0:
            errors.append(f"Row {i} ({sid}): dry_run={row.get('dry_run')} expected 0 (production row)")

        # truth_level must be POWERLOTTO_WAVE4_STRATEGY_BACKFILL_VERIFIED
        if row.get("truth_level") != TRUTH_LEVEL:
            errors.append(f"Row {i} ({sid}): truth_level={row.get('truth_level')} expected {TRUTH_LEVEL}")

    return {
        "total_rows_checked": len(prod_rows),
        "errors": errors[:20],
        "error_count": len(errors),
        "semantics_valid": len(errors) == 0,
    }


# ─── Production DB apply ──────────────────────────────────────────────────────

def _apply_to_production(rows: List[dict]) -> Tuple[int, int]:
    """
    INSERT rows into production DB inside a single atomic transaction.
    Returns (inserted, duplicate_count).
    Rolls back automatically on any exception.
    """
    inserted   = 0
    duplicates = 0

    conn = sqlite3.connect(str(PROD_DB_PATH))
    try:
        conn.execute("BEGIN EXCLUSIVE")
        for row in rows:
            try:
                conn.execute(
                    """
                    INSERT INTO strategy_prediction_replays (
                        lottery_type, target_draw, target_date, strategy_id,
                        strategy_name, strategy_version, history_cutoff_draw,
                        replay_status, reject_reason, predicted_numbers,
                        predicted_special, actual_numbers, actual_special,
                        hit_numbers, hit_count, special_hit, replay_run_id,
                        generated_at, truth_level, controlled_apply_id, source,
                        provenance_hash, provenance_source, dry_run,
                        prediction_cutoff_date, prediction_generated_at
                    ) VALUES (
                        :lottery_type, :target_draw, :target_date, :strategy_id,
                        :strategy_name, :strategy_version, :history_cutoff_draw,
                        :replay_status, :reject_reason, :predicted_numbers,
                        :predicted_special, :actual_numbers, :actual_special,
                        :hit_numbers, :hit_count, :special_hit, :replay_run_id,
                        :generated_at, :truth_level, :controlled_apply_id, :source,
                        :provenance_hash, :provenance_source, :dry_run,
                        :prediction_cutoff_date, :prediction_generated_at
                    )
                    """,
                    row,
                )
                inserted += 1
            except sqlite3.IntegrityError:
                duplicates += 1
        conn.commit()
        logger.info(
            "Production apply committed: inserted=%d, duplicates=%d",
            inserted, duplicates,
        )
    except Exception:
        conn.rollback()
        conn.close()
        raise
    conn.close()
    return inserted, duplicates


# ─── Hit rate stats ───────────────────────────────────────────────────────────

def _compute_hit_stats(rows: List[dict]) -> dict:
    """Compute per-strategy hit rate statistics for production rows."""
    by_strategy: dict = defaultdict(lambda: defaultdict(int))

    for row in rows:
        sid = row["strategy_id"]
        if row["replay_status"] == "PREDICTED":
            by_strategy[sid]["predicted"] += 1
            hc = row.get("hit_count", 0) or 0
            by_strategy[sid][f"hit_{hc}"] += 1
            by_strategy[sid]["special_hit"] += int(row.get("special_hit", 0) or 0)
        else:
            by_strategy[sid]["error"] += 1

    stats = {}
    for sid in WAVE4_STRATEGY_IDS:
        counts = by_strategy.get(sid, {})
        predicted = counts.get("predicted", 0)
        errors    = counts.get("error", 0)
        hit_3plus = sum(counts.get(f"hit_{h}", 0) for h in (3, 4, 5, 6))
        special_hits = counts.get("special_hit", 0)
        stats[sid] = {
            "predicted":         predicted,
            "errors":            errors,
            "total":             predicted + errors,
            "hit_3plus":         hit_3plus,
            "hit_3plus_rate":    round(hit_3plus / predicted, 4) if predicted > 0 else 0.0,
            "special_hits":      special_hits,
            "special_hit_rate":  round(special_hits / predicted, 4) if predicted > 0 else 0.0,
            "hit_breakdown":     {str(h): counts.get(f"hit_{h}", 0) for h in range(7)},
        }
    return stats


# ─── Post-apply production verification ──────────────────────────────────────

def _post_apply_verify(expected_total: int) -> dict:
    """Verify production DB after apply: row count, per-strategy counts, truth_level."""
    conn = sqlite3.connect(str(PROD_DB_PATH))
    try:
        total = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays"
        ).fetchone()[0]

        per_strategy = {}
        for sid in WAVE4_STRATEGY_IDS:
            n = conn.execute(
                "SELECT COUNT(*) FROM strategy_prediction_replays "
                "WHERE lottery_type='POWER_LOTTO' AND strategy_id=? AND truth_level=?",
                (sid, TRUTH_LEVEL),
            ).fetchone()[0]
            per_strategy[sid] = n

        powerlotto_total = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE lottery_type='POWER_LOTTO'"
        ).fetchone()[0]

        wave4_total = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE controlled_apply_id=?",
            (CONTROLLED_APPLY_ID,),
        ).fetchone()[0]

    finally:
        conn.close()

    return {
        "total_rows": total,
        "expected_total": expected_total,
        "row_count_ok": total == expected_total,
        "powerlotto_total": powerlotto_total,
        "wave4_applied_total": wave4_total,
        "per_strategy_after": per_strategy,
    }


# ─── Main orchestrator ────────────────────────────────────────────────────────

def main(argv: Optional[List[str]] = None) -> dict:
    parser = argparse.ArgumentParser(
        description="P48 Wave 4 POWER_LOTTO Production Apply"
    )
    parser.add_argument(
        "--json-out",
        default=str(OUTPUT_DIR / "p48_powerlotto_wave4_production_apply_20260524.json"),
        help="Output JSON path",
    )
    parser.add_argument(
        "--dry-run-check",
        action="store_true",
        help="Run pre-flight and duplicate check only; do NOT write to DB",
    )
    args = parser.parse_args(argv)

    started_at = datetime.now(timezone.utc).isoformat()
    logger.info("=== P48 Wave 4 POWER_LOTTO Production Apply ===")
    logger.info("Started: %s", started_at)
    logger.info("Controlled apply ID: %s", CONTROLLED_APPLY_ID)
    logger.info("Authorization: YES apply P48 production wave4 powerlotto")
    logger.info("Special NULL policy: Policy A (skip rows where actual_special is NULL)")

    # ── Pre-flight: assert production rows == 37960 ───────────────────────────
    logger.info("Pre-flight: checking production DB row count...")
    prod_rows_before = _check_prod_rows(PRE_APPLY_PROD_ROWS)
    logger.info("Production DB before: %d rows (PASS)", prod_rows_before)

    # ── Pre-apply duplicate check ─────────────────────────────────────────────
    logger.info("Pre-apply duplicate check...")
    dup_check = _duplicate_check()
    logger.info(
        "Duplicate check: existing_p48=%d, p47_dryrun_in_prod=%d, pass=%s",
        dup_check["existing_p48_rows"],
        dup_check["p47_dryrun_in_production"],
        dup_check["duplicate_check_pass"],
    )
    if not dup_check["duplicate_check_pass"]:
        raise RuntimeError(
            f"P48_BLOCKED_BY_DUPLICATES: found {dup_check['existing_p48_rows']} "
            f"existing P48 rows in production DB. Aborting."
        )

    # ── Load POWER_LOTTO draws (read-only) ────────────────────────────────────
    logger.info("Loading POWER_LOTTO draws...")
    all_draws = _load_powerlotto_draws()
    total_draws = len(all_draws)
    logger.info("Loaded %d POWER_LOTTO draws", total_draws)

    # ── Import Wave 4 adapters ────────────────────────────────────────────────
    from lottery_api.models.p47_wave4_powerlotto_adapters import generate_dryrun_rows
    logger.info("Wave 4 adapters loaded (lifecycle=DRY_RUN, NOT ONLINE)")

    # ── Generate rows ─────────────────────────────────────────────────────────
    logger.info("Generating %d rows (%d strategies × %d draws)...",
                EXPECTED_APPLIED_ROWS, STRATEGIES_COUNT, WINDOW_PERIODS)
    now_str = datetime.now(timezone.utc).isoformat()
    raw_rows = generate_dryrun_rows(all_draws, rows_per_strategy=WINDOW_PERIODS)
    logger.info("Generated %d raw rows", len(raw_rows))

    if len(raw_rows) != EXPECTED_APPLIED_ROWS:
        raise RuntimeError(
            f"Row count mismatch: generated {len(raw_rows)}, expected {EXPECTED_APPLIED_ROWS}"
        )

    # ── Apply Policy A: filter actual_special is NULL rows ───────────────────
    prod_rows = []
    skip_count = 0
    for raw in raw_rows:
        built = _build_production_row(raw, now_str)
        if built is None:
            skip_count += 1
        else:
            prod_rows.append(built)

    actual_target = PRE_APPLY_PROD_ROWS + len(prod_rows)
    logger.info(
        "Policy A: raw_rows=%d, skipped(actual_special=NULL)=%d, to_insert=%d",
        len(raw_rows), skip_count, len(prod_rows),
    )
    logger.info("Target post-apply row count: %d", actual_target)

    # Per-strategy counts
    per_strategy_to_insert: dict = defaultdict(int)
    for r in prod_rows:
        per_strategy_to_insert[r["strategy_id"]] += 1
    for sid in WAVE4_STRATEGY_IDS:
        logger.info("  %s: %d rows to insert", sid, per_strategy_to_insert.get(sid, 0))

    # ── Dry-run check only — stop here if requested ───────────────────────────
    if args.dry_run_check:
        logger.info("--dry-run-check mode: stopping before DB write")
        result = {
            "mode": "dry_run_check",
            "prod_rows_before": prod_rows_before,
            "duplicate_check": dup_check,
            "total_draws": total_draws,
            "raw_rows_generated": len(raw_rows),
            "skip_count": skip_count,
            "to_insert": len(prod_rows),
            "per_strategy_to_insert": dict(per_strategy_to_insert),
            "started_at": started_at,
        }
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        Path(args.json_out).write_text(json.dumps(result, indent=2, ensure_ascii=False))
        return result

    # ── Validate POWER_LOTTO semantics before DB write ────────────────────────
    logger.info("Validating POWER_LOTTO two-zone semantics...")
    semantics = _validate_powerlotto_semantics(prod_rows)
    logger.info(
        "Semantics validation: valid=%s, errors=%d",
        semantics["semantics_valid"], semantics["error_count"],
    )
    if not semantics["semantics_valid"]:
        for err in semantics["errors"][:10]:
            logger.error("  %s", err)
        raise RuntimeError(
            f"P48_BLOCKED_BY_POWERLOTTO_SEMANTICS: {semantics['error_count']} errors. Aborting."
        )

    # ── Apply to production DB ────────────────────────────────────────────────
    logger.info(
        "Applying %d rows to production DB (authorized by: YES apply P48 production wave4 powerlotto)...",
        len(prod_rows),
    )
    inserted, duplicates = _apply_to_production(prod_rows)
    logger.info("Applied: inserted=%d, duplicates=%d", inserted, duplicates)

    if inserted != len(prod_rows):
        raise RuntimeError(
            f"P48_BLOCKED_BY_ROW_COUNT_MISMATCH: inserted {inserted} but expected {len(prod_rows)}. "
            f"Duplicates: {duplicates}."
        )

    # ── Post-apply verification ───────────────────────────────────────────────
    logger.info("Post-apply verification...")
    post_verify = _post_apply_verify(actual_target)
    logger.info(
        "Post-apply rows: %d (expected %d, ok=%s)",
        post_verify["total_rows"], actual_target, post_verify["row_count_ok"],
    )
    if not post_verify["row_count_ok"]:
        raise RuntimeError(
            f"P48_BLOCKED_BY_ROW_COUNT_MISMATCH: post-apply rows={post_verify['total_rows']}, "
            f"expected={actual_target}."
        )

    # ── Hit stats ─────────────────────────────────────────────────────────────
    hit_stats = _compute_hit_stats(prod_rows)

    # ── Coverage denominator ──────────────────────────────────────────────────
    strategy_universe_denominator = 59
    n_groups_before = 25
    n_groups_after  = 28
    coverage_before = round(n_groups_before / strategy_universe_denominator, 4)
    coverage_after  = round(n_groups_after  / strategy_universe_denominator, 4)
    remaining_strategies = strategy_universe_denominator - n_groups_after
    approx_rows_to_target = remaining_strategies * 1500

    coverage_block = {
        "production_rows_before":          prod_rows_before,
        "production_rows_after":           post_verify["total_rows"],
        "inserted_count":                  inserted,
        "skip_count_policy_a":             skip_count,
        "n_strategy_groups_with_rows_before": n_groups_before,
        "n_strategy_groups_with_rows_after":  n_groups_after,
        "strategy_universe_denominator":   strategy_universe_denominator,
        "coverage_ratio_before":           coverage_before,
        "coverage_ratio_after":            coverage_after,
        "remaining_strategies":            remaining_strategies,
        "approx_rows_to_full_coverage":    approx_rows_to_target,
        "gap_to_target": (
            f"{remaining_strategies} strategies remaining; "
            f"~{approx_rows_to_target:,} rows needed to reach 1500×all_executable_strategies."
        ),
    }
    logger.info("Coverage: %d/%d → %d/%d (denominator=%d)",
                n_groups_before, strategy_universe_denominator,
                n_groups_after,  strategy_universe_denominator,
                strategy_universe_denominator)
    logger.info("Gap to CEO target: %s", coverage_block["gap_to_target"])

    finished_at = datetime.now(timezone.utc).isoformat()

    # ── Build manifest ────────────────────────────────────────────────────────
    manifest = {
        "phase":                   "P48_WAVE4_POWERLOTTO_PRODUCTION_APPLY",
        "task_id":                 "P48",
        "controlled_apply_id":     CONTROLLED_APPLY_ID,
        "run_id":                  RUN_ID,
        "truth_level":             TRUTH_LEVEL,
        "authorization_phrases": [
            "YES create new branch for P48 powerlotto wave4 production apply",
            "YES apply P48 production wave4 powerlotto",
        ],
        "started_at":             started_at,
        "finished_at":            finished_at,
        "branch":                 "p48-powerlotto-wave4-production-apply",
        "lottery_type":           "POWER_LOTTO",
        "strategies":             WAVE4_STRATEGY_IDS,
        "window_periods":         WINDOW_PERIODS,
        "total_draws_loaded":     total_draws,
        "raw_rows_generated":     len(raw_rows),
        "special_null_policy":    f"Policy {SPECIAL_NULL_POLICY}: skip rows where actual_special is NULL",
        "skip_count":             skip_count,
        "rows_to_insert":         len(prod_rows),
        "inserted":               inserted,
        "duplicates_in_apply":    duplicates,
        "prod_rows_before":       prod_rows_before,
        "prod_rows_after":        post_verify["total_rows"],
        "row_count_ok":           post_verify["row_count_ok"],
        "per_strategy_inserted":  dict(per_strategy_to_insert),
        "per_strategy_after":     post_verify["per_strategy_after"],
        "duplicate_check":        dup_check,
        "semantics_validation":   semantics,
        "hit_stats":              hit_stats,
        "coverage":               coverage_block,
        "lifecycle_confirmation": {
            "all_strategies_lifecycle": "DRY_RUN",
            "online_promotions":        0,
            "registry_mutations":       0,
            "note": "Lifecycle remains DRY_RUN. No ONLINE promotion. P50 territory.",
        },
        "powerlotto_semantics": {
            "first_zone":     "6 unique ints in [1, 38]",
            "special_zone":   "1 int in [1, 8] (non-null enforced by Policy A)",
            "hit_count":      "first-zone intersection only (NEVER includes special)",
            "special_hit":    "1 if predicted_special == actual_special, else 0",
            "dry_run_flag":   "0 (production row)",
        },
        "wave5_readiness_sketch": _wave5_sketch(),
        "classification":         "P48_POWERLOTTO_WAVE4_PRODUCTION_APPLY_READY",
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = Path(args.json_out)
    out_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    logger.info("Manifest written: %s", out_path)
    logger.info("=== P48 COMPLETE: inserted=%d, prod_rows=%d ===",
                inserted, post_verify["total_rows"])

    return manifest


def _wave5_sketch() -> List[dict]:
    """Wave 5 readiness sketch: 5-10 candidate strategies for the next wave."""
    return [
        {
            "strategy_id": "hot_window_powerlotto_2bet",
            "lottery_type": "POWER_LOTTO",
            "effort": "LOW",
            "expected_rows": 1500,
            "rationale": "Sliding hot-window (last 30 draws) for POWER_LOTTO; simple, complementary to MidFreq strategies.",
        },
        {
            "strategy_id": "gap_profile_powerlotto_3bet",
            "lottery_type": "POWER_LOTTO",
            "effort": "LOW",
            "expected_rows": 1500,
            "rationale": "Overdue-number gap profiling; proven for DAILY_539 Wave 2, direct POWER_LOTTO port.",
        },
        {
            "strategy_id": "combo_markov_fourier_powerlotto_2bet",
            "lottery_type": "POWER_LOTTO",
            "effort": "MED",
            "expected_rows": 1500,
            "rationale": "Markov+Fourier ensemble (variant without PP3); diversifies from Wave 4 strategies.",
        },
        {
            "strategy_id": "zone_segmented_biglotto_3bet",
            "lottery_type": "BIG_LOTTO",
            "effort": "MED",
            "expected_rows": 1500,
            "rationale": "Zone-segmented pool (low/mid/high thirds) for BIG_LOTTO; from P30 manual_review list.",
        },
        {
            "strategy_id": "harmonic_cycle_daily539_2bet",
            "lottery_type": "DAILY_539",
            "effort": "LOW",
            "expected_rows": 1500,
            "rationale": "Harmonic cycle detection for DAILY_539; complements Wave 2 frequency strategies.",
        },
        {
            "strategy_id": "cold_bridge_powerlotto_2bet",
            "lottery_type": "POWER_LOTTO",
            "effort": "LOW",
            "expected_rows": 1500,
            "rationale": "Cold-number bridge strategy; analogous to P22 cold_bridge concept but for POWER_LOTTO.",
        },
        {
            "strategy_id": "bayesian_fusion_powerlotto_3bet",
            "lottery_type": "POWER_LOTTO",
            "effort": "HIGH",
            "expected_rows": 1500,
            "rationale": "Bayesian score fusion (P21 variant); highest-effort but strongest theoretical foundation.",
        },
    ]


if __name__ == "__main__":
    result = main()
    print(json.dumps({
        "classification":   result.get("classification"),
        "inserted":         result.get("inserted"),
        "prod_rows_before": result.get("prod_rows_before"),
        "prod_rows_after":  result.get("prod_rows_after"),
        "skip_count":       result.get("skip_count"),
        "semantics_valid":  result.get("semantics_validation", {}).get("semantics_valid"),
        "duplicate_check_pass": result.get("duplicate_check", {}).get("duplicate_check_pass"),
    }, indent=2))
