# P68: All-Strategy Executability Inventory Scan

**Date:** 2026-05-26
**Task:** P68
**Status:** EVIDENCE_ONLY
**DB Writes:** None
**Production rows before:** 46960
**Production rows after:** 46960 (unchanged)

---

## Executive Summary

This document is a comprehensive read-only inventory of all strategy candidates in the
LotteryNew system, classified into executability buckets for Milestone 2 planning.

Total unique strategy-name/lottery-type combinations scanned: **31 row-backed** (31 in DB with rows > 0),
plus additional registry-tracked and research-documented candidates.

The P0 strategy universe inventory (outputs/replay/p0_strategy_universe_inventory_20260517.json)
enumerates 512 entries across DAILY_539 (67), BIG_LOTTO (163), POWER_LOTTO (80),
UNSPECIFIED (187), and CROSS_GAME (15). Most UNSPECIFIED and CROSS_GAME entries are
research scripts, tool functions, or rejected hypotheses — not deployable strategies.
This inventory focuses on actionable strategy candidates with clear lottery-type bindings.

---

## Classification Bucket Summary

| Bucket | Count | Description |
|--------|-------|-------------|
| **row-backed** | 31 | strategy_name in DB with >= 1500 rows |
| **executable-no-row** | 0 | adapter exists, 0 rows currently |
| **adapter-needed** | 0 | identifiable strategy, no adapter function |
| **unsupported** | 2 | depends on unavailable data / deprecated models |
| **rejected** | 6 | REJECTED lifecycle in registry or p-value failure |
| **dependency-blocked** | 0 | requires another strategy / system first |
| **manual-review** | 0 | ambiguous or insufficient evidence |
| **no-data** | 0 | requires data not in lottery_v2.db |
| **artifact-only** | 4 | docs/reports only, no executable adapter |
| **code-only** | 6 | model code exists, no replay adapter wrapper |
| **reconstructible** | 0 | could be re-derived with moderate effort |
| **sub-baseline** | 2 | row-backed but M3+ < lottery baseline |
| **fallback-equivalent** | 1 | row-backed M3+ ~= baseline with regime caveat |

NOTE: sub-baseline and fallback-equivalent are sub-classifications within row-backed.
They are disclosed as performance labels, not separate mutually-exclusive buckets.

---

## Section 1: DAILY_539 Strategies

**Baseline:** 1-bet M3+ ≈ depends on draw; tracked via RSM.
**Signal status:** L82 — signal space exhausted (H001~H008 all REJECT/FAST_REJECT).
**Production strategies:** acb_single_539, 539_3bet_orthogonal (best validated).

### Row-Backed Strategies (DAILY_539)

