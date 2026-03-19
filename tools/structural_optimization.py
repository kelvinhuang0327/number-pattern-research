#!/usr/bin/env python3
"""
Structural Optimization Research Engine
========================================
2026-03-15 | Beyond signal ceiling: structural, combinatorial, game-theoretic

6 Research Directions:
  1. Bet Portfolio Optimization (2/3/4/5-bet)
  2. Coverage Matrix Optimization (Mandel-style)
  3. Anti-Crowd Strategy Research
  4. Cross-Lottery Signal Transfer
  5. Capital Allocation Research (Kelly)
  6. Game Structure Exploitation (EV, jackpots)
"""
import sys, os, json, time, math
import numpy as np
from collections import Counter
from itertools import combinations

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

SEED = 20260315
np.random.seed(SEED)
rng = np.random.default_rng(SEED)

# Game constants
GAMES = {
    'DAILY_539': {
        'max_num': 39, 'pick': 5, 'has_special': False,
        'cost': 50, 'match_threshold': 2,
        'p_single': 0.1140,  # M2+ for 5-from-39
        'prizes': {2: 300, 3: 2000, 4: 20000, 5: 8_000_000},
    },
    'BIG_LOTTO': {
        'max_num': 49, 'pick': 6, 'has_special': True, 'special_range': 49,
        'cost': 50, 'match_threshold': 3,
        'p_single': 0.0186,  # M3+ for 6-from-49
        'prizes': {3: 400, 4: 1000, 5: 20000, 6: 500_000},
    },
    'POWER_LOTTO': {
        'max_num': 38, 'pick': 6, 'has_special': True, 'special_range': 8,
        'cost': 100, 'match_threshold': 3,
        'p_single': 0.0387,  # M3+ for 6-from-38
        'prizes': {3: 100, 4: 800, 5: 20000, 6: 4_000_000},
    },
}


