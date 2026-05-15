#!/usr/bin/env python3
"""
Fast Buildout — Lightweight hypothesis generation for learning activation.
==========================================================================
- 3 hypotheses per lottery type
- Windows: 150 and 300 only (skip 500/full)
- Permutation: 5 runs only
- Stop when each type has >=1 PROVISIONAL + >=1 REJECTED (if possible)
"""
import sys, os, json, time, random, math
from collections import Counter

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
sys.path.insert(0, _SCRIPT_DIR)
sys.path.insert(0, _PROJECT_ROOT)
os.chdir(_SCRIPT_DIR)

LOTTERY_TYPES = ['DAILY_539', 'BIG_LOTTO', 'POWER_LOTTO']
HYPOTHESES_PER_TYPE = 3


def count_hypotheses():
    path = os.path.join('data', 'hypothesis_registry.jsonl')
    if not os.path.exists(path):
        return {lt: Counter() for lt in LOTTERY_TYPES}
    seen = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
                seen[e['hypothesis_id']] = e
            except (json.JSONDecodeError, KeyError):
                continue
    by_lt = {lt: Counter() for lt in LOTTERY_TYPES}
    for h in seen.values():
        lt = h.get('lottery', '?')
        if lt in by_lt:
            by_lt[lt][h.get('status', '?')] += 1
    return by_lt


def generate_policies(n, seed_offset=0):
    from analysis.decision_engine_v2 import PolicyConfig
    rng = random.Random(99 + seed_offset)
    timestamp = int(time.time())
    strategies = ['best_300p', 'greedy_30p']
    weight_keys = ['signal_strength', 'signal_agreement', 'regime_stability',
                   'entropy_state', 'recent_performance']
    policies = []
    for i in range(n):
        raw = {k: rng.uniform(0.05, 0.5) for k in weight_keys}
        s = sum(raw.values())
        weights = {k: round(v / s, 4) for k, v in raw.items()}
        thresholds = sorted([round(rng.uniform(0.2, 0.9), 3) for _ in range(4)])
        policy = PolicyConfig(
            policy_id=f"fast_{timestamp}_{i:03d}",
            conf_weights=weights,
            n_bets_thresholds=thresholds,
            strategy_mode=rng.choice(strategies),
            portfolio_type='coverage_only',
            min_confidence=round(rng.uniform(0.15, 0.45), 3),
        )
        policies.append(policy)
    return policies


def register_hypotheses(policies, lottery_type):
    from engine.hypothesis_registry import register, list_all
    existing_names = {h['name'] for h in list_all() if h['lottery'] == lottery_type}
    registered = []
    for policy in policies:
        if policy.policy_id in existing_names:
            continue
        try:
            hyp = register(
                name=policy.policy_id,
                lottery=lottery_type,
                theory_basis=f"Fast buildout ({policy.strategy_mode})",
                expected_direction="2-window Edge check",
                test_thresholds={"perm_p": 0.10, "two_window": True,
                                 "min_edge": 0.0, "sharpe_gt_0": True},
                seed=42,
                n_periods=300,
                notes=json.dumps({
                    "conf_weights": policy.conf_weights,
                    "n_bets_thresholds": policy.n_bets_thresholds,
                    "strategy_mode": policy.strategy_mode,
                    "portfolio_type": policy.portfolio_type,
                    "min_confidence": policy.min_confidence,
                }),
            )
            registered.append(hyp)
        except Exception as e:
            print(f"  Register failed: {policy.policy_id}: {e}")
    return registered


