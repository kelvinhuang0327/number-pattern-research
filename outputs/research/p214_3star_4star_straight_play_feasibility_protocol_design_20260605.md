# P214 — 3_STAR / 4_STAR Straight-Play Feasibility and Diagnostic Protocol Design

**Date:** 2026-06-05  
**Task ID:** P214  
**Classification:** `P214_3STAR_4STAR_STRAIGHT_PLAY_FEASIBILITY_PROTOCOL_DESIGN_COMPLETE`  
**Task Type:** Type B — Read-only Design Doc / Artifact  
**Author:** Worker Agent (standard model)  
**Production DB Write:** false  
**Ingestion Performed:** false  
**Strategy Scan Performed:** false  

---

## 1. Scope and Non-Goals

### In Scope

- Design protocol for straight-play diagnostics for 3_STAR and 4_STAR lotteries
- Define baseline rates for straight-play exact ordered match
- Identify statistical power limitations and minimum sample requirements
- Propose pre-registered evaluation windows, metrics, and hypotheses
- Define multiple-testing correction policy
- Define data leakage guard
- Define shape of future P214B and P214C tasks if user authorizes
- Provide a clear recommendation (HOLD vs. proceed)

### Non-Goals (Explicit Prohibitions)

- No straight-play implementation in this task
- No strategy scan or box-play re-scan
- No DB write, ingestion, or replay generation
- No registry mutation or production/recommendation change
- No monitoring or scheduler job
- No strategy adapter or promotion
- No betting advice, no number suggestions
- No hit-rate improvement claim
- No P211 restart or NIST build

---

## 2. P213L Data-Ready Recap

### What Changed After P213H and P213L

**P213H (Type D — Positional Backfill):**
- Updated `numbers_positional` column for 7,101 existing 3_STAR / 4_STAR draw rows that already had canonical numbers stored
- Confirmed that the existing DB stored draws as sorted (not positional) arrays
- Restored positional order from real CSV source files (`開出順序` column)
- Replay rows unchanged at 94,924

**P213L (Type D — Missing Source-Row Ingestion):**
- Inserted 4,599 source-only rows that existed in real CSV sources but were absent from the DB
- Source rows parsed: 11,700 (5,850 per lottery type)
- DB match after apply: 11,700 / 11,700
- 3_STAR draw rows: 4,179 → 5,850
- 4_STAR draw rows: 2,922 → 5,850
- `numbers_positional` column populated for all 11,700 star draw rows
- Replay rows unchanged at 94,924
- Drift guard: REPLAY_LIFECYCLE_DRIFT_GUARD_PASS

### Current DB State (as of 2026-06-05)

| Metric | Value |
|---|---|
| Total draw rows | 64,361 |
| 3_STAR draw rows | 5,850 |
| 4_STAR draw rows | 5,850 |
| 3_STAR `numbers_positional` populated | 5,850 |
| 4_STAR `numbers_positional` populated | 5,850 |
| Source-to-DB match | 11,700 / 11,700 (0 mismatches, 0 missing) |
| 3_STAR replay rows | 0 |
| 4_STAR replay rows | 0 |
| `strategy_prediction_replays` total | 94,924 |
| DB integrity | ok |
| Drift guard | PASS |

### Strategic Status After P213L

Before P213H/P213L, straight-play was **BLOCKED** because:
1. The DB stored draws as sorted arrays (`json.dumps(sorted(numbers))`), losing positional order
2. 4,599 source rows were missing from the DB entirely

After P213H/P213L:
- **Positional order is now preserved** in `numbers_positional` for all 11,700 star rows
- **All source rows are in DB** — 11,700 / 11,700 match
- **Straight-play is technically possible from a data perspective**
- **Status: DATA_READY_NO_SCAN_AUTHORIZED**

---

## 3. Prior P227C Box-Play Result Recap

### P227C Result Summary

P227C ran a 120-hypothesis dry-run scan (10 features × 6 windows × 2 lotteries) using box-play (multiset / sorted match, order-independent).

| Lottery | Draw Count | Baseline | Bonferroni Pass | BH-FDR Pass | Classification |
|---|---|---|---|---|---|
| 3_STAR | 4,179 | 1/120 = 0.00833 | 0 | 1 (weak) | UNDERPOWERED_NO_SIGNAL |
| 4_STAR | 2,922 | 1/210 = 0.00476 | 0 | 0 | UNDERPOWERED_NO_SIGNAL |

