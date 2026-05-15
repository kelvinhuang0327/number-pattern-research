#!/usr/bin/env python3
"""
=============================================================================
539 P0-C: 3注 F500Top5 + ColdTop5 + ColdTop5-2nd 完整驗證
=============================================================================
來源: P0-B 意外發現 — 三組對照中 3bet_F_Cold_only 最強
  1500p M2+ edge +5.16% (z=4.34), 比主策略 +3.82% 高 +1.34pp

策略設計:
  注1: Fourier 500p rank 1-5
  注2: Cold 近100期前5，排除注1
  注3: Cold 近100期前6-10（次批），排除注1+2

vs P0-B 主策略的差異:
  注3 用「冷號第二批」取代「Fourier rank 21-25」
  → 去掉 Fmid，用雙層冷號覆蓋

採納標準:
  - 三窗口全正 M2+ (150/500/1500)
  - Permutation Signal Edge > 0 AND p ≤ 0.05
  - 零重疊 (15 unique)

Output: backtest_539_3bet_f_cold_x2_results.json
=============================================================================
"""

import sys, os, json, random, math, time, warnings
from collections import Counter
from datetime import datetime

import numpy as np
from scipy import stats as scipy_stats
from scipy.fft import fft, fftfreq

warnings.filterwarnings('ignore')

_base = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_base, '..', 'lottery_api'))
sys.path.insert(0, os.path.join(_base, '..'))
from database import DatabaseManager

MAX_NUM = 39
PICK = 5
N_BETS = 3
TOTAL_NUMBERS = list(range(1, MAX_NUM + 1))
SEED = 42

from math import comb
C39_5 = comb(39, 5)
def _pmatch(k): return comb(5,k)*comb(34,5-k)/C39_5
P_MATCH = {k: _pmatch(k) for k in range(6)}
P_GE2_1 = sum(P_MATCH[k] for k in range(2,6))
P_GE3_1 = sum(P_MATCH[k] for k in range(3,6))
P_GE2_3 = 1-(1-P_GE2_1)**3
P_GE3_3 = 1-(1-P_GE3_1)**3
P_GE3_5 = 1-(1-P_GE3_1)**5

print(f"[BASELINE] 3-bet M2+ = {P_GE2_3*100:.2f}%  (理論, 主指標)")
print(f"[BASELINE] 3-bet M3+ = {P_GE3_3*100:.3f}%")
print(f"[NOTE] Shuffle均值 ≈ 32.58% (P0-B實測, 幾何覆蓋效益)")


def load_data():
    db_path = os.path.join(_base,'..','lottery_api','data','lottery_v2.db')
    db = DatabaseManager(db_path=db_path)
    raw = db.get_all_draws('DAILY_539')
    draws = sorted(raw, key=lambda x: (x['date'],x['draw']))
    print(f"[DATA] {len(draws)} draws: {draws[0]['date']} → {draws[-1]['date']}")
    return draws

def get_numbers(draw):
    nums = draw.get('numbers',[])
    if isinstance(nums,str): nums=json.loads(nums)
    return list(nums)

def fourier_scores(hist, window=500):
    h = hist[-window:] if len(hist)>=window else hist
    w = len(h)
    scores = {}
    for n in range(1, MAX_NUM+1):
        bh = np.zeros(w)
        for idx,d in enumerate(h):
            if n in get_numbers(d): bh[idx]=1
        if sum(bh)<2: scores[n]=0.0; continue
        yf=fft(bh-np.mean(bh)); xf=fftfreq(w,1)
        ip=np.where(xf>0)
        py=np.abs(yf[ip]); px=xf[ip]; pk=np.argmax(py); fv=px[pk]
        if fv==0: scores[n]=0.0; continue
        period=1/fv
        lh=np.where(bh==1)[0]
        if len(lh)==0: scores[n]=0.0; continue
        gap=(w-1)-lh[-1]
        scores[n]=1.0/(abs(gap-period)+1.0)
    return scores