def load_draws(lottery_type):
    from database import DatabaseManager
    db = DatabaseManager(os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    draws = sorted(db.get_all_draws(lottery_type), key=lambda x: (x['date'], x['draw']))
    pick = GAMES[lottery_type]['pick']
    draws = [d for d in draws if d.get('numbers') and len(d['numbers']) >= pick]
    return draws


# ============================================================
# Shared scoring functions (parameterized by game)
# ============================================================

def acb_scores(history, max_num, pick, window=100):
    recent = history[-window:] if len(history) >= window else history
    counter = Counter()
    for n in range(1, max_num + 1):
        counter[n] = 0
    for d in recent:
        for n in d['numbers'][:pick]:
            if 1 <= n <= max_num:
                counter[n] += 1
    last_seen = {}
    for i, d in enumerate(recent):
        for n in d['numbers'][:pick]:
            if 1 <= n <= max_num:
                last_seen[n] = i
    expected = len(recent) * pick / max_num
    scores = {}
    for n in range(1, max_num + 1):
        fd = expected - counter[n]
        gs = (len(recent) - last_seen.get(n, -1)) / max(len(recent) / 2, 1)
        bb = 1.2 if (n <= max(8, max_num // 5) or n >= max_num - max(4, max_num // 10)) else 1.0
        scores[n] = (fd * 0.4 + gs * 0.6) * bb
    return scores


def midfreq_scores(history, max_num, pick, window=100):
    recent = history[-window:] if len(history) >= window else history
    freq = Counter()
    for n in range(1, max_num + 1):
        freq[n] = 0
    for d in recent:
        for n in d['numbers'][:pick]:
            if 1 <= n <= max_num:
                freq[n] += 1
    expected = len(recent) * pick / max_num
    max_dist = max(abs(freq[n] - expected) for n in range(1, max_num + 1))
    if max_dist < 1e-9:
        max_dist = 1.0
    scores = {}
    for n in range(1, max_num + 1):
        scores[n] = max_dist - abs(freq[n] - expected)
    return scores


def markov_scores(history, max_num, pick, window=30):
    recent = history[-window:] if len(history) >= window else history
    transitions = {}
    for i in range(len(recent) - 1):
        for pn in recent[i]['numbers'][:pick]:
            if pn > max_num:
                continue
            if pn not in transitions:
                transitions[pn] = Counter()
            for nn in recent[i + 1]['numbers'][:pick]:
                if 1 <= nn <= max_num:
                    transitions[pn][nn] += 1
    scores = Counter()
    for pn in history[-1]['numbers'][:pick]:
        if pn > max_num:
            continue
        trans = transitions.get(pn, Counter())
        total = sum(trans.values())
        if total > 0:
            for nn, cnt in trans.items():
                scores[nn] += cnt / total
    for n in range(1, max_num + 1):
        if n not in scores:
            scores[n] = 0.0
    return dict(scores)


def pick_top(scores_dict, exclude, count):
    ranked = sorted(scores_dict, key=lambda x: -scores_dict[x])
    out = []
    for n in ranked:
        if n in exclude:
            continue
        out.append(n)
        if len(out) >= count:
            break
    return sorted(out)


def check_hit(bets, actual, threshold):
    actual_set = set(actual)
    return any(len(set(b) & actual_set) >= threshold for b in bets)


# ============================================================
# Direction 1: Bet Portfolio Optimization
# ============================================================

def direction1_portfolio(draws_539):
    print("\n" + "=" * 72)
    print("  DIRECTION 1: Bet Portfolio Optimization")
    print("  539 — Optimal 2/3/4/5-bet portfolios")
    print("=" * 72)

    game = GAMES['DAILY_539']
    T = len(draws_539)
    tp = min(1500, T - 300)
    eval_start = T - tp

    # Load MicroFish genome
    vpath = os.path.join(project_root, 'validated_strategy_set.json')
    with open(vpath) as fp:
        vdata = json.load(fp)
    genome = vdata['valid'][0]

    # Build feature matrix for MicroFish
    print("  Building MicroFish feature matrix...")
    from tools.microfish_engine import build_feature_matrix
    F, feature_names, hit_mat = build_feature_matrix(draws_539)
    fi = np.array([feature_names.index(f) for f in genome['features']])
    w_genome = np.array(genome['weights'])

    # Strategy scoring functions
    def _mf_scores(t):
        scores_vec = F[t, :, :][:, fi].dot(w_genome)  # [39]
        return {n + 1: float(scores_vec[n]) for n in range(game['max_num'])}

    # Test all portfolio configurations
    strategies = ['MicroFish', 'MidFreq', 'ACB', 'Markov']

    def _get_all_scores(hist, t):
        return {
            'MicroFish': _mf_scores(t),
            'MidFreq': midfreq_scores(hist, game['max_num'], game['pick']),
            'ACB': acb_scores(hist, game['max_num'], game['pick']),
            'Markov': markov_scores(hist, game['max_num'], game['pick']),
        }

    # Portfolio configs to test
    configs = {
        # 1-bet
        '1bet_MF': ['MicroFish'],
        '1bet_ACB': ['ACB'],
        '1bet_MidFreq': ['MidFreq'],
        # 2-bet
        '2bet_MF_MidFreq': ['MicroFish', 'MidFreq'],
        '2bet_MF_ACB': ['MicroFish', 'ACB'],
        '2bet_MF_Markov': ['MicroFish', 'Markov'],
        '2bet_ACB_MidFreq': ['ACB', 'MidFreq'],
        '2bet_ACB_Markov': ['ACB', 'Markov'],
        # 3-bet
        '3bet_MF_MidFreq_ACB': ['MicroFish', 'MidFreq', 'ACB'],
        '3bet_MF_MidFreq_Markov': ['MicroFish', 'MidFreq', 'Markov'],
        '3bet_MF_ACB_Markov': ['MicroFish', 'ACB', 'Markov'],
        '3bet_ACB_MidFreq_Markov': ['ACB', 'MidFreq', 'Markov'],
        # 4-bet
        '4bet_all': ['MicroFish', 'MidFreq', 'ACB', 'Markov'],
        # 5-bet: 4 strategies + RRF consensus
        '5bet_all_rrf': ['MicroFish', 'MidFreq', 'ACB', 'Markov', 'RRF'],
    }

    results = {}

    for config_name, strat_list in configs.items():
        n_bets = len(strat_list)
        baseline = 1 - (1 - game['p_single']) ** n_bets
        hits = 0
        details = []

        for i in range(tp):
            t = eval_start + i
            hist = draws_539[:t]
            actual = draws_539[t]['numbers'][:game['pick']]
            all_sc = _get_all_scores(hist, t)

            # Build orthogonal bets
            bets = []
            used = set()
            for s in strat_list:
                if s == 'RRF':
                    # Reciprocal rank fusion
                    rrf = Counter()
                    for m in ['MicroFish', 'MidFreq', 'ACB', 'Markov']:
                        ranked = sorted(all_sc[m], key=lambda x: -all_sc[m][x])
                        for rank, n in enumerate(ranked):
                            rrf[n] += 1.0 / (60 + rank + 1)
                    sc = dict(rrf)
                else:
                    sc = all_sc[s]
                bet = pick_top(sc, used, game['pick'])
                bets.append(bet)
                used.update(bet)

            h = check_hit(bets, actual, game['match_threshold'])
            details.append(1 if h else 0)
            if h:
                hits += 1

        rate = hits / tp
        edge = rate - baseline
        se = np.sqrt(baseline * (1 - baseline) / tp) if tp > 0 else 1
        z = edge / se if se > 0 else 0

        # Three-window check
        windows = {}
        for ww in [150, 500, 1500]:
            wp = min(ww, tp)
            r = sum(details[-wp:]) / wp
            windows[str(ww)] = (r - baseline) * 100

        results[config_name] = {
            'n_bets': n_bets, 'rate': rate, 'edge_pct': edge * 100,
            'baseline': baseline, 'z': z, 'cost': n_bets * game['cost'],
            'edge_per_NTD': edge * 100 / (n_bets * game['cost']),
            'windows': windows,
        }

    # Print results sorted by n_bets then edge
    print(f"\n  {'Config':<30} {'N':>3} {'Rate':>8} {'Edge':>8} {'z':>6} "
          f"{'E/NTD':>8} {'150p':>8} {'500p':>8} {'1500p':>8}")
    print(f"  {'-'*30} {'-'*3} {'-'*8} {'-'*8} {'-'*6} {'-'*8} {'-'*8} {'-'*8} {'-'*8}")

    for name in sorted(results, key=lambda n: (results[n]['n_bets'], -results[n]['edge_pct'])):
        r = results[name]
        w = r['windows']
        print(f"  {name:<30} {r['n_bets']:>3} {r['rate']*100:>7.2f}% "
              f"{r['edge_pct']:>+7.2f}% {r['z']:>5.2f} {r['edge_per_NTD']:>7.4f} "
              f"{w['150']:>+7.2f}% {w['500']:>+7.2f}% {w['1500']:>+7.2f}%")

    # Marginal utility
    print(f"\n  === Marginal Utility per Extra Bet ===")
    best_by_n = {}
    for name, r in results.items():
        n = r['n_bets']
        if n not in best_by_n or r['edge_pct'] > best_by_n[n]['edge_pct']:
            best_by_n[n] = {**r, 'name': name}

    prev_edge = 0
    for n in sorted(best_by_n):
        b = best_by_n[n]
        marginal = b['edge_pct'] - prev_edge
        print(f"  {n}-bet best ({b['name']}): edge={b['edge_pct']:+.2f}%, "
              f"marginal={marginal:+.2f}%, E/NTD={b['edge_per_NTD']:.4f}")
        prev_edge = b['edge_pct']

    return results


# ============================================================
# Direction 2: Coverage Matrix Optimization
# ============================================================

def direction2_coverage():
    print("\n" + "=" * 72)
    print("  DIRECTION 2: Coverage Matrix Optimization (Mandel-style)")
    print("=" * 72)

    coverage_results = {}

    for game_name, game in GAMES.items():
        max_num = game['max_num']
        pick = game['pick']
        total_combos = math.comb(max_num, pick)
        cost_per_bet = game['cost']

        print(f"\n  --- {game_name} ---")
        print(f"  Total combinations: C({max_num},{pick}) = {total_combos:,}")
        print(f"  Cost to cover all: NTD {total_combos * cost_per_bet:,}")

        # Compute coverage probabilities for N bets
        p_single = game['p_single']
        threshold = game['match_threshold']

        # Exact M_threshold+ probability for a single random bet
        # P(M>=k) = sum_{j=k}^{pick} C(pick,j)*C(max_num-pick, pick-j) / C(max_num, pick)
        p_exact = 0
        for j in range(threshold, pick + 1):
            p_exact += math.comb(pick, j) * math.comb(max_num - pick, pick - j)
        p_exact /= total_combos

        print(f"  Exact P(M{threshold}+, 1 bet) = {p_exact:.6f} ({p_exact*100:.4f}%)")
        print(f"  Stored P_SINGLE = {p_single:.4f}")

        # N-bet coverage (independent bets)
        print(f"\n  Random N-bet coverage:")
        for n in [1, 2, 3, 5, 10, 20, 50]:
            p_n = 1 - (1 - p_exact) ** n
            cost = n * cost_per_bet
            prizes = game['prizes']
            ev_per_bet = sum(prizes.get(m, 0) * math.comb(pick, m) * math.comb(max_num - pick, pick - m) / total_combos
                           for m in prizes)
            ev_n = n * ev_per_bet
            roi = (ev_n / cost - 1) * 100 if cost > 0 else 0
            print(f"    N={n:>3}: P(hit)={p_n*100:>7.3f}%, cost={cost:>6,} NTD, "
                  f"EV={ev_n:>8.1f} NTD, ROI={roi:>+7.2f}%")

        # Partial coverage analysis — how many bets to guarantee M_threshold+ with probability p?
        print(f"\n  Bets needed for coverage guarantee:")
        for target_p in [0.50, 0.75, 0.90, 0.95, 0.99]:
            n_needed = math.ceil(math.log(1 - target_p) / math.log(1 - p_exact))
            cost = n_needed * cost_per_bet
            print(f"    P≥{target_p*100:.0f}%: N={n_needed:>6,} bets, cost={cost:>10,} NTD")

        # Wheeling system analysis
        # A k-coverage wheel: every possible subset of k numbers from a pool is "covered"
        # For 539: if we have a pool of 10 numbers, C(10,5) = 252 bets covers all 5-subsets
        print(f"\n  Wheeling systems (pool → bets):")
        for pool_size in range(pick + 1, min(pick + 8, max_num + 1)):
            wheel_bets = math.comb(pool_size, pick)
            wheel_cost = wheel_bets * cost_per_bet
            # Probability that all drawn numbers fall in pool
            p_pool = math.comb(pool_size, pick) / total_combos
            # If all drawn in pool, we guaranteed M=pick (jackpot)
            # P(M>=threshold | pool): more complex but at minimum p_pool guarantees full coverage
            # P(at least 'threshold' numbers in pool)
            p_at_least_k = sum(
                math.comb(pool_size, j) * math.comb(max_num - pool_size, pick - j)
                for j in range(threshold, min(pick, pool_size) + 1)
            ) / total_combos

            print(f"    Pool={pool_size:>2}: {wheel_bets:>5} bets, cost={wheel_cost:>8,} NTD, "
                  f"P(≥{threshold} in pool)={p_at_least_k*100:.2f}%")

        coverage_results[game_name] = {
            'total_combos': total_combos,
            'p_exact': p_exact,
            'ev_per_bet': ev_per_bet if 'ev_per_bet' in dir() else 0,
        }

    return coverage_results


# ============================================================
# Direction 3: Anti-Crowd Strategy
# ============================================================

def direction3_anticrowd():
    print("\n" + "=" * 72)
    print("  DIRECTION 3: Anti-Crowd Strategy Research")
    print("  Reducing prize splitting risk through number uniqueness")
    print("=" * 72)

    results = {}

    # Analyze number popularity patterns
    # Birthday numbers: 1-31 are overrepresented (dates)
    # Lucky numbers: 7, 8 (Chinese culture)
    # Round numbers: multiples of 5, 10
    # Edges: 1, last number
    # Patterns: 1-2-3-4-5, 5-10-15-20-25, etc.

    print(f"\n  === Popularity Model (theoretical) ===")
    print(f"  Based on known behavioral biases in lottery number selection:")

    popularity_model = {}

    for game_name, game in GAMES.items():
        max_num = game['max_num']
        pop = np.ones(max_num + 1)  # 1-indexed
        pop[0] = 0

        # Birthday bias: numbers 1-31 more popular
        for n in range(1, min(32, max_num + 1)):
            pop[n] *= 1.3

        # Month bias: 1-12 even more popular
        for n in range(1, min(13, max_num + 1)):
            pop[n] *= 1.1

        # Lucky numbers (Chinese culture)
        for n in [7, 8, 9, 18, 28, 38]:
            if n <= max_num:
                pop[n] *= 1.15

        # Round numbers
        for n in range(5, max_num + 1, 5):
            pop[n] *= 1.05

        # Unlucky 4 (Chinese culture)
        for n in [4, 14, 24, 34, 44]:
            if n <= max_num:
                pop[n] *= 0.9

        # High numbers less popular (birthday effect)
        for n in range(32, max_num + 1):
            pop[n] *= 0.85

        # Normalize
        pop = pop / pop[1:].sum() * max_num  # relative to uniform = 1.0

        popularity_model[game_name] = pop

        # Anti-crowd: prefer numbers with low popularity
        anti_crowd_nums = sorted(range(1, max_num + 1), key=lambda n: pop[n])
        popular_nums = sorted(range(1, max_num + 1), key=lambda n: -pop[n])

        print(f"\n  {game_name} (1-{max_num}):")
        print(f"  Most popular (crowd favorites):   {popular_nums[:10]}")
        print(f"  Least popular (anti-crowd):        {anti_crowd_nums[:10]}")
        print(f"  Popularity range: {pop[1:].min():.3f} — {pop[1:].max():.3f}")

    # For 539 specifically: quantify split risk impact
    print(f"\n  === Split Risk Analysis (539) ===")
    game = GAMES['DAILY_539']
    pop = popularity_model['DAILY_539']

    # If you hit M5 (jackpot), expected number of other winners depends on
    # how "popular" your ticket is
    # More popular ticket → more likely others have it too → more splitting

    # Simulate: if N_total players, and popularity model gives P(ticket),
    # expected co-winners = N_total * P(specific_ticket)

    # For 539: C(39,5) = 575,757 possible tickets
    total_tickets_539 = math.comb(39, 5)

    # Estimate total bets per draw (rough: 539 has ~NTD 40M sales per draw at NTD 50 each)
    estimated_bets_per_draw = 800_000  # ~40M / 50

    # Under uniform selection, P(anyone else has same ticket) = (N-1) * 1/C(39,5)
    p_same_uniform = (estimated_bets_per_draw - 1) / total_tickets_539
    print(f"  Total tickets 539: {total_tickets_539:,}")
    print(f"  Estimated bets/draw: {estimated_bets_per_draw:,}")
    print(f"  P(co-winner | uniform): {p_same_uniform:.4f}")

    # Under biased selection, popular tickets have higher P(same)
    # If a ticket's popularity weight = w, then P(same) ≈ w * (N-1) / C
    # For anti-crowd pick: use least popular numbers
    anti_pick = sorted(range(1, 40), key=lambda n: pop[n])[:5]
    anti_weight = np.prod([pop[n] for n in anti_pick])
    crowd_pick = sorted(range(1, 40), key=lambda n: -pop[n])[:5]
    crowd_weight = np.prod([pop[n] for n in crowd_pick])

    ratio = crowd_weight / max(anti_weight, 1e-10)

    print(f"\n  Anti-crowd pick: {sorted(anti_pick)} (weight={anti_weight:.4f})")
    print(f"  Crowd-favorite pick: {sorted(crowd_pick)} (weight={crowd_weight:.4f})")
    print(f"  Crowd/Anti-crowd ratio: {ratio:.2f}x")
    print(f"  Expected jackpot splitting if anti-crowd: ~{1/(1+p_same_uniform*anti_weight/crowd_weight*ratio):.1%} of pot")
    print(f"  Expected jackpot splitting if crowd:      ~{1/(1+p_same_uniform*ratio):.1%} of pot")

    # Impact on EV
    base_jackpot = 8_000_000
    ev_anticrowd = base_jackpot * 1 / (1 + p_same_uniform * anti_weight)
    ev_crowd = base_jackpot * 1 / (1 + p_same_uniform * crowd_weight)
    print(f"\n  Expected jackpot value:")
    print(f"    Anti-crowd: NTD {ev_anticrowd:,.0f}")
    print(f"    Crowd:      NTD {ev_crowd:,.0f}")
    print(f"    Difference: NTD {ev_anticrowd - ev_crowd:,.0f}")

    print(f"\n  VERDICT: Split risk is negligible for 539 (fixed M2/M3/M4 prizes).")
    print(f"  Only M5 jackpot is affected, and M5 probability is ~1 in 575,757.")
    print(f"  Anti-crowd has NO impact on practical EV for sub-M5 matches.")

    results['popularity_model'] = {g: pop.tolist() for g, pop in popularity_model.items()}
    results['verdict'] = 'NEGLIGIBLE for fixed-prize games, MARGINAL for jackpot-only games'
    return results


# ============================================================
# Direction 4: Cross-Lottery Signal Transfer
# ============================================================

def direction4_cross_transfer():
    print("\n" + "=" * 72)
    print("  DIRECTION 4: Cross-Lottery Signal Transfer")
    print("  Testing ACB/MidFreq/Markov portability across 539/BL/PL")
    print("=" * 72)

    transfer_results = {}

    for game_name in ['DAILY_539', 'BIG_LOTTO', 'POWER_LOTTO']:
        game = GAMES[game_name]
        draws = load_draws(game_name)
        T = len(draws)
        max_num = game['max_num']
        pick_n = game['pick']
        p_single = game['p_single']
        threshold = game['match_threshold']
        tp = min(1500, T - 200)
        eval_start = T - tp

        if tp < 100:
            print(f"\n  {game_name}: insufficient data ({T} draws)")
            continue

        print(f"\n  --- {game_name} ({T} draws, eval {tp}p) ---")
        print(f"  Rules: pick {pick_n} from {max_num}, M{threshold}+ baseline = {p_single*100:.2f}%")

        strat_results = {}

        for strat_name, score_fn in [
            ('ACB', lambda h: acb_scores(h, max_num, pick_n)),
            ('MidFreq', lambda h: midfreq_scores(h, max_num, pick_n)),
            ('Markov', lambda h: markov_scores(h, max_num, pick_n)),
        ]:
            hits = 0
            total = 0
            details = []

            for i in range(tp):
                t_idx = eval_start + i
                if t_idx < 100:
                    details.append(0)
                    continue
                hist = draws[:t_idx]
                actual = draws[t_idx]['numbers'][:pick_n]
                scores = score_fn(hist)
                bet = pick_top(scores, set(), pick_n)
                h = len(set(bet) & set(actual)) >= threshold
                details.append(1 if h else 0)
                if h:
                    hits += 1
                total += 1

            rate = hits / total if total > 0 else 0
            edge = rate - p_single
            se = np.sqrt(p_single * (1 - p_single) / total) if total > 0 else 1
            z = edge / se if se > 0 else 0

            # Three-window
            windows = {}
            for ww in [150, 500, 1500]:
                wp = min(ww, len(details))
                r = sum(details[-wp:]) / wp if wp > 0 else 0
                windows[str(ww)] = (r - p_single) * 100

            # Permutation test (200 shuffles)
            real_rate = rate
            perm_count = 0
            n_perm = 200
            for p_i in range(n_perm):
                prng = np.random.RandomState(p_i * 7919 + 42)
                idx = list(range(len(details)))
                prng.shuffle(idx)
                shift = prng.randint(0, len(details))
                shifted = details[shift:] + details[:shift]
                sr = sum(shifted) / len(shifted)
                if sr >= real_rate:
                    perm_count += 1
            perm_p = (perm_count + 1) / (n_perm + 1)

            all_pos = all(windows.get(str(w), -1) > 0 for w in [150, 500, 1500])
            status = 'VALIDATED' if edge > 0 and z > 1.96 and all_pos and perm_p < 0.05 else \
                     'WEAK' if edge > 0 else 'REJECTED'

            strat_results[strat_name] = {
                'rate': rate, 'edge_pct': edge * 100, 'z': z,
                'perm_p': perm_p, 'windows': windows,
                'all_positive': all_pos, 'status': status,
            }

            print(f"    {strat_name:<10}: rate={rate*100:.2f}% edge={edge*100:+.2f}% z={z:.2f} "
                  f"perm_p={perm_p:.3f} [{status}]")
            for ww in [150, 500, 1500]:
                w_edge = windows.get(str(ww), 0)
                marker = '+' if w_edge > 0 else '-'
                print(f"      {ww}p: {w_edge:+.2f}% [{marker}]")

        transfer_results[game_name] = strat_results

    # Cross-transfer summary
    print(f"\n  === Transfer Matrix ===")
    print(f"  {'Strategy':<12} {'539':>10} {'BIG_LOTTO':>10} {'POWER_LOTTO':>12}")
    for strat in ['ACB', 'MidFreq', 'Markov']:
        row = f"  {strat:<12}"
        for game in ['DAILY_539', 'BIG_LOTTO', 'POWER_LOTTO']:
            if game in transfer_results and strat in transfer_results[game]:
                s = transfer_results[game][strat]
                row += f" {s['edge_pct']:>+8.2f}%{s['status'][0]}"
            else:
                row += f" {'N/A':>10}"
        print(row)

    return transfer_results


# ============================================================
# Direction 5: Capital Allocation (Kelly)
# ============================================================

def direction5_kelly():
    print("\n" + "=" * 72)
    print("  DIRECTION 5: Capital Allocation Research (Kelly Criterion)")
    print("=" * 72)

    results = {}

    for game_name, game in GAMES.items():
        max_num = game['max_num']
        pick_n = game['pick']
        cost = game['cost']
        prizes = game['prizes']
        p_single = game['p_single']
        total_combos = math.comb(max_num, pick_n)

        print(f"\n  --- {game_name} ---")

        # Compute match probabilities
        match_probs = {}
        for m in range(pick_n + 1):
            p = math.comb(pick_n, m) * math.comb(max_num - pick_n, pick_n - m) / total_combos
            match_probs[m] = p

        # Expected value per bet (random)
        ev_random = sum(prizes.get(m, 0) * match_probs[m] for m in match_probs)
        roi_random = (ev_random / cost - 1) * 100

        print(f"  Match probabilities:")
        for m in range(pick_n + 1):
            prize_str = f"NTD {prizes.get(m, 0):>10,}" if m in prizes else f"{'NTD 0':>14}"
            print(f"    M{m}: P={match_probs[m]:.6f} ({match_probs[m]*100:.4f}%) → {prize_str}")

        print(f"\n  EV per random bet: NTD {ev_random:.2f}")
        print(f"  Cost per bet: NTD {cost}")
        print(f"  ROI (random): {roi_random:+.2f}%")

        # With our edge
        # Assume our edge is p_advantage above random for M_threshold+ hit
        edges = {'conservative': 0.03, 'current': 0.047, 'optimistic': 0.06}

        for edge_name, edge_val in edges.items():
            p_with_edge = p_single + edge_val
            # Simplified: edge increases M_threshold probability proportionally
            # Scale up the lowest match probabilities
            ev_with_edge = ev_random * (p_with_edge / p_single)
            roi_with_edge = (ev_with_edge / cost - 1) * 100

            # Kelly criterion: f* = (bp - q) / b
            # where b = net odds, p = prob of winning, q = 1-p
            # For lottery: b = (EV_payout / cost) - 1 per winning event
            mean_payout_given_hit = ev_with_edge / p_with_edge if p_with_edge > 0 else 0
            b = mean_payout_given_hit / cost  # odds
            p = p_with_edge
            q = 1 - p

            kelly_f = (b * p - q) / b if b > 0 else 0
            kelly_f = max(kelly_f, 0)  # Can't be negative

            print(f"\n  Kelly ({edge_name}, edge={edge_val*100:.1f}%):")
            print(f"    P(hit) = {p_with_edge*100:.2f}%, EV = NTD {ev_with_edge:.2f}, ROI = {roi_with_edge:+.2f}%")
            print(f"    Mean payout given hit: NTD {mean_payout_given_hit:.0f}")
            print(f"    Kelly fraction f* = {kelly_f:.6f} ({kelly_f*100:.4f}%)")

            # Practical interpretation
            if kelly_f > 0:
                for bankroll in [10_000, 50_000, 100_000, 1_000_000]:
                    bet_amount = bankroll * kelly_f
                    n_bets = max(1, int(bet_amount / cost))
                    actual_cost = n_bets * cost
                    print(f"      Bankroll NTD {bankroll:>10,}: Kelly suggests {n_bets:>3} bets "
                          f"(NTD {actual_cost:>6,})")
            else:
                print(f"    Kelly says: DON'T BET (negative edge after costs)")

        # Diminishing returns curve
        print(f"\n  Diminishing returns (marginal edge per additional bet):")
        for n in [1, 2, 3, 4, 5, 10]:
            p_n = 1 - (1 - p_single) ** n
            p_n_plus = 1 - (1 - p_single) ** (n + 1)
            marginal_p = p_n_plus - p_n
            marginal_cost = cost
            print(f"    Bet {n}→{n+1}: ΔP = {marginal_p*100:.4f}%, cost = NTD {marginal_cost}")

        results[game_name] = {
            'ev_random': ev_random,
            'roi_random': roi_random,
            'match_probs': match_probs,
            'kelly_current': kelly_f,
        }

    return results


# ============================================================
# Direction 6: Game Structure Exploitation
# ============================================================

def direction6_game_structure():
    print("\n" + "=" * 72)
    print("  DIRECTION 6: Game Structure Exploitation")
    print("  EV analysis, jackpot dynamics, structural edges")
    print("=" * 72)

    results = {}

    for game_name, game in GAMES.items():
        max_num = game['max_num']
        pick_n = game['pick']
        cost = game['cost']
        prizes = game['prizes']
        total_combos = math.comb(max_num, pick_n)

        draws = load_draws(game_name)
        T = len(draws)

        print(f"\n  --- {game_name} ({T} draws) ---")

        # Base EV analysis
        match_probs = {}
        for m in range(pick_n + 1):
            p = math.comb(pick_n, m) * math.comb(max_num - pick_n, pick_n - m) / total_combos
            match_probs[m] = p

        ev_base = sum(prizes.get(m, 0) * match_probs[m] for m in match_probs)
        roi_base = (ev_base / cost - 1) * 100

        print(f"  Base EV: NTD {ev_base:.2f} (ROI: {roi_base:+.2f}%)")
        print(f"  House edge: {-roi_base:.2f}%")

        # Jackpot rollover analysis
        top_match = max(prizes.keys())
        p_jackpot = match_probs[top_match]
        jackpot_base = prizes[top_match]

        # Expected draws between jackpots
        expected_draws_between = 1 / p_jackpot if p_jackpot > 0 else float('inf')
        print(f"\n  Jackpot analysis:")
        print(f"    P(jackpot) = {p_jackpot:.8f} (1 in {1/p_jackpot:,.0f})")
        print(f"    Expected draws between jackpots: {expected_draws_between:,.0f}")

        # EV breakeven jackpot level
        # At what jackpot size does EV become positive?
        ev_without_jackpot = sum(prizes.get(m, 0) * match_probs[m]
                                for m in match_probs if m != top_match)
        jackpot_needed = (cost - ev_without_jackpot) / match_probs[top_match]
        print(f"    EV without jackpot: NTD {ev_without_jackpot:.2f}")
        print(f"    Jackpot needed for EV breakeven: NTD {jackpot_needed:,.0f}")
        print(f"    Base jackpot: NTD {jackpot_base:,}")
        print(f"    Multiplier needed: {jackpot_needed/jackpot_base:.1f}x")

        # Historical draw sum statistics
        draw_sums = [sum(d['numbers'][:pick_n]) for d in draws]
        print(f"\n  Draw sum statistics:")
        print(f"    Mean: {np.mean(draw_sums):.1f}")
        print(f"    Std:  {np.std(draw_sums):.1f}")
        print(f"    Min:  {min(draw_sums)}")
        print(f"    Max:  {max(draw_sums)}")
        print(f"    Theoretical mean: {pick_n * (max_num + 1) / 2:.1f}")

        # Number frequency analysis (should be ~uniform)
        freq = Counter(n for d in draws for n in d['numbers'][:pick_n])
        expected = T * pick_n / max_num
        max_dev = max(abs(freq.get(n, 0) - expected) / expected * 100
                     for n in range(1, max_num + 1))
        print(f"\n  Frequency uniformity:")
        print(f"    Expected per number: {expected:.1f}")
        print(f"    Max deviation: {max_dev:.2f}%")
        print(f"    {'UNIFORM' if max_dev < 10 else 'NON-UNIFORM'}")

        # Consecutive number analysis
        consec_count = 0
        for d in draws:
            nums = sorted(d['numbers'][:pick_n])
            for i in range(len(nums) - 1):
                if nums[i + 1] - nums[i] == 1:
                    consec_count += 1
                    break
        consec_pct = consec_count / T * 100

        # Expected consecutive rate (theoretical)
        # P(at least one consecutive pair in pick-from-max_num)
        # Approximate: 1 - C(max_num - pick + 1, pick) / C(max_num, pick)
        p_no_consec = 1
        for i in range(pick_n):
            p_no_consec *= (max_num - pick_n + 1 - i) / (max_num - i)
        expected_consec_pct = (1 - p_no_consec) * 100

        print(f"\n  Consecutive numbers:")
        print(f"    Observed: {consec_pct:.1f}% of draws have consecutive pair")
        print(f"    Expected: {expected_consec_pct:.1f}%")
        print(f"    {'NORMAL' if abs(consec_pct - expected_consec_pct) < 5 else 'ANOMALY'}")

        results[game_name] = {
            'ev_base': ev_base,
            'roi_base_pct': roi_base,
            'house_edge_pct': -roi_base,
            'jackpot_breakeven': jackpot_needed,
            'jackpot_multiplier_needed': jackpot_needed / jackpot_base,
            'draw_sum_mean': float(np.mean(draw_sums)),
            'max_freq_deviation_pct': max_dev,
            'consecutive_observed_pct': consec_pct,
            'consecutive_expected_pct': expected_consec_pct,
        }

    # === Cross-game comparison ===
    print(f"\n  === Cross-Game Structure Comparison ===")
    print(f"  {'Game':<15} {'House%':>8} {'JP Break':>12} {'JP Mult':>8} {'EV':>8}")
    for g, r in results.items():
        print(f"  {g:<15} {r['house_edge_pct']:>7.2f}% "
              f"NTD {r['jackpot_breakeven']:>10,.0f} {r['jackpot_multiplier_needed']:>7.1f}x "
              f"NTD {r['ev_base']:>6.2f}")

    return results


# ============================================================
# Main
# ============================================================

def main():
    total_start = time.time()
    print("=" * 72)
    print("  Structural Optimization Research Engine")
    print("  6 Directions: Portfolio, Coverage, Anti-Crowd,")
    print("  Transfer, Kelly, Game Structure")
    print("  2026-03-15")
    print("=" * 72)

    draws_539 = load_draws('DAILY_539')
    print(f"\n  539 data: {len(draws_539)} draws")

    # Direction 1: Portfolio
    d1 = direction1_portfolio(draws_539)

    # Direction 2: Coverage
    d2 = direction2_coverage()

    # Direction 3: Anti-Crowd
    d3 = direction3_anticrowd()

    # Direction 4: Cross-Transfer
    d4 = direction4_cross_transfer()

    # Direction 5: Kelly
    d5 = direction5_kelly()

    # Direction 6: Game Structure
    d6 = direction6_game_structure()

    total_elapsed = time.time() - total_start

    # Save results
    output = {
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'total_elapsed_s': total_elapsed,
        'direction1_portfolio': d1,
        'direction2_coverage': {k: v for k, v in d2.items()},
        'direction3_anticrowd': {k: v for k, v in d3.items() if k != 'popularity_model'},
        'direction4_cross_transfer': d4,
        'direction5_kelly': {k: {kk: vv for kk, vv in v.items() if kk != 'match_probs'} for k, v in d5.items()},
        'direction6_game_structure': d6,
    }

    out_path = os.path.join(project_root, 'structural_optimization_results.json')
    with open(out_path, 'w') as f:
        json.dump(output, f, indent=2, ensure_ascii=False, default=str)

    # Final summary
    print("\n" + "=" * 72)
    print("  RESEARCH SUMMARY")
    print("=" * 72)

    print(f"\n  D1 Portfolio: Best config per bet level identified")
    print(f"  D2 Coverage: Wheeling systems analyzed for all 3 games")
    print(f"  D3 Anti-Crowd: Split risk negligible for fixed-prize games")
    print(f"  D4 Transfer: Signal portability tested across 3 games")
    print(f"  D5 Kelly: Capital allocation framework established")
    print(f"  D6 Structure: EV breakeven jackpot levels computed")

    print(f"\n  Total elapsed: {total_elapsed:.0f}s")
    print(f"  Results: {out_path}")
    print("=" * 72)


if __name__ == '__main__':
    main()
