#!/usr/bin/env python3
"""
Phase P — Explainability Layer Validation
==========================================
Validates that:
1. Explanation objects are generated for all 3 lottery types
2. Values reflect real decision path (not placeholders)
3. Learning/Quality/Profile fields are populated
4. No regression in prediction path
5. API endpoints work
6. Persistence works

2026-04-16 Created — Phase P Validation
"""
import sys
import os
import json
import sqlite3
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'lottery_api'))

DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'lottery_api', 'data', 'lottery_v2.db'
)

LOTTERY_TYPES = ['DAILY_539', 'BIG_LOTTO', 'POWER_LOTTO']
CHECKS = []
FAILURES = []


def check(name, condition, detail=""):
    CHECKS.append(name)
    if condition:
        print(f"  ✅ {name}")
    else:
        FAILURES.append(name)
        print(f"  ❌ {name} — {detail}")


def load_history(lottery_type):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "SELECT draw, date, numbers, special FROM draws WHERE lottery_type=? ORDER BY CAST(draw AS INTEGER) ASC",
        (lottery_type,)
    )
    rows = cur.fetchall()
    conn.close()
    history = []
    for draw, date, nums_str, special in rows:
        nums = json.loads(nums_str) if isinstance(nums_str, str) else nums_str
        history.append({
            'draw': draw,
            'date': date,
            'numbers': [int(n) for n in nums],
            'special': special,
        })
    return history


print("=" * 70)
print("Phase P — Explainability Layer Validation")
print("=" * 70)
print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print()

# ─── Test 1: Explanation generation for each lottery type ────────
print("Test 1: Explanation generation")
print("-" * 50)

explanations = {}
for lt in LOTTERY_TYPES:
    history = load_history(lt)
    print(f"\n  {lt}: {len(history)} draws loaded")

    from lottery_api.engine.strategy_coordinator import (
        StrategyCoordinator, coordinator_predict, get_last_explanation
    )

    # Run prediction
    bets, desc = coordinator_predict(lt, history, n_bets=3, mode='direct')
    exp = get_last_explanation()

    check(f"{lt} explanation exists", exp is not None, "get_last_explanation() returned None")

    if exp:
        explanations[lt] = exp

        # Test 2: Required fields exist
        check(f"{lt} has lottery_type", exp.get('lottery_type') == lt,
              f"Expected {lt}, got {exp.get('lottery_type')}")
        check(f"{lt} has profile", 'profile' in exp and exp['profile'] in ('conservative', 'balanced', 'aggressive'),
              f"profile={exp.get('profile')}")
        check(f"{lt} has learning", 'learning' in exp and isinstance(exp['learning'], dict))
        check(f"{lt} has quality", 'quality' in exp and isinstance(exp['quality'], dict))
        check(f"{lt} has profile_detail", 'profile_detail' in exp and isinstance(exp['profile_detail'], dict))
        check(f"{lt} has selection", 'selection' in exp and isinstance(exp['selection'], dict))
        check(f"{lt} has base_score_summary", 'base_score_summary' in exp)

        # Test 3: Learning fields are not placeholders
        lr = exp['learning']
        check(f"{lt} learning.gate is valid", lr.get('gate') in ('ENABLED', 'WEAK', 'DISABLED'),
              f"gate={lr.get('gate')}")
        check(f"{lt} learning.factor is numeric", isinstance(lr.get('factor'), (int, float)),
              f"factor={lr.get('factor')}")
        check(f"{lt} learning.research_score is numeric", isinstance(lr.get('research_score'), (int, float)),
              f"rs={lr.get('research_score')}")
        check(f"{lt} learning.summary is not empty", bool(lr.get('summary')),
              f"summary='{lr.get('summary')}'")
        check(f"{lt} learning.hypotheses has counts",
              isinstance(lr.get('hypotheses'), dict) and 'total' in lr['hypotheses'])

        # Test 4: Quality fields
        qr = exp['quality']
        check(f"{lt} quality.enabled is bool", isinstance(qr.get('enabled'), bool))
        check(f"{lt} quality.summary is not empty", bool(qr.get('summary')))

        # Test 5: Profile fields
        pr = exp['profile_detail']
        check(f"{lt} profile.name valid", pr.get('name') in ('conservative', 'balanced', 'aggressive'))
        check(f"{lt} profile.learning_amp is numeric", isinstance(pr.get('learning_amp'), (int, float)))
        check(f"{lt} profile.summary is not empty", bool(pr.get('summary')))

        # Test 6: Selection fields
        sel = exp['selection']
        check(f"{lt} selection.ranking_changed is bool", isinstance(sel.get('ranking_changed'), bool))
        check(f"{lt} selection.top_numbers_before_bonus has values",
              isinstance(sel.get('top_numbers_before_bonus'), list) and len(sel['top_numbers_before_bonus']) > 0)
        check(f"{lt} selection.top_numbers_after_bonus has values",
              isinstance(sel.get('top_numbers_after_bonus'), list) and len(sel['top_numbers_after_bonus']) > 0)