# ── 主策略 ──────────────────────────────────────────────────────
def predict_3bet_f_cold_x2(hist):
    """
    P0-C 主策略: F500Top5 + ColdTop5 + Cold次批(6-10)
    注1: Fourier 500p rank 1-5
    注2: Cold 近100期 最冷5 (排除注1)
    注3: Cold 近100期 次冷5(rank 6-10) (排除注1+2)
    """
    sc = fourier_scores(hist, 500)
    ranked = [n for n in sorted(sc, key=lambda x:-sc[x]) if sc[n]>0]
    if len(ranked)<5:
        ranked.extend([n for n in TOTAL_NUMBERS if n not in ranked])

    bet1 = sorted(ranked[:5])
    excl = set(bet1)

    freq = Counter()
    for d in hist[-100:]:
        for n in get_numbers(d): freq[n]+=1
    cold_sorted = sorted(TOTAL_NUMBERS, key=lambda n: freq.get(n,0))

    bet2 = sorted([n for n in cold_sorted if n not in excl][:5])
    excl.update(bet2)

    bet3 = sorted([n for n in cold_sorted if n not in excl][:5])
    if len(bet3)<5:
        rem=[n for n in TOTAL_NUMBERS if n not in excl and n not in bet3]
        bet3=sorted((bet3+rem)[:5])

    return [bet1, bet2, bet3]


# ── 對照組 (P0-B 最優5注) ──────────────────────────────────────
def predict_5bet_f4cold(hist):
    """現有5注策略 (McNemar對照)"""
    sc = fourier_scores(hist, 500)
    ranked = [n for n in sorted(sc, key=lambda x:-sc[x]) if sc[n]>0]
    if len(ranked)<20:
        ranked.extend([n for n in TOTAL_NUMBERS if n not in ranked])
    bets = [sorted(ranked[i*5:(i+1)*5]) for i in range(4)]
    excl = set(sum(bets,[]))
    freq = Counter()
    for d in hist[-100:]:
        for n in get_numbers(d): freq[n]+=1
    cold_sorted = sorted(TOTAL_NUMBERS, key=lambda n:freq.get(n,0))
    bet5 = sorted([n for n in cold_sorted if n not in excl][:5])
    bets.append(bet5)
    return bets


def predict_random_3bet(seed_val):
    def _predict(hist):
        rng=random.Random(seed_val); pool=list(TOTAL_NUMBERS); rng.shuffle(pool)
        return [sorted(pool[i*5:(i+1)*5]) for i in range(3)]
    return _predict


# ── 回測引擎 ────────────────────────────────────────────────────
def backtest(predict_func, all_draws, test_periods=1500, seed=42, min_train=500):
    random.seed(seed); np.random.seed(seed)
    results=[]
    for i in range(test_periods):
        tidx = len(all_draws)-test_periods+i
        if tidx<min_train: continue
        target=all_draws[tidx]; hist=all_draws[:tidx]
        actual=set(get_numbers(target))
        try: bets=predict_func(hist)
        except: continue
        any_ge2=False; any_ge3=False; max_m=0
        for bet in bets:
            m=len(set(bet)&actual)
            max_m=max(max_m,m)
            if m>=2: any_ge2=True
            if m>=3: any_ge3=True
        all_nums=set(sum([list(b) for b in bets],[]))
        results.append({'ge2':any_ge2,'ge3':any_ge3,'max_m':max_m,
                        'cov':len(all_nums&actual),'unique':len(all_nums),
                        'overlap':sum(len(b) for b in bets)-len(all_nums)})
    total=len(results)
    if total==0: return {'total':0,'ge2_rate':0,'ge3_rate':0,'ge2_hits':0,'ge3_hits':0,
                         'ge2_edge':0,'ge3_edge':0,'avg_unique':0,'avg_overlap':0,'avg_cov':0}
    ge2=sum(1 for r in results if r['ge2'])
    ge3=sum(1 for r in results if r['ge3'])
    return {'total':total,'ge2_hits':ge2,'ge3_hits':ge3,
            'ge2_rate':ge2/total,'ge3_rate':ge3/total,
            'ge2_edge':ge2/total-P_GE2_3,'ge3_edge':ge3/total-P_GE3_3,
            'avg_unique':np.mean([r['unique'] for r in results]),
            'avg_overlap':np.mean([r['overlap'] for r in results]),
            'avg_cov':np.mean([r['cov'] for r in results])}


