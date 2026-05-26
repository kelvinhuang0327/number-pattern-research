# P69 All-Strategy Dry-Run Batch Plan

**Phase:** P69 — All-Strategy Dry-Run Batch Plan (Plan-Only, No Production Write)
**Date:** 2026-05-26
**Status:** P69_ALL_STRATEGY_DRY_RUN_BATCH_PLAN_READY

---

## PROJECT_CONTEXT_LOCK

```
Project = LotteryNew
Canonical Repo = /Users/kelvin/Kelvin-WorkSpace/LotteryNew
Canonical Branch = main
```

This document applies ONLY to LotteryNew.

---

## Repository Context

| Field | Value |
|---|---|
| Repo | /Users/kelvin/Kelvin-WorkSpace/LotteryNew |
| Branch | p69-all-strategy-dry-run-batch-plan |
| HEAD (local main base) | 364a081 |
| origin/main HEAD | a736621 (P2 merged via PR #189) |
| Production rows before | 46960 |
| Production rows after | 46960 |
| DB write | NO |
| Force push | NO |
| Lifecycle promotion | NO |
| Registry mutation | NO |
| Champion replacement | NO |
| Production apply | NO |

---

## Guard Results (Pre-flight)

| Guard | Result |
|---|---|
| Drift guard (pre) | REPLAY_LIFECYCLE_DRIFT_GUARD_PASS |
| Branch governance (pre, main) | BRANCH_GOVERNANCE_PASS — branch='main' rows=46960 |
| Branch governance (P69 branch) | BRANCH_GOVERNANCE_PASS — branch='p69-all-strategy-dry-run-batch-plan' rows=46960 |
| Cross-project contamination | CLEAN — novel_hybrid_lotto and "novel axis" are LotteryNew-internal |

---

## P2 Audit Gate Summary

P2 Prediction-Helpfulness Audit (merged to origin/main, commit a736621, PR #189) classified 31 row-backed strategies. Only strategies labelled **prediction-helpful** with recommendation **prioritize-for-expansion** are authorized for P69.

| P2 metric | Value |
|---|---|
| Total strategies audited | 31 |
| prediction-helpful | 10 |
| baseline-equivalent | 5 |
| sub-baseline | 9 |
| fallback-equivalent | 1 |
| insufficient-evidence | 6 |
| Authorized for P69 | **8** (prediction-helpful + prioritize-for-expansion) |

Theoretical baselines (m3+):
- POWER_LOTTO: 3.87%
- BIG_LOTTO: 2.40% (saturated — excluded from P69)
- DAILY_539: 1.00%

---

## P68 Executability Inventory Summary

P68 (merged to origin/main, commit d2cec07, PR #187) scanned all 31 row-backed strategies for adapter existence and executability.

Key findings relevant to P69:
- All 8 authorized candidates have 1500 production rows each
- POWER_LOTTO candidates have adapters in `p47_wave4_powerlotto_adapters.py` (fourier_rhythm_3bet) and `p56_wave5_powerlotto_adapters.py` (fourier30_markov30_2bet)
- DAILY_539 RETIRED candidates (acb_1bet, acb_markov_midfreq_3bet, midfreq_acb_2bet, midfreq_fourier_2bet) have adapters in `p31a_wave1_retired_adapters.py`
- DAILY_539 ACTIVE candidates (539_3bet_orthogonal, acb_single_539) have adapters in `p36_wave2_daily539_adapters.py`
- All adapters are implemented and registered in `replay_strategy_registry.py`

---

## Explicit Exclusions

### BIG_LOTTO — Excluded (signal space exhausted)

BIG_LOTTO is excluded from P69 entirely. Reason: L90/L91 signal axis saturated. All BIG_LOTTO row-backed strategies achieved m3+ at or below the theoretical baseline of 2.40% (best: biglotto_deviation_2bet at 2.40% = exactly baseline). No prediction-helpful BIG_LOTTO strategy with prioritize-for-expansion exists.

Strategies excluded:
- biglotto_deviation_2bet (baseline-equivalent, keep-row-backed-only)
- ts3_regime_3bet (baseline-equivalent, keep-row-backed-only)
- bet2_fourier_expansion_biglotto (baseline-equivalent, keep-row-backed-only)
- markov_2bet_biglotto (sub-baseline, block-expansion)
- markov_single_biglotto (sub-baseline, block-expansion)
- cold_complement_biglotto (sub-baseline, block-expansion)
- coldpool15_biglotto (sub-baseline, block-expansion)
- fourier30_markov30_biglotto (sub-baseline, block-expansion)
- biglotto_triple_strike (insufficient-evidence, pre-governance)

### Sub-baseline POWER_LOTTO — Blocked

- **cold_complement_2bet**: m3+ 3.67% vs baseline 3.87% (−0.20%), sub-baseline, block-expansion

### Fallback-equivalent POWER_LOTTO — Blocked

- **zonal_entropy_2bet**: m3+ 3.67% vs baseline 3.87%, fallback-equivalent (identical to cold_complement_2bet performance), block-expansion unless re-scoped

### Deferred POWER_LOTTO — Pending OOS

- **midfreq_fourier_mk_3bet**: prediction-helpful (m3+ 4.40%, +0.53% vs baseline), but deferred pending OOS gates at 150/300/500 draws. Cannot proceed to P69 until OOS monitoring confirms performance holds out-of-sample.

### Sub-baseline DAILY_539 — Blocked

- **zone_gap_3bet_539**: m3+ 0.73% vs baseline 1.00% (−0.27%), block-expansion
- **p0b_539_3bet_f_cold_fmid**: m3+ 0.87% vs baseline 1.00%, block-expansion
- **p0c_539_3bet_f_cold_x2**: m3+ 0.87%, block-expansion

### Insufficient-evidence DAILY_539 — Not in first batch

- **daily539_f4cold**: REPLAY_ERROR, manual-review required first
- **daily539_markov_cold**: REPLAY_ERROR, manual-review required first

---

## Authorized Candidates (8 Strategies)

### POWER_LOTTO Candidates (2)

| # | strategy_id | P2 Label | m3+ | vs Baseline | Rows | Apply ID | P68 Adapter | Lifecycle |
|---|---|---|---|---|---|---|---|---|
| 1 | fourier_rhythm_3bet | prediction-helpful | 4.93% | +1.06% | 1500 | P19B_POWERLOTTO_FOURIER_1500_PROD_20260520 | p47_wave4_powerlotto_adapters.py | ONLINE |
| 2 | fourier30_markov30_2bet | prediction-helpful | 4.07% | +0.20% | 1500 | P58_POWERLOTTO_WAVE5_FOURIER30_MARKOV30_1500_PROD_20260525 | p56_wave5_powerlotto_adapters.py | ACTIVE |

### DAILY_539 Candidates (6)

| # | strategy_id | P2 Label | m3+ | vs Baseline | Rows | Apply ID | P68 Adapter | Lifecycle |
|---|---|---|---|---|---|---|---|---|
| 3 | acb_markov_midfreq_3bet | prediction-helpful | 1.07% | +0.07% | 1500 | P31B_DAILY539_RETIRED_7500_PROD_20260523 | p31a_wave1_retired_adapters.py | RETIRED |
| 4 | midfreq_acb_2bet | prediction-helpful | 1.27% | +0.27% | 1500 | P31B_DAILY539_RETIRED_7500_PROD_20260523 | p31a_wave1_retired_adapters.py | RETIRED |
| 5 | midfreq_fourier_2bet | prediction-helpful | 1.27% | +0.27% | 1500 | P31B_DAILY539_RETIRED_7500_PROD_20260523 | p31a_wave1_retired_adapters.py | RETIRED |
| 6 | acb_1bet | prediction-helpful | 1.07% | +0.07% | 1500 | P31B_DAILY539_RETIRED_7500_PROD_20260523 | p31a_wave1_retired_adapters.py | RETIRED |
| 7 | 539_3bet_orthogonal | prediction-helpful | 1.07% | +0.07% | 1500 | P37_DAILY539_WAVE2_9000_PROD_20260523 | p36_wave2_daily539_adapters.py | ACTIVE |
| 8 | acb_single_539 | prediction-helpful | 1.07% | +0.07% | 1500 | P37_DAILY539_WAVE2_9000_PROD_20260523 | p36_wave2_daily539_adapters.py | ACTIVE |

---

## Per-Strategy Dry-Run Plan

### Strategy 1: fourier_rhythm_3bet (POWER_LOTTO)

- **P2 label**: prediction-helpful
- **Baseline vs**: +1.06% (strongest POWER_LOTTO signal)
- **Current state**: ONLINE, 1500 rows, P19B apply
- **Adapter**: p47_wave4_powerlotto_adapters.py — present and registered
- **Dry-run executable without production write**: YES
- **Dry-run recommendation**: dry-run-now (Batch A)
- **Expected dry-run periods**:
  - 100 draws: ~2 months of POWER_LOTTO history; rapid sanity check
  - 500 draws: ~10 months; confirms medium-term signal
  - 1000 draws: ~20 months; deep validation
  - 1500 draws: ~30 months; matches current production depth
- **Expected row impact if applied** (new wave): 1500 rows per new apply wave
- **Risk**: Already ONLINE — any new expansion must use a new controlled_apply_id to avoid row collision with P19B rows
- **Blockers / dependencies**: None; adapter confirmed, rows confirmed
- **Required gate before P70**:
  - ☐ dry-run artifact (temp DB output)
  - ☐ temp DB rehearsal confirming no row collision
  - ☐ duplicate draw check
  - ☐ rollback plan documented
  - ☐ branch governance guard PASS
  - ☐ drift guard PASS
  - ☐ explicit apply authorization from CTO

---

### Strategy 2: fourier30_markov30_2bet (POWER_LOTTO)

- **P2 label**: prediction-helpful
- **Baseline vs**: +0.20%
- **Current state**: ACTIVE, 1500 rows, P58 apply
- **Adapter**: p56_wave5_powerlotto_adapters.py — present and registered
- **Dry-run executable without production write**: YES
- **Dry-run recommendation**: dry-run-now (Batch A)
- **Expected dry-run periods**:
  - 100 / 500 / 1000 / 1500 draws: same cadence as fourier_rhythm_3bet
- **Expected row impact if applied**: 1500 rows per new wave
- **Risk**: ACTIVE lifecycle; must not promote to ONLINE without separate P-phase
- **Blockers / dependencies**: None
- **Required gate before P70**: same as Strategy 1

---

### Strategy 3: acb_markov_midfreq_3bet (DAILY_539)

- **P2 label**: prediction-helpful
- **Baseline vs**: +0.07% (modest margin, statistically confirmed in P2)
- **Current state**: RETIRED lifecycle, 1500 rows, P31B apply
- **Adapter**: p31a_wave1_retired_adapters.py — present and registered
- **Dry-run executable without production write**: YES — RETIRED lifecycle does not block dry-run; adapter is still loadable
- **Dry-run recommendation**: dry-run-now (Batch B)
- **Expected dry-run periods**:
  - 100 draws: ~1.5 months (DAILY_539 draws 3×/week); rapid check
  - 500 draws: ~7.5 months; confirms signal persistence
  - 1000 draws: ~15 months; deep validation
  - 1500 draws: ~22 months; matches current production depth
- **Expected row impact if applied**: 1500 rows per new apply wave
- **Risk**: RETIRED lifecycle — any promotion requires explicit lifecycle promotion gate (not in P69)
- **Blockers / dependencies**: None for dry-run; lifecycle promotion needs separate authorization
- **Required gate before P70**: same standard gates + explicit lifecycle promotion authorization

---

### Strategy 4: midfreq_acb_2bet (DAILY_539)

- **P2 label**: prediction-helpful
- **Baseline vs**: +0.27% (strongest DAILY_539 signal alongside midfreq_fourier_2bet)
- **Current state**: RETIRED, 1500 rows, P31B apply
- **Adapter**: p31a_wave1_retired_adapters.py — present and registered
- **Dry-run executable without production write**: YES
- **Dry-run recommendation**: dry-run-now (Batch B, prioritized due to highest margin)
- **Expected dry-run periods**: 100 / 500 / 1000 / 1500 draws
- **Expected row impact if applied**: 1500 rows per wave
- **Risk**: RETIRED lifecycle (same as acb_markov_midfreq_3bet)
- **Required gate before P70**: standard gates + lifecycle authorization

---

### Strategy 5: midfreq_fourier_2bet (DAILY_539)

- **P2 label**: prediction-helpful
- **Baseline vs**: +0.27% (tied for highest DAILY_539 margin)
- **Note**: This is the DAILY_539 version (P31B apply). There is a separate POWER_LOTTO strategy with the same strategy_id (P48 apply, 4.67%). P69 scope is DAILY_539 only for this entry.
- **Current state**: RETIRED, 1500 rows, P31B apply
- **Adapter**: p31a_wave1_retired_adapters.py — present and registered
- **Dry-run executable without production write**: YES
- **Dry-run recommendation**: dry-run-now (Batch B, prioritized due to highest margin)
- **Expected dry-run periods**: 100 / 500 / 1000 / 1500 draws
- **Expected row impact if applied**: 1500 rows per wave
- **Risk**: Dual strategy_id (also exists as POWER_LOTTO row) — dry-run must filter by `lottery_type = DAILY_539` to avoid confusion
- **Required gate before P70**: standard gates + lottery_type filter confirmation

---

### Strategy 6: acb_1bet (DAILY_539)

- **P2 label**: prediction-helpful
- **Baseline vs**: +0.07%
- **Current state**: RETIRED, 1500 rows, P31B apply
- **Adapter**: p31a_wave1_retired_adapters.py — present and registered
- **Dry-run executable without production write**: YES
- **Dry-run recommendation**: dry-run-now (Batch B)
- **Expected dry-run periods**: 100 / 500 / 1000 / 1500 draws
- **Expected row impact if applied**: 1500 rows per wave
- **Risk**: RETIRED lifecycle
- **Required gate before P70**: standard gates + lifecycle authorization

---

### Strategy 7: 539_3bet_orthogonal (DAILY_539)

- **P2 label**: prediction-helpful
- **Baseline vs**: +0.07%
- **Current state**: ACTIVE, 1500 rows, P37 apply
- **Adapter**: p36_wave2_daily539_adapters.py — present and registered
- **Dry-run executable without production write**: YES
- **Dry-run recommendation**: dry-run-now (Batch B)
- **Expected dry-run periods**: 100 / 500 / 1000 / 1500 draws
- **Expected row impact if applied**: 1500 rows per wave
- **Risk**: None beyond standard
- **Required gate before P70**: standard gates

---

### Strategy 8: acb_single_539 (DAILY_539)

- **P2 label**: prediction-helpful
- **Baseline vs**: +0.07%
- **Current state**: ACTIVE, 1500 rows, P37 apply
- **Adapter**: p36_wave2_daily539_adapters.py — present and registered
- **Dry-run executable without production write**: YES
- **Dry-run recommendation**: dry-run-now (Batch B)
- **Expected dry-run periods**: 100 / 500 / 1000 / 1500 draws
- **Expected row impact if applied**: 1500 rows per wave
- **Risk**: None beyond standard
- **Required gate before P70**: standard gates

---

## Batch Grouping Recommendation

### Batch A — POWER_LOTTO (Priority 1)

Execute first. Smaller draw frequency (weekly) = faster human review cycle.

| Strategy | Reason for Priority |
|---|---|
| fourier_rhythm_3bet | Highest m3+ (+1.06%), ONLINE lifecycle, strongest signal |
| fourier30_markov30_2bet | +0.20% vs baseline, Wave 5 proven adapter |

**Recommended dry-run period for Batch A first pass**: 500 draws (≈10 months POWER_LOTTO history)
**Fallback**: Start at 100 draws if adapter smoke test needed

### Batch B — DAILY_539 (Priority 2)

Execute after Batch A confirms no adapter or DB issues. Larger draw frequency (3×/week) = larger row impact per wave but same 1500-row window.

Sub-batch B1 (higher margin, prioritize):

| Strategy | m3+ vs Baseline |
|---|---|
| midfreq_acb_2bet | +0.27% |
| midfreq_fourier_2bet (DAILY_539) | +0.27% |
| acb_markov_midfreq_3bet | +0.07% |

Sub-batch B2 (standard margin):

| Strategy | m3+ vs Baseline |
|---|---|
| acb_1bet | +0.07% |
| 539_3bet_orthogonal | +0.07% |
| acb_single_539 | +0.07% |

**Recommended dry-run period for Batch B first pass**: 500 draws (≈7.5 months DAILY_539 history)

---

## Expected Dry-Run Row Impact

These are **temp DB only** figures — production DB is NOT touched.

### POWER_LOTTO

| Period | Rows per strategy | Batch A total |
|---|---|---|
| 100 draws | 100 rows | 200 rows |
| 500 draws | 500 rows | 1000 rows |
| 1000 draws | 1000 rows | 2000 rows |
| 1500 draws | 1500 rows | 3000 rows |

### DAILY_539

| Period | Rows per strategy | Batch B total (6 strategies) |
|---|---|---|
| 100 draws | 100 rows | 600 rows |
| 500 draws | 500 rows | 3000 rows |
| 1000 draws | 1000 rows | 6000 rows |
| 1500 draws | 1500 rows | 9000 rows |

**Total dry-run rows (all 8 strategies, 1500-draw period)**: 12000 rows (temp DB only; production remains 46960)

**Expected production row impact if all 8 strategies later receive P70 approval and wave apply**: +12000 rows → production would be 58960

---

## Required Gates Before P70

For each strategy, ALL of the following must pass before any P70 controlled apply proposal:

1. **Dry-run artifact**: JSON output file from temp DB dry-run run
2. **Temp DB rehearsal**: Full rehearsal against temp DB confirming correct row counts, no duplicates, correct lottery_type
3. **Duplicate check**: No overlap with existing controlled_apply_id rows
4. **Rollback plan**: Documented procedure to remove new rows if needed
5. **Branch governance guard**: BRANCH_GOVERNANCE_PASS on apply branch
6. **Drift guard**: REPLAY_LIFECYCLE_DRIFT_GUARD_PASS on apply branch
7. **Explicit apply authorization**: CTO-level explicit authorization phrase in task description
8. **lifecycle_promotion check** (RETIRED strategies only): Must not promote lifecycle as side effect of dry-run

---

## Risk Table

| Risk | Affected Strategies | Mitigation |
|---|---|---|
| Dual strategy_id (midfreq_fourier_2bet exists in both POWER_LOTTO and DAILY_539) | midfreq_fourier_2bet | Always filter by `lottery_type = DAILY_539` in dry-run |
| RETIRED lifecycle may require reactivation before new wave apply | acb_1bet, acb_markov_midfreq_3bet, midfreq_acb_2bet, midfreq_fourier_2bet | Dry-run does NOT change lifecycle; P70 must explicitly authorize lifecycle gate |
| Row collision with existing apply IDs | All 8 | New wave must use new controlled_apply_id distinct from existing P19B/P31B/P37/P58 IDs |
| P6 remote sync debt (local main 19 ahead, 2 behind origin/main) | All | DO NOT resolve P6 in P69; dry-run operates against local DB which is canonical |
| midfreq_fourier_mk_3bet may appear in future expansion requests | N/A | Remains DEFERRED until OOS gates at 150/300/500 draws confirmed |

---

## Governance Confirmation

- **No DB write**: CONFIRMED
- **No force push**: CONFIRMED
- **No lifecycle promotion**: CONFIRMED
- **No registry mutation**: CONFIRMED
- **No champion replacement**: CONFIRMED
- **No production row apply**: CONFIRMED
- **No P70 apply proposal started**: CONFIRMED
- **P6 remote sync debt**: NOT modified

---

## Final Classification

```
P69_ALL_STRATEGY_DRY_RUN_BATCH_PLAN_READY
```
