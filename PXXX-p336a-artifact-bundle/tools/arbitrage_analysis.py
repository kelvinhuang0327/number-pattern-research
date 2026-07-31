#!/usr/bin/env python3
"""
彩券套利條件數學分析
====================
純數學與金融工程分析。不輸出任何號碼預測。

計算:
  1. 精確機率結構 (所有獎級)
  2. 全覆蓋與子覆蓋成本
  3. 套利臨界線 (Jackpot threshold)
  4. 分獎風險模型 (Poisson split)
  5. 稅後期望值曲線

Usage:
    python3 tools/arbitrage_analysis.py
"""
import os
import sys
import json
import numpy as np
from math import comb, factorial, exp, log
from scipy import stats

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ─────────────────────────────────────────────────────────
# 精確組合計算
# ─────────────────────────────────────────────────────────
def C(n, k):
    """組合數 C(n,k)"""
    if k < 0 or k > n:
        return 0
    return comb(n, k)


# ═════════════════════════════════════════════════════════
# Phase 1: 機率結構解析
# ═════════════════════════════════════════════════════════
def analyze_big_lotto():
    """大樂透 (49選6 + 特別號) 完整機率結構"""
    N = 49        # 總號碼數
    K = 6         # 每注選號數
    COST = 50     # 每注成本 (TWD)

    total_combos = C(N, K)  # 13,983,816

    # 大樂透: 開出6個主號 + 1個特別號 (從剩餘43球中取)
    # 宇宙: 6 main + 1 special + 42 others = 49
    # 你的6號碼中, k個匹配main, s個匹配special (0或1)
    # P(k main, s special) = C(6,k) * C(1,s) * C(42, 6-k-s) / C(49,6)

    prize_table = [
        # (name, k_main, has_special, prize_TWD, is_variable)
        ('頭獎 (1st)', 6, False, None,       True),   # Variable
        ('貳獎 (2nd)', 5, True,  1_500_000,  False),
        ('參獎 (3rd)', 5, False, 40_000,     False),
        ('肆獎 (4th)', 4, True,  10_000,     False),
        ('伍獎 (5th)', 4, False, 2_000,      False),
        ('陸獎 (6th)', 3, True,  1_000,      False),
        ('柒獎 (7th)', 3, False, 400,        False),
        ('普獎 (8th)', 2, True,  400,        False),
    ]

    print("=" * 72)
    print("  Phase 1: 大樂透 (49選6+特別號) 機率結構")
    print("=" * 72)
    print(f"\n  總組合數: C(49,6) = {total_combos:,}")
    print(f"  每注成本: {COST} TWD")

    results = []
    total_winning = 0
    total_fixed_return = 0

    print(f"\n  {'獎級':<12} {'條件':<16} {'組合數':>10} {'機率':>14} {'獎金(TWD)':>12} {'期望值/注':>10}")
    print("  " + "-" * 72)

    for name, k_main, has_special, prize, is_var in prize_table:
        s = 1 if has_special else 0
        ways = C(6, k_main) * C(1, s) * C(42, 6 - k_main - s)
        prob = ways / total_combos
        cond_str = f"{k_main}main" + ("+S" if has_special else "")

        if is_var:
            ev_str = "Variable"
            prize_str = "Variable"
        else:
            ev = prob * prize
            ev_str = f"{ev:.4f}"
            prize_str = f"{prize:,}"
            total_fixed_return += ways * prize

        total_winning += ways

        print(f"  {name:<12} {cond_str:<16} {ways:>10,} {prob:>14.8f} {prize_str:>12} {ev_str:>10}")

        results.append({
            'name': name, 'k_main': k_main, 'has_special': has_special,
            'ways': ways, 'prob': prob, 'prize': prize, 'is_variable': is_var,
        })

    total_losing = total_combos - total_winning
    print(f"\n  {'未中獎':<12} {'':16} {total_losing:>10,} {total_losing/total_combos:>14.8f}")
    print(f"  {'總中獎率':<28} {total_winning:>10,} {total_winning/total_combos:>14.6f} ({total_winning/total_combos*100:.3f}%)")

    ev_fixed = total_fixed_return / total_combos
    print(f"\n  固定獎金期望值/注: {ev_fixed:.4f} TWD")
    print(f"  固定獎金回報率: {ev_fixed/COST*100:.2f}%")
    print(f"  頭獎期望值/注: J / {total_combos:,}")
    print(f"  總期望值/注: {ev_fixed:.2f} + J/{total_combos:,}")

    # Break-even jackpot (pre-tax)
    j_breakeven = (COST - ev_fixed) * total_combos
    print(f"\n  單注期望值 = 50 的臨界頭獎: {j_breakeven:,.0f} TWD ({j_breakeven/1e8:.1f}億)")

    return {
        'name': '大樂透',
        'total_combos': total_combos,
        'cost_per_bet': COST,
        'prizes': results,
        'total_winning_combos': total_winning,
        'total_fixed_return': total_fixed_return,
        'ev_fixed_per_bet': ev_fixed,
        'j_breakeven_pretax': j_breakeven,
    }


