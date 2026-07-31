# P166 — POWER_LOTTO Ensemble / Voting Research Plan

**Task**: P166_POWER_LOTTO_ENSEMBLE_VOTING_RESEARCH_PLAN_ONLY  
**Date**: 2026-06-01  
**Final Classification**: `P166_POWER_LOTTO_ENSEMBLE_VOTING_RESEARCH_PLAN_READY`  
**Status**: PLAN ONLY — no implementation executed

---

## Phase 0 Verification — ALL PASS

| Check | Result |
|---|---|
| Worktree | `/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802` ✓ |
| Branch | `claude/zen-gates-ff6802` ✓ |
| DB rows | 94,924 ✓ |
| Drift guard | PASS ✓ |
| P161–P165B tests | PASS (173/173) ✓ |
| P161 artifact | Present ✓ |
| P165B artifact | Present ✓ |

---

## Canonical Research Dataset

All P166/P167 research must use zen-gates canonical dataset (designated in P165B):

| Field | Value |
|---|---|
| DB total rows | 94,924 |
| POWER_LOTTO rows | 36,104 |
| Distinct draws | 1,551 |
| bet_index | PRESENT |
| main stale rows | 54,462 (DO NOT USE for research) |

---

## P161 Baseline Summary — NULL Result

P161 evaluated 10 POWER_LOTTO strategies across 1,551 draws.

| Metric | Value |
|---|---|
| Main random baseline | 0.9474 (6 × 6/38) |
| Special random baseline | 0.125 (1/8) |
| Family size (correction) | 40 tests |
| Strategies above random (raw) | 7 of 10 |
| Strategies surviving Bonferroni | **0** |
| Strategies surviving BH | **0** |
| Best raw p-value | 0.0076 (midfreq_fourier_mk_3bet) — p_bonferroni = 0.304, NOT significant |
| Best strategy mean | 0.9749 (fourier_rhythm_3bet, 3-bet, per-draw) |

**NULL result confirmed.** No success-rate improvement method has been identified. P166 searches for ensemble/voting approaches that may reveal signal not visible in single-strategy per-draw evaluation. A NULL result from P167 remains possible and must be reported honestly.

---

## Research Goal

Search for statistically defensible success-rate improvement by combining signals from multiple POWER_LOTTO strategies via ensemble voting, slot-weighting, and walk-forward OOS validation.

**P166 defines the protocol only. Implementation and execution begin in P167 after explicit user authorization.**

---

## Leakage-Safe Protocol

All P167 implementation must follow these rules:

| Rule | Requirement |
|---|---|
| Training/test split | No draw used in both training and test; test window starts strictly after training cutoff |
| Walk-forward | Expanding or rolling window; minimum OOS window = **500 draws** for predictive claims |
| Configuration freeze | All ensemble configurations, weights, and thresholds declared **before** any test data is examined |
| Statistical unit | **Per distinct draw** (not per bet row). Multi-bet slots must aggregate to draw level before significance testing. |
| Multiple testing | Bonferroni + BH on pre-declared family size; family size declared before execution |
| Baseline | Beat (1) random 0.9474, (2) best single-strategy 0.9749, (3) permutation null |
| Prohibited | Selecting best config after seeing OOS results; reporting raw p as significant; mixing train/test draws |

---

## Research Modules

### Module A — Strategy Consensus Voting

| Field | Detail |
|---|---|
| **Research question** | Does majority/weighted-vote ensemble produce higher per-draw hit rates than single strategy or random baseline after correction? |
| **Input data** | P161 per-draw hit counts for all 10 strategies (36,104 rows, 1,551 draws) |
| **Metric** | Per-draw ensemble hit count; consensus vote rate; OOS mean hit count |
| **Baseline** | Random 0.9474; best single strategy 0.9749; permutation null |
| **Leakage risk** | MEDIUM — vote threshold and weights must be frozen before test window |
| **Statistical guard** | Bonferroni on all vote-threshold variants; walk-forward OOS ≥ 500 draws; 1000-shuffle permutation test |
| **Pass criterion** | p_bh < 0.05 AND OOS mean > 0.9749 AND survives permutation test |
| **Type** | Predictive |

---

### Module B — bet_index Slot Effectiveness and Weighting

