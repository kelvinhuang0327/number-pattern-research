#!/usr/bin/env python3
"""Quick debug: verify determinism and actual score differences."""
import json, sqlite3, sys, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'lottery_api'))

from engine.strategy_coordinator import StrategyCoordinator

# Load draws
conn = sqlite3.connect(os.path.join(ROOT, 'lottery_api', 'data', 'lottery_v2.db'))
conn.row_factory = sqlite3.Row
rows = conn.execute(
    'SELECT draw, numbers FROM draws WHERE lottery_type="DAILY_539" '
    'ORDER BY CAST(draw AS INTEGER) ASC LIMIT 1800'
).fetchall()
conn.close()
history = [{'draw': r['draw'], 'numbers': json.loads(r['numbers'])} for r in rows[:1750]]

# Pipeline A: run twice
c1 = StrategyCoordinator('DAILY_539', disable_learning=True)
bets1 = c1.predict(history, n_bets=3)
c2 = StrategyCoordinator('DAILY_539', disable_learning=True)
bets2 = c2.predict(history, n_bets=3)
print(f"A vs A: same={bets1 == bets2}")

# Pipeline B: run twice
c3 = StrategyCoordinator('DAILY_539', disable_learning=False)
bets3 = c3.predict(history, n_bets=3)
c4 = StrategyCoordinator('DAILY_539', disable_learning=False)
bets4 = c4.predict(history, n_bets=3)
print(f"B vs B: same={bets3 == bets4}")

# A vs B
print(f"A vs B: same={bets1 == bets3}")
print(f"  A bets: {bets1}")
print(f"  B bets: {bets3}")

# Bonuses
print(f"\nBonuses B: {c3._learning_bonuses}")

# Score differences
scores_a = c1.aggregate_scores(history)
scores_b = c3.aggregate_scores(history)
diffs = {n: round(scores_b[n] - scores_a[n], 8) for n in sorted(scores_a)}
nonzero = {n: d for n, d in diffs.items() if abs(d) > 1e-10}
print(f"\nScore diffs (B-A): {len(nonzero)}/{len(diffs)} numbers differ")

ranked_a = sorted(scores_a, key=lambda n: -scores_a[n])[:20]
ranked_b = sorted(scores_b, key=lambda n: -scores_b[n])[:20]
print(f"Top 20 A: {ranked_a}")
print(f"Top 20 B: {ranked_b}")

# Show where ranking changes
for i, (a, b) in enumerate(zip(ranked_a, ranked_b)):
    if a != b:
        print(f"  Rank {i}: A={a} (score {scores_a[a]:.6f}) vs B={b} (score {scores_b[b]:.6f})")
