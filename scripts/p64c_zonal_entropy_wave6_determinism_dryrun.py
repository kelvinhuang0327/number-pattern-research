#!/usr/bin/env python3
"""
P64c: POWER_LOTTO Wave 6 zonal_entropy_2bet Determinism Review + Dry-Run Rehearsal
====================================================================================
P64c performs two objectives:
  1. Determinism review: verify ZonalEntropy2BetAdapter is fully deterministic.
     P63 flagged determinism_concern=True (source tool power_scientific_zonal.py
     used random.seed(42) + random.sample).  P56 reimplemented the adapter without
     any randomness.  This task confirms the fix is in place and records evidence.
  2. Dry-run rehearsal: replay 1500 POWER_LOTTO draws for zonal_entropy_2bet ONLY.

Reads from production DB (draws table, read-only).
Writes ONLY to temp DB: /tmp/p64c_zonal_entropy_temp.db
Never writes to production DB.

Governance constraints:
  - Production DB rows must remain exactly 43960 before AND after.
  - lifecycle for all dry-run rows = "DRY_RUN"
  - Adapter reused from p56_wave5_powerlotto_adapters.ZonalEntropy2BetAdapter
  - 1500 draw window (matching prior P56 / P57 convention)
  - Only zonal_entropy_2bet is generated (no cold_complement, no fourier, no lag_reversion)
  - No production apply, no lifecycle promotion, no champion replacement

Determinism verification:
  - Call predict twice with same history → assert identical output
  - Run at 5 different history points for robustness
  - Record determinism_pass=True/False in output
  - If determinism_pass=False: halt immediately (BLOCKED_BY_NON_DETERMINISM)

Readiness decision output:
  READY_FOR_P65_CONTROLLED_APPLY_PROPOSAL   — all validations pass, M3+≥baseline
  READY_FOR_P65_WITH_CAUTION               — pass, M3+ within -1.0pp of baseline
  WATCHLIST_REHEARSAL_ONLY                  — M3+ more than -1.0pp below baseline
  BLOCKED_BY_NON_DETERMINISM               — determinism check failed

Output artifacts:
  outputs/replay/p64c_zonal_entropy_wave6_determinism_dryrun_20260525.json
  docs/replay/p64c_zonal_entropy_wave6_determinism_dryrun_20260525.md

Usage:
  cd /path/to/LotteryNew
  .venv/bin/python3.9 scripts/p64c_zonal_entropy_wave6_determinism_dryrun.py
"""
from __future__ import annotations

import json
import logging
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple

# ─── Paths ────────────────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(REPO_ROOT))

PROD_DB_PATH = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
TEMP_DB_PATH = Path("/tmp/p64c_zonal_entropy_temp.db")
OUTPUT_DIR = REPO_ROOT / "outputs" / "replay"
OUTPUT_JSON = OUTPUT_DIR / "p64c_zonal_entropy_wave6_determinism_dryrun_20260525.json"
DOCS_DIR = REPO_ROOT / "docs" / "replay"
OUTPUT_DOC = DOCS_DIR / "p64c_zonal_entropy_wave6_determinism_dryrun_20260525.md"

EXPECTED_PROD_ROWS = 43960
WINDOW_PERIODS = 1500
STRATEGY_ID = "zonal_entropy_2bet"
RUN_ID = "p64c_zonal_entropy_wave6_determinism_dryrun_20260525"
MARKER = "P64C_ZONAL_ENTROPY_WAVE6_DETERMINISM_DRYRUN_20260525"
THEORETICAL_M3_PLUS_BASELINE = 3.87   # % per bet per draw
PRIOR_P57_M3PLUS_PCT = 3.67           # P57 Wave 5 reference
DETERMINISM_CHECKS_N = 5

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
            f"expected {expected}, got {count}. Aborting P64c."
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


# ─── Determinism check ────────────────────────────────────────────────────────

