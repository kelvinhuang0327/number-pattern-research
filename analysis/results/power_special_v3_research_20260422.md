# POWER_LOTTO Special V3 Research (2026-04-22)

## Inventory

- Historical +2.20% source is the 1000-period, 1-pick V3 claim documented in lottery_api/CLAUDE.md, tools/sbp_audit_special_v3.py, and rejected/special_mab_decay_adjustment_power.json.
- tools/verify_special_v2_performance.py and tools/verify_special_v3_performance.py both instantiate the same PowerLottoSpecialPredictor, so they are wrapper labels rather than distinct independent baselines.
- tools/analyze_special_number.py contains the older exploratory V1-style family (random / hot / cold / Markov / repeater), not the current production-strength V3 stack.

### Current V3 reference rerun

| Window | Hit Rate | Edge |
|---|---:|---:|
| 150 | 18.67% | +6.17% |
| 500 | 15.80% | +3.30% |
| 1000 | 14.60% | +2.10% |
| 1500 | 14.13% | +1.63% |

## Candidate results

### special_v3_drought_regime_top2

- Thesis: Recency / drought regime on the special ball may be exploitable as a shortlist.
- Definition: Score = bounded drought gap (180 draws) + recent under-representation (24 draws) + repeat penalty (6 draws); output top-2 shortlist.
- Verdict: **WATCH**
- Missing gates: permutation p-value does not clear 0.05 in all windows, Cohen's d does not clear 1.0 in all windows

| Window | Top-k | Hit Rate | Baseline | Edge | p-value | Cohen's d | Efficiency | Leakage |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| 150 | 2 | 28.67% | 25.00% | +3.67% | 0.1493 | 1.112 | 114.7% | 150 checks |
| 500 | 2 | 27.20% | 25.00% | +2.20% | 0.1493 | 1.131 | 108.8% | 500 checks |
| 1500 | 2 | 25.60% | 25.00% | +0.60% | 0.2736 | 0.551 | 102.4% | 1500 checks |

### special_v3_markov_backoff_top2

- Thesis: Recent transition structure may help if first-order and second-order states are blended with an under-owned backoff.
- Definition: Score = 55% first-order transition + 25% second-order transition + 20% recent under-representation, using a 360-draw state window; output top-2 shortlist.
- Verdict: **WATCH**
- Missing gates: permutation p-value does not clear 0.05 in all windows, Cohen's d does not clear 1.0 in all windows

| Window | Top-k | Hit Rate | Baseline | Edge | p-value | Cohen's d | Efficiency | Leakage |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| 150 | 2 | 30.00% | 25.00% | +5.00% | 0.0995 | 1.479 | 120.0% | 150 checks |
| 500 | 2 | 25.80% | 25.00% | +0.80% | 0.4129 | 0.341 | 103.2% | 500 checks |
| 1500 | 2 | 26.33% | 25.00% | +1.33% | 0.1294 | 1.115 | 105.3% | 1500 checks |

### special_v3_main_analog_residual_top2

- Thesis: A special-only shortlist might be improved by retrieving historical specials under main-zone states analogous to the latest observed main-zone configuration, then blending with drought.
- Definition: Score = 50% main-zone analog retrieval over the latest observed main-zone state (sum / odd count / Z3 count over 360 draws) + 50% drought-regime score; output top-2 shortlist.
- Verdict: **WATCH**
- Missing gates: permutation p-value does not clear 0.05 in all windows, Cohen's d does not clear 1.0 in all windows

| Window | Top-k | Hit Rate | Baseline | Edge | p-value | Cohen's d | Efficiency | Leakage |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| 150 | 2 | 29.33% | 25.00% | +4.33% | 0.1393 | 1.270 | 117.3% | 150 checks |
| 500 | 2 | 26.40% | 25.00% | +1.40% | 0.2139 | 0.837 | 105.6% | 500 checks |
| 1500 | 2 | 26.33% | 25.00% | +1.33% | 0.1144 | 1.207 | 105.3% | 1500 checks |

## Final conclusion

- Overall verdict: **WATCH**
- Best candidate: `special_v3_main_analog_residual_top2`
- RSM note: WATCH only; not a direct RSM upgrade and not worth displacing the current V3 stack.
- Worth making the next main POWER_LOTTO research priority? **no**
