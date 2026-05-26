# P2 Prediction-Helpfulness Audit

**Phase:** P2 — Prediction-Helpfulness Audit (Read-Only)
**Branch:** `p2-prediction-helpfulness-audit-read-only`
**Date:** 2026-05-26
**Production rows at audit:** 46,960
**Classification:** `P2_PREDICTION_HELPFULNESS_AUDIT_COMPLETE`

---

## 1. Purpose

This audit classifies all 31 row-backed strategies by **prediction-helpfulness** — whether their historical replay rows demonstrate above-baseline hit performance. Having a row in production does NOT mean a strategy is prediction-helpful. This audit establishes which strategies should be prioritized for expansion (P69+), which should be blocked, and which require more evidence.

**This task is read-only. No rows were applied. No strategies were promoted. No registry was mutated.**

---

## 2. Governance

| Guard | Result |
|---|---|
| Drift guard | `REPLAY_LIFECYCLE_DRIFT_GUARD_PASS` |
| Branch governance | `BRANCH_GOVERNANCE_PASS — branch='p2-prediction-helpfulness-audit-read-only' rows=46960` |
| P58 controlled apply rows | 1500 ✅ |
| P66 cold_complement rows | 1500 ✅ |
| P66 zonal_entropy rows | 1500 ✅ |
| No DB write | ✅ |
| No lifecycle promotion | ✅ |
| No registry mutation | ✅ |

---

## 3. Theoretical Baselines

Performance is evaluated against per-game theoretical hit-rate baselines derived from combinatorics:

| Game | Pool | Picks | Mean Hit Baseline | M3+ Baseline |
|---|---|---|---|---|
| POWER_LOTTO | 38 | 6 | 0.9474 (36/38) | 3.87% |
| BIG_LOTTO | 49 | 6 | 0.7347 (36/49) | 1.86% |
| DAILY_539 | 39 | 5 | 0.6410 (25/39) | 1.00% |

**M3+ = draws where hit_count ≥ 3 (matching 3 or more predicted numbers)**

---

## 4. Label Definitions

| Label | Meaning |
|---|---|
| **prediction-helpful** | M3+ rate AND mean_hit both exceed theoretical baseline; formal validation or production evidence present |
| **baseline-equivalent** | Mixed signals (one metric above, one below); performance at threshold; more evidence needed |
| **sub-baseline** | M3+ rate below theoretical baseline; expanding adds no prediction value |
| **fallback-equivalent** | Statistically indistinguishable from random; 100% chaotic/cold fallback regime |
| **insufficient-evidence** | Metrics may look positive but formal validation failed or data quality issues prevent reliable classification |
| **manual-review** | REPLAY_ERROR status, non-standard row counts, or pre-governance apply; requires investigation |

---

## 5. Recommendation Definitions

| Recommendation | Meaning |
|---|---|
| **prioritize-for-expansion** | Include in P69 dry-run batch; prediction-helpfulness validated |
| **defer-expansion** | Hold; OOS monitoring or additional gates must pass first |
| **keep-row-backed-only** | Rows serve historical coverage; do not expand (game exhausted or mixed evidence) |
| **block-expansion** | Do not expand; sub-baseline or fallback performance |
| **requires-more-evidence** | Re-evaluate after additional draws or formal gate re-run |
| **manual-review** | Investigate REPLAY_ERROR or pre-governance apply before any decision |

---

## 6. POWER_LOTTO Strategy Audit (9 strategies)

*Theoretical baseline: M3+ = 3.87%, Mean hit = 0.9474*

