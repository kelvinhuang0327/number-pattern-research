# P172 — POWER_LOTTO New Strategy Prototype Plan

**Task**: `P172_POWER_LOTTO_NEW_STRATEGY_PROTOTYPE_PLAN_ONLY`
**Final Classification**: `P172_POWER_LOTTO_NEW_STRATEGY_PROTOTYPE_PLAN_READY`
**Date**: 2026-06-01
**Branch**: `claude/zen-gates-ff6802`
**Authorization Phrase**: `YES start P172 POWER_LOTTO new strategy prototype plan`

---

## Phase 0 Verification — PASS

| Check | Expected | Actual | Status |
|-------|----------|--------|--------|
| Repo | `zen-gates-ff6802` | `/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802` | PASS |
| Branch | `claude/zen-gates-ff6802` | `claude/zen-gates-ff6802` | PASS |
| DB rows | `94924` | `94924` | PASS |
| Drift guard | PASS | PASS | PASS |
| P167 script | PASS | PASS | PASS |
| P170 script | PASS | PASS | PASS |
| P161–P171 tests | 584 PASS | 584 PASS | PASS |
| P171 classification | `DISCOVERY_PLAN_READY` | `P171_POWER_LOTTO_NEW_STRATEGY_FEATURE_ENGINEERING_DISCOVERY_PLAN_READY` | PASS |

---

## P171 Summary

R1 (P161–P170) closed with `NO_DEFENSIBLE_EDGE_FOUND`. P171 inventoried 10 feature families and 8 strategy candidates not evaluated in R1 — plan only, no implementation, no edge found.

**P172 does NOT represent a finding of edge or success-rate improvement.**

---

## Data Availability Check

A key finding from Phase 0: the `draws` table contains **1,913 actual POWER_LOTTO draw records** (numbers format: JSON array of 6 integers from 1–38, plus special 1–8). This means **all 10 feature families from P171 can be computed from existing DB tables** — no external data source is required for any of the 8 strategy candidates.

| Table | Rows | Use |
|-------|------|-----|
| `strategy_prediction_replays` (POWER_LOTTO) | 36,000 | OOS evaluation (hit_count, predicted_numbers, actual_numbers) |
| `draws` (POWER_LOTTO) | 1,913 | Feature extraction (actual historical draw numbers) |

---

## Top 3 Prototype Candidates

### Rank 1 — C01: Weighted Recency Frequency Strategy

**Feature family**: F01 (recency frequency features)

**Why top 3**: Uses only `draws` table with exponential decay weighting. Theoretically motivated by P170-confirmed non-stationarity (recent draws differ from historical). Single pre-declarable parameter (decay half-life). Most distinct from existing uniform-window MidFreq. Lowest implementation complexity among recency-based approaches.

| Field | Value |
|-------|-------|
| Data source | `draws` table (actual numbers per draw) |
| External data needed | No |
| Leakage risk | LOW |
| Overfitting risk | MEDIUM (single decay parameter, pre-declared) |
| Min OOS draws | 200 |

**P173 pre-declared config**:
- `decay_half_life_draws = 50`
- `lookback_window_draws = 200`
- `top_k = 6`

**P173 prototype scope**: Read-only query against `draws` table. Compute decay-weighted frequency vector per number 1–38 using strictly prior draws. Select top-6 by weight. Evaluate against `actual_numbers` in replay DB. No DB write.

**Comparison baselines**: 36/38 random (0.9474), C08 constrained random, P161 pool mean (0.9674)

---

### Rank 2 — C02: Gap-Adjusted Overdue Strategy

**Feature family**: F05 (gap/overdue/last-seen distance features)

**Why top 3**: Lowest overfitting risk of all 8 candidates (single threshold, theoretically grounded by geometric distribution). Mean gap under fair random model = 38/6 ≈ 6.33 is a fixed theoretical value requiring no estimation from data. Cleanest null hypothesis: if overdue signal has no predictive power, z-scores are uncorrelated with future hits. Clearest falsification criterion.

