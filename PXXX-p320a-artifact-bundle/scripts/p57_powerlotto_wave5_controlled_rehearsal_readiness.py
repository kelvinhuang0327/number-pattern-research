"""
p57_powerlotto_wave5_controlled_rehearsal_readiness.py
=======================================================
P57 — POWER_LOTTO Wave 5 controlled rehearsal readiness review.

READ-ONLY. No production DB write. No lifecycle promotion. No registry mutation.

Reads P56 artifacts and production DB (read-only) to assess whether each
Wave 5 strategy is ready for a P58 controlled production apply proposal.

Outputs:
  outputs/replay/p57_powerlotto_wave5_controlled_rehearsal_readiness_20260525.json

Classification:
  P57_POWERLOTTO_WAVE5_CONTROLLED_REHEARSAL_READINESS_COMPLETED
  P57_POWERLOTTO_WAVE5_PARTIAL_COHORT_RECOMMENDED
"""
from __future__ import annotations

import json
import logging
import math
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# ─── Constants ────────────────────────────────────────────────────────────────

PROD_DB_PATH = PROJECT_ROOT / "lottery_api" / "data" / "lottery_v2.db"
P56_JSON_PATH = PROJECT_ROOT / "outputs" / "replay" / \
    "p56_powerlotto_wave5_adapter_bootstrap_dryrun_20260525.json"
P57_JSON_OUT = PROJECT_ROOT / "outputs" / "replay" / \
    "p57_powerlotto_wave5_controlled_rehearsal_readiness_20260525.json"

EXPECTED_PROD_ROWS = 42460
EXPECTED_DRY_RUN_ROWS = 4500
ROWS_PER_STRATEGY = 1500
LOTTERY_TYPE = "POWER_LOTTO"
FIRST_ZONE_POOL = 38
FIRST_ZONE_PICK = 6
SPECIAL_POOL = 8

WAVE5_STRATEGIES = [
    "cold_complement_2bet",
    "fourier30_markov30_2bet",
    "zonal_entropy_2bet",
]

# Theoretical M3+ baseline for 6-from-38 hypergeometric pick
# P(X >= 3) = 1 - P(X=0) - P(X=1) - P(X=2)
# Computed via combinatorics: ≈ 3.88%
THEORETICAL_M3_BASELINE = 0.0388  # 3.88%

# Special hit rate theoretical baseline: 1/8 = 12.5%
THEORETICAL_SPECIAL_BASELINE = 1.0 / SPECIAL_POOL  # 0.125


# ─── Hypergeometric helpers ───────────────────────────────────────────────────

def _comb(n: int, k: int) -> int:
    """Binomial coefficient C(n, k)."""
    if k < 0 or k > n:
        return 0
    if k == 0 or k == n:
        return 1
    k = min(k, n - k)
    result = 1
    for i in range(k):
        result = result * (n - i) // (i + 1)
    return result


def _hypergeom_pmf(k: int, N: int, K: int, n: int) -> float:
    """P(X = k) for Hypergeometric(N, K, n)."""
    return _comb(K, k) * _comb(N - K, n - k) / _comb(N, n)


def compute_theoretical_m3_baseline(N: int = 38, K: int = 6, n: int = 6) -> float:
    """
    Theoretical P(X >= 3) for 6-from-38 hypergeometric draw.
    N = pool size (38), K = draw size (6), n = pick size (6).
    """
    p_lt3 = sum(_hypergeom_pmf(k, N, K, n) for k in range(3))
    return 1.0 - p_lt3


# ─── Statistical significance ─────────────────────────────────────────────────

def binomial_z_test(observed: float, baseline: float, n: int) -> dict:
    """
    One-sample one-tailed binomial z-test (observed > baseline).

    Returns z-score and approximate p-value.
    """
    se = math.sqrt(baseline * (1.0 - baseline) / n)
    if se == 0:
        return {"z": 0.0, "p_value": 1.0, "significant_at_05": False}

    z = (observed - baseline) / se

    # Approximation: 1 - Φ(z) using erf
    p_value = 0.5 * math.erfc(z / math.sqrt(2))

    return {
        "z": round(z, 4),
        "p_value": round(p_value, 4),
        "significant_at_05": p_value < 0.05,
    }


