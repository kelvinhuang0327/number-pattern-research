#!/usr/bin/env python3
"""
Phase I — Research Data Buildout
=================================
Generates diverse hypotheses with unique names, registers them,
then validates them through the existing pipeline until each lottery
type has >=10 terminal verdicts (VALIDATED or REJECTED).

Does NOT change any formulas or learning logic — only builds data.
"""
import sys, os, json, time, random
from collections import Counter

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
sys.path.insert(0, _SCRIPT_DIR)
sys.path.insert(0, _PROJECT_ROOT)
os.chdir(_SCRIPT_DIR)

LOTTERY_TYPES = ['DAILY_539', 'BIG_LOTTO', 'POWER_LOTTO']
TARGET_TERMINAL = 10
MAX_CYCLES = 6
HYPOTHESES_PER_BATCH = 13


def count_hypotheses():
    path = os.path.join('data', 'hypothesis_registry.jsonl')
    if not os.path.exists(path):
        return {lt: {'total': 0, 'REGISTERED': 0, 'PROVISIONAL': 0,
                      'VALIDATED': 0, 'REJECTED': 0, 'FAILED': 0, 'terminal': 0}
                for lt in LOTTERY_TYPES}
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
    by_lt = {lt: [] for lt in LOTTERY_TYPES}
    for h in seen.values():
        lt = h.get('lottery', '?')
        if lt in by_lt:
            by_lt[lt].append(h)
    result = {}
    for lt in LOTTERY_TYPES:
        sc = Counter(h.get('status') for h in by_lt[lt])
        result[lt] = {
            'total': len(by_lt[lt]),
            'REGISTERED': sc.get('REGISTERED', 0),
            'PROVISIONAL': sc.get('PROVISIONAL', 0),
            'VALIDATED': sc.get('VALIDATED', 0),
            'REJECTED': sc.get('REJECTED', 0),
            'FAILED': sc.get('FAILED', 0),
            'terminal': sc.get('VALIDATED', 0) + sc.get('REJECTED', 0),
        }
    return result


def generate_diverse_policies(n, seed_offset=0):
    from analysis.decision_engine_v2 import PolicyConfig
    rng = random.Random(42 + seed_offset)
    timestamp = int(time.time())
    strategies = ['best_300p', 'greedy_30p', 'best_300p', 'greedy_30p']
    portfolios = ['coverage_only', 'coverage+concentration', 'coverage_only']
    weight_keys = ['signal_strength', 'signal_agreement', 'regime_stability',
                   'entropy_state', 'recent_performance']
    policies = []
    for i in range(n):
        raw = {k: rng.uniform(0.05, 0.5) for k in weight_keys}
        s = sum(raw.values())
        weights = {k: round(v / s, 4) for k, v in raw.items()}
        thresholds = sorted([round(rng.uniform(0.2, 0.9), 3) for _ in range(4)])
        policy = PolicyConfig(
            policy_id=f"buildout_{timestamp}_{i:03d}",
            conf_weights=weights,
            n_bets_thresholds=thresholds,
            strategy_mode=rng.choice(strategies),
            portfolio_type=rng.choice(portfolios),
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
                theory_basis=f"Buildout diverse mutation ({policy.strategy_mode})",
                expected_direction="3-window Edge > 0, perm_p < 0.05",
                test_thresholds={"perm_p": 0.05, "three_window": True,
                                 "min_edge": 0.0, "sharpe_gt_0": True},
                seed=42,
                n_periods=1500,
                notes=json.dumps({
                    "conf_weights": policy.conf_weights,
                    "n_bets_thresholds": policy.n_bets_thresholds,
                    "strategy_mode": policy.strategy_mode,
                    "portfolio_type": policy.portfolio_type,
                    "min_confidence": policy.min_confidence,
                }, ensure_ascii=False),
            )
            registered.append(hyp)
        except Exception as e:
            print(f"    Register failed: {policy.policy_id}: {e}")
    return registered


