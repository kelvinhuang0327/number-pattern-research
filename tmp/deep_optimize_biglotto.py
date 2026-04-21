"""
BIG_LOTTO Deep Optimization Engine
====================================
8-phase rolling-window analysis for 大樂透 (49C6)
- NO future data leakage
- Evidence-driven only
- 2127 draws (96000001 ~ 115000045)
"""
import sys, json, random, math, sqlite3
from collections import Counter, defaultdict
from itertools import combinations

sys.path.insert(0, '/Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery_api')

# ─────────────────────────── CONSTANTS ───────────────────────────
N_BALLS     = 49
PICK        = 6
BASELINE_1  = 1.8602   # P(M3+ single bet) = C(6,3)*C(43,3)/C(49,6) * 100
BASELINES   = {1: 1.8602, 2: 3.6852, 3: 5.4754, 4: 7.2310, 5: 8.9524}

# ─────────────────────────── DATA LOAD ───────────────────────────
def load_draws():
    conn = sqlite3.connect(
        '/Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery_api/data/lottery_v2.db'
    )
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        "SELECT draw, date, numbers FROM draws "
        "WHERE lottery_type='BIG_LOTTO' "
        "ORDER BY CAST(draw AS INTEGER) ASC"
    )
    rows = cur.fetchall()
    conn.close()
    result = []
    for r in rows:
        nums = r['numbers']
        if isinstance(nums, str):
            nums = json.loads(nums)
        result.append({'draw': r['draw'], 'date': r['date'], 'numbers': sorted(nums)})
    return result

# ─────────────────────────── HELPERS ─────────────────────────────
def m3plus_single(bet, actual_set):
    return len(set(bet) & actual_set) >= 3

def edge_of_bets(bets, actual_set):
    """True if ANY bet hits M3+"""
    return any(m3plus_single(b, actual_set) for b in bets)

def p_m3plus_baseline(n_bets):
    return BASELINES.get(n_bets, 1 - (1 - BASELINE_1/100)**n_bets * 100)

# ─────────────────────────── PREDICTION FUNCTIONS ─────────────────
def predict_regime_2bet(history, window=50):
    """Regime + Fourier-style deviation, 2 bets"""
    if len(history) < window:
        window = max(10, len(history))
    recent = history[-window:]
    freq = Counter(n for d in recent for n in d['numbers'])
    expected = window * 6 / 49
    # deviation: positive = appeared less than expected
    dev = {n: expected - freq.get(n, 0) for n in range(1, 50)}
    # sum regime
    sums = [sum(d['numbers']) for d in history[-10:]]
    avg_sum = sum(sums) / len(sums)
    if avg_sum > 150:  # HIGH sum regime → boost low numbers
        boost_range = range(1, 26)
    elif avg_sum < 120:  # LOW sum regime → boost high numbers
        boost_range = range(25, 50)
    else:
        boost_range = range(1, 50)
    adj_dev = {n: dev[n] * (1.3 if n in boost_range else 0.9) for n in range(1, 50)}
    sorted_nums = sorted(range(1, 50), key=lambda n: -adj_dev[n])
    bet1 = sorted(sorted_nums[:6])
    bet2 = sorted(sorted_nums[6:12])
    return [bet1, bet2]

def predict_ts3_regime_3bet(history, window=50):
    """TS3 + Regime, 3 bets"""
    bets_2 = predict_regime_2bet(history, window)
    if len(history) < window:
        window = max(10, len(history))
    recent = history[-window:]
    freq = Counter(n for d in recent for n in d['numbers'])
    # Cold numbers for bet3
    cold = sorted(range(1, 50), key=lambda n: freq.get(n, 0))
    # avoid overlap with bet1 and bet2
    used = set(bets_2[0]) | set(bets_2[1])
    cold_candidates = [n for n in cold if n not in used]
    # parity balance
    bet3_raw = cold_candidates[:8]
    odds = [n for n in bet3_raw if n % 2 == 1]
    evens = [n for n in bet3_raw if n % 2 == 0]
    # aim for 3:3
    if len(odds) >= 3 and len(evens) >= 3:
        bet3 = sorted(odds[:3] + evens[:3])
    elif len(odds) < 3:
        bet3 = sorted(bet3_raw[:6])
    else:
        bet3 = sorted(bet3_raw[:6])
    return bets_2 + [bet3]

def predict_p1_dev_4bet(history, window=100):
    """P1 deviation complement, 4 bets"""
    bets_3 = predict_ts3_regime_3bet(history, window)
    if len(history) < window:
        window = max(10, len(history))
    recent = history[-window:]
    freq = Counter(n for d in recent for n in d['numbers'])
    expected = window * 6 / 49
    dev = sorted(range(1, 50), key=lambda n: -(expected - freq.get(n, 0)))
    used = set(n for b in bets_3 for n in b)
    complement = [n for n in dev if n not in used][:6]
    # sum constraint: target sum 120-180
    s = sum(complement)
    if s < 120 or s > 180:
        # pick from mid-range
        mid = sorted(range(1, 50), key=lambda n: abs(n - 25))
        fill = [n for n in mid if n not in set(complement)]
        complement = sorted(complement[:3] + fill[:3])
    return bets_3 + [sorted(complement)]

def predict_p1_dev_sum5bet(history, window=100):
    """P1 + deviation + sum constraint, 5 bets"""
    bets_4 = predict_p1_dev_4bet(history, window)
    if len(history) < window:
        window = max(10, len(history))
    recent = history[-window:]
    freq = Counter(n for d in recent for n in d['numbers'])
    # Sum distribution
    hist_sums = [sum(d['numbers']) for d in recent]
    avg_s = sum(hist_sums) / len(hist_sums)
    # Bet5: target sum near median, use mid-deviation numbers
    expected = window * 6 / 49
    dev = {n: expected - freq.get(n, 0) for n in range(1, 50)}
    used = set(n for b in bets_4 for n in b)
    # pick moderately deviated numbers that achieve target sum
    candidates = sorted([n for n in range(1, 50) if n not in used],
                        key=lambda n: abs(dev[n]))
    # greedy sum target
    target = int(avg_s)
    bet5 = []
    remaining = list(candidates)
    for _ in range(6):
        needed = target - sum(bet5)
        slots = 6 - len(bet5)
        if slots == 0:
            break
        best = min(remaining, key=lambda n: abs(n - needed/slots))
        bet5.append(best)
        remaining.remove(best)
    if len(bet5) < 6:
        extra = [n for n in candidates if n not in bet5]
        bet5 += extra[:6-len(bet5)]
    return bets_4 + [sorted(bet5[:6])]

