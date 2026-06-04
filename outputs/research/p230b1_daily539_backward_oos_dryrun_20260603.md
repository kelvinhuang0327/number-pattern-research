# P230B1 — DAILY_539 Backward-OOS Code-Only Dry-Run

**Date:** 2026-06-03 (Asia/Taipei)  
**Task:** `P230B1_DAILY539_BACKWARD_OOS_CODE_ONLY_ARTIFACT_DRYRUN`  
**Classification:** `P230B1_BACKWARD_OOS_DRYRUN_BELOW_BASELINE`  
**Status:** COMPLETE / CODE-ONLY / ZERO DB WRITE

> **Dry-run artifact only.** No DB write, no replay rows created, no registry/production/recommendation change, no P225. Not betting advice and not a guaranteed predictive edge. Backward-OOS is older-regime robustness, **not** true future OOS, and cannot replace the P224B future 300/500-draw gate.

## Methodology

- Candidate: `midfreq_fourier_2bet / DAILY_539`, bet_index=1 (pure MidFreq bet-1; Fourier bet-2 not stored/invented).
- Reused `MidfreqFourier2BetAdapter` (`min_history=100`) + P31B causal slice `history = all_draws[:i]`.
- DB opened **read-only** (`mode=ro`); writes physically impossible. Artifacts only.
- Leakage guard: `history_cutoff_draw` = ordinal predecessor (`all_draws[i-1]`), not numeric `target_draw-1`.
- Baseline = `0.6410256410256411` (= 25/39, era-invariant). Stats replicate P224 (sample SD, 1.96·SE CI, one-sided z).

## Backward-OOS Inventory

| Field | Value |
|---|---|
| DAILY_539 total draws | 5876 |
| Candidate window min target_draw | 110000190 |
| Backward total (strictly earlier) | 4365 |
| Warmup skipped (min_history=100) | 100 |
| **Replayable backward targets** | **4265** |
| First replayable | 96000101 @ 2007/05/21 |
| Last backward target | 110000189 @ 2021/08/09 |

## Overall Result

| Metric | Backward-OOS | P224 in-window |
|---|---:|---:|
| n | 4265 | 1500 |
| mean hit_count | 0.637515 | 0.669333 |
| baseline | 0.641026 | 0.641026 |
| 95% CI | [0.616119, 0.658910] | [0.632237, 0.706430] |
| CI crosses baseline | True | True |
| one-sided p vs baseline | 0.626134 | 0.067372 |
| M1+ / M2+ / M3+ | 0.5104 / 0.1161 / 0.0106 | 0.524 / 0.1327 / 0.0127 |
| direction | below | above |

## Block Stability

| Block size | n blocks | above baseline | majority | block mean SD | worst | best |
|---|---:|---:|---|---:|---:|---:|
| 100 | 43 | 22 | True | 0.063656 | 0.500000 | 0.760000 |
| 150 | 29 | 16 | True | 0.055222 | 0.513333 | 0.746667 |
| 300 | 15 | 7 | False | 0.041021 | 0.566667 | 0.726667 |

## Robustness

| Check | n | mean | at/above baseline |
|---|---:|---:|---|
| Exclude hit_count≥3 (45 removed) | 4220 | 0.611848 | False |
| Exclude strongest 150-block (#18) | — | 0.633086 | False |

## Era Splits

| Era | n | mean | direction | one-sided p |
|---|---:|---:|---|---:|
| early_2007_2011 | 1258 | 0.631955 | below | 0.669782 |
| middle_2012_2016 | 1566 | 0.657088 | above | 0.184018 |
| late_2017_2021 | 1441 | 0.621096 | below | 0.859241 |

## Decision

- **Final classification:** `P230B1_BACKWARD_OOS_DRYRUN_BELOW_BASELINE`
- **Rationale:** backward-OOS mean 0.637515 < baseline 0.641026 -> historical-artifact direction
- DB write performed: **False** (rows 94924 → 94924).
- P230B2 (DB write/backfill), P230C (validation), and P225 (model design) remain **separately authorized only**. No production / registry / recommendation change. No promotion regardless of outcome.