| Field | Value |
|-------|-------|
| Data source | `draws` table (gap computation) |
| External data needed | No |
| Leakage risk | LOW |
| Overfitting risk | LOW (geometric mean is theoretical; only z-threshold is free) |
| Min OOS draws | 200 |

**P173 pre-declared config**:
- `overdue_z_threshold = 1.5`
- `geometric_mean_gap = 6.333` (= 38/6, theoretical)
- `top_k = 6`

**P173 prototype scope**: Read-only query. For each target_draw, compute draws_since_last_hit for each number 1–38 from prior draws only. Compute z-score vs geometric mean. Select top-6 by z-score. Evaluate against replay DB. No DB write.

**Comparison baselines**: 36/38 random (0.9474), `冷號互補` existing strategy, C08 constrained random

---

### Rank 3 — C04: Zone-Balanced Frequency Strategy

**Feature family**: F07 (high/low/zone distribution features)

**Why top 3**: Zone boundaries are fixed mathematical partitions (low=1–13, mid=14–25, high=26–38), eliminating boundary-tuning leakage entirely. Zone-count targets derived from first 500 training draws only — no OOS leakage. Most distinct from all existing strategies (Zonal Entropy measures entropy of prediction set; this constrains the zone-count distribution of selected numbers — a different mechanism). Can be implemented with pure SQL/Python without complex numerical methods.

| Field | Value |
|-------|-------|
| Data source | `draws` table (actual numbers for zone frequency) |
| External data needed | No |
| Leakage risk | LOW |
| Overfitting risk | MEDIUM (zone-count targets from training split only) |
| Min OOS draws | 200 |

**P173 pre-declared config**:
- Zone low: 1–13 (13 numbers), mid: 14–25 (12 numbers), high: 26–38 (13 numbers)
- Zone-count target method: empirical mode from first 500 training draws
- Selection: frequency-ranked within zone constraint
- `top_k = 6`

**P173 prototype scope**: Read-only query. Compute zone-count distribution from training draws. For each target_draw, select top-6 satisfying zone balance constraint, ranked by historical frequency per zone. Evaluate against replay DB. No DB write.

**Comparison baselines**: 36/38 random (0.9474), Zonal Entropy existing strategy (P161), C08 constrained random

---

## Deferred Candidates — 5

| Candidate | Reason Deferred | Reactivation Condition |
|-----------|----------------|----------------------|
| **C03** Co-occurrence Pair Graph | HIGH overfitting risk (703 pairs → Bonferroni family=703). Min 300 OOS draws. Complexity disproportionate for first prototype. | C01/C02/C04 OOS complete |
| **C05** Entropy/Dispersion Controlled | Similar information to C04 at higher complexity. Sum/span/MAD captures draw-level diversity addressed by C04 zone balance. | C04 OOS complete; reactivate only if C04 passes primary threshold |
| **C06** Regime-Adaptive Window | HIGH overfitting risk (CUSUM threshold + window per regime). MEDIUM leakage risk (causal CUSUM requires careful engineering). C01 partially addresses non-stationarity with lower risk. | C01 OOS complete |
| **C07** Hybrid Rank Aggregation | Requires F01+F05+F06+F07 (4 families) individually validated before aggregation. Min 300 OOS. HIGH overfitting risk from weight grid. | At least 2 of C01/C02/C04 show individual OOS signal |
| **C08** Constrained Random Baseline | Null model only — not a predictive strategy. Used as comparison baseline in P173 validation runs. | N/A — implemented as baseline, not as a candidate |

---

## P173 Minimal Prototype Plan

### Feature Extraction Input Contract

| Item | Value |
|------|-------|
| Primary input table | `draws` |
| Filter | `lottery_type = 'POWER_LOTTO'` |
| Ordering | `ORDER BY CAST(draw AS INTEGER) ASC` |
| Available rows | 1,913 |
| Evaluation join | `strategy_prediction_replays` (1,499 distinct draws) |
| Numbers format | JSON array `[n1, n2, n3, n4, n5, n6]`, values 1–38 |

### Pre-Declared Candidate Configs

