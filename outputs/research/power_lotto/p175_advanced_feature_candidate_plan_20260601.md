# P175 — POWER_LOTTO R2 Advanced Feature Candidate Plan (Plan-Only)

**Task**: `P175_POWER_LOTTO_R2_ADVANCED_FEATURE_CANDIDATE_PLAN_ONLY`
**Final Classification**: `P175_POWER_LOTTO_R2_ADVANCED_FEATURE_CANDIDATE_PLAN_READY`
**Date**: 2026-06-01
**Branch**: `claude/zen-gates-ff6802`
**Authorization Phrase**: `YES start P175 POWER_LOTTO R2 advanced feature candidate plan`

---

## Phase 0 Verification — PASS

| Check | Actual | Status |
|-------|--------|--------|
| Repo | `zen-gates-ff6802` | PASS |
| Branch | `claude/zen-gates-ff6802` | PASS |
| DB rows | `94924` | PASS |
| POWER_LOTTO draws | `1913` | PASS |
| Drift guard | PASS | PASS |
| P173 script | PASS | PASS |
| P161–P174 tests | 822 PASSED | PASS |
| P174 classification | `P174_POWER_LOTTO_R2_DECISION_REVIEW_READY` | PASS |

---

## Honest Preface

**P175 is a plan-only document. It does NOT represent a finding that advanced feature candidates will yield edge.**

The prior probability of finding corrected-significant OOS edge in POWER_LOTTO remains LOW given:
- R1 NULL: 10 existing strategies, P161–P170, zero pass after Bonferroni/BH
- R2 Top 3 NULL: C01/C02/C04, P173, all FAIL_CORRECTED (p_bonf: 0.803/0.711/0.681)
- POWER_LOTTO pool structure consistent with fair random (1913-draw history)

P175 designs the plan for C03/C05/C06/C07 to fulfill the user's exhaustive-search goal. No prototype is implemented here.

---

## P174 Summary

| Item | Value |
|------|-------|
| P174 classification | `P174_POWER_LOTTO_R2_DECISION_REVIEW_READY` |
| Recommended option | B — plan-only for C03/C05/C06/C07 |
| P173 NULL | Unchanged |
| P161–P174 NULL/no-edge | Unchanged |
| No edge found as of P174 | Confirmed |

---

## Candidate Plan — 4 Advanced Candidates

### C03 — Co-occurrence Pair Graph Strategy

**Feature family**: F04 (pair/triplet co-occurrence features)

**Description**: Number co-occurrence frequencies for pairs within the same actual draw. Degree centrality from pair co-occurrence adjacency matrix. Numbers ranked by centrality; top-6 selected.

| Field | Value |
|-------|-------|
| Pair space | C(38,2) = **703 edges** |
| Overfitting risk | **HIGH** |
| Leakage risk | LOW |
| Min OOS draws | **300** |

**Causal extraction rule**: For draw index `i`, rebuild pair adjacency matrix from draws[0..i-1] ONLY. No lookahead.

**Frozen config** (must not change before P176 OOS):
- Centrality metric: degree centrality (sum of pair co-occurrence weights)
- Min pair co-occurrence threshold: 2
- Lookback: all prior draws (full history)
- top_k = 6

**Critical warning — internal pair-space burden**: Bonferroni over family=4 (threshold=0.0125) does NOT account for the 703-edge internal selection. Degree-centrality implicitly tests which nodes are most central across 703 possible pairs. **Effective Type I error rate for C03 may be higher than 0.0125.** This must be explicitly documented in P176 report.

**Failure condition**: p_bonferroni ≥ 0.0125  
**NULL reporting rule**: If FAIL_CORRECTED, do not narrow pair threshold post-hoc. Do not interpret uncorrected p-values as positive signals.

---

### C05 — Entropy/Dispersion Controlled Strategy

**Feature family**: F08 (sum/span/variance/dispersion features)

**Description**: Predictions scored by how closely their sum/span/MAD match the historical POWER_LOTTO draw distribution. Top-6 by composite dispersion-match score.

| Field | Value |
|-------|-------|
| Overfitting risk | **MEDIUM** |
| Leakage risk | LOW |
| Min OOS draws | **200** |

**Causal extraction rule**: Distribution parameters (sum/span/MAD mean and std) computed from draws[0..i-1]. Expanding window — parameters update with each new draw.

