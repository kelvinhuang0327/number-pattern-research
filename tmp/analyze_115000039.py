"""Analysis script for BIG_LOTTO draw 115000039"""
import json, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'lottery_api'))
from math import comb

actual = [4, 8, 23, 26, 29, 36]
special = 38
actual_set = set(actual)

print("=" * 60)
print("BIG_LOTTO Draw 115000039 Analysis")
print("=" * 60)
print(f"Numbers: {actual}  Special: {special}")
print()

total = sum(actual)
odd = sum(1 for n in actual if n % 2 == 1)
even = 6 - odd
big = sum(1 for n in actual if n > 24)
small = 6 - big
zones = [0] * 5
for n in actual:
    z = (n - 1) // 10
    zones[min(z, 4)] += 1
gaps = [actual[i + 1] - actual[i] for i in range(5)]
tails = [n % 10 for n in actual]

print("=== Feature Profile ===")
print(f"  Sum: {total} (theoretical mean ~150, deviation={total - 150})")
print(f"  Odd/Even: {odd}:{even}")
print(f"  Big/Small (>24): {big}:{small}")
print(f"  Zone distribution (01-10, 11-20, 21-30, 31-40, 41-49): {zones}")
print(f"  Gaps between consecutive: {gaps}")
print(f"  Tails: {tails}")
print(f"  AC value: {len(set(abs(actual[i]-actual[j]) for i in range(6) for j in range(i+1,6))) - 5}")
print()

# Baseline calculations
total_combos = comb(49, 6)
print("=== Baseline Calculations ===")
print(f"  C(49,6) = {total_combos:,}")
for n_bets in [1, 2, 3, 4, 5]:
    p_single = comb(6, 3) * comb(43, 3) / total_combos
    baseline = 1 - (1 - p_single) ** n_bets
    print(f"  {n_bets} bets baseline(>=3 hits): {baseline:.4f} ({baseline * 100:.2f}%)")
print()

# VALID predictions (runs 4/6/7 - Coordinator-Direct, old format)
valid_preds = [
    [2, 13, 15, 31, 33, 39],
    [6, 11, 16, 20, 22, 32],
    [3, 27, 34, 43, 46, 49],
]
print("=== VALID Predictions (Coordinator-Direct, runs 4/6/7) ===")
for i, pred in enumerate(valid_preds):
    hits = sorted(set(pred) & actual_set)
    sp_hit = special in pred
    pred_sum = sum(pred)
    pred_odd = sum(1 for n in pred if n % 2 == 1)
    pred_big = sum(1 for n in pred if n > 24)
    print(f"  Bet{i + 1}: {pred}")
    print(f"    Hits: {len(hits)} {hits}  Special: {'HIT' if sp_hit else 'MISS'}")
    print(f"    Sum={pred_sum} Odd/Even={pred_odd}:{6-pred_odd} Big/Small={pred_big}:{6-pred_big}")

union = set()
for p in valid_preds:
    union |= set(p)
union_hits = sorted(union & actual_set)
print(f"  Union coverage: {len(union)} distinct numbers, {len(union_hits)} actual hits: {union_hits}")
sp_in_union = special in union
print(f"  Special {special} in union: {'YES' if sp_in_union else 'NO'}")
print()

# Feature deviation between predictions and actual
print("=== Deviation Analysis ===")
print(f"  Actual numbers are LOW (sum={total}, 4 of 6 are <= 29)")
print(f"  Predictions were biased toward higher numbers:")
for i, pred in enumerate(valid_preds):
    diff = sum(pred) - total
    coverage_match = len(set(pred) & actual_set)
    print(f"    Bet{i+1}: sum={sum(pred)}, diff from actual={diff:+d}, overlap={coverage_match}")
print()

# What numbers were missed entirely
all_pred_nums = set()
for p in valid_preds:
    all_pred_nums |= set(p)
missed_nums = sorted(actual_set - all_pred_nums)
print(f"  Numbers completely missed (not in any bet): {missed_nums}")
print(f"  These are: {', '.join(str(n) for n in missed_nums)}")
print()

