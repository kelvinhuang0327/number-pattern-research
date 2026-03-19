#!/usr/bin/env python3
"""
=============================================================================
539 P1_anomaly_capture (ACB) — 完整 Permutation Test
=============================================================================
目的: 驗證 ACB 單注 +2.80% (1500p) 是否為真實時序信號

ACB 設計:
  freq_deficit × 0.4 + gap_score × 0.6
  × boundary_bonus(1-5/35-39 → 1.2x)
  × mod3_bonus(3的倍數 → 1.1x)
  + cross-zone constraint (強制≥2個zone)

回測協議:
  - Walk-forward，min_train=100（ACB window=100）
  - 主指標: M2+ (單注 5 選 5)
  - 三窗口: 150 / 500 / 1500 期
  - Permutation Test: 500次隨機洗牌（比標準200次更嚴謹）
  - Signal Edge = actual − shuffle_mean  ← 核心判斷
  - Random baseline: 每次隨機選5個號碼
  - McNemar: ACB vs cold_single（冷號單注對照）

採納標準:
  Signal Edge > 0  AND  p ≤ 0.05  AND  三窗口全正

Output: backtest_acb_permutation_results.json
=============================================================================
"""

import json, math, os, random, sys, time, warnings
from collections import Counter
from datetime import datetime

import numpy as np
from scipy import stats as scipy_stats

warnings.filterwarnings('ignore')

_base = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_base, '..', 'lottery_api'))
sys.path.insert(0, os.path.join(_base, '..'))
from database import DatabaseManager

# ─── Constants ────────────────────────────────────────────────────
POOL = 39
PICK = 5
TOTAL_NUMBERS = list(range(1, POOL + 1))
SEED = 42

from math import comb
C39_5 = comb(39, 5)
def _pmatch(k): return comb(5,k)*comb(34,5-k)/C39_5
P_GE2_1 = sum(_pmatch(k) for k in range(2,6))   # 單注 M2+ 基準 ≈ 11.40%
P_GE3_1 = sum(_pmatch(k) for k in range(3,6))   # 單注 M3+ 基準 ≈ 1.00%

print(f"[BASELINE] 1-bet M2+ = {P_GE2_1*100:.4f}%  ← 主指標基準")
print(f"[BASELINE] 1-bet M3+ = {P_GE3_1*100:.4f}%")


# ─── Data ─────────────────────────────────────────────────────────
def load_data():
    db_path = os.path.join(_base,'..','lottery_api','data','lottery_v2.db')
    db = DatabaseManager(db_path=db_path)
    raw = db.get_all_draws('DAILY_539')
    draws = sorted(raw, key=lambda x: (x['date'], x['draw']))
    print(f"[DATA] {len(draws)} draws: {draws[0]['date']} → {draws[-1]['date']}")
    return draws

def get_numbers(draw):
    n = draw.get('numbers', [])
    if isinstance(n, str): n = json.loads(n)
    return list(n)


# ─── ACB 實作（完整複製自 backtest_539_structural_upgrade.py）─────
def predict_acb(hist, window=100):
    """
    P1_anomaly_capture (ACB) — 異常捕捉注
    freq_deficit × 0.4 + gap_score × 0.6
    × boundary_bonus × mod3_bonus + cross-zone constraint
    """
    recent = hist[-window:] if len(hist) >= window else hist

    counter = Counter()
    for n in range(1, POOL + 1): counter[n] = 0
    for d in recent:
        for n in get_numbers(d): counter[n] += 1

    last_seen = {}
    for i, d in enumerate(recent):
        for n in get_numbers(d): last_seen[n] = i
    current = len(recent)
    gaps = {n: current - last_seen.get(n, -1) for n in range(1, POOL + 1)}

    expected_freq = len(recent) * PICK / POOL
    scores = {}
    for n in range(1, POOL + 1):
        freq_deficit = expected_freq - counter[n]
        gap_score    = gaps[n] / (len(recent) / 2)
        boundary_bonus = 1.2 if (n <= 5 or n >= 35) else 1.0
        mod3_bonus     = 1.1 if n % 3 == 0 else 1.0
        scores[n] = (freq_deficit * 0.4 + gap_score * 0.6) * boundary_bonus * mod3_bonus

    ranked = sorted(scores, key=lambda x: -scores[x])

    zones_selected = set()
    result = []
    for n in ranked:
        zone = 0 if n <= 13 else (1 if n <= 26 else 2)
        if len(result) < PICK:
            result.append(n)
            zones_selected.add(zone)
        if len(result) >= PICK:
            break

    if len(zones_selected) < 2 and len(result) >= PICK:
        missing_zones = set(range(3)) - zones_selected
        for mz in missing_zones:
            zr = range(1,14) if mz==0 else (range(14,27) if mz==1 else range(27,40))
            zc = sorted(zr, key=lambda x: -scores[x])
            if zc: result[-1] = zc[0]; break

    return sorted(result[:PICK])