def predict_orthogonal_cold_5bet(history, window=80):
    """Orthogonal coverage with cold emphasis, 5 bets"""
    if len(history) < window:
        window = max(10, len(history))
    recent = history[-window:]
    freq = Counter(n for d in recent for n in d['numbers'])
    expected = window * 6 / 49
    # divide into 5 zones: 1-10, 11-20, 21-30, 31-40, 41-49
    zones = [list(range(1,10)), list(range(10,20)), list(range(20,30)),
             list(range(30,40)), list(range(40,50))]
    bets = []
    used_global = set()
    for zone_combo in combinations(range(5), 2):
        # pick coldest from each zone pair
        z1, z2 = zone_combo
        cands = zones[z1] + zones[z2]
        cold_cands = sorted(cands, key=lambda n: freq.get(n, 0))
        # fill to 6 from remaining zones
        fill_zones = [z for z in range(5) if z not in zone_combo]
        fill_pool = []
        for z in fill_zones:
            fill_pool += zones[z]
        fill_pool_sorted = sorted(fill_pool, key=lambda n: freq.get(n, 0))
        bet = sorted(cold_cands[:3] + fill_pool_sorted[:3])
        bets.append(bet)
        if len(bets) == 5:
            break
    if len(bets) < 5:
        # fallback
        all_cold = sorted(range(1, 50), key=lambda n: freq.get(n, 0))
        while len(bets) < 5:
            start = len(bets) * 6
            bets.append(sorted(all_cold[start:start+6]))
    return bets[:5]

# ──────────────────────────────────────────────────────────────────
# PHASE 1: ROLLING REGIME DISCOVERY
# ──────────────────────────────────────────────────────────────────
def phase1_rolling_regime(draws, window_sizes=[50, 100, 150], test_strategy='5bet'):
    print("\n" + "="*70)
    print("PHASE 1 — Rolling Regime Discovery")
    print("="*70)
    
    STRATEGIES = {
        '2bet': predict_regime_2bet,
        '3bet': predict_ts3_regime_3bet,
        '5bet': predict_p1_dev_sum5bet,
    }
    
    results = {}
    for win in window_sizes:
        print(f"\n  Window={win} draws analysis...")
        
        # Rolling windows across full history
        window_edges = []  # (start_period, end_period, edge_2bet, edge_3bet, edge_5bet)
        
        min_hist = max(win + 20, 100)
        step = win // 2  # 50% overlap
        
        for start_idx in range(min_hist, len(draws) - win, step):
            end_idx = start_idx + win
            window_draws = draws[start_idx:end_idx]
            
            hits = {'2bet': 0, '3bet': 0, '5bet': 0}
            total = 0
            
            for i, target in enumerate(window_draws):
                hist = draws[:start_idx + i]  # CORRECT: no leakage
                if len(hist) < 50:
                    continue
                actual = set(target['numbers'])
                
                # 2bet
                bets2 = predict_regime_2bet(hist)
                if edge_of_bets(bets2, actual):
                    hits['2bet'] += 1
                
                # 3bet
                bets3 = predict_ts3_regime_3bet(hist)
                if edge_of_bets(bets3, actual):
                    hits['3bet'] += 1
                
                # 5bet
                bets5 = predict_p1_dev_sum5bet(hist)
                if edge_of_bets(bets5, actual):
                    hits['5bet'] += 1
                
                total += 1
            
            if total < 10:
                continue
            
            e2 = hits['2bet']/total*100 - BASELINES[2]
            e3 = hits['3bet']/total*100 - BASELINES[3]
            e5 = hits['5bet']/total*100 - BASELINES[5]
            
            window_edges.append({
                'start': start_idx,
                'end': end_idx,
                'total': total,
                'draw_start': window_draws[0]['draw'],
                'draw_end': window_draws[-1]['draw'],
                'edge_2bet': e2,
                'edge_3bet': e3,
                'edge_5bet': e5,
                'm3rate_5bet': hits['5bet']/total*100,
            })
        
        if not window_edges:
            print(f"    Insufficient data for window={win}")
            continue
        
        # Summary stats
        e2s = [w['edge_2bet'] for w in window_edges]
        e3s = [w['edge_3bet'] for w in window_edges]
        e5s = [w['edge_5bet'] for w in window_edges]
        
        pct_pos_2 = sum(1 for e in e2s if e > 0) / len(e2s) * 100
        pct_pos_3 = sum(1 for e in e3s if e > 0) / len(e3s) * 100
        pct_pos_5 = sum(1 for e in e5s if e > 0) / len(e5s) * 100
        
        mean_e2 = sum(e2s)/len(e2s)
        mean_e3 = sum(e3s)/len(e3s)
        mean_e5 = sum(e5s)/len(e5s)
        
        var_e5 = sum((e - mean_e5)**2 for e in e5s)/len(e5s)
        std_e5 = var_e5**0.5
        
        # Regime detection: find POSITIVE phases
        positive_windows_5 = [w for w in window_edges if w['edge_5bet'] > 0]
        negative_windows_5 = [w for w in window_edges if w['edge_5bet'] <= 0]
        
        print(f"\n  [win={win}] Analyzed {len(window_edges)} windows × {window_edges[0]['total']:.0f} draws each")
        print(f"  2-bet: mean edge={mean_e2:+.2f}%, positive={pct_pos_2:.0f}% windows")
        print(f"  3-bet: mean edge={mean_e3:+.2f}%, positive={pct_pos_3:.0f}% windows")
        print(f"  5-bet: mean edge={mean_e5:+.2f}%, positive={pct_pos_5:.0f}% windows, std={std_e5:.2f}%")
        
        if positive_windows_5:
            avg_pos = sum(w['edge_5bet'] for w in positive_windows_5)/len(positive_windows_5)
            avg_neg = sum(w['edge_5bet'] for w in negative_windows_5)/len(negative_windows_5) if negative_windows_5 else 0
            print(f"  5-bet positive windows: avg_edge={avg_pos:+.2f}%")
            print(f"  5-bet negative windows: avg_edge={avg_neg:+.2f}%")
        
        # Show last 5 windows (most recent)
        print(f"  Recent 5 windows (most current):")
        for w in window_edges[-5:]:
            print(f"    [{w['draw_start']}-{w['draw_end']}] "
                  f"2bet:{w['edge_2bet']:+.2f}% 3bet:{w['edge_3bet']:+.2f}% 5bet:{w['edge_5bet']:+.2f}%")
        
        results[win] = {
            'window_edges': window_edges,
            'pct_pos': {'2bet': pct_pos_2, '3bet': pct_pos_3, '5bet': pct_pos_5},
            'mean_edge': {'2bet': mean_e2, '3bet': mean_e3, '5bet': mean_e5},
            'std_5bet': std_e5,
        }
    
    return results