| strategy_name | strategy_id | bucket | rows | truth_level | apply_id | notes |
|---|---|---|---|---|---|---|
| 今彩539 ACB 1注 | acb_1bet | row-backed | 1500 | DAILY539_RETIRED_STRATEGY_BACKFILL_VERIFIED | P31B | RETIRED lifecycle |
| 今彩539 ACB Single 1注 | acb_single_539 | row-backed | 1500 | DAILY539_WAVE2_STRATEGY_BACKFILL_VERIFIED | P37 | ACTIVE/production |
| 今彩539 ACB+Markov 中頻 | acb_markov_midfreq | row-backed | 1500 | DAILY539_RETIRED_STRATEGY_BACKFILL_VERIFIED | P31B | RETIRED lifecycle |
| 今彩539 ACB+Markov 中頻 3注 | acb_markov_midfreq_3bet | row-backed | 1500 | DAILY539_RETIRED_STRATEGY_BACKFILL_VERIFIED | P31B | RETIRED lifecycle |
| 今彩539 ACB+Markov+Fourier 正交 3注 | 539_3bet_orthogonal | row-backed | 1500 | DAILY539_WAVE2_STRATEGY_BACKFILL_VERIFIED | P37 | ACTIVE/production |
| 今彩539 F4 Cold | daily539_f4cold | row-backed | 1590 | null (legacy) | null | ONLINE registry; 90 legacy rows |
| 今彩539 Fourier4正交 cold+midfreq 3注 | p0b_539_3bet_f_cold_fmid | row-backed | 1500 | DAILY539_WAVE2_STRATEGY_BACKFILL_VERIFIED | P37 | ACTIVE/production |
| 今彩539 Fourier4正交 x2 cold 3注 | p0c_539_3bet_f_cold_x2 | row-backed | 1500 | DAILY539_WAVE2_STRATEGY_BACKFILL_VERIFIED | P37 | ACTIVE/production |
| 今彩539 Markov 1注 | markov_1bet_539 | row-backed | 1500 | DAILY539_WAVE2_STRATEGY_BACKFILL_VERIFIED | P37 | ACTIVE/production |
| 今彩539 Markov Cold | daily539_markov_cold | row-backed | 1590 | null (legacy) | null | ONLINE registry; 90 legacy rows |
| 今彩539 Zone+Gap 3注 | zone_gap_3bet_539 | row-backed | 1500 | DAILY539_WAVE2_STRATEGY_BACKFILL_VERIFIED | P37 | ACTIVE/production |
| 今彩539 中頻 ACB 2注 | midfreq_acb_2bet | row-backed | 1500 | DAILY539_RETIRED_STRATEGY_BACKFILL_VERIFIED | P31B | RETIRED lifecycle |
| 今彩539 中頻 Fourier 2注 | midfreq_fourier_2bet | row-backed | 1500 | DAILY539_RETIRED_STRATEGY_BACKFILL_VERIFIED | P31B | RETIRED lifecycle |

**DAILY_539 M3+ Performance (from DB, hit_count >= 3):**

| strategy_name | rows | m3plus | m3plus_pct |
|---|---|---|---|
| 今彩539 ACB+Markov 中頻 | 1500 | 20 | 1.33% |
| 今彩539 中頻 ACB 2注 | 1500 | 19 | 1.27% |
| 今彩539 中頻 Fourier 2注 | 1500 | 1.27% |
| 今彩539 Markov 1注 | 1500 | 17 | 1.13% |
| 今彩539 Markov Cold | 1590 | 18 | 1.13% |
| 今彩539 ACB 1注 | 1500 | 16 | 1.07% |
| 今彩539 ACB Single 1注 | 1500 | 16 | 1.07% |
| 今彩539 ACB+Markov 中頻 3注 | 1500 | 16 | 1.07% |
| 今彩539 ACB+Markov+Fourier 正交 3注 | 1500 | 16 | 1.07% |
| 今彩539 Fourier4正交 cold+midfreq 3注 | 1500 | 13 | 0.87% |
| 今彩539 Fourier4正交 x2 cold 3注 | 1500 | 13 | 0.87% |
| 今彩539 F4 Cold | 1590 | 13 | 0.82% |
| 今彩539 Zone+Gap 3注 | 1500 | 11 | 0.73% |

### Registry-Only (Non-Executable) DAILY_539

| strategy_id | lifecycle | bucket | reason |
|---|---|---|---|
| p1_deviation_2bet_539 | REJECTED | rejected | McNemar p > 0.05, L82 signal exhaustion |

---

## Section 2: BIG_LOTTO Strategies

**Baseline:** 1-bet M3+ = 1.86% (1-49 choose 6).
**Signal status:** L91 — 49C6 statistically indistinguishable from fair random process.
All BIG_LOTTO strategies are coverage-only; sub-baseline results are expected.
**Maintenance mode:** No new signal research authorized (L90 final conclusion).

### Row-Backed Strategies (BIG_LOTTO)

