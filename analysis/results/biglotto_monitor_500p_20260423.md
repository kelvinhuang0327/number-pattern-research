# BIG_LOTTO 500p monitoring report (2026-04-23)

- overall_status: **DOWNGRADE_TRIGGERED**
- recommended_action: **SHADOW_ONLY**
- leakage_check: **PASS**
- next McNemar replacement candidate: **NO**
- rationale: No candidate enters next McNemar replacement validation. Only shadow `regime_2bet` was evaluated, and it is not a like-for-like replacement for 4/5-bet active slots.

## p1_deviation_4bet

- Decision: **DOWNGRADE_CANDIDATE**
- Lifecycle pattern: **STABLE**
- Downgrade triggers: recent_150: permutation p=0.1294 >= 0.05

| Window | Hit Rate | Edge | Sharpe | Perm p | Cohen's d | Efficiency | vs Stage0 Edge |
|---|---:|---:|---:|---:|---:|---:|---:|
| 150 | 10.67% | +3.42% | +0.1107 | 0.1294 | +1.353 | 280.1% | +2.20pp |
| 500 | 9.80% | +2.55% | +0.0858 | 0.0348 | +1.852 | 209.1% | +1.33pp |
| 1500 | 9.73% | +2.48% | +0.0838 | 0.0050 | +3.300 | 203.6% | +1.26pp |

## p1_dev_sum5bet

- Decision: **DOWNGRADE_CANDIDATE**
- Lifecycle pattern: **STABLE**
- Downgrade triggers: recent_150: permutation p=0.0547 >= 0.05; recent_1500: per-bet efficiency=77.2% <= 80%

| Window | Hit Rate | Edge | Sharpe | Perm p | Cohen's d | Efficiency | vs Stage0 Edge |
|---|---:|---:|---:|---:|---:|---:|---:|
| 150 | 14.00% | +5.02% | +0.1447 | 0.0547 | +1.805 | 134.3% | +1.28pp |
| 500 | 12.20% | +3.22% | +0.0985 | 0.0199 | +2.367 | 86.2% | -0.52pp |
| 1500 | 11.87% | +2.89% | +0.0893 | 0.0050 | +3.902 | 77.2% | -0.85pp |

## Shadow fallback ranking

| Rank | Strategy | 500p Edge | 500p Perm p | 500p Cohen's d | Action | Reason |
|---:|---|---:|---:|---:|---|---|
| 1 | regime_2bet | +2.11% | 0.0149 | +2.618 | SHADOW_ONLY | Best available shadow comparator inside scope; still advisory only because bet count is not like-for-like with current 4/5-bet active strategies. |

## Handoff notes

- wiki 無需更新