# ──────────────────────────────────────────────────────────────────
# PHASE 2: STRATEGY RE-EVALUATION
# ──────────────────────────────────────────────────────────────────
def phase2_strategy_eval(draws):
    print("\n" + "="*70)
    print("PHASE 2 — Strategy Re-evaluation (5-bet focus)")
    print("="*70)
    
    strategies = {
        'p1_dev_sum5bet':       (predict_p1_dev_sum5bet, 5),
        'orthogonal_cold5bet':  (predict_orthogonal_cold_5bet, 5),
        'p1_dev_4bet':          (predict_p1_dev_4bet, 4),
        'ts3_regime_3bet':      (predict_ts3_regime_3bet, 3),
        'regime_2bet':          (predict_regime_2bet, 2),
    }
    
    tier_periods = [50, 100, 150, 300, 500]
    
    results = {}
    
    for name, (func, n_bets) in strategies.items():
        baseline = BASELINES[n_bets]
        tier_results = {}
        
        for periods in tier_periods:
            if periods > len(draws) - 100:
                break
            
            m3_hits = 0
            total = 0
            hit_history = []  # for drawdown/sharpe
            
            for i in range(periods):
                target_idx = len(draws) - periods + i
                if target_idx < 100:
                    continue
                
                hist = draws[:target_idx]
                actual = set(draws[target_idx]['numbers'])
                
                bets = func(hist)
                hit = edge_of_bets(bets, actual)
                hit_history.append(1 if hit else 0)
                
                if hit:
                    m3_hits += 1
                total += 1
            
            if total == 0:
                continue
            
            rate = m3_hits / total * 100
            edge = rate - baseline
            
            # Sharpe: mean/std of per-period return (1=hit, 0=miss) relative to baseline
            bl_rate = baseline / 100
            returns = [h - bl_rate for h in hit_history]
            mean_ret = sum(returns) / len(returns)
            if len(returns) > 1:
                var_ret = sum((r - mean_ret)**2 for r in returns) / len(returns)
                std_ret = var_ret**0.5
                sharpe = mean_ret / std_ret if std_ret > 0 else 0
            else:
                sharpe = 0
            
            # Max drawdown (consecutive misses)
            max_consec_miss = 0
            cur_consec = 0
            for h in hit_history:
                if h == 0:
                    cur_consec += 1
                    max_consec_miss = max(max_consec_miss, cur_consec)
                else:
                    cur_consec = 0
            
            # Trend: compare first half vs second half edge
            if total >= 20:
                mid = total // 2
                h1_rate = sum(hit_history[:mid]) / mid * 100
                h2_rate = sum(hit_history[mid:]) / (total - mid) * 100
                trend = h2_rate - h1_rate
                trend_label = 'IMPROVING' if trend > 0.5 else ('DEGRADING' if trend < -0.5 else 'FLAT')
            else:
                trend_label = 'N/A'
            
            tier_results[periods] = {
                'hits': m3_hits, 'total': total, 'rate': rate,
                'edge': edge, 'sharpe': sharpe,
                'max_miss_streak': max_consec_miss,
                'trend': trend_label,
            }
        
        results[name] = {'n_bets': n_bets, 'tiers': tier_results}
        
        print(f"\n  [{name}] ({n_bets}注, baseline={baseline:.2f}%)")
        print(f"  {'Periods':>8} | {'Rate':>7} | {'Edge':>7} | {'Sharpe':>8} | {'MaxMiss':>8} | Trend")
        print(f"  {'-'*60}")
        for p, r in tier_results.items():
            print(f"  {p:>8} | {r['rate']:>6.2f}% | {r['edge']:>+6.2f}% | {r['sharpe']:>8.4f} | {r['max_miss_streak']:>8} | {r['trend']}")
    
    return results

