# P214B — 3_STAR / 4_STAR Straight-Play Read-Only Diagnostic

**Date:** 2026-06-05
**Task ID:** P214B
**Classification:** `P214B_3STAR_4STAR_STRAIGHT_PLAY_READONLY_DIAGNOSTIC_COMPLETE`
**Task Type:** Type C — Small Additive Implementation
**Production DB Write:** false
**Ingestion Performed:** false
**Replay Generation Performed:** false
**Strategy Scan Performed:** false
**Generated at:** 2026-06-05 15:44

---

## 1. Scope and Non-Goals

### In Scope

- Read-only diagnostic of 3_STAR and 4_STAR straight-play positional digit patterns
- Per-position digit distribution analysis (all-history + rolling windows)
- Descriptive chi-squared and entropy metrics
- Exact-match baseline and power-warning accounting
- Honest null-friendly summary

### Non-Goals (Explicit Prohibitions)

- No exact-match hit-rate prediction or scan
- No strategy promotion or registry change
- No DB write, ingestion, or replay generation
- No betting advice or number suggestions
- No claim of predictive edge or improved win rate
- No P211 restart or NIST build

---

## 2. Phase 0 Summary

All Phase 0 checks PASS:

| Check | Expected | Actual |
|---|---|---|
| repo | /Users/kelvin/Kelvin-WorkSpace/LotteryNew | PASS |
| branch | main | PASS |
| HEAD == origin/main | ef820db7 | PASS |
| DB integrity | ok | ok |
| replay rows | 94,924 | 94,924 |
| draw rows | 64,361 | 64,361 |
| 3_STAR rows | 5,850 | 5,850 |
| 4_STAR rows | 5,850 | 5,850 |
| star replay rows | 0 | 0 |
| drift guard | PASS | REPLAY_LIFECYCLE_DRIFT_GUARD_PASS |

---

## 3. P214 Protocol Recap

| Metric | 3_STAR | 4_STAR |
|---|---|---|
| Exact straight baseline | 1/1000 = 0.001 | 1/10000 = 0.0001 |
| Expected hits at N=5,850 | 5.85 | 0.585 |
| Exact-match power | MARGINAL | INOPERABLE |
| Per-position baseline | 1/10 per position | 1/10 per position |
| Per-position power | TRACTABLE | TRACTABLE |

---

## 4. Data Baseline

| Metric | Value |
|---|---|
| 3_STAR draws with numbers_positional | 5,850 |
| 4_STAR draws with numbers_positional | 5,850 |
| Source-to-DB match | 11,700 / 11,700 (P213L verified) |
| P227C box-play prior | UNDERPOWERED_NO_SIGNAL (both types) |

---

## 5. Diagnostic Method

For each lottery type:

1. Load all draws with `numbers_positional` from DB (read-only)
2. Parse positional digit arrays (JSON; each digit 0–9)
3. Compute per-position digit distribution (count of each digit 0–9 at each position)
4. Compute Shannon entropy per position (uniform reference: log₂(10) = 3.3219 bits)
5. Compute descriptive chi-squared vs uniform (descriptive context only)
6. Compute repeated-digit rate (draws with at least one repeated digit)
7. Compute rolling-window summaries for pre-registered windows

**No significance threshold is applied.** All metrics are descriptive context.

---

## 6. 3_STAR Findings

**Draw count:** 5,850
**Exact-match baseline:** 1/1,000 (MARGINAL power — see §8)
**Expected exact hits under random:** 5.85

### Per-Position Distribution (All History)

| Position | Obs | Entropy (bits) | Chi² (descriptive) | Max deviation | Most deviant digit |
|---|---|---|---|---|---|
| pos_0 | 5,850 | 3.3208 | 9.443 | 0.0079 | 6 (0.108) |
| pos_1 | 5,850 | 3.3211 | 6.338 | 0.0056 | 1 (0.094) |
| pos_2 | 5,850 | 3.3205 | 11.111 | 0.0096 | 1 (0.090) |