**Frozen config**:
- Dispersion metrics: draw_sum, draw_span, draw_mad
- Scoring: negative L2 distance from training distribution mean
- top_k = 6

**Failure condition**: p_bonferroni ≥ 0.0125  
**NULL reporting rule**: If FAIL_CORRECTED, do not re-score using a different dispersion metric post-hoc.

---

### C06 — Regime-Adaptive Window Strategy (CUSUM)

**Feature family**: F10 (trend-shift/regime-window features)

**Description**: CUSUM change-point detection assigns a regime label (high/neutral/low activity) based on hit-rate history up to the target draw. Frequency window size adapts to the current regime. Motivated by P170's confirmation of non-stationarity.

| Field | Value |
|-------|-------|
| Overfitting risk | **HIGH** |
| Leakage risk | **MEDIUM** |
| Min OOS draws | **300** |

**Causal extraction rule**: CUSUM runs ONE-SIDED on draws[0..i-1] sequentially. Regime label at position i is determined ONLY from prior draws. **No two-sided CUSUM. No future-aware smoothing. No retrospective regime labels.**

**Frozen config**:
- CUSUM threshold: 2.0
- CUSUM slack: 0.5
- Regime window sizes: high-activity=50, neutral=100, low-activity=200
- top_k = 6

**P170 connection**: P170 confirmed non-stationarity (Window 2 below random at all thresholds). This MOTIVATES the regime-adaptive approach but does NOT constitute evidence it will generalize. Non-stationarity itself may be non-stationary.

**STRICT leakage rule**: Regime label for draw i may ONLY reference draws 0..i-1. Any implementation using smoothed signals including draw i is a leakage violation.

**Failure condition**: p_bonferroni ≥ 0.0125  
**NULL reporting rule**: If FAIL_CORRECTED, do not re-tune CUSUM parameters post-hoc.

---

### C07 — Hybrid Rank Aggregation Strategy

**Feature family**: F01+F05+F07+F04 (C01+C02+C04+C03 components)

**Description**: Borda-count rank aggregation of 4 independent feature rankings: recency-weighted frequency (C01), gap-adjusted overdue (C02), zone-adjusted frequency (C04), co-occurrence centrality (C03). Top-6 by combined Borda score.

| Field | Value |
|-------|-------|
| Overfitting risk | **HIGH** |
| Leakage risk | LOW |
| Min OOS draws | **300** |

**Causal extraction rule**: Each component ranking (C01/C02/C04/C03) computed independently from draws[0..i-1]. Borda aggregation is a deterministic function of 4 input rankings.

**Frozen config**:
- Component weights: equal (each contributes equally to Borda count)
- Tie-breaking: alphabetical by candidate_id (C01>C02>C04>C03)
- top_k = 6

**Dependency warning**: C01/C02/C04 were evaluated in P173 and ALL FAIL_CORRECTED individually. Borda aggregation of individually-null signals has low prior probability of yielding a non-null composite. This does not prevent evaluation but must be stated.

**Failure condition**: p_bonferroni ≥ 0.0125  
**NULL reporting rule**: If FAIL_CORRECTED, do not interpret aggregation as improving on components post-hoc.

---

## Multiple-Testing Plan

| Parameter | Value |
|-----------|-------|
| Family size | **4** (one per candidate: C03/C05/C06/C07) |
| α | 0.05 |
| **Bonferroni threshold** | **0.0125** (= 0.05/4) |
| Secondary | BH (Benjamini-Hochberg) |
| Report both | Corrected AND uncorrected p-values |

**C03 internal burden**: C(38,2)=703 edges. Bonferroni over family=4 does NOT correct for pair-space selection. P176 must document this.

**Pre-declaration requirement**: All configs listed above are frozen as of P175. No changes permitted after P176 OOS begins.

**Null ruling**: If 0/4 candidates pass — overall R2 advanced-feature NULL reported.

---

## OOS Protocol Plan

| Parameter | Value |
|-----------|-------|
| Data source | `draws` table, `lottery_type='POWER_LOTTO'`, ordered by `CAST(draw AS INTEGER) ASC` |
| Available rows | 1,913 |
| Read-only | YES |
| Initial training size | 500 |
| Evaluation method | Expanding window |
| No shuffling | YES |
| No OOS refitting | YES |
| Statistical unit | Per draw (distinct POWER_LOTTO draw, NOT per bet-row) |