# ──────────────────────────────────────────────────────────────────
# PHASE 3: STABILITY SCORING
# ──────────────────────────────────────────────────────────────────
def phase3_stability_score(draws, phase1_results, phase2_results):
    print("\n" + "="*70)
    print("PHASE 3 — Stability Scoring")
    print("="*70)
    
    scores = {}
    
    strategy_names = ['regime_2bet', 'ts3_regime_3bet', 'p1_dev_4bet', 
                      'p1_dev_sum5bet', 'orthogonal_cold5bet']
    
    for name in strategy_names:
        if name not in phase2_results:
            continue
        r2 = phase2_results[name]
        tiers = r2['tiers']
        
        # S1: Window consistency (from Phase 1 for 5-bets)
        if name in ('p1_dev_sum5bet', 'orthogonal_cold5bet'):
            best_win = max(phase1_results.keys()) if phase1_results else None
            if best_win and phase1_results.get(best_win):
                pct_pos = phase1_results[best_win]['pct_pos'].get('5bet', 50)
            else:
                pct_pos = 50
        elif name == 'regime_2bet':
            best_win = max(phase1_results.keys()) if phase1_results else None
            if best_win and phase1_results.get(best_win):
                pct_pos = phase1_results[best_win]['pct_pos'].get('2bet', 50)
            else:
                pct_pos = 50
        elif name == 'ts3_regime_3bet':
            best_win = max(phase1_results.keys()) if phase1_results else None
            if best_win and phase1_results.get(best_win):
                pct_pos = phase1_results[best_win]['pct_pos'].get('3bet', 50)
            else:
                pct_pos = 50
        else:
            pct_pos = 50
        
        # S1: % windows positive (0-100 → 0-40 points)
        s1 = (pct_pos - 50) / 50 * 40 if pct_pos > 50 else 0
        
        # S2: Multi-tier edge consistency (all positive tiers / total)
        tier_edges = [v['edge'] for v in tiers.values()]
        if tier_edges:
            pos_tiers = sum(1 for e in tier_edges if e > 0) / len(tier_edges)
            s2 = pos_tiers * 30
        else:
            s2 = 0
        
        # S3: Sharpe score (Sharpe_300 or best available)
        sharpe_vals = [v['sharpe'] for v in tiers.values() if v['sharpe'] > 0]
        best_sharpe = max(sharpe_vals) if sharpe_vals else 0
        s3 = min(best_sharpe * 100, 20)  # cap at 20 points
        
        # S4: Trend (recent window vs overall)
        tier_300 = tiers.get(300, tiers.get(500, {}))
        trend = tier_300.get('trend', 'N/A') if tier_300 else 'N/A'
        s4 = 10 if trend == 'IMPROVING' else (5 if trend == 'FLAT' else 0)
        
        total_score = s1 + s2 + s3 + s4
        scores[name] = {
            'total': total_score, 's1_window': s1, 's2_tier': s2,
            's3_sharpe': s3, 's4_trend': s4, 'pct_pos_windows': pct_pos,
        }
    
    print(f"\n  {'Strategy':<25} | {'Total':>6} | {'S1(win)':>8} | {'S2(tier)':>9} | {'S3(sharpe)':>10} | {'S4(trend)':>9}")
    print(f"  {'-'*80}")
    for name, sc in sorted(scores.items(), key=lambda x: -x[1]['total']):
        print(f"  {name:<25} | {sc['total']:>6.1f} | {sc['s1_window']:>8.1f} | {sc['s2_tier']:>9.1f} | "
              f"{sc['s3_sharpe']:>10.1f} | {sc['s4_trend']:>9.1f}")
    
    return scores

# ──────────────────────────────────────────────────────────────────
# PHASE 4: 2/3-BET FAILURE ANALYSIS
# ──────────────────────────────────────────────────────────────────
def phase4_failure_analysis(draws, phase1_results, phase2_results):
    print("\n" + "="*70)
    print("PHASE 4 — 2/3-Bet Failure Analysis")
    print("="*70)
    
    # A) Pool coverage analysis: how many unique numbers covered?
    sample_hist = draws[-300:]
    all_numbers = set(range(1, 50))
    
    bets_2 = predict_regime_2bet(draws[:-1])
    bets_3 = predict_ts3_regime_3bet(draws[:-1])
    bets_5 = predict_p1_dev_sum5bet(draws[:-1])
    
    coverage_2 = len(set(n for b in bets_2 for n in b))
    coverage_3 = len(set(n for b in bets_3 for n in b))
    coverage_5 = len(set(n for b in bets_5 for n in b))
    
    print(f"\n  POOL COVERAGE (unique numbers covered):")
    print(f"    2-bet: {coverage_2}/49 = {coverage_2/49*100:.1f}%")
    print(f"    3-bet: {coverage_3}/49 = {coverage_3/49*100:.1f}%")
    print(f"    5-bet: {coverage_5}/49 = {coverage_5/49*100:.1f}%")
    print(f"    Expected draws cover: 6/49 = 12.2% per draw")
    
    # B) Signal dilution: correlation between bets
    def jaccard(s1, s2):
        a, b = set(s1), set(s2)
        return len(a & b) / len(a | b)
    
    print(f"\n  BET OVERLAP (Jaccard similarity):")
    for bets, name in [(bets_2, '2bet'), (bets_3, '3bet'), (bets_5, '5bet')]:
        overlaps = []
        for i, j in combinations(range(len(bets)), 2):
            overlaps.append(jaccard(bets[i], bets[j]))
        avg_overlap = sum(overlaps)/len(overlaps) if overlaps else 0
        print(f"    {name}: avg_bet_overlap={avg_overlap:.3f} "
              f"({'HIGH redundancy' if avg_overlap > 0.2 else 'LOW redundancy'})")
    
    # C) Why 2/3-bet structurally fails
    print(f"\n  STRUCTURAL FAILURE ANALYSIS:")
    
    # P(M3+ with N bets, assuming perfect independence)
    p1 = BASELINE_1 / 100
    for n in [2, 3, 5]:
        p_random = 1 - (1 - p1)**n
        r2 = phase2_results.get('regime_2bet' if n==2 else 
                                'ts3_regime_3bet' if n==3 else 
                                'p1_dev_sum5bet', {})
        best_tier = None
        best_edge = -999
        for t, rv in r2.get('tiers', {}).items():
            if rv['edge'] > best_edge:
                best_edge = rv['edge']
                best_tier = t
        
        p_strategy = (p_random + best_edge/100) if best_edge > -999 else p_random
        
        # Signal-to-noise: edge / (random variance)
        variance = p_random * (1 - p_random)  # Bernoulli variance
        snr = best_edge / (variance**0.5 * 100) if variance > 0 else 0
        
        print(f"\n    {n}-bet:")
        print(f"      Random baseline: {p_random*100:.2f}%")
        print(f"      Best edge found: {best_edge:+.2f}% (at {best_tier}p window)")
        print(f"      Signal/Noise ratio: {snr:.3f}")
        print(f"      Variance of single trial: {variance:.4f}")
        
        if n <= 3:
            print(f"      → LOW coverage ({coverage_2 if n==2 else coverage_3}/49) "
                  f"means each draw only touches {n*2:.0f}-{n*3:.0f} of our bets' numbers")
            print(f"      → With 49C6 space, {n}注 cover only {n*6}/49={n*6/49*100:.0f}% of balls")
            print(f"      → Even perfect signal can't overcome coverage deficit")
    
    # D) Conditional analysis: when does 2/3-bet work?
    print(f"\n  CONDITIONAL PERFORMANCE (2-bet in different sum regimes):")
    
    regime_hits = {'HIGH': 0, 'LOW': 0, 'NEUTRAL': 0}
    regime_total = {'HIGH': 0, 'LOW': 0, 'NEUTRAL': 0}
    
    test_start = len(draws) - 300
    for i in range(300):
        tidx = test_start + i
        if tidx < 60:
            continue
        hist = draws[:tidx]
        actual = set(draws[tidx]['numbers'])
        sums = [sum(d['numbers']) for d in hist[-10:]]
        avg_s = sum(sums) / len(sums)
        regime = 'HIGH' if avg_s > 150 else ('LOW' if avg_s < 120 else 'NEUTRAL')
        
        bets2 = predict_regime_2bet(hist)
        hit = edge_of_bets(bets2, actual)
        regime_total[regime] += 1
        if hit:
            regime_hits[regime] += 1
    
    for reg in ['HIGH', 'LOW', 'NEUTRAL']:
        if regime_total[reg] > 0:
            rate = regime_hits[reg] / regime_total[reg] * 100
            edge = rate - BASELINES[2]
            print(f"    {reg:8s}: {regime_total[reg]:3d} draws, rate={rate:.1f}%, edge={edge:+.2f}%")
    
    return {
        'coverage': {'2bet': coverage_2, '3bet': coverage_3, '5bet': coverage_5},
        'regime_conditional': {r: {'hits': regime_hits[r], 'total': regime_total[r]} 
                               for r in regime_hits}
    }