| strategy_name | strategy_id | bucket | rows | truth_level | apply_id | notes |
|---|---|---|---|---|---|---|
| 大樂透 Cold Complement 2注 | cold_complement_biglotto | row-backed | 1500 | BIGLOTTO_WAVE3_STRATEGY_BACKFILL_VERIFIED | P43 | |
| 大樂透 Cold Pool-15 Pick-6 | coldpool15_biglotto | row-backed | 1500 | BIGLOTTO_WAVE3_STRATEGY_BACKFILL_VERIFIED | P43 | |
| 大樂透 Deviation 2注 | biglotto_deviation_2bet | row-backed | 1570 | null (legacy) | null | 70 legacy rows; ONLINE registry |
| 大樂透 Fourier 2注 Expansion | bet2_fourier_expansion_biglotto | row-backed | 1500 | BIGLOTTO_WAVE3_STRATEGY_BACKFILL_VERIFIED | P43 | |
| 大樂透 Fourier30+Markov30 | fourier30_markov30_biglotto | row-backed | 1500 | BIGLOTTO_WAVE3_STRATEGY_BACKFILL_VERIFIED | P43 | |
| 大樂透 Markov 2注 | markov_2bet_biglotto | row-backed | 1500 | BIGLOTTO_WAVE3_STRATEGY_BACKFILL_VERIFIED | P43 | |
| 大樂透 Markov Single 1注 | markov_single_biglotto | row-backed | 1500 | BIGLOTTO_WAVE3_STRATEGY_BACKFILL_VERIFIED | P43 | |
| 大樂透 TS3+Regime 3注 | ts3_regime_3bet | row-backed | 1500 | BIGLOTTO_SINGLE_STRATEGY_BACKFILL_VERIFIED | P14D | ONLINE registry |
| 大樂透 Triple Strike | biglotto_triple_strike | row-backed | 1570 | null (legacy) | null | 70 legacy rows; ONLINE registry |

**BIG_LOTTO M3+ Performance (baseline 1-bet = 1.86%):**

| strategy_name | rows | m3plus | m3plus_pct | vs_1bet_baseline |
|---|---|---|---|---|
| 大樂透 Triple Strike | 1570 | 39 | 2.48% | +0.62pp |
| 大樂透 Fourier 2注 Expansion | 1500 | 36 | 2.40% | +0.54pp (2-bet) |
| 大樂透 TS3+Regime 3注 | 1500 | 36 | 2.40% | +0.54pp (3-bet) |
| 大樂透 Deviation 2注 | 1570 | 37 | 2.36% | +0.50pp (2-bet) |
| 大樂透 Markov 2注 | 1500 | 23 | 1.53% | -0.33pp (2-bet) |
| 大樂透 Markov Single 1注 | 1500 | 23 | 1.53% | -0.33pp |
| 大樂透 Cold Complement 2注 | 1500 | 22 | 1.47% | -0.39pp (2-bet) |
| 大樂透 Cold Pool-15 Pick-6 | 1500 | 22 | 1.47% | -0.39pp |
| 大樂透 Fourier30+Markov30 | 1500 | 21 | 1.40% | -0.46pp (2-bet) |

NOTE: BIG_LOTTO 49C6 pool is signal-exhausted (L91). All M3+ rates are within
noise band (99th pct MC baseline = +0.778% edge). TS3+Regime 3注 and Triple Strike
show above-1-bet-baseline rates on a per-draw basis due to multi-bet coverage.

### Registry-Only (Non-Executable) BIG_LOTTO

| strategy_id | lifecycle | bucket | reason |
|---|---|---|---|
| biglotto_ts3_acb_4bet | REJECTED | rejected | McNemar p=0.074, marginal efficiency <80% (L56) |
| biglotto_ts3_markov_freq_5bet | REJECTED | rejected | SUPERSEDED by P1+deviation+sum; archived |

### Code-Only BIG_LOTTO (no replay adapter)