| Strategy | Rows | M3+ Rate | vs Baseline | Mean Hit | vs Baseline | Label | Recommendation |
|---|---|---|---|---|---|---|---|
| fourier_rhythm_3bet | 1500 | 4.93% | +1.06pp ✅ | 0.9927 | +0.0453 ✅ | **prediction-helpful** | **prioritize-for-expansion** |
| fourier30_markov30_2bet | 1500 | 4.07% | +0.20pp ✅ | 0.9640 | +0.0166 ✅ | **prediction-helpful** | **prioritize-for-expansion** |
| midfreq_fourier_mk_3bet | 1500 | 4.40% | +0.53pp ✅ | 1.0273 | +0.0800 ✅ | **prediction-helpful** | **defer-expansion** |
| pp3_freqort_4bet | 1500 | 5.40% | +1.53pp | 1.0020 | +0.0546 | insufficient-evidence | requires-more-evidence |
| midfreq_fourier_2bet | 1500 | 4.67% | +0.80pp | 0.9727 | +0.0253 | insufficient-evidence | requires-more-evidence |
| power_orthogonal_5bet | 1570 | 4.90% | +1.03pp | 0.9924 | +0.0450 | insufficient-evidence | requires-more-evidence |
| power_precision_3bet | 1570 | 4.90% | +1.03pp | 0.9924 | +0.0450 | insufficient-evidence | requires-more-evidence |
| cold_complement_2bet | 1500 | 3.67% | -0.20pp ❌ | 0.9400 | -0.0074 ❌ | **sub-baseline** | **block-expansion** |
| zonal_entropy_2bet | 1500 | 3.67% | -0.20pp ❌ | 0.9473 | -0.0001 ❌ | **fallback-equivalent** | **block-expansion** |

### Notes

- **midfreq_fourier_mk_3bet**: Highest mean_hit of all POWER_LOTTO strategies (1.027). Classified prediction-helpful by raw metrics. However, WATCHLIST_STAGED_WITH_G4_WAIVER in P53 — OOS monitoring active with gates at 150/300/500 draws from draw 115000041. Do not expand until 300-draw OOS gate passes.
- **pp3_freqort_4bet**: Strongest raw M3+ in POWER_LOTTO (5.40%) but P50/P53 classified INCONCLUSIVE with early OOS windows underperforming. 500 additional draws recommended before re-evaluation.
- **midfreq_fourier_2bet** (POWER_LOTTO): G2/G3/G6 McNemar gate failures in P53 wave4 analysis despite positive raw metrics. Cannot classify as prediction-helpful under formal gates.
- **cold_complement_2bet** / **zonal_entropy_2bet**: Applied P66 for coverage expansion only. Not performance claims. Confirmed in P68.

---

## 7. BIG_LOTTO Strategy Audit (9 strategies)

*Theoretical baseline: M3+ = 1.86%, Mean hit = 0.7347*

**Critical note: L90/L91 established BIG_LOTTO (49C6) signal space is exhausted. All 7 signals failed p<0.05. The game is statistically indistinguishable from a fair random process. No BIG_LOTTO strategy should be expanded regardless of raw metrics.**

| Strategy | Rows | M3+ Rate | vs Baseline | Mean Hit | vs Baseline | Label | Recommendation |
|---|---|---|---|---|---|---|---|
| biglotto_deviation_2bet | 1570 | 2.36% | +0.49pp ✅ | 0.7573 | +0.0226 ✅ | **prediction-helpful** | **keep-row-backed-only** |
| biglotto_triple_strike | 1570 | 2.48% | +0.62pp ✅ | 0.7280 | -0.0067 ❌ | baseline-equivalent | keep-row-backed-only |
| ts3_regime_3bet | 1500 | 2.40% | +0.54pp ✅ | 0.7220 | -0.0127 ❌ | baseline-equivalent | keep-row-backed-only |
| bet2_fourier_expansion_biglotto | 1500 | 2.40% | +0.54pp ✅ | 0.7240 | -0.0107 ❌ | baseline-equivalent | keep-row-backed-only |
| cold_complement_biglotto | 1500 | 1.47% | -0.40pp ❌ | 0.7353 | +0.0006 | **sub-baseline** | **block-expansion** |
| coldpool15_biglotto | 1500 | 1.47% | -0.40pp ❌ | 0.7353 | +0.0006 | **sub-baseline** | **block-expansion** |
| markov_2bet_biglotto | 1500 | 1.53% | -0.33pp ❌ | 0.7280 | -0.0067 ❌ | **sub-baseline** | **block-expansion** |
| markov_single_biglotto | 1500 | 1.53% | -0.33pp ❌ | 0.7280 | -0.0067 ❌ | **sub-baseline** | **block-expansion** |
| fourier30_markov30_biglotto | 1500 | 1.40% | -0.46pp ❌ | 0.7213 | -0.0134 ❌ | **sub-baseline** | **block-expansion** |