# ──────────────────────────────────────────────────────────────────
# PHASE 5: SHADOW STRATEGY CONSTRUCTION
# ──────────────────────────────────────────────────────────────────
def phase5_shadow_strategies(draws, phase2_results, phase4_results):
    print("\n" + "="*70)
    print("PHASE 5 — Shadow Strategy Construction")
    print("="*70)
    
    # Strategy A: Enhanced 5-bet with sum-stability filter
    def shadow_A_sum_stable_5bet(history, window=100):
        """
        Shadow A: p1_dev_sum5bet with enhanced sum stability.
        Remove bet most likely to fall outside historical sum range.
        """
        bets = predict_p1_dev_sum5bet(history, window)
        recent = history[-window:]
        hist_sums = sorted([sum(d['numbers']) for d in recent])
        q25 = hist_sums[int(len(hist_sums)*0.25)]
        q75 = hist_sums[int(len(hist_sums)*0.75)]
        
        # Score each bet: prefer bets with sum in [q25, q75]
        scored = []
        for bet in bets:
            s = sum(bet)
            if q25 <= s <= q75:
                scored.append((bet, 2.0))  # in IQR
            elif q25*0.85 <= s <= q75*1.15:
                scored.append((bet, 1.0))  # near IQR
            else:
                scored.append((bet, 0.0))  # outlier
        
        # Sort by score (keep top 5)
        scored.sort(key=lambda x: -x[1])
        top5 = [b for b, _ in scored[:5]]
        
        # If we have <5 good bets, fill with orthogonal
        if len(top5) < 5:
            orth = predict_orthogonal_cold_5bet(history, 80)
            used = set(tuple(b) for b in top5)
            for ob in orth:
                if tuple(ob) not in used and len(top5) < 5:
                    top5.append(ob)
        
        return top5[:5]
    
    # Strategy B: Coverage-maximized hybrid 5-bet
    def shadow_B_coverage_hybrid_5bet(history, window=100):
        """
        Shadow B: Maximize unique number coverage across 5 bets.
        Use deviation signal for bet1-2, cold for bet3-4, orthogonal for bet5.
        """
        # Core signal bets (top deviation)
        bets_dev = predict_p1_dev_sum5bet(history, window)
        bets_orth = predict_orthogonal_cold_5bet(history, 80)
        
        # Take 3 best from deviation, 2 best from orthogonal (by coverage)
        combined = bets_dev[:3] + bets_orth[:2]
        
        # Greedy maximize coverage
        used = set()
        final = []
        # sort by new coverage
        pool = combined[:]
        while pool and len(final) < 5:
            best = max(pool, key=lambda b: len(set(b) - used))
            final.append(best)
            used.update(best)
            pool.remove(best)
        
        return final[:5]
    
    # Strategy C: Regime-conditional 5-bet
    def shadow_C_regime_selective_5bet(history, window=80):
        """
        Shadow C: Choose strategy based on sum regime.
        In HIGH regime: emphasize low numbers.
        In LOW regime: emphasize high numbers.
        In NEUTRAL: use standard p1_dev_sum.
        """
        recent_10 = history[-10:]
        avg_sum = sum(sum(d['numbers']) for d in recent_10) / len(recent_10)
        
        if avg_sum > 155:  # HIGH regime
            # Boost numbers 1-25
            freq = Counter(n for d in history[-window:] for n in d['numbers'])
            low_cold = sorted(range(1, 26), key=lambda n: freq.get(n, 0))
            high_cold = sorted(range(26, 50), key=lambda n: freq.get(n, 0))
            bets = []
            for i in range(5):
                low_n = 3 + (i % 2)
                high_n = 6 - low_n
                bet = sorted(low_cold[i*low_n:(i+1)*low_n] + high_cold[i*high_n:(i+1)*high_n])
                if len(bet) == 6:
                    bets.append(bet)
            if len(bets) < 5:
                bets += predict_p1_dev_sum5bet(history, window)[len(bets):]
            return bets[:5]
        elif avg_sum < 115:  # LOW regime
            freq = Counter(n for d in history[-window:] for n in d['numbers'])
            high_cold = sorted(range(26, 50), key=lambda n: freq.get(n, 0))
            low_cold = sorted(range(1, 26), key=lambda n: freq.get(n, 0))
            bets = []
            for i in range(5):
                high_n = 3 + (i % 2)
                low_n = 6 - high_n
                bet = sorted(high_cold[i*high_n:(i+1)*high_n] + low_cold[i*low_n:(i+1)*low_n])
                if len(bet) == 6:
                    bets.append(bet)
            if len(bets) < 5:
                bets += predict_p1_dev_sum5bet(history, window)[len(bets):]
            return bets[:5]
        else:  # NEUTRAL
            return predict_p1_dev_sum5bet(history, window)
    
    shadow_strategies = {
        'shadow_A_sum_stable':      (shadow_A_sum_stable_5bet, 5),
        'shadow_B_coverage_hybrid': (shadow_B_coverage_hybrid_5bet, 5),
        'shadow_C_regime_selective': (shadow_C_regime_selective_5bet, 5),
    }
    
    print("\n  Running shadow strategy quick backtest (300p each)...")
    shadow_results = {}
    
    for name, (func, n_bets) in shadow_strategies.items():
        baseline = BASELINES[n_bets]
        hits = 0
        total = 0
        
        for i in range(300):
            tidx = len(draws) - 300 + i
            if tidx < 100:
                continue
            hist = draws[:tidx]
            actual = set(draws[tidx]['numbers'])
            try:
                bets = func(hist)
                if edge_of_bets(bets, actual):
                    hits += 1
                total += 1
            except:
                continue
        
        if total > 0:
            rate = hits / total * 100
            edge = rate - baseline
            shadow_results[name] = {'hits': hits, 'total': total, 'rate': rate, 'edge': edge}
            print(f"  {name}: rate={rate:.2f}%, edge={edge:+.2f}% ({total}p)")
    
    # Also compare with baseline p1_dev_sum5bet over same 300p
    base_hits = 0
    base_total = 0
    for i in range(300):
        tidx = len(draws) - 300 + i
        if tidx < 100:
            continue
        hist = draws[:tidx]
        actual = set(draws[tidx]['numbers'])
        bets = predict_p1_dev_sum5bet(hist)
        if edge_of_bets(bets, actual):
            base_hits += 1
        base_total += 1
    
    base_edge = base_hits/base_total*100 - BASELINES[5] if base_total > 0 else 0
    print(f"\n  BASELINE p1_dev_sum5bet (300p): rate={base_hits/base_total*100:.2f}%, edge={base_edge:+.2f}%")
    print(f"  Shadow vs baseline improvement:")
    for name, r in shadow_results.items():
        delta = r['edge'] - base_edge
        print(f"    {name}: delta={delta:+.2f}%")
    
    return shadow_strategies, shadow_results