**Anti-pseudo-replication rule**: Hit count assessed once per draw per candidate prediction. Evaluating multiple bet-row hits per draw inflates effective sample size and is prohibited.

**Hypothesis test**: One-sided z-test (H0: mean=36/38, H1: mean>36/38) using hypergeometric variance (N=38, K=6, n=6).

**Min OOS draws**: C03=300, C05=200, C06=300, C07=300.

---

## Leakage Prevention Plan

| Candidate | Prevention Rule |
|-----------|----------------|
| C03 | Pair adjacency matrix rebuilt from draws[0..i-1] per target draw |
| C05 | Distribution parameters from draws[0..i-1], expanding window |
| C06 | CUSUM run sequentially on draws[0..i-1]; one-sided only |
| C07 | All 4 component rankings from draws[0..i-1] independently |

Verification method: P176 script must include per-candidate leakage audit comment documenting which draws are used in feature extraction.

---

## Risk Assessment

| Candidate | Overfitting Risk | Leakage Risk | Min OOS | Key Risk |
|-----------|-----------------|--------------|---------|----------|
| C03 | HIGH | LOW | 300 | 703-pair selection; graph fits noise |
| C05 | MEDIUM | LOW | 200 | Distribution drift under non-stationarity |
| C06 | HIGH | MEDIUM | 300 | 5 CUSUM params; causal implementation critical |
| C07 | HIGH | LOW | 300 | Components individually null in P173 |

**Cumulative testing burden**: P161–P175 represents an extensive multiple-testing sequence. The probability of at least one false positive increases with each additional family. This must be acknowledged in P176 reporting.

**If all P176 null**: R2 research should be concluded. No further feature engineering without structural change (new data, new theory, different lottery type with documented anomalies).

---

## P176 Scope Boundary

**Task**: `P176_POWER_LOTTO_R2_ADVANCED_FEATURE_MINIMAL_PROTOTYPE_READ_ONLY`

| Allowed | Forbidden |
|---------|-----------|
| Read-only SQL (`draws`, `strategy_prediction_replays`) | DB write |
| Analysis scripts in `analysis/power_lotto/` | Registry mutation |
| OOS evaluation using P175 pre-declared configs | Replay row insertion |
| Output artifacts in `outputs/research/power_lotto/` | Champion promotion |
| Contract test in `tests/` | controlled_apply |
| | Deployment to production |
| | Wagering recommendations |
| | Win-guarantee claims |
| | Strategy code in `lottery_api/` or `tools/` |
| | Config changes after OOS begins |
| | Retroactive threshold adjustment |

**P176 BLOCKED until user provides authorization phrase**: `YES start P176 POWER_LOTTO R2 advanced feature minimal prototype read-only`

---

## Governance Confirmations

| Item | Status |
|------|--------|
| DB rows before/after | 94,924 / 94,924 |
| DB write | 0 |
| Registry mutation | 0 |
| Prototype script in P175 | None (plan-only) |
| Strategy implementation | None |
| controlled_apply | Not executed |
| Champion promotion | Not executed |
| Wagering recommendations | None |
| No win-guarantee claim | Confirmed |
| No stage/commit/push | Confirmed |
| P173 NULL | Unchanged |
| P161–P174 NULL results | All unchanged |
| main/zen-gates split | Still unresolved |

---

## Next Task

**`P176_POWER_LOTTO_R2_ADVANCED_FEATURE_MINIMAL_PROTOTYPE_READ_ONLY`**

**BLOCKED — requires explicit user authorization.**

Authorization phrase: `YES start P176 POWER_LOTTO R2 advanced feature minimal prototype read-only`

P176 scope: read-only minimal prototype for C03/C05/C06/C07 using P175 pre-declared configs only. No DB write, no registry mutation, no deployment. If all 4 candidates FAIL_CORRECTED: R2 research concluded.

---

*P175 is a plan-only document. No prototype was implemented. No OOS evaluation was performed. No edge has been found. P173 NULL and all P161–P174 conclusions stand unchanged. All lottery games remain deeply negative EV. No wagering recommendations are given.*