> Shannon entropy reference: uniform = log₂(10) ≈ 3.3219 bits.
> Entropy close to 3.3219 → near-uniform. Lower → concentrated on fewer digits.
> Chi-squared and entropy values are descriptive context only.

### Repeated Digit Rate (3_STAR)

| Draws with ≥1 repeated digit | Total draws | Rate | Random expected |
|---|---|---|---|
| 1,671 | 5,850 | 0.2856 | 0.2800 |

Random expected: 1 - (10×9×8)/(10³) = 0.28

### Rolling Window Summaries (3_STAR)

**w150 (last 150 draws):**

| Position | Entropy (bits) | Chi² | Max deviation |
|---|---|---|---|
| pos_0 | 3.2879 | 7.067 | 0.0400 |
| pos_1 | 3.2928 | 5.867 | 0.0333 |
| pos_2 | 3.2772 | 9.200 | 0.0400 |

**w500 (last 500 draws):**

| Position | Entropy (bits) | Chi² | Max deviation |
|---|---|---|---|
| pos_0 | 3.3062 | 10.960 | 0.0260 |
| pos_1 | 3.3107 | 7.840 | 0.0240 |
| pos_2 | 3.3044 | 12.800 | 0.0400 |

**w750 (last 750 draws):**

| Position | Entropy (bits) | Chi² | Max deviation |
|---|---|---|---|
| pos_0 | 3.3117 | 10.773 | 0.0187 |
| pos_1 | 3.3049 | 18.160 | 0.0347 |
| pos_2 | 3.3105 | 11.973 | 0.0267 |

**w1000 (last 1000 draws):**

| Position | Entropy (bits) | Chi² | Max deviation |
|---|---|---|---|
| pos_0 | 3.3152 | 9.300 | 0.0170 |
| pos_1 | 3.3153 | 9.300 | 0.0180 |
| pos_2 | 3.3136 | 11.600 | 0.0160 |

---

## 7. 4_STAR Findings

**Draw count:** 5,850
**Exact-match baseline:** 1/10,000 (INOPERABLE — see §8)
**Expected exact hits under random:** 0.585

> **4_STAR exact-match analysis is excluded** due to statistical inoperability at N=5,850.
> Per-position analysis only.

### Per-Position Distribution (All History)

| Position | Obs | Entropy (bits) | Chi² (descriptive) | Max deviation | Most deviant digit |
|---|---|---|---|---|---|
| pos_0 | 5,850 | 3.3203 | 13.415 | 0.0082 | 8 (0.092) |
| pos_1 | 5,850 | 3.3208 | 8.974 | 0.0082 | 0 (0.092) |
| pos_2 | 5,850 | 3.3196 | 19.032 | 0.0108 | 6 (0.111) |
| pos_3 | 5,850 | 3.3208 | 9.135 | 0.0097 | 3 (0.110) |

### Repeated Digit Rate (4_STAR)

| Draws with ≥1 repeated digit | Total draws | Rate | Random expected |
|---|---|---|---|
| 2,928 | 5,850 | 0.5005 | 0.4960 |

Random expected: 1 - (10×9×8×7)/(10⁴) = 0.496

### Rolling Window Summaries (4_STAR)

**w150 (last 150 draws):**

| Position | Entropy (bits) | Chi² | Max deviation |
|---|---|---|---|
| pos_0 | 3.3054 | 3.467 | 0.0267 |
| pos_1 | 3.2872 | 7.867 | 0.0600 |
| pos_2 | 3.2495 | 14.400 | 0.0533 |
| pos_3 | 3.2691 | 10.667 | 0.0467 |

**w500 (last 500 draws):**

| Position | Entropy (bits) | Chi² | Max deviation |
|---|---|---|---|
| pos_0 | 3.3200 | 1.360 | 0.0100 |
| pos_1 | 3.3025 | 13.640 | 0.0340 |
| pos_2 | 3.3160 | 4.200 | 0.0200 |
| pos_3 | 3.3083 | 9.560 | 0.0240 |

**w750 (last 750 draws):**

