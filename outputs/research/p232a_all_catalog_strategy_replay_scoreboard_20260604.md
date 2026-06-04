# P232A — All-Catalog Strategy Historical Replay Scoreboard

**Date:** 20260604  
**Task:** `P232A_ALL_CATALOG_STRATEGY_HISTORICAL_REPLAY_SCOREBOARD`  
**Status:** COMPLETE / READ-ONLY / ZERO DB WRITE

> **HISTORICAL EVIDENCE ONLY.** This scoreboard covers all catalog strategies regardless of lifecycle. It is NOT a deployability ranking, NOT betting advice, and does NOT prove future predictive edge. lifecycle is a label, not an exclusion. No active deployable candidate exists in any lottery (P211A–P231B governance arc).

## Executive Summary

| Metric | Value |
|---|---|
| Total strategies in report | 41 |
| Catalog-registered (registry_presence=true) | 21 |
| With replay rows | 36 |
| No replay rows | 5 |
| LIFECYCLE_UNRESOLVED (DB-only, not in catalog) | 20 |
| DB rows (unchanged before/after) | 94924 |
| DB write performed | False |

### Per-Lottery Strategy Counts

| Lottery Type | Strategy Count |
|---|---:|
| BIG_LOTTO | 13 |
| DAILY_539 | 16 |
| POWER_LOTTO | 12 |

### Lifecycle Distribution

| Lifecycle | Count | Meaning |
|---|---:|---|
| DRY_RUN | 3 | Code dry-run artifact only; not production-eligible |
| LIFECYCLE_UNRESOLVED | 20 | In replay DB but not in any catalog; no governance decision recorded |
| OBSERVATION | 1 | Under shadow evaluation / observation |
| ONLINE | 8 | Deployed and active in replay generation |
| REJECTED | 4 | Evaluated and rejected during governance |
| RETIRED | 5 | Formally retired; old rows preserved |

## Methodology Notes

- **lifecycle is a label only** — every strategy appears in this report regardless of lifecycle status.
- **Row-level metrics** pool all bet_index rows for a strategy. For multi-bet strategies (bet_index 1,2,3…) this includes all bets combined.
- **Draw-level metrics** use the best-hit-count per draw (max across bet_index values). This better reflects the realistic outcome of placing all bets for one draw.
- **Second-zone / special** is DISPLAY ONLY — it never enters classification or ranking.
- **Baselines** for `mean_hit_count` use the formula `k*k/pool` where k = numbers picked / drawn and pool = lottery pool size (BIG_LOTTO 49, POWER_LOTTO 38 first-zone, DAILY_539 39).
- **LIFECYCLE_UNRESOLVED** strategies appear in the replay DB but are not registered in the main registry or P47 catalog. They were historically recorded but have no current governance classification.
- **Classification legend:**
  - `HISTORICAL_REPLAY_ONLY` — replay rows exist; no safe baseline comparison available
  - `NULL_OR_BASELINE_LIKE` — mean_hit_count within ±2% of random baseline
  - `WEAK_OBSERVATION_ONLY` — mean_hit_count marginally above baseline; not statistically confirmed
  - `INSUFFICIENT_ROWS` — fewer than 100 distinct draws; not enough for reliable conclusions
  - `NO_REPLAY_ROWS` — zero replay rows; catalog entry only
  - `LIFECYCLE_UNRESOLVED` — in DB but not in any catalog

## BIG_LOTTO — Historical Replay Scoreboard

> Random baseline mean_hit_count: **0.734694 (6*6/49)**  
> Tables below are **historical-only**. Not deployability ranking. Not betting advice.

### BIG_LOTTO — Strategies with Replay Rows (11 entries)