| strategy_id | code_file | bucket | notes |
|---|---|---|---|
| biglotto_2bet_deviation_complement | tools/predict_biglotto_deviation_2bet.py | code-only | No wave adapter; aliased to biglotto_deviation_2bet |
| biglotto_3bet_triple_strike_v2 | tools/predict_biglotto_triple_strike.py | code-only | v2 Sum-Constraint; not in wave adapter files |
| biglotto_4bet_p1_deviation | tools/backtest_p1dev_4bet.py | code-only | P1+deviation 4-bet; no adapter |
| biglotto_5bet_p1_dev_sum | tools/quick_predict.py | code-only | P1+deviation+sum 5-bet; production but no replay rows |

---

## Section 3: POWER_LOTTO Strategies

**Baseline:** 1-bet M3+ = 3.87% (1-38 choose 6 main numbers).
**Signal status:** Active — MidFreq and Fourier signals validated (L83).
**Best validated:** fourier30_markov30_2bet (Wave 5, prediction-helpful, M3+ 4.07%).

### Row-Backed Strategies (POWER_LOTTO)

| strategy_name | strategy_id | bucket | rows | truth_level | apply_id | notes |
|---|---|---|---|---|---|---|
| fourier30_markov30_2bet | fourier30_markov30_2bet | row-backed / prediction-helpful | 1500 | POWER_LOTTO_WAVE5_CONTROLLED_APPLY_VERIFIED | P58 | M3+ 4.07% > 3.87% baseline |
| 威力彩 Fourier Rhythm 3注 | fourier_rhythm_3bet | row-backed | 1500 | POWERLOTTO_SINGLE_STRATEGY_BACKFILL_VERIFIED | P19B | ONLINE |
| 威力彩 MidFreq+Fourier 2注 | midfreq_fourier_2bet | row-backed | 1500 | POWERLOTTO_WAVE4_STRATEGY_BACKFILL_VERIFIED | P48 | ACTIVE |
| 威力彩 MidFreq+Fourier+Markov 3注 | midfreq_fourier_mk_3bet | row-backed | 1500 | POWERLOTTO_WAVE4_STRATEGY_BACKFILL_VERIFIED | P48 | ACTIVE |
| 威力彩 Orthogonal 5注 | power_orthogonal_5bet | row-backed | 1570 | null (legacy) | null | 70 legacy rows; ONLINE registry |
| 威力彩 PP3+FreqOrt 4注 | pp3_freqort_4bet | row-backed | 1500 | POWERLOTTO_WAVE4_STRATEGY_BACKFILL_VERIFIED | P48 | ACTIVE; best M3+ 5.40% |
| 威力彩 Precision 3注 | power_precision_3bet | row-backed | 1570 | null (legacy) | null | 70 legacy rows; ONLINE registry |
| 威力彩 Zonal Entropy 2注 | zonal_entropy_2bet | row-backed / fallback-equivalent | 1500 | POWER_LOTTO_WAVE6_CONTROLLED_APPLY_VERIFIED | P66 | M3+ 3.67%; regime 100% chaotic |
| 威力彩 冷號互補 2注 | cold_complement_2bet | row-backed / sub-baseline | 1500 | POWER_LOTTO_WAVE6_CONTROLLED_APPLY_VERIFIED | P66 | M3+ 3.67% < 3.87% baseline |

**POWER_LOTTO M3+ Performance (baseline 1-bet = 3.87%):**

| strategy_name | rows | m3plus | m3plus_pct | vs_baseline |
|---|---|---|---|---|
| 威力彩 PP3+FreqOrt 4注 | 1500 | 81 | 5.40% | +1.53pp |
| 威力彩 Fourier Rhythm 3注 | 1500 | 74 | 4.93% | +1.06pp |
| 威力彩 Orthogonal 5注 | 1570 | 77 | 4.90% | +1.03pp |
| 威力彩 Precision 3注 | 1570 | 77 | 4.90% | +1.03pp |
| 威力彩 MidFreq+Fourier 2注 | 1500 | 70 | 4.67% | +0.80pp |
| 威力彩 MidFreq+Fourier+Markov 3注 | 1500 | 66 | 4.40% | +0.53pp |
| fourier30_markov30_2bet | 1500 | 61 | 4.07% | +0.20pp (prediction-helpful) |
| 威力彩 Zonal Entropy 2注 | 1500 | 55 | 3.67% | -0.20pp (fallback-equivalent) |
| 威力彩 冷號互補 2注 | 1500 | 55 | 3.67% | -0.20pp (sub-baseline) |