**Important note:** P227C used the pre-P213L draw counts (4,179 and 2,922). After P213L, counts are now 5,850 and 5,850. Any future scan must use the updated counts.

### Implications for Straight-Play Design

1. Box-play already returned UNDERPOWERED_NO_SIGNAL — the easier metric (order-independent) found nothing
2. Straight-play is a strictly harder metric: the prediction must match the exact digit order
3. If box-play is underpowered, straight-play faces an even more severe power problem
4. Any future straight-play scan must acknowledge this prior null result

---

## 4. Straight-Play Baseline Rates

### Definition of Straight-Play

Straight-play (直式玩法) requires an **exact ordered match** of all digits at each position. This is categorically different from box-play:

- **Box-play:** Prediction multiset equals actual multiset (order irrelevant)
- **Straight-play:** Prediction digit at position k equals actual digit at position k, for every position k

### 3_STAR Baseline

- Digits: 3 digits, each independently drawn from {0, 1, 2, ..., 9}
- Combination space: 10^3 = 1,000 ordered sequences
- **Exact straight match baseline: 1/1000 = 0.001**
- Expected exact hits in 5,850 draws: 5.85
- 95% Wilson CI for 5.85 hits / 5,850 draws: approximately [0.00038, 0.00231]

### 4_STAR Baseline

- Digits: 4 digits, each independently drawn from {0, 1, 2, ..., 9}
- Combination space: 10^4 = 10,000 ordered sequences
- **Exact straight match baseline: 1/10000 = 0.0001**
- Expected exact hits in 5,850 draws: 0.585
- Expected exact hits in any window ≤ 1,000 draws: ≤ 0.1
- **4_STAR straight-play exact match is essentially untestable at current sample sizes**

### Per-Position Digit Accuracy Baseline (Alternative Metric)

Rather than full exact match, per-position accuracy examines whether a specific digit at position k is predicted correctly.

| Metric | Baseline | 3_STAR Expected Observations | 4_STAR Expected Observations |
|---|---|---|---|
| Per-position digit accuracy | 1/10 = 0.10 | 5,850 × 3 = 17,550 | 5,850 × 4 = 23,400 |
| Per-position bias (chi-squared) | Uniform over {0-9} | 17,550 digit obs | 23,400 digit obs |

Per-position analysis is substantially more tractable than full exact-match due to more observations per test unit.

### Comparison: Box-Play vs Straight-Play

| Metric | 3_STAR | 4_STAR |
|---|---|---|
| Box baseline | 1/120 ≈ 0.00833 | 1/210 ≈ 0.00476 |
| Straight baseline | 1/1000 = 0.001 | 1/10000 = 0.0001 |
| Straight is harder by factor | ~8× | ~48× |
| Expected hits / 5,850 draws (straight) | 5.85 | 0.585 |

---

## 5. Statistical Power Warnings

### 3_STAR Straight Exact Match

With N = 5,850 draws and p₀ = 0.001:

- Expected hits under null: 5.85
- Standard deviation of hit count under null: √(5,850 × 0.001 × 0.999) ≈ 2.42
- To detect a doubling of the hit rate (p₁ = 0.002) at α = 0.05, power = 0.80:
  - Minimum detectable excess = z₀.₉₇₅ × σ₀ + z₀.₈₀ × σ₁
  - At N = 5,850: can detect approximately 11+ hits (expected under p₁ = 0.002 → 11.7)
  - This is marginal — a 2× signal would just clear the detection threshold at N = 5,850
- For Bonferroni-corrected threshold (dividing by family size of ~60–120 hypotheses):
  - Bonferroni-corrected α per test ≈ 0.05/120 ≈ 0.00042
  - Required z-score ≈ 3.55 → require hits ≥ 14
  - To reliably produce 14 hits under a 2× signal (p₁ = 0.002) would need N ≈ 7,000 draws
  - **3_STAR exact-match Bonferroni power: MARGINAL at N = 5,850**

### 4_STAR Straight Exact Match

With N = 5,850 draws and p₀ = 0.0001:

- Expected hits under null: 0.585
- Most likely 0 exact hits in the entire dataset
- Even under a 10× signal (p₁ = 0.001), expected hits = 5.85 — barely detectable
- **4_STAR exact-match straight-play is INOPERABLE at N = 5,850**
- Minimum recommended sample for any 4_STAR exact-match test: N ≥ 50,000 draws
- Current data represents ~11.7% of needed sample