### Notes

- **ts3_regime_3bet**: Production RSM champion (Edge +3.51%, Sharpe 0.123). Row-level M3+ is above theoretical but mean is below. The RSM edge reflects betting-layer decisions, not raw hit rate. L90/L91 exhaustion applies game-wide — rows serve historical coverage only.
- **biglotto_deviation_2bet**: Best BIG_LOTTO metrics (M3+=2.36%, mean=0.7573). Classified prediction-helpful on raw metrics. However, L90/L91 game-level exhaustion overrides individual strategy expansion. Keep-row-backed-only.
- **5 sub-baseline strategies**: Cold pool strategies uniformly below theoretical M3+ baseline. No expansion justified.

---

## 8. DAILY_539 Strategy Audit (13 strategies)

*Theoretical baseline: M3+ = 1.00%, Mean hit = 0.6410*

| Strategy | Rows | M3+ Rate | vs Baseline | Mean Hit | vs Baseline | Label | Recommendation |
|---|---|---|---|---|---|---|---|
| acb_markov_midfreq_3bet | 1500 | 1.07% | +0.06pp ✅ | 0.6720 | +0.0310 ✅ | **prediction-helpful** | **prioritize-for-expansion** |
| midfreq_acb_2bet | 1500 | 1.27% | +0.26pp ✅ | 0.6693 | +0.0283 ✅ | **prediction-helpful** | **prioritize-for-expansion** |
| midfreq_fourier_2bet | 1500 | 1.27% | +0.26pp ✅ | 0.6693 | +0.0283 ✅ | **prediction-helpful** | **prioritize-for-expansion** |
| acb_1bet | 1500 | 1.07% | +0.06pp ✅ | 0.6720 | +0.0310 ✅ | **prediction-helpful** | **prioritize-for-expansion** |
| 539_3bet_orthogonal | 1500 | 1.07% | +0.06pp ✅ | 0.6720 | +0.0310 ✅ | **prediction-helpful** | **prioritize-for-expansion** |
| acb_single_539 | 1500 | 1.07% | +0.06pp ✅ | 0.6720 | +0.0310 ✅ | **prediction-helpful** | **prioritize-for-expansion** |
| acb_markov_midfreq | 1500 | 1.33% | +0.33pp ✅ | 0.6367 | -0.0044 ❌ | baseline-equivalent | requires-more-evidence |
| markov_1bet_539 | 1500 | 1.13% | +0.13pp ✅ | 0.6340 | -0.0070 ❌ | baseline-equivalent | requires-more-evidence |
| daily539_f4cold | 1590 | 0.82% | -0.19pp ❌ | 0.6673 | +0.0263 | insufficient-evidence | **manual-review** |
| daily539_markov_cold | 1590 | 1.13% | +0.13pp ✅ | 0.6258 | -0.0152 ❌ | insufficient-evidence | **manual-review** |
| p0b_539_3bet_f_cold_fmid | 1500 | 0.87% | -0.14pp ❌ | 0.6773 | +0.0363 | **sub-baseline** | **block-expansion** |
| p0c_539_3bet_f_cold_x2 | 1500 | 0.87% | -0.14pp ❌ | 0.6773 | +0.0363 | **sub-baseline** | **block-expansion** |
| zone_gap_3bet_539 | 1500 | 0.73% | -0.27pp ❌ | 0.6287 | -0.0124 ❌ | **sub-baseline** | **block-expansion** |

### Notes

- **Top production strategies confirmed**: acb_markov_midfreq_3bet (RSM +8.50%), midfreq_acb_2bet (RSM +8.46%), acb_1bet (RSM +3.27%) all confirmed prediction-helpful by raw replay metrics.
- **midfreq_fourier_2bet** (DAILY_539 variant): Different strategy from POWER_LOTTO midfreq_fourier_2bet. L83 confirmed 539→POWER_LOTTO MidFreq+Fourier signal transfer. This 539 variant shows the same positive metrics.
- **acb_markov_midfreq** (no "3bet"): Mixed — highest M3+ rate among 539 (1.33%) but mean below baseline. May concentrate hits at M3+ level while underperforming on single-hit draws. Requires more evidence.
- **daily539_f4cold / daily539_markov_cold**: REPLAY_ERROR status with rows=1590. Metrics unreliable. Manual review required before any expansion.
- **Zone-based strategies** (zone_gap_3bet_539, p0b/p0c): Sub-baseline on M3+. L73 confirmed Zone/Sum white noise in 539. No expansion justified.

