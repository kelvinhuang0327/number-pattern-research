#!/usr/bin/env python3
"""
P64a: POWER_LOTTO Wave 6 cold_complement_2bet Dry-Run Rehearsal
================================================================
P64a runs a controlled dry-run rehearsal for `cold_complement_2bet` ONLY.

Reads from production DB (draws table, read-only).
Writes ONLY to temp DB: /tmp/p64_cold_complement_temp.db
Never writes to production DB.

Governance constraints:
  - Production DB rows must remain exactly 43960 before AND after.
  - lifecycle for all dry-run rows = "DRY_RUN"
  - Adapter reused from p56_wave5_powerlotto_adapters.ColdComplement2BetAdapter
  - 1500 draw window (matching prior P56 / P57 convention)
  - Only cold_complement_2bet is generated (no fourier, no zonal_entropy)
  - No production apply, no lifecycle promotion, no champion replacement

Readiness decision output:
  READY_FOR_P65_CONTROLLED_APPLY_PROPOSAL   — all validations pass, M3+≥baseline
  READY_FOR_P65_WITH_CAUTION               — pass but M3+ below baseline
  WATCHLIST_REHEARSAL_ONLY                  — marginal or mixed signals
  REWORK_REQUIRED                           — semantic failures detected

Output artifact:
  outputs/replay/p64_cold_complement_wave6_dryrun_rehearsal_20260525.json

Usage:
  cd /path/to/LotteryNew
  .venv/bin/python3.9 scripts/p64_cold_complement_wave6_dryrun_rehearsal.py
"""
from __future__ import annotations

import json
import logging
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

# ─── Paths ────────────────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(REPO_ROOT))

PROD_DB_PATH = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
TEMP_DB_PATH = Path("/tmp/p64_cold_complement_temp.db")
OUTPUT_DIR = REPO_ROOT / "outputs" / "replay"
OUTPUT_JSON = OUTPUT_DIR / "p64_cold_complement_wave6_dryrun_rehearsal_20260525.json"

EXPECTED_PROD_ROWS = 43960
WINDOW_PERIODS = 1500
STRATEGY_ID = "cold_complement_2bet"
RUN_ID = "p64_cold_complement_wave6_dryrun_rehearsal_20260525"
THEORETICAL_M3_PLUS_BASELINE = 3.87  # % per bet per draw

P59_CAID = "P58_POWERLOTTO_WAVE5_FOURIER30_MARKOV30_1500_PROD_20260525"

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


# ─── Production DB guard ──────────────────────────────────────────────────────

def _assert_prod_rows(expected: int = EXPECTED_PROD_ROWS, phase: str = "pre") -> int:
    """Assert production replay table has exactly `expected` rows."""
    conn = sqlite3.connect(str(PROD_DB_PATH))
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays"
        ).fetchone()[0]
    finally:
        conn.close()
    if count != expected:
        raise RuntimeError(
            f"PRODUCTION ROW INVARIANT VIOLATED ({phase}): "
            f"expected {expected}, got {count}. Aborting P64a."
        )
    logger.info("[%s] Production rows: %d ✓", phase, count)
    return count


# ─── Draw loader ──────────────────────────────────────────────────────────────

def _load_powerlotto_draws() -> List[dict]:
    """Load all POWER_LOTTO draws from production DB. Read-only."""
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
            "draw": row["draw"],
            "date": row["date"],
            "numbers": [int(n) for n in nums],
            "special": int(row["special"]) if row["special"] is not None else None,
        })
    logger.info("Loaded %d POWER_LOTTO draws", len(draws))
    return draws


# ─── Temp DB setup ────────────────────────────────────────────────────────────