### Per-Position Accuracy (More Tractable)

With 17,550 digit observations (3_STAR) or 23,400 (4_STAR), per-position bias tests are feasible:

- Chi-squared test over {0-9} at each position: df = 9
- Detecting a ±2 percentage-point deviation from 10% baseline: power ≈ 85% at N = 1,755 per position (achievable)
- Per-position accuracy: feasible diagnostic if signals are large enough

### Critical Warning

Any scan using 4_STAR exact straight-play metric with N = 5,850 will almost certainly return 0 exact hits. A result of "0 hits" is statistically consistent with both the null hypothesis (no signal) and any signal up to p₁ ≈ 0.003. **Overclaiming from 0 or near-0 hits is forbidden.**

---

## 6. Candidate Evaluation Units

### Draw-Level vs Bet-Level

- **Draw-level:** One prediction set per draw (how many draws had at least one correct bet?)
- **Bet-level:** Individual bets as rows (how many bets were exact straight matches?)
- For straight-play, bet-level analysis is more granular and statistically cleaner for Bonferroni correction
- Draw-level avoids double-counting when multiple bets are placed per draw

**Recommendation:** Use bet-level as primary unit for statistical tests. Use draw-level as secondary for consistency with P227C methodology.

### Metric Definitions for Future P214B Implementation

| Metric | Description | Baseline | Power Level |
|---|---|---|---|
| `star_straight_exact_match` | All digits match in exact position order | 3_STAR: 1/1000, 4_STAR: 1/10000 | 3_STAR: MARGINAL, 4_STAR: INOPERABLE |
| `star_position_accuracy_k` | Digit at position k is correct | 1/10 per position | TRACTABLE |
| `star_partial_match_count` | Number of positions with correct digit | 0–3 or 0–4, expected 0.3 (3_STAR) | MODERATE |
| `star_digit_bias_at_position_k` | Chi-squared over {0-9} for predicted vs actual digit at position k | Uniform chi-squared df=9 | TRACTABLE |

### Forbidden Metric

- **`calculate_match_score` (from box-play):** Must not be reused for straight-play. Box-play uses sorted multiset comparison. Straight-play requires position-ordered digit comparison.

---

## 7. Pre-Registered Windows

### Why Windows Must Be Pre-Registered

Pre-registration prevents post-hoc window selection, which manufactures false positives by choosing the window that happens to look best after seeing the data. Windows must be declared before any scan is run.

### Proposed Windows (Pre-Registration for Future P214C)

Following P221F anti-overfit protocol:

| Window Type | Window Size | Role |
|---|---|---|
| Short | 150 draws | Recency feature; cannot be standalone basis for signal claim |
| Mid | 500 draws | Primary stability window |
| Mid | 750 draws | Secondary stability window |
| Mid | 1000 draws | Tertiary stability window |
| All-history | All draws (5,850) | Reference only — must not be used as gating window |

**Short window (150 draws) constraint:** Per P210 protocol, short windows produce highly variable estimates. A 150-draw window for 3_STAR exact-match produces expected 0.15 hits under null — **effectively no information for exact-match signal detection**. Short windows may only serve as recency features fed into prediction logic, never as standalone significance claims.

### Why These Windows

- Inherited from P221F cross-lottery feature-discovery protocol (frozen 2026-06-03)
- Consistent with P227C box-play scan window design
- Allows cross-comparison between box-play (P227C) and straight-play results
- All-history excluded from gating to prevent full-history parameter fitting

---

## 8. Multiple-Testing Correction Policy

### Family Size Definition

For any future P214C scan, the multiple-testing family must be defined before scanning:

| Dimension | Count |
|---|---|
| Lottery types | 2 (3_STAR, 4_STAR) |
| Metrics | N_m (to be fixed before scan; at minimum 4: exact_match, position_0, position_1, position_2) |
| Windows | 4 (w150, w500, w750, w1000; all-history excluded from gating) |
| Features | N_f (to be fixed; expected 5–10 per feature category) |

**Minimum family size (without features):** 2 × 4 × 4 = 32 hypotheses  
**Typical family size (with features):** 2 × 4 × 4 × 8 = 256 hypotheses

### Required Corrections

