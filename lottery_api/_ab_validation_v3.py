#!/usr/bin/env python3
"""
A/B Validation v3: Additive Learning Bonus
============================================
Tests the v2 additive bonus architecture that replaced the broken
multiplicative multiplier.

Pipeline A (Baseline): disable_learning=True  → no additive bonus
Pipeline B (Learning): disable_learning=False → additive bonus from hypotheses
Pipeline C (Mechanism): Inject simulated hypotheses → verify differential bonus works

Key difference from v2: No disk-level strategy_states manipulation needed.
The StrategyCoordinator now accepts disable_learning flag directly.
"""
import sys, os, json, math, copy, time
import numpy as np
from collections import Counter

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _SCRIPT_DIR)
os.chdir(_SCRIPT_DIR)

LOTTERY_TYPES = ['DAILY_539', 'BIG_LOTTO', 'POWER_LOTTO']
WINDOWS = [30, 100, 300]
N_PERM = 500
SEED = 42

BASELINES_1BET = {
    'DAILY_539': 0.114,
    'BIG_LOTTO': 0.076,
    'POWER_LOTTO': 0.076,
}
METRIC_THRESHOLDS = {
    'DAILY_539': 2,
    'BIG_LOTTO': 3,
    'POWER_LOTTO': 3,
}
N_BETS_DEFAULT = {'DAILY_539': 3, 'BIG_LOTTO': 3, 'POWER_LOTTO': 3}


def load_history(lottery_type, limit=1500):
    import sqlite3
    db_path = os.path.join('data', 'lottery_v2.db')
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


def build_coordinator(lottery_type, disable_learning):
    from engine.strategy_coordinator import StrategyCoordinator
    coord = StrategyCoordinator(lottery_type, disable_learning=disable_learning)
    return coord


def walk_forward_evaluate(lottery_type, history, coordinator, window_size, n_bets):
    thresh = METRIC_THRESHOLDS[lottery_type]
    start_idx = max(100, len(history) - window_size)
    end_idx = len(history)
    results = []
    for i in range(start_idx, end_idx):
        h_train = history[:i]
        actual = set(history[i]['numbers'])
        try:
            bets = coordinator.predict(h_train, n_bets=n_bets)
        except Exception:
            bets = []
        if not bets:
            results.append({'draw': history[i].get('draw', str(i)),
                            'hit': False, 'max_match': 0, 'matches_per_bet': [], 'n_bets': n_bets})
            continue
        matches_per_bet = [len(set(bet) & actual) for bet in bets]
        max_match = max(matches_per_bet)
        results.append({'draw': history[i].get('draw', str(i)),
                        'hit': max_match >= thresh, 'max_match': max_match,
                        'matches_per_bet': matches_per_bet, 'n_bets': n_bets})
    return results


def compute_metrics(results, baseline_1bet, n_bets):
    if not results:
        return {'n_draws': 0, 'hit_rate': 0, 'edge': 0, 'sharpe': 0,
                'max_drawdown': 0, 'variance': 0}
    hits = [1 if r['hit'] else 0 for r in results]
    n = len(hits)
    hit_rate = sum(hits) / n
    baseline_n = 1 - (1 - baseline_1bet) ** n_bets
    edge = hit_rate - baseline_n
    vol = math.sqrt(baseline_n * (1 - baseline_n) + 1e-9)
    sharpe = edge / vol if vol > 0 else 0
    max_dd = 0
    cur_dd = 0
    for h in hits:
        if h == 0:
            cur_dd += 1
            max_dd = max(max_dd, cur_dd)
        else:
            cur_dd = 0
    if n >= 30:
        rolling = [sum(hits[j:j+30])/30 for j in range(n - 29)]
        variance = float(np.var(rolling))
    else:
        variance = float(np.var(hits))
    return {
        'n_draws': n,
        'hit_rate': round(hit_rate, 5),
        'baseline': round(baseline_n, 5),
        'edge': round(edge, 5),
        'sharpe': round(sharpe, 4),
        'max_drawdown': max_dd,
        'variance': round(variance, 6),
    }