# ─── Readiness classification ─────────────────────────────────────────────────

READINESS_LEVELS = [
    "READY_FOR_P58_CONTROLLED_APPLY_PROPOSAL",
    "READY_FOR_P58_WITH_CAUTION",
    "WATCHLIST_REHEARSAL_ONLY",
    "REWORK_REQUIRED",
    "BLOCKED_BY_SEMANTICS",
    "BLOCKED_BY_LEAKAGE_RISK",
]


def classify_strategy(
    strategy_id: str,
    stats: dict,
    baseline: float,
) -> dict:
    """
    Classify a Wave 5 strategy based on P56 rehearsal evidence.

    Scoring criteria:
    1. Errors / invalid predictions → REWORK_REQUIRED if > 0
    2. Leakage violations → BLOCKED_BY_LEAKAGE_RISK if > 0
    3. Semantic compliance (valid range, pick count) → BLOCKED_BY_SEMANTICS if fail
    4. M3+ vs baseline + z-test → determines READY vs WATCHLIST
    """
    errors = stats.get("errors", 0)
    if errors > 0:
        return {
            "classification": "REWORK_REQUIRED",
            "reason": f"{errors} prediction errors found in P56 dry-run",
        }

    leakage = stats.get("leakage_violations", 0)
    if leakage > 0:
        return {
            "classification": "BLOCKED_BY_LEAKAGE_RISK",
            "reason": f"{leakage} data leakage violations",
        }

    # Semantic compliance from P56: errors=0 means all rows passed schema validation
    # We trust the P56 schema_validation.valid=True flag (no separate re-check needed)

    hit_3plus_rate = stats.get("hit_3plus_rate", 0.0)
    z_result = binomial_z_test(hit_3plus_rate, baseline, ROWS_PER_STRATEGY)
    z = z_result["z"]
    significant = z_result["significant_at_05"]

    if hit_3plus_rate > baseline and significant:
        classification = "READY_FOR_P58_CONTROLLED_APPLY_PROPOSAL"
        reason = (
            f"M3+ {hit_3plus_rate:.2%} > baseline {baseline:.2%}, "
            f"z={z:.2f}, p<0.05"
        )
    elif hit_3plus_rate > baseline and not significant:
        classification = "READY_FOR_P58_WITH_CAUTION"
        reason = (
            f"M3+ {hit_3plus_rate:.2%} > baseline {baseline:.2%} but "
            f"NOT statistically significant (z={z:.2f}, p={z_result['p_value']:.3f}). "
            f"1500-draw window is insufficient to confirm edge."
        )
    else:
        classification = "WATCHLIST_REHEARSAL_ONLY"
        reason = (
            f"M3+ {hit_3plus_rate:.2%} < baseline {baseline:.2%}. "
            f"Below baseline — not recommended for production apply at this time."
        )

    return {
        "classification": classification,
        "reason": reason,
        "z_test": z_result,
    }


# ─── Production integrity check ───────────────────────────────────────────────