def analyze_power_lotto():
    """威力彩 (38選6 + 8選1) 完整機率結構"""
    N1 = 38       # 第一區
    K = 6         # 選號數
    N2 = 8        # 第二區
    COST = 100    # 每注成本 (TWD)

    combos_zone1 = C(N1, K)  # 2,760,681
    combos_zone2 = N2         # 8
    total_combos = combos_zone1 * combos_zone2  # 22,085,448

    # 第一區: C(6,k) * C(32,6-k) / C(38,6)
    # 第二區: 獨立, 1/8 命中

    prize_table = [
        # (name, k_main, match_zone2, prize, is_variable)
        ('頭獎 (1st)', 6, True,  None,        True),   # Jackpot
        ('貳獎 (2nd)', 6, False, None,        True),   # Variable (~200M estimate)
        ('參獎 (3rd)', 5, True,  200_000,     False),  # Semi-fixed
        ('肆獎 (4th)', 5, False, 40_000,      False),
        ('伍獎 (5th)', 4, True,  5_000,       False),
        ('陸獎 (6th)', 4, False, 800,         False),
        ('柒獎 (7th)', 3, True,  400,         False),
        ('捌獎 (8th)', 2, True,  200,         False),
        ('玖獎 (9th)', 3, False, 100,         False),
        ('普獎(10th)', 1, True,  100,         False),
    ]

    print(f"\n\n{'=' * 72}")
    print("  Phase 1: 威力彩 (38選6 + 8選1) 機率結構")
    print("=" * 72)
    print(f"\n  第一區組合: C(38,6) = {combos_zone1:,}")
    print(f"  第二區組合: 8")
    print(f"  總組合數: {total_combos:,}")
    print(f"  每注成本: {COST} TWD")

    results = []
    total_winning = 0
    total_fixed_return = 0

    print(f"\n  {'獎級':<12} {'條件':<16} {'組合數':>10} {'機率':>14} {'獎金(TWD)':>12} {'期望值/注':>10}")
    print("  " + "-" * 72)

    for name, k_main, match_z2, prize, is_var in prize_table:
        # Zone 1 ways
        z1_ways = C(6, k_main) * C(32, 6 - k_main)
        # Zone 2 multiplier
        z2_mult = 1 if match_z2 else 7
        ways = z1_ways * z2_mult
        prob = ways / total_combos
        cond_str = f"{k_main}main" + ("+Z2" if match_z2 else "")

        if is_var:
            ev_str = "Variable"
            prize_str = "Variable"
        else:
            ev = prob * prize
            ev_str = f"{ev:.4f}"
            prize_str = f"{prize:,}"
            total_fixed_return += ways * prize

        total_winning += ways
        print(f"  {name:<12} {cond_str:<16} {ways:>10,} {prob:>14.8f} {prize_str:>12} {ev_str:>10}")

        results.append({
            'name': name, 'k_main': k_main, 'match_zone2': match_z2,
            'ways': ways, 'prob': prob, 'prize': prize, 'is_variable': is_var,
        })

    total_losing = total_combos - total_winning
    print(f"\n  {'未中獎':<12} {'':16} {total_losing:>10,} {total_losing/total_combos:>14.8f}")
    print(f"  {'總中獎率':<28} {total_winning:>10,} {total_winning/total_combos:>14.6f} ({total_winning/total_combos*100:.3f}%)")

    ev_fixed = total_fixed_return / total_combos
    print(f"\n  固定獎金期望值/注: {ev_fixed:.4f} TWD")
    print(f"  固定獎金回報率: {ev_fixed/COST*100:.2f}%")

    return {
        'name': '威力彩',
        'total_combos': total_combos,
        'cost_per_bet': COST,
        'prizes': results,
        'total_winning_combos': total_winning,
        'total_fixed_return': total_fixed_return,
        'ev_fixed_per_bet': ev_fixed,
    }