### Registry-Only (Non-Executable) POWER_LOTTO

| strategy_id | lifecycle | bucket | reason |
|---|---|---|---|
| power_shlc_midfreq | REJECTED | rejected | SHLC 中頻指標 REJECTED (L50) |
| h6_gate_mk20_ew85 | OBSERVATION | artifact-only | Experimental; no replay rows |

### Code-Only POWER_LOTTO (no replay adapter)

| strategy_id | code_file | bucket | notes |
|---|---|---|---|
| power_twin_strike_2bet | tools/power_twin_strike.py | code-only | Cold complement 2-bet v1 (superseded by wave6) |
| power_triple_strike | tools/power_triple_strike.py | code-only | Superseded by Power Precision |

---

## Section 4: Performance Disclosures (Pre-Confirmed)

### fourier30_markov30_2bet — PREDICTION-HELPFUL

- Lottery type: POWER_LOTTO
- strategy_id: fourier30_markov30_2bet
- Controlled apply: P58_POWERLOTTO_WAVE5_FOURIER30_MARKOV30_1500_PROD_20260525
- Rows: 1500
- M3+ hit rate: **4.07%** (61/1500)
- Baseline (1-bet): 3.87%
- Edge: **+0.20pp** above baseline
- Label: PREDICTION-HELPFUL — exceeds random baseline, suitable for prediction use

### cold_complement_2bet — SUB-BASELINE

- Lottery type: POWER_LOTTO
- strategy_id: cold_complement_2bet (威力彩 冷號互補 2注)
- Controlled apply: P66_POWERLOTTO_WAVE6_COLD_COMPLEMENT_1500_PROD_20260525
- Rows: 1500
- M3+ hit rate: **3.67%** (55/1500)
- Baseline (1-bet): 3.87%
- Edge: **-0.20pp** below baseline
- Label: SUB-BASELINE — does not exceed random baseline; for coverage/tracking only

### zonal_entropy_2bet — FALLBACK-EQUIVALENT

- Lottery type: POWER_LOTTO
- strategy_id: zonal_entropy_2bet (威力彩 Zonal Entropy 2注)
- Controlled apply: P66_POWERLOTTO_WAVE6_ZONAL_ENTROPY_1500_PROD_20260525
- Rows: 1500
- M3+ hit rate: **3.67%** (55/1500)
- Baseline (1-bet): 3.87%
- Edge: **-0.20pp** below baseline
- Caveat: Zonal entropy regime detected as 100% chaotic in Wave 6 window
- Label: FALLBACK-EQUIVALENT — near-baseline with specific regime caveat;
  useful as fallback when regime classification is unavailable

---

## Section 5: Row-Impact Estimates

For strategies with rows = 1500 (standard), further expansion would require:

| strategy_id | current_rows | expansion_to_2000 | expansion_to_2500 | expansion_to_3000 | notes |
|---|---|---|---|---|---|
| fourier30_markov30_2bet | 1500 | ~500 rows | ~1000 rows | ~1500 rows | POWER_LOTTO; 1 row/draw |
| cold_complement_2bet | 1500 | ~500 rows | ~1000 rows | ~1500 rows | POWER_LOTTO; 1 row/draw |
| zonal_entropy_2bet | 1500 | ~500 rows | ~1000 rows | ~1500 rows | POWER_LOTTO; 1 row/draw |
| ts3_regime_3bet | 1500 | ~500 rows | ~1000 rows | ~1500 rows | BIG_LOTTO; 1 row/draw |
| 539_3bet_orthogonal | 1500 | ~500 rows | ~1000 rows | ~1500 rows | DAILY_539; 1 row/draw |
| pp3_freqort_4bet | 1500 | ~500 rows | ~1000 rows | ~1500 rows | POWER_LOTTO; 1 row/draw |
| fourier_rhythm_3bet | 1500 | ~500 rows | ~1000 rows | ~1500 rows | POWER_LOTTO; 1 row/draw |

