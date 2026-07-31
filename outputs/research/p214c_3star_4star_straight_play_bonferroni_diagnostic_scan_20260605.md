# P214C — 3_STAR / 4_STAR Straight-Play Bonferroni-Corrected Diagnostic Scan

**Date:** 2026-06-05
**Task ID:** P214C
**Classification:** `P214C_3STAR_4STAR_STRAIGHT_PLAY_BONFERRONI_DIAGNOSTIC_SCAN_COMPLETE`
**Task Type:** Type C — Read-only Diagnostic Scan
**Production DB Write:** false
**Ingestion Performed:** false
**Replay Generation Performed:** false
**Strategy Scan Performed:** false
**Generated at:** 2026-06-05 16:08

---

## 1. Scope and Non-Goals

### In Scope
- Per-position digit uniformity chi-squared tests (Bonferroni-corrected)
- Walk-forward OOS check for any uncorrected-significant result (descriptive)
- Honest null-friendly classification

### Non-Goals
- No 4_STAR exact ordered significance test (INOPERABLE power)
- No strategy promotion or registry change
- No DB write, ingestion, or replay generation
- No betting advice or number suggestions
- No claim of predictive edge

---

## 2. Phase 0 Summary — All PASS

| Check | Value |
|---|---|
| repo | /Users/kelvin/Kelvin-WorkSpace/LotteryNew |
| branch | main / dev branch |
| DB integrity | ok |
| replay rows | 94,924 |
| draw rows | 64,361 |
| 3_STAR rows | 5,850 |
| 4_STAR rows | 5,850 |
| star replay rows | 0 |
| drift guard | REPLAY_LIFECYCLE_DRIFT_GUARD_PASS |

---

## 3. P214 / P214B Protocol Recap

| Lottery | Exact baseline | Exact power | Per-pos baseline | Per-pos power |
|---|---|---|---|---|
| 3_STAR | 1/1000 | MARGINAL (not tested) | 1/10 | TRACTABLE |
| 4_STAR | 1/10000 | INOPERABLE (excluded) | 1/10 | TRACTABLE |

P227C box-play prior: UNDERPOWERED_NO_SIGNAL (both types). Straight-play is harder.

---

## 4. Pre-Registered Tests and Family Size

**Family size (pre-declared):** 7

| # | Test | Lottery | Position | df |
|---|---|---|---|---|
| 1 | Chi-squared digit uniformity | 3_STAR | pos_0 | 9 |
| 2 | Chi-squared digit uniformity | 3_STAR | pos_1 | 9 |
| 3 | Chi-squared digit uniformity | 3_STAR | pos_2 | 9 |
| 4 | Chi-squared digit uniformity | 4_STAR | pos_0 | 9 |
| 5 | Chi-squared digit uniformity | 4_STAR | pos_1 | 9 |
| 6 | Chi-squared digit uniformity | 4_STAR | pos_2 | 9 |
| 7 | Chi-squared digit uniformity | 4_STAR | pos_3 | 9 |

**4_STAR exact ordered match:** excluded (INOPERABLE).
**3_STAR exact ordered match:** MARGINAL power; no prediction model available; not tested.

---

## 5. Bonferroni Correction Policy

| Parameter | Value |
|---|---|
| ALPHA | 0.05 |
| Family size | 7 |
| Bonferroni alpha | 0.05/7 = 0.007143 |
| Chi-squared df | 9 |
| Total tests run | 7 |
| Bonferroni-significant tests | 0 |
| Uncorrected-significant (fails Bonferroni) | 1 |

**Significance hierarchy:** result counts as notable only if Bonferroni p < alpha.
Uncorrected pass alone → label `EXPLORATORY_WEAK_SIGNAL_UNCONFIRMED`. No strategy use.

---

## 6. 3_STAR Per-Position Test Results

| Position | N | Chi² | p (raw) | Bonf-pass | Uncorr-pass | Classification |
|---|---|---|---|---|---|---|
| pos_0 | 5,850 | 9.4427 | 0.3974 | NO | NO | NOT_SIGNIFICANT |
| pos_1 | 5,850 | 6.3385 | 0.7056 | NO | NO | NOT_SIGNIFICANT |
| pos_2 | 5,850 | 11.1111 | 0.2682 | NO | NO | NOT_SIGNIFICANT |

**3_STAR result:** NULL_NO_SIGNIFICANCE_EXACT_MATCH_MARGINAL_NOT_TESTED