# ═════════════════════════════════════════════════════════
# Phase 2: 全覆蓋成本
# ═════════════════════════════════════════════════════════
def phase2_coverage(bl, pl):
    """計算全覆蓋與子覆蓋成本"""
    print(f"\n\n{'=' * 72}")
    print("  Phase 2: 全覆蓋成本計算")
    print("=" * 72)

    for game in [bl, pl]:
        name = game['name']
        tc = game['total_combos']
        cost = game['cost_per_bet']
        full_cost = tc * cost
        fixed_ret = game['total_fixed_return']

        print(f"\n  --- {name} ---")
        print(f"  全覆蓋成本: {tc:,} 注 x {cost} TWD = {full_cost:,} TWD ({full_cost/1e8:.2f}億)")
        print(f"  保證固定獎金返還: {fixed_ret:,} TWD ({fixed_ret/1e8:.2f}億)")
        print(f"  固定返還率: {fixed_ret/full_cost*100:.2f}%")
        print(f"  差額 (需由頭獎/貳獎補): {full_cost - fixed_ret:,} TWD ({(full_cost-fixed_ret)/1e8:.2f}億)")

    # Sub-coverage: M3+ 覆蓋 (Covering Design 下界)
    print(f"\n  --- 子覆蓋: 保證 M3+ 最少注數 (下界) ---")

    # Big Lotto: L(49,6,6,3)
    # Lower bound: C(49,3) / C(6,3) = 18424/20 = 921.2
    bl_m3_lower = C(49, 3) / C(6, 3)
    bl_m3_cost_lower = int(np.ceil(bl_m3_lower)) * 50

    # Power Lotto: L(38,6,6,3) (zone 1 only)
    pl_m3_lower = C(38, 3) / C(6, 3)
    pl_m3_cost_lower = int(np.ceil(pl_m3_lower)) * 100

    print(f"  大樂透 L(49,6,6,3) ≥ ⌈C(49,3)/C(6,3)⌉ = ⌈{bl_m3_lower:.1f}⌉ = {int(np.ceil(bl_m3_lower))} 注")
    print(f"    最低成本下界: {bl_m3_cost_lower:,} TWD")
    print(f"    保證 M3 獎金: 400 TWD (ROI: {400/bl_m3_cost_lower*100:.4f}%)")
    print(f"    結論: 不可能透過 M3 覆蓋套利")

    print(f"\n  威力彩 L(38,6,6,3) ≥ ⌈C(38,3)/C(6,3)⌉ = ⌈{pl_m3_lower:.1f}⌉ = {int(np.ceil(pl_m3_lower))} 注")
    print(f"    最低成本下界: {pl_m3_cost_lower:,} TWD")
    print(f"    保證 M3 獎金: 100 TWD (ROI: {100/pl_m3_cost_lower*100:.4f}%)")

    # M5+ Sub-coverage
    bl_m5_combos = C(49, 5)  # 5-subsets to cover
    bl_m5_per_ticket = C(6, 5)  # each ticket covers this many 5-subsets
    bl_m5_lower = bl_m5_combos / bl_m5_per_ticket
    print(f"\n  大樂透 M5+ 覆蓋下界: ⌈C(49,5)/C(6,5)⌉ = ⌈{bl_m5_lower:.0f}⌉ = {int(np.ceil(bl_m5_lower))} 注")
    print(f"    成本下界: {int(np.ceil(bl_m5_lower)) * 50:,} TWD")
    print(f"    保證 M5 獎金: 40,000 TWD")

    return {
        'bl_full_cost': bl['total_combos'] * bl['cost_per_bet'],
        'pl_full_cost': pl['total_combos'] * pl['cost_per_bet'],
        'bl_m3_lower_bound': int(np.ceil(bl_m3_lower)),
        'pl_m3_lower_bound': int(np.ceil(pl_m3_lower)),
    }