# ─── 對照組：冷號單注 ──────────────────────────────────────────────
def predict_cold_single(hist, window=100):
    """冷號單注（近100期頻率最低的5個）— 對照組"""
    freq = Counter()
    for d in hist[-window:]:
        for n in get_numbers(d): freq[n] += 1
    cold = sorted(TOTAL_NUMBERS, key=lambda n: freq.get(n, 0))
    return sorted(cold[:PICK])


# ─── 隨機基準 ──────────────────────────────────────────────────────
def predict_random_1bet(seed_val):
    def _predict(hist):
        rng = random.Random(seed_val)
        return sorted(rng.sample(TOTAL_NUMBERS, PICK))
    return _predict


# ─── 回測引擎（Walk-Forward，嚴格無洩漏）─────────────────────────
def backtest_1bet(predict_func, all_draws, test_periods=1500, seed=42, min_train=100):
    random.seed(seed); np.random.seed(seed)
    results = []
    for i in range(test_periods):
        tidx = len(all_draws) - test_periods + i
        if tidx < min_train: continue
        target = all_draws[tidx]
        hist   = all_draws[:tidx]   # 嚴格 walk-forward
        actual = set(get_numbers(target))
        try:
            bet = predict_func(hist)
        except Exception:
            continue
        m = len(set(bet) & actual)
        results.append({'m': m, 'ge2': m >= 2, 'ge3': m >= 3})

    total = len(results)
    if total == 0:
        return {'total':0,'ge2_hits':0,'ge3_hits':0,'ge2_rate':0,'ge3_rate':0,
                'ge2_edge':0,'ge3_edge':0,'avg_match':0}
    ge2 = sum(1 for r in results if r['ge2'])
    ge3 = sum(1 for r in results if r['ge3'])
    return {
        'total':   total,
        'ge2_hits': ge2, 'ge3_hits': ge3,
        'ge2_rate': ge2/total, 'ge3_rate': ge3/total,
        'ge2_edge': ge2/total - P_GE2_1,
        'ge3_edge': ge3/total - P_GE3_1,
        'avg_match': np.mean([r['m'] for r in results]),
        'results': results,
    }


def z_test(hits, total, baseline):
    rate = hits/total
    se = math.sqrt(baseline*(1-baseline)/total)
    if se == 0: return {'z':0,'p':1.0}
    z = (rate-baseline)/se
    return {'z':z, 'p':1-scipy_stats.norm.cdf(z)}


def three_window(func, all_draws, seed=42, min_train=100):
    out = {}
    for period in [150, 500, 1500]:
        if len(all_draws) < period + min_train: continue
        r = backtest_1bet(func, all_draws, period, seed, min_train)
        r.pop('results', None)
        out[period] = {**r,
                       'z_ge2': z_test(r['ge2_hits'], r['total'], P_GE2_1),
                       'z_ge3': z_test(r['ge3_hits'], r['total'], P_GE3_1)}
    return out


# ─── Permutation Test ──────────────────────────────────────────────
def permutation_test(func, all_draws, test_periods=500, n_perms=500, seed=42, min_train=100):
    """
    vs random single-bet baseline（每次隨機選5個號）
    Signal Edge = actual_M2+ − shuffle_mean  ← 關鍵判斷
    """
    print(f"  [PERM] actual ({test_periods}p)...", end='', flush=True)
    actual = backtest_1bet(func, all_draws, test_periods, seed, min_train)
    actual_rate = actual['ge2_rate']
    print(f" M2+={actual_rate*100:.3f}% ({actual['ge2_hits']}/{actual['total']})")

    perm_rates = []
    print(f"  [PERM] {n_perms} random shuffles...", end='', flush=True)
    for i in range(n_perms):
        rf = predict_random_1bet(seed*10000 + i)
        r  = backtest_1bet(rf, all_draws, test_periods, seed+i+99999, min_train)
        perm_rates.append(r['ge2_rate'])
        if (i+1) % 100 == 0: print(f" {i+1}", end='', flush=True)
    print()

    pm  = np.mean(perm_rates)
    ps  = np.std(perm_rates, ddof=1) or 1e-10
    z   = (actual_rate - pm) / ps
    # empirical p-value（單側）
    p   = (np.sum(np.array(perm_rates) >= actual_rate) + 1) / (n_perms + 1)
    d   = z  # Cohen's d = z when using perm std

    return {
        'actual_rate':     actual_rate,
        'actual_hits':     actual['ge2_hits'],
        'actual_total':    actual['total'],
        'perm_mean':       pm,
        'perm_std':        ps,
        'perm_min':        float(np.min(perm_rates)),
        'perm_max':        float(np.max(perm_rates)),
        'z_score':         z,
        'p_value_empirical': p,
        'p_value_normal':  float(1-scipy_stats.norm.cdf(z)),
        'cohen_d':         d,
        'n_perms':         n_perms,
        'shuffle_bias':    pm - P_GE2_1,   # 分布偏好（單注應幾乎=0）
        'signal_edge':     actual_rate - pm,  # 純時序信號
        'total_edge':      actual_rate - P_GE2_1,
    }