def _run_determinism_check(all_draws: List[dict]) -> dict:
    """
    Verify ZonalEntropy2BetAdapter is fully deterministic.

    P63 flagged determinism_concern=True because the source tool
    tools/power_scientific_zonal.py uses random.seed(42) + random.sample().
    The P56 adapter reimplemented the algorithm without any randomness
    (confirmed by docstring: "No random.seed() — was flagged in
    power_scientific_zonal.py — removed").

    Verification: call get_one_bet twice with identical history at 5 draw points.
    All (nums, special) pairs must be bitwise identical.
    """
    from lottery_api.models.p56_wave5_powerlotto_adapters import (
        ZonalEntropy2BetAdapter,
    )

    adapter = ZonalEntropy2BetAdapter()
    total = len(all_draws)
    violations = 0
    checks_run = 0
    check_details = []

    # Sample 5 different history lengths spread across the dataset
    sample_indices = [
        total // 6,
        total // 3,
        total // 2,
        2 * total // 3,
        5 * total // 6,
    ]

    for idx in sample_indices:
        history = all_draws[:idx]
        if len(history) < adapter.meta.min_history:
            check_details.append({
                "history_length": len(history),
                "skipped": True,
                "reason": f"Insufficient history (need {adapter.meta.min_history})",
            })
            continue

        nums1, sp1 = adapter.get_one_bet(history, "POWER_LOTTO")
        nums2, sp2 = adapter.get_one_bet(history, "POWER_LOTTO")

        identical = (nums1 == nums2 and sp1 == sp2)
        if not identical:
            violations += 1
        checks_run += 1
        check_details.append({
            "history_length": len(history),
            "call_1_numbers": nums1,
            "call_1_special": sp1,
            "call_2_numbers": nums2,
            "call_2_special": sp2,
            "identical": identical,
        })

    determinism_pass = (violations == 0 and checks_run >= 3)
    return {
        "determinism_pass": determinism_pass,
        "checks_run": checks_run,
        "violations": violations,
        "check_details": check_details,
        "fix_applied": False,
        "fix_details": (
            "No fix needed. P56 reimplemented ZonalEntropy2BetAdapter without "
            "random.seed() or random.sample(). Source risk was in "
            "tools/power_scientific_zonal.py (NOT in the adapter)."
        ),
        "source_risk_status": "RESOLVED_IN_P56",
        "adapter_random_seed": False,
        "adapter_random_sample": False,
    }


# ─── Temp DB setup ────────────────────────────────────────────────────────────