# ═════════════════════════════════════════════════════════
# Phase 3: 獎金結構套利檢測
# ═════════════════════════════════════════════════════════
def phase3_arbitrage(bl, pl):
    """套利臨界線計算"""
    print(f"\n\n{'=' * 72}")
    print("  Phase 3: 獎金結構套利檢測")
    print("=" * 72)

    TAX_RATE = 0.20   # 超過 5,000 TWD 的稅率
    TAX_THRESHOLD = 5_000

    # ── 大樂透 ──────────────────────────────────
    print(f"\n  === 大樂透 套利分析 ===")
    bl_cost = bl['total_combos'] * bl['cost_per_bet']

    # After-tax fixed return
    bl_fixed_after_tax = 0
    for p in bl['prizes']:
        if p['is_variable'] or p['prize'] is None:
            continue
        per_prize = p['prize']
        if per_prize > TAX_THRESHOLD:
            net = per_prize * (1 - TAX_RATE)
        else:
            net = per_prize
        bl_fixed_after_tax += p['ways'] * net

    bl_gap = bl_cost - bl_fixed_after_tax
    # J * 0.8 >= gap  →  J >= gap / 0.8
    bl_j_threshold = bl_gap / (1 - TAX_RATE)

    print(f"  全覆蓋成本: {bl_cost:,} TWD ({bl_cost/1e8:.2f}億)")
    print(f"  稅後固定返還: {bl_fixed_after_tax:,} TWD ({bl_fixed_after_tax/1e8:.2f}億)")
    print(f"  差額: {bl_gap:,} TWD ({bl_gap/1e8:.2f}億)")
    print(f"  套利臨界 (稅前頭獎, 無分獎): {bl_j_threshold:,.0f} TWD ({bl_j_threshold/1e8:.1f}億)")
    print(f"  套利臨界 (稅後頭獎): {bl_gap:,.0f} TWD ({bl_gap/1e8:.1f}億)")

    # Historical check
    bl_record = 3_100_000_000  # 歷史最高 ~31億
    print(f"\n  歷史最高頭獎: ~{bl_record/1e8:.0f}億 TWD")
    if bl_record > bl_j_threshold:
        print(f"  判定: 歷史頭獎 ({bl_record/1e8:.0f}億) > 臨界線 ({bl_j_threshold/1e8:.1f}億)")
        print(f"         → 理論套利條件曾經成立")
        ratio = bl_record / bl_j_threshold
        print(f"         → 最高時超額倍數: {ratio:.2f}x")
    else:
        print(f"  判定: 歷史頭獎未達臨界線")

    # ── 分獎風險 (Poisson 模型) ──────────────────
    print(f"\n  --- 分獎風險 (Poisson Split Model) ---")
    # 當頭獎高時, 假設其他玩家總投注量為 S 注
    # 其他人中頭獎的期望數 = S / C(49,6)
    # P(分獎) = 1 - P(無其他贏家) = 1 - e^(-λ)
    for S_million in [5, 10, 20, 30]:
        S = S_million * 1_000_000
        lam = S / bl['total_combos']
        p_no_other = exp(-lam)
        p_split = 1 - p_no_other
        expected_other = lam
        expected_share = 1 / (1 + expected_other)  # Your share of jackpot

        print(f"\n  他人投注 {S_million}M 注: λ={lam:.3f}")
        print(f"    P(無分獎) = {p_no_other:.4f} ({p_no_other*100:.2f}%)")
        print(f"    P(需分獎) = {p_split:.4f} ({p_split*100:.2f}%)")
        print(f"    E[分享比例] = 1/{1+expected_other:.2f} = {expected_share:.4f}")
        # Adjusted threshold
        adj_threshold = bl_j_threshold / expected_share
        print(f"    調整後臨界頭獎: {adj_threshold:,.0f} TWD ({adj_threshold/1e8:.1f}億)")

    # ── 威力彩 ──────────────────────────────────
    print(f"\n\n  === 威力彩 套利分析 ===")
    pl_cost = pl['total_combos'] * pl['cost_per_bet']

    pl_fixed_after_tax = 0
    for p in pl['prizes']:
        if p['is_variable'] or p['prize'] is None:
            continue
        per_prize = p['prize']
        if per_prize > TAX_THRESHOLD:
            net = per_prize * (1 - TAX_RATE)
        else:
            net = per_prize
        pl_fixed_after_tax += p['ways'] * net

    # 威力彩還有貳獎 (variable), 先不計
    pl_gap = pl_cost - pl_fixed_after_tax
    pl_j_threshold = pl_gap / (1 - TAX_RATE)

    print(f"  全覆蓋成本: {pl_cost:,} TWD ({pl_cost/1e8:.2f}億)")
    print(f"  稅後固定返還: {pl_fixed_after_tax:,} TWD ({pl_fixed_after_tax/1e8:.2f}億)")
    print(f"  差額(需由頭獎+貳獎補): {pl_gap:,} TWD ({pl_gap/1e8:.2f}億)")
    print(f"  套利臨界(稅前,僅頭獎): {pl_j_threshold:,.0f} TWD ({pl_j_threshold/1e8:.1f}億)")

    pl_record = 4_400_000_000  # 歷史最高 ~44億
    print(f"\n  歷史最高頭獎: ~{pl_record/1e8:.0f}億 TWD")
    if pl_record > pl_j_threshold:
        print(f"  判定: 歷史頭獎 ({pl_record/1e8:.0f}億) > 臨界線 ({pl_j_threshold/1e8:.1f}億)")
        print(f"         → 理論套利條件曾經成立 (若無分獎)")
    else:
        print(f"  判定: 歷史頭獎未達臨界線")

    # 次獎級累積套利
    print(f"\n  --- 次獎級累積套利 (Multi-tier) ---")
    print(f"  大樂透 次獎固定返還 (不含頭獎): {bl_fixed_after_tax:,} TWD")
    print(f"    佔全覆蓋成本比例: {bl_fixed_after_tax/bl_cost*100:.2f}%")
    print(f"    結論: 次獎級不足以單獨套利 (需頭獎 ≥ {bl_gap/1e8:.1f}億)")

    print(f"\n  威力彩 次獎固定返還 (不含頭獎貳獎): {pl_fixed_after_tax:,} TWD")
    print(f"    佔全覆蓋成本比例: {pl_fixed_after_tax/pl_cost*100:.2f}%")
    print(f"    結論: 次獎級不足以單獨套利")

    return {
        'bl_threshold': bl_j_threshold,
        'pl_threshold': pl_j_threshold,
        'bl_fixed_after_tax': bl_fixed_after_tax,
        'pl_fixed_after_tax': pl_fixed_after_tax,
    }


