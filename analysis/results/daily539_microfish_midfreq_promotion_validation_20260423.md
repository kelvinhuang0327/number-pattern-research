# DAILY_539 MicroFish+MidFreq Promotion Validation (2026-04-23)

**Verdict:** REJECT

## Failure-context correction

- This round did **not** rerun `POWER_LOTTO Winning Quality P2-1` because the same direction was repeatedly blocked by environment permission/quota failures rather than producing new trusted evidence.
- This round did **not** rerun `DAILY_539 H011/H012/H013`: H011/H012 are already trusted **REJECT**, and H013 is trusted **REJECT(DATA_UNAVAILABLE)** with proxy validation explicitly forbidden.
- Therefore the only trusted actionable 539 bypass topic for this 8-hour slot was `MicroFish+MidFreq 2-bet` promotion gating against `midfreq_acb_2bet`.

## Reproducibility

- Command: `python3 tools/validate_daily539_microfish_midfreq_promotion_20260423.py`
- Params: seed=42, n_perm=200, min_history=300, perm_warmup=900, windows=[150, 500, 1500]
- Data range: 96000001 (2007/01/01) → 115000095 (2026/04/17), total draws=5839

## Candidate mapping

- Requested candidate: `microfish_midfreq_2bet`
- Active-code mapping: `MicroFish+MidFreq 2-bet`
- Mapping note: Active-code mapping follows tools/production_validation.py: bet1 is the evolved MicroFish genome, bet2 is MidFreq with exclusion from bet1.
- Incumbent comparator: `midfreq_acb_2bet`

## Summary

- Formal leakage checker: PASS (`tools/verify_no_data_leakage.py` -> `analysis/results/daily539_microfish_midfreq_promotion_no_leakage_20260423.txt`)
- Promotion rule: all three windows must clear positive edge, permutation p<0.05, Cohen's d>1.0, incremental efficiency >80%, and stable McNemar superiority over `midfreq_acb_2bet`.
- Failed gates (union): mcnemar>=0.05

## Window results

| Window | Candidate edge | Incumbent edge | Candidate perm p | Candidate d | McNemar p | McNemar net |
|---:|---:|---:|---:|---:|---:|---:|
| 150 | +11.79% | +8.46% | 0.0050 | 2.885 | 0.1797 | +5 |
| 500 | +11.06% | +8.26% | 0.0050 | 5.300 | 0.0201 | +14 |
| 1500 | +7.33% | +5.53% | 0.0050 | 6.376 | 0.0132 | +27 |

## Detailed gates

### 150p

- Candidate hit rate / edge / sharpe: 33.33% / +11.79% / 0.250
- Incumbent hit rate / edge / sharpe: 30.00% / +8.46% / 0.185
- Candidate permutation: p=0.0050, d=2.885, shuffle_mean_edge=+1.57%
- McNemar vs incumbent: p=0.1797, net=+5
- Candidate bet efficiency: bet1=100.00%, bet2=164.37%
- Failed gates: mcnemar>=0.05

### 500p

- Candidate hit rate / edge / sharpe: 32.60% / +11.06% / 0.236
- Incumbent hit rate / edge / sharpe: 29.80% / +8.26% / 0.181
- Candidate permutation: p=0.0050, d=5.300, shuffle_mean_edge=+0.80%
- McNemar vs incumbent: p=0.0201, net=+14
- Candidate bet efficiency: bet1=100.00%, bet2=149.90%
- Failed gates: none

### 1500p

- Candidate hit rate / edge / sharpe: 28.87% / +7.33% / 0.162
- Incumbent hit rate / edge / sharpe: 27.07% / +5.53% / 0.124
- Candidate permutation: p=0.0050, d=6.376, shuffle_mean_edge=+0.67%
- McNemar vs incumbent: p=0.0132, net=+27
- Candidate bet efficiency: bet1=100.00%, bet2=124.92%
- Failed gates: none

## Conclusion

- Final decision: **REJECT**. At least one promotion gate failed, so the incumbent stays unchanged.

## Handoff Notes

- Wiki update: applied.