| Field | Detail |
|---|---|
| **Research question** | Do higher bet_index slots produce systematically different hit rates? Does slot-weighting improve ensemble accuracy? |
| **Input data** | Multi-bet strategies only (e.g., fourier_rhythm_3bet n_bet_slots=3); per-slot aggregated to draw level |
| **Metric** | Per-slot mean hit count (per draw); slot lift over bet_index=1; slot contribution to ensemble vote |
| **Baseline** | Random 0.9474; P161 per-draw strategy mean |
| **Leakage risk** | LOW (descriptive slot comparison); MEDIUM (predictive slot weighting — freeze on training) |
| **Statistical guard** | CI overlap for descriptive; Bonferroni on slot comparisons; frozen weights for predictive |
| **Pass criterion** | Slot i useful if mean hit count > bet_index=1 by ≥ 1 SEM AND stable across rolling windows |
| **Type** | Descriptive + Predictive |
| **Note** | Strategies with n_bet_slots=1 (pseudo-replicated rows) excluded from slot analysis |

---

### Module C — Recent-Window vs Full-History Comparison

| Field | Detail |
|---|---|
| **Research question** | Does ensemble performance in recent 100/300/500 draws differ from full-history? Is there non-stationarity favoring recent-window training? |
| **Input data** | All 36,104 POWER_LOTTO rows; split into recent (last 500) vs historical |
| **Metric** | Per-draw hit count in recent vs historical; slope of hit rate over time; rolling mean stability |
| **Baseline** | Random 0.9474; full-history mean; random-drift null (shuffle draw order 1000×) |
| **Leakage risk** | LOW (descriptive trend); MEDIUM (predictive window selection — freeze size on training) |
| **Statistical guard** | t-test / Mann-Whitney recent vs historical; Ljung-Box autocorrelation test; min 100 draws per window |
| **Pass criterion** | Recent window preferred if: recent hit rate > full-history AND p_bh < 0.05 AND stable across 3+ non-overlapping recent windows |
| **Type** | Descriptive + Predictive |

---

### Module D — Lifecycle-Aware Descriptive Grouping

| Field | Detail |
|---|---|
| **Research question** | Do strategies with different lifecycle labels (ONLINE, RETIRED) show different hit-rate distributions? |
| **Input data** | P161 per-strategy results with lifecycle labels from P156C registry (10 strategies) |
| **Metric** | Mean hit count by lifecycle group; distribution overlap (KL divergence / overlap coefficient) |
| **Baseline** | Random 0.9474; null = lifecycle group does not predict hit rate |
| **Leakage risk** | **HIGH** — survivorship bias. Lifecycle labels were assigned after observing historical performance. ONLINE label is not an independent predictor. |
| **Statistical guard** | **Descriptive only.** Report with explicit survivorship-bias caveat. Do NOT use lifecycle as a predictive feature without OOS-only evaluation after label assignment. |
| **Pass criterion** | Descriptive — PASS if group statistics computed with caveat clearly documented. No predictive pass/fail. |
| **Type** | **Descriptive only** |
| **⚠ Critical caveat** | ONLINE/RETIRED split is potentially confounded by selection bias. Any performance difference may reflect selection, not predictive signal. |

---

### Module E — Main-Number vs Special-Number Separated Evaluation

| Field | Detail |
|---|---|
| **Research question** | Can an ensemble improve main-number or special-number hit rates independently? Is special-number prediction systematically below random? |
| **Input data** | P161 main hit counts (6 of 38 pool) and special hit counts (1 of 8 pool); per-draw separated |
| **Metric** | Main: per-draw mean hit count (baseline 0.9474); Special: per-draw hit rate (baseline 0.125) |
| **Baseline** | Main random 0.9474; Special random 0.125; P161: special below random for all 9 strategies tested |
| **Leakage risk** | LOW (descriptive separation); MEDIUM (ensemble targeting specific numbers) |
| **Statistical guard** | Separate Bonferroni family for main and special; min OOS 500 draws for special (high variance); report NULL if no improvement |
| **Pass criterion** | Main: ensemble OOS mean > 0.9749 AND p_bh < 0.05. Special: ensemble OOS rate > 0.125 AND p_binom_bh < 0.05 (≥ 500 draws). |
| **Type** | Descriptive + Predictive |
| **P161 finding** | All 9 strategies with special predictions were BELOW random 0.125. Special number prediction may be near-random or negatively predictive for current strategies. |