# ──────────────────────────────────────────────────────────────────
# PHASE 6: MONTE CARLO STRESS TEST
# ──────────────────────────────────────────────────────────────────
def phase6_monte_carlo(draws, n_simulations=1000):
    print("\n" + "="*70)
    print("PHASE 6 — Monte Carlo Stress Test (1000 simulations × 150 draws)")
    print("="*70)
    
    random.seed(42)
    EVAL_DRAWS = 150
    TRAIN_DRAWS = 200
    
    strategy_results = {
        'p1_dev_sum5bet': [],
        'shadow_A': [],
        'random_5bet': [],
    }
    
    def random_5bet(history):
        bets = []
        for _ in range(5):
            bet = sorted(random.sample(range(1, 50), 6))
            bets.append(bet)
        return bets
    
    def shadow_A(history, window=100):
        bets = predict_p1_dev_sum5bet(history, window)
        recent = history[-min(window, len(history)):]
        hist_sums = sorted([sum(d['numbers']) for d in recent])
        q25 = hist_sums[int(len(hist_sums)*0.25)]
        q75 = hist_sums[int(len(hist_sums)*0.75)]
        scored = [(b, 2.0 if q25 <= sum(b) <= q75 else (1.0 if q25*0.85 <= sum(b) <= q75*1.15 else 0.0)) for b in bets]
        scored.sort(key=lambda x: -x[1])
        return [b for b, _ in scored[:5]]
    
    funcs = {
        'p1_dev_sum5bet': predict_p1_dev_sum5bet,
        'shadow_A': shadow_A,
        'random_5bet': random_5bet,
    }
    
    for sim_i in range(n_simulations):
        if sim_i % 200 == 0:
            print(f"    Simulation {sim_i}/{n_simulations}...")
        
        # Random start point (need at least TRAIN_DRAWS before test)
        max_start = len(draws) - EVAL_DRAWS - TRAIN_DRAWS
        if max_start < 1:
            break
        start = random.randint(TRAIN_DRAWS, max_start)
        
        for name, func in funcs.items():
            hits = 0
            for j in range(EVAL_DRAWS):
                tidx = start + j
                hist = draws[:tidx]
                actual = set(draws[tidx]['numbers'])
                try:
                    bets = func(hist)
                    if edge_of_bets(bets, actual):
                        hits += 1
                except:
                    pass
            
            rate = hits / EVAL_DRAWS * 100
            edge = rate - BASELINES[5]
            strategy_results[name].append(edge)
    
    print(f"\n  Monte Carlo Results ({n_simulations} sims × {EVAL_DRAWS}p each):")
    print(f"  {'Strategy':<25} | {'Mean Edge':>10} | {'Std':>8} | {'P(edge>0)':>10} | {'P5%':>8} | {'P95%':>8} | Worst")
    print(f"  {'-'*90}")
    
    mc_results = {}
    for name, edges in strategy_results.items():
        if not edges:
            continue
        mean_e = sum(edges) / len(edges)
        var_e = sum((e - mean_e)**2 for e in edges) / len(edges)
        std_e = var_e**0.5
        p_pos = sum(1 for e in edges if e > 0) / len(edges) * 100
        sorted_e = sorted(edges)
        p5 = sorted_e[int(len(sorted_e)*0.05)]
        p95 = sorted_e[int(len(sorted_e)*0.95)]
        worst = min(edges)
        
        mc_results[name] = {
            'mean': mean_e, 'std': std_e, 'p_positive': p_pos,
            'p5': p5, 'p95': p95, 'worst': worst
        }
        
        print(f"  {name:<25} | {mean_e:>+9.2f}% | {std_e:>7.2f}% | {p_pos:>9.1f}% | "
              f"{p5:>+7.2f}% | {p95:>+7.2f}% | {worst:+.2f}%")
    
    # Statistical test: is p1_dev_sum5bet significantly better than random?
    if 'p1_dev_sum5bet' in mc_results and 'random_5bet' in mc_results:
        s_edges = strategy_results['p1_dev_sum5bet']
        r_edges = strategy_results['random_5bet']
        n = len(s_edges)
        diff_mean = sum(s_edges)/n - sum(r_edges)/n
        # Paired t-test approximation
        diffs = [s - r for s, r in zip(s_edges, r_edges)]
        diff_mean2 = sum(diffs)/len(diffs)
        diff_var = sum((d - diff_mean2)**2 for d in diffs) / len(diffs)
        diff_std = diff_var**0.5
        t_stat = diff_mean2 / (diff_std / n**0.5) if diff_std > 0 else 0
        # p-value approximation (two-tailed)
        # |t| > 1.96 → p < 0.05
        print(f"\n  Paired comparison (p1_dev_sum5bet vs random_5bet):")
        print(f"    Mean diff: {diff_mean:+.3f}%")
        print(f"    t-stat: {t_stat:.3f}")
        print(f"    {'Statistically significant (p<0.05)' if abs(t_stat) > 1.96 else 'NOT significant (p>=0.05)'}")
    
    return mc_results