1. **Bonferroni correction** (primary gate): α_per_test = 0.05 / family_size
2. **Benjamini-Hochberg FDR** (secondary, exploratory only): q = 0.05; BH pass alone does NOT authorize deployment
3. **Permutation test** (required for any result claiming statistical significance): ≥ 1,000 permutations of draw labels

### Significance Hierarchy

A hypothesis may only be reported as "potentially signal-bearing" if it passes ALL of:
1. Bonferroni-corrected p < α_per_test
2. Permutation test p < 0.05
3. Effect size meets minimum practical threshold (to be specified in P214B design)
4. Block stability: majority of non-overlapping sub-windows show same direction
5. Walk-forward OOS: edge holds on held-out future draws

BH-FDR pass alone warrants only the label: `EXPLORATORY_WEAK_SIGNAL_UNCONFIRMED` — not deployment.

---

## 9. Leakage Guard

### What Constitutes Leakage in This Context

1. **Full-history feature selection:** Choosing which features, windows, or thresholds to use after looking at the full dataset, then reporting the best result as if pre-registered
2. **Future rows in features:** Using draw N's actual outcome when computing a feature for draw N's prediction
3. **Post-hoc window adjustment:** Selecting which window size to report after seeing which gives the best p-value
4. **Baseline manipulation:** Changing the baseline after observing the hit distribution

### Required Leakage Guards

| Guard | Requirement |
|---|---|
| Feature window | Features at draw N must only use draws {1, ..., N-1} |
| Walk-forward OOS | All significance tests must use OOS draws only; IS period used only for feature design, never for claiming signal |
| No all-history parameter fitting | Cannot select features, weights, or thresholds using the full 5,850-draw history, then test on the same history |
| Pre-declared baseline | Exact straight match baseline (1/1000 or 1/10000) must be declared before scan; positional baseline (1/10) must be declared before scan |
| Family size pre-declaration | The full hypothesis family must be stated before any scan begins; no adding hypotheses after seeing results |

### Walk-Forward Implementation Shape

```
For draw N from (window_size) to 5849:
    features[N] = compute(draws[N-window_size : N])  # strictly past data
    prediction[N] = predict(features[N])
    outcome[N] = actual_digits[N]
    score[N] = is_straight_exact_match(prediction[N], outcome[N])

oos_hit_rate = mean(score[walk_forward_window_start : end])
```

---

## 10. Future Implementation Shape

### What P214B Should Implement (If Authorized)

P214B is a **Type C additive implementation** that:

1. Implements `star_straight_exact_match(predicted_digits, actual_digits)` function
2. Implements `star_position_accuracy(predicted_digits, actual_digits, position_k)` function
3. Implements `star_digit_bias_at_position(draws, position_k, window)` function
4. Implements `compute_straight_play_metrics(draws, window_config)` dry-run script
5. Implements unit tests with mock data (no real DB write)
6. Validates that `numbers_positional` column is correctly parsed as ordered digit list
7. Does NOT implement any prediction logic or strategy adapter
8. Does NOT write to DB

Authorization phrase for P214B: `Authorize P214B 3_STAR/4_STAR straight-play dry-run code implementation (Type C, no DB write, no strategy scan, additive only)`

### What P214C Should Run (If Authorized)

P214C is a **Type C read-only diagnostic run** that:

1. Runs the P214B code dry-run on the 5,850 3_STAR draws only (4_STAR exact-match power too low)
2. Tests per-position digit accuracy across pre-registered windows {w150, w500, w750, w1000}
3. Tests per-position digit bias (chi-squared) at each position
4. Reports Bonferroni-corrected results over pre-declared family
5. Reports permutation test p-values for any result passing Bonferroni
6. Reports block stability for any result passing permutation test
7. Reports walk-forward OOS edge with 95% Wilson CI
8. Produces JSON + Markdown artifact (no DB write)
9. Does NOT recommend any strategy or prediction
10. Must include no-claim attestation

**4_STAR exact-match should not be the primary focus of P214C** due to expected 0 hits. 4_STAR analysis in P214C should be limited to per-position digit bias only.

Authorization phrase for P214C: `Authorize P214C 3_STAR/4_STAR straight-play read-only diagnostic run (Type C, no DB write, no strategy scan, per-position only for 4_STAR, follows P214B implementation)`

---

## 11. Recommendation

### Assessment

