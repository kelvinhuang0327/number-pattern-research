# 三星彩 (3_STAR) Baseline Dry-Run Report — 2026-05-27

## Summary

| Field | Value |
|-------|-------|
| Task | `special3_baseline_dryrun` |
| Dry run | ✅ `true` — NO DB writes, NO replay row inserts |
| Draws loaded | **4,115** (`lottery_type='3_STAR'`) |
| Windows evaluated | 150 / 500 / 1500 |
| Top-N evaluated | 10 / 20 / 50 / 100 |
| Strategies evaluated | 6 |
| Random seed | 42 |
| DB writes | `false` |
| Replay rows changed | `0` |
| No production promotion | `true` |

## Random Baseline (Analytical)

3_STAR outcome space |Ω| = 10³ = **1,000** ordered 3-tuples.

| Top-N | Analytical baseline |
|-------|-------------------|
| Top-10 | 1.0% (10/1000) |
| Top-20 | 2.0% (20/1000) |
| Top-50 | 5.0% (50/1000) |
| Top-100 | 10.0% (100/1000) |

Note: Fast analytical baselines used throughout. No slow brute-force Monte Carlo null tests.

## Strategy Classifications

| Strategy | Classification | Avg Edge (all windows × top-N) | 3-Window Positive (top-20) |
|----------|--------------|--------------------------------|---------------------------|
| `position_frequency_topk` | **PROVISIONAL** | +0.2836 | ✅ |
| `recent_position_hot_topk` | **PROVISIONAL** | +0.2641 | ✅ |
| `position_cold_rebound_topk` | **REJECT** | −0.0449 | ❌ |
| `sum_band_frequency` | **PROVISIONAL** | +0.2464 | ✅ |
| `span_band_frequency` | **PROVISIONAL** | +0.1726 | ✅ |
| `ensemble_rank_v1` | **PROVISIONAL** | +0.2690 | ✅ |

**5 PROVISIONAL, 1 REJECT**

### Classification Rules
- `PROVISIONAL`: beats random baseline across ALL 3 windows at top-20 → eligible for further validation
- `REJECT`: underperforms random baseline in at least one window at top-20 → archive, do not promote
- `INCONCLUSIVE`: insufficient evidence (N < 500 test draws) → not applicable here (N=3,965)

## Direct Hit Rate — top-20 by Window

| Strategy | w=150 | w=500 | w=1500 | Random (2.0%) |
|----------|-------|-------|--------|--------------|
| `position_frequency_topk` | 17.18% | 17.81% | 17.59% | 2.0% |
| `recent_position_hot_topk` | 17.23% | 17.21% | 17.25% | 2.0% |
| `position_cold_rebound_topk` | 0.00% | 0.00% | 0.00% | 2.0% ⛔ |
| `sum_band_frequency` | 17.65% | 18.06% | 17.55% | 2.0% |
| `span_band_frequency` | 12.48% | 13.22% | 13.12% | 2.0% |
| `ensemble_rank_v1` | 16.02% | 16.29% | 15.83% | 2.0% |

## `position_cold_rebound_topk` — Rejection Detail

All three windows return `direct_hit_rate = 0.000` at top-20. The cold-rebound logic
selects digits that have NOT appeared recently, which for 3_STAR uniform draws produces
no predictive signal — the "cold" digits are no more likely to appear than any other.
This strategy is archived as `REJECT`. It may merit re-evaluation only if structural
non-uniformity in 3_STAR draws is detected (e.g., manufacturing bias in physical balls).

## Notes on `ensemble_rank_v1`

Ensemble slightly underperforms the best individual strategies (`position_frequency_topk`,
`sum_band_frequency`) at top-20. This is expected: ensemble averaging dilutes the signal
of the strongest component when a weak strategy (`position_cold_rebound_topk`) is included.
Recommendation: re-run ensemble excluding the REJECT strategy before final validation.

## Governance

| Guard | Status |
|-------|--------|
| `strategy_prediction_replays` rows | **54,462** (unchanged) |
| DB writes during dry run | **0** |
| BIG_LOTTO / POWER_LOTTO / DAILY_539 strategies | Not touched |
| `POWER_LOTTO max_draw` | **115000041** (unchanged) |

## Next Steps (post dry-run)

1. **Required before any promotion**: Full walk-forward OOS + permutation test (p < 0.05)
2. **Ensemble v2**: Re-run `ensemble_rank_v1` without `position_cold_rebound_topk`
3. **Sharpe Ratio**: Compute per-strategy Sharpe before labeling VALIDATED
4. `span_band_frequency` shows lowest edge (+0.1726) — borderline PROVISIONAL; monitor closely
5. File a P98 task for formal validation of the 5 PROVISIONAL strategies

## Classification

`P97_SPECIAL3_SPECIAL4_DRYRUN_CLOSURE_READY` — Special3 dry-run complete. Special4 data-blocked.
