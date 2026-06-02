# P171 — POWER_LOTTO New Strategy Feature Engineering Discovery Plan

**Task**: `P171_POWER_LOTTO_NEW_STRATEGY_FEATURE_ENGINEERING_DISCOVERY_PLAN`
**Final Classification**: `P171_POWER_LOTTO_NEW_STRATEGY_FEATURE_ENGINEERING_DISCOVERY_PLAN_READY`
**Date**: 2026-06-01
**Branch**: `claude/zen-gates-ff6802`
**Authorization Phrase**: `YES start R2 new POWER_LOTTO strategy discovery from feature engineering, read-only planning first, no DB write`

---

## Phase 0 Verification — PASS

| Check | Expected | Actual | Status |
|-------|----------|--------|--------|
| Repo | `zen-gates-ff6802` | `/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802` | PASS |
| Branch | `claude/zen-gates-ff6802` | `claude/zen-gates-ff6802` | PASS |
| HEAD | — | `c8b423d0c1de26253be4cec79ae6de77719d1074` | PASS |
| DB rows | `94924` | `94924` | PASS |
| Drift guard | PASS | PASS | PASS |
| P167 script | PASS | PASS | PASS |
| P170 script | PASS | PASS | PASS |
| P161–P170 tests | 489 PASS | 489 PASS | PASS |
| P170 classification | `SENSITIVITY_DOES_NOT_SUPPORT_TRACKING` | `P170_POWER_LOTTO_SENSITIVITY_DOES_NOT_SUPPORT_TRACKING` | PASS |

---

## R1 Summary — No Defensible Edge Found

R1 research (P161–P170) has exhausted the existing strategy signal space for POWER_LOTTO.

| Task | Finding |
|------|---------|
| P161 Effectiveness Baseline | Zero strategies beat random after Bonferroni/BH correction (family=40). Pool mean +0.020, no corrected significance. |
| P167 Ensemble/Voting | 6-module ensemble: Module F final gate FAILED. No consistent OOS edge over random or best-single-strategy. |
| P170 Threshold Sensitivity | Signal non-stationary. Window 2 below random at ALL 5 sensitivity thresholds. Held-out signals A=0.865, E=0.920 — both below random 0.9474. |

**R1 Classification**: `NO_DEFENSIBLE_EDGE_FOUND`

Existing strategy signals exhausted: Fourier, Markov, MidFreq, Orthogonal, FreqOrt, PP3, Precision, Zonal Entropy, Cold Number.

**This conclusion stands unchanged. P171 does not revise or reframe R1 results.**

---

## Why Pivot to R2 New Strategy Discovery

The user explicitly requested exploring approaches that are not just recombinations of existing strategies. R1 has demonstrated that the existing signal space — built from frequency analysis, Fourier transforms, Markov transitions, orthogonality constraints, and cold-number heuristics — does not yield a defensible OOS edge in POWER_LOTTO.

R2 starts from feature engineering: building new signal representations from raw lottery history before selecting any strategy architecture. This is qualitatively different from P167's approach of combining existing strategy outputs.

**Pivoting to R2 does not mean edge has been found. It means a different research direction is being explored.**

---

## Canonical Research Dataset

| Field | Value |
|-------|-------|
| Dataset | zen-gates-ff6802 DB |
| DB path | `lottery_api/data/lottery_v2.db` |
| Total rows | 94,924 |
| POWER_LOTTO rows | 36,000 |
| Distinct draws | 1,499 |
| Designation | `P165B_ZEN_GATES_CANONICAL_RESEARCH_DATASET_DESIGNATED` |

---

## Feature Engineering Inventory — 10 Families

All features must be computable from pre-target draws only. Leakage prevention is mandatory.

### F01 — Recency Frequency Features

Exponentially decay-weighted number hit frequency. Window sizes: 20, 50, 100, 200 draws.

- **Signals**: `exp_decay_hit_rate`, `recency_weighted_rank`, `half_life_adjusted_frequency`
- **Leakage risk**: LOW — decay applied to draws strictly before `target_draw`
- **Distinct from existing**: MidFreq uses uniform window count. Decay weighting is a different transformation motivated by the non-stationarity confirmed in P170.

### F02 — Rolling Hot/Cold Features