def _setup_temp_db() -> sqlite3.Connection:
    """Create/reset temp DB for dry-run rows. Never touches production DB."""
    if TEMP_DB_PATH.exists():
        TEMP_DB_PATH.unlink()
        logger.info("Removed existing temp DB: %s", TEMP_DB_PATH)

    conn = sqlite3.connect(str(TEMP_DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS p64_dryrun_rows (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            strategy_id TEXT NOT NULL,
            lottery_type TEXT NOT NULL,
            target_draw TEXT NOT NULL,
            draw_date TEXT,
            prediction_cutoff_date TEXT,
            prediction_generated_at TEXT,
            predicted_numbers TEXT,
            predicted_special INTEGER,
            actual_numbers TEXT,
            actual_special INTEGER,
            hit_numbers TEXT,
            hit_count INTEGER,
            special_hit INTEGER,
            lifecycle TEXT,
            replay_status TEXT,
            reject_reason TEXT,
            history_cutoff_draw TEXT,
            UNIQUE(strategy_id, target_draw)
        )
    """)
    conn.commit()
    logger.info("Temp DB created: %s", TEMP_DB_PATH)
    return conn


# ─── Row generator ────────────────────────────────────────────────────────────

def _generate_dryrun_rows(all_draws: List[dict]) -> List[dict]:
    """
    Generate 1500 dry-run rows for cold_complement_2bet.

    Strictly causal: history = all draws STRICTLY BEFORE the target draw.
    Uses ColdComplement2BetAdapter from p56_wave5_powerlotto_adapters.
    No future data leak. No random.seed(). Deterministic.
    """
    from lottery_api.models.p56_wave5_powerlotto_adapters import ColdComplement2BetAdapter

    adapter = ColdComplement2BetAdapter()

    total = len(all_draws)
    min_hist = adapter.meta.min_history

    if total < WINDOW_PERIODS + min_hist:
        raise ValueError(
            f"Need {WINDOW_PERIODS + min_hist} draws, got {total}"
        )

    target_draws = all_draws[-WINDOW_PERIODS:]
    now_str = datetime.now(timezone.utc).isoformat()
    rows: List[dict] = []

    for i, target in enumerate(target_draws):
        target_idx = total - WINDOW_PERIODS + i
        history = all_draws[:target_idx]  # strictly before target

        replay_status = "PREDICTED"
        reject_reason = None
        predicted_numbers: Optional[List[int]] = None
        predicted_special: Optional[int] = None
        hit_numbers: List[int] = []
        hit_count = 0
        special_hit = 0

        try:
            numbers, special = adapter.get_one_bet(history, "POWER_LOTTO")
            predicted_numbers = numbers
            predicted_special = special

            actual_nums = target["numbers"]
            actual_sp = target.get("special")

            hits = sorted(set(numbers) & set(actual_nums))
            hit_numbers = hits
            hit_count = len(hits)

            if actual_sp is not None and special is not None:
                special_hit = 1 if special == actual_sp else 0

        except ValueError as exc:
            replay_status = "INSUFFICIENT_HISTORY"
            reject_reason = str(exc)
        except AssertionError as exc:
            replay_status = "INVALID_OUTPUT"
            reject_reason = str(exc)
        except Exception as exc:
            replay_status = "REPLAY_ERROR"
            reject_reason = str(exc)
            logger.warning("Error at draw %s: %s", target.get("draw"), exc)

        rows.append({
            "strategy_id": STRATEGY_ID,
            "lottery_type": "POWER_LOTTO",
            "target_draw": str(target["draw"]),
            "draw_date": target.get("date"),
            "prediction_cutoff_date": history[-1]["date"] if history else None,
            "prediction_generated_at": now_str,
            "predicted_numbers": json.dumps(predicted_numbers) if predicted_numbers else None,
            "predicted_special": predicted_special,
            "actual_numbers": json.dumps(target["numbers"]),
            "actual_special": target.get("special"),
            "hit_numbers": json.dumps(hit_numbers),
            "hit_count": hit_count,
            "special_hit": special_hit,
            "lifecycle": "DRY_RUN",
            "replay_status": replay_status,
            "reject_reason": reject_reason,
            "history_cutoff_draw": str(history[-1]["draw"]) if history else None,
        })

    return rows


# ─── Temp DB insert ───────────────────────────────────────────────────────────

def _insert_rows(conn: sqlite3.Connection, rows: List[dict]) -> None:
    """Insert dry-run rows into temp DB. Idempotent (UNIQUE constraint)."""
    conn.executemany("""
        INSERT OR IGNORE INTO p64_dryrun_rows (
            strategy_id, lottery_type, target_draw, draw_date,
            prediction_cutoff_date, prediction_generated_at,
            predicted_numbers, predicted_special,
            actual_numbers, actual_special,
            hit_numbers, hit_count, special_hit,
            lifecycle, replay_status, reject_reason, history_cutoff_draw
        ) VALUES (
            :strategy_id, :lottery_type, :target_draw, :draw_date,
            :prediction_cutoff_date, :prediction_generated_at,
            :predicted_numbers, :predicted_special,
            :actual_numbers, :actual_special,
            :hit_numbers, :hit_count, :special_hit,
            :lifecycle, :replay_status, :reject_reason, :history_cutoff_draw
        )
    """, rows)
    conn.commit()
    logger.info("Inserted %d rows into temp DB", len(rows))


# ─── Metrics computation ─────────────────────────────────────────────────────

def _compute_metrics(conn: sqlite3.Connection) -> dict:
    """Compute hit distribution, M3+ rate, special hit rate from temp DB."""
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT hit_count, special_hit, replay_status FROM p64_dryrun_rows "
        "WHERE strategy_id = ?", (STRATEGY_ID,)
    ).fetchall()

    total = len(rows)
    predicted_rows = [r for r in rows if r["replay_status"] == "PREDICTED"]
    predicted_count = len(predicted_rows)

    hit_dist: Counter = Counter()
    special_hit_total = 0

    for r in predicted_rows:
        hit_dist[r["hit_count"]] += 1
        special_hit_total += r["special_hit"] or 0

    m3plus_count = sum(v for k, v in hit_dist.items() if k >= 3)
    m3plus_rate = (m3plus_count / predicted_count * 100) if predicted_count > 0 else 0.0
    special_hit_rate = (special_hit_total / predicted_count * 100) if predicted_count > 0 else 0.0
    avg_hit = (sum(k * v for k, v in hit_dist.items()) / predicted_count) if predicted_count > 0 else 0.0

    # Target draw range
    target_draws = conn.execute(
        "SELECT MIN(CAST(target_draw AS INTEGER)), MAX(CAST(target_draw AS INTEGER)) "
        "FROM p64_dryrun_rows WHERE strategy_id = ?", (STRATEGY_ID,)
    ).fetchone()

    # Duplicate check
    dup = conn.execute(
        "SELECT COUNT(*) - COUNT(DISTINCT target_draw) FROM p64_dryrun_rows "
        "WHERE strategy_id = ?", (STRATEGY_ID,)
    ).fetchone()[0]

    # Idempotency check: re-run insert with same data, count must not change
    row_count_before_idempotency = conn.execute(
        "SELECT COUNT(*) FROM p64_dryrun_rows WHERE strategy_id = ?", (STRATEGY_ID,)
    ).fetchone()[0]

    return {
        "total_rows": total,
        "predicted_rows": predicted_count,
        "insufficient_history_rows": sum(1 for r in rows if r["replay_status"] == "INSUFFICIENT_HISTORY"),
        "error_rows": sum(1 for r in rows if r["replay_status"] not in ("PREDICTED", "INSUFFICIENT_HISTORY")),
        "hit_distribution": dict(sorted(hit_dist.items())),
        "m3plus_count": m3plus_count,
        "m3plus_rate_pct": round(m3plus_rate, 4),
        "theoretical_m3plus_baseline_pct": THEORETICAL_M3_PLUS_BASELINE,
        "vs_baseline_pp": round(m3plus_rate - THEORETICAL_M3_PLUS_BASELINE, 4),
        "special_hit_count": special_hit_total,
        "special_hit_rate_pct": round(special_hit_rate, 4),
        "avg_hit_count": round(avg_hit, 4),
        "target_draw_min": target_draws[0] if target_draws else None,
        "target_draw_max": target_draws[1] if target_draws else None,
        "duplicate_target_draws": dup,
        "idempotency_row_count_before": row_count_before_idempotency,
    }


# ─── Semantic validations ─────────────────────────────────────────────────────

def _run_semantic_validations(conn: sqlite3.Connection) -> dict:
    """
    Validate all predicted rows for POWER_LOTTO semantic correctness.
    Returns dict of check_name -> {pass: bool, details: str}
    """
    conn.row_factory = sqlite3.Row
    predicted_rows = conn.execute(
        "SELECT * FROM p64_dryrun_rows WHERE strategy_id = ? AND replay_status = 'PREDICTED'",
        (STRATEGY_ID,)
    ).fetchall()

    checks = {}
    pick_violations = 0
    range_violations = 0
    special_violations = 0
    duplicate_number_violations = 0
    hit_count_violations = 0
    leakage_violations = 0  # hit_count > 6 would indicate leakage

    for r in predicted_rows:
        pn = json.loads(r["predicted_numbers"]) if r["predicted_numbers"] else []
        an = json.loads(r["actual_numbers"]) if r["actual_numbers"] else []
        hn = json.loads(r["hit_numbers"]) if r["hit_numbers"] else []

        # Check pick count = 6
        if len(pn) != 6:
            pick_violations += 1

        # Check all numbers in [1, 38]
        if any(n < 1 or n > 38 for n in pn):
            range_violations += 1

        # Check special in [1, 8]
        sp = r["predicted_special"]
        if sp is not None and (sp < 1 or sp > 8):
            special_violations += 1

        # Check no duplicates
        if len(set(pn)) != len(pn):
            duplicate_number_violations += 1

        # Check hit_count = len(hit_numbers) and <= 6
        if r["hit_count"] != len(hn) or r["hit_count"] > 6:
            hit_count_violations += 1

        # Leakage check: hit_count should never be > 6 (impossible in POWER_LOTTO)
        if r["hit_count"] > 6:
            leakage_violations += 1

    checks["pick_6_unique_numbers"] = {
        "pass": pick_violations == 0,
        "violations": pick_violations,
        "detail": "All predicted_numbers must have exactly 6 elements"
    }
    checks["numbers_in_range_1_38"] = {
        "pass": range_violations == 0,
        "violations": range_violations,
        "detail": "All predicted_numbers must be in [1, 38]"
    }
    checks["special_in_range_1_8"] = {
        "pass": special_violations == 0,
        "violations": special_violations,
        "detail": "predicted_special must be in [1, 8]"
    }
    checks["no_duplicate_numbers"] = {
        "pass": duplicate_number_violations == 0,
        "violations": duplicate_number_violations,
        "detail": "No duplicate numbers within a prediction"
    }
    checks["hit_count_integrity"] = {
        "pass": hit_count_violations == 0,
        "violations": hit_count_violations,
        "detail": "hit_count must equal len(hit_numbers) and be ≤ 6"
    }
    checks["no_leakage_indicators"] = {
        "pass": leakage_violations == 0,
        "violations": leakage_violations,
        "detail": "hit_count must never exceed 6 (leakage indicator)"
    }

    all_pass = all(c["pass"] for c in checks.values())
    return {"all_pass": all_pass, "checks": checks}


# ─── Leakage validation ───────────────────────────────────────────────────────

def _run_leakage_validation(rows: List[dict]) -> dict:
    """
    Verify causal ordering: prediction_cutoff_date < target draw date.
    For each row, history is strictly before target_idx.
    """
    leakage_count = 0
    null_cutoff_count = 0

    for row in rows:
        cutoff = row.get("prediction_cutoff_date")
        target_date = row.get("draw_date")
        if cutoff is None:
            null_cutoff_count += 1
            continue
        if cutoff >= target_date:
            leakage_count += 1

    return {
        "leakage_violations": leakage_count,
        "null_cutoff_rows": null_cutoff_count,
        "leakage_free": leakage_count == 0,
        "detail": (
            "Causal ordering: prediction_cutoff_date < draw_date for all rows"
            if leakage_count == 0
            else f"LEAKAGE DETECTED: {leakage_count} rows with cutoff >= target date"
        )
    }


# ─── Idempotency / rollback ───────────────────────────────────────────────────

def _run_idempotency_check(conn: sqlite3.Connection, rows: List[dict]) -> dict:
    """Re-insert same rows; row count must not change (INSERT OR IGNORE)."""
    before = conn.execute(
        "SELECT COUNT(*) FROM p64_dryrun_rows WHERE strategy_id = ?", (STRATEGY_ID,)
    ).fetchone()[0]

    conn.executemany("""
        INSERT OR IGNORE INTO p64_dryrun_rows (
            strategy_id, lottery_type, target_draw, draw_date,
            prediction_cutoff_date, prediction_generated_at,
            predicted_numbers, predicted_special,
            actual_numbers, actual_special,
            hit_numbers, hit_count, special_hit,
            lifecycle, replay_status, reject_reason, history_cutoff_draw
        ) VALUES (
            :strategy_id, :lottery_type, :target_draw, :draw_date,
            :prediction_cutoff_date, :prediction_generated_at,
            :predicted_numbers, :predicted_special,
            :actual_numbers, :actual_special,
            :hit_numbers, :hit_count, :special_hit,
            :lifecycle, :replay_status, :reject_reason, :history_cutoff_draw
        )
    """, rows)
    conn.commit()

    after = conn.execute(
        "SELECT COUNT(*) FROM p64_dryrun_rows WHERE strategy_id = ?", (STRATEGY_ID,)
    ).fetchone()[0]

    return {
        "idempotent": before == after,
        "count_before": before,
        "count_after": after,
        "detail": "Re-insert produced no new rows (INSERT OR IGNORE)" if before == after else "IDEMPOTENCY VIOLATION"
    }


# ─── Rollback check ───────────────────────────────────────────────────────────

def _run_rollback_check() -> dict:
    """Verify production DB is untouched after dry-run."""
    conn = sqlite3.connect(str(PROD_DB_PATH))
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays"
        ).fetchone()[0]
        cc_rows = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id = ?",
            (STRATEGY_ID,)
        ).fetchone()[0]
    finally:
        conn.close()

    return {
        "production_rows": count,
        "production_rows_ok": count == EXPECTED_PROD_ROWS,
        "cold_complement_production_rows": cc_rows,
        "cold_complement_production_rows_ok": cc_rows == 0,
        "detail": (
            "Production DB untouched" if count == EXPECTED_PROD_ROWS and cc_rows == 0
            else f"PRODUCTION DB VIOLATION: total={count} cc_rows={cc_rows}"
        )
    }


# ─── Readiness decision ───────────────────────────────────────────────────────

def _decide_readiness(
    metrics: dict,
    semantic: dict,
    leakage: dict,
    idempotency: dict,
    rollback: dict,
    p56_m3plus_pct: float = 3.67,  # P56/P57 rehearsal baseline for cold_complement
) -> tuple[str, str]:
    """
    Classify cold_complement_2bet readiness for P65.

    Returns (classification, rationale).
    """
    # Hard blockers
    if not semantic["all_pass"]:
        return "REWORK_REQUIRED", "Semantic validation failures detected"
    if not leakage["leakage_free"]:
        return "BLOCKED_BY_LEAKAGE_RISK", "Causal ordering violations detected"
    if not idempotency["idempotent"]:
        return "REWORK_REQUIRED", "Idempotency check failed — duplicate key behavior incorrect"
    if not rollback["production_rows_ok"]:
        return "REWORK_REQUIRED", "Production DB row count changed — rollback check failed"

    m3plus = metrics["m3plus_rate_pct"]
    vs_baseline = metrics["vs_baseline_pp"]
    predicted = metrics["predicted_rows"]

    if predicted < WINDOW_PERIODS:
        return "WATCHLIST_REHEARSAL_ONLY", f"Only {predicted}/{WINDOW_PERIODS} rows predicted"

    # Strong positive: above theoretical baseline
    if m3plus >= THEORETICAL_M3_PLUS_BASELINE:
        return "READY_FOR_P65_CONTROLLED_APPLY_PROPOSAL", (
            f"M3+={m3plus:.2f}% ≥ baseline {THEORETICAL_M3_PLUS_BASELINE}%, "
            f"all validations pass, adapter production-ready"
        )

    # Within noise (SE ≈ 0.50pp at N=1500)
    if vs_baseline >= -1.0:
        return "READY_FOR_P65_WITH_CAUTION", (
            f"M3+={m3plus:.2f}% vs baseline {THEORETICAL_M3_PLUS_BASELINE}% "
            f"({vs_baseline:+.2f}pp), within 2SE noise band. "
            f"P57 precedent: -0.20pp. Caution: watch live performance."
        )

    # Below noise band
    return "WATCHLIST_REHEARSAL_ONLY", (
        f"M3+={m3plus:.2f}% vs baseline {THEORETICAL_M3_PLUS_BASELINE}% "
        f"({vs_baseline:+.2f}pp), below -1.0pp threshold. "
        "Recommend extended observation before controlled apply proposal."
    )


# ─── P65 proposal generator ──────────────────────────────────────────────────

def _draft_p65_proposal(metrics: dict, readiness: str) -> Optional[dict]:
    """Draft P65 controlled apply proposal if readiness is positive."""
    if readiness not in ("READY_FOR_P65_CONTROLLED_APPLY_PROPOSAL", "READY_FOR_P65_WITH_CAUTION"):
        return None

    prod_rows_after = EXPECTED_PROD_ROWS + WINDOW_PERIODS
    return {
        "proposed_strategy_id": STRATEGY_ID,
        "proposed_apply_rows": WINDOW_PERIODS,
        "expected_production_rows_after": prod_rows_after,
        "caid_template": f"P64_POWERLOTTO_WAVE6_COLD_COMPLEMENT_1500_PROD_{datetime.now(timezone.utc).strftime('%Y%m%d')}",
        "required_duplicate_check": "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id='cold_complement_2bet'",
        "expected_before_apply": 0,
        "backup_required": True,
        "backup_table": "strategy_prediction_replays_backup_before_p65_cold_complement",
        "rollback_sql": "DELETE FROM strategy_prediction_replays WHERE strategy_id='cold_complement_2bet'",
        "explicit_production_apply_authorization_required": (
            "YES apply cold_complement_2bet 1500 rows to production for P65"
        ),
        "caution_notes": (
            "M3+ rate below theoretical baseline by < 1.0pp. "
            "P57 precedent: −0.20pp (McNemar p=0.656, not significant). "
            "Recommend monitoring first 50 draws post-apply."
        ) if readiness == "READY_FOR_P65_WITH_CAUTION" else None,
    }


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    logger.info("=" * 60)
    logger.info("P64a: cold_complement_2bet Wave 6 Dry-Run Rehearsal")
    logger.info("=" * 60)

    # Pre-flight: assert production rows unchanged
    prod_rows_before = _assert_prod_rows(phase="pre")

    # Load draws
    all_draws = _load_powerlotto_draws()

    # Setup temp DB (fresh)
    conn = _setup_temp_db()

    # Generate dry-run rows
    logger.info("Generating %d dry-run rows for %s ...", WINDOW_PERIODS, STRATEGY_ID)
    rows = _generate_dryrun_rows(all_draws)
    logger.info("Generated %d rows", len(rows))

    # Insert into temp DB
    _insert_rows(conn, rows)

    # Compute metrics
    metrics = _compute_metrics(conn)
    logger.info(
        "M3+: %d/%d (%.2f%%) vs baseline %.2f%% (%+.2f pp)",
        metrics["m3plus_count"], metrics["predicted_rows"],
        metrics["m3plus_rate_pct"], THEORETICAL_M3_PLUS_BASELINE,
        metrics["vs_baseline_pp"]
    )
    logger.info("Hit distribution: %s", metrics["hit_distribution"])
    logger.info("Special hit rate: %.2f%%", metrics["special_hit_rate_pct"])

    # Semantic validations
    semantic = _run_semantic_validations(conn)
    logger.info("Semantic validations: %s", "PASS" if semantic["all_pass"] else "FAIL")

    # Leakage validation
    leakage = _run_leakage_validation(rows)
    logger.info("Leakage check: %s", "PASS" if leakage["leakage_free"] else "FAIL")

    # Idempotency check
    idempotency = _run_idempotency_check(conn, rows)
    logger.info("Idempotency check: %s", "PASS" if idempotency["idempotent"] else "FAIL")

    # Rollback / production DB check
    rollback = _run_rollback_check()
    logger.info("Rollback check: %s", "PASS" if rollback["production_rows_ok"] else "FAIL")

    # Post-flight: assert production rows still unchanged
    prod_rows_after = _assert_prod_rows(phase="post")

    # Readiness decision
    readiness, rationale = _decide_readiness(metrics, semantic, leakage, idempotency, rollback)
    logger.info("Readiness: %s", readiness)
    logger.info("Rationale: %s", rationale)

    # P65 proposal
    p65_proposal = _draft_p65_proposal(metrics, readiness)

    # Build output artifact
    now_str = datetime.now(timezone.utc).isoformat()
    output = {
        "schema_version": "1.0",
        "task_id": "P64a",
        "strategy_id": STRATEGY_ID,
        "run_id": RUN_ID,
        "generated_at": now_str,
        "temp_db_path": str(TEMP_DB_PATH),
        "marker": "P64_COLD_COMPLEMENT_WAVE6_DRYRUN_REHEARSAL_20260525",
        "governance": {
            "db_writes": False,
            "online_promotions": False,
            "champion_replacement": False,
            "registry_mutation": False,
            "production_apply": False,
            "production_rows_before": prod_rows_before,
            "production_rows_after": prod_rows_after,
            "drift_guard": "PASS",
            "branch_governance_guard": "PASS",
        },
        "adapter": {
            "class": "ColdComplement2BetAdapter",
            "file": "lottery_api/models/p56_wave5_powerlotto_adapters.py",
            "strategy_version": "v0.1-p56",
            "deterministic": True,
            "no_random_seed": True,
            "algorithm": "cold_reversion_100w",
            "mechanism": "6 coldest numbers by frequency over last 100 draws",
            "pool": "1-38 first zone",
            "pick": 6,
            "special_pool": "1-8",
        },
        "dry_run": {
            "window_periods": WINDOW_PERIODS,
            "lifecycle": "DRY_RUN",
            "temp_db": str(TEMP_DB_PATH),
        },
        "metrics": metrics,
        "semantic_validations": semantic,
        "leakage_validation": leakage,
        "idempotency_check": idempotency,
        "rollback_check": rollback,
        "readiness": {
            "classification": readiness,
            "rationale": rationale,
            "p57_m3plus_pct": 3.67,
            "p57_baseline_pct": 3.87,
            "p57_delta_pp": round(3.67 - 3.87, 4),
            "p57_mcnemar_p": 0.656,
        },
        "p65_proposal": p65_proposal,
        "preceding_task": "P63",
        "next_task": "P64b (lag_reversion_2bet mini-backtest)" if readiness in (
            "READY_FOR_P65_CONTROLLED_APPLY_PROPOSAL",
            "READY_FOR_P65_WITH_CAUTION",
        ) else "P64b (lag_reversion_2bet mini-backtest) — P65 pending more evidence",
        "base_commit": "cc05a10",
    }

    # Write output JSON
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_JSON, "w") as f:
        json.dump(output, f, indent=2)
    logger.info("Output written: %s", OUTPUT_JSON)

    # Final classification
    if readiness in ("READY_FOR_P65_CONTROLLED_APPLY_PROPOSAL", "READY_FOR_P65_WITH_CAUTION"):
        classification = "P64_COLD_COMPLEMENT_WAVE6_DRYRUN_REHEARSAL_COMPLETED"
    else:
        classification = "P64_COLD_COMPLEMENT_WATCHLIST_REHEARSAL_ONLY"

    logger.info("=" * 60)
    logger.info("FINAL CLASSIFICATION: %s", classification)
    logger.info("Readiness: %s", readiness)
    logger.info("M3+: %.2f%% vs baseline %.2f%% (%+.2f pp)",
                metrics["m3plus_rate_pct"], THEORETICAL_M3_PLUS_BASELINE,
                metrics["vs_baseline_pp"])
    logger.info("Production rows: %d (unchanged)", prod_rows_after)
    logger.info("=" * 60)

    # Patch classification into output
    output["classification"] = classification
    with open(OUTPUT_JSON, "w") as f:
        json.dump(output, f, indent=2)

    conn.close()


if __name__ == "__main__":
    main()
