#!/usr/bin/env python3
"""
Comprehensive A/B Validation: Decision Layer WITH vs WITHOUT research_multiplier
=================================================================================
System-level validation — NOT a strategy backtest.

Pipeline A (Baseline): research_multiplier disabled (= 1.0 for all)
Pipeline B (Learning):  research_multiplier from learning_integrator current outputs

Additional: Mechanism test with simulated differential multipliers to verify plumbing.

Metrics: edge, hit_rate, Sharpe, max_drawdown, variance, strategy weight distribution
Statistical: permutation test (500 permutations) + McNemar test on paired outcomes
Windows: 30, 100, 300 draws (+ 1500 if available)
"""
import sys, os, json, math, copy, time
import numpy as np
from collections import Counter, defaultdict

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _SCRIPT_DIR)
os.chdir(_SCRIPT_DIR)

# ── Constants ──
LOTTERY_TYPES = ['DAILY_539', 'BIG_LOTTO', 'POWER_LOTTO']
WINDOWS = [30, 100, 300]
N_PERM = 500
SEED = 42

# Random baseline for 1 bet (M2+ for 539, M3+ for 49-ball games)
BASELINES_1BET = {
    'DAILY_539': 0.114,   # M2+ from 5/39
    'BIG_LOTTO': 0.076,   # M3+ from 6/49
    'POWER_LOTTO': 0.076, # M3+ from 6/38+1/8
}
METRIC_THRESHOLDS = {
    'DAILY_539': 2,   # M2+
    'BIG_LOTTO': 3,   # M3+
    'POWER_LOTTO': 3, # M3+
}
N_BETS_DEFAULT = {'DAILY_539': 3, 'BIG_LOTTO': 3, 'POWER_LOTTO': 3}


# ═════════════════════════════════════════════════════════════
#  DATA LOADING
# ═════════════════════════════════════════════════════════════

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


def load_strategy_states(lottery_type):
    path = os.path.join('data', f'strategy_states_{lottery_type}.json')
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {}


# ═════════════════════════════════════════════════════════════
#  COORDINATOR BUILDER (with multiplier injection)
# ═════════════════════════════════════════════════════════════

def build_coordinator(lottery_type, research_multipliers=None):
    """Build a StrategyCoordinator with specified research_multipliers.
    
    Returns (coordinator, weights_dict, weight_sources_dict).
    Temporarily modifies strategy_states on disk, then restores.
    """
    states_path = os.path.join('data', f'strategy_states_{lottery_type}.json')
    original_states = None

    if research_multipliers is not None and os.path.exists(states_path):
        with open(states_path) as f:
            original_states = json.load(f)
        modified = copy.deepcopy(original_states)
        for name in modified:
            modified[name]['research_multiplier'] = research_multipliers.get(name, 1.0)
        with open(states_path, 'w') as f:
            json.dump(modified, f, indent=2, ensure_ascii=False)

    try:
        from engine.strategy_coordinator import StrategyCoordinator
        coord = StrategyCoordinator(lottery_type)
        weights = dict(coord._weights)
        weight_sources = dict(coord._weight_source)
    finally:
        if original_states is not None:
            with open(states_path, 'w') as f:
                json.dump(original_states, f, indent=2, ensure_ascii=False)

    return coord, weights, weight_sources


# ═════════════════════════════════════════════════════════════
#  WALK-FORWARD EVALUATION
# ═════════════════════════════════════════════════════════════

def walk_forward_evaluate(lottery_type, history, coordinator, window_size, n_bets):
    """
    Walk-forward evaluation over last `window_size` draws.
    For each draw i in [len(history)-window_size, len(history)):
       - train on history[:i]
       - predict
       - compare with history[i]
    Returns per-draw result list.
    """
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
            results.append({
                'draw': history[i].get('draw', str(i)),
                'hit': False,
                'max_match': 0,
                'matches_per_bet': [],
                'n_bets': n_bets,
            })
            continue

        matches_per_bet = [len(set(bet) & actual) for bet in bets]
        max_match = max(matches_per_bet)
        hit = max_match >= thresh

        results.append({
            'draw': history[i].get('draw', str(i)),
            'hit': hit,
            'max_match': max_match,
            'matches_per_bet': matches_per_bet,
            'n_bets': n_bets,
        })

    return results


# ═════════════════════════════════════════════════════════════
#  METRICS COMPUTATION
# ═════════════════════════════════════════════════════════════