# ─── McNemar ───────────────────────────────────────────────────────
def mcnemar(func_a, func_b, label_a, label_b, all_draws,
            test_periods=500, seed=42, min_train=100):
    a=b=c=d=0; ra=[]; rb=[]
    for i in range(test_periods):
        tidx = len(all_draws)-test_periods+i
        if tidx < min_train: continue
        actual = set(get_numbers(all_draws[tidx]))
        hist   = all_draws[:tidx]
        try:
            ba = func_a(hist); bb = func_b(hist)
        except: continue
        ha = len(set(ba)&actual) >= 2
        hb = len(set(bb)&actual) >= 2
        ra.append(ha); rb.append(hb)
        if ha and hb: a+=1
        elif ha: b+=1
        elif hb: c+=1
        else: d+=1
    chi2=0; p=1.0
    if b+c > 0:
        chi2 = (abs(b-c)-1)**2/(b+c)
        p = 1-scipy_stats.chi2.cdf(chi2, 1)
    return {'label_a':label_a,'label_b':label_b,
            'total':a+b+c+d,'both':a,'a_only':b,'b_only':c,'both_miss':d,
            'rate_a': sum(ra)/len(ra) if ra else 0,
            'rate_b': sum(rb)/len(rb) if rb else 0,
            'net':b-c,'chi2':chi2,'p':p,'sig':p<0.05}