All wave-adapter-backed strategies share the same history depth: ~1500 draws available.
Extending beyond 1500 draws would require importing older draw history not currently
present in lottery_v2.db for the relevant lottery type.

**Current DB draw history depth per lottery type (approximate):**
- DAILY_539: ~1500+ draws available in DB (deep history)
- BIG_LOTTO: ~1500+ draws available
- POWER_LOTTO: ~1500+ draws available

Next-prediction-only expansion (1 row per future draw): All ONLINE strategies
generate 1 new row per draw cycle via the post-draw pipeline.

---

## Section 6: Complete Row-Backed Strategy List (31 strategies)

| # | strategy_name | lottery_type | rows | strategy_id |
|---|---|---|---|---|
| 1 | 今彩539 ACB 1注 | DAILY_539 | 1500 | acb_1bet |
| 2 | 今彩539 ACB Single 1注 | DAILY_539 | 1500 | acb_single_539 |
| 3 | 今彩539 ACB+Markov 中頻 | DAILY_539 | 1500 | acb_markov_midfreq |
| 4 | 今彩539 ACB+Markov 中頻 3注 | DAILY_539 | 1500 | acb_markov_midfreq_3bet |
| 5 | 今彩539 ACB+Markov+Fourier 正交 3注 | DAILY_539 | 1500 | 539_3bet_orthogonal |
| 6 | 今彩539 F4 Cold | DAILY_539 | 1590 | daily539_f4cold |
| 7 | 今彩539 Fourier4正交 cold+midfreq 3注 | DAILY_539 | 1500 | p0b_539_3bet_f_cold_fmid |
| 8 | 今彩539 Fourier4正交 x2 cold 3注 | DAILY_539 | 1500 | p0c_539_3bet_f_cold_x2 |
| 9 | 今彩539 Markov 1注 | DAILY_539 | 1500 | markov_1bet_539 |
| 10 | 今彩539 Markov Cold | DAILY_539 | 1590 | daily539_markov_cold |
| 11 | 今彩539 Zone+Gap 3注 | DAILY_539 | 1500 | zone_gap_3bet_539 |
| 12 | 今彩539 中頻 ACB 2注 | DAILY_539 | 1500 | midfreq_acb_2bet |
| 13 | 今彩539 中頻 Fourier 2注 | DAILY_539 | 1500 | midfreq_fourier_2bet (539) |
| 14 | 大樂透 Cold Complement 2注 | BIG_LOTTO | 1500 | cold_complement_biglotto |
| 15 | 大樂透 Cold Pool-15 Pick-6 | BIG_LOTTO | 1500 | coldpool15_biglotto |
| 16 | 大樂透 Deviation 2注 | BIG_LOTTO | 1570 | biglotto_deviation_2bet |
| 17 | 大樂透 Fourier 2注 Expansion | BIG_LOTTO | 1500 | bet2_fourier_expansion_biglotto |
| 18 | 大樂透 Fourier30+Markov30 | BIG_LOTTO | 1500 | fourier30_markov30_biglotto |
| 19 | 大樂透 Markov 2注 | BIG_LOTTO | 1500 | markov_2bet_biglotto |
| 20 | 大樂透 Markov Single 1注 | BIG_LOTTO | 1500 | markov_single_biglotto |
| 21 | 大樂透 TS3+Regime 3注 | BIG_LOTTO | 1500 | ts3_regime_3bet |
| 22 | 大樂透 Triple Strike | BIG_LOTTO | 1570 | biglotto_triple_strike |
| 23 | fourier30_markov30_2bet | POWER_LOTTO | 1500 | fourier30_markov30_2bet |
| 24 | 威力彩 Fourier Rhythm 3注 | POWER_LOTTO | 1500 | fourier_rhythm_3bet |
| 25 | 威力彩 MidFreq+Fourier 2注 | POWER_LOTTO | 1500 | midfreq_fourier_2bet (PL) |
| 26 | 威力彩 MidFreq+Fourier+Markov 3注 | POWER_LOTTO | 1500 | midfreq_fourier_mk_3bet |
| 27 | 威力彩 Orthogonal 5注 | POWER_LOTTO | 1570 | power_orthogonal_5bet |
| 28 | 威力彩 PP3+FreqOrt 4注 | POWER_LOTTO | 1500 | pp3_freqort_4bet |
| 29 | 威力彩 Precision 3注 | POWER_LOTTO | 1570 | power_precision_3bet |
| 30 | 威力彩 Zonal Entropy 2注 | POWER_LOTTO | 1500 | zonal_entropy_2bet |
| 31 | 威力彩 冷號互補 2注 | POWER_LOTTO | 1500 | cold_complement_2bet |