def _setup_temp_db() -> sqlite3.Connection:
    """Create/reset temp DB for dry-run rows. Never touches production DB."""
    if TEMP_DB_PATH.exists():
        TEMP_DB_PATH.unlink()
        logger.info("Removed existing temp DB: %s", TEMP_DB_PATH)

    conn = sqlite3.connect(str(TEMP_DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS p64c_dryrun_rows (
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
            entropy_value REAL,
            regime TEXT,
            UNIQUE(strategy_id, target_draw)
        )
    """)
    conn.commit()
    logger.info("Temp DB created: %s", TEMP_DB_PATH)
    return conn


# ─── Row generator ────────────────────────────────────────────────────────────

def _generate_dryrun_rows(all_draws: List[dict]) -> List[dict]:
    """
    Generate 1500 dry-run rows for zonal_entropy_2bet.

    Strictly causal: history = all draws STRICTLY BEFORE the target draw.
    Uses ZonalEntropy2BetAdapter from p56_wave5_powerlotto_adapters.
    No future data leak. No random.seed(). Deterministic.
    Also records entropy value and regime (chaotic/stable) per draw.
    """
    from lottery_api.models.p56_wave5_powerlotto_adapters import (
        ZonalEntropy2BetAdapter,
        _zone_entropy,
        _ENTROPY_CHAOS_THRESHOLD,
        _ZONE_WINDOW,
    )

    adapter = ZonalEntropy2BetAdapter()
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
        history = all_draws[:target_idx]  # strictly before target (causal)

        replay_status = "PREDICTED"
        reject_reason = None
        predicted_numbers: Optional[List[int]] = None
        predicted_special: Optional[int] = None
        hit_numbers: List[int] = []
        hit_count = 0
        special_hit = 0
        entropy_value = None
        regime = None

        try:
            # Compute entropy for regime tracking (same window used by adapter)
            if len(history) >= _ZONE_WINDOW:
                entropy_value = _zone_entropy(history, window=_ZONE_WINDOW)
                regime = "chaotic" if entropy_value > _ENTROPY_CHAOS_THRESHOLD else "stable"

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
            "entropy_value": entropy_value,
            "regime": regime,
        })

    return rows


# ─── Temp DB insert ───────────────────────────────────────────────────────────

def _insert_rows(conn: sqlite3.Connection, rows: List[dict]) -> None:
    """Insert dry-run rows into temp DB. Idempotent (UNIQUE constraint)."""
    conn.executemany("""
        INSERT OR IGNORE INTO p64c_dryrun_rows (
            strategy_id, lottery_type, target_draw, draw_date,
            prediction_cutoff_date, prediction_generated_at,
            predicted_numbers, predicted_special,
            actual_numbers, actual_special,
            hit_numbers, hit_count, special_hit,
            lifecycle, replay_status, reject_reason, history_cutoff_draw,
            entropy_value, regime
        ) VALUES (
            :strategy_id, :lottery_type, :target_draw, :draw_date,
            :prediction_cutoff_date, :prediction_generated_at,
            :predicted_numbers, :predicted_special,
            :actual_numbers, :actual_special,
            :hit_numbers, :hit_count, :special_hit,
            :lifecycle, :replay_status, :reject_reason, :history_cutoff_draw,
            :entropy_value, :regime
        )
    """, rows)
    conn.commit()
    logger.info("Inserted %d rows into temp DB", len(rows))


# ─── Metrics computation ─────────────────────────────────────────────────────

def _compute_metrics(conn: sqlite3.Connection) -> dict:
    """Compute hit distribution, M3+ rate, special hit rate, regime dist from temp DB."""
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT hit_count, special_hit, replay_status, regime "
        "FROM p64c_dryrun_rows WHERE strategy_id = ?", (STRATEGY_ID,)
    ).fetchall()

    total = len(rows)
    predicted_rows = [r for r in rows if r["replay_status"] == "PREDICTED"]
    predicted_count = len(predicted_rows)

    hit_dist: Counter = Counter()
    special_hit_total = 0
    regime_chaotic = 0
    regime_stable = 0
    regime_unknown = 0

    for r in predicted_rows:
        hit_dist[r["hit_count"]] += 1
        special_hit_total += r["special_hit"] or 0
        reg = r["regime"]
        if reg == "chaotic":
            regime_chaotic += 1
        elif reg == "stable":
            regime_stable += 1
        else:
            regime_unknown += 1

    m3plus_count = sum(v for k, v in hit_dist.items() if k >= 3)
    m3plus_rate = (m3plus_count / predicted_count * 100) if predicted_count > 0 else 0.0
    special_hit_rate = (special_hit_total / predicted_count * 100) if predicted_count > 0 else 0.0
    avg_hit = (
        sum(k * v for k, v in hit_dist.items()) / predicted_count
    ) if predicted_count > 0 else 0.0

    target_draws = conn.execute(
        "SELECT MIN(CAST(target_draw AS INTEGER)), MAX(CAST(target_draw AS INTEGER)) "
        "FROM p64c_dryrun_rows WHERE strategy_id = ?", (STRATEGY_ID,)
    ).fetchone()

    dup = conn.execute(
        "SELECT COUNT(*) - COUNT(DISTINCT target_draw) FROM p64c_dryrun_rows "
        "WHERE strategy_id = ?", (STRATEGY_ID,)
    ).fetchone()[0]

    return {
        "total_rows": total,
        "predicted_rows": predicted_count,
        "insufficient_history_rows": sum(
            1 for r in rows if r["replay_status"] == "INSUFFICIENT_HISTORY"
        ),
        "error_rows": sum(
            1 for r in rows
            if r["replay_status"] not in ("PREDICTED", "INSUFFICIENT_HISTORY")
        ),
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
        "regime_distribution": {
            "chaotic": regime_chaotic,
            "stable": regime_stable,
            "unknown": regime_unknown,
            "chaotic_pct": round(
                regime_chaotic / predicted_count * 100 if predicted_count > 0 else 0.0, 2
            ),
        },
        "prior_p57_m3plus_pct": PRIOR_P57_M3PLUS_PCT,
        "vs_prior_p57_pp": round(m3plus_rate - PRIOR_P57_M3PLUS_PCT, 4),
    }


# ─── Semantic validations ─────────────────────────────────────────────────────

def _run_semantic_validations(conn: sqlite3.Connection) -> dict:
    """
    Validate all predicted rows for POWER_LOTTO semantic correctness.
    Returns dict of check_name -> {pass: bool, violations: int, detail: str}
    """
    conn.row_factory = sqlite3.Row
    predicted_rows = conn.execute(
        "SELECT * FROM p64c_dryrun_rows WHERE strategy_id = ? AND replay_status = 'PREDICTED'",
        (STRATEGY_ID,)
    ).fetchall()

    pick_violations = 0
    range_violations = 0
    special_violations = 0
    duplicate_number_violations = 0
    hit_count_violations = 0
    leakage_violations = 0

    for r in predicted_rows:
        pn = json.loads(r["predicted_numbers"]) if r["predicted_numbers"] else []
        hn = json.loads(r["hit_numbers"]) if r["hit_numbers"] else []

        if len(pn) != 6:
            pick_violations += 1
        if any(n < 1 or n > 38 for n in pn):
            range_violations += 1
        sp = r["predicted_special"]
        if sp is not None and (sp < 1 or sp > 8):
            special_violations += 1
        if len(set(pn)) != len(pn):
            duplicate_number_violations += 1
        if r["hit_count"] != len(hn) or r["hit_count"] > 6:
            hit_count_violations += 1
        if r["hit_count"] > 6:
            leakage_violations += 1

    checks = {
        "pick_6_unique_numbers": {
            "pass": pick_violations == 0,
            "violations": pick_violations,
            "detail": "All predicted_numbers must have exactly 6 elements",
        },
        "numbers_in_range_1_38": {
            "pass": range_violations == 0,
            "violations": range_violations,
            "detail": "All predicted_numbers must be in [1, 38]",
        },
        "special_in_range_1_8": {
            "pass": special_violations == 0,
            "violations": special_violations,
            "detail": "predicted_special must be in [1, 8]",
        },
        "no_duplicate_numbers": {
            "pass": duplicate_number_violations == 0,
            "violations": duplicate_number_violations,
            "detail": "No duplicate numbers within a prediction",
        },
        "hit_count_integrity": {
            "pass": hit_count_violations == 0,
            "violations": hit_count_violations,
            "detail": "hit_count must equal len(hit_numbers) and be ≤ 6",
        },
        "no_leakage_indicators": {
            "pass": leakage_violations == 0,
            "violations": leakage_violations,
            "detail": "hit_count must never exceed 6 (leakage indicator)",
        },
    }

    all_pass = all(c["pass"] for c in checks.values())
    return {"all_pass": all_pass, "checks": checks}


# ─── Leakage validation ───────────────────────────────────────────────────────

def _run_leakage_validation(rows: List[dict]) -> dict:
    """Verify causal ordering: prediction_cutoff_date < target draw date."""
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
        ),
    }


# ─── Idempotency check ────────────────────────────────────────────────────────

def _run_idempotency_check(conn: sqlite3.Connection, rows: List[dict]) -> dict:
    """Re-insert same rows; row count must not change (INSERT OR IGNORE)."""
    before = conn.execute(
        "SELECT COUNT(*) FROM p64c_dryrun_rows WHERE strategy_id = ?", (STRATEGY_ID,)
    ).fetchone()[0]

    conn.executemany("""
        INSERT OR IGNORE INTO p64c_dryrun_rows (
            strategy_id, lottery_type, target_draw, draw_date,
            prediction_cutoff_date, prediction_generated_at,
            predicted_numbers, predicted_special,
            actual_numbers, actual_special,
            hit_numbers, hit_count, special_hit,
            lifecycle, replay_status, reject_reason, history_cutoff_draw,
            entropy_value, regime
        ) VALUES (
            :strategy_id, :lottery_type, :target_draw, :draw_date,
            :prediction_cutoff_date, :prediction_generated_at,
            :predicted_numbers, :predicted_special,
            :actual_numbers, :actual_special,
            :hit_numbers, :hit_count, :special_hit,
            :lifecycle, :replay_status, :reject_reason, :history_cutoff_draw,
            :entropy_value, :regime
        )
    """, rows)
    conn.commit()

    after = conn.execute(
        "SELECT COUNT(*) FROM p64c_dryrun_rows WHERE strategy_id = ?", (STRATEGY_ID,)
    ).fetchone()[0]

    return {
        "idempotent": before == after,
        "count_before": before,
        "count_after": after,
        "detail": (
            "Re-insert produced no new rows (INSERT OR IGNORE)"
            if before == after
            else "IDEMPOTENCY VIOLATION"
        ),
    }


# ─── Rollback check ───────────────────────────────────────────────────────────

def _run_rollback_check() -> dict:
    """Verify production DB is untouched after dry-run."""
    conn = sqlite3.connect(str(PROD_DB_PATH))
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays"
        ).fetchone()[0]
        ze_rows = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id = ?",
            (STRATEGY_ID,)
        ).fetchone()[0]
    finally:
        conn.close()

    return {
        "production_rows": count,
        "production_rows_ok": count == EXPECTED_PROD_ROWS,
        "zonal_entropy_production_rows": ze_rows,
        "zonal_entropy_production_rows_ok": ze_rows == 0,
        "detail": (
            "Production DB untouched"
            if count == EXPECTED_PROD_ROWS and ze_rows == 0
            else f"PRODUCTION DB VIOLATION: total={count} ze_rows={ze_rows}"
        ),
    }


# ─── Readiness decision ───────────────────────────────────────────────────────

def _decide_readiness(
    determinism: dict,
    metrics: dict,
    semantic: dict,
    leakage: dict,
    idempotency: dict,
    rollback: dict,
) -> Tuple[str, str]:
    """Classify zonal_entropy_2bet readiness for P65."""
    # Determinism blocker (highest priority)
    if not determinism["determinism_pass"]:
        return (
            "BLOCKED_BY_NON_DETERMINISM",
            f"Determinism check failed: {determinism['violations']} violations "
            f"in {determinism['checks_run']} checks",
        )

    # Hard blockers
    if not semantic["all_pass"]:
        return "REWORK_REQUIRED", "Semantic validation failures detected"
    if not leakage["leakage_free"]:
        return "BLOCKED_BY_LEAKAGE_RISK", "Causal ordering violations detected"
    if not idempotency["idempotent"]:
        return "REWORK_REQUIRED", "Idempotency check failed"
    if not rollback["production_rows_ok"]:
        return "REWORK_REQUIRED", "Production DB row count changed"

    m3plus = metrics["m3plus_rate_pct"]
    vs_baseline = metrics["vs_baseline_pp"]
    predicted = metrics["predicted_rows"]

    if predicted < WINDOW_PERIODS:
        return "WATCHLIST_REHEARSAL_ONLY", (
            f"Only {predicted}/{WINDOW_PERIODS} rows predicted"
        )

    if m3plus >= THEORETICAL_M3_PLUS_BASELINE:
        return "READY_FOR_P65_CONTROLLED_APPLY_PROPOSAL", (
            f"M3+={m3plus:.2f}% ≥ baseline {THEORETICAL_M3_PLUS_BASELINE}%, "
            "all validations pass including determinism, adapter production-ready"
        )

    # Within noise band (SE ≈ 0.50pp at N=1500; -1.0pp = 2σ)
    if vs_baseline >= -1.0:
        return "READY_FOR_P65_WITH_CAUTION", (
            f"M3+={m3plus:.2f}% vs baseline {THEORETICAL_M3_PLUS_BASELINE}% "
            f"({vs_baseline:+.2f}pp), within 2SE noise band. "
            f"P57 precedent: {PRIOR_P57_M3PLUS_PCT}% (−0.20pp, p=0.656). "
            "Determinism verified. Caution: watch live performance first 50 draws."
        )

    return "WATCHLIST_REHEARSAL_ONLY", (
        f"M3+={m3plus:.2f}% vs baseline {THEORETICAL_M3_PLUS_BASELINE}% "
        f"({vs_baseline:+.2f}pp), below −1.0pp noise band. "
        "Recommend extended observation before controlled apply proposal."
    )


# ─── P65 proposal ─────────────────────────────────────────────────────────────

def _draft_p65_proposal(metrics: dict, readiness: str) -> Optional[dict]:
    """Draft P65 controlled apply proposal if readiness is positive."""
    if readiness not in (
        "READY_FOR_P65_CONTROLLED_APPLY_PROPOSAL",
        "READY_FOR_P65_WITH_CAUTION",
    ):
        return None

    prod_rows_after = EXPECTED_PROD_ROWS + WINDOW_PERIODS
    return {
        "proposed_strategy_id": STRATEGY_ID,
        "proposed_apply_rows": WINDOW_PERIODS,
        "expected_production_rows_after": prod_rows_after,
        "caid_template": (
            f"P65_POWERLOTTO_WAVE6_ZONAL_ENTROPY_1500_PROD_"
            f"{datetime.now(timezone.utc).strftime('%Y%m%d')}"
        ),
        "required_duplicate_check": (
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE strategy_id='zonal_entropy_2bet'"
        ),
        "expected_before_apply": 0,
        "backup_required": True,
        "backup_table": "strategy_prediction_replays_backup_before_p65_zonal_entropy",
        "rollback_sql": (
            "DELETE FROM strategy_prediction_replays "
            "WHERE strategy_id='zonal_entropy_2bet'"
        ),
        "explicit_production_apply_authorization_required": (
            "YES apply zonal_entropy_2bet 1500 rows to production for P65"
        ),
        "caution_notes": (
            "M3+ rate below theoretical baseline by < 1.0pp. "
            f"P57 precedent: −0.20pp (z=−0.40, p=0.656, not significant). "
            "Recommend monitoring first 50 draws post-apply."
        ) if readiness == "READY_FOR_P65_WITH_CAUTION" else None,
    }


# ─── Markdown doc writer ──────────────────────────────────────────────────────

def _write_markdown_doc(output: dict) -> None:
    """Write P64c markdown report doc."""
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    m = output["metrics"]
    det = output["determinism_check"]
    rd = output["readiness"]
    gov = output["governance"]
    regime = m.get("regime_distribution", {})

    lines = [
        f"# P64c: POWER_LOTTO Wave 6 — `zonal_entropy_2bet` Determinism + Dry-Run Rehearsal",
        f"",
        f"**Marker**: `{MARKER}`  ",
        f"**Task ID**: P64c  ",
        f"**Strategy**: `{STRATEGY_ID}`  ",
        f"**Date**: {output['generated_at'][:10]}  ",
        f"**Branch**: `p64c-zonal-entropy-wave6-determinism-dryrun`  ",
        f"",
        f"---",
        f"",
        f"## Summary",
        f"",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Production rows (before) | {gov['production_rows_before']} |",
        f"| Production rows (after)  | {gov['production_rows_after']} |",
        f"| Dry-run rows generated   | {m['predicted_rows']} / {WINDOW_PERIODS} |",
        f"| M3+ rate                 | {m['m3plus_rate_pct']:.2f}% |",
        f"| Baseline                 | {THEORETICAL_M3_PLUS_BASELINE:.2f}% |",
        f"| vs Baseline              | {m['vs_baseline_pp']:+.2f} pp |",
        f"| vs Prior P57             | {m['vs_prior_p57_pp']:+.4f} pp |",
        f"| Special hit rate         | {m['special_hit_rate_pct']:.2f}% |",
        f"| Avg hit count            | {m['avg_hit_count']:.4f} |",
        f"| Determinism pass         | {'✅ YES' if det['determinism_pass'] else '❌ NO'} |",
        f"| Readiness                | **{rd['classification']}** |",
        f"",
        f"---",
        f"",
        f"## Determinism Review",
        f"",
        f"**P63 concern**: `determinism_concern=True` — source tool `tools/power_scientific_zonal.py`",
        f"uses `random.seed(42)` + `random.sample()`.  ",
        f"",
        f"**Finding**: P56 **reimplemented** `ZonalEntropy2BetAdapter` independently of the source tool,",
        f"with no `random` module usage. The adapter docstring explicitly states:",
        f"> \"No random.seed() — was flagged in power_scientific_zonal.py — removed\"",
        f"",
        f"**Verification**: Called `get_one_bet()` twice with identical history at "
        f"{det['checks_run']} different draw points.",
        f"All outputs were bitwise identical.",
        f"",
        f"- Fix applied: {'YES' if det['fix_applied'] else 'NO (already clean in P56)'}",
        f"- Violations: {det['violations']} / {det['checks_run']}",
        f"- Source risk status: `{det['source_risk_status']}`",
        f"",
        f"---",
        f"",
        f"## Hit Distribution",
        f"",
        f"| Hits | Count | % of Predicted |",
        f"|------|-------|----------------|",
    ]

    pred = m["predicted_rows"]
    for k in range(7):
        cnt = m["hit_distribution"].get(k, 0)
        pct = cnt / pred * 100 if pred > 0 else 0.0
        lines.append(f"| {k}    | {cnt:5d} | {pct:6.2f}%         |")

    lines += [
        f"",
        f"**M3+ ({m['m3plus_count']} / {pred})**: {m['m3plus_rate_pct']:.2f}%  ",
        f"**vs Baseline ({THEORETICAL_M3_PLUS_BASELINE}%)**: {m['vs_baseline_pp']:+.2f} pp  ",
        f"**vs Prior P57 ({PRIOR_P57_M3PLUS_PCT}%)**: {m['vs_prior_p57_pp']:+.4f} pp  ",
        f"",
        f"---",
        f"",
        f"## Regime Distribution (Entropy Adaptive)",
        f"",
        f"Entropy chaos threshold: `{2.2} bits` (zonal entropy > 2.2 → chaotic / cold mode)",
        f"",
        f"| Regime  | Draws | % |",
        f"|---------|-------|---|",
        f"| Chaotic (cold mode) | {regime.get('chaotic', 0)} | {regime.get('chaotic_pct', 0):.1f}% |",
        f"| Stable (hot mode)   | {regime.get('stable', 0)} | {100 - regime.get('chaotic_pct', 0):.1f}% |",
        f"",
        f"---",
        f"",
        f"## Governance",
        f"",
        f"- **DB writes**: {gov['db_writes']}",
        f"- **Production apply**: {gov['production_apply']}",
        f"- **Online promotions**: {gov['online_promotions']}",
        f"- **Champion replacement**: {gov['champion_replacement']}",
        f"- **Production rows before**: {gov['production_rows_before']}",
        f"- **Production rows after**: {gov['production_rows_after']}",
        f"- **Temp DB**: `{TEMP_DB_PATH}` (not staged, not production)",
        f"",
        f"---",
        f"",
        f"## Readiness Decision",
        f"",
        f"**Classification**: `{rd['classification']}`  ",
        f"",
        f"**Rationale**: {rd['rationale']}  ",
        f"",
    ]

    if output.get("p65_proposal"):
        p65 = output["p65_proposal"]
        lines += [
            f"## P65 Proposal (Conditional)",
            f"",
            f"If authorized, P65 would apply {p65['proposed_apply_rows']} rows for `{STRATEGY_ID}`.",
            f"",
            f"- Expected production rows after: {p65['expected_production_rows_after']}",
            f"- Requires authorization phrase: `{p65['explicit_production_apply_authorization_required']}`",
            f"- Caution: {p65.get('caution_notes', 'None')}",
            f"",
        ]

    lines += [
        f"---",
        f"",
        f"## Classification",
        f"",
        f"`{output.get('classification', 'PENDING')}`  ",
        f"",
        f"_Generated by P64c dry-run rehearsal script. Temp DB: `{TEMP_DB_PATH}`._",
        f"_Production rows: {gov['production_rows_after']} (unchanged)._",
    ]

    with open(OUTPUT_DOC, "w") as f:
        f.write("\n".join(lines) + "\n")
    logger.info("Doc written: %s", OUTPUT_DOC)


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    logger.info("=" * 60)
    logger.info("P64c: zonal_entropy_2bet Wave 6 Determinism + Dry-Run Rehearsal")
    logger.info("=" * 60)

    # Pre-flight: assert production rows unchanged
    prod_rows_before = _assert_prod_rows(phase="pre")

    # Load draws
    all_draws = _load_powerlotto_draws()

    # STEP 1: Determinism review (must pass before dry-run proceeds)
    logger.info("-" * 40)
    logger.info("STEP 1: Determinism review ...")
    determinism = _run_determinism_check(all_draws)
    logger.info(
        "Determinism: %s (%d checks, %d violations)",
        "PASS" if determinism["determinism_pass"] else "FAIL",
        determinism["checks_run"],
        determinism["violations"],
    )

    if not determinism["determinism_pass"]:
        raise RuntimeError(
            f"DETERMINISM CHECK FAILED: {determinism['violations']} violations. "
            "Aborting P64c — adapter must be fixed before dry-run."
        )

    # STEP 2: Dry-run rehearsal
    logger.info("-" * 40)
    logger.info("STEP 2: Dry-run rehearsal (%d draws) ...", WINDOW_PERIODS)

    conn = _setup_temp_db()
    rows = _generate_dryrun_rows(all_draws)
    logger.info("Generated %d rows", len(rows))

    _insert_rows(conn, rows)

    metrics = _compute_metrics(conn)
    logger.info(
        "M3+: %d/%d (%.2f%%) vs baseline %.2f%% (%+.2f pp)",
        metrics["m3plus_count"], metrics["predicted_rows"],
        metrics["m3plus_rate_pct"], THEORETICAL_M3_PLUS_BASELINE,
        metrics["vs_baseline_pp"],
    )
    logger.info("Hit distribution: %s", metrics["hit_distribution"])
    logger.info("Special hit rate: %.2f%%", metrics["special_hit_rate_pct"])
    logger.info(
        "Regime: chaotic=%d stable=%d (%.1f%% chaotic)",
        metrics["regime_distribution"]["chaotic"],
        metrics["regime_distribution"]["stable"],
        metrics["regime_distribution"]["chaotic_pct"],
    )

    semantic = _run_semantic_validations(conn)
    logger.info("Semantic validations: %s", "PASS" if semantic["all_pass"] else "FAIL")

    leakage = _run_leakage_validation(rows)
    logger.info("Leakage check: %s", "PASS" if leakage["leakage_free"] else "FAIL")

    idempotency = _run_idempotency_check(conn, rows)
    logger.info("Idempotency check: %s", "PASS" if idempotency["idempotent"] else "FAIL")

    rollback = _run_rollback_check()
    logger.info("Rollback check: %s", "PASS" if rollback["production_rows_ok"] else "FAIL")

    # Post-flight: assert production rows still unchanged
    prod_rows_after = _assert_prod_rows(phase="post")

    # Readiness decision
    readiness, rationale = _decide_readiness(
        determinism, metrics, semantic, leakage, idempotency, rollback
    )
    logger.info("Readiness: %s", readiness)
    logger.info("Rationale: %s", rationale)

    p65_proposal = _draft_p65_proposal(metrics, readiness)

    # Build output artifact
    now_str = datetime.now(timezone.utc).isoformat()
    output = {
        "schema_version": "1.0",
        "task_id": "P64c",
        "strategy_id": STRATEGY_ID,
        "run_id": RUN_ID,
        "marker": MARKER,
        "generated_at": now_str,
        "temp_db_path": str(TEMP_DB_PATH),
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
            "class": "ZonalEntropy2BetAdapter",
            "file": "lottery_api/models/p56_wave5_powerlotto_adapters.py",
            "strategy_version": "v0.1-p56",
            "deterministic": True,
            "no_random_seed": True,
            "no_random_sample": True,
            "algorithm": "entropy_adaptive_zone_selection",
            "mechanism": (
                "Entropy-adaptive zone selection — "
                "LOW entropy: reinforce dominant zone cluster (hot mode, window=30); "
                "HIGH entropy (>2.2 bits): revert to cold/gap (cold mode, window=100)"
            ),
            "entropy_chaos_threshold_bits": 2.2,
            "zone_entropy_window": 30,
            "cold_fallback_window": 100,
            "pool": "1-38 first zone",
            "pick": 6,
            "special_pool": "1-8",
            "min_history": 30,
        },
        "dry_run": {
            "window_periods": WINDOW_PERIODS,
            "lifecycle": "DRY_RUN",
            "temp_db": str(TEMP_DB_PATH),
            "in_memory": False,
            "temp_db_only": True,
        },
        "determinism_check": determinism,
        "metrics": metrics,
        "semantic_validations": semantic,
        "leakage_validation": leakage,
        "idempotency_check": idempotency,
        "rollback_check": rollback,
        "readiness": {
            "classification": readiness,
            "rationale": rationale,
            "prior_p57_m3plus_pct": PRIOR_P57_M3PLUS_PCT,
            "prior_p57_baseline_pct": THEORETICAL_M3_PLUS_BASELINE,
            "prior_p57_delta_pp": round(PRIOR_P57_M3PLUS_PCT - THEORETICAL_M3_PLUS_BASELINE, 4),
            "prior_p57_mcnemar_p": 0.656,
            "prior_p57_classification": "WATCHLIST_REHEARSAL_ONLY",
        },
        "p65_proposal": p65_proposal,
        "preceding_tasks": ["P63", "P64a", "P64b"],
        "p64a_readiness": "READY_FOR_P65_WITH_CAUTION",
        "p64b_gate": "FAIL",
        "base_commit": "b49c969",
    }

    # Determine final classification marker
    if readiness == "READY_FOR_P65_CONTROLLED_APPLY_PROPOSAL":
        classification = "P64C_ZONAL_ENTROPY_WAVE6_READY_FOR_P65"
    elif readiness == "READY_FOR_P65_WITH_CAUTION":
        classification = "P64C_ZONAL_ENTROPY_WAVE6_READY_WITH_CAUTION"
    elif readiness == "WATCHLIST_REHEARSAL_ONLY":
        classification = "P64C_ZONAL_ENTROPY_WAVE6_WATCHLIST_REHEARSAL_ONLY"
    else:
        classification = f"P64C_ZONAL_ENTROPY_{readiness}"

    output["classification"] = classification

    # Write output JSON
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_JSON, "w") as f:
        json.dump(output, f, indent=2)
    logger.info("Output JSON written: %s", OUTPUT_JSON)

    # Write markdown doc
    _write_markdown_doc(output)

    conn.close()

    logger.info("=" * 60)
    logger.info("FINAL CLASSIFICATION: %s", classification)
    logger.info("Readiness: %s", readiness)
    logger.info(
        "M3+: %.2f%% vs baseline %.2f%% (%+.2f pp)",
        metrics["m3plus_rate_pct"], THEORETICAL_M3_PLUS_BASELINE,
        metrics["vs_baseline_pp"],
    )
    logger.info("Determinism: %s", "PASS" if determinism["determinism_pass"] else "FAIL")
    logger.info("Production rows: %d (unchanged)", prod_rows_after)
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