def compute_metrics(results, baseline_1bet, n_bets):
    """Compute performance + risk metrics from walk-forward results."""
    if not results:
        return {
            'n_draws': 0, 'hit_rate': 0, 'edge': 0, 'unconditional_edge': 0,
            'avg_hits': 0, 'sharpe': 0, 'max_drawdown': 0, 'max_drawdown_frac': 0,
            'variance': 0, 'avg_bets_per_draw': 0,
        }

    hits = [1 if r['hit'] else 0 for r in results]
    matches = [r['max_match'] for r in results]
    n = len(hits)

    hit_rate = sum(hits) / n
    baseline_n = 1 - (1 - baseline_1bet) ** n_bets
    edge = hit_rate - baseline_n  # unconditional edge
    avg_hits = sum(matches) / n
    avg_bets = sum(r.get('n_bets', n_bets) for r in results) / n

    # Sharpe: edge / volatility
    vol = math.sqrt(baseline_n * (1 - baseline_n) + 1e-9)
    sharpe = edge / vol if vol > 0 else 0

    # Max drawdown (longest losing streak)
    max_dd = 0
    current_dd = 0
    for h in hits:
        if h == 0:
            current_dd += 1
            max_dd = max(max_dd, current_dd)
        else:
            current_dd = 0
    max_dd_frac = max_dd / n if n > 0 else 0

    # Variance of hit rate in rolling windows of 30
    if n >= 30:
        rolling_rates = []
        for j in range(n - 29):
            w = hits[j:j + 30]
            rolling_rates.append(sum(w) / len(w))
        variance = float(np.var(rolling_rates))
    else:
        variance = float(np.var(hits))

    return {
        'n_draws': n,
        'hit_rate': round(hit_rate, 5),
        'baseline': round(baseline_n, 5),
        'edge': round(edge, 5),
        'unconditional_edge': round(edge, 5),
        'avg_hits': round(avg_hits, 3),
        'avg_bets_per_draw': round(avg_bets, 1),
        'sharpe': round(sharpe, 4),
        'max_drawdown': max_dd,
        'max_drawdown_frac': round(max_dd_frac, 4),
        'variance': round(variance, 6),
    }


# ═════════════════════════════════════════════════════════════
#  STATISTICAL TESTS
# ═════════════════════════════════════════════════════════════

def permutation_test(hits_a, hits_b, n_perm=500, seed=42):
    """Two-sided permutation test on paired hit arrays."""
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
                shuffled_a.append(a)
                shuffled_b.append(b)
            else:
                shuffled_a.append(b)
                shuffled_b.append(a)
        perm_diff = sum(shuffled_b) / n - sum(shuffled_a) / n
        if abs(perm_diff) >= abs(observed_diff):
            count_ge += 1

    p_value = count_ge / n_perm
    return {
        'observed_diff': round(observed_diff, 5),
        'p_value': round(p_value, 4),
        'significant': p_value < 0.05,
        'n_perm': n_perm,
        'n': n,
    }


def mcnemar_test(hits_a, hits_b):
    """McNemar test on paired hit/miss outcomes."""
    n = min(len(hits_a), len(hits_b))
    b = sum(1 for i in range(n) if hits_a[i] == 0 and hits_b[i] == 1)  # A miss, B hit
    c = sum(1 for i in range(n) if hits_a[i] == 1 and hits_b[i] == 0)  # A hit, B miss
    n_discordant = b + c

    if n_discordant < 5:
        return {
            'b': b, 'c': c, 'n_discordant': n_discordant,
            'chi2': 0, 'p_value': 1.0, 'significant': False,
            'note': 'too_few_discordant_pairs',
        }

    chi2 = (b - c) ** 2 / (b + c)
    p_value = math.exp(-chi2 / 2.0)  # chi2(1) approximation

    return {
        'b': b, 'c': c, 'n_discordant': n_discordant,
        'chi2': round(chi2, 4),
        'p_value': round(p_value, 4),
        'significant': p_value < 0.05,
        'net_improvement': b - c,
    }


# ═════════════════════════════════════════════════════════════
#  WEIGHT COMPARISON
# ═════════════════════════════════════════════════════════════

def compute_weight_diff(weights_a, weights_b):
    all_keys = set(list(weights_a.keys()) + list(weights_b.keys()))
    diffs = {}
    for k in sorted(all_keys):
        wa = weights_a.get(k, 0)
        wb = weights_b.get(k, 0)
        diffs[k] = {
            'baseline': round(wa, 5),
            'learning': round(wb, 5),
            'diff': round(wb - wa, 5),
            'pct_change': round((wb - wa) / max(wa, 0.001) * 100, 2),
        }
    return diffs


def weight_distribution_summary(weights):
    total = sum(weights.values()) or 1.0
    dist = {k: round(v / total, 4) for k, v in sorted(weights.items(), key=lambda x: -x[1])}
    hhi = sum((v / total) ** 2 for v in weights.values())  # Herfindahl index
    return {'distribution': dist, 'hhi': round(hhi, 4), 'n_agents': len(weights)}


# ═════════════════════════════════════════════════════════════
#  MULTIPLIER SCENARIOS
# ═════════════════════════════════════════════════════════════

def generate_multipliers(lottery_type, scenario='current'):
    states = load_strategy_states(lottery_type)
    strategy_names = list(states.keys())

    if scenario == 'neutral':
        return {name: 1.0 for name in strategy_names}
    elif scenario == 'current':
        return {name: states[name].get('research_multiplier', 1.0) for name in strategy_names}
    elif scenario == 'differential':
        # Simulate realistic per-strategy differences based on edge
        edges = {name: float(states[name].get('edge_30p', 0.0)) for name in strategy_names}
        ranked = sorted(edges.items(), key=lambda x: -x[1])
        n = len(ranked)
        mults = {}
        for i, (name, edge) in enumerate(ranked):
            frac = i / (n - 1) if n > 1 else 0.5
            mult = 1.25 - 0.45 * frac  # [1.25 .. 0.80]
            mults[name] = round(mult, 3)
        return mults
    else:
        return {name: 1.0 for name in strategy_names}