---

## 7. 4_STAR Per-Position Test Results

> 4_STAR exact ordered match is **excluded** (INOPERABLE at N=5,850).

| Position | N | Chi² | p (raw) | Bonf-pass | Uncorr-pass | Classification |
|---|---|---|---|---|---|---|
| pos_0 | 5,850 | 13.4154 | 0.1447 | NO | NO | NOT_SIGNIFICANT |
| pos_1 | 5,850 | 8.9744 | 0.4396 | NO | NO | NOT_SIGNIFICANT |
| pos_2 | 5,850 | 19.0325 | 0.0249 | NO | YES | UNCORRECTED_WEAK |
| pos_3 | 5,850 | 9.1350 | 0.4249 | NO | NO | NOT_SIGNIFICANT |

**4_STAR result:** UNCORRECTED_WEAK_1_POSITIONS_FAILS_BONFERRONI_EXACT_MATCH_EXCLUDED_INOPERABLE

---

## 8. Exact-Match Power Warning

| Lottery | Exact baseline | Expected hits (random) | Power | Action |
|---|---|---|---|---|
| 3_STAR | 1/1000 | 5.85 | MARGINAL | Not tested (no prediction model) |
| 4_STAR | 1/10000 | 0.585 | INOPERABLE | Excluded |

---

## 9. Walk-Forward OOS Checks

Walk-forward OOS checks triggered for 1 uncorrected-significant result(s).

### 4_STAR_pos_2 — digit 6

| Split | N | Rate | Baseline | Above baseline? |
|---|---|---|---|---|
| IS (first 4388) | 4388 | 0.1105 | 0.1 | True |
| OOS (last 1462) | 1462 | 0.1115 | 0.1 | True |

**Direction:** consistent

> Walk-forward OOS check for most-deviant digit. DESCRIPTIVE ONLY — not a significance claim. Even if direction is consistent, this does not authorize strategy use.
> This finding fails Bonferroni correction. OOS check is descriptive context only.
> Label: `EXPLORATORY_WEAK_SIGNAL_UNCONFIRMED` — does not authorize strategy use.

---

## 10. Leakage and Multiple-Testing Controls

| Control | Status |
|---|---|
| Pre-declared family | YES — 7 tests declared before scan |
| Bonferroni correction | Applied: alpha = 0.05/7 |
| Walk-forward OOS | Applied for 1 uncorrected-significant result(s) |
| No full-history fitting | All-history used uniformly; no post-hoc window selection |
| Significance test on all-history | YES — no train/test split for uniformity test itself |

---

## 11. Prior P227C Box-Play Caution

P227C (box-play, 120 hypotheses): UNDERPOWERED_NO_SIGNAL for both lottery types.
Straight-play is harder than box-play by ~8× (3_STAR) and ~48× (4_STAR).
This diagnostic tests digit uniformity only, not ordered hit-rate.

---

## 12. Classification

**`P214C_3STAR_4STAR_STRAIGHT_PLAY_BONFERRONI_DIAGNOSTIC_SCAN_COMPLETE`**

- Bonferroni-significant tests: **0** / 7
- Uncorrected-significant (fails Bonferroni): **1** / 7

**Result: NULL across all tested positions.** No corrected-significant digit bias detected.
1 result(s) pass uncorrected p<0.05 but fail Bonferroni correction.
These are labeled `EXPLORATORY_WEAK_SIGNAL_UNCONFIRMED` and do not authorize strategy use.

---

## 13. Recommended Next Direction

**HOLD** — no Bonferroni-significant digit bias detected.

The per-position digit distributions for 3_STAR and 4_STAR are consistent with
uniform random draws after multiple-testing correction. No corrected-significant
positional bias exists to motivate further straight-play research.

If the user wants to extend the research:

> No specific authorization phrase offered — result is NULL.
> Any new direction requires a new explicit user authorization with a fresh pre-registration.

---

## 14. No-Claim Attestation

This document:
- Makes **no claim** that any digit position has a predictable pattern
- Makes **no claim** that any finding (including OOS checks) provides an advantage
- Makes **no betting advice** for 3_STAR or 4_STAR
- Makes **no number suggestions** for any future draw
- Makes **no strategy promotion** or registry change
- Treats NULL as a valid and complete result
- Historical data is for diagnostic research only, not investment or gambling advice