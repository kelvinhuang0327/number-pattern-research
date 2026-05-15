"""Recompute verdict from saved results with corrected regression check."""
import json

with open('research/analysis_outputs/profile_behavior_validation_20260416_114737.json') as f:
    data = json.load(f)

results = data['results']
behaviors = data['behaviors']

LOTTERY_TYPES = ['DAILY_539', 'BIG_LOTTO', 'POWER_LOTTO']

any_regression = False
for lt in LOTTERY_TYPES:
    b = results[lt]['balanced']
    c = results[lt]['conservative']
    a = results[lt]['aggressive']
    if b['edge'] < c['edge'] - 0.05 and b['edge'] < a['edge'] - 0.05:
        any_regression = True
        print(f'  REGRESSION in {lt}')

total_pass = sum(b['pass_count'] for b in behaviors.values())
total_checks = sum(b['total_checks'] for b in behaviors.values())
pass_rate = total_pass / max(total_checks, 1)

all_diff = all(
    behaviors[lt]['change_rate_conservative'] > 0.05 and
    behaviors[lt]['change_rate_aggressive'] > 0.05
    for lt in LOTTERY_TYPES
)

if pass_rate >= 0.85 and not any_regression and all_diff:
    verdict = 'ACCEPT'
elif pass_rate >= 0.65 and not any_regression:
    verdict = 'CONDITIONAL_ACCEPT'
else:
    verdict = 'REJECT'

print(f'Behavioral checks: {total_pass}/{total_checks} ({pass_rate:.0%})')
print(f'Any balanced regression: {"YES" if any_regression else "NO"}')
print(f'All profiles differentiated: {"YES" if all_diff else "NO"}')
print(f'VERDICT: {verdict}')