---

## Section 7: Executable-No-Row Strategies

All strategies with adapters currently have rows in the DB. There are no strategies
with working adapter functions but 0 rows at the time of this scan.

The following are ONLINE adapters with row-backed status confirmed:
- power_precision_3bet: 1570 rows (legacy)
- power_orthogonal_5bet: 1570 rows (legacy)
- fourier_rhythm_3bet: 1500 rows (P19B)
- biglotto_triple_strike: 1570 rows (legacy)
- biglotto_deviation_2bet: 1570 rows (legacy)
- ts3_regime_3bet: 1500 rows (P14D)
- daily539_f4cold: 1590 rows (legacy)
- daily539_markov_cold: 1590 rows (legacy)

Result: **executable-no-row count = 0**

---

## Section 8: Rejected Strategies

| strategy_id | lottery_type | reason | reference |
|---|---|---|---|
| biglotto_ts3_acb_4bet | BIG_LOTTO | McNemar p=0.074, efficiency <80% | L56 |
| biglotto_ts3_markov_freq_5bet | BIG_LOTTO | SUPERSEDED by P1+deviation | MEMORY.md |
| power_shlc_midfreq | POWER_LOTTO | SHLC 中頻指標 REJECTED | L50 |
| p1_deviation_2bet_539 | DAILY_539 | Signal non-transferable from BIG_LOTTO | L84 |
| lag_reversion_2bet | POWER_LOTTO | P64b GATE_FAIL (mini-backtest) | P64b commit |
| h6_gate_mk20_ew85 | POWER_LOTTO | OBSERVATION only; no production rows | Registry |

---

## Section 9: Artifact-Only Strategies

Strategies documented in research outputs but with no executable adapter:

| strategy_id | artifact_location | notes |
|---|---|---|
| h6_gate_mk20_ew85 | docs/replay/ | OBSERVATION stub in registry; no rows |
| biglotto_2bet_deviation_complement | lottery_api/CLAUDE.md | Documented as early strategy; subsumed |
| power_fourier_rhythm_2bet | data/rolling_monitor_POWER_LOTTO.json | RSM tracked variant; superseded by wave adapters |
| bl_ts3_m4_fo | P0 inventory | Research ID only; no adapter |

---

## Governance Attestation

- **drift_guard:** PASS (both pre and post)
- **branch_governance_guard:** PASS (branch=p68-all-strategy-executability-inventory-scan, rows=46960)
- **project_context_lock:** LotteryNew confirmed
- **cross-project scan:** NO_CROSS_PROJECT_CONTEXT_FOUND
- **DB writes:** None (read-only scan)
- **lifecycle promotions:** None
- **production rows before:** 46960
- **production rows after:** 46960 (unchanged)

---

*Generated: 2026-05-26 | Task: P68 | Branch: p68-all-strategy-executability-inventory-scan*