| Strategy ID | Lifecycle | Draws | Rows | BetIdx | RowMeanHit | Δbaseline | DrawMeanHit | M2+% (row) | M3+% (row) | Classification |
|---|---|---:|---:|---|---:|---:|---:|---:|---:|---|
| biglotto_deviation_2bet | ONLINE | 1550 | 1570 | 1,2 | 0.7573 | 0.0226 | 0.7574 | 15.3 | 2.4 | `WEAK_OBSERVATION_ONLY` |
| biglotto_triple_strike | ONLINE | 1550 | 1570 | 1,2 | 0.7280 | -0.0067 | 0.7265 | 13.9 | 2.5 | `NULL_OR_BASELINE_LIKE` |
| biglotto_echo_aware_3bet | LIFECYCLE_UNRESOLVED | 1500 | 4500 | 1,2,3 | 0.7478 | 0.0131 | 1.4600 | 16.0 | 2.2 | `LIFECYCLE_UNRESOLVED` |
| cold_complement_biglotto | LIFECYCLE_UNRESOLVED | 1500 | 1500 | 1 | 0.7353 | 0.0006 | 0.7353 | 14.9 | 1.5 | `LIFECYCLE_UNRESOLVED` |
| coldpool15_biglotto | LIFECYCLE_UNRESOLVED | 1500 | 1500 | 1 | 0.7353 | 0.0006 | 0.7353 | 14.9 | 1.5 | `LIFECYCLE_UNRESOLVED` |
| biglotto_ts3_markov_4bet_w30 | LIFECYCLE_UNRESOLVED | 1500 | 6000 | 1,2,3,4 | 0.7330 | -0.0017 | 1.5853 | 14.6 | 2.2 | `LIFECYCLE_UNRESOLVED` |
| markov_2bet_biglotto | LIFECYCLE_UNRESOLVED | 1500 | 1500 | 1 | 0.7280 | -0.0067 | 0.7280 | 14.4 | 1.5 | `LIFECYCLE_UNRESOLVED` |
| markov_single_biglotto | LIFECYCLE_UNRESOLVED | 1500 | 1500 | 1 | 0.7280 | -0.0067 | 0.7280 | 14.4 | 1.5 | `LIFECYCLE_UNRESOLVED` |
| bet2_fourier_expansion_biglotto | LIFECYCLE_UNRESOLVED | 1500 | 1500 | 1 | 0.7240 | -0.0107 | 0.7240 | 14.0 | 2.4 | `LIFECYCLE_UNRESOLVED` |
| ts3_regime_3bet | ONLINE | 1500 | 1500 | 1 | 0.7220 | -0.0127 | 0.7220 | 13.7 | 2.4 | `NULL_OR_BASELINE_LIKE` |
| fourier30_markov30_biglotto | LIFECYCLE_UNRESOLVED | 1500 | 1500 | 1 | 0.7213 | -0.0134 | 0.7213 | 14.0 | 1.4 | `LIFECYCLE_UNRESOLVED` |

### BIG_LOTTO — Strategies with No Replay Rows (2 entries)

| Strategy ID | Lifecycle | Catalog Source | Classification |
|---|---|---|---|
| biglotto_ts3_acb_4bet | REJECTED | MAIN_REGISTRY | `NO_REPLAY_ROWS` |
| biglotto_ts3_markov_freq_5bet | REJECTED | MAIN_REGISTRY | `NO_REPLAY_ROWS` |

## DAILY_539 — Historical Replay Scoreboard

> Random baseline mean_hit_count: **0.641026 (5*5/39)**  
> Tables below are **historical-only**. Not deployability ranking. Not betting advice.

### DAILY_539 — Strategies with Replay Rows (15 entries)