def lightweight_validate(hypothesis, lottery_type):
    """
    Lightweight validation: 2 windows (150, 300), 5 permutations.
    Returns (status, result_summary).
    """
    import numpy as np
    from analysis.decision_engine_v2 import (
        PolicyConfig, PolicyValidator, ConfidenceEngine,
        BASELINES, METRIC_THRESHOLD, POOL_SIZE, MAX_BETS,
    )
    from engine.research_runner import _get_history, _get_coordinator

    # Parse policy from hypothesis notes
    notes = hypothesis.get('notes', '{}')
    try:
        cfg = json.loads(notes) if isinstance(notes, str) else notes
    except json.JSONDecodeError:
        return 'REJECTED', {'reason': 'bad_notes'}

    policy = PolicyConfig(
        policy_id=hypothesis['name'],
        conf_weights=cfg.get('conf_weights', {}),
        n_bets_thresholds=cfg.get('n_bets_thresholds', [0.35, 0.5, 0.65, 0.8]),
        strategy_mode=cfg.get('strategy_mode', 'best_300p'),
        portfolio_type=cfg.get('portfolio_type', 'coverage_only'),
        min_confidence=cfg.get('min_confidence', 0.3),
    )

    history = _get_history(lottery_type, limit=500)
    coordinator = _get_coordinator(lottery_type)
    validator = PolicyValidator()
    conf_engine = ConfidenceEngine(os.path.join(_SCRIPT_DIR, 'data'))

    # 2 windows only: 150 and 300
    e150 = validator._rolling_edge(policy, lottery_type, history, conf_engine, coordinator, 150)
    e300 = validator._rolling_edge(policy, lottery_type, history, conf_engine, coordinator, 300)

    two_window_ok = (e150 > 0) and (e300 > 0)

    # Lightweight permutation: 5 runs
    obs_edge, perm_p = validator._permutation_test(
        policy, lottery_type, history, conf_engine, coordinator,
        n_perm=5, test_window=200,
    )
    perm_ok = perm_p < 0.10  # relaxed threshold for fast mode

    # Sharpe
    baseline_1 = BASELINES[lottery_type][1]
    avg_bets = 3.0
    baseline = 1.0 - (1.0 - baseline_1) ** avg_bets
    vol = math.sqrt(baseline * (1 - baseline) + 1e-9)
    sharpe = obs_edge / vol if vol > 0 else 0.0

    # Verdict: 3 gates
    gates = sum([two_window_ok, perm_ok, sharpe > 0])
    if gates >= 3:
        verdict = 'ADOPT'
        status = 'VALIDATED'
    elif gates == 2:
        verdict = 'WATCH'
        status = 'PROVISIONAL'
    else:
        verdict = 'REJECT'
        status = 'REJECTED'

    summary = {
        'window_150': round(e150, 5),
        'window_300': round(e300, 5),
        'two_window_ok': two_window_ok,
        'perm_p': round(perm_p, 4),
        'sharpe': round(sharpe, 4),
        'verdict': verdict,
        'mode': 'fast_lightweight',
    }
    return status, summary


def main():
    from engine.hypothesis_registry import list_by_status, update_status

    print("=" * 60)
    print("  FAST BUILDOUT — Lightweight Learning Activation")
    print("=" * 60)

    counts = count_hypotheses()
    print("\nCURRENT STATE:")
    for lt in LOTTERY_TYPES:
        c = counts[lt]
        print(f"  {lt:<14} total={sum(c.values())} {dict(c)}")

    total_start = time.time()

    for lt in LOTTERY_TYPES:
        c = counts[lt]
        has_prov_or_val = c.get('PROVISIONAL', 0) + c.get('VALIDATED', 0) > 0
        has_rej = c.get('REJECTED', 0) > 0

        if has_prov_or_val and has_rej:
            print(f"\n  [{lt}] Already has PROVISIONAL/VALIDATED + REJECTED. SKIP.")
            continue

        print(f"\n{'='*60}")
        print(f"  [{lt}] Processing...")
        print(f"{'='*60}")

        # Generate and register 3 new hypotheses
        seed_off = LOTTERY_TYPES.index(lt) * 777
        policies = generate_policies(HYPOTHESES_PER_TYPE, seed_offset=seed_off)
        registered = register_hypotheses(policies, lt)
        print(f"  Registered {len(registered)} new hypotheses")

        # Validate all REGISTERED for this type
        pending = [h for h in list_by_status('REGISTERED') if h['lottery'] == lt]
        pending = pending[:HYPOTHESES_PER_TYPE]  # cap at 3

        for i, hyp in enumerate(pending):
            hid = hyp['hypothesis_id']
            short = hid[:50]
            t0 = time.time()

            status, summary = lightweight_validate(hyp, lt)
            update_status(hid, status, summary)

            elapsed = time.time() - t0
            print(f"  [{i+1}/{len(pending)}] {short:<50s} -> {status:<12s} ({elapsed:.1f}s)")

    # Final summary
    counts = count_hypotheses()
    elapsed_total = time.time() - total_start

    print(f"\n{'='*60}")
    print(f"  FINAL SUMMARY  (elapsed: {elapsed_total:.0f}s)")
    print(f"{'='*60}")
    hdr = f"  {'Type':<14} {'Total':>5} {'REG':>5} {'PROV':>5} {'VAL':>5} {'REJ':>5}"
    print(f"\n{hdr}")
    print(f"  {'---':<14} {'---':>5} {'---':>5} {'---':>5} {'---':>5} {'---':>5}")
    for lt in LOTTERY_TYPES:
        c = counts[lt]
        print(f"  {lt:<14} {sum(c.values()):>5} {c.get('REGISTERED',0):>5} "
              f"{c.get('PROVISIONAL',0):>5} {c.get('VALIDATED',0):>5} {c.get('REJECTED',0):>5}")

    print(f"\nDone. Elapsed: {elapsed_total:.0f}s")


if __name__ == '__main__':
    main()