All configs declared here before any OOS evaluation. No tuning after seeing OOS data.

| Candidate | Parameter | Value |
|-----------|-----------|-------|
| C01 | `decay_half_life_draws` | 50 |
| C01 | `lookback_window_draws` | 200 |
| C01 | `top_k` | 6 |
| C02 | `overdue_z_threshold` | 1.5 |
| C02 | `geometric_mean_gap` | 6.333 (= 38/6, theoretical) |
| C02 | `top_k` | 6 |
| C04 | `zone_low` | 1–13 |
| C04 | `zone_mid` | 14–25 |
| C04 | `zone_high` | 26–38 |
| C04 | `zone_count_target_method` | empirical mode from first 500 training draws |
| C04 | `top_k` | 6 |

### Train/Test Time Split

- **Training**: first 1,000 POWER_LOTTO draws in `draws` table (chronological by CAST(draw AS INTEGER))
- **OOS**: draws 1,001–1,913 from `draws` table, evaluated on the subset overlapping with replay DB distinct draws (≤1,499)
- **No shuffling** — strictly time-ordered
- **Test set never used** for hyperparameter selection

### Walk-Forward OOS Protocol

- Initial training size: 500 draws (expanding window)
- Evaluation block: 50 draws per step
- No refitting on OOS data
- Accumulate all OOS results before computing final statistics

### Baseline Comparisons

| Baseline | Hit Rate | Source |
|----------|----------|--------|
| B1: Fair random 36/38 | 0.9474 | P161 confirmed |
| B2: Constrained random (C08) | computed | Monte Carlo using training zone/parity distribution |
| B3: P161 best strategy (`midfreq_fourier_mk_3bet`) | 0.9674 | P161 pool mean |

### Multiple-Testing Correction

- **Bonferroni**: family = 3, α = 0.05, threshold = 0.0167
- **BH (Benjamini-Hochberg)**: secondary
- Report both corrected and uncorrected p-values
- NULL reporting: if no candidate achieves p_bonferroni < 0.0167 on OOS walk-forward → report NULL

---

## P173 Boundary

| Allowed | Forbidden |
|---------|-----------|
| Read-only SQL queries (`draws`, `strategy_prediction_replays`) | DB write of any kind |
| Analysis scripts in `analysis/power_lotto/` only | Registry mutation |
| OOS evaluation of pre-declared C01/C02/C04 configs | Replay row insertion |
| Output artifacts in `outputs/research/power_lotto/` | Champion promotion |
| Contract test in `tests/` | controlled_apply |
| | Deployment to production |
| | Betting advice |
| | Strategy code in `lottery_api/` or `tools/` |
| | Modifying existing analysis scripts |
| | Tuning after seeing OOS data |

**P173 BLOCKED until user provides authorization phrase**: `YES start P173 POWER_LOTTO minimal prototype read-only`

---

## Governance Confirmations

| Item | Status |
|------|--------|
| DB rows before/after | 94,924 / 94,924 |
| DB write | 0 |
| Registry mutation | 0 |
| Strategy implementation | None |
| controlled_apply | Not executed |
| Champion promotion | Not executed |
| Betting advice | None |
| No win-guarantee claim | Confirmed |
| No stage/commit/push | Confirmed |
| R2 no edge found yet | Confirmed |
| P161–P171 NULL results | Stand unchanged |
| main/zen-gates split | Still unresolved |

---

## Next Task

**`P173_POWER_LOTTO_NEW_STRATEGY_MINIMAL_PROTOTYPE_READ_ONLY`**

**BLOCKED — requires explicit user authorization.**

Authorization phrase: `YES start P173 POWER_LOTTO minimal prototype read-only`

P173 scope: minimal feature extraction prototype for C01, C02, C04 only. Read-only DB. No registry mutation. No replay row insertion. No champion. No deployment. No betting advice.

---

*P172 selects Top 3 prototype candidates for further evaluation. This does not represent a finding that success-rate improvement has been identified. R2 research is ongoing — no edge has been found. All lottery games remain deeply negative EV. Ruin probability at sustained real-money play is 1.000.*