# ═══════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════
def main():
    t0 = time.time()
    print("="*70)
    print("  539 P1_anomaly_capture (ACB) — 完整 Permutation Test")
    print("  Signal Edge 決定採納 | Walk-Forward | 500次洗牌 | 三窗口")
    print("="*70)
    all_draws = load_data()
    MIN_TRAIN = 100
    N_PERMS   = 500

    report = {
        'timestamp': datetime.now().isoformat(),
        'strategy': 'P1_anomaly_capture (ACB)',
        'description': 'freq_deficit*0.4+gap_score*0.6 × boundary_bonus × mod3_bonus + cross-zone',
        'baseline_M2+_1bet': P_GE2_1,
        'data_size': len(all_draws),
    }

    # ── 0. ACB 預測展示 ───────────────────────────────────────────
    print(f"\n{'='*70}")
    print("  [0] ACB 預測展示（最近5期）")
    print(f"{'='*70}")
    for i in range(5):
        idx  = len(all_draws) - 5 + i
        hist = all_draws[:idx]
        bet  = predict_acb(hist)
        actual = sorted(get_numbers(all_draws[idx]))
        hits = sorted(set(bet) & set(actual))
        print(f"  Draw {all_draws[idx]['draw']}: 預測={bet}  開獎={actual}  命中={hits}({len(hits)})")

    # ── 1. 三窗口穩定性 ───────────────────────────────────────────
    print(f"\n{'='*70}")
    print("  [1] THREE-WINDOW STABILITY (M2+ 主指標, 1注)")
    print(f"{'='*70}")
    tw_acb  = three_window(predict_acb,         all_draws, SEED, MIN_TRAIN)
    tw_cold = three_window(predict_cold_single,  all_draws, SEED, MIN_TRAIN)

    report['three_window_acb']  = {}
    report['three_window_cold'] = {}
    edges = {}

    print(f"\n  ▸ ACB:")
    for period in [150, 500, 1500]:
        if period not in tw_acb: continue
        r = tw_acb[period]
        print(f"    {period}p: M2+={r['ge2_rate']*100:.3f}% (edge={r['ge2_edge']*100:+.3f}%) "
              f"z={r['z_ge2']['z']:.2f} p={r['z_ge2']['p']:.4f} | "
              f"M3+={r['ge3_rate']*100:.3f}% | avg_match={r['avg_match']:.4f}")
        edges[period] = r['ge2_edge']
        report['three_window_acb'][str(period)] = {
            k:v for k,v in r.items() if not isinstance(v,dict)}

    print(f"\n  ▸ Cold (對照組):")
    for period in [150, 500, 1500]:
        if period not in tw_cold: continue
        r = tw_cold[period]
        print(f"    {period}p: M2+={r['ge2_rate']*100:.3f}% (edge={r['ge2_edge']*100:+.3f}%) "
              f"z={r['z_ge2']['z']:.2f}")
        report['three_window_cold'][str(period)] = {
            k:v for k,v in r.items() if not isinstance(v,dict)}

    tw_stable = all(edges.get(p,-1) > 0 for p in [150,500,1500] if p in tw_acb)
    if tw_stable:
        stability = 'STABLE_ALL_POSITIVE'
    elif edges.get(1500,-1) > 0 and edges.get(150,0) <= 0:
        stability = 'LATE_BLOOMER'
    elif all(e <= 0 for e in edges.values()):
        stability = 'INEFFECTIVE'
    else:
        stability = 'MIXED'
    print(f"\n  → ACB 穩定性: {stability}")
    report['stability'] = stability

    # ── 2. Permutation Test (主要驗證) ───────────────────────────
    print(f"\n{'='*70}")
    print(f"  [2] PERMUTATION TEST ({N_PERMS} shuffles, M2+ 單注)")
    print(f"  ★ Signal Edge = actual − shuffle_mean  ← 採納決定指標")
    print(f"{'='*70}")

    perm = permutation_test(predict_acb, all_draws,
                            test_periods=500, n_perms=N_PERMS,
                            seed=SEED, min_train=MIN_TRAIN)
    report['permutation'] = perm

    print(f"\n  Actual M2+:    {perm['actual_rate']*100:.4f}%  ({perm['actual_hits']}/{perm['actual_total']})")
    print(f"  Theoretical:   {P_GE2_1*100:.4f}%  (超額={perm['total_edge']*100:+.4f}%)")
    print(f"  Shuffle mean:  {perm['perm_mean']*100:.4f}% ± {perm['perm_std']*100:.4f}%")
    print(f"  Shuffle range: [{perm['perm_min']*100:.2f}%, {perm['perm_max']*100:.2f}%]")
    print(f"  Shuffle bias:  {perm['shuffle_bias']*100:+.4f}%  (單注期望≈0)")
    print(f"")
    print(f"  ★ Signal Edge: {perm['signal_edge']*100:+.4f}%")
    print(f"  ★ Total Edge:  {perm['total_edge']*100:+.4f}%")
    print(f"  z = {perm['z_score']:.3f}")
    print(f"  p (empirical) = {perm['p_value_empirical']:.4f}")
    print(f"  p (normal)    = {perm['p_value_normal']:.4f}")
    print(f"  Cohen's d     = {perm['cohen_d']:.3f}")

    sig  = perm['p_value_empirical'] <= 0.05
    bonf = perm['p_value_empirical'] <= 0.025
    se_pos = perm['signal_edge'] > 0
    print(f"")
    print(f"  Signal Edge > 0: {'✅' if se_pos else '❌ 無時序信號'}")
    print(f"  p ≤ 0.05:        {'✅ SIGNAL_DETECTED' if sig else '❌ NO_SIGNAL'}")
    print(f"  p ≤ 0.025 (Bonf):{'✅ PASS' if bonf else '❌ FAIL'}")

    # ── 3. McNemar ACB vs Cold ─────────────────────────────────
    print(f"\n{'='*70}")
    print("  [3] McNEMAR: ACB vs Cold單注 (M2+, 500p)")
    print(f"{'='*70}")
    mc = mcnemar(predict_acb, predict_cold_single, 'ACB', 'Cold',
                 all_draws, 500, SEED, MIN_TRAIN)
    report['mcnemar_vs_cold'] = mc
    print(f"  ACB  M2+: {mc['rate_a']*100:.3f}%")
    print(f"  Cold M2+: {mc['rate_b']*100:.3f}%")
    print(f"  ACB only: {mc['a_only']}  Cold only: {mc['b_only']}  Net: {mc['net']:+d}")
    print(f"  χ²={mc['chi2']:.3f}  p={mc['p']:.4f}  {'✅ SIGNIFICANT' if mc['sig'] else '◎ NOT_SIGNIFICANT'}")

    # ── 4. 參數敏感度（window 50/100/200）─────────────────────────
    print(f"\n{'='*70}")
    print("  [4] 參數敏感度: ACB window = 50 / 100 / 200")
    print(f"{'='*70}")
    for w in [50, 100, 200]:
        def _acb_w(hist, _w=w): return predict_acb(hist, window=_w)
        r = backtest_1bet(_acb_w, all_draws, 1500, SEED, MIN_TRAIN)
        print(f"  window={w:3d}: M2+={r['ge2_rate']*100:.3f}% (edge={r['ge2_edge']*100:+.3f}%)")
    report['window_sensitivity'] = {}
    for w in [50, 100, 200]:
        def _acb_w(hist, _w=w): return predict_acb(hist, window=_w)
        r = backtest_1bet(_acb_w, all_draws, 1500, SEED, MIN_TRAIN)
        report['window_sensitivity'][str(w)] = {
            'ge2_rate': r['ge2_rate'], 'ge2_edge': r['ge2_edge']}

    # ── 5. 最終決策 ──────────────────────────────────────────────
    elapsed = time.time() - t0
    print(f"\n{'='*70}")
    print("  [5] FINAL DECISION")
    print(f"{'='*70}")

    pass_criteria = {
        '三窗口全正_M2+':       tw_stable,
        'Signal_Edge_positive': se_pos,
        'perm_p_≤_0.05':        sig,
    }
    all_pass = all(pass_criteria.values())

    print(f"\n  通過標準:")
    for k, v in pass_criteria.items():
        print(f"  {'✅' if v else '❌'} {k}")

    print(f"\n  ★ ACB 三窗口 M2+ Edge:")
    for p in [150, 500, 1500]:
        if p in tw_acb:
            r = tw_acb[p]
            print(f"    {p}p: {r['ge2_rate']*100:.3f}% (edge={r['ge2_edge']*100:+.3f}%) z={r['z_ge2']['z']:.2f}")
    print(f"\n  ★ Signal Edge = {perm['signal_edge']*100:+.4f}%")
    print(f"  ★ p(empirical) = {perm['p_value_empirical']:.4f},  Cohen's d = {perm['cohen_d']:.3f}")

    if all_pass and bonf:
        decision = 'PASS → ADOPT'
        note = f'三窗口全正 + Signal Edge 正 + p={perm["p_value_empirical"]:.3f}≤0.025 Bonferroni通過。ACB 可作為第6注加入5注組合研究。'
    elif all_pass and sig:
        decision = 'PASS → PROVISIONAL'
        note = f'三窗口全正 + Signal Edge 正 + p={perm["p_value_empirical"]:.3f}≤0.05。採 PROVISIONAL 狀態，需200期滾動驗證。'
    elif tw_stable and se_pos and not sig:
        decision = 'MARGINAL → MONITOR'
        note = f'三窗口全正且 Signal Edge 正，但 p={perm["p_value_empirical"]:.3f}>0.05。信號存在但統計力不足，持續觀察。'
    elif not se_pos:
        decision = 'FAIL → 分布偏好假象'
        note = 'Signal Edge ≤ 0，三窗口Edge來自號碼分布偏好而非時序信號。歸檔。'
    else:
        decision = 'FAIL → REJECT'
        note = '未通過驗證。歸檔。'

    print(f"\n  {'='*50}")
    print(f"  最終決策: {decision}")
    print(f"  說明: {note}")
    print(f"  Runtime: {elapsed:.1f}s")
    print(f"  {'='*50}")
    print("="*70)

    report['pass_criteria']  = pass_criteria
    report['decision']       = decision
    report['decision_note']  = note
    report['elapsed']        = round(elapsed, 1)

    def _clean(obj):
        if isinstance(obj, (np.bool_,)):    return bool(obj)
        if isinstance(obj, (np.integer,)):  return int(obj)
        if isinstance(obj, (np.floating,)): return float(obj)
        if isinstance(obj, np.ndarray):     return obj.tolist()
        if isinstance(obj, dict):  return {k: _clean(v) for k,v in obj.items()}
        if isinstance(obj, list):  return [_clean(v) for v in obj]
        return obj

    out = os.path.join(_base, '..', 'backtest_acb_permutation_results.json')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(_clean(report), f, indent=2, ensure_ascii=False)
    print(f"\n[SAVED] {out}")


if __name__ == '__main__':
    main()