| Dimension | Assessment |
|---|---|
| 3_STAR exact straight-match | MARGINAL power at N=5,850. Feasible but borderline. Per-position analysis is more robust. |
| 4_STAR exact straight-match | INOPERABLE at N=5,850. Expected ~0.5 hits; cannot distinguish null from any moderate signal. |
| 3_STAR per-position digit accuracy | TRACTABLE. 17,550 observations per position. Feasible diagnostic. |
| 4_STAR per-position digit accuracy | TRACTABLE. 23,400 observations per position. Feasible diagnostic. |
| Prior box-play result (P227C) | UNDERPOWERED_NO_SIGNAL. Straight-play is harder; prior null provides context. |
| Prior Lessons | L86 (overfit), L89 (MicroFish overfit), L91 (BIG_LOTTO signal-space boundary), L85 (dilution at scale). |

### Recommended Direction

**HOLD on full diagnostic implementation pending explicit authorization.**

The design work in this document is sufficient to define a safe P214B + P214C scope. However, given:
1. Prior box-play null result (P227C)
2. 4_STAR exact-match statistical impracticality at N = 5,850
3. Project-level exhaustion of most signal spaces (L82, L90, L91)
4. Risk of manufacturing false positives from low-count sparse-hit tests

The recommended posture is: **HOLD unless user explicitly authorizes P214B read-only code implementation.**

If the user wants to proceed, P214B (additive code) is the next safe step, followed by P214C (diagnostic run) only after P214B is verified.

### Alternative: Design-Only Extension

If the user wants to further extend the design without implementation, a P214D design doc could:
- Enumerate all candidate features for straight-play (digit recency, positional frequency, digit transition matrices)
- Pre-register the full hypothesis family before P214C
- Specify minimum sample requirements for future data collection

---

## 12. Exact Next Authorization Phrase

If the user authorizes straight-play code implementation:

> **Authorize P214B 3_STAR/4_STAR straight-play dry-run code implementation (Type C, no DB write, no strategy scan, additive only)**

If the user authorizes straight-play diagnostic run (requires P214B complete first):

> **Authorize P214C 3_STAR/4_STAR straight-play read-only diagnostic run (Type C, no DB write, no strategy scan, per-position only for 4_STAR, follows P214B implementation)**

If the user wants to remain on hold:

> No authorization phrase needed — system remains at WAITING_FOR_USER_AUTHORIZATION.

---

## 13. No-Claim Attestation

This document:

- Makes **no claim** that straight-play has any predictive edge over random baseline
- Makes **no claim** that per-position digit frequency analysis provides any betting advantage
- Makes **no betting recommendation** for 3_STAR or 4_STAR
- Makes **no strategy promotion** or registry change
- Makes **no claim** that the P213H/P213L data recovery implies signal exists
- **Does not imply** that future P214B/P214C results will be anything other than null
- Historical replay evidence (if any) is for diagnostic research only, not investment, gambling, or financial advice
- NULL is a valid and complete result for any future diagnostic scan

---

## Appendix A: Phase 0 Verification Results

| Check | Expected | Actual | Status |
|---|---|---|---|
| repo | /Users/kelvin/Kelvin-WorkSpace/LotteryNew | /Users/kelvin/Kelvin-WorkSpace/LotteryNew | PASS |
| branch | main (dev for write) | main / p214-straight-play-feasibility-protocol-design | PASS |
| HEAD == origin/main | b1027d232ed54ce7530528e3da1147e6d113b51c | b1027d232ed54ce7530528e3da1147e6d113b51c | PASS |
| staged files | 0 | 0 | PASS |
| DB integrity | ok | ok | PASS |
| replay rows | 94,924 | 94,924 | PASS |
| draw rows | 64,361 | 64,361 | PASS |
| 3_STAR draw rows | 5,850 | 5,850 | PASS |
| 4_STAR draw rows | 5,850 | 5,850 | PASS |
| 3_STAR numbers_positional | 5,850 | 5,850 | PASS |
| 4_STAR numbers_positional | 5,850 | 5,850 | PASS |
| 3_STAR replay rows | 0 | 0 | PASS |
| 4_STAR replay rows | 0 | 0 | PASS |
| bet_index nulls | 0 | 0 | PASS |
| duplicate replay keys | 0 | 0 | PASS |
| drift guard | PASS | REPLAY_LIFECYCLE_DRIFT_GUARD_PASS | PASS |