def permutation_test(hits_a, hits_b, n_perm=500, seed=42):
    rng = np.random.RandomState(seed)
    n = len(hits_a)
    if n != len(hits_b) or n == 0:
        return {'observed_diff': 0, 'p_value': 1.0, 'significant': False, 'n': 0}
    observed_diff = sum(hits_b) / n - sum(hits_a) / n
    combined = list(zip(hits_a, hits_b))
    count_ge = 0
    for _ in range(n_perm):
        shuffled_a, shuffled_b = [], []
        for a, b in combined:
            if rng.random() < 0.5:
                shuffled_a.append(a); shuffled_b.append(b)
            else:
                shuffled_a.append(b); shuffled_b.append(a)
        perm_diff = sum(shuffled_b) / n - sum(shuffled_a) / n
        if abs(perm_diff) >= abs(observed_diff):
            count_ge += 1
    p_value = count_ge / n_perm
    return {'observed_diff': round(observed_diff, 5), 'p_value': round(p_value, 4),
            'significant': p_value < 0.05, 'n_perm': n_perm, 'n': n}


def mcnemar_test(hits_a, hits_b):
    n = min(len(hits_a), len(hits_b))
    b = sum(1 for i in range(n) if hits_a[i] == 0 and hits_b[i] == 1)
    c = sum(1 for i in range(n) if hits_a[i] == 1 and hits_b[i] == 0)
    n_discordant = b + c
    if n_discordant < 5:
        return {'b': b, 'c': c, 'n_discordant': n_discordant,
                'p_value': 1.0, 'significant': False, 'note': 'too_few_discordant'}
    chi2 = (b - c) ** 2 / (b + c)
    p_value = math.exp(-chi2 / 2.0)
    return {'b': b, 'c': c, 'n_discordant': n_discordant,
            'chi2': round(chi2, 4), 'p_value': round(p_value, 4),
            'significant': p_value < 0.05, 'net_improvement': b - c}


def inject_simulated_hypotheses(lottery_type, n_extra=5):
    """Temporarily add simulated hypotheses so all 3 types have data for mechanism test."""
    from datetime import datetime, timezone
    registry_path = os.path.join('data', 'hypothesis_registry.jsonl')
    injected_ids = []
    entries = []
    for i in range(n_extra):
        hid = f"SIM_{lottery_type}_{i}_{int(time.time())}"
        status = 'PROVISIONAL' if i % 2 == 0 else 'VALIDATED'
        entries.append({
            'hypothesis_id': hid,
            'name': f'sim_test_{i}',
            'lottery': lottery_type,
            'status': status,
            'registered_at': datetime.now(timezone.utc).isoformat(),
            'validated_at': datetime.now(timezone.utc).isoformat() if status != 'REGISTERED' else None,
            'result_summary': {'window_full': 0.05, 'verdict': 'WATCH'},
            '_simulated': True,
        })
        injected_ids.append(hid)
    with open(registry_path, 'a', encoding='utf-8') as f:
        for e in entries:
            f.write(json.dumps(e, ensure_ascii=False, default=str) + '\n')
    return injected_ids