---

### Module F — Walk-Forward OOS Validation and Multiple-Testing Correction

| Field | Detail |
|---|---|
| **Research question** | Across all modules A–E, which configurations survive strict walk-forward OOS with pre-declared family-size multiple-testing correction? |
| **Input data** | All 36,104 POWER_LOTTO rows; training cutoff declared before execution; OOS window ≥ 500 draws |
| **Metric** | Final OOS per-draw mean hit count vs random; BH-adjusted p across all configurations; permutation test; walk-forward stability across ≥ 3 non-overlapping OOS windows |
| **Baseline** | Random 0.9474; best P161 single strategy 0.9749; 1000-shuffle permutation null |
| **Leakage risk** | **HIGH** if configurations selected after seeing OOS. **All configurations must be pre-declared before any OOS data is examined.** |
| **Statistical guard** | Pre-registration of all configurations; family size = number of pre-declared configs; Bonferroni threshold = 0.05 / family_size; BH procedure; 1000-shuffle permutation; ≥ 3 non-overlapping 500-draw OOS windows |
| **Pass criterion** | ≥ 1 configuration achieves: p_bh < 0.05 AND p_permutation < 0.05 AND OOS mean > 0.9749 AND stable across 3 walk-forward windows. If none: **report NULL.** |
| **Type** | **Predictive — final gate** |
| **⚠ Critical note** | This is the **final gate**. In-sample results from Modules A–E do NOT constitute evidence of predictive value. Only configurations that survive Module F may be considered for P167 deployment or further evaluation. |

---

## P167 Implementation Boundary

### Allowed in P167 (after explicit user authorization)

- Implement the 6 modules above using zen-gates canonical dataset
- Produce per-module descriptive statistics and OOS test results
- Run walk-forward OOS validation (Module F) as final gate
- Report NULL honestly if no configuration survives Module F
- Produce P167 artifact with per-module results and final classification

### Forbidden in P167 without separate authorization

- DB writes (new rows, schema changes)
- Registry or lifecycle label modifications
- Champion promotion
- Controlled_apply
- Win-promise claims or real-money guidance of any kind
- Claiming success-rate improvement without Module F OOS evidence
- Modifying main branch DB or code

### P167 Success Criteria

1. Must beat random baseline (0.9474) in OOS evaluation
2. Must beat best single-strategy baseline (fourier_rhythm_3bet 0.9749) in OOS
3. Must survive Bonferroni or BH correction on pre-declared family size
4. Must use distinct target_draw as statistical unit (not bet rows as N)
5. Must separate in-sample descriptive results from OOS predictive results
6. Must report NULL honestly if no edge found after Module F

### P167 Failure Criteria

- No configuration beats random baseline OOS → P167 result = NULL, no deployment
- p_bh ≥ 0.05 for all configurations → NULL
- Walk-forward windows inconsistent (any window negative) → UNSTABLE flag
- OOS < 500 draws available → INSUFFICIENT_OOS_DATA, no significance claim

---

## No-Action Confirmations

P166 performed:
- **Zero DB writes** — DB unchanged at 94,924 rows
- **Zero strategy implementations** — no ensemble algorithm executed
- **Zero new strategy results produced** — plan document only
- **Zero registry mutations** — no lifecycle labels changed
- **Zero commits or pushes** — artifact is untracked output only
- **Zero champion promotions** — P147 still blocked
- **Zero scheduler/cron installations**
- **No wager tips, no win guarantees, no real-money guidance**

---

## Next Task — BLOCKED WAITING FOR USER AUTHORIZATION

**P167_POWER_LOTTO_ENSEMBLE_VOTING_RESEARCH_IMPLEMENTATION**

P166 defines the research plan. P167 may not begin without explicit user authorization. No autonomous execution of any research module.

Current state of success-rate search: **NULL — no method found yet.** P167 will attempt to find ensemble signal; a NULL result from P167 remains possible and must be reported honestly.

---

## Governance Invariants

| Invariant | Value |
|---|---|
| DB rows | 94,924 (must not change) |
| Drift guard | PASS |
| main/zen-gates split | **UNRESOLVED** |
| Predictive edge identified | **NO** — NULL result still current |
| Implementation status | **NOT STARTED** — plan only |