| Strategy ID | Lifecycle | Draws | Rows | BetIdx | RowMeanHit | Δbaseline | DrawMeanHit | M2+% (row) | M3+% (row) | Classification |
|---|---|---:|---:|---|---:|---:|---:|---:|---:|---|
| daily539_f4cold | ONLINE | 1550 | 1590 | 1,2,3 | 0.6786 | 0.0376 | 0.6729 | 13.8 | 0.8 | `WEAK_OBSERVATION_ONLY` |
| daily539_markov_cold | ONLINE | 1550 | 1590 | 1,2,3 | 0.6327 | -0.0083 | 0.6348 | 12.2 | 1.1 | `NULL_OR_BASELINE_LIKE` |
| p0b_539_3bet_f_cold_fmid | LIFECYCLE_UNRESOLVED | 1500 | 1500 | 1 | 0.6773 | 0.0363 | 0.6773 | 14.1 | 0.9 | `LIFECYCLE_UNRESOLVED` |
| p0c_539_3bet_f_cold_x2 | LIFECYCLE_UNRESOLVED | 1500 | 1500 | 1 | 0.6773 | 0.0363 | 0.6773 | 14.1 | 0.9 | `LIFECYCLE_UNRESOLVED` |
| acb_1bet | RETIRED | 1500 | 1500 | 1 | 0.6720 | 0.0310 | 0.6720 | 11.9 | 1.1 | `WEAK_OBSERVATION_ONLY` |
| 539_3bet_orthogonal | LIFECYCLE_UNRESOLVED | 1500 | 1500 | 1 | 0.6720 | 0.0310 | 0.6720 | 11.9 | 1.1 | `LIFECYCLE_UNRESOLVED` |
| acb_single_539 | LIFECYCLE_UNRESOLVED | 1500 | 1500 | 1 | 0.6720 | 0.0310 | 0.6720 | 11.9 | 1.1 | `LIFECYCLE_UNRESOLVED` |
| midfreq_acb_2bet | RETIRED | 1500 | 1500 | 1 | 0.6693 | 0.0283 | 0.6693 | 13.3 | 1.3 | `WEAK_OBSERVATION_ONLY` |
| midfreq_fourier_2bet | RETIRED | 1500 | 1500 | 1 | 0.6693 | 0.0283 | 0.6693 | 13.3 | 1.3 | `WEAK_OBSERVATION_ONLY` |
| acb_markov_midfreq_3bet | RETIRED | 1500 | 4500 | 1,2,3 | 0.6600 | 0.0190 | 1.2973 | 12.4 | 1.2 | `WEAK_OBSERVATION_ONLY` |
| daily539_f4cold_3bet | LIFECYCLE_UNRESOLVED | 1500 | 4500 | 1,2,3 | 0.6558 | 0.0148 | 1.3160 | 12.8 | 1.1 | `LIFECYCLE_UNRESOLVED` |
| daily539_f4cold_5bet | LIFECYCLE_UNRESOLVED | 1500 | 7500 | 1,2,3,4,5 | 0.6492 | 0.0082 | 1.6140 | 12.3 | 1.3 | `LIFECYCLE_UNRESOLVED` |
| acb_markov_midfreq | RETIRED | 1500 | 1500 | 1 | 0.6367 | -0.0044 | 0.6367 | 11.3 | 1.3 | `NULL_OR_BASELINE_LIKE` |
| markov_1bet_539 | LIFECYCLE_UNRESOLVED | 1500 | 1500 | 1 | 0.6340 | -0.0070 | 0.6340 | 12.1 | 1.1 | `LIFECYCLE_UNRESOLVED` |
| zone_gap_3bet_539 | LIFECYCLE_UNRESOLVED | 1500 | 1500 | 1 | 0.6287 | -0.0124 | 0.6287 | 10.5 | 0.7 | `LIFECYCLE_UNRESOLVED` |

### DAILY_539 — Strategies with No Replay Rows (1 entries)

| Strategy ID | Lifecycle | Catalog Source | Classification |
|---|---|---|---|
| p1_deviation_2bet_539 | REJECTED | MAIN_REGISTRY | `NO_REPLAY_ROWS` |

## POWER_LOTTO — Historical Replay Scoreboard

> Random baseline mean_hit_count: **0.947368 (6*6/38)**  
> Tables below are **historical-only**. Not deployability ranking. Not betting advice.

### POWER_LOTTO — Strategies with Replay Rows (10 entries)