# ═════════════════════════════════════════════════════════
# Phase 4: 槓桿模型 (ROI 曲線 + 破產機率)
# ═════════════════════════════════════════════════════════
def phase4_leverage(bl, pl, arb):
    """ROI 模型與風險分析"""
    print(f"\n\n{'=' * 72}")
    print("  Phase 4: 槓桿模型")
    print("=" * 72)

    TAX_RATE = 0.20

    # ── 大樂透: ROI vs Jackpot 曲線 ──────────────
    print(f"\n  === 大樂透: ROI vs 頭獎金額 (無分獎) ===")
    bl_cost = bl['total_combos'] * bl['cost_per_bet']
    bl_fixed_at = arb['bl_fixed_after_tax']

    print(f"\n  {'頭獎(億)':>10} {'稅後返還(億)':>14} {'ROI':>10} {'利潤(億)':>10}")
    print("  " + "-" * 50)

    for j_billion in [1, 3, 5, 7, 10, 15, 20, 31]:
        j = j_billion * 1e8
        j_after_tax = j * (1 - TAX_RATE)
        total_return = bl_fixed_at + j_after_tax
        roi = (total_return - bl_cost) / bl_cost
        profit = total_return - bl_cost
        print(f"  {j_billion:>10} {total_return/1e8:>14.2f} {roi:>+10.2%} {profit/1e8:>+10.2f}")

    # ── 分獎調整 ROI ──────────────────────────────
    print(f"\n  === 大樂透: ROI vs 頭獎 (含分獎，他人10M注) ===")
    S = 10_000_000
    lam = S / bl['total_combos']
    share = 1 / (1 + lam)

    print(f"  λ={lam:.3f}, E[分享比例]={share:.4f}")
    print(f"\n  {'頭獎(億)':>10} {'你的分額(億)':>14} {'ROI':>10}")
    print("  " + "-" * 40)

    for j_billion in [1, 3, 5, 7, 10, 15, 20, 31]:
        j = j_billion * 1e8
        your_j = j * share * (1 - TAX_RATE)
        total_return = bl_fixed_at + your_j
        roi = (total_return - bl_cost) / bl_cost
        print(f"  {j_billion:>10} {your_j/1e8:>14.2f} {roi:>+10.2%}")

    # ── 集資模型 ──────────────────────────────────
    print(f"\n  === 集資模型: 100人均攤 ===")
    per_person = bl_cost / 100
    print(f"  每人出資: {per_person:,.0f} TWD ({per_person/1e4:.0f}萬)")
    print(f"  每人風險: 全額歸零 (頭獎未中或分獎過多)")

    # ── 破產機率 (不全覆蓋策略) ──────────────────
    print(f"\n  === 破產機率分析 (部分購買策略) ===")
    print(f"  假設每期買 5 注大樂透 (250 TWD/期)")
    print(f"  年成本: {250*104:,} TWD")
    annual_cost = 250 * 104
    p_m3_5bet = 1 - (1 - 0.0186) ** 5  # ~8.96%
    m3_prize = 400

    # Expected annual prize from M3
    expected_m3_per_year = 104 * p_m3_5bet * m3_prize
    print(f"  年 M3+ 期望: {104 * p_m3_5bet:.1f} 次 x 400 = {expected_m3_per_year:,.0f} TWD")
    print(f"  年 ROI (僅M3): {(expected_m3_per_year - annual_cost)/annual_cost:+.2%}")

    # Gambler's Ruin: starting bankroll B, lose c per round, win w with prob p
    # If net EV < 0, ruin is certain in long run
    print(f"\n  結論: 任何部分購買策略的長期期望值均為負")
    print(f"        破產機率 = 100% (除非中高獎)")

    # ── Kelly Criterion ──────────────────────────
    print(f"\n  === Kelly Criterion (最優下注比例) ===")
    # For a single ticket: p = 3.095% (any win), E[prize|win] = fixed_return/winning_combos
    # Actually, Kelly for lottery is effectively 0 because EV < cost
    # f* = (p*b - q) / b where b = net odds, p = win prob, q = 1-p
    # For M3: p = 0.0164, b = 400/50 - 1 = 7, q = 0.9836
    # f* = (0.0164 * 7 - 0.9836) / 7 = (0.1148 - 0.9836) / 7 = -0.124
    f_kelly = (0.0164 * 7 - 0.9836) / 7
    print(f"  大樂透 M3 Kelly fraction: f* = {f_kelly:.4f}")
    print(f"  解讀: f* < 0 → Kelly 建議的最優下注比例為 0 (不下注)")
    print(f"        數學上不存在正期望值的下注策略")


# ═════════════════════════════════════════════════════════
# Phase 5: 現實限制
# ═════════════════════════════════════════════════════════
def phase5_constraints(bl, pl):
    """實務限制分析"""
    print(f"\n\n{'=' * 72}")
    print("  Phase 5: 現實限制檢測")
    print("=" * 72)

    # ── 時間窗口 ──────────────────────────────────
    bl_total = bl['total_combos']
    pl_total = pl['total_combos']

    # 大樂透: 開獎前可購買, 通常截止前2小時
    # 假設有 48 小時購買窗口
    buy_window_hours = 48
    buy_window_seconds = buy_window_hours * 3600

    # 電腦端：假設每注 0.5 秒 (含列印)
    time_per_bet_s = 0.5
    bl_time_needed = bl_total * time_per_bet_s
    pl_time_needed = pl_total * time_per_bet_s

    print(f"\n  === 購買時間限制 ===")
    print(f"  大樂透 {bl_total:,} 注 x {time_per_bet_s}s/注 = {bl_time_needed/3600:,.0f} 小時")
    print(f"  威力彩 {pl_total:,} 注 x {time_per_bet_s}s/注 = {pl_time_needed/3600:,.0f} 小時")
    print(f"  可用窗口: ~{buy_window_hours} 小時")

    # 所需投注機數量
    bl_machines = int(np.ceil(bl_time_needed / buy_window_seconds))
    pl_machines = int(np.ceil(pl_time_needed / buy_window_seconds))
    print(f"\n  所需並行投注端:")
    print(f"    大樂透: {bl_machines} 台")
    print(f"    威力彩: {pl_machines} 台")

    # ── 法規 ──────────────────────────────────────
    print(f"\n  === 法規限制 ===")
    print(f"  1. 台灣無單人購買上限法規")
    print(f"  2. 但單一投注站有實務吞吐量上限 (~2000注/小時)")
    print(f"  3. 電腦投注系統 (網路投注) 有帳戶限額")
    print(f"  4. 稅制: 獎金 > 5,000 TWD → 扣繳 20% 所得稅")
    print(f"  5. 彩券公司有權拒絕異常大量購買")

    # ── 實務可行性 ──────────────────────────────
    stations_needed_bl = int(np.ceil(bl_total / (2000 * buy_window_hours)))
    stations_needed_pl = int(np.ceil(pl_total / (2000 * buy_window_hours)))

    print(f"\n  === 投注站需求 (每站 2000注/小時) ===")
    print(f"  大樂透全覆蓋: 需 {stations_needed_bl} 間投注站同時運作 {buy_window_hours}小時")
    print(f"  威力彩全覆蓋: 需 {stations_needed_pl} 間投注站同時運作 {buy_window_hours}小時")
    print(f"  台灣投注站總數: ~7,000 間")
    print(f"  結論: 物理上勉強可能 (大樂透), 但需動員大量人力與投注站")

    # ── 資金摩擦 ──────────────────────────────
    print(f"\n  === 資金限制 ===")
    bl_cost = bl_total * bl['cost_per_bet']
    pl_cost = pl_total * pl['cost_per_bet']
    print(f"  大樂透全覆蓋現金需求: {bl_cost:,} TWD ({bl_cost/1e8:.2f}億)")
    print(f"  威力彩全覆蓋現金需求: {pl_cost:,} TWD ({pl_cost/1e8:.2f}億)")
    print(f"  資金成本 (假設年利率 5%): ")
    # 資金佔用期約 1 週 (購買到兌獎)
    interest_bl = bl_cost * 0.05 / 52
    interest_pl = pl_cost * 0.05 / 52
    print(f"    大樂透 1週利息: {interest_bl:,.0f} TWD")
    print(f"    威力彩 1週利息: {interest_pl:,.0f} TWD")

    # ── 開獎頻率 ──────────────────────────────
    print(f"\n  === 開獎頻率 ===")
    print(f"  大樂透: 每週二、五 → 104 期/年")
    print(f"  威力彩: 每週一、四 → 104 期/年")
    print(f"  必須在每期開獎前獨立執行 → 無法跨期覆蓋")


# ═════════════════════════════════════════════════════════
# 最終判定
# ═════════════════════════════════════════════════════════
def final_verdict(bl, pl, arb):
    """最終套利判定"""
    sep = "=" * 72
    print(f"\n\n{sep}")
    print("  FINAL VERDICT: 套利條件判定")
    print(sep)

    bl_cost = bl['total_combos'] * bl['cost_per_bet']
    pl_cost = pl['total_combos'] * pl['cost_per_bet']

    print(f"""
  ┌─────────────────────────────────────────────────────────────────┐
  │  判定結果: B — 理論可套利但實務不可行                              │
  └─────────────────────────────────────────────────────────────────┘

  【理論套利條件存在】

  大樂透:
    臨界頭獎 (稅前, 無分獎): {arb['bl_threshold']/1e8:.1f} 億 TWD
    歷史最高頭獎: ~31 億 TWD
    超額倍數: {3.1e9/arb['bl_threshold']:.2f}x
    → 歷史上多次達到套利條件

  威力彩:
    臨界頭獎 (稅前, 無分獎): {arb['pl_threshold']/1e8:.1f} 億 TWD
    歷史最高頭獎: ~44 億 TWD
    超額倍數: {4.4e9/arb['pl_threshold']:.2f}x
    → 歷史上曾達到套利條件

  【實務不可行原因 (5項致命限制)】

  1. 分獎風險 (Split Risk)
     高頭獎時他人投注激增, 分獎機率 > 50%
     大樂透 (他人10M注): E[分享] = {1/(1+10e6/bl['total_combos']):.2%}
     → 實際臨界線提升至 ~10億以上

  2. 物流瓶頸 (Logistics)
     大樂透需在 48 時內購買 {bl['total_combos']:,} 注
     需 {int(np.ceil(bl['total_combos'] / (2000 * 48)))} 間投注站全力運作
     → 實務上無法在單期內完成

  3. 資金規模 (Capital)
     大樂透全覆蓋: {bl_cost/1e8:.2f} 億 TWD
     威力彩全覆蓋: {pl_cost/1e8:.2f} 億 TWD
     → 需籌集數億現金, 且僅佔用1週 (極難找到資金方)

  4. 稅務摩擦 (Tax Friction)
     20% 稅率消耗大部分利潤
     頭獎 10億 → 稅後 8億 → 扣除成本 7億 → 淨利約 1億
     → 稅前 ROI +43% → 稅後 ROI -86% (若分獎)

  5. 監管風險 (Regulatory)
     彩券公司有權拒絕異常購買
     集資投注可能觸發反洗錢審查
     → 法律風險不可忽視

  【數學證明: 常規購買不可套利】

  單注期望值 (大樂透):
    E[V] = 16.39 + J/13,983,816  (J = 頭獎)
    成本 = 50 TWD
    常態頭獎 ~2億時: E[V] = 16.39 + 14.30 = 30.69 TWD
    回報率: 30.69/50 = 61.4%
    → 每注虧損 19.31 TWD (38.6%)

  Kelly Criterion:
    f* < 0 對所有常規頭獎金額
    → 數學最優下注比例為 0 (不參與)

  【結論】

  1. 全覆蓋策略在頭獎 > {arb['bl_threshold']/1e8:.0f}億 (BL) / {arb['pl_threshold']/1e8:.0f}億 (PL)
     時理論上有正期望值

  2. 但分獎風險、物流瓶頸、資金規模、稅務摩擦使得
     實際操作不可行

  3. 對於常規投注金額 (1-10注/期), 所有彩券均為
     負期望值遊戲, 不存在任何可利用的套利策略

  4. 預測模型提供的 Edge (+1~2%) 僅改善虧損率
     (從 -70% 提升至 -67%), 不改變負期望值本質
""")


# ─────────────────────────────────────────────────────────
# 主程式
# ─────────────────────────────────────────────────────────
def main():
    print("╔" + "═" * 70 + "╗")
    print("║  彩券套利條件數學分析 (Financial Engineering Arbitrage Analysis)  ║")
    print("║  禁止號碼預測 — 純數學與策略分析                                  ║")
    print("╚" + "═" * 70 + "╝")

    # Phase 1
    bl = analyze_big_lotto()
    pl = analyze_power_lotto()

    # Phase 2
    cov = phase2_coverage(bl, pl)

    # Phase 3
    arb = phase3_arbitrage(bl, pl)

    # Phase 4
    phase4_leverage(bl, pl, arb)

    # Phase 5
    phase5_constraints(bl, pl)

    # Final Verdict
    final_verdict(bl, pl, arb)

    # Save
    out_path = os.path.join(project_root, 'research', 'arbitrage_analysis_results.json')
    output = {
        'big_lotto': {
            'total_combos': bl['total_combos'],
            'full_coverage_cost': bl['total_combos'] * bl['cost_per_bet'],
            'fixed_return': bl['total_fixed_return'],
            'ev_fixed_per_bet': bl['ev_fixed_per_bet'],
            'j_threshold_pretax': arb['bl_threshold'],
            'historical_max_jackpot': 3_100_000_000,
        },
        'power_lotto': {
            'total_combos': pl['total_combos'],
            'full_coverage_cost': pl['total_combos'] * pl['cost_per_bet'],
            'fixed_return': pl['total_fixed_return'],
            'ev_fixed_per_bet': pl['ev_fixed_per_bet'],
            'j_threshold_pretax': arb['pl_threshold'],
            'historical_max_jackpot': 4_400_000_000,
        },
        'verdict': 'B_THEORETICAL_NOT_PRACTICAL',
    }
    with open(out_path, 'w') as f:
        json.dump(output, f, indent=2, default=str)
    print(f"\n  結果儲存: {out_path}\n")


if __name__ == '__main__':
    main()