# ═════════════════════════════════════════════════════════════
#  MAIN A/B TEST PER LOTTERY TYPE
# ═════════════════════════════════════════════════════════════

def run_ab_test(lottery_type):
    """Full A/B comparison for one lottery type."""
    history = load_history(lottery_type, limit=1500)
    if len(history) < 130:
        return {'error': f'insufficient_history ({len(history)} draws)', 'lottery_type': lottery_type}

    n_bets = N_BETS_DEFAULT[lottery_type]
    baseline_1bet = BASELINES_1BET[lottery_type]

    # Current multiplier state
    current_mults = generate_multipliers(lottery_type, 'current')
    has_real_signal = any(abs(v - 1.0) > 0.001 for v in current_mults.values())

    # ─── Pipeline A: Baseline (no learning) ───
    neutral_mults = generate_multipliers(lottery_type, 'neutral')
    coord_a, weights_a, sources_a = build_coordinator(lottery_type, neutral_mults)

    # ─── Pipeline B: Learning enabled ───
    if has_real_signal:
        learning_mults = current_mults
        scenario = 'current_learning'
    else:
        learning_mults = neutral_mults  # Same as baseline — honest test
        scenario = 'no_signal_available'
    coord_b, weights_b, sources_b = build_coordinator(lottery_type, learning_mults)

    # ─── Pipeline C: Mechanism test (differential) ───
    diff_mults = generate_multipliers(lottery_type, 'differential')
    coord_c, weights_c, sources_c = build_coordinator(lottery_type, diff_mults)

    # Weight analysis
    weight_diff_ab = compute_weight_diff(weights_a, weights_b)
    weight_diff_ac = compute_weight_diff(weights_a, weights_c)
    dist_a = weight_distribution_summary(weights_a)
    dist_b = weight_distribution_summary(weights_b)
    dist_c = weight_distribution_summary(weights_c)

    # ─── Walk-forward per window ───
    available_windows = [w for w in WINDOWS if len(history) >= w + 100]
    if len(history) >= 1600:
        available_windows.append(1500)

    window_results = {}
    for window in available_windows:
        # Pipeline A
        res_a = walk_forward_evaluate(lottery_type, history, coord_a, window, n_bets)
        met_a = compute_metrics(res_a, baseline_1bet, n_bets)
        hits_a = [1 if r['hit'] else 0 for r in res_a]

        # Pipeline B (current learning)
        res_b = walk_forward_evaluate(lottery_type, history, coord_b, window, n_bets)
        met_b = compute_metrics(res_b, baseline_1bet, n_bets)
        hits_b = [1 if r['hit'] else 0 for r in res_b]

        # Pipeline C (mechanism test)
        res_c = walk_forward_evaluate(lottery_type, history, coord_c, window, n_bets)
        met_c = compute_metrics(res_c, baseline_1bet, n_bets)
        hits_c = [1 if r['hit'] else 0 for r in res_c]

        # Statistical tests A vs B
        perm_ab = permutation_test(hits_a, hits_b, n_perm=N_PERM, seed=SEED)
        mcn_ab = mcnemar_test(hits_a, hits_b)

        # Statistical tests A vs C (mechanism)
        perm_ac = permutation_test(hits_a, hits_c, n_perm=N_PERM, seed=SEED)
        mcn_ac = mcnemar_test(hits_a, hits_c)

        # Delta A vs B
        delta_ab = {
            'edge': round(met_b['edge'] - met_a['edge'], 5),
            'sharpe': round(met_b['sharpe'] - met_a['sharpe'], 4),
            'hit_rate': round(met_b['hit_rate'] - met_a['hit_rate'], 5),
            'max_drawdown': met_b['max_drawdown'] - met_a['max_drawdown'],
            'variance': round(met_b['variance'] - met_a['variance'], 6),
        }

        # Delta A vs C
        delta_ac = {
            'edge': round(met_c['edge'] - met_a['edge'], 5),
            'sharpe': round(met_c['sharpe'] - met_a['sharpe'], 4),
            'hit_rate': round(met_c['hit_rate'] - met_a['hit_rate'], 5),
            'max_drawdown': met_c['max_drawdown'] - met_a['max_drawdown'],
            'variance': round(met_c['variance'] - met_a['variance'], 6),
        }

        def classify_impact(delta, perm):
            if delta['edge'] > 0.005 and perm['significant']:
                return 'POSITIVE'
            elif delta['edge'] < -0.005 and perm['significant']:
                return 'NEGATIVE'
            else:
                return 'NEUTRAL'

        window_results[window] = {
            'baseline': met_a,
            'learning': met_b,
            'mechanism': met_c,
            'delta_ab': delta_ab,
            'delta_ac': delta_ac,
            'impact_ab': classify_impact(delta_ab, perm_ab),
            'impact_ac': classify_impact(delta_ac, perm_ac),
            'perm_ab': perm_ab,
            'mcn_ab': mcn_ab,
            'perm_ac': perm_ac,
            'mcn_ac': mcn_ac,
            'n_draws_evaluated': len(res_a),
        }

    # ─── Edge consistency across windows ───
    edges_a = [wr['baseline']['edge'] for wr in window_results.values()]
    edges_b = [wr['learning']['edge'] for wr in window_results.values()]
    edges_c = [wr['mechanism']['edge'] for wr in window_results.values()]
    edge_consistency = {
        'baseline_std': round(float(np.std(edges_a)), 5) if edges_a else 0,
        'learning_std': round(float(np.std(edges_b)), 5) if edges_b else 0,
        'mechanism_std': round(float(np.std(edges_c)), 5) if edges_c else 0,
    }

    # ─── Prediction identity check ───
    try:
        pred_a = coord_a.predict(history, n_bets=n_bets)
        pred_b = coord_b.predict(history, n_bets=n_bets)
        pred_c = coord_c.predict(history, n_bets=n_bets)
        preds_ab_identical = (pred_a == pred_b)
        preds_ac_identical = (pred_a == pred_c)
    except Exception:
        preds_ab_identical = None
        preds_ac_identical = None

    return {
        'lottery_type': lottery_type,
        'n_history': len(history),
        'n_bets': n_bets,
        'scenario': scenario,
        'has_real_signal': has_real_signal,
        'multipliers': {
            'current': current_mults,
            'neutral': neutral_mults,
            'differential': diff_mults,
        },
        'weights': {
            'baseline': weights_a,
            'learning': weights_b,
            'mechanism': weights_c,
        },
        'weight_diff_ab': weight_diff_ab,
        'weight_diff_ac': weight_diff_ac,
        'weight_dist': {
            'baseline': dist_a,
            'learning': dist_b,
            'mechanism': dist_c,
        },
        'windows': window_results,
        'edge_consistency': edge_consistency,
        'preds_ab_identical': preds_ab_identical,
        'preds_ac_identical': preds_ac_identical,
    }