| Position | Entropy (bits) | Chi² | Max deviation |
|---|---|---|---|
| pos_0 | 3.3170 | 5.173 | 0.0160 |
| pos_1 | 3.3140 | 8.533 | 0.0267 |
| pos_2 | 3.3197 | 2.293 | 0.0093 |
| pos_3 | 3.3143 | 7.893 | 0.0160 |

**w1000 (last 1000 draws):**

| Position | Entropy (bits) | Chi² | Max deviation |
|---|---|---|---|
| pos_0 | 3.3185 | 4.800 | 0.0140 |
| pos_1 | 3.3187 | 4.640 | 0.0180 |
| pos_2 | 3.3198 | 2.900 | 0.0110 |
| pos_3 | 3.3167 | 7.220 | 0.0130 |

---

## 8. Exact-Match Power Warning

| Lottery | N draws | Expected hits (random) | Power status |
|---|---|---|---|
| 3_STAR | 5,850 | 5.85 | MARGINAL |
| 4_STAR | 5,850 | 0.585 | INOPERABLE |

**3_STAR:** At N=5850 draws, expected exact hits under random = 5.85. Bonferroni-corrected threshold (~60 hypotheses) requires ~14 hits. 2x signal detection is borderline. Do not overclaim.

**4_STAR:** At N=5850 draws, expected exact hits under random = 0.585. Most likely 0 exact hits in the entire dataset. 4_STAR exact-match cannot distinguish null from any moderate signal. Exact-match analysis is excluded. Per-position analysis only.

---

## 9. Per-Position Tractability Findings

| Lottery | Total digit obs | Per-position N | Uniform expected count |
|---|---|---|---|
| 3_STAR | 17,550 | 5,850 | 585 per digit |
| 4_STAR | 23,400 | 5,850 | 585 per digit |

Per-position analysis can detect ±2 percentage-point deviations at high power.
However, detecting bias ≠ predicting the next draw. Predictive claims require walk-forward OOS + Bonferroni.

---

## 10. Leakage and Multiple-Testing Controls

| Control | Status |
|---|---|
| Feature window rule | Descriptive only — no prediction features computed |
| Walk-forward OOS | Not run — required for any future P214C significance claim |
| Pre-registered windows | w150, w500, w750, w1000 (inherited from P221F/P214) |
| Bonferroni | Required for any future P214C scan (family ≥ 32, typical ≥ 256) |
| All-history fitting | Used for descriptive context only — no gating |
| Significance tests run | 0 |

---

## 11. Prior P227C Box-Play Caution

| Lottery | Bonferroni pass | BH-FDR pass | Classification |
|---|---|---|---|
| 3_STAR | 0 | 1 (weak) | UNDERPOWERED_NO_SIGNAL |
| 4_STAR | 0 | 0 | UNDERPOWERED_NO_SIGNAL |

Straight-play is harder than box-play by ~8× (3_STAR) and ~48× (4_STAR).
Any future straight-play scan must inherit this prior null context.

---

## 12. Classification

**`P214B_3STAR_4STAR_STRAIGHT_PLAY_READONLY_DIAGNOSTIC_COMPLETE`**

This diagnostic is complete as a read-only descriptive artifact.
It does not constitute a strategy scan, signal claim, or deployment recommendation.

---

## 13. Recommended Next Direction

**HOLD** unless user explicitly authorizes P214C.

If user wants to proceed:

> `Authorize P214C 3_STAR/4_STAR straight-play read-only diagnostic scan (Type C, no DB write, no strategy promotion, Bonferroni-corrected, per-position only for 4_STAR, walk-forward OOS required)`

---

## 14. No-Claim Attestation

This document:

- Makes **no claim** that any digit position shows a predictable pattern
- Makes **no claim** that per-position bias provides any advantage over random
- Makes **no betting advice** for 3_STAR or 4_STAR
- Makes **no number suggestions** for any future draw
- Makes **no strategy promotion** or registry change
- Does not imply future P214C will find anything other than null
- Historical positional data is for diagnostic research only
- NULL is a valid and complete result for any future scan