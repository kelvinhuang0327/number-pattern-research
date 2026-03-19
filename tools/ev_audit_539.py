#!/usr/bin/env python3
"""
539 Expected Value Mathematical Audit
=====================================
Independent verification of 今彩539 EV calculation.

Previous research claimed +40.93% ROI (EV = NTD 70.47 vs cost NTD 50).
This audit verifies whether that finding is correct.

Tasks:
1. Compute exact combinatorial probabilities for each prize tier
2. Test BOTH potential prize structures (code version vs official version)
3. Compute EV = Σ(probability × prize)
4. Cross-validate with Monte Carlo (10M+ simulations)
5. Include tax and prize splitting analysis
6. Produce detailed audit report
"""

import math
import numpy as np
import time
import json
import os

SEED = 42
np.random.seed(SEED)
rng = np.random.default_rng(SEED)

# ============================================================
# SECTION 1: Exact Combinatorial Probabilities
# ============================================================
# 今彩539: Pick 5 numbers from 1-39, no special number
# Total combinations: C(39, 5)

MAX_NUM = 39
PICK = 5
TOTAL_COMBOS = math.comb(MAX_NUM, PICK)  # 575,757
COST_PER_BET = 50  # NTD

print("=" * 72)
print("  539 EXPECTED VALUE MATHEMATICAL AUDIT")
print("=" * 72)
print(f"\n  Game: 今彩539 (Daily 539)")
print(f"  Pick {PICK} from 1-{MAX_NUM}")
print(f"  Total combinations: C({MAX_NUM},{PICK}) = {TOTAL_COMBOS:,}")
print(f"  Cost per bet: NTD {COST_PER_BET}")

# Exact probability of matching exactly m numbers
# P(match exactly m) = C(5,m) * C(34, 5-m) / C(39,5)
# where 34 = 39 - 5 (non-drawn numbers)

NON_DRAWN = MAX_NUM - PICK  # 34

print(f"\n{'='*72}")
print("  SECTION 1: Exact Combinatorial Probabilities")
print(f"{'='*72}")

probabilities = {}
cumulative_prob = 0.0

for m in range(PICK + 1):
    ways_match = math.comb(PICK, m)          # ways to choose m from 5 drawn
    ways_miss = math.comb(NON_DRAWN, PICK - m)  # ways to choose (5-m) from 34 non-drawn
    count = ways_match * ways_miss
    prob = count / TOTAL_COMBOS
    probabilities[m] = {
        'ways_match': ways_match,
        'ways_miss': ways_miss,
        'count': count,
        'probability': prob,
        'one_in': 1.0 / prob if prob > 0 else float('inf'),
    }
    cumulative_prob += prob

print(f"\n  {'Match':<8} {'C(5,m)':<10} {'C(34,5-m)':<12} {'Count':<12} {'Probability':<14} {'1 in':<12}")
print(f"  {'-'*8} {'-'*10} {'-'*12} {'-'*12} {'-'*14} {'-'*12}")
for m in range(PICK + 1):
    p = probabilities[m]
    print(f"  {m:<8} {p['ways_match']:<10} {p['ways_miss']:<12,} {p['count']:<12,} "
          f"{p['probability']:<14.10f} {p['one_in']:<12.1f}")

print(f"\n  Σ probabilities = {cumulative_prob:.15f}")
assert abs(cumulative_prob - 1.0) < 1e-12, f"Probabilities don't sum to 1: {cumulative_prob}"
print(f"  ✓ Verified: probabilities sum to exactly 1.000000000000000")

# ============================================================
# SECTION 2: TWO Prize Structures Side-by-Side
# ============================================================

print(f"\n{'='*72}")
print("  SECTION 2: Prize Structure Comparison")
print(f"{'='*72}")

# Prize structure A: As used in structural_optimization.py and meta_strategy_research.py
PRIZES_CODE = {2: 300, 3: 2000, 4: 20000, 5: 8_000_000}
# Prize structure B: Official Taiwan Lottery 今彩539 (confirmed via public records)
PRIZES_OFFICIAL = {2: 50, 3: 300, 4: 20000, 5: 8_000_000}

print(f"\n  Prize Structure A (used in code):")
print(f"  {'Match':<8} {'Prize (NTD)':<15} {'Source'}")
print(f"  {'-'*8} {'-'*15} {'-'*40}")
print(f"  {'M2':<8} {'300':<15} structural_optimization.py line 34")
print(f"  {'M3':<8} {'2,000':<15} structural_optimization.py line 34")
print(f"  {'M4':<8} {'20,000':<15} structural_optimization.py line 34")
print(f"  {'M5':<8} {'8,000,000':<15} structural_optimization.py line 34")

print(f"\n  Prize Structure B (official Taiwan Lottery):")
print(f"  {'Match':<8} {'Prize (NTD)':<15} {'Source'}")
print(f"  {'-'*8} {'-'*15} {'-'*40}")
print(f"  {'M2':<8} {'50':<15} Taiwan Lottery official (肆獎)")
print(f"  {'M3':<8} {'300':<15} Taiwan Lottery official (參獎)")
print(f"  {'M4':<8} {'20,000':<15} Taiwan Lottery official (貳獎)")
print(f"  {'M5':<8} {'~8,000,000':<15} Taiwan Lottery official (頭獎, pari-mutuel)")

print(f"\n  Discrepancies:")
print(f"  {'Match':<8} {'Code':<12} {'Official':<12} {'Ratio':<12} {'Status'}")
print(f"  {'-'*8} {'-'*12} {'-'*12} {'-'*12} {'-'*12}")
for m in range(2, 6):
    code_val = PRIZES_CODE.get(m, 0)
    off_val = PRIZES_OFFICIAL.get(m, 0)
    ratio = code_val / off_val if off_val > 0 else 0
    status = "MATCH" if code_val == off_val else "*** MISMATCH ***"
    print(f"  M{m:<7} {code_val:<12,} {off_val:<12,} {ratio:<12.2f}x {status}")

# ============================================================
# SECTION 3: EV Calculation with Both Prize Structures
# ============================================================

print(f"\n{'='*72}")
print("  SECTION 3: Expected Value Calculation")
print(f"{'='*72}")

def compute_ev(prizes, label):
    print(f"\n  --- {label} ---")
    print(f"  {'Match':<8} {'Probability':<14} {'Prize (NTD)':<14} {'EV Contrib':<14} {'% of Total EV'}")
    print(f"  {'-'*8} {'-'*14} {'-'*14} {'-'*14} {'-'*14}")

    ev_total = 0.0
    ev_components = {}
    for m in range(PICK + 1):
        prize = prizes.get(m, 0)
        prob = probabilities[m]['probability']
        ev_contrib = prob * prize
        ev_total += ev_contrib
        ev_components[m] = ev_contrib

    for m in range(PICK + 1):
        prize = prizes.get(m, 0)
        prob = probabilities[m]['probability']
        ev_contrib = ev_components[m]
        pct = (ev_contrib / ev_total * 100) if ev_total > 0 else 0
        if prize > 0:
            print(f"  M{m:<7} {prob:<14.10f} {prize:<14,} {ev_contrib:<14.4f} {pct:<14.1f}%")

    ev_without_jackpot = ev_total - ev_components.get(5, 0)

    print(f"\n  Total EV = NTD {ev_total:.4f}")
    print(f"  EV without jackpot = NTD {ev_without_jackpot:.4f}")
    print(f"  Cost per bet = NTD {COST_PER_BET}")
    print(f"  Net EV = NTD {ev_total - COST_PER_BET:.4f}")
    roi = (ev_total - COST_PER_BET) / COST_PER_BET * 100
    print(f"  ROI = {roi:+.2f}%")
    print(f"  House edge = {-roi:+.2f}%")

    if ev_total > COST_PER_BET:
        print(f"\n  ⚠️  EV > COST: This implies POSITIVE expected value!")
    else:
        print(f"\n  ✓ EV < COST: This is the normal expected state for a lottery game.")

    return ev_total, roi, ev_components

ev_code, roi_code, comp_code = compute_ev(PRIZES_CODE, "Prize Structure A (Code)")
ev_official, roi_official, comp_official = compute_ev(PRIZES_OFFICIAL, "Prize Structure B (Official)")

# ============================================================
# SECTION 4: Impact Analysis
# ============================================================

print(f"\n{'='*72}")
print("  SECTION 4: Impact of Prize Error")
print(f"{'='*72}")

print(f"\n  {'Metric':<30} {'Code (A)':<20} {'Official (B)':<20} {'Difference'}")
print(f"  {'-'*30} {'-'*20} {'-'*20} {'-'*20}")
print(f"  {'EV per bet (NTD)':<30} {ev_code:<20.4f} {ev_official:<20.4f} {ev_code-ev_official:+.4f}")
print(f"  {'ROI':<30} {roi_code:>+19.2f}% {roi_official:>+19.2f}% {roi_code-roi_official:+.2f}pp")

m2_impact = (PRIZES_CODE[2] - PRIZES_OFFICIAL[2]) * probabilities[2]['probability']
m3_impact = (PRIZES_CODE[3] - PRIZES_OFFICIAL[3]) * probabilities[3]['probability']
print(f"\n  EV inflation from M2 error: {m2_impact:+.4f} NTD")
print(f"  EV inflation from M3 error: {m3_impact:+.4f} NTD")
print(f"  Total EV inflation:         {m2_impact + m3_impact:+.4f} NTD")

# ============================================================
# SECTION 5: Monte Carlo Validation
# ============================================================

print(f"\n{'='*72}")
print("  SECTION 5: Monte Carlo Validation (10M simulations)")
print(f"{'='*72}")

N_SIM = 10_000_000

print(f"\n  Running {N_SIM:,} simulated random bets...")
t0 = time.time()

# Simulate: for each bet, draw 5 from 39 (winning), draw 5 from 39 (bet)
# Count matches
pool = np.arange(1, MAX_NUM + 1)  # 1..39

match_counts = np.zeros(PICK + 1, dtype=np.int64)

BATCH = 500_000  # process in batches to avoid memory issues
n_done = 0

for batch_start in range(0, N_SIM, BATCH):
    batch_size = min(BATCH, N_SIM - batch_start)

    # Generate random winning numbers and bet numbers
    winning = np.array([rng.choice(pool, size=PICK, replace=False) for _ in range(batch_size)])
    betting = np.array([rng.choice(pool, size=PICK, replace=False) for _ in range(batch_size)])

    # Count matches per simulation
    for i in range(batch_size):
        matches = len(set(winning[i]) & set(betting[i]))
        match_counts[matches] += 1

    n_done += batch_size
    if n_done % 2_000_000 == 0:
        print(f"    ... {n_done:,} / {N_SIM:,} done")

elapsed = time.time() - t0
print(f"  Completed in {elapsed:.1f}s")

# Compare simulated vs theoretical
print(f"\n  {'Match':<8} {'Theoretical':<14} {'Monte Carlo':<14} {'MC Count':<12} {'Error':<12}")
print(f"  {'-'*8} {'-'*14} {'-'*14} {'-'*12} {'-'*12}")

mc_ev_a = 0.0
mc_ev_b = 0.0

for m in range(PICK + 1):
    mc_prob = match_counts[m] / N_SIM
    theo_prob = probabilities[m]['probability']
    error_pct = (mc_prob - theo_prob) / theo_prob * 100 if theo_prob > 0 else 0
    print(f"  M{m:<7} {theo_prob:<14.10f} {mc_prob:<14.10f} {match_counts[m]:<12,} {error_pct:+.4f}%")
    mc_ev_a += mc_prob * PRIZES_CODE.get(m, 0)
    mc_ev_b += mc_prob * PRIZES_OFFICIAL.get(m, 0)

print(f"\n  Monte Carlo EV (Code prizes):     NTD {mc_ev_a:.4f}  (vs exact {ev_code:.4f}, diff {mc_ev_a-ev_code:+.4f})")
print(f"  Monte Carlo EV (Official prizes): NTD {mc_ev_b:.4f}  (vs exact {ev_official:.4f}, diff {mc_ev_b-ev_official:+.4f})")

mc_roi_a = (mc_ev_a - COST_PER_BET) / COST_PER_BET * 100
mc_roi_b = (mc_ev_b - COST_PER_BET) / COST_PER_BET * 100
print(f"  Monte Carlo ROI (Code prizes):     {mc_roi_a:+.2f}%")
print(f"  Monte Carlo ROI (Official prizes): {mc_roi_b:+.2f}%")

# ============================================================
# SECTION 6: Tax and Prize Splitting Analysis
# ============================================================

print(f"\n{'='*72}")
print("  SECTION 6: Tax and Prize Splitting Rules")
print(f"{'='*72}")

print("""
  Taiwan Lottery Tax Rules:
  ╔══════════════════════════════════════════════════════════════════╗
  ║ Prize ≤ NTD 5,000:    No tax (免稅)                            ║
  ║ NTD 5,001 ~ 20,000:   Withheld at source (just reported)       ║
  ║ Prize > NTD 20,000:    20% withholding tax (扣繳20%)            ║
  ╚══════════════════════════════════════════════════════════════════╝

  For 今彩539 (with OFFICIAL prizes):
  - M2 (NTD 50):     No tax → Net NTD 50
  - M3 (NTD 300):    No tax → Net NTD 300
  - M4 (NTD 20,000): No tax → Net NTD 20,000
  - M5 (Jackpot):    20% tax → Net = 0.80 × Jackpot

  Prize splitting: M5 (jackpot) is pari-mutuel — split among all winners.
  M2/M3/M4 are FIXED prizes — no splitting.
""")

# Post-tax EV with official prizes
TAX_RATE_HIGH = 0.20
jp_base = 8_000_000
jp_net = jp_base * (1 - TAX_RATE_HIGH)

ev_post_tax = (
    probabilities[2]['probability'] * 50 +      # M2, no tax
    probabilities[3]['probability'] * 300 +      # M3, no tax
    probabilities[4]['probability'] * 20000 +    # M4, no tax (exactly at threshold)
    probabilities[5]['probability'] * jp_net      # M5, 20% tax
)
roi_post_tax = (ev_post_tax - COST_PER_BET) / COST_PER_BET * 100

print(f"  Post-tax EV (official, base jackpot): NTD {ev_post_tax:.4f}")
print(f"  Post-tax ROI: {roi_post_tax:+.2f}%")

# Jackpot needed for breakeven (post-tax)
# EV = sum_m2_m4 + P(M5) * JP_net = 50
# JP_net = (50 - sum_m2_m4) / P(M5)
# JP_gross = JP_net / 0.8
ev_m2_m4 = (
    probabilities[2]['probability'] * 50 +
    probabilities[3]['probability'] * 300 +
    probabilities[4]['probability'] * 20000
)
jp_breakeven_net = (COST_PER_BET - ev_m2_m4) / probabilities[5]['probability']
jp_breakeven_gross = jp_breakeven_net / (1 - TAX_RATE_HIGH)

print(f"\n  EV from M2+M3+M4 alone: NTD {ev_m2_m4:.4f}")
print(f"  Jackpot needed for EV = cost (pre-tax):  NTD {jp_breakeven_gross:,.0f}")
print(f"  Jackpot needed for EV = cost (post-tax): NTD {jp_breakeven_gross:,.0f}")
print(f"  Current base jackpot:                    NTD {jp_base:,}")
print(f"  Multiplier needed:                       {jp_breakeven_gross/jp_base:.1f}x")

# ============================================================
# SECTION 7: Final Verdict
# ============================================================

print(f"\n{'='*72}")
print("  SECTION 7: FINAL AUDIT VERDICT")
print(f"{'='*72}")

print(f"""
  ┌──────────────────────────────────────────────────────────────────┐
  │                    CRITICAL FINDING                             │
  │                                                                │
  │  The +40.93% ROI finding is INCORRECT.                          │
  │                                                                │
  │  Root cause: Wrong prize table in code                          │
  │    Code used:   M2=300, M3=2,000                                │
  │    Correct:     M2=50,  M3=300                                  │
  │                                                                │
  │  Correct EV:   NTD {ev_official:.2f} (vs cost NTD 50)               │
  │  Correct ROI:  {roi_official:+.2f}%                                    │
  │  Post-tax ROI: {roi_post_tax:+.2f}%                                    │
  │                                                                │
  │  539 is a NEGATIVE EV game, as expected for a lottery.          │
  └──────────────────────────────────────────────────────────────────┘

  Affected Reports:
  1. structural_optimization_report.md — Direction 5 (Kelly) and Direction 6 (Structure)
  2. structural_optimization_results.json — EV calculations
  3. meta_strategy_report.md — Phase 6 Payout-Aware section
  4. meta_strategy_results.json — Payout ROI calculations

  Impact on Strategy Research:
  - M2+ hit rate analysis (edge calculations) is UNAFFECTED
    (edge is computed from hit rates, not prize amounts)
  - Kelly criterion result CHANGES FUNDAMENTALLY:
    Code conclusion: "539 is positive EV, bet aggressively (Kelly f*=9.3%)"
    Correct conclusion: "539 is negative EV (-{abs(roi_official):.1f}%),
                         Kelly requires edge to overcome house deficit"

  Recommendations:
  1. FIX prize table in structural_optimization.py line 34
  2. FIX prize table in meta_strategy_research.py lines 1270-1273
  3. RE-RUN Kelly calculation with correct prizes
  4. UPDATE all reports that reference "positive EV" or "+40.93% ROI"
  5. VERIFY prize tables for BIG_LOTTO and POWER_LOTTO as well
""")

# ============================================================
# SECTION 8: Correct Prize Verification Table
# ============================================================

print(f"{'='*72}")
print("  SECTION 8: Correct 今彩539 Prize Structure")
print(f"{'='*72}")

print(f"""
  ╔═══════╦══════════════╦═════════════╦══════════════╦═════════════╗
  ║ Match ║ Chinese Name ║ Prize (NTD) ║ Type         ║ Tax         ║
  ╠═══════╬══════════════╬═════════════╬══════════════╬═════════════╣
  ║ M5    ║ 頭獎         ║ ~8,000,000  ║ Pari-mutuel  ║ 20% if >20K ║
  ║ M4    ║ 貳獎         ║ 20,000      ║ Fixed        ║ Borderline  ║
  ║ M3    ║ 參獎         ║ 300         ║ Fixed        ║ None        ║
  ║ M2    ║ 肆獎         ║ 50          ║ Fixed        ║ None        ║
  ║ M1    ║ -            ║ 0           ║ -            ║ -           ║
  ║ M0    ║ -            ║ 0           ║ -            ║ -           ║
  ╠═══════╬══════════════╬═════════════╬══════════════╬═════════════╣
  ║ Cost  ║              ║ 50 / bet    ║              ║             ║
  ╚═══════╩══════════════╩═════════════╩══════════════╩═════════════╝

  Key observations:
  1. M2 prize (50 NTD) = ticket cost — this is a "break-even" consolation
  2. M3 prize (300 NTD) = 6x ticket cost — the practical return for casual bettors
  3. M4 prize (20,000 NTD) = 400x ticket cost — the "big hit" for strategy-guided betting
  4. M5 jackpot is pari-mutuel and subject to 20% tax

  Note: The 39樂合彩 (39 Lotto), which piggybacks on 539's draw, has its OWN prizes:
  - 二合 = 50 NTD, 三合 = 300 NTD, 四合 = 3,000+ NTD
  This may have caused confusion — the 39 Lotto "三合" 300 NTD was incorrectly
  assigned as 539's "M2" in the code.
""")

# Save results
results = {
    'audit_date': '2026-03-15',
    'game': 'DAILY_539',
    'total_combinations': TOTAL_COMBOS,
    'cost_per_bet': COST_PER_BET,
    'probabilities': {
        str(m): {
            'exact_probability': probabilities[m]['probability'],
            'one_in': probabilities[m]['one_in'],
            'count': probabilities[m]['count'],
        }
        for m in range(PICK + 1)
    },
    'prize_structures': {
        'code_version_WRONG': PRIZES_CODE,
        'official_version_CORRECT': PRIZES_OFFICIAL,
    },
    'ev_analysis': {
        'code_wrong': {'ev': round(ev_code, 4), 'roi_pct': round(roi_code, 2)},
        'official_correct': {'ev': round(ev_official, 4), 'roi_pct': round(roi_official, 2)},
        'post_tax': {'ev': round(ev_post_tax, 4), 'roi_pct': round(roi_post_tax, 2)},
    },
    'monte_carlo': {
        'n_simulations': N_SIM,
        'seed': SEED,
        'mc_ev_code': round(mc_ev_a, 4),
        'mc_ev_official': round(mc_ev_b, 4),
        'mc_roi_code': round(mc_roi_a, 2),
        'mc_roi_official': round(mc_roi_b, 2),
    },
    'verdict': {
        'previous_claim': '+40.93% ROI (INCORRECT)',
        'correct_roi': f'{roi_official:+.2f}%',
        'root_cause': 'Prize table error: M2=300 (should be 50), M3=2000 (should be 300)',
        'impact_on_edge_research': 'NONE — hit rate analysis unaffected',
        'impact_on_kelly': 'FUNDAMENTAL — 539 is negative EV, Kelly requires prediction edge',
        'jackpot_breakeven_ntd': round(jp_breakeven_gross),
    },
    'affected_files': [
        'tools/structural_optimization.py (line 34)',
        'tools/meta_strategy_research.py (lines 1270-1273)',
        'structural_optimization_report.md',
        'structural_optimization_results.json',
        'meta_strategy_report.md',
        'meta_strategy_results.json',
    ],
}

output_path = os.path.join(os.path.dirname(__file__), '..', 'ev_audit_539_results.json')
with open(output_path, 'w') as f:
    json.dump(results, f, indent=2, ensure_ascii=False)
print(f"\n  Results saved to: {output_path}")

print(f"\n{'='*72}")
print("  AUDIT COMPLETE")
print(f"{'='*72}\n")