Rolling percentile-based hot (>75th pct) / cold (<25th pct) / neutral designation per number. Hot-cold transition count as a feature.

- **Signals**: `rolling_hot_flag`, `rolling_cold_flag`, `hot_cold_transition_count`
- **Leakage risk**: LOW
- **Distinct from existing**: 冷號互補 uses raw absence count. This adds transition counting and percentile-based thresholds.

### F03 — Positional Frequency / Number-Position Interaction

Per-bet-position (slot) frequency of each number value. Number-slot correlation matrix. Slot-specific entropy.

- **Signals**: `slot_frequency_by_value`, `cross_slot_rank`, `slot_entropy`
- **Leakage risk**: MEDIUM — must aggregate by slot strictly before target_draw
- **Distinct from existing**: FreqOrt uses orthogonality constraint. This uses actual slot co-placement patterns.

### F04 — Pair/Triplet Co-occurrence Features

Number co-occurrence frequencies for pairs and triplets within the same draw. Graph-based degree centrality.

- **Signals**: `pair_cooccurrence_rate`, `triplet_frequency`, `number_centrality_score`
- **Data source**: Requires `lottery_draws` table (historical draw records)
- **Leakage risk**: LOW if using pre-target draws only
- **Distinct from existing**: None of the 10 existing strategies use co-occurrence graph structure.
- **Note**: Pair space C(38,2)=703 edges — Bonferroni correction mandatory.

### F05 — Gap/Overdue/Last-Seen Distance Features

Draws since last appearance (gap). Overdue z-score normalized against theoretical geometric distribution (mean gap = 38/6 ≈ 6.33 for POWER_LOTTO main).

- **Signals**: `draws_since_last_hit`, `overdue_z_score`, `expected_gap_ratio`
- **Leakage risk**: LOW — last-seen defined strictly before target_draw
- **Distinct from existing**: 冷號互補 uses raw count. This adds z-score normalization against geometric null — a statistically grounded overdue measure.

### F06 — Parity / Odd-Even Balance Features

Proportion of odd vs even numbers per draw. Parity streak length. Deviation from expected 0.5 balance.

- **Signals**: `odd_even_ratio`, `parity_streak`, `parity_deviation_z`
- **Leakage risk**: LOW
- **Distinct from existing**: None of the 10 existing strategies explicitly model parity balance. POWER_LOTTO 1–38 has exactly 19 odd / 19 even.

### F07 — High/Low/Zone Distribution Features

Partition 1–38 into low (1–13), mid (14–25), high (26–38) zones. Zone count distribution per draw. Zone imbalance score.

- **Signals**: `zone_count_low`, `zone_count_mid`, `zone_count_high`, `zone_entropy`, `zone_imbalance_score`
- **Leakage risk**: LOW — zone boundaries fixed
- **Distinct from existing**: Zonal Entropy measures entropy of prediction set. This adds zone-count features and cross-zone frequency modeling.

### F08 — Sum/Span/Variance/Dispersion Features

Draw sum, span (max-min), variance, mean absolute deviation. Rolling percentile of these statistics.

- **Signals**: `draw_sum`, `draw_span`, `draw_variance`, `draw_mad`, `sum_percentile`
- **Data source**: Requires `lottery_draws` table (historical draw records)
- **Leakage risk**: LOW if distribution parameters computed from pre-target history
- **Distinct from existing**: No existing strategy models draw-level dispersion.

### F09 — Modulo / Residue-Class Features

Numbers classified by mod-3, mod-5, mod-7 residue classes. Residue class frequency imbalance. Cross-mod interaction counts per draw.

- **Signals**: `mod3_distribution`, `mod5_distribution`, `mod7_distribution`, `mod_entropy`
- **Leakage risk**: LOW
- **Distinct from existing**: L84 showed ACB boundary/mod3 heuristic failed for BIG_LOTTO — but that was a hard inclusion rule. This is a pure distributional residue feature with a different mechanism.

### F10 — Trend-Shift / Regime-Window Features

CUSUM change-point detection on hit rates. Regime label (high/mid/low activity) per rolling window. Regime transition probability and stability score.

- **Signals**: `cusum_signal`, `regime_label`, `regime_stability_score`, `window_hit_rate_trend`
- **Leakage risk**: MEDIUM — CUSUM must be one-sided historical lookback only
- **Distinct from existing**: Existing Regime strategy uses retrospective labeling. CUSUM provides online, causal regime detection. P170 confirmed non-stationarity — adaptive detection is the principled response.

