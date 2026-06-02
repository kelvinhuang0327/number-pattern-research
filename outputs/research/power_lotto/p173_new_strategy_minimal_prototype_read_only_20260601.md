# P173 — POWER_LOTTO New Strategy Minimal Prototype — Read-Only

**Task**: `P173_POWER_LOTTO_NEW_STRATEGY_MINIMAL_PROTOTYPE_READ_ONLY`
**Final Classification**: `P173_POWER_LOTTO_R2_MINIMAL_PROTOTYPE_NULL_RESULT`
**Date**: 2026-06-01
**Branch**: `claude/zen-gates-ff6802`
**Authorization Phrase**: `YES start P173 POWER_LOTTO minimal prototype read-only`

---

## Phase 0 Verification — PASS

| Check | Actual | Status |
|-------|--------|--------|
| Repo | `/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802` | PASS |
| Branch | `claude/zen-gates-ff6802` | PASS |
| DB rows | `94924` | PASS |
| POWER_LOTTO draws | `1913` | PASS |
| Drift guard | PASS | PASS |
| P167 script | PASS | PASS |
| P170 script | PASS | PASS |
| P161–P172 tests | 673 PASSED | PASS |
| P172 classification | `P172_POWER_LOTTO_NEW_STRATEGY_PROTOTYPE_PLAN_READY` | PASS |

---

## P172 Summary

Top 3 selected: C01 (weighted recency freq), C02 (gap-adjusted overdue), C04 (zone-balanced freq). All use `draws` table (1,913 actual POWER_LOTTO records). No external data needed. P172 pre-declared all configs before OOS evaluation.

**P173 does NOT represent a finding of edge. R2 research is ongoing — this is the prototype evaluation step.**

---

## OOS Protocol

| Parameter | Value |
|-----------|-------|
| Initial training draws | 500 (chronological, used for C04 zone targets only) |
| OOS draws evaluated | 1,413 (draws 501–1913) |
| Evaluation method | Expanding window, one draw at a time |
| No shuffling | YES |
| No OOS refitting | YES |

For each OOS draw at index `i`:
- Features computed from draws `0..i-1` ONLY (no leakage)
- Predict top-6 numbers
- Count hits against actual draw numbers from `draws` table

---

## Pre-Declared Candidate Configs (frozen from P172)

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
| C04 | `zone_targets_computed` | low=2, mid=2, high=2 (sum=6) |
| C04 | `top_k` | 6 |

---

## OOS Results

### Statistical Method

- **Test**: one-sided z-test (H0: mean hit count = 36/38, H1: mean > 36/38)
- **Variance per draw**: Hypergeometric(N=38, K=6, n=6) → Var = 6×6×32×32/(38²×37) ≈ 0.690
- **SE_mean**: √(0.690/1413) ≈ 0.0221
- **Family size**: 3 → Bonferroni threshold = 0.05/3 = **0.01667**

### Per-Candidate Results

| Candidate | Mean Hit Count | vs Baseline (0.9474) | z-score | p_raw | p_bonferroni | p_bh | Status |
|-----------|---------------|----------------------|---------|-------|-------------|------|--------|
| C01 weighted recency freq | **0.9611** | +0.0137 | 0.619 | 0.268 | 0.803 | 0.803 | **FAIL_CORRECTED** |
| C02 gap-adjusted overdue | **0.9632** | +0.0158 | 0.715 | 0.237 | 0.711 | 0.711 | **FAIL_CORRECTED** |
| C04 zone-balanced freq | **0.9639** | +0.0165 | 0.748 | 0.227 | 0.681 | 0.681 | **FAIL_CORRECTED** |

### Baseline Comparisons

| Baseline | Value |
|----------|-------|
| B1: Fair random 36/38 | 0.9474 |
| B3: P161 best strategy pool mean | 0.9674 |
| C08 constrained random | C08_NOT_IMPLEMENTED — expected same E[hit]=36/38 as unconstrained random |

All three candidates show slightly above-random mean hit counts (0.961–0.964 vs 0.947), but **none approaches statistical significance** after Bonferroni correction. The highest z-score is 0.748 (C04), requiring z > 2.394 to pass the corrected threshold.

---

## NULL Result Statement

**No candidate achieved p_bonferroni < 0.016667.**

C01, C02, and C04 are statistically indistinguishable from fair-random 36/38 selection after Bonferroni correction. The small positive deltas (+0.014 to +0.017) are consistent with random sampling variation.

**This is the expected outcome consistent with R1 findings (P161–P170) and with L91/L90 (BIG_LOTTO signal boundary).**

P173 NULL result does NOT mean the experiment was invalid — it means these three feature types do not yield a detectable OOS edge under the pre-declared configuration with n=1,413 draws.

**P161–P172 NULL/no-edge conclusions stand unchanged.**

---

## Governance Confirmations

| Item | Status |
|------|--------|
| DB rows before/after | 94,924 / 94,924 |
| DB write | 0 |
| Registry mutation | 0 |
| Strategy implementation in registry | None |
| controlled_apply | Not executed |
| Champion promotion | Not executed |
| Wagering recommendations | None |
| No win-guarantee claim | Confirmed |
| No stage/commit/push | Confirmed |
| R2 no edge found yet | Confirmed |
| P161–P172 NULL results | Stand unchanged |
| main/zen-gates split | Still unresolved |

---

## Next Task

**`P174_POWER_LOTTO_R2_DECISION_REVIEW`**

**BLOCKED — requires explicit user authorization.**

Authorization phrase: `YES start P174 POWER_LOTTO R2 decision review`

P174 scope: decision review of P173 NULL result and R2 roadmap. Options include: halt R2 (null confirmed), try deferred candidates (C03/C06 with higher complexity), wait for new data (POWER_LOTTO draws > 115000041), or redirect research. Decision requires user authorization.

---

*P173 is a read-only research prototype. The NULL result is honest and does not represent a failure of process — it represents a genuine scientific finding that C01/C02/C04 feature-based strategies do not outperform random selection in POWER_LOTTO under the pre-declared OOS protocol. No wagering recommendations are given. No win outcome is guaranteed. All lottery games remain deeply negative EV.*