def validate_registered(lottery_type, max_count=15):
    from engine.hypothesis_registry import list_by_status
    from engine.research_runner import (
        _validate_hypothesis, _get_auto_researcher, _get_history, _get_coordinator
    )
    (AutoResearcherCls, _, PolicyValidatorCls,
     ConfidenceEngineCls, _, _) = _get_auto_researcher()
    researcher = AutoResearcherCls()
    validator = PolicyValidatorCls()
    conf_engine = ConfidenceEngineCls(os.path.join(_SCRIPT_DIR, 'data'))
    history = _get_history(lottery_type, limit=1500)
    coordinator = _get_coordinator(lottery_type)

    pending = [h for h in list_by_status('REGISTERED') if h['lottery'] == lottery_type]
    pending = pending[:max_count]
    results = []
    for i, hyp in enumerate(pending):
        t0 = time.time()
        result = _validate_hypothesis(
            hyp, researcher, validator, conf_engine,
            coordinator, history, n_perm=50,
        )
        elapsed = time.time() - t0
        status = result.get('status', result.get('verdict', '?'))
        hid = hyp['hypothesis_id']
        short = hid[:45]
        print(f"    [{i+1}/{len(pending)}] {short:<45s} -> {status:<12s} ({elapsed:.1f}s)")
        results.append(result)
    return results


def needs_more(counts):
    return [lt for lt in LOTTERY_TYPES if counts[lt]['terminal'] < TARGET_TERMINAL]


def print_table(counts):
    hdr = f"  {'Type':<14} {'Total':>5} {'REG':>5} {'PROV':>5} {'VAL':>5} {'REJ':>5} {'FAIL':>5} {'Term':>5} {'Ready':>6}"
    sep = f"  {'---':<14} {'---':>5} {'---':>5} {'---':>5} {'---':>5} {'---':>5} {'---':>5} {'---':>5} {'---':>6}"
    print(f"\n{hdr}\n{sep}")
    for lt in LOTTERY_TYPES:
        c = counts[lt]
        ready = 'YES' if c['terminal'] >= TARGET_TERMINAL else 'NO'
        print(f"  {lt:<14} {c['total']:>5} {c['REGISTERED']:>5} {c['PROVISIONAL']:>5} "
              f"{c['VALIDATED']:>5} {c['REJECTED']:>5} {c['FAILED']:>5} {c['terminal']:>5} {ready:>6}")


def main():
    print("=" * 60)
    print("  Phase I -- Research Data Buildout")
    print("=" * 60)

    counts = count_hypotheses()
    print("\nBASELINE:")
    print_table(counts)

    total_start = time.time()
    cycle = 0

    while cycle < MAX_CYCLES:
        needed = needs_more(counts)
        if not needed:
            break

        cycle += 1
        print(f"\n{'='*60}")
        print(f"  CYCLE {cycle}/{MAX_CYCLES} -- targeting: {', '.join(needed)}")
        print(f"{'='*60}")

        for lt in needed:
            t_lt = time.time()
            remaining = TARGET_TERMINAL - counts[lt]['terminal']
            n_gen = max(remaining + 4, HYPOTHESES_PER_BATCH)

            print(f"\n  [{lt}] Generating {n_gen} diverse hypotheses...")
            seed_off = cycle * 100 + LOTTERY_TYPES.index(lt) * 1000
            policies = generate_diverse_policies(n_gen, seed_offset=seed_off)
            registered = register_hypotheses(policies, lt)
            print(f"  [{lt}] Registered: {len(registered)} new")

            total_pending = counts[lt]['REGISTERED'] + len(registered)
            if total_pending == 0:
                print(f"  [{lt}] No hypotheses to validate, skipping")
                continue

            print(f"  [{lt}] Validating {total_pending} REGISTERED hypotheses...")
            results = validate_registered(lt, max_count=n_gen + 5)

            elapsed_lt = time.time() - t_lt
            verdicts = Counter(r.get('status', r.get('verdict', '?')) for r in results)
            print(f"  [{lt}] Results: {dict(verdicts)} in {elapsed_lt:.1f}s")

        counts = count_hypotheses()
        print_table(counts)

    total_elapsed = time.time() - total_start
    print(f"\n{'='*60}")
    print(f"  BUILDOUT COMPLETE -- {cycle} cycles, {total_elapsed:.0f}s total")
    print(f"{'='*60}")
    counts = count_hypotheses()
    print_table(counts)

    print(f"\n  Learning Readiness:")
    all_ready = True
    for lt in LOTTERY_TYPES:
        c = counts[lt]
        ready = c['terminal'] >= TARGET_TERMINAL
        if not ready:
            all_ready = False
        status = 'READY' if ready else f'NEEDS {TARGET_TERMINAL - c["terminal"]} MORE'
        print(f"    {lt}: {status} (terminal={c['terminal']})")

    if all_ready:
        print(f"\n  ALL TYPES LEARNING-READY. Proceed to A/B validation.")
    else:
        print(f"\n  WARNING: Some types not yet learning-ready.")

    return counts


if __name__ == '__main__':
    main()