def z_test(hits, total, baseline):
    rate=hits/total; se=math.sqrt(baseline*(1-baseline)/total)
    if se==0: return {'z':0,'p':1.0}
    z=(rate-baseline)/se; p=1-scipy_stats.norm.cdf(z)
    return {'z':z,'p':p}


def three_window(func, all_draws, seed=42, min_train=500):
    out={}
    for period in [150,500,1500]:
        if len(all_draws)<period+min_train: continue
        r=backtest(func,all_draws,period,seed,min_train)
        out[period]={**r,'z_ge2':z_test(r['ge2_hits'],r['total'],P_GE2_3),
                         'z_ge3':z_test(r['ge3_hits'],r['total'],P_GE3_3)}
    return out


def permutation_test(func, all_draws, test_periods=500, n_perms=200, seed=42, min_train=500):
    print(f"  [PERM] actual ({test_periods}p)...", end='', flush=True)
    actual=backtest(func,all_draws,test_periods,seed,min_train)
    actual_rate=actual['ge2_rate']
    print(f" M2+={actual_rate*100:.2f}%")

    perm_rates=[]
    print(f"  [PERM] {n_perms} shuffles...", end='', flush=True)
    for i in range(n_perms):
        rf=predict_random_3bet(seed*1000+i)
        r=backtest(rf,all_draws,test_periods,seed+i+10000,min_train)
        perm_rates.append(r['ge2_rate'])
        if (i+1)%50==0: print(f" {i+1}",end='',flush=True)
    print()

    pm=np.mean(perm_rates); ps=np.std(perm_rates,ddof=1) or 1e-10
    z=(actual_rate-pm)/ps
    p=(np.sum(np.array(perm_rates)>=actual_rate)+1)/(n_perms+1)
    return {'actual_rate':actual_rate,'actual_hits':actual['ge2_hits'],
            'actual_total':actual['total'],
            'perm_mean':pm,'perm_std':ps,
            'perm_min':float(np.min(perm_rates)),'perm_max':float(np.max(perm_rates)),
            'z_score':z,'p_value_empirical':p,
            'p_value_normal':float(1-scipy_stats.norm.cdf(z)),
            'cohen_d':z,
            'shuffle_bias':pm-P_GE2_3,'signal_edge':actual_rate-pm,
            'total_edge':actual_rate-P_GE2_3}


def mcnemar(func_a, func_b, label_a, label_b, all_draws,
            test_periods=500, seed=42, min_train=500, thresh_a=2, thresh_b=2):
    """通用McNemar，支援不同命中門檻"""
    a=b=c=d=0; total=0; ra=[]; rb=[]
    for i in range(test_periods):
        tidx=len(all_draws)-test_periods+i
        if tidx<min_train: continue
        target=all_draws[tidx]; hist=all_draws[:tidx]
        actual=set(get_numbers(target))
        try:
            ba=func_a(hist); bb=func_b(hist)
        except: continue
        ha=any(len(set(bt)&actual)>=thresh_a for bt in ba)
        hb=any(len(set(bt)&actual)>=thresh_b for bt in bb)
        ra.append(ha); rb.append(hb)
        if ha and hb: a+=1
        elif ha and not hb: b+=1
        elif not ha and hb: c+=1
        else: d+=1
        total+=1
    chi2=0; p=1.0
    if b+c>0:
        chi2=(abs(b-c)-1)**2/(b+c)
        p=1-scipy_stats.chi2.cdf(chi2,1)
    return {'label_a':label_a,'label_b':label_b,'total':total,
            'both':a,'a_only':b,'b_only':c,'both_miss':d,
            'rate_a':sum(ra)/len(ra) if ra else 0,
            'rate_b':sum(rb)/len(rb) if rb else 0,
            'net':b-c,'chi2':chi2,'p':p,'sig':p<0.05}