| Strategy ID | Lifecycle | Draws | Rows | BetIdx | RowMeanHit | Δbaseline | DrawMeanHit | M2+% (row) | M3+% (row) | Classification |
|---|---|---:|---:|---|---:|---:|---:|---:|---:|---|
| power_orthogonal_5bet | ONLINE | 1550 | 7550 | 1,2,3,4,5 | 0.9633 | 0.0159 | 1.6477 | 23.7 | 4.3 | `NULL_OR_BASELINE_LIKE` |
| power_precision_3bet | ONLINE | 1550 | 4550 | 1,2,3 | 0.9580 | 0.0107 | 1.6394 | 23.6 | 4.1 | `NULL_OR_BASELINE_LIKE` |
| fourier_rhythm_3bet | ONLINE | 1501 | 4503 | 1,2,3 | 0.9749 | 0.0275 | 1.6236 | 24.2 | 4.5 | `WEAK_OBSERVATION_ONLY` |
| fourier30_markov30_2bet | LIFECYCLE_UNRESOLVED | 1501 | 1501 | 1 | 0.9647 | 0.0173 | 0.9647 | 23.6 | 4.1 | `LIFECYCLE_UNRESOLVED` |
| midfreq_fourier_mk_3bet | DRY_RUN | 1500 | 4500 | 1,2,3 | 0.9896 | 0.0422 | 1.5240 | 25.4 | 4.5 | `WEAK_OBSERVATION_ONLY` |
| midfreq_fourier_2bet | DRY_RUN | 1500 | 1500 | 1 | 0.9727 | 0.0253 | 0.9727 | 23.5 | 4.7 | `WEAK_OBSERVATION_ONLY` |
| pp3_freqort_4bet | DRY_RUN | 1500 | 6000 | 1,2,3,4 | 0.9710 | 0.0236 | 1.6673 | 24.2 | 4.6 | `WEAK_OBSERVATION_ONLY` |
| power_fourier_rhythm_2bet | LIFECYCLE_UNRESOLVED | 1500 | 3000 | 1,2 | 0.9633 | 0.0160 | 1.4700 | 23.8 | 4.5 | `LIFECYCLE_UNRESOLVED` |
| zonal_entropy_2bet | LIFECYCLE_UNRESOLVED | 1500 | 1500 | 1 | 0.9460 | -0.0014 | 0.9460 | 23.1 | 3.7 | `LIFECYCLE_UNRESOLVED` |
| cold_complement_2bet | LIFECYCLE_UNRESOLVED | 1500 | 1500 | 1 | 0.9407 | -0.0067 | 0.9407 | 21.9 | 3.7 | `LIFECYCLE_UNRESOLVED` |

### POWER_LOTTO — Strategies with No Replay Rows (2 entries)

| Strategy ID | Lifecycle | Catalog Source | Classification |
|---|---|---|---|
| power_shlc_midfreq | REJECTED | MAIN_REGISTRY | `NO_REPLAY_ROWS` |
| h6_gate_mk20_ew85 | OBSERVATION | MAIN_REGISTRY | `NO_REPLAY_ROWS` |

## 3_STAR — No Catalog Entries and No Replay Rows

> Per governance docs (P226–P227C): 3_STAR has 0 replay rows and 0 catalog strategies in the current registry. Straight-play is BLOCKED (positional order lost in DB sorted storage). Box-play was scanned in P227C and classified UNDERPOWERED_NO_SIGNAL. Re-scan requires ≥10,000 3_STAR or ≥17,000 4_STAR draws (currently 4,179 / 2,922 respectively).

## 4_STAR — No Catalog Entries and No Replay Rows

> Per governance docs (P226–P227C): 4_STAR has 0 replay rows and 0 catalog strategies in the current registry. Straight-play is BLOCKED (positional order lost in DB sorted storage). Box-play was scanned in P227C and classified UNDERPOWERED_NO_SIGNAL. Re-scan requires ≥10,000 3_STAR or ≥17,000 4_STAR draws (currently 4,179 / 2,922 respectively).

## Caveats

- HISTORICAL EVIDENCE ONLY — not deployability ranking, not betting advice, not future edge proof.
- lifecycle is a label only — it never excludes a strategy from this report.
- Row-level metrics pool all bet_index rows; draw-level metrics use best-bet-per-draw.
- Multi-bet strategies with more bet_index rows must not be compared directly with single-bet strategies using row-level means alone — check per_bet_index and draw_level instead.
- Second-zone / special metrics are DISPLAY_ONLY and never used in classification or ranking.
- LIFECYCLE_UNRESOLVED means the strategy_id exists in the replay DB but is not registered in the main registry or P47 catalog — no lifecycle governance decision has been recorded.
- mean_hit_count delta vs baseline is NOT a forward-looking edge estimate — it is a historical summary only.
- No active deployable candidate in any lottery (per P211A–P231B governance arc).

## Final Classification

`P232A_ALL_CATALOG_STRATEGY_HISTORICAL_REPLAY_SCOREBOARD_COMPLETE`

> DB write performed: **False** (rows 94924 → 94924).