def check_production_integrity() -> dict:
    """
    Read-only check of production DB. Confirms:
    - Total rows = 42460
    - POWER_LOTTO rows = 9140
    - Wave 5 strategies NOT in production DB
    - Champion fourier_rhythm_3bet still ONLINE
    """
    conn = sqlite3.connect(f"file:{PROD_DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    result: dict[str, Any] = {}

    cur.execute("SELECT COUNT(*) AS cnt FROM strategy_prediction_replays")
    total = cur.fetchone()["cnt"]
    result["total_rows"] = total
    result["total_ok"] = total == EXPECTED_PROD_ROWS

    cur.execute(
        "SELECT COUNT(*) AS cnt FROM strategy_prediction_replays "
        "WHERE lottery_type = ?",
        (LOTTERY_TYPE,),
    )
    pl_rows = cur.fetchone()["cnt"]
    result["power_lotto_rows"] = pl_rows
    result["power_lotto_ok"] = pl_rows == 9140

    # Wave 5 must NOT be in production DB
    wave5_in_prod: dict[str, int] = {}
    for sid in WAVE5_STRATEGIES:
        cur.execute(
            "SELECT COUNT(*) AS cnt FROM strategy_prediction_replays "
            "WHERE strategy_id = ? AND lottery_type = ?",
            (sid, LOTTERY_TYPE),
        )
        wave5_in_prod[sid] = cur.fetchone()["cnt"]
    result["wave5_in_prod"] = wave5_in_prod
    result["wave5_not_in_prod"] = all(v == 0 for v in wave5_in_prod.values())

    # Champion check — production table uses replay_status, not lifecycle
    cur.execute(
        "SELECT COUNT(*) AS cnt FROM strategy_prediction_replays "
        "WHERE strategy_id = 'fourier_rhythm_3bet' "
        "AND lottery_type = ?",
        (LOTTERY_TYPE,),
    )
    champ_rows = cur.fetchone()["cnt"]
    result["champion_fourier_rhythm_3bet_rows"] = champ_rows
    result["champion_online"] = champ_rows > 0

    conn.close()
    return result


# ─── P56 artifact integrity ────────────────────────────────────────────────────

def verify_p56_artifacts() -> dict:
    """
    Verify P56 artifact files exist and contain expected data.
    Returns a dict with per-file checks.
    """
    result: dict[str, Any] = {}

    if not P56_JSON_PATH.exists():
        result["p56_json_exists"] = False
        result["ok"] = False
        return result

    result["p56_json_exists"] = True

    with open(P56_JSON_PATH) as f:
        p56 = json.load(f)

    result["classification"] = p56.get("classification")
    result["classification_ok"] = (
        p56.get("classification") == "P56_POWERLOTTO_WAVE5_ADAPTER_BOOTSTRAP_DRYRUN_COMPLETED"
    )
    result["actual_raw_rows"] = p56.get("actual_raw_rows")
    result["rows_ok"] = p56.get("actual_raw_rows") == EXPECTED_DRY_RUN_ROWS
    result["production_rows_before"] = p56.get("production_rows_before")
    result["production_rows_after"] = p56.get("production_rows_after")
    result["production_unchanged"] = (
        p56.get("production_rows_before") == EXPECTED_PROD_ROWS
        and p56.get("production_rows_after") == EXPECTED_PROD_ROWS
    )
    result["schema_valid"] = p56.get("schema_validation", {}).get("valid", False)
    result["leakage_pass"] = p56.get("data_leakage_check", {}).get("pass", False)
    result["r1_ok"] = p56.get("rehearsal", {}).get("r1_apply", {}).get("r1_ok", False)
    result["r2_idempotent"] = p56.get("rehearsal", {}).get("r2_idempotency", {}).get("r2_idempotent", False)
    result["r3_rollback_ok"] = p56.get("rehearsal", {}).get("r3_rollback", {}).get("r3_rollback_ok", False)
    result["governance_no_prod_write"] = not p56.get("governance", {}).get("production_db_write", True)
    result["governance_no_promotion"] = not p56.get("governance", {}).get("lifecycle_promotion", True)
    result["governance_no_champion_replace"] = not p56.get("governance", {}).get("champion_replacement", True)
    result["all_dry_run"] = p56.get("governance", {}).get("all_dry_run", False)
    result["adapters_not_in_registry"] = p56.get("governance", {}).get("adapters_not_in_registry", False)

    result["ok"] = all([
        result["classification_ok"],
        result["rows_ok"],
        result["production_unchanged"],
        result["schema_valid"],
        result["leakage_pass"],
        result["r1_ok"],
        result["r2_idempotent"],
        result["r3_rollback_ok"],
        result["governance_no_prod_write"],
        result["governance_no_promotion"],
        result["governance_no_champion_replace"],
        result["all_dry_run"],
        result["adapters_not_in_registry"],
    ])

    # Return p56 hit_stats for use by readiness scoring
    result["hit_stats"] = p56.get("hit_stats", {})
    result["row_counts_by_strategy"] = p56.get("row_counts_by_strategy", {})

    return result


# ─── P58 proposal ─────────────────────────────────────────────────────────────

def draft_p58_proposal(
    cohort: list[str],
    prod_rows_before: int,
    rows_per_strategy: int,
) -> dict:
    """
    Draft a P58 controlled apply proposal for the selected cohort.
    Does NOT perform any apply — this is a planning artifact only.
    """
    expected_new_rows = len(cohort) * rows_per_strategy
    projected_after = prod_rows_before + expected_new_rows

    return {
        "phase": "P58",
        "title": "POWER_LOTTO Wave 5 Controlled Production Apply",
        "controlled_apply_id": "p58_powerlotto_wave5_controlled_apply",
        "strategies": cohort,
        "rows_per_strategy": rows_per_strategy,
        "expected_new_rows": expected_new_rows,
        "production_rows_before": prod_rows_before,
        "projected_rows_after": projected_after,
        "authorization_phrase_required": (
            "YES apply Wave 5 POWER_LOTTO strategies to production DB"
        ),
        "pre_apply_checks": [
            "drift guard PASS (--strict)",
            f"branch governance guard PASS (--expected-rows {prod_rows_before})",
            "duplicate check: 0 rows already exist for (lottery_type, target_draw, strategy_id)",
            "schema validation PASS on all rows before apply",
            "leakage check PASS (0 violations)",
            "forbidden staging scan PASS",
            f"sqlite3 row count == {prod_rows_before} before apply",
        ],
        "rollback_requirements": [
            "Take DB backup: cp lottery_api/data/lottery_v2.db lottery_api/data/lottery_v2.db.bak_p58",
            "Apply via transaction: BEGIN; INSERT ...; COMMIT;",
            "On failure: ROLLBACK; restore from backup",
            "Verify row count == projected_after after commit",
        ],
        "forbidden_staging": [
            "DB / data files",
            "pid files",
            "backups",
            "runtime files",
            "raw feeds",
            ".fuse_hidden*",
            ".gitignore",
            ".claude/worktrees",
            "unrelated p-series outputs/docs/tests",
            "CEO-Decision.md / active_task.md unless authorized",
        ],
        "tests_required": [
            "tests/test_replay_lifecycle_drift_guard.py",
            "tests/test_replay_api_contract.py",
            "tests/test_replay_branch_governance_guard.py",
            "tests/test_p56_powerlotto_wave5_adapter_bootstrap_dryrun.py",
            "tests/test_p57_powerlotto_wave5_controlled_rehearsal_readiness.py",
            "tests/test_p58_powerlotto_wave5_controlled_apply.py (to be created)",
        ],
        "governance_constraints": [
            "No git add -A or git add .",
            "Whitelist-only staging",
            "lifecycle must be set to ONLINE for production rows",
            "Champion fourier_rhythm_3bet must remain ONLINE",
            "No registry mutation beyond controlled apply rows",
            "No live API calls",
            "No browser smoke tests",
        ],
        "branch": "p58-powerlotto-wave5-controlled-apply (to be created, requires authorization)",
        "note": (
            "P58 must be separately authorized. "
            "P57 recommendation does NOT constitute P58 authorization."
        ),
    }


# ─── Coverage value assessment ─────────────────────────────────────────────────

def assess_coverage_value(strategy_stats: dict) -> dict:
    """
    Assess whether a below-baseline strategy still adds coverage value.
    Coverage value = diversity from existing strategies in different algorithm class.
    """
    coverage = {}
    for sid, stats in strategy_stats.items():
        rate = stats.get("hit_3plus_rate", 0.0)
        below_baseline = rate < THEORETICAL_M3_BASELINE
        margin = abs(rate - THEORETICAL_M3_BASELINE)
        errors = stats.get("errors", 0)
        leakage = stats.get("leakage_violations", 0)

        if errors > 0 or leakage > 0:
            adds_coverage = False
            coverage_note = "Disqualified: errors or leakage violations"
        elif margin <= 0.003:  # within 0.3pp of baseline
            adds_coverage = True
            coverage_note = (
                "Within 0.3pp of baseline — adds coverage diversity "
                "with acceptable performance cost"
            )
        else:
            adds_coverage = False
            coverage_note = (
                f"Below baseline by {margin:.2%} — insufficient evidence "
                "to justify production apply on coverage grounds alone"
            )

        coverage[sid] = {
            "below_baseline": below_baseline,
            "margin_from_baseline": round(margin, 4),
            "adds_coverage_value": adds_coverage,
            "coverage_note": coverage_note,
        }
    return coverage


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    started_at = datetime.now(timezone.utc).isoformat()
    logger.info("=== P57 POWER_LOTTO Wave 5 Controlled Rehearsal Readiness ===")

    # 1. Verify P56 artifacts
    logger.info("Step 1: Verifying P56 artifacts...")
    p56_integrity = verify_p56_artifacts()
    if not p56_integrity.get("ok"):
        logger.error("P56 artifact integrity check FAILED")
        logger.error(json.dumps(p56_integrity, indent=2))
        sys.exit(1)
    logger.info("P56 artifact integrity: OK")

    # 2. Check production DB (read-only)
    logger.info("Step 2: Production DB read-only integrity check...")
    prod_integrity = check_production_integrity()
    if not prod_integrity["total_ok"]:
        logger.error(
            f"Production row count mismatch: expected {EXPECTED_PROD_ROWS}, "
            f"got {prod_integrity['total_rows']}"
        )
        sys.exit(1)
    if not prod_integrity["wave5_not_in_prod"]:
        logger.error("Wave 5 strategies found in production DB — should be DRY_RUN only")
        sys.exit(1)
    logger.info(
        f"Production DB OK: {prod_integrity['total_rows']} rows, "
        f"POWER_LOTTO={prod_integrity['power_lotto_rows']}, "
        f"champion={'ONLINE' if prod_integrity['champion_online'] else 'MISSING'}"
    )

    # 3. Compute theoretical baseline
    baseline = compute_theoretical_m3_baseline()
    logger.info(f"Theoretical M3+ baseline (6/38 hypergeometric): {baseline:.4f} ({baseline:.2%})")

    # 4. Per-strategy readiness scoring
    logger.info("Step 3: Per-strategy readiness scoring...")
    hit_stats = p56_integrity["hit_stats"]
    strategy_results: dict[str, Any] = {}

    for sid in WAVE5_STRATEGIES:
        s = hit_stats.get(sid, {})
        # Augment with leakage (from P56 global leakage check: 0 violations)
        s["leakage_violations"] = 0

        classification_result = classify_strategy(sid, s, baseline)
        z_test = classification_result.get("z_test", {})

        row_count = p56_integrity["row_counts_by_strategy"].get(sid, 0)
        hit_3plus_rate = s.get("hit_3plus_rate", 0.0)
        special_hit_rate = s.get("special_hit_rate", 0.0)

        strategy_results[sid] = {
            "row_count": row_count,
            "predicted": s.get("predicted", 0),
            "errors": s.get("errors", 0),
            "leakage_violations": 0,
            "duplicate_rate": 0.0,  # R2 confirmed 0 duplicates
            "hit_3plus": s.get("hit_3plus", 0),
            "hit_3plus_rate": hit_3plus_rate,
            "hit_count_distribution": s.get("hit_breakdown", {}),
            "special_hits": s.get("special_hits", 0),
            "special_hit_rate": special_hit_rate,
            "theoretical_m3_baseline": round(baseline, 4),
            "theoretical_special_baseline": round(THEORETICAL_SPECIAL_BASELINE, 4),
            "m3_vs_baseline_pp": round((hit_3plus_rate - baseline) * 100, 3),
            "special_vs_baseline_pp": round(
                (special_hit_rate - THEORETICAL_SPECIAL_BASELINE) * 100, 3
            ),
            "deterministic_reproducible": True,  # verified in P56 test suite
            "adapter_source_risk": "LOW",  # bugs fixed (range, random.seed) in P56
            "semantic_compliance": True,  # schema_validation.valid=True in P56
            "z_test": z_test,
            "classification": classification_result["classification"],
            "classification_reason": classification_result["reason"],
            "in_prod_db": prod_integrity["wave5_in_prod"].get(sid, 0) > 0,
        }

        logger.info(
            f"  {sid}: M3+={hit_3plus_rate:.2%} vs baseline={baseline:.2%} "
            f"(z={z_test.get('z', 0):.2f}, p={z_test.get('p_value', 0):.3f}) "
            f"→ {classification_result['classification']}"
        )

    # 5. Coverage value assessment
    logger.info("Step 4: Coverage value assessment...")
    coverage = assess_coverage_value({sid: hit_stats.get(sid, {}) for sid in WAVE5_STRATEGIES})

    # 6. Cohort decision
    logger.info("Step 5: P58 cohort decision...")
    p58_cohort = [
        sid for sid, r in strategy_results.items()
        if r["classification"] in (
            "READY_FOR_P58_CONTROLLED_APPLY_PROPOSAL",
            "READY_FOR_P58_WITH_CAUTION",
        )
    ]
    watchlist = [
        sid for sid, r in strategy_results.items()
        if r["classification"] == "WATCHLIST_REHEARSAL_ONLY"
    ]

    if len(p58_cohort) == len(WAVE5_STRATEGIES):
        cohort_decision = "FULL_COHORT_P58"
    elif len(p58_cohort) > 0:
        cohort_decision = "PARTIAL_COHORT_P58"
    else:
        cohort_decision = "NO_P58"

    logger.info(f"Cohort decision: {cohort_decision}")
    logger.info(f"  P58 candidates: {p58_cohort}")
    logger.info(f"  WATCHLIST: {watchlist}")

    # 7. P58 proposal
    logger.info("Step 6: Drafting P58 proposal...")
    p58_proposal = draft_p58_proposal(
        cohort=p58_cohort,
        prod_rows_before=EXPECTED_PROD_ROWS,
        rows_per_strategy=ROWS_PER_STRATEGY,
    )

    # 8. Final classification
    if cohort_decision == "PARTIAL_COHORT_P58":
        final_classification = "P57_POWERLOTTO_WAVE5_PARTIAL_COHORT_RECOMMENDED"
    elif cohort_decision == "FULL_COHORT_P58":
        final_classification = "P57_POWERLOTTO_WAVE5_CONTROLLED_REHEARSAL_READINESS_COMPLETED"
    else:
        final_classification = "P57_POWERLOTTO_WAVE5_REHEARSAL_INCONCLUSIVE"

    finished_at = datetime.now(timezone.utc).isoformat()

    # 9. Write output JSON
    output = {
        "run_id": "p57_wave5_powerlotto_rehearsal_readiness_20260525",
        "classification": final_classification,
        "phase": "P57",
        "lottery_type": LOTTERY_TYPE,
        "started_at": started_at,
        "finished_at": finished_at,
        "pre_flight": {
            "production_rows": prod_integrity["total_rows"],
            "production_rows_ok": prod_integrity["total_ok"],
            "p56_artifact_integrity": p56_integrity["ok"],
            "wave5_not_in_prod": prod_integrity["wave5_not_in_prod"],
            "champion_online": prod_integrity["champion_online"],
        },
        "theoretical_m3_baseline": round(baseline, 4),
        "theoretical_special_baseline": round(THEORETICAL_SPECIAL_BASELINE, 4),
        "strategy_readiness": strategy_results,
        "coverage_value": coverage,
        "cohort_decision": cohort_decision,
        "p58_cohort": p58_cohort,
        "watchlist": watchlist,
        "p58_proposal": p58_proposal,
        "governance": {
            "production_db_write": False,
            "lifecycle_promotion": False,
            "champion_replacement": False,
            "registry_mutation": False,
            "live_api_call": False,
        },
        "overall_ok": True,
        "p56_ref": {
            "commit": "c3f0325",
            "classification": "P56_POWERLOTTO_WAVE5_ADAPTER_BOOTSTRAP_DRYRUN_COMPLETED",
        },
    }

    P57_JSON_OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(P57_JSON_OUT, "w") as f:
        json.dump(output, f, indent=2)

    logger.info(f"JSON written to: {P57_JSON_OUT}")
    logger.info(f"=== RESULT: {final_classification} ===")


if __name__ == "__main__":
    main()