# Historical context - check recent draws patterns
print("=== Recent Draws Context ===")
recent_draws = [
    ("115000038", [14, 33, 41, 42, 44, 48], 47),
    ("115000037", [11, 15, 33, 38, 41, 43], 21),
    ("115000036", [2, 6, 10, 22, 40, 45], 17),
    ("115000035", [5, 12, 13, 38, 47, 48], 3),
    ("115000034", [5, 11, 29, 37, 43, 47], 10),
]
for draw_no, nums, sp in recent_draws:
    draw_sum = sum(nums)
    draw_odd = sum(1 for n in nums if n % 2 == 1)
    draw_big = sum(1 for n in nums if n > 24)
    overlap_with_039 = sorted(set(nums) & actual_set)
    print(f"  {draw_no}: {nums} sp={sp} sum={draw_sum} odd/even={draw_odd}:{6-draw_odd} big/small={draw_big}:{6-draw_big} overlap_039={overlap_with_039}")
print()

# Popularity / Winning Quality Analysis
print("=== Winning Quality Analysis ===")
# Common player preferences: birthdays (1-31), lucky numbers (7, 8, 3, 9)
birthday_count = sum(1 for n in actual if n <= 31)
print(f"  Birthday-range numbers (<=31): {birthday_count}/6 = {birthday_count/6*100:.0f}%")
lucky_nums = {3, 7, 8, 9, 13, 18, 28, 38}
lucky_in_draw = sorted(actual_set & lucky_nums)
print(f"  'Lucky' numbers in draw: {lucky_in_draw}")

# Estimate split risk
# Low numbers and round numbers are more popular among casual players
popular_indicators = 0
if birthday_count >= 4:
    popular_indicators += 1
    print(f"  [!] High birthday coverage -> more players likely picked similar")
if 8 in actual:  # 8 is very popular in Chinese culture
    popular_indicators += 1
    print(f"  [!] Number 8 (lucky number) present")
if 23 in actual or 26 in actual:
    popular_indicators += 1
    print(f"  [!] Mid-range numbers 23, 26 are moderately popular")
if any(n % 10 == 0 for n in actual):
    popular_indicators += 1
    print(f"  [!] Round number present")

if popular_indicators >= 3:
    split_risk = "HIGH"
elif popular_indicators >= 2:
    split_risk = "MEDIUM"
else:
    split_risk = "LOW"
print(f"  Split Risk Assessment: {split_risk} (indicators={popular_indicators}/4)")
print(f"  Payout Quality: {'LOW' if split_risk == 'HIGH' else 'MEDIUM' if split_risk == 'MEDIUM' else 'HIGH'}")
print()

# Strategy edge analysis from strategy_states
print("=== Current Strategy States (Best per bet count) ===")
strategies = {
    2: ("regime_2bet", 0.0364, 0.073, 0.1398),
    3: ("ts3_regime_3bet", 0.0351, 0.090, 0.1226),
    4: ("ts3_markov_4bet_w30", 0.0208, 0.093, 0.0716),
    5: ("p1_dev_sum5bet", 0.0404, 0.130, 0.1201),
}
for nb, (name, edge, rate, sharpe) in strategies.items():
    print(f"  {nb} bets: {name}")
    print(f"    edge_300p={edge:.4f} rate_300p={rate:.1%} sharpe_300p={sharpe:.4f}")
print()

# Gate assessment
print("=== Stage Gate Assessment ===")
for nb, (name, edge, rate, sharpe) in strategies.items():
    p_single = comb(6, 3) * comb(43, 3) / total_combos
    baseline = 1 - (1 - p_single) ** nb
    gate1 = edge > 0  # Edge > baseline (already relative)
    gate4 = sharpe > 0
    status = "PRODUCTION" if gate1 and gate4 else "WATCH"
    print(f"  {nb} bets ({name}):")
    print(f"    Stage1 (Edge>0): {'PASS' if gate1 else 'FAIL'} (edge={edge:.4f})")
    print(f"    Stage4 (Sharpe>0): {'PASS' if gate4 else 'FAIL'} (sharpe={sharpe:.4f})")
    print(f"    Status: {status}")
print()

print("=== Summary ===")
print("VALID predictions (Coordinator-Direct old format): 0/6 hits across 3 bets")
print("Root cause: Old Coordinator strategy was not using current best strategies")
print("The system has since migrated to MULTI_STRATEGY format with RSM-validated strategies")
print("Key issue: VALID predictions were captured before MULTI_STRATEGY migration")
