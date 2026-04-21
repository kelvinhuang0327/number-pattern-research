"""
Research Runner — 研究執行引擎
==============================
Connects existing components into an autonomous research loop.

Components Connected:
  - HypothesisRegistry: Pre-registration & append-only audit trail
  - AutoResearcher:     Mutation generation & policy memory
  - PolicyValidator:    3-window + permutation test validation gates
  - WeightAdjuster:     Feedback to production weights (existing)
  - StrategyCoordinator: Prediction engine for backtesting

State Machine:
  REGISTERED → RUNNING → VALIDATED / REJECTED / FAILED

Trigger Points:
  1. Cron schedule (daily at 04:00 via APScheduler)
  2. Manual API call  POST /api/research/run
  3. Discovery mode: auto-generate mutations when idle

Design Principles:
  - Pre-register in HypothesisRegistry BEFORE running any validation
  - All results persisted (append-only JSONL + AutoResearcher memory)
  - Fixed random seed for reproducibility
  - No production state mutation — only updates strategy_states via
    existing WeightAdjuster pathway after adoption
  - Concurrency-safe: single-execution lock prevents overlapping runs

2026-04-15 Created — Activating the research loop
"""
import json
import logging
import os
import sys
import time
import threading
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

_HERE = os.path.dirname(os.path.abspath(__file__))
_API_ROOT = os.path.dirname(_HERE)
_PROJECT_ROOT = os.path.dirname(_API_ROOT)
_DATA_DIR = os.path.join(_API_ROOT, 'data')

if _API_ROOT not in sys.path:
    sys.path.insert(0, _API_ROOT)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# Run log — append-only JSONL
_RUN_LOG_PATH = os.path.join(_DATA_DIR, 'research_runs.jsonl')

# Execution lock — prevent concurrent runs
_run_lock = threading.Lock()

ALL_LOTTERY_TYPES = ["DAILY_539", "BIG_LOTTO", "POWER_LOTTO"]


# ═══════════════════════════════════════════════════════════════════════════
# Lazy Imports — avoid circular dependencies at module load
# ═══════════════════════════════════════════════════════════════════════════

def _get_hypothesis_registry():
    from engine.hypothesis_registry import (
        register, update_status, list_by_status, list_all
    )
    return register, update_status, list_by_status, list_all


def _get_auto_researcher():
    from analysis.decision_engine_v2 import (
        AutoResearcher, PolicyConfig, PolicyValidator,
        ConfidenceEngine, ValidationResult,
        _generate_heuristic_policies,
    )
    return AutoResearcher, PolicyConfig, PolicyValidator, ConfidenceEngine, ValidationResult, _generate_heuristic_policies


def _get_coordinator(lottery_type: str):
    from engine.strategy_coordinator import StrategyCoordinator
    return StrategyCoordinator(lottery_type)


def _get_history(lottery_type: str, limit: int = 1500) -> List[Dict]:
    import sqlite3
    db_path = os.path.join(_DATA_DIR, 'lottery_v2.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(
        "SELECT draw, date, numbers, special FROM draws "
        "WHERE lottery_type=? ORDER BY CAST(draw AS INTEGER) ASC LIMIT ?",
        (lottery_type, limit)
    )
    rows = c.fetchall()
    conn.close()
    result = []
    for row in rows:
        nums = json.loads(row["numbers"]) if isinstance(row["numbers"], str) else list(row["numbers"])
        result.append({
            "draw": row["draw"],
            "date": row["date"],
            "numbers": [int(n) for n in nums],
            "special": row["special"],
        })
    return result


# ═══════════════════════════════════════════════════════════════════════════
# Run Log — append-only JSONL for full traceability
# ═══════════════════════════════════════════════════════════════════════════

def _append_run_log(entry: Dict):
    os.makedirs(os.path.dirname(_RUN_LOG_PATH), exist_ok=True)
    with open(_RUN_LOG_PATH, 'a', encoding='utf-8') as f:
        f.write(json.dumps(entry, ensure_ascii=False, default=str) + '\n')