# ═══════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════
def main():
    t0=time.time()
    print("="*70)
    print("  539 P0-C: 3注 F500Top5 + ColdTop5 + Cold次批(6-10)")
    print("  P0-B意外發現 — 雙冷號層設計完整驗證")
    print("  M2+ 主指標 | 三窗口 | Permutation Test | 零重疊")
    print("="*70)
    all_draws=load_data()
    MIN_TRAIN=500
    report={'timestamp':datetime.now().isoformat(),
            'strategy':'F500Top5+ColdTop5+Cold次批(rank6-10)',
            'research_context':'P0-B意外發現: 3bet_F_Cold_only 1500p M2+ +5.16%',
            'baselines':{'M2+_3bet':P_GE2_3,'M3+_3bet':P_GE3_3,'M3+_5bet':P_GE3_5,
                         'shuffle_mean_est':0.3258}}

    # ── 0. 零重疊驗證 ─────────────────────────────────────────────
    print(f"\n{'='*70}")
    print("  [0] 零重疊驗證")
    print(f"{'='*70}")
    checks=[]
    for i in range(5):
        idx=len(all_draws)-6+i; hist=all_draws[:idx]
        bets=predict_3bet_f_cold_x2(hist)
        all_n=set(sum([list(b) for b in bets],[])); u=len(all_n); ov=15-u
        checks.append(ov)
        print(f"  Draw {idx}: {[sorted(b) for b in bets]}  unique={u}  overlap={ov}")
    avg_ov=np.mean(checks)
    print(f"  平均 overlap={avg_ov:.1f}  {'✅ 零重疊' if avg_ov==0 else '⚠️ 有重疊!'}")
    report['zero_overlap']=bool(avg_ov==0)

    # ── 1. 三窗口穩定性 ──────────────────────────────────────────
    print(f"\n{'='*70}")
    print("  [1] THREE-WINDOW STABILITY (M2+ 主指標)")
    print(f"{'='*70}")
    tw=three_window(predict_3bet_f_cold_x2,all_draws,SEED,MIN_TRAIN)
    report['three_window']={}
    edges={}
    for period in [150,500,1500]:
        if period not in tw: continue
        r=tw[period]
        print(f"  {period}p: M2+={r['ge2_rate']*100:.2f}% (edge={r['ge2_edge']*100:+.2f}%) "
              f"z={r['z_ge2']['z']:.2f} p={r['z_ge2']['p']:.4f} | "
              f"M3+={r['ge3_rate']*100:.2f}% (edge={r['ge3_edge']*100:+.2f}%) | "
              f"unique={r['avg_unique']:.1f} cov={r['avg_cov']:.2f}")
        edges[period]=r['ge2_edge']
        report['three_window'][str(period)]={k:v for k,v in r.items()
            if not isinstance(v,(dict,list))}

    tw_stable=all(edges.get(p,-1)>0 for p in [150,500,1500] if p in tw)
    stability='STABLE_ALL_POSITIVE' if tw_stable else (
        'LATE_BLOOMER' if edges.get(1500,-1)>0 and edges.get(150,0)<=0 else
        'INEFFECTIVE' if all(e<=0 for e in edges.values()) else 'MIXED')
    print(f"  → M2+ 穩定性: {stability}")
    report['stability']=stability

    # ── 2. Permutation Test ──────────────────────────────────────
    print(f"\n{'='*70}")
    print("  [2] PERMUTATION TEST (vs random non-overlapping 3-bet)")
    print(f"{'='*70}")
    perm=permutation_test(predict_3bet_f_cold_x2,all_draws,500,200,SEED,MIN_TRAIN)
    report['permutation']=perm
    print(f"  Actual M2+:    {perm['actual_rate']*100:.2f}%")
    print(f"  Shuffle mean:  {perm['perm_mean']*100:.2f}% ± {perm['perm_std']*100:.3f}%")
    print(f"  Shuffle range: [{perm['perm_min']*100:.2f}%, {perm['perm_max']*100:.2f}%]")
    print(f"  Shuffle bias:  {perm['shuffle_bias']*100:+.3f}% (幾何覆蓋效益)")
    print(f"  Signal Edge:   {perm['signal_edge']*100:+.3f}%  ← 關鍵指標")
    print(f"  Total Edge:    {perm['total_edge']*100:+.3f}%")
    print(f"  z={perm['z_score']:.2f}  p(emp)={perm['p_value_empirical']:.4f}  "
          f"p(norm)={perm['p_value_normal']:.4f}  Cohen's d={perm['cohen_d']:.2f}")
    sig=perm['p_value_empirical']<=0.05
    bonf=perm['p_value_empirical']<=0.025
    print(f"  p≤0.05:  {'✅ SIGNAL_DETECTED' if sig else '❌ NO_SIGNAL'}")
    print(f"  p≤0.025: {'✅ BONF_PASS' if bonf else '❌ BONF_FAIL'}")
    print(f"  Signal Edge > 0: {'✅' if perm['signal_edge']>0 else '❌ 負Signal'}")

    # ── 3. McNemar 3注 vs 5注 ───────────────────────────────────
    print(f"\n{'='*70}")
    print("  [3] McNEMAR: 3注M2+ vs 5注M3+ (各自主指標)")
    print(f"{'='*70}")
    mc_5=mcnemar(predict_3bet_f_cold_x2,predict_5bet_f4cold,
                 '3bet_F_Cold_x2(M2+)','5bet_F4Cold(M3+)',
                 all_draws,500,SEED,MIN_TRAIN,thresh_a=2,thresh_b=3)
    report['mcnemar_vs_5bet']=mc_5
    print(f"  3注M2+: {mc_5['rate_a']*100:.2f}%  5注M3+: {mc_5['rate_b']*100:.2f}%")
    print(f"  3注獨贏: {mc_5['a_only']}  5注獨贏: {mc_5['b_only']}  Net: {mc_5['net']:+d}")
    print(f"  χ²={mc_5['chi2']:.3f}  p={mc_5['p']:.4f}  {'✅ SIGNIFICANT' if mc_5['sig'] else '◎'}")

    # 成本效益分析: 3注M2+(NT$150) vs 5注M3+(NT$250)
    rate3=mc_5['rate_a']; rate5=mc_5['rate_b']
    # 每NT$100投入命中率
    rate3_per100=rate3/1.5; rate5_per100=rate5/2.5
    print(f"\n  成本效益:")
    print(f"  3注 NT$150 M2+率: {rate3*100:.2f}%  → 每百元命中率: {rate3_per100*100:.2f}%")
    print(f"  5注 NT$250 M3+率: {rate5*100:.2f}%  → 每百元命中率: {rate5_per100*100:.2f}%")
    print(f"  相對效率 3注/5注: {rate3_per100/rate5_per100:.2f}x")

    # ── 4. McNemar 3注 vs 3注_P0-B主策略 ───────────────────────
    # P0-B 主策略內聯復現
    def p0b_func(hist):
        """P0-B主策略: F500Top5 + Cold5 + Fmid rank21-25"""
        sc2 = fourier_scores(hist, 500)
        ranked2 = [n for n in sorted(sc2, key=lambda x: -sc2[x]) if sc2[n] > 0]
        if len(ranked2) < 25:
            ranked2.extend([n for n in TOTAL_NUMBERS if n not in ranked2])
        b1 = sorted(ranked2[:5]); ex2 = set(b1)
        fr2 = Counter()
        for d in hist[-100:]:
            for n in get_numbers(d): fr2[n] += 1
        cs2 = sorted(TOTAL_NUMBERS, key=lambda n: fr2.get(n, 0))
        b2 = sorted([n for n in cs2 if n not in ex2][:5]); ex2.update(b2)
        b3p = [n for n in ranked2[20:] if n not in ex2]
        b3 = sorted(b3p[:5])
        if len(b3) < 5:
            rem = [n for n in TOTAL_NUMBERS if n not in ex2 and n not in b3]
            b3 = sorted((b3 + rem)[:5])
        return [b1, b2, b3]

    print(f"\n{'='*70}")
    print("  [4] McNEMAR: P0-C vs P0-B主策略 (M2+直接對比)")
    print(f"{'='*70}")
    mc_p0b=mcnemar(predict_3bet_f_cold_x2,p0b_func,
                   '3bet_F_Cold_x2','3bet_F_Cold_Fmid',
                   all_draws,500,SEED,MIN_TRAIN)
    report['mcnemar_vs_p0b']=mc_p0b
    print(f"  P0-C M2+: {mc_p0b['rate_a']*100:.2f}%  P0-B M2+: {mc_p0b['rate_b']*100:.2f}%")
    print(f"  P0-C獨贏: {mc_p0b['a_only']}  P0-B獨贏: {mc_p0b['b_only']}  Net: {mc_p0b['net']:+d}")
    print(f"  χ²={mc_p0b['chi2']:.3f}  p={mc_p0b['p']:.4f}  {'✅ SIGNIFICANT' if mc_p0b['sig'] else '◎'}")

    # ── 5. 最終決策 ──────────────────────────────────────────────
    elapsed=time.time()-t0
    print(f"\n{'='*70}")
    print("  [5] FINAL DECISION")
    print(f"{'='*70}")

    pass_criteria={
        '三窗口全正_M2+': tw_stable,
        'Signal_Edge_positive': perm['signal_edge']>0,
        'perm_p_le_005': sig,
        '零重疊': bool(avg_ov==0),
    }
    all_pass=all(pass_criteria.values())

    print(f"\n  通過標準:")
    for k,v in pass_criteria.items():
        print(f"  {'✅' if v else '❌'} {k}")

    print(f"\n  ★ 三窗口 M2+ Edge:")
    for p in [150,500,1500]:
        if p in tw:
            r=tw[p]
            print(f"    {p}p: {r['ge2_rate']*100:.2f}% (edge={r['ge2_edge']*100:+.2f}%) z={r['z_ge2']['z']:.2f}")
    print(f"\n  ★ Permutation: Signal Edge={perm['signal_edge']*100:+.3f}%, "
          f"z={perm['z_score']:.2f}, p={perm['p_value_empirical']:.4f}")

    if all_pass:
        decision='PASS → PROVISIONAL'
        note=f'三窗口全正 + Signal Edge > 0 + perm p={perm["p_value_empirical"]:.3f}≤0.05。採PROVISIONAL，需200期後重驗。NT$150 3注策略。'
    elif tw_stable and perm['signal_edge']>0 and not sig:
        decision='MARGINAL → MONITOR'
        note=f'三窗口全正且Signal Edge正，但p={perm["p_value_empirical"]:.3f}>0.05。信號存在但強度不足。可觀察不部署。'
    elif tw_stable and not perm['signal_edge']>0:
        decision='FAIL → 分布偏好假象'
        note='三窗口全正但Signal Edge負，與P0-B相同問題：幾何覆蓋效益偽造Edge。歸檔。'
    else:
        decision='FAIL → REJECT'
        note='未通過驗證。'

    print(f"\n  {'='*50}")
    print(f"  最終決策: {decision}")
    print(f"  說明: {note}")
    print(f"  Runtime: {elapsed:.1f}s")
    print(f"  {'='*50}")
    print("="*70)

    report['pass_criteria']=pass_criteria; report['decision']=decision
    report['decision_note']=note; report['elapsed']=round(elapsed,1)

    def _clean(obj):
        if isinstance(obj,(np.bool_,)): return bool(obj)
        if isinstance(obj,(np.integer,)): return int(obj)
        if isinstance(obj,(np.floating,)): return float(obj)
        if isinstance(obj,np.ndarray): return obj.tolist()
        if isinstance(obj,dict): return {k:_clean(v) for k,v in obj.items()}
        if isinstance(obj,list): return [_clean(v) for v in obj]
        return obj

    out=os.path.join(_base,'..','backtest_539_3bet_f_cold_x2_results.json')
    with open(out,'w',encoding='utf-8') as f:
        json.dump(_clean(report),f,indent=2,ensure_ascii=False)
    print(f"\n[SAVED] {out}")

if __name__=='__main__':
    main()