---

## Strategy Candidates — 8 Types

### C01 — Weighted Recency Frequency Strategy

**Hypothesis**: Numbers appearing more frequently in recent draws (exponential decay) have marginally higher probability of appearing in future draws.

| Field | Value |
|-------|-------|
| Required features | F01 |
| Output | Ranked number list; top-6 selected |
| Leakage risk | LOW |
| Overfitting risk | MEDIUM — decay rate must be pre-declared |
| Validation | Walk-forward OOS (min 200 draws); permutation test; Bonferroni |
| Min OOS draws | 200 |
| Distinct from old | MidFreq uses uniform window. Decay weighting is different transformation. |

### C02 — Gap-Adjusted Overdue Strategy

**Hypothesis**: Numbers absent longer than expected geometric inter-arrival time carry a measurable overdue signal.

| Field | Value |
|-------|-------|
| Required features | F05 |
| Output | Numbers ranked by overdue z-score; top-6 selected |
| Leakage risk | LOW |
| Overfitting risk | LOW — single threshold parameter |
| Validation | Walk-forward OOS (min 200 draws); compare vs 冷號互補; permutation test |
| Min OOS draws | 200 |
| Distinct from old | 冷號互補 uses raw count; this uses z-score normalization against geometric null. |

### C03 — Co-occurrence Pair Graph Strategy

**Hypothesis**: Certain number pairs co-occur more frequently than chance. Graph centrality identifies structurally non-random numbers.

| Field | Value |
|-------|-------|
| Required features | F04 |
| Output | Numbers ranked by co-occurrence centrality; top-6 selected |
| Leakage risk | LOW |
| Overfitting risk | HIGH — 703 edges; Bonferroni mandatory |
| Validation | Walk-forward OOS (min 300 draws); Bonferroni over pair count; permutation test |
| Min OOS draws | 300 |
| Distinct from old | No existing strategy uses co-occurrence graph structure. |

### C04 — Zone-Balanced Frequency Strategy

**Hypothesis**: Predictions constrained to match historical zone balance and ranked by zone-adjusted frequency outperform unconstrained selection.

| Field | Value |
|-------|-------|
| Required features | F07 |
| Output | Top-6 satisfying zone balance constraints |
| Leakage risk | LOW |
| Overfitting risk | MEDIUM — zone-count targets pre-declared from training |
| Validation | Walk-forward OOS (min 200 draws); compare vs unconstrained frequency; permutation test |
| Min OOS draws | 200 |
| Distinct from old | Zonal Entropy uses entropy of prediction. This uses zone-count constraint mechanism. |

### C05 — Entropy/Dispersion Controlled Strategy

**Hypothesis**: Predictions whose sum/span statistics match historical draw distribution avoid systematic biases and improve coverage.

| Field | Value |
|-------|-------|
| Required features | F08 |
| Output | Top-6 by dispersion-match composite score |
| Leakage risk | LOW |
| Overfitting risk | MEDIUM — dispersion targets pre-declared from training |
| Validation | Walk-forward OOS (min 200 draws); permutation test; compare vs C08 |
| Min OOS draws | 200 |
| Distinct from old | No existing strategy models draw-level dispersion (sum, span, MAD). |

### C06 — Regime-Adaptive Window Strategy

**Hypothesis**: P170 confirmed non-stationarity. A strategy that detects regime shifts via CUSUM and adapts its window to current regime outperforms fixed-window strategies.

| Field | Value |
|-------|-------|
| Required features | F10 |
| Output | Regime-adaptive frequency rank; top-6 |
| Leakage risk | MEDIUM — CUSUM must be causal/one-sided |
| Overfitting risk | HIGH — CUSUM threshold + window sizes must be pre-declared |
| Validation | Walk-forward OOS (min 300 draws); compare vs P161 best; compare vs P167 ensemble; permutation test |
| Min OOS draws | 300 |
| Distinct from old | Existing Regime uses retrospective labels. CUSUM is online, causal. |

### C07 — Hybrid Rank Aggregation Strategy

**Hypothesis**: Borda-count aggregation of independent feature rankings (recency, gap, zone, parity) is more robust than any single feature.