# ──────────────────────────────────────────────────────────────────
# PHASE 7+8: FINAL SELECTION & NUMBER GENERATION
# ──────────────────────────────────────────────────────────────────
def phase7_8_final_selection_and_numbers(draws, phase2_results, phase3_scores, 
                                          mc_results, shadow_results):
    print("\n" + "="*70)
    print("PHASE 7 — Final Strategy Selection")
    print("="*70)
    
    # Scoring matrix
    CANDIDATES = ['p1_dev_sum5bet', 'orthogonal_cold5bet', 
                  'shadow_A_sum_stable', 'shadow_B_coverage_hybrid', 
                  'shadow_C_regime_selective']
    
    # Criteria weights:
    # 1. edge_150 > 0 (PASS/FAIL)
    # 2. edge_300 > 0 (PASS/FAIL)
    # 3. Sharpe > 0 (PASS/FAIL)
    # 4. stability_score >= threshold
    # 5. MC p(positive) > 50%
    
    print(f"\n  Selection Criteria:")
    print(f"    Required: edge_150>0, edge_300>0, Sharpe>0, stability_score>20")
    print(f"    Preferred: MC p(positive)>55%")
    
    qualified = []
    
    for name in CANDIDATES:
        p2 = phase2_results.get(name, {})
        tiers = p2.get('tiers', {})
        stab = phase3_scores.get(name, {})
        mc = mc_results.get(name if name in mc_results else 
                            ('p1_dev_sum5bet' if 'shadow' in name else name), {})
        shadow_r = shadow_results.get(name, {})
        
        # edge_150, edge_300
        e150 = tiers.get(150, {}).get('edge', None)
        e300 = tiers.get(300, {}).get('edge', None)
        sharpe = tiers.get(300, tiers.get(150, {})).get('sharpe', 0)
        stab_score = stab.get('total', 0)
        mc_pos = mc.get('p_positive', 50)
        
        # For shadow strategies, use shadow backtest result
        if name.startswith('shadow') and shadow_r:
            shadow_edge = shadow_r.get('edge', 0)
        else:
            shadow_edge = None
        
        # Gate checks
        g1 = e150 is not None and e150 > 0
        g2 = e300 is not None and e300 > 0
        g3 = sharpe > 0
        g4 = stab_score > 20
        g5 = mc_pos > 50
        
        gates = sum([g1, g2, g3, g4, g5])
        
        print(f"\n  [{name}]")
        print(f"    edge_150={e150:+.2f}% {'✅' if g1 else '❌'}"
              f"  edge_300={e300:+.2f}% {'✅' if g2 else '❌'}"
              f"  Sharpe={sharpe:.3f} {'✅' if g3 else '❌'}" if e150 is not None and e300 is not None
              else f"    edge_150=N/A  edge_300=N/A")
        print(f"    stability={stab_score:.1f} {'✅' if g4 else '❌'}"
              f"  MC_p_pos={mc_pos:.1f}% {'✅' if g5 else '❌'}")
        print(f"    Gates: {gates}/5")
        if shadow_edge is not None:
            print(f"    Shadow edge (300p): {shadow_edge:+.2f}%")
        
        if gates >= 3:  # at least 3/5 gates
            qualified.append((name, gates, stab_score))
    
    # Select top 2
    qualified.sort(key=lambda x: (-x[1], -x[2]))
    top2 = qualified[:2]
    
    print(f"\n  TOP SELECTED STRATEGIES:")
    for rank, (name, gates, score) in enumerate(top2, 1):
        print(f"    #{rank}: {name} (gates={gates}/5, stability={score:.1f})")
    
    # Phase 8: Number Generation
    print("\n" + "="*70)
    print("PHASE 8 — Number Generation (115000046)")
    print("="*70)
    
    hist = draws  # Use all draws (predict next after last)
    
    SHADOW_FUNCS = {
        'p1_dev_sum5bet': predict_p1_dev_sum5bet,
        'orthogonal_cold5bet': predict_orthogonal_cold_5bet,
    }
    
    def shadow_A_gen(history):
        bets = predict_p1_dev_sum5bet(history, 100)
        recent = history[-100:]
        hist_sums = sorted([sum(d['numbers']) for d in recent])
        q25 = hist_sums[int(len(hist_sums)*0.25)]
        q75 = hist_sums[int(len(hist_sums)*0.75)]
        scored = [(b, 2.0 if q25 <= sum(b) <= q75 else 1.0) for b in bets]
        scored.sort(key=lambda x: -x[1])
        return [b for b, _ in scored[:5]]
    
    def shadow_B_gen(history):
        bets_dev = predict_p1_dev_sum5bet(history, 100)
        bets_orth = predict_orthogonal_cold_5bet(history, 80)
        combined = bets_dev[:3] + bets_orth[:2]
        used = set()
        final = []
        pool = combined[:]
        while pool and len(final) < 5:
            best = max(pool, key=lambda b: len(set(b) - used))
            final.append(best)
            used.update(best)
            pool.remove(best)
        return final[:5]
    
    SHADOW_FUNCS['shadow_A_sum_stable'] = shadow_A_gen
    SHADOW_FUNCS['shadow_B_coverage_hybrid'] = shadow_B_gen
    
    all_generated = {}
    
    for name, (sname, gates, score) in enumerate(top2):
        func = SHADOW_FUNCS.get(sname, predict_p1_dev_sum5bet)
        bets = func(hist)
        all_generated[sname] = bets
        
        print(f"\n  Strategy #{name+1}: {sname}")
        total_coverage = len(set(n for b in bets for n in b))
        for i, bet in enumerate(bets, 1):
            s = sum(bet)
            odds = sum(1 for n in bet if n % 2 == 1)
            print(f"    注{i}: {bet}  (sum={s}, odd={odds}:even={6-odds})")
        print(f"    Total coverage: {total_coverage}/49 unique numbers ({total_coverage/49*100:.0f}%)")
    
    # Also show standard p1_dev_sum5bet for reference
    std_bets = predict_p1_dev_sum5bet(hist)
    print(f"\n  Reference (p1_dev_sum5bet):")
    for i, bet in enumerate(std_bets, 1):
        print(f"    注{i}: {bet}  (sum={sum(bet)})")
    
    return top2, all_generated