def get_run_history(limit: int = 20) -> List[Dict]:
    if not os.path.exists(_RUN_LOG_PATH):
        return []
    entries = []
    with open(_RUN_LOG_PATH, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return entries[-limit:]


# ═══════════════════════════════════════════════════════════════════════════
# Core: Policy ↔ Hypothesis Bridge
# ═══════════════════════════════════════════════════════════════════════════

def _policy_to_hypothesis_params(policy, lottery_type: str) -> Dict:
    """Convert a PolicyConfig to HypothesisRegistry.register() kwargs."""
    return {
        "name": policy.policy_id,
        "lottery": lottery_type,
        "theory_basis": f"AutoResearch mutation of {policy.strategy_mode}",
        "expected_direction": "3-window Edge > 0, perm_p < 0.05",
        "test_thresholds": {
            "perm_p": 0.05,
            "three_window": True,
            "min_edge": 0.0,
            "sharpe_gt_0": True,
        },
        "seed": 42,
        "n_periods": 1500,
        "notes": json.dumps({
            "conf_weights": policy.conf_weights,
            "n_bets_thresholds": policy.n_bets_thresholds,
            "strategy_mode": policy.strategy_mode,
            "portfolio_type": policy.portfolio_type,
            "min_confidence": policy.min_confidence,
        }, ensure_ascii=False),
    }


def _hypothesis_to_policy(hypothesis: Dict):
    """Reconstruct PolicyConfig from a registered hypothesis."""
    AutoResearcher, PolicyConfig, *_ = _get_auto_researcher()
    notes = hypothesis.get("notes", "{}")
    try:
        config = json.loads(notes)
    except (json.JSONDecodeError, TypeError):
        return None

    if not isinstance(config, dict) or "conf_weights" not in config:
        return None

    return PolicyConfig(
        policy_id=hypothesis["name"],
        conf_weights=config["conf_weights"],
        n_bets_thresholds=config["n_bets_thresholds"],
        strategy_mode=config.get("strategy_mode", "best_300p"),
        portfolio_type=config.get("portfolio_type", "coverage_only"),
        min_confidence=config.get("min_confidence", 0.30),
    )


# ═══════════════════════════════════════════════════════════════════════════
# Core: Run Validation for a Single Hypothesis
# ═══════════════════════════════════════════════════════════════════════════

def _validate_hypothesis(
    hypothesis: Dict,
    researcher,
    validator,
    conf_engine,
    coordinator,
    history: List[Dict],
    n_perm: int = 50,
) -> Dict:
    """
    Run full validation for a single registered hypothesis.
    Returns result dict with verdict and metrics.
    """
    register_fn, update_status_fn, *_ = _get_hypothesis_registry()

    policy = _hypothesis_to_policy(hypothesis)
    if policy is None:
        update_status_fn(hypothesis["hypothesis_id"], "REJECTED", {
            "reason": "Invalid PolicyConfig in hypothesis notes"
        })
        return {"verdict": "FAILED", "reason": "invalid_config"}

    lottery_type = hypothesis["lottery"]
    hid = hypothesis["hypothesis_id"]

    try:
        # Run PolicyValidator.validate()
        val_result = validator.validate(
            policy, lottery_type, history, conf_engine, coordinator,
            n_perm=n_perm,
        )

        # Record in AutoResearcher memory
        researcher.record(lottery_type, policy, val_result)

        # Map verdict to hypothesis status
        if val_result.verdict == "ADOPT":
            status = "VALIDATED"
        elif val_result.verdict == "WATCH":
            status = "PROVISIONAL"
        else:
            status = "REJECTED"

        result_summary = {
            "window_150": val_result.window_150,
            "window_500": val_result.window_500,
            "window_full": val_result.window_full,
            "edge_150": val_result.window_150,
            "edge_300": val_result.window_500,
            "edge_full": val_result.window_full,
            "three_window_ok": val_result.three_window_ok,
            "perm_p": val_result.perm_p,
            "sharpe": val_result.sharpe,
            "verdict": val_result.verdict,
            "n_oos": val_result.n_oos,
        }

        update_status_fn(hid, status, result_summary)

        return {
            "hypothesis_id": hid,
            "policy_id": policy.policy_id,
            "verdict": val_result.verdict,
            "status": status,
            **result_summary,
        }

    except Exception as e:
        logger.error(f"Validation failed for {hid}: {e}")
        update_status_fn(hid, "REJECTED", {"reason": f"runtime_error: {e}"})
        return {"hypothesis_id": hid, "verdict": "FAILED", "reason": str(e)}


# ═══════════════════════════════════════════════════════════════════════════
# Core: Discovery Mode — Generate & Register New Hypotheses
# ═══════════════════════════════════════════════════════════════════════════

def discover_candidates(
    lottery_type: str,
    n_mutations: int = 5,
    n_random: int = 3,
) -> List[Dict]:
    """
    Generate new candidate policies and pre-register them as hypotheses.

    Sources:
      1. Mutations of best adopted policy (via AutoResearcher)
      2. Heuristic seeds (if no adopted policy exists)

    Returns list of registered hypothesis dicts.
    """
    register_fn, _, list_by_status_fn, list_all_fn = _get_hypothesis_registry()
    (AutoResearcher, PolicyConfig, _, _, _,
     _generate_heuristic_policies) = _get_auto_researcher()

    researcher = AutoResearcher()
    registered = []

    # Get best adopted policy for this lottery type
    best = researcher.get_best_adopted(lottery_type)

    if best:
        # Generate mutations of best policy
        mutations = researcher.generate_mutations(best, n=n_mutations)
    else:
        # No adopted policy yet — use heuristic seeds + random
        mutations = _generate_heuristic_policies()[:n_mutations]

    # Check existing hypotheses to avoid duplicates
    existing_names = {h["name"] for h in list_all_fn() if h["lottery"] == lottery_type}

    for policy in mutations:
        if policy.policy_id in existing_names:
            logger.debug(f"Skipping duplicate hypothesis: {policy.policy_id}")
            continue

        params = _policy_to_hypothesis_params(policy, lottery_type)
        try:
            hyp = register_fn(**params)
            registered.append(hyp)
            logger.info(f"[Discovery] Registered: {hyp['hypothesis_id']}")
        except Exception as e:
            logger.warning(f"Failed to register {policy.policy_id}: {e}")

    return registered


# ═══════════════════════════════════════════════════════════════════════════
# Main Entry: run_research_cycle
# ═══════════════════════════════════════════════════════════════════════════

def run_research_cycle(
    lottery_types: Optional[List[str]] = None,
    max_per_type: int = 5,
    n_perm: int = 50,
    discover: bool = True,
    n_discover_mutations: int = 5,
    verbose: bool = False,
) -> Dict:
    """
    Execute one full research cycle:

    1. Discovery: Generate & register new candidate hypotheses
    2. Validation: Run all REGISTERED hypotheses through PolicyValidator
    3. Record: Persist results in HypothesisRegistry + AutoResearcher memory
    4. Report: Return summary of cycle

    This is the main entry point — called by scheduler or API.

    Parameters
    ----------
    lottery_types : list of lottery types to process (default: all 3)
    max_per_type  : max hypotheses to validate per lottery type per cycle
    n_perm        : number of permutations for significance test
    discover      : whether to auto-generate new candidates
    n_discover_mutations : number of mutations per type in discovery
    verbose       : log details

    Returns
    -------
    dict with cycle summary
    """
    if not _run_lock.acquire(blocking=False):
        return {"status": "skipped", "reason": "another_run_in_progress"}

    cycle_start = time.time()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")

    if lottery_types is None:
        lottery_types = ALL_LOTTERY_TYPES

    # Lazy-load shared components
    (AutoResearcherCls, PolicyConfig, PolicyValidatorCls,
     ConfidenceEngineCls, ValidationResult,
     _gen_heuristic) = _get_auto_researcher()

    researcher = AutoResearcherCls()
    validator = PolicyValidatorCls()
    conf_engine = ConfidenceEngineCls(_DATA_DIR)

    register_fn, update_status_fn, list_by_status_fn, list_all_fn = _get_hypothesis_registry()

    cycle_results = {
        "run_id": run_id,
        "status": "completed",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "lottery_types": lottery_types,
        "discovery": {},
        "validation": {},
        "summary": {
            "total_discovered": 0,
            "total_validated": 0,
            "total_adopted": 0,
            "total_rejected": 0,
            "total_failed": 0,
        },
    }

    try:
        for lt in lottery_types:
            logger.info(f"[ResearchRunner] === {lt} ===")

            # ── Step 1: Discovery ──
            discovered = []
            if discover:
                try:
                    discovered = discover_candidates(
                        lt,
                        n_mutations=n_discover_mutations,
                    )
                    cycle_results["discovery"][lt] = len(discovered)
                    cycle_results["summary"]["total_discovered"] += len(discovered)
                    logger.info(f"[ResearchRunner] {lt}: discovered {len(discovered)} candidates")
                except Exception as e:
                    logger.error(f"[ResearchRunner] Discovery failed for {lt}: {e}")
                    cycle_results["discovery"][lt] = f"error: {e}"

            # ── Step 2: Load data ──
            try:
                history = _get_history(lt, limit=1500)
                coordinator = _get_coordinator(lt)
            except Exception as e:
                logger.error(f"[ResearchRunner] Data load failed for {lt}: {e}")
                cycle_results["validation"][lt] = {"error": str(e)}
                continue

            if len(history) < 200:
                logger.warning(f"[ResearchRunner] {lt}: insufficient history ({len(history)} draws)")
                cycle_results["validation"][lt] = {"skipped": "insufficient_history"}
                continue

            # ── Step 3: Validate REGISTERED hypotheses ──
            pending = [
                h for h in list_by_status_fn("REGISTERED")
                if h["lottery"] == lt
            ]

            # Limit per cycle to avoid long runs
            pending = pending[:max_per_type]

            lt_results = []
            for hyp in pending:
                if verbose:
                    logger.info(f"[ResearchRunner] Validating: {hyp['hypothesis_id']}")

                result = _validate_hypothesis(
                    hyp, researcher, validator, conf_engine,
                    coordinator, history, n_perm=n_perm,
                )
                lt_results.append(result)

                verdict = result.get("verdict", "FAILED")
                if verdict == "ADOPT":
                    cycle_results["summary"]["total_adopted"] += 1
                elif verdict in ("REJECT", "WATCH"):
                    cycle_results["summary"]["total_rejected"] += 1
                else:
                    cycle_results["summary"]["total_failed"] += 1

                cycle_results["summary"]["total_validated"] += 1

            cycle_results["validation"][lt] = lt_results

        # ── Step 4: Apply learning signals to strategy weights ──
        try:
            from engine.learning_integrator import apply_all_types as apply_learning
            learn_results = apply_learning(dry_run=False)
            cycle_results["learning"] = {
                lt: r.get("global_multiplier", 1.0)
                for lt, r in learn_results.items()
                if isinstance(r, dict) and r.get("status") == "applied"
            }
        except Exception as e:
            logger.warning(f"[ResearchRunner] Learning integration failed: {e}")
            cycle_results["learning"] = {"error": str(e)}

    except Exception as e:
        logger.error(f"[ResearchRunner] Cycle error: {e}")
        cycle_results["status"] = "error"
        cycle_results["error"] = str(e)
    finally:
        elapsed = time.time() - cycle_start
        cycle_results["elapsed_seconds"] = round(elapsed, 2)
        cycle_results["completed_at"] = datetime.now(timezone.utc).isoformat()

        # Persist run log
        _append_run_log(cycle_results)
        _run_lock.release()

    logger.info(
        f"[ResearchRunner] Cycle {run_id} complete: "
        f"discovered={cycle_results['summary']['total_discovered']}, "
        f"validated={cycle_results['summary']['total_validated']}, "
        f"adopted={cycle_results['summary']['total_adopted']}, "
        f"elapsed={cycle_results.get('elapsed_seconds', '?')}s"
    )
    return cycle_results


# ═══════════════════════════════════════════════════════════════════════════
# Status / Monitoring
# ═══════════════════════════════════════════════════════════════════════════

def get_status() -> Dict:
    """Return current research system status."""
    try:
        _, _, list_by_status_fn, list_all_fn = _get_hypothesis_registry()
        all_hyps = list_all_fn()
        from collections import Counter
        status_counts = Counter(h["status"] for h in all_hyps)
        lottery_counts = Counter(h["lottery"] for h in all_hyps)
    except Exception:
        status_counts = {}
        lottery_counts = {}
        all_hyps = []

    recent_runs = get_run_history(limit=5)

    return {
        "hypothesis_registry": {
            "total": len(all_hyps),
            "by_status": dict(status_counts),
            "by_lottery": dict(lottery_counts),
        },
        "recent_runs": recent_runs,
        "runner_locked": _run_lock.locked(),
    }