def remove_simulated_hypotheses(injected_ids):
    """Remove simulated hypotheses from registry."""
    registry_path = os.path.join('data', 'hypothesis_registry.jsonl')
    if not os.path.exists(registry_path):
        return
    lines = []
    with open(registry_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                if entry.get('hypothesis_id') not in injected_ids:
                    lines.append(line)
            except (json.JSONDecodeError, KeyError):
                lines.append(line)
    with open(registry_path, 'w', encoding='utf-8') as f:
        for line in lines:
            f.write(line + '\n')


def run_ab_test(lottery_type):
    history = load_history(lottery_type, limit=1500)
    if len(history) < 130:
        return {'error': f'insufficient_history ({len(history)} draws)', 'lottery_type': lottery_type}

    n_bets = N_BETS_DEFAULT[lottery_type]
    baseline_1bet = BASELINES_1BET[lottery_type]

    # Pipeline A: No learning
    coord_a = build_coordinator(lottery_type, disable_learning=True)
    bonuses_a = dict(coord_a._learning_bonuses)

    # Pipeline B: Additive bonus enabled
    coord_b = build_coordinator(lottery_type, disable_learning=False)
    bonuses_b = dict(coord_b._learning_bonuses)

    has_bonuses = bool(bonuses_b) and any(abs(v) > 1e-8 for v in bonuses_b.values())
    bonuses_are_differential = len(set(round(v, 8) for v in bonuses_b.values())) > 1 if bonuses_b else False

    # Pipeline C: Mechanism test — inject simulated hypotheses if needed
    injected_ids = []
    if not has_bonuses:
        injected_ids = inject_simulated_hypotheses(lottery_type, n_extra=5)

    coord_c = build_coordinator(lottery_type, disable_learning=False)
    bonuses_c = dict(coord_c._learning_bonuses)

    if injected_ids:
        remove_simulated_hypotheses(injected_ids)

    # Prediction identity check
    try:
        pred_a = coord_a.predict(history, n_bets=n_bets)
        pred_b = coord_b.predict(history, n_bets=n_bets)
        pred_c = coord_c.predict(history, n_bets=n_bets)
        preds_ab_identical = (pred_a == pred_b)
        preds_ac_identical = (pred_a == pred_c)
    except Exception:
        preds_ab_identical = None
        preds_ac_identical = None

    # Walk-forward per window
    available_windows = [w for w in WINDOWS if len(history) >= w + 100]
    if len(history) >= 1600:
        available_windows.append(1500)

    window_results = {}
    for window in available_windows:
        res_a = walk_forward_evaluate(lottery_type, history, coord_a, window, n_bets)
        met_a = compute_metrics(res_a, baseline_1bet, n_bets)
        hits_a = [1 if r['hit'] else 0 for r in res_a]

        res_b = walk_forward_evaluate(lottery_type, history, coord_b, window, n_bets)
        met_b = compute_metrics(res_b, baseline_1bet, n_bets)
        hits_b = [1 if r['hit'] else 0 for r in res_b]

        res_c = walk_forward_evaluate(lottery_type, history, coord_c, window, n_bets)
        met_c = compute_metrics(res_c, baseline_1bet, n_bets)
        hits_c = [1 if r['hit'] else 0 for r in res_c]

        perm_ab = permutation_test(hits_a, hits_b, n_perm=N_PERM, seed=SEED)
        mcn_ab = mcnemar_test(hits_a, hits_b)
        perm_ac = permutation_test(hits_a, hits_c, n_perm=N_PERM, seed=SEED)
        mcn_ac = mcnemar_test(hits_a, hits_c)

        delta_ab = {
            'edge': round(met_b['edge'] - met_a['edge'], 5),
            'sharpe': round(met_b['sharpe'] - met_a['sharpe'], 4),
            'hit_rate': round(met_b['hit_rate'] - met_a['hit_rate'], 5),
            'max_drawdown': met_b['max_drawdown'] - met_a['max_drawdown'],
        }
        delta_ac = {
            'edge': round(met_c['edge'] - met_a['edge'], 5),
            'sharpe': round(met_c['sharpe'] - met_a['sharpe'], 4),
            'hit_rate': round(met_c['hit_rate'] - met_a['hit_rate'], 5),
            'max_drawdown': met_c['max_drawdown'] - met_a['max_drawdown'],
        }

        window_results[window] = {
            'baseline': met_a, 'learning': met_b, 'mechanism': met_c,
            'delta_ab': delta_ab, 'delta_ac': delta_ac,
            'perm_ab': perm_ab, 'mcn_ab': mcn_ab,
            'perm_ac': perm_ac, 'mcn_ac': mcn_ac,
            'n_draws': len(res_a),
        }

    return {
        'lottery_type': lottery_type,
        'n_history': len(history),
        'n_bets': n_bets,
        'has_bonuses': has_bonuses,
        'bonuses_are_differential': bonuses_are_differential,
        'bonuses': {
            'baseline': bonuses_a,
            'learning': {k: round(v, 6) for k, v in bonuses_b.items()},
            'mechanism': {k: round(v, 6) for k, v in bonuses_c.items()},
        },
        'preds_ab_identical': preds_ab_identical,
        'preds_ac_identical': preds_ac_identical,
        'windows': window_results,
        'injected_simulated': bool(injected_ids),
    }


def generate_report(all_results):
    out = []
    def p(s=''):
        out.append(s)

    p("=" * 72)
    p("  A/B VALIDATION v3 — ADDITIVE LEARNING BONUS")
    p("  Date: " + time.strftime("%Y-%m-%d %H:%M:%S"))
    p("=" * 72)

    # Section 1: Architecture Summary
    p("\n── SECTION 1: Architecture ──\n")
    p("  v2 Fix: Replaced multiplicative research_multiplier with additive bonus.")
    p("  Bonuses are applied AFTER weight normalization in aggregate_scores(),")
    p("  bypassing the (k·w/Σk·w) cancellation that killed v1.")
    p("  Bonuses are rank-differentiated by each agent's edge_30p.")
    p("  λ=0.10, clamp=[-0.2, +0.2]")

    # Section 2: Bonus Values
    p("\n── SECTION 2: Per-Agent Bonus Values ──")
    for lt in LOTTERY_TYPES:
        res = all_results.get(lt, {})
        if 'error' in res:
            p(f"\n  {lt}: ERROR — {res['error']}")
            continue
        p(f"\n  {lt} (has_bonuses={res['has_bonuses']}, differential={res['bonuses_are_differential']}):")
        bonuses = res['bonuses']['learning']
        if bonuses:
            for agent, bonus in sorted(bonuses.items(), key=lambda x: -x[1]):
                p(f"    {agent:25s}: {bonus:+.6f}")
        else:
            p("    (no bonuses — insufficient hypotheses)")

        bonuses_c = res['bonuses']['mechanism']
        if bonuses_c:
            p(f"  Mechanism test bonuses:")
            for agent, bonus in sorted(bonuses_c.items(), key=lambda x: -x[1]):
                p(f"    {agent:25s}: {bonus:+.6f}")

    # Section 3: Prediction Identity
    p("\n── SECTION 3: Prediction Identity Check ──")
    for lt in LOTTERY_TYPES:
        res = all_results.get(lt, {})
        if 'error' in res:
            continue
        ab = res.get('preds_ab_identical')
        ac = res.get('preds_ac_identical')
        p(f"  {lt}: A≡B={ab}  A≡C={ac}")
        if ab is False:
            p(f"    ✓ Learning bonus CHANGES predictions (MECHANISM EFFECTIVE)")
        elif ab is True and res['has_bonuses']:
            p(f"    ⚠ Bonus exists but predictions unchanged (NEEDS INVESTIGATION)")
        elif ab is True and not res['has_bonuses']:
            p(f"    ○ No bonus available (insufficient hypotheses) — A≡B expected")
        if ac is False:
            p(f"    ✓ Mechanism test confirms predictions ARE affected by bonus")
        elif ac is True:
            p(f"    ⚠ Mechanism test: predictions unchanged despite bonus")

    # Section 4: Metrics Table
    p("\n── SECTION 4: A/B Metrics Table ──")
    for lt in LOTTERY_TYPES:
        res = all_results.get(lt, {})
        if 'error' in res:
            continue
        p(f"\n  ┌── {lt} ──┐")

        p(f"  │ A vs B (True A/B — additive bonus):")
        p(f"  │ {'Win':>5} | {'edge_A':>10} | {'edge_B':>10} | {'Δ':>10} | {'sharpe_A':>9} | {'sharpe_B':>9} | {'Δ':>8}")
        p(f"  │ {'-'*5}-+-{'-'*10}-+-{'-'*10}-+-{'-'*10}-+-{'-'*9}-+-{'-'*9}-+-{'-'*8}")
        for w, wr in res.get('windows', {}).items():
            a, b = wr['baseline'], wr['learning']
            d = wr['delta_ab']
            p(f"  │ {w:>5} | {a['edge']:>+10.5f} | {b['edge']:>+10.5f} | {d['edge']:>+10.5f} | {a['sharpe']:>9.4f} | {b['sharpe']:>9.4f} | {d['sharpe']:>+8.4f}")

        p(f"  │")
        p(f"  │ A vs C (Mechanism test{' — simulated hypotheses' if res.get('injected_simulated') else ''}):")
        p(f"  │ {'Win':>5} | {'edge_A':>10} | {'edge_C':>10} | {'Δ':>10} | {'sharpe_A':>9} | {'sharpe_C':>9} | {'Δ':>8}")
        p(f"  │ {'-'*5}-+-{'-'*10}-+-{'-'*10}-+-{'-'*10}-+-{'-'*9}-+-{'-'*9}-+-{'-'*8}")
        for w, wr in res.get('windows', {}).items():
            a, c = wr['baseline'], wr['mechanism']
            d = wr['delta_ac']
            p(f"  │ {w:>5} | {a['edge']:>+10.5f} | {c['edge']:>+10.5f} | {d['edge']:>+10.5f} | {a['sharpe']:>9.4f} | {c['sharpe']:>9.4f} | {d['sharpe']:>+8.4f}")
        p(f"  └{'─'*68}┘")

    # Section 5: Statistical Tests
    p("\n── SECTION 5: Statistical Tests ──")
    for lt in LOTTERY_TYPES:
        res = all_results.get(lt, {})
        if 'error' in res:
            continue
        p(f"\n  {lt}:")
        for w, wr in res.get('windows', {}).items():
            pm_ab = wr['perm_ab']
            pm_ac = wr['perm_ac']
            mc_ab = wr['mcn_ab']
            mc_ac = wr['mcn_ac']
            sig_ab = "SIG" if pm_ab['significant'] else "n.s."
            sig_ac = "SIG" if pm_ac['significant'] else "n.s."
            p(f"    W{w:>4}: A/B perm p={pm_ab['p_value']:.4f} ({sig_ab}) McN b={mc_ab['b']} c={mc_ab['c']}")
            p(f"           A/C perm p={pm_ac['p_value']:.4f} ({sig_ac}) McN b={mc_ac['b']} c={mc_ac['c']}")

    # Section 6: Verdict
    p("\n── SECTION 6: VERDICT ──\n")

    # Check critical conditions
    any_ab_diff = any(
        not all_results.get(lt, {}).get('preds_ab_identical', True)
        for lt in LOTTERY_TYPES if 'error' not in all_results.get(lt, {})
    )
    any_ac_diff = any(
        not all_results.get(lt, {}).get('preds_ac_identical', True)
        for lt in LOTTERY_TYPES if 'error' not in all_results.get(lt, {})
    )
    all_differential = all(
        all_results.get(lt, {}).get('bonuses_are_differential', False)
        for lt in LOTTERY_TYPES if 'error' not in all_results.get(lt, {}) and all_results.get(lt, {}).get('has_bonuses')
    )

    p("  Condition Checks:")
    p(f"    [{'✓' if any_ac_diff else '✗'}] Mechanism works: bonus changes predictions (A≢C)")
    p(f"    [{'✓' if all_differential else '○'}] Bonuses are differential (non-uniform)")
    p(f"    [{'✓' if any_ab_diff else '○'}] Real learning changes predictions (A≢B)")

    if any_ac_diff:
        p(f"\n  ═══ MECHANISM: PASS ═══")
        p(f"  The additive bonus architecture WORKS.")
        p(f"  Differential bonuses DO change prediction ranking.")
        p(f"  The v1 normalization cancellation flaw is FIXED.")
    else:
        p(f"\n  ═══ MECHANISM: FAIL ═══")
        p(f"  Additive bonus does NOT change predictions.")

    if any_ab_diff:
        p(f"\n  ═══ LEARNING SIGNAL: ACTIVE ═══")
        p(f"  Real hypothesis data produces non-zero differential bonuses.")
    else:
        has_any_bonus = any(
            all_results.get(lt, {}).get('has_bonuses', False)
            for lt in LOTTERY_TYPES if 'error' not in all_results.get(lt, {})
        )
        if not has_any_bonus:
            p(f"\n  ═══ LEARNING SIGNAL: INACTIVE (insufficient hypotheses) ═══")
            p(f"  A≡B is expected when no hypothesis data exists.")
        else:
            p(f"\n  ═══ LEARNING SIGNAL: PRESENT BUT MAY NEED MORE DATA ═══")

    p("\n" + "=" * 72)
    p("  A/B VALIDATION v3 COMPLETE")
    p("=" * 72)

    return '\n'.join(out)


def main():
    print("A/B Validation v3 — Additive Learning Bonus\n")

    all_results = {}
    for lt in LOTTERY_TYPES:
        print(f"  Running {lt}...", end='', flush=True)
        t0 = time.time()
        try:
            result = run_ab_test(lt)
            all_results[lt] = result
            elapsed = time.time() - t0
            print(f" done ({elapsed:.1f}s)")
        except Exception as e:
            print(f" ERROR: {e}")
            import traceback; traceback.print_exc()
            all_results[lt] = {'error': str(e), 'lottery_type': lt}

    report = generate_report(all_results)
    print(report)

    output_path = os.path.join('data', 'ab_validation_v3_result.json')
    serializable = copy.deepcopy(all_results)
    serializable['_timestamp'] = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(output_path, 'w') as f:
        json.dump(serializable, f, indent=2, ensure_ascii=False, default=str)
    print(f"\nResults saved to: {output_path}")


if __name__ == '__main__':
    main()