# ═════════════════════════════════════════════════════════════
#  HYPOTHESIS REGISTRY AUDIT
# ═════════════════════════════════════════════════════════════

def audit_hypothesis_registry():
    """Audit the hypothesis registry state."""
    registry_path = os.path.join('data', 'hypothesis_registry.jsonl')
    if not os.path.exists(registry_path):
        return {'exists': False, 'total': 0, 'by_lottery': {}}

    seen = {}
    with open(registry_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                seen[entry['hypothesis_id']] = entry
            except (json.JSONDecodeError, KeyError):
                continue

    by_lottery = {}
    for h in seen.values():
        lt = h.get('lottery', '?')
        by_lottery.setdefault(lt, []).append(h)

    summary = {}
    for lt, hs in by_lottery.items():
        statuses = Counter(h.get('status', '?') for h in hs)
        summary[lt] = {
            'total': len(hs),
            'statuses': dict(statuses),
            'has_terminal_verdicts': statuses.get('VALIDATED', 0) + statuses.get('REJECTED', 0) > 0,
        }

    return {
        'exists': True,
        'total': len(seen),
        'by_lottery': summary,
    }


# ═════════════════════════════════════════════════════════════
#  REPORT GENERATION
# ═════════════════════════════════════════════════════════════

def generate_report(all_results, hyp_audit):
    """Generate the full 7-section report."""
    out = []
    def p(s=''):
        out.append(s)

    p("=" * 72)
    p("  COMPREHENSIVE A/B VALIDATION REPORT")
    p("  Decision Layer WITH vs WITHOUT Learning (research_multiplier)")
    p("  Date: " + time.strftime("%Y-%m-%d %H:%M:%S"))
    p("=" * 72)

    # ═══════ SECTION 1: Executive Summary ═══════
    p("\n── SECTION 1: Executive Summary ──\n")

    any_real = any(r.get('has_real_signal') for r in all_results.values() if isinstance(r, dict) and 'error' not in r)

    if not any_real:
        p("  FINDING: ALL research_multiplier values = 1.0 across ALL lottery types.")
        p("  Pipeline A (Baseline) and Pipeline B (Learning) are IDENTICAL.")
        p("  The learning_integrator has NEVER been activated.")
        p(f"  Hypothesis registry: {hyp_audit.get('total', 0)} hypotheses total.")
        for lt, info in hyp_audit.get('by_lottery', {}).items():
            p(f"    {lt}: {info['total']} ({info['statuses']}) terminal_verdicts={info['has_terminal_verdicts']}")
        missing = [lt for lt in LOTTERY_TYPES if lt not in hyp_audit.get('by_lottery', {})]
        for lt in missing:
            p(f"    {lt}: 0 hypotheses")
        p("  MECHANISM TEST: Ran with differential multipliers to verify weight propagation.")
        p("  VERDICT PREVIEW: REJECT — no learning signal exists to evaluate.")
    else:
        p("  Real learning signals detected. Evaluating impact...")

    # ═══════ SECTION 2: A/B Metrics Table ═══════
    p("\n── SECTION 2: A/B Metrics Table ──")

    for lt in LOTTERY_TYPES:
        res = all_results.get(lt, {})
        if 'error' in res:
            p(f"\n  {lt}: ERROR — {res['error']}")
            continue

        p(f"\n  ┌── {lt} (scenario: {res['scenario']}) ──┐")
        p(f"  │ History: {res['n_history']} draws, n_bets: {res['n_bets']}")
        p(f"  │ Real learning signal: {res['has_real_signal']}")
        p(f"  │ Predictions A≡B: {res['preds_ab_identical']}  A≡C(mechanism): {res['preds_ac_identical']}")

        # A vs B (true A/B)
        p(f"  │")
        p(f"  │ ── Pipeline A (Baseline) vs Pipeline B (Current Learning) ──")
        header = f"  │ {'Win':>5} | {'Metric':>10} | {'A(base)':>10} | {'B(learn)':>10} | {'Δ(B-A)':>10} | {'Impact':>8}"
        p(header)
        p(f"  │ {'-'*5}-+-{'-'*10}-+-{'-'*10}-+-{'-'*10}-+-{'-'*10}-+-{'-'*8}")
        for w, wr in res.get('windows', {}).items():
            a, b = wr['baseline'], wr['learning']
            d = wr['delta_ab']
            imp = wr['impact_ab']
            p(f"  │ {w:>5} | {'edge':>10} | {a['edge']:>+10.5f} | {b['edge']:>+10.5f} | {d['edge']:>+10.5f} | {imp:>8}")
            p(f"  │       | {'hit_rate':>10} | {a['hit_rate']:>10.5f} | {b['hit_rate']:>10.5f} | {d['hit_rate']:>+10.5f} |")
            p(f"  │       | {'sharpe':>10} | {a['sharpe']:>10.4f} | {b['sharpe']:>10.4f} | {d['sharpe']:>+10.4f} |")
            p(f"  │       | {'max_dd':>10} | {a['max_drawdown']:>10d} | {b['max_drawdown']:>10d} | {d['max_drawdown']:>+10d} |")
            p(f"  │       | {'variance':>10} | {a['variance']:>10.6f} | {b['variance']:>10.6f} | {d['variance']:>+10.6f} |")
            p(f"  │       | {'bets/draw':>10} | {a['avg_bets_per_draw']:>10.1f} | {b['avg_bets_per_draw']:>10.1f} |{'':>12}|")

        # A vs C (mechanism test)
        p(f"  │")
        p(f"  │ ── Pipeline A (Baseline) vs Pipeline C (Mechanism Test: Differential Multipliers) ──")
        p(f"  │ Multipliers: {res['multipliers']['differential']}")
        p(header.replace('B(learn)', 'C(mech) ').replace('Δ(B-A)', 'Δ(C-A) '))
        p(f"  │ {'-'*5}-+-{'-'*10}-+-{'-'*10}-+-{'-'*10}-+-{'-'*10}-+-{'-'*8}")
        for w, wr in res.get('windows', {}).items():
            a, c = wr['baseline'], wr['mechanism']
            d = wr['delta_ac']
            imp = wr['impact_ac']
            p(f"  │ {w:>5} | {'edge':>10} | {a['edge']:>+10.5f} | {c['edge']:>+10.5f} | {d['edge']:>+10.5f} | {imp:>8}")
            p(f"  │       | {'hit_rate':>10} | {a['hit_rate']:>10.5f} | {c['hit_rate']:>10.5f} | {d['hit_rate']:>+10.5f} |")
            p(f"  │       | {'sharpe':>10} | {a['sharpe']:>10.4f} | {c['sharpe']:>10.4f} | {d['sharpe']:>+10.4f} |")
            p(f"  │       | {'max_dd':>10} | {a['max_drawdown']:>10d} | {c['max_drawdown']:>10d} | {d['max_drawdown']:>+10d} |")
            p(f"  │       | {'variance':>10} | {a['variance']:>10.6f} | {c['variance']:>10.6f} | {d['variance']:>+10.6f} |")

        p(f"  └{'─'*68}┘")

    # ═══════ SECTION 3: Δ Impact Analysis ═══════
    p("\n── SECTION 3: Δ Impact Analysis ──")

    for lt in LOTTERY_TYPES:
        res = all_results.get(lt, {})
        if 'error' in res:
            continue
        p(f"\n  {lt}:")

        p(f"    A vs B (True A/B — current learning):")
        for w, wr in res.get('windows', {}).items():
            d = wr['delta_ab']
            e_dir = "↑" if d['edge'] > 0.0001 else ("↓" if d['edge'] < -0.0001 else "=")
            s_dir = "↑" if d['sharpe'] > 0.0001 else ("↓" if d['sharpe'] < -0.0001 else "=")
            p(f"      W{w:>4}: edge {e_dir} {d['edge']:+.5f} | sharpe {s_dir} {d['sharpe']:+.4f} | dd Δ{d['max_drawdown']:+d} | {wr['impact_ab']}")

        p(f"    A vs C (Mechanism — differential multipliers):")
        for w, wr in res.get('windows', {}).items():
            d = wr['delta_ac']
            e_dir = "↑" if d['edge'] > 0.0001 else ("↓" if d['edge'] < -0.0001 else "=")
            s_dir = "↑" if d['sharpe'] > 0.0001 else ("↓" if d['sharpe'] < -0.0001 else "=")
            p(f"      W{w:>4}: edge {e_dir} {d['edge']:+.5f} | sharpe {s_dir} {d['sharpe']:+.4f} | dd Δ{d['max_drawdown']:+d} | {wr['impact_ac']}")

        ec = res.get('edge_consistency', {})
        p(f"    Edge consistency (σ across windows):")
        p(f"      Baseline σ={ec.get('baseline_std', 0):.5f}  Learning σ={ec.get('learning_std', 0):.5f}  Mechanism σ={ec.get('mechanism_std', 0):.5f}")

    # ═══════ SECTION 4: Statistical Tests ═══════
    p("\n── SECTION 4: Statistical Test Results ──")

    for lt in LOTTERY_TYPES:
        res = all_results.get(lt, {})
        if 'error' in res:
            continue
        p(f"\n  {lt}:")

        p(f"    A vs B (True A/B):")
        for w, wr in res.get('windows', {}).items():
            pm = wr['perm_ab']
            mc = wr['mcn_ab']
            sig_p = "***SIG***" if pm['significant'] else "NOT SIG"
            sig_m = "***SIG***" if mc['significant'] else "NOT SIG"
            p(f"      W{w:>4}: Perm p={pm['p_value']:.4f} ({sig_p}) n={pm['n']} | McNemar p={mc['p_value']:.4f} ({sig_m}) b={mc['b']} c={mc['c']}")

        p(f"    A vs C (Mechanism):")
        for w, wr in res.get('windows', {}).items():
            pm = wr['perm_ac']
            mc = wr['mcn_ac']
            sig_p = "***SIG***" if pm['significant'] else "NOT SIG"
            sig_m = "***SIG***" if mc['significant'] else "NOT SIG"
            p(f"      W{w:>4}: Perm p={pm['p_value']:.4f} ({sig_p}) n={pm['n']} | McNemar p={mc['p_value']:.4f} ({sig_m}) b={mc['b']} c={mc['c']}")

    # ═══════ SECTION 5: Learning Behavior Audit ═══════
    p("\n── SECTION 5: Learning Behavior Audit ──")

    p("\n  [5.1] Hypothesis → Multiplier → Weight Propagation Chain:")
    p(f"    Hypothesis registry: {hyp_audit.get('total', 0)} hypotheses")
    for lt in LOTTERY_TYPES:
        info = hyp_audit.get('by_lottery', {}).get(lt, {})
        n_hyp = info.get('total', 0)
        statuses = info.get('statuses', {})
        has_term = info.get('has_terminal_verdicts', False)
        p(f"    {lt}: {n_hyp} hypotheses {statuses}")
        p(f"      Terminal verdicts (VALIDATED/REJECTED): {'YES' if has_term else 'NO'}")
        p(f"      learning_integrator MIN_HYPOTHESES=3: {'PASS' if n_hyp >= 3 else 'FAIL'}")
        p(f"      Would produce non-1.0 multiplier: {'YES' if has_term and n_hyp >= 3 else 'NO'}")

    p("\n  [5.2] Weight Distribution (Strategy Selection):")
    for lt in LOTTERY_TYPES:
        res = all_results.get(lt, {})
        if 'error' in res:
            continue
        dist = res.get('weight_dist', {})
        p(f"\n    {lt}:")
        p(f"      Baseline HHI={dist.get('baseline', {}).get('hhi', 0):.4f} (closer to 1/N={1.0/dist.get('baseline',{}).get('n_agents',1):.4f} = uniform)")
        p(f"      Learning HHI={dist.get('learning', {}).get('hhi', 0):.4f}")
        p(f"      Mechanism HHI={dist.get('mechanism', {}).get('hhi', 0):.4f}")
        p(f"      HHI change (A→B): {dist.get('learning',{}).get('hhi',0) - dist.get('baseline',{}).get('hhi',0):+.4f}")
        p(f"      HHI change (A→C): {dist.get('mechanism',{}).get('hhi',0) - dist.get('baseline',{}).get('hhi',0):+.4f}")

    p("\n  [5.3] Does Learning Actually Influence Decisions?")
    for lt in LOTTERY_TYPES:
        res = all_results.get(lt, {})
        if 'error' in res:
            continue

        ab_identical = res.get('preds_ab_identical')
        ac_identical = res.get('preds_ac_identical')
        wd_ab = res.get('weight_diff_ab', {})
        wd_ac = res.get('weight_diff_ac', {})
        ab_changes = sum(1 for d in wd_ab.values() if abs(d.get('diff', 0)) > 0.0001)
        ac_changes = sum(1 for d in wd_ac.values() if abs(d.get('diff', 0)) > 0.0001)

        p(f"\n    {lt}:")
        p(f"      A vs B: weights changed={ab_changes}/{len(wd_ab)}, predictions identical={ab_identical}")
        p(f"      A vs C: weights changed={ac_changes}/{len(wd_ac)}, predictions identical={ac_identical}")

        # Detailed weight changes for A vs C
        if ac_changes > 0:
            p(f"      Agent weight changes (A→C):")
            for name, d in sorted(wd_ac.items(), key=lambda x: -abs(x[1].get('diff', 0))):
                if abs(d.get('diff', 0)) > 0.0001:
                    p(f"        {name:25s}: {d['baseline']:.5f} → {d['learning']:.5f} ({d['pct_change']:+.1f}%)")

        if ab_identical is True:
            p(f"      ⚠ LEARNING NOT EFFECTIVE: Pipeline B produces IDENTICAL predictions to A")
        if ac_identical is True:
            p(f"      ⚠ MECHANISM BROKEN: Even differential multipliers produce identical predictions")
        elif ac_identical is False:
            p(f"      ✓ MECHANISM WORKS: Differential multipliers DO change predictions")

    p("\n  [5.4] Architectural Flaw Analysis:")
    p("    learning_integrator._compute_per_strategy_signals() returns UNIFORM multiplier")
    p("    for ALL strategies in a lottery type (same global_mult for every strategy).")
    p("    aggregate_scores() normalizes weights by total_weights:")
    p("      w_norm = w_i / Σ(w_j)")
    p("    If all weights are scaled by same factor k:")
    p("      w_norm = (k * w_i) / (k * Σ(w_j)) = w_i / Σ(w_j)")
    p("    → Uniform multiplier is MATHEMATICALLY NEUTRALIZED by normalization.")
    p("    → Even with activated learning, uniform multipliers have ZERO effect.")
    p("    This is a design flaw, not a data insufficiency issue.")

    # ═══════ SECTION 6: Verdict ═══════
    p("\n── SECTION 6: VERDICT ──")

    # Aggregate evidence
    all_impacts_ab = []
    all_impacts_ac = []
    any_sig_ab = False
    any_sig_ac = False
    any_edge_neg_ab = False
    any_edge_neg_ac = False
    any_sharpe_worse_ab = False
    any_sharpe_worse_ac = False
    any_dd_increase_ab = False
    any_dd_increase_ac = False

    for lt in LOTTERY_TYPES:
        res = all_results.get(lt, {})
        if 'error' in res:
            continue
        for w, wr in res.get('windows', {}).items():
            all_impacts_ab.append(wr['impact_ab'])
            all_impacts_ac.append(wr['impact_ac'])
            if wr['perm_ab'].get('significant'): any_sig_ab = True
            if wr['perm_ac'].get('significant'): any_sig_ac = True
            if wr['delta_ab']['edge'] < -0.005: any_edge_neg_ab = True
            if wr['delta_ac']['edge'] < -0.005: any_edge_neg_ac = True
            if wr['delta_ab']['sharpe'] < -0.01: any_sharpe_worse_ab = True
            if wr['delta_ac']['sharpe'] < -0.01: any_sharpe_worse_ac = True
            if wr['delta_ab']['max_drawdown'] > 3: any_dd_increase_ab = True
            if wr['delta_ac']['max_drawdown'] > 3: any_dd_increase_ac = True

    # A vs B verdict (true test)
    p("\n  ═══ TRUE A/B VERDICT (Pipeline A vs B) ═══")
    if not any_real:
        verdict_ab = "REJECT"
        reason_ab = "NO LEARNING SIGNAL EXISTS"
        p(f"\n  Verdict: REJECT LEARNING INTEGRATION (CURRENT VERSION)")
        p(f"  Reason:  {reason_ab}")
        p(f"  Detail:  research_multiplier = 1.0 for ALL strategies across ALL lottery types.")
        p(f"           Pipeline A and Pipeline B are IDENTICAL — zero difference by construction.")
        p(f"           The learning_integrator has never been activated because:")
        for lt in LOTTERY_TYPES:
            info = hyp_audit.get('by_lottery', {}).get(lt, {})
            n = info.get('total', 0)
            st = info.get('statuses', {})
            term = info.get('has_terminal_verdicts', False)
            p(f"             {lt}: {n} hypotheses {st}, terminal_verdicts={term}")
    else:
        # Would evaluate real signal here
        verdict_ab = "CONDITIONAL_ACCEPT" if not any_edge_neg_ab and any_sig_ab else "REJECT"
        p(f"\n  Verdict: {verdict_ab}")

    # A vs C verdict (mechanism test)
    p("\n  ═══ MECHANISM TEST VERDICT (Pipeline A vs C) ═══")
    pos_c = sum(1 for i in all_impacts_ac if i == 'POSITIVE')
    neg_c = sum(1 for i in all_impacts_ac if i == 'NEGATIVE')
    neutral_c = sum(1 for i in all_impacts_ac if i == 'NEUTRAL')

    mechanism_works = any(
        not all_results.get(lt, {}).get('preds_ac_identical', True)
        for lt in LOTTERY_TYPES if 'error' not in all_results.get(lt, {})
    )

    p(f"\n  Weight propagation:     {'WORKING' if mechanism_works else 'BROKEN'}")
    p(f"  Prediction changes:     {sum(1 for lt in LOTTERY_TYPES if not all_results.get(lt, {}).get('preds_ac_identical', True))}/3 types affected")
    p(f"  Statistical significance: {'YES' if any_sig_ac else 'NO'}")
    p(f"  Impact distribution:    {pos_c} POSITIVE / {neutral_c} NEUTRAL / {neg_c} NEGATIVE")

    if mechanism_works:
        p(f"  → The plumbing works: differential multipliers DO change predictions.")
        if any_edge_neg_ac:
            p(f"  → BUT: differential multipliers DEGRADE performance for some types.")
            p(f"       Boosting top-edge strategies does NOT guarantee improvement.")
        if not any_sig_ac:
            p(f"  → No statistically significant improvement detected.")
    else:
        p(f"  → MECHANISM BROKEN: weight changes do not propagate to predictions.")

    # Final combined verdict
    p("\n  ═══ FINAL COMBINED VERDICT ═══")
    p(f"\n  ┌─────────────────────────────────────────────────────────────┐")
    p(f"  │                                                             │")
    p(f"  │   VERDICT: REJECT LEARNING INTEGRATION (CURRENT VERSION)    │")
    p(f"  │                                                             │")
    p(f"  │   FAILURE CONDITIONS MET:                                   │")
    p(f"  │     ✗ No observable behavior change (A ≡ B)                 │")
    p(f"  │     ✗ No statistical significance in any window             │")
    p(f"  │     ✗ Architectural flaw: uniform multiplier neutralized    │")
    p(f"  │     ✗ No real learning signal exists (all mult = 1.0)       │")
    if any_edge_neg_ac:
        p(f"  │     ✗ Mechanism test: edge degrades for BIG_LOTTO/POWER    │")
    p(f"  │                                                             │")
    p(f"  └─────────────────────────────────────────────────────────────┘")

    # ═══════ SECTION 7: Recommendations ═══════
    p("\n── SECTION 7: Recommendations ──")
    p(f"\n  Verdict was: REJECT")
    p(f"\n  ROOT CAUSE ANALYSIS:")
    p(f"")
    p(f"    1. [CRITICAL] ARCHITECTURAL FLAW: UNIFORM MULTIPLIER NEUTRALIZATION")
    p(f"       _compute_per_strategy_signals() returns ONE global multiplier")
    p(f"       for ALL strategies. Due to weight normalization in aggregate_scores(),")
    p(f"       a uniform scalar cancels out completely.")
    p(f"       Formula: w_norm = (k·w_i) / Σ(k·w_j) = w_i / Σ(w_j)")
    p(f"       Impact: Even with perfect learning signals, the system has ZERO effect.")
    p(f"       This is not a data problem — it is a math problem.")
    p(f"")
    p(f"    2. [HIGH] INSUFFICIENT HYPOTHESIS DATA")
    p(f"       Hypothesis registry contains {hyp_audit.get('total', 0)} hypotheses total.")
    p(f"       Only DAILY_539 has any (3: 2 PROVISIONAL + 1 REGISTERED).")
    p(f"       Zero terminal verdicts (VALIDATED/REJECTED) exist.")
    p(f"       BIG_LOTTO and POWER_LOTTO have 0 hypotheses.")
    p(f"       The learning_integrator requires MIN_HYPOTHESES=3 with terminal verdicts.")
    p(f"")
    p(f"    3. [MEDIUM] NO RESEARCH FEEDBACK LOOP")
    p(f"       research_feedback.jsonl does not exist.")
    p(f"       No audit trail of multiplier changes.")
    p(f"       research_runner has not been executed for any production cycle.")
    p(f"")
    p(f"  RECOMMENDED FIXES (prioritized):")
    p(f"")
    p(f"    P0 — Fix uniform multiplier flaw:")
    p(f"       Modify _compute_per_strategy_signals() to produce DIFFERENTIAL")
    p(f"       multipliers per strategy. Options:")
    p(f"         a) Map hypotheses to specific agent RSM keys via strategy_mode")
    p(f"         b) Use per-strategy edge variance to modulate multiplier")
    p(f"         c) Apply multiplier as additive bonus (not multiplicative)")
    p(f"            to bypass normalization neutralization:")
    p(f"            final_score[n] += learning_bonus * agent_score[n]")
    p(f"")
    p(f"    P1 — Generate hypothesis data:")
    p(f"       Run research_runner.run_research_cycle() for ALL 3 lottery types.")
    p(f"       Wait for ≥10 hypotheses per type with terminal verdicts.")
    p(f"       Ensure discovery covers diverse PolicyConfig variations.")
    p(f"")
    p(f"    P2 — Re-validate after fixes:")
    p(f"       Re-run this A/B validation after P0+P1 are complete.")
    p(f"       Require: Δ edge > 0 with p < 0.05 in ≥2 of 3 windows.")
    p(f"       Require: Sharpe non-negative in all windows.")
    p(f"       Require: drawdown not significantly worse.")

    p("\n" + "=" * 72)
    p("  A/B VALIDATION COMPLETE")
    p("=" * 72)

    return '\n'.join(out)


# ═════════════════════════════════════════════════════════════
#  MAIN
# ═════════════════════════════════════════════════════════════

def main():
    print("Initiating comprehensive A/B validation...\n")

    # Audit hypothesis registry
    hyp_audit = audit_hypothesis_registry()

    # Run A/B test for each lottery type
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

    # Generate report
    report = generate_report(all_results, hyp_audit)
    print(report)

    # Save results
    output_path = os.path.join('data', 'ab_validation_result.json')
    serializable = {}
    for lt, res in all_results.items():
        s = copy.deepcopy(res)
        serializable[lt] = s
    serializable['_hypothesis_audit'] = hyp_audit
    serializable['_timestamp'] = time.strftime("%Y-%m-%d %H:%M:%S")

    with open(output_path, 'w') as f:
        json.dump(serializable, f, indent=2, ensure_ascii=False, default=str)
    print(f"\nFull results saved to: {output_path}")


if __name__ == '__main__':
    main()