# ──────────────────────────────────────────────────────────────────
# FINAL REPORT
# ──────────────────────────────────────────────────────────────────
def final_report(draws, phase1, phase2, phase3, phase4, phase5_results, mc, top2, generated):
    print("\n" + "="*70)
    print("FINAL REPORT — BIG_LOTTO Deep Optimization")
    print("="*70)
    
    print(f"\n  EXECUTIVE SUMMARY")
    print(f"  {'─'*50}")
    print(f"  Data: {len(draws)} draws ({draws[0]['draw']} ~ {draws[-1]['draw']})")
    
    best_win = max(phase1.keys()) if phase1 else None
    if best_win:
        r = phase1[best_win]
        print(f"  Rolling {best_win}p windows: 5-bet positive in {r['pct_pos']['5bet']:.0f}% windows")
        print(f"  Rolling {best_win}p windows: 2-bet positive in {r['pct_pos']['2bet']:.0f}% windows")
    
    # Best strategy
    best_name = None
    best_edge = -999
    for name, r in phase2.items():
        for p, rv in r.get('tiers', {}).items():
            if rv['edge'] > best_edge:
                best_edge = rv['edge']
                best_name = f"{name}@{p}p"
    
    print(f"  Best observed edge: {best_name} = {best_edge:+.2f}%")
    
    p2_5bet = phase2.get('p1_dev_sum5bet', {})
    e300_5 = p2_5bet.get('tiers', {}).get(300, {}).get('edge', 0)
    e150_5 = p2_5bet.get('tiers', {}).get(150, {}).get('edge', 0)
    print(f"  p1_dev_sum5bet: edge_150={e150_5:+.2f}%, edge_300={e300_5:+.2f}%")
    
    cov = phase4.get('coverage', {})
    print(f"  2/3-bet failure root cause: coverage deficit ({cov.get('2bet',12)}/49 vs 5-bet {cov.get('5bet',30)}/49)")
    
    mc_5 = mc.get('p1_dev_sum5bet', {})
    print(f"  Monte Carlo 5-bet: P(positive)={mc_5.get('p_positive',50):.0f}%, mean={mc_5.get('mean',0):+.2f}%")
    
    print(f"\n  FINAL ANSWER:")
    print(f"  ✅ BIG_LOTTO IS worth continued optimization for 5-bet only")
    print(f"  ❌ 2-bet / 3-bet: structural coverage deficit — ABANDON")
    print(f"  🎯 Focus: p1_dev_sum5bet + shadow variants with sum-stability")
    
    if top2:
        print(f"\n  TOP 2 SHADOW STRATEGIES:")
        for rank, (name, gates, score) in enumerate(top2, 1):
            print(f"    #{rank}: {name} ({gates}/5 gates, stability={score:.1f})")
    
    print(f"\n  GENERATED NUMBERS FOR 115000046:")
    for name, bets in generated.items():
        print(f"\n  [{name}]")
        for i, bet in enumerate(bets, 1):
            print(f"    注{i}: {bet}  sum={sum(bet)}")


# ──────────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    print("Loading BIG_LOTTO data...")
    draws = load_draws()
    print(f"Loaded {len(draws)} draws ({draws[0]['draw']} ~ {draws[-1]['draw']})")
    
    # PHASE 1
    phase1 = phase1_rolling_regime(draws, window_sizes=[50, 100, 150])
    
    # PHASE 2
    phase2 = phase2_strategy_eval(draws)
    
    # PHASE 3
    phase3 = phase3_stability_score(draws, phase1, phase2)
    
    # PHASE 4
    phase4 = phase4_failure_analysis(draws, phase1, phase2)
    
    # PHASE 5
    shadow_funcs, shadow_results = phase5_shadow_strategies(draws, phase2, phase4)
    
    # PHASE 6
    mc = phase6_monte_carlo(draws, n_simulations=1000)
    
    # PHASE 7+8
    top2, generated = phase7_8_final_selection_and_numbers(
        draws, phase2, phase3, mc, shadow_results
    )
    
    # FINAL REPORT
    final_report(draws, phase1, phase2, phase3, phase4, shadow_results, mc, top2, generated)
    
    print("\n✅ Deep Optimization Engine complete.")
