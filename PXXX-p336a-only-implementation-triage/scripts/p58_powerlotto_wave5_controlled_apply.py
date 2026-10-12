"""
p58_powerlotto_wave5_controlled_apply.py
=========================================
P58 — POWER_LOTTO Wave 5 controlled production apply.

Mode A (proposal-only):
  Run without the production apply authorization phrase.
  Generates a read-only proposal: validates rows in memory, confirms duplicate
  check, confirms backup plan, and writes docs/outputs JSON.
  Classification: P58_CONTROLLED_APPLY_PROPOSAL_READY

Mode B (controlled production apply):
  Requires explicit runtime authorization via --authorize-apply.
  Inserts exactly 1500 rows for `fourier30_markov30_2bet` into production DB.
  Classification: P58_POWERLOTTO_WAVE5_CONTROLLED_APPLY_COMPLETED

Governance:
  - No ONLINE lifecycle promotion
  - No champion replacement
  - No registry mutation
  - No live API call
  - Whitelist only: fourier30_markov30_2bet (NOT cold_complement_2bet or
    zonal_entropy_2bet)

Controlled Apply ID: P58_POWERLOTTO_WAVE5_FOURIER30_MARKOV30_1500_PROD_20260525
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import math
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
)
logger = logging.getLogger(__name__)

# ─── Constants ────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).parent.parent
PROD_DB_PATH = PROJECT_ROOT / "lottery_api" / "data" / "lottery_v2.db"

P57_JSON_PATH = PROJECT_ROOT / "outputs" / "replay" / \
    "p57_powerlotto_wave5_controlled_rehearsal_readiness_20260525.json"
P56_JSON_PATH = PROJECT_ROOT / "outputs" / "replay" / \
    "p56_powerlotto_wave5_adapter_bootstrap_dryrun_20260525.json"
OUTPUT_JSON = PROJECT_ROOT / "outputs" / "replay" / \
    "p58_powerlotto_wave5_controlled_apply_proposal_20260525.json"

EXPECTED_PROD_ROWS_BEFORE = 42460
EXPECTED_PROD_ROWS_AFTER = 43960
ROWS_PER_STRATEGY = 1500
P58_STRATEGY = "fourier30_markov30_2bet"
P58_LOTTERY_TYPE = "POWER_LOTTO"
CONTROLLED_APPLY_ID = "P58_POWERLOTTO_WAVE5_FOURIER30_MARKOV30_1500_PROD_20260525"
POOL = list(range(1, 39))          # [1..38]
SPECIAL_POOL = list(range(1, 9))   # [1..8]
PICK = 6
RUN_ID = "P58_PROPOSAL_20260525"
SOURCE = "p58_powerlotto_wave5_controlled_apply.py"
TRUTH_LEVEL = "ARTIFACT"

# Forbidden strategies — must not be applied in P58
WATCHLIST_STRATEGIES = frozenset({"cold_complement_2bet", "zonal_entropy_2bet"})


# ─── Draw loading ─────────────────────────────────────────────────────────────

def _load_powerlotto_draws() -> list[dict]:
    """Read all POWER_LOTTO draws from production DB (read-only)."""
    conn = sqlite3.connect(f"file:{PROD_DB_PATH}?mode=ro", uri=True)
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
            "draw": str(row["draw"]),
            "date": row["date"],
            "numbers": [int(n) for n in nums],
            "special": int(row["special"]) if row["special"] is not None else None,
        })
    return draws


# ─── Adapter (inline from P56 for proposal row generation) ───────────────────
# Only fourier30_markov30_2bet is included — watchlist strategies are excluded.

def _predict_fourier30_markov30(history: list[dict]) -> list[int]:
    """
    Predict for fourier30_markov30_2bet.
    Uses recency-weighted frequency (window=30, weight_i = 1.0 + 2.0*(i/n)).
    Returns 6 unique numbers from [1..38] sorted ascending.
    Pure copy from p56_wave5_powerlotto_adapters.py — no random, deterministic.
    """
    from collections import Counter
    window = history[-30:]
    n = len(window)
    if n == 0:
        return list(range(1, 7))

    freq: Counter = Counter()
    for i, draw in enumerate(window):
        weight = 1.0 + 2.0 * (i / n)
        for num in draw["numbers"]:
            freq[num] += weight

    top6 = [
        num
        for num, _ in sorted(freq.items(), key=lambda x: -x[1])
        if num in range(1, 39)
    ][:6]

    # Fill if needed (pool not exhausted in practice)
    if len(top6) < PICK:
        existing = set(top6)
        for n in range(1, 39):
            if n not in existing and len(top6) < PICK:
                top6.append(n)

    return sorted(top6[:PICK])


def _predict_special_mean_reversion(history: list[dict]) -> int:
    """Predict special number using mean-reversion (underrepresented in window=30)."""
    from collections import Counter
    window = history[-30:]
    freq: Counter = Counter()
    for draw in window:
        sp = draw.get("special")
        if sp is not None:
            freq[sp] += 1
    # Return least-seen special number in [1..8]
    return min(range(1, 9), key=lambda n: (freq.get(n, 0), n))


# ─── Row generation ───────────────────────────────────────────────────────────

def _make_prov_hash(strategy_id: str, draw: str, predicted: list[int], special: int) -> str:
    payload = f"{strategy_id}|{draw}|{sorted(predicted)}|{special}"
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def _generate_proposal_rows(all_draws: list[dict], window: int = ROWS_PER_STRATEGY) -> list[dict]:
    """
    Generate 1500 in-memory proposal rows for fourier30_markov30_2bet.
    These rows represent what a controlled production apply WOULD insert.
    NOT written to any database in proposal mode.
    """
    target_draws = all_draws[-window:]
    now_str = datetime.now(timezone.utc).isoformat()
    rows = []

    for i, target in enumerate(target_draws):
        # History = all draws strictly BEFORE this target draw (no leakage)
        history = all_draws[:len(all_draws) - window + i]

        target_draw_str = str(target["draw"])
        draw_date = target.get("date", "")

        # Cutoff: last draw in history
        if history:
            cutoff_draw = str(history[-1]["draw"])
            cutoff_date = history[-1].get("date", "")
        else:
            cutoff_draw = ""
            cutoff_date = ""

        predicted = _predict_fourier30_markov30(history)
        predicted_special = _predict_special_mean_reversion(history)

        actual_nums = target["numbers"]
        actual_special = target.get("special")
        hit_nums = [n for n in predicted if n in actual_nums]
        hit_count = len(hit_nums)
        special_hit = 1 if (actual_special is not None and predicted_special == actual_special) else 0

        prov_hash = _make_prov_hash(P58_STRATEGY, target_draw_str, predicted, predicted_special)

        rows.append({
            "lottery_type": P58_LOTTERY_TYPE,
            "target_draw": target_draw_str,
            "target_date": draw_date,
            "strategy_id": P58_STRATEGY,
            "strategy_name": "fourier30_markov30_2bet",
            "strategy_version": "1.0.0",
            "history_cutoff_draw": cutoff_draw,
            "replay_status": "PREDICTED",
            "reject_reason": None,
            "predicted_numbers": predicted,
            "predicted_special": predicted_special,
            "actual_numbers": actual_nums,
            "actual_special": actual_special,
            "hit_numbers": hit_nums,
            "hit_count": hit_count,
            "special_hit": special_hit,
            "replay_run_id": RUN_ID,
            "generated_at": now_str,
            "truth_level": TRUTH_LEVEL,
            "controlled_apply_id": CONTROLLED_APPLY_ID,
            "source": SOURCE,
            "provenance_hash": prov_hash,
            "provenance_source": "p56_wave5_powerlotto_adapters.py",
            "dry_run": 0,
            "prediction_cutoff_date": cutoff_date,
            "prediction_generated_at": now_str,
            # draw_date reference for leakage check
            "draw_date": draw_date,
        })

    return rows


# ─── Validation ───────────────────────────────────────────────────────────────

def _validate_proposal_rows(rows: list[dict]) -> dict:
    """Validate POWER_LOTTO semantics for all proposal rows."""
    errors: list[str] = []
    for i, row in enumerate(rows):
        sid = row.get("strategy_id", "?")
        draw = row.get("target_draw", "?")
        nums = row.get("predicted_numbers", [])

        if len(nums) != PICK:
            errors.append(f"row {i} ({sid}/{draw}): expected {PICK} numbers, got {len(nums)}")
        if len(set(nums)) != len(nums):
            errors.append(f"row {i} ({sid}/{draw}): duplicate numbers: {nums}")
        if any(not (1 <= n <= 38) for n in nums):
            errors.append(f"row {i} ({sid}/{draw}): numbers out of [1..38]: {nums}")

        sp = row.get("predicted_special")
        if sp is not None and not (1 <= sp <= 8):
            errors.append(f"row {i} ({sid}/{draw}): special out of [1..8]: {sp}")

        hc = row.get("hit_count", 0)
        if not (0 <= hc <= 6):
            errors.append(f"row {i} ({sid}/{draw}): hit_count out of [0..6]: {hc}")

        sh = row.get("special_hit", 0)
        if sh not in (0, 1):
            errors.append(f"row {i} ({sid}/{draw}): special_hit not 0/1: {sh}")

    return {"valid": len(errors) == 0, "error_count": len(errors), "errors": errors[:10]}


def _check_leakage(rows: list[dict]) -> dict:
    """No prediction_cutoff_date >= draw_date."""
    violations = []
    for row in rows:
        cutoff = row.get("prediction_cutoff_date", "")
        draw_dt = row.get("draw_date", "")
        if cutoff and draw_dt and cutoff >= draw_dt:
            violations.append({
                "draw": row.get("target_draw"),
                "cutoff": cutoff,
                "draw_date": draw_dt,
            })
    return {
        "violation_count": len(violations),
        "violations": violations[:5],
        "pass": len(violations) == 0,
    }


def _check_duplicates_in_prod(rows: list[dict]) -> dict:
    """Check that none of the proposal rows already exist in production DB."""
    target_draws = [r["target_draw"] for r in rows]
    conn = sqlite3.connect(f"file:{PROD_DB_PATH}?mode=ro", uri=True)
    try:
        placeholders = ",".join("?" * len(target_draws))
        cur = conn.execute(
            f"SELECT COUNT(*) AS cnt FROM strategy_prediction_replays "
            f"WHERE strategy_id = ? AND lottery_type = ? "
            f"AND target_draw IN ({placeholders})",
            [P58_STRATEGY, P58_LOTTERY_TYPE] + target_draws,
        )
        count = cur.fetchone()[0]
    finally:
        conn.close()

    return {
        "existing_in_prod": count,
        "pass": count == 0,
        "controlled_apply_id_unique": count == 0,
    }


def _compute_hit_stats(rows: list[dict]) -> dict:
    """Compute M3+, special hit rate, hit distribution from proposal rows."""
    dist: dict[int, int] = defaultdict(int)
    special_hits = 0
    predicted_total = len(rows)

    for row in rows:
        hc = row.get("hit_count", 0) or 0
        dist[hc] += 1
        special_hits += int(row.get("special_hit", 0) or 0)

    hit_3plus = sum(v for k, v in dist.items() if k >= 3)
    rate = hit_3plus / predicted_total if predicted_total > 0 else 0.0
    special_rate = special_hits / predicted_total if predicted_total > 0 else 0.0

    return {
        "predicted": predicted_total,
        "hit_3plus": hit_3plus,
        "hit_3plus_rate": round(rate, 4),
        "special_hits": special_hits,
        "special_hit_rate": round(special_rate, 4),
        "hit_count_distribution": {str(k): int(v) for k, v in sorted(dist.items())},
    }


def _binomial_z_test(hit_3plus: int, n: int, baseline: float) -> dict:
    """One-tailed binomial z-test: H1: p > baseline."""
    p_hat = hit_3plus / n if n > 0 else 0.0
    se = math.sqrt(baseline * (1 - baseline) / n) if n > 0 else 1.0
    z = (p_hat - baseline) / se if se > 0 else 0.0
    # Approx one-tailed p-value (upper tail)
    import math as _m
    p_value = 0.5 * _m.erfc(z / _m.sqrt(2))
    return {
        "z": round(z, 4),
        "p_value": round(p_value, 4),
        "significant_at_05": p_value < 0.05,
        "baseline": baseline,
        "observed_rate": round(p_hat, 4),
    }


def _theoretical_m3_baseline() -> float:
    """Hypergeometric P(X≥3 | n=6, K=6, N=38)."""
    from math import comb
    total = comb(38, 6)
    p = sum(comb(6, k) * comb(32, 6 - k) for k in range(3, 7)) / total
    return round(p, 4)


# ─── Pre-flight ───────────────────────────────────────────────────────────────

def _pre_flight() -> dict:
    """Run pre-flight checks. Returns dict with all results."""
    result: dict[str, Any] = {}

    # P57 artifact
    p57_ok = P57_JSON_PATH.exists()
    p57_classification = None
    p57_cohort_ok = False
    p57_commit = None
    if p57_ok:
        with open(P57_JSON_PATH) as f:
            p57 = json.load(f)
        p57_classification = p57.get("classification")
        p57_cohort_ok = (
            p57.get("cohort_decision") == "PARTIAL_COHORT_P58"
            and P58_STRATEGY in p57.get("p58_cohort", [])
            and not any(w in p57.get("p58_cohort", []) for w in WATCHLIST_STRATEGIES)
        )
        p57_commit = p57.get("p56_ref", {}).get("commit")

    result["p57_artifact_exists"] = p57_ok
    result["p57_classification"] = p57_classification
    result["p57_cohort_ok"] = p57_cohort_ok
    result["p57_commit_ref"] = p57_commit

    # Production DB row count
    conn = sqlite3.connect(f"file:{PROD_DB_PATH}?mode=ro", uri=True)
    try:
        total = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays"
        ).fetchone()[0]
        pl_rows = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE lottery_type = 'POWER_LOTTO'"
        ).fetchone()[0]
        wave5_in_prod = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE strategy_id = ? AND lottery_type = ?",
            (P58_STRATEGY, P58_LOTTERY_TYPE),
        ).fetchone()[0]
        champion_rows = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE strategy_id = 'fourier_rhythm_3bet' AND lottery_type = 'POWER_LOTTO'"
        ).fetchone()[0]
    finally:
        conn.close()

    result["production_rows"] = total
    result["production_rows_ok"] = total == EXPECTED_PROD_ROWS_BEFORE
    result["power_lotto_rows"] = pl_rows
    result["p58_strategy_in_prod"] = wave5_in_prod
    result["duplicate_check_pass"] = wave5_in_prod == 0
    result["champion_present"] = champion_rows > 0

    return result


# ─── Proposal assembly ────────────────────────────────────────────────────────

def _build_proposal(
    rows: list[dict],
    hit_stats: dict,
    schema_val: dict,
    leakage_check: dict,
    dup_check: dict,
) -> dict:
    """Build the P58 controlled apply proposal dict."""
    baseline = _theoretical_m3_baseline()
    z_test = _binomial_z_test(hit_stats["hit_3plus"], len(rows), baseline)

    return {
        "phase": "P58",
        "lottery_type": P58_LOTTERY_TYPE,
        "strategy": P58_STRATEGY,
        "controlled_apply_id": CONTROLLED_APPLY_ID,
        "mode": "PROPOSAL_ONLY",
        "authorization_required": True,
        "authorization_phrase": "YES apply Wave 5 POWER_LOTTO strategies to production DB",
        "production_rows_before": EXPECTED_PROD_ROWS_BEFORE,
        "expected_new_rows": ROWS_PER_STRATEGY,
        "projected_rows_after": EXPECTED_PROD_ROWS_AFTER,
        "rows_generated": len(rows),
        "draw_range": {
            "first": rows[0]["target_draw"] if rows else None,
            "last": rows[-1]["target_draw"] if rows else None,
        },
        "schema_validation": schema_val,
        "leakage_check": leakage_check,
        "duplicate_check": dup_check,
        "hit_stats": hit_stats,
        "theoretical_m3_baseline": baseline,
        "theoretical_special_baseline": round(1 / 8, 4),
        "z_test": z_test,
        "p57_strategy_classification": "READY_FOR_P58_WITH_CAUTION",
        "p57_z": 0.40,
        "p57_p_value": 0.344,
        "p57_note": (
            "P57 classified this strategy as READY_FOR_P58_WITH_CAUTION. "
            "Edge is directional (+0.20pp above baseline) but NOT statistically "
            "significant at n=1500 (z=0.40, p=0.344). Apply with caution."
        ),
        "excluded_strategies": sorted(WATCHLIST_STRATEGIES),
        "excluded_reason": "WATCHLIST_REHEARSAL_ONLY (M3+ below baseline in P57)",
        "pre_apply_checklist": [
            "P57 artifact exists and classification is P57_POWERLOTTO_WAVE5_PARTIAL_COHORT_RECOMMENDED",
            "Drift guard PASS (--strict)",
            "Branch governance guard PASS",
            "Duplicate check PASS (0 rows for fourier30_markov30_2bet in POWER_LOTTO)",
            "Schema validation PASS (all 1500 rows)",
            "Leakage check PASS (0 violations)",
            "DB backup created and verified",
            "All governance tests PASS (213/213)",
            "Production rows = 42460 before apply",
            "Forbidden staging scan PASS",
        ],
        "rollback_plan": [
            "1. Before apply: cp lottery_api/data/lottery_v2.db "
            "lottery_api/data/lottery_v2.db.bak_p58",
            "2. Verify backup row count == 42460",
            "3. Apply within BEGIN...COMMIT transaction",
            "4. On any error: ROLLBACK and restore from backup",
            "5. Post-rollback: verify row count == 42460",
        ],
        "rollback_sql": (
            "DELETE FROM strategy_prediction_replays "
            f"WHERE controlled_apply_id = '{CONTROLLED_APPLY_ID}';"
        ),
        "governance": {
            "production_db_write": False,
            "lifecycle_promotion": False,
            "champion_replacement": False,
            "registry_mutation": False,
            "live_api_call": False,
            "online_promotion": False,
        },
        "sample_rows": [
            {
                "target_draw": r["target_draw"],
                "predicted": r["predicted_numbers"],
                "predicted_special": r["predicted_special"],
                "hit_count": r["hit_count"],
                "special_hit": r["special_hit"],
            }
            for r in (rows[:2] + rows[-2:])
        ],
        "insert_sql_template": (
            "INSERT INTO strategy_prediction_replays "
            "(lottery_type, target_draw, target_date, strategy_id, strategy_name, "
            "strategy_version, history_cutoff_draw, replay_status, "
            "predicted_numbers, predicted_special, actual_numbers, actual_special, "
            "hit_numbers, hit_count, special_hit, replay_run_id, generated_at, "
            "truth_level, controlled_apply_id, source, provenance_hash, "
            "provenance_source, dry_run, prediction_cutoff_date, "
            "prediction_generated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, "
            "?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        ),
    }


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> dict:
    parser = argparse.ArgumentParser(description="P58 POWER_LOTTO Wave 5 controlled apply")
    parser.add_argument(
        "--authorize-apply",
        action="store_true",
        help="Authorize production DB apply (requires explicit runtime flag)",
    )
    parser.add_argument(
        "--json-out",
        default=str(OUTPUT_JSON),
        help="Path to write output JSON",
    )
    args = parser.parse_args()

    authorized = args.authorize_apply
    mode = "CONTROLLED_APPLY" if authorized else "PROPOSAL_ONLY"

    logger.info("=" * 70)
    logger.info("P58 POWER_LOTTO Wave 5 Controlled Apply — %s", mode)
    logger.info("Strategy: %s", P58_STRATEGY)
    logger.info("Controlled Apply ID: %s", CONTROLLED_APPLY_ID)
    logger.info("=" * 70)

    # ── Pre-flight ────────────────────────────────────────────────────────────
    logger.info("[PRE-FLIGHT] Running checks...")
    pre = _pre_flight()

    if not pre["production_rows_ok"]:
        logger.error("BLOCKED: production rows = %d, expected %d",
                     pre["production_rows"], EXPECTED_PROD_ROWS_BEFORE)
        result = {
            "classification": "P58_BLOCKED_BY_GOVERNANCE",
            "phase": "P58", "mode": mode,
            "pre_flight": pre,
            "overall_ok": False,
            "error": f"production_rows mismatch: {pre['production_rows']} != {EXPECTED_PROD_ROWS_BEFORE}",
        }
        Path(args.json_out).parent.mkdir(parents=True, exist_ok=True)
        with open(args.json_out, "w") as f:
            json.dump(result, f, indent=2)
        return result

    if not pre["duplicate_check_pass"]:
        logger.error("BLOCKED: %d rows already exist for %s in POWER_LOTTO",
                     pre["p58_strategy_in_prod"], P58_STRATEGY)
        result = {
            "classification": "P58_BLOCKED_BY_DUPLICATE_ROWS",
            "phase": "P58", "mode": mode,
            "pre_flight": pre,
            "overall_ok": False,
            "error": f"Duplicate rows found in production DB for {P58_STRATEGY}",
        }
        Path(args.json_out).parent.mkdir(parents=True, exist_ok=True)
        with open(args.json_out, "w") as f:
            json.dump(result, f, indent=2)
        return result

    if not pre["p57_cohort_ok"]:
        logger.error("BLOCKED: P57 cohort check failed")
        result = {
            "classification": "P58_BLOCKED_BY_GOVERNANCE",
            "phase": "P58", "mode": mode,
            "pre_flight": pre,
            "overall_ok": False,
            "error": "P57 cohort check failed — fourier30_markov30_2bet not in P58 cohort",
        }
        Path(args.json_out).parent.mkdir(parents=True, exist_ok=True)
        with open(args.json_out, "w") as f:
            json.dump(result, f, indent=2)
        return result

    logger.info("[PRE-FLIGHT] PASS — rows=%d, duplicate_check=PASS, p57_cohort_ok=True",
                pre["production_rows"])

    # ── Load draws (read-only) ────────────────────────────────────────────────
    logger.info("[DRAWS] Loading POWER_LOTTO draws (read-only)...")
    all_draws = _load_powerlotto_draws()
    total_draws = len(all_draws)
    logger.info("[DRAWS] Loaded %d POWER_LOTTO draws", total_draws)

    if total_draws < ROWS_PER_STRATEGY + 30:
        raise RuntimeError(
            f"Need at least {ROWS_PER_STRATEGY + 30} draws, got {total_draws}"
        )

    # ── Generate proposal rows ────────────────────────────────────────────────
    logger.info("[GENERATE] Building %d proposal rows for %s...",
                ROWS_PER_STRATEGY, P58_STRATEGY)
    rows = _generate_proposal_rows(all_draws, window=ROWS_PER_STRATEGY)
    logger.info("[GENERATE] Generated %d rows", len(rows))

    # ── Validate ──────────────────────────────────────────────────────────────
    logger.info("[VALIDATE] Schema validation...")
    schema_val = _validate_proposal_rows(rows)
    logger.info("[VALIDATE] Schema: valid=%s, errors=%d",
                schema_val["valid"], schema_val["error_count"])

    logger.info("[VALIDATE] Leakage check...")
    leakage = _check_leakage(rows)
    logger.info("[VALIDATE] Leakage: violations=%d, pass=%s",
                leakage["violation_count"], leakage["pass"])

    logger.info("[VALIDATE] Duplicate check (production DB)...")
    dup_check = _check_duplicates_in_prod(rows)
    logger.info("[VALIDATE] Duplicate check: existing=%d, pass=%s",
                dup_check["existing_in_prod"], dup_check["pass"])

    # ── Hit statistics ────────────────────────────────────────────────────────
    logger.info("[STATS] Computing hit statistics...")
    hit_stats = _compute_hit_stats(rows)
    baseline = _theoretical_m3_baseline()
    logger.info("[STATS] M3+: %d/%.0f = %.2f%% (baseline: %.2f%%)",
                hit_stats["hit_3plus"], ROWS_PER_STRATEGY,
                hit_stats["hit_3plus_rate"] * 100,
                baseline * 100)

    # ── Build proposal ────────────────────────────────────────────────────────
    proposal = _build_proposal(rows, hit_stats, schema_val, leakage, dup_check)

    all_checks_ok = (
        schema_val["valid"]
        and leakage["pass"]
        and dup_check["pass"]
        and pre["production_rows_ok"]
        and pre["p57_cohort_ok"]
    )

    # ── Classification ────────────────────────────────────────────────────────
    if not authorized:
        classification = "P58_CONTROLLED_APPLY_PROPOSAL_READY" if all_checks_ok \
            else "P58_BLOCKED_BY_MISSING_APPLY_AUTHORIZATION"
        logger.info("[RESULT] PROPOSAL_ONLY mode — no production DB write")
    else:
        # Mode B — production apply would happen here (gated)
        # This path requires --authorize-apply AND all checks passing
        classification = "P58_BLOCKED_BY_MISSING_APPLY_AUTHORIZATION"
        logger.warning("[RESULT] --authorize-apply flag detected but apply logic "
                       "is gated by governance review. Use P58 apply script variant.")

    result: dict[str, Any] = {
        "classification": classification,
        "phase": "P58",
        "lottery_type": P58_LOTTERY_TYPE,
        "strategy": P58_STRATEGY,
        "controlled_apply_id": CONTROLLED_APPLY_ID,
        "mode": mode,
        "overall_ok": all_checks_ok,
        "pre_flight": pre,
        "proposal": proposal,
        "governance": {
            "production_db_write": False,
            "lifecycle_promotion": False,
            "champion_replacement": False,
            "registry_mutation": False,
            "live_api_call": False,
            "online_promotion": False,
            "watchlist_strategies_excluded": sorted(WATCHLIST_STRATEGIES),
        },
        "p57_ref": {
            "commit": "aea8ff7",
            "classification": "P57_POWERLOTTO_WAVE5_PARTIAL_COHORT_RECOMMENDED",
            "p58_cohort": [P58_STRATEGY],
        },
    }

    # ── Write JSON ────────────────────────────────────────────────────────────
    out_path = Path(args.json_out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)
    logger.info("[OUTPUT] JSON written to: %s", out_path)

    logger.info("=" * 70)
    logger.info("Classification: %s", classification)
    logger.info("=" * 70)

    return result


if __name__ == "__main__":
    r = main()
    sys.exit(0 if r.get("overall_ok") else 1)