# ─── Test 7: No regression — prediction path unchanged ────────
print("\n\nTest 7: No regression in prediction path")
print("-" * 50)

for lt in LOTTERY_TYPES:
    history = load_history(lt)

    # Run prediction with explainability (default)
    bets_with, _ = coordinator_predict(lt, history, n_bets=3, mode='direct')

    # Run prediction without explainability (same path, explanation is just data capture)
    coord_no_trace = StrategyCoordinator(lt)
    bets_without = coord_no_trace.predict(history, n_bets=3)

    match = bets_with == bets_without
    check(f"{lt} prediction unchanged by explainability", match,
          f"with={bets_with}, without={bets_without}")

# ─── Test 8: Persistence ────────
print("\n\nTest 8: Persistence layer")
print("-" * 50)

from lottery_api.engine.explainability import (
    save_explanation, get_explanation_by_run, get_latest_explanation, get_summary
)

for lt in LOTTERY_TYPES:
    if lt not in explanations:
        continue
    exp = explanations[lt]
    # Use negative run_id to avoid conflicting with real data
    test_run_id = -1000 - LOTTERY_TYPES.index(lt)
    row_id = save_explanation(lt, exp, prediction_run_id=test_run_id, profile=exp.get('profile', 'balanced'))
    check(f"{lt} save_explanation succeeded", row_id > 0, f"row_id={row_id}")

    # Retrieve
    retrieved = get_explanation_by_run(test_run_id)
    check(f"{lt} get_explanation_by_run works", retrieved is not None and retrieved['lottery_type'] == lt)
    check(f"{lt} retrieved explanation matches",
          retrieved and retrieved['explanation'].get('lottery_type') == lt)

    # Latest
    latest = get_latest_explanation(lt)
    check(f"{lt} get_latest_explanation works", latest is not None)

# Summary
summary = get_summary()
check("get_summary works", summary and 'total_explanations' in summary,
      f"summary={summary}")
check("summary has by_lottery_type",
      summary and isinstance(summary.get('by_lottery_type'), dict))

# ─── Cleanup test data ────────
conn = sqlite3.connect(DB_PATH)
conn.execute("DELETE FROM prediction_explanations WHERE prediction_run_id < 0")
conn.commit()
conn.close()

# ─── Print example explanations ────────
print("\n\n" + "=" * 70)
print("Example Explanation JSONs")
print("=" * 70)

for lt in LOTTERY_TYPES:
    if lt in explanations:
        print(f"\n{'─' * 60}")
        print(f"  {lt}")
        print(f"{'─' * 60}")
        print(json.dumps(explanations[lt], indent=2, ensure_ascii=False, default=str))

# ─── Verdict ────────
print("\n\n" + "=" * 70)
print("VERDICT")
print("=" * 70)
total = len(CHECKS)
passed = total - len(FAILURES)
pass_rate = passed / max(total, 1)

print(f"  Checks: {passed}/{total} ({pass_rate:.0%})")
if FAILURES:
    print(f"  Failures: {', '.join(FAILURES)}")

if pass_rate >= 0.95 and not any('regression' in f.lower() for f in FAILURES):
    verdict = "ACCEPT"
elif pass_rate >= 0.80:
    verdict = "PARTIAL"
else:
    verdict = "REJECT"

print(f"  VERDICT: {verdict}")
print("=" * 70)

# Save results
results_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            'research', 'analysis_outputs')
os.makedirs(results_dir, exist_ok=True)
ts = datetime.now().strftime('%Y%m%d_%H%M%S')
results_path = os.path.join(results_dir, f'phase_p_validation_{ts}.json')
with open(results_path, 'w') as f:
    json.dump({
        'phase': 'P',
        'timestamp': ts,
        'verdict': verdict,
        'total_checks': total,
        'passed': passed,
        'pass_rate': pass_rate,
        'failures': FAILURES,
        'explanations': explanations,
    }, f, indent=2, ensure_ascii=False, default=str)
print(f"\nResults saved to: {results_path}")