| Field | Value |
|-------|-------|
| Required features | F01, F05, F06, F07 |
| Output | Borda-count aggregated rank; top-6 |
| Leakage risk | LOW |
| Overfitting risk | HIGH — feature weights pre-declared; Bonferroni over weight grid |
| Validation | Walk-forward OOS (min 300 draws); compare vs each component; compare vs P167 ensemble; Bonferroni |
| Min OOS draws | 300 |
| Distinct from old | P167 combines strategy outputs (numbers). This aggregates raw feature rankings (inputs) — different fusion level. Features F01/F05/F06/F07 not extracted by existing strategies. |

### C08 — Constrained Random Baseline Challenger (Null Model)

**Hypothesis**: A random baseline constrained by zone balance (F07) and parity (F06) provides a tighter null model than unconstrained random.

| Field | Value |
|-------|-------|
| Required features | F06, F07 |
| Output | Random draw constrained to historical zone/parity distribution (comparison baseline only) |
| Leakage risk | LOW |
| Overfitting risk | NOT_APPLICABLE — null model only |
| Validation | Used as secondary comparison baseline. Not itself a predictive strategy. |
| Min OOS draws | Same as primary strategy being compared |
| Distinct from old | R1 used unconstrained random (36/38). This provides a tighter null accounting for structural constraints. |

---

## P172 Prototype Boundary

| Allowed | Forbidden |
|---------|-----------|
| Plan-only or minimal feature extraction prototype | Registry mutation |
| Read-only DB queries | Replay row insertion |
| Pre-declared strategy configs in plan artifacts | Champion promotion |
| OOS evaluation scripts (no DB write) | controlled_apply |
| | Deployment to production |
| | Betting advice |
| | DB write of any kind |

**P172 is BLOCKED until user provides explicit authorization.**

---

## R2 Validation Protocol

1. **Time-ordered train/test split** — strictly by `target_draw`. No shuffling. Test set never seen during hyperparameter selection.
2. **Walk-forward OOS evaluation** — expanding window starting with min 500 training draws; 50-draw evaluation blocks; no OOS refitting.
3. **Pre-declared strategy configs** — all hyperparameters declared in P172 plan artifact before any OOS evaluation. Treated as pre-registration.
4. **Random baseline comparison** — primary: 36/38 fair-random (P161 confirmed). Secondary: constrained random (C08).
5. **P161 best strategy comparison** — must outperform `midfreq_fourier_mk_3bet` (hit rate 0.9674) in OOS only.
6. **P167 ensemble comparison** — must show consistent OOS superiority where P167 showed no consistent edge.
7. **Multiple testing correction** — Bonferroni over candidate strategies × hyperparameter configurations. BH as secondary. Report both corrected and uncorrected p-values.
8. **Honest NULL reporting** — if no candidate beats corrected threshold: report NULL. No uncorrected p-value claims. No retroactive reframing. R2 NULL is acceptable.

---

## Governance Confirmations

| Governance Item | Status |
|----------------|--------|
| DB rows before | 94,924 |
| DB rows after | 94,924 |
| DB unchanged | YES |
| No DB write | YES |
| No registry mutation | YES |
| No strategy implementation | YES |
| No controlled_apply | YES |
| No champion promotion | YES |
| No betting advice | YES |
| No win-guarantee claim | YES |
| No stage/commit/push | YES |
| No checkout branch | YES |
| No merge/rebase/reset | YES |
| R2 no edge found yet | YES |
| P161-P170 NULL results unchanged | YES |
| main/zen-gates split still unresolved | YES |

---

## Next Task

**`P172_POWER_LOTTO_NEW_STRATEGY_PROTOTYPE_PLAN_ONLY`**

**BLOCKED — requires explicit user authorization before proceeding.**

Authorization phrase required: `YES start P172 POWER_LOTTO new strategy prototype plan`

P172 scope: plan-only or minimal prototype implementation of feature extraction. Read-only DB. No registry mutation. No replay row insertion. No champion. No deployment. No betting advice.

---

*P171 is a pivot to new strategy discovery. It does not represent a finding that a success-rate improvement method has been identified. R2 research has just started. No edge has been found. All lottery games remain deeply negative EV (L87, L99). Ruin probability at sustained real-money play is 1.000.*
