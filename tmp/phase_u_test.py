"""Phase U end-to-end validation."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lottery_api'))

# Force enable for testing
os.environ['PHASE_U_ENABLED'] = 'true'

from engine.promotion_engine import (
    evaluate_lottery, evaluate_all, get_promotion_status,
    confirm_promotion, ENABLED, AUTO_PROMOTE, _load_promotions,
    PROMOTIONS_FILE,
)
from engine.confidence_scorer import get_lottery_confidence

print(f'Phase U enabled: {ENABLED}')
print(f'Auto promote: {AUTO_PROMOTE}')
print()

# ── Test 1: Evaluate all lotteries ──────────────────────────────────────────
print('=== EVALUATE ALL ===')
results = evaluate_all()
for lt, report in results.items():
    print(f'\n--- {lt} ---')
    print(f'  production:   {report.get("production")}')
    print(f'  shadow:       {report.get("shadow")}')
    print(f'  promotable:   {list(report.get("promotable", {}).keys())}')
    print(f'  check #:      {report.get("check_number")}')
    print(f'  in_cooldown:  {report.get("in_cooldown")}')
    print(f'  actions:')
    for a in report.get('actions', []):
        print(f'    {a["type"]}: {a.get("strategy", "")} — {a.get("reason", "")}')
    print(f'  demote_warnings: {report.get("demote_warnings", {})}')

# ── Test 2: Read-only status ────────────────────────────────────────────────
print('\n=== STATUS (read-only) ===')
status = get_promotion_status()
for lt, st in status.items():
    print(f'{lt}: prod={st.get("production")}, shadow={st.get("shadow")}, '
          f'checks={st.get("total_checks")}, '
          f'promotable_tracking={list(st.get("promotable", {}).keys())}')

# ── Test 3: Verify persistence ──────────────────────────────────────────────
import json
if os.path.exists(PROMOTIONS_FILE):
    with open(PROMOTIONS_FILE) as f:
        data = json.load(f)
    print(f'\nPersisted lotteries: {list(data.keys())}')
    for lt, d in data.items():
        print(f'  {lt}: production={d.get("production")}, checks={d.get("total_checks")}, '
              f'history_len={len(d.get("history", []))}')
else:
    print('\nNo promotions file yet')

# ── Test 4: Actionable integration ──────────────────────────────────────────
print('\n=== ACTIONABLE INTEGRATION ===')
from engine.actionable_intelligence import get_actionable_summary
summary = get_actionable_summary()
for lt, entry in summary.items():
    sig = entry.get('signals_summary', {})
    promo = entry.get('promotion', {})
    print(f'{lt}:')
    print(f'  prod={sig.get("promotion_production")}, shadow={sig.get("shadow_count")}, '
          f'tracking={sig.get("promotable_tracking")}')
    # Check for Phase U rules
    for ins in entry.get('insights', []):
        if ins.get('code', '').startswith('R1') and int(ins['code'][1:3]) >= 12:
            print(f'  rule {ins["code"]}: {ins["message"]}')

print('\n=== OK ===')