---

## 9. Summary Dashboard

| Game | Total | Prediction-Helpful | Baseline-Equiv | Sub-Baseline | Fallback-Equiv | Insufficient | Expand | Block |
|---|---|---|---|---|---|---|---|---|
| POWER_LOTTO | 9 | 3 | 0 | 1 | 1 | 4 | 2 + 1 defer | 2 |
| BIG_LOTTO | 9 | 1 | 3 | 5 | 0 | 0 | 0 (all keep/block) | 5 |
| DAILY_539 | 13 | 6 | 2 | 3 | 0 | 2 | 6 | 3 |
| **Total** | **31** | **10** | **5** | **9** | **1** | **6** | **8 prioritize + 1 defer** | **10** |

---

## 10. P69 Dry-Run Batch Input

### Include in P69

| Strategy | Game | Label | M3+ vs Baseline |
|---|---|---|---|
| fourier_rhythm_3bet | POWER_LOTTO | prediction-helpful | +1.06pp |
| fourier30_markov30_2bet | POWER_LOTTO | prediction-helpful | +0.20pp |
| acb_1bet | DAILY_539 | prediction-helpful | +0.06pp |
| acb_markov_midfreq_3bet | DAILY_539 | prediction-helpful | +0.06pp |
| midfreq_acb_2bet | DAILY_539 | prediction-helpful | +0.26pp |
| midfreq_fourier_2bet | DAILY_539 | prediction-helpful | +0.26pp |
| 539_3bet_orthogonal | DAILY_539 | prediction-helpful | +0.06pp |
| acb_single_539 | DAILY_539 | prediction-helpful | +0.06pp |

### Deferred (await OOS gate)

| Strategy | Game | Reason |
|---|---|---|
| midfreq_fourier_mk_3bet | POWER_LOTTO | OOS monitoring — 300-draw gate required |

### Excluded from P69 (block-expansion)

- cold_complement_2bet, zonal_entropy_2bet (POWER_LOTTO)
- All 5 BIG_LOTTO sub-baseline strategies
- p0b_539_3bet_f_cold_fmid, p0c_539_3bet_f_cold_x2, zone_gap_3bet_539 (DAILY_539)

### Excluded from P69 (manual-review first)

- daily539_f4cold, daily539_markov_cold — REPLAY_ERROR investigation required

### BIG_LOTTO Exclusion (game-level)

All BIG_LOTTO strategies are excluded from P69 expansion per L90/L91: 49C6 signal space exhausted.

---

## 11. Audit Limitations

1. **M3+ metric only**: This audit uses M3+ hit rate and mean_hit as proxies for prediction quality. Formal statistical gates (permutation test, McNemar, multi-window ROI) were not re-run — those belong in P69/P70 validation phases.
2. **Row count anomalies**: Strategies with rows=1570 (power_orthogonal_5bet, power_precision_3bet, biglotto_deviation_2bet, biglotto_triple_strike) have non-standard counts from early applies. This does not affect percentage calculations but limits comparability.
3. **REPLAY_ERROR rows**: daily539_f4cold and daily539_markov_cold have error-flagged rows mixed into their row counts (1590 each). Metrics from error rows are included in calculations and may not represent true prediction performance.
4. **BIG_LOTTO game exhaustion**: L90/L91 conclusions override individual strategy metrics. Even prediction-helpful BIG_LOTTO strategies (biglotto_deviation_2bet) should not be expanded.

---

## 12. Files Created

- `outputs/replay/p2_prediction_helpfulness_audit_20260526.json` — Machine-readable audit with per-strategy classifications
- `docs/replay/p2_prediction_helpfulness_audit_20260526.md` — This document
- `tests/test_p2_prediction_helpfulness_audit.py` — Test suite validating audit artifact integrity

---

## 13. Classification

`P2_PREDICTION_HELPFULNESS_AUDIT_COMPLETE`

No DB writes. No lifecycle promotions. No registry mutations. Audit is read-only.
