# P231B — POWER_LOTTO First-Zone Backward-OOS Code-Only Dry-Run

**Date:** 2026-06-04 (Asia/Taipei)  
**Task:** `P231B_POWERLOTTO_FIRST_ZONE_BACKWARD_OOS_DRYRUN`  
**Classification:** `P231B_POWERLOTTO_FIRST_ZONE_BACKWARD_OOS_DRYRUN_NULL`  
**Status:** COMPLETE / CODE-ONLY / ZERO DB WRITE

> **Dry-run artifact only.** No DB write, no replay rows created, no registry/production/recommendation change, no promotion. Not betting advice and not a guaranteed predictive edge. Backward-OOS is older-regime robustness, **not** true future OOS, and cannot confirm deployment. Second zone is display-only (P211A).

## Methodology

- Candidate: `midfreq_fourier_mk_3bet / POWER_LOTTO`, **first zone**, deterministic **bet-1** (composite MidFreq×0.3 + Fourier×0.4 + Markov×0.3).
- In-window bets 2,3 are NOT in the deterministic P47 adapter and are **not invented** (P230B1 discipline).
- Reused `MidFreqFourierMk3BetAdapter` (`min_history=30`) + causal slice `history = all_draws[:i]`.
- DB opened **read-only** (`mode=ro`); writes physically impossible. Artifacts only.
- Leakage guard: `history_cutoff_draw` = ordinal predecessor (`all_draws[i-1]`), not numeric `target_draw-1`.
- First-zone baseline = `0.947368` (= 36/38). Second-zone baseline = `0.125` (= 1/8), display-only.
- Determinism: adapter has no RNG (numpy argsort); fully reproducible, no seed required.

## Backward-OOS Inventory

| Field | Value |
|---|---|
| POWER_LOTTO total draws | 1915 |
| Candidate window min target_draw | 101000002 |
| Backward total (strictly earlier) | 412 |
| Warmup skipped (min_history=30) | 30 |
| **Replayable backward targets (adapter-min)** | **382** |
| Replayable under conservative 100-warmup | 312 |
| First replayable | 97000031 @ 2008/05/08 |
| Last backward target | 101000001 @ 2012/01/02 |

## Overall First-Zone Result

| Metric | Backward-OOS (bet-1) | In-window bet-1 | In-window strategy-level (3-bet pooled) |
|---|---:|---:|---:|
| n | 382 | 1500 | 4500 |
| mean first-zone hit | 0.968586 | 1.027333 | 0.989556 |
| baseline (36/38) | 0.947368 | 0.947368 | 0.947368 |
| 95% CI | [0.888501, 1.048672] | — | — |
| CI crosses baseline | True | — | — |
| z vs baseline | 0.519288 | — | — |
| one-sided p vs baseline | 0.301780 | — | — |
| direction | above | above | above |
| hit distribution | `{'0': 116, '1': 173, '2': 83, '3': 9, '4': 1}` | — | — |

## Block Stability

| Block size | n blocks | above baseline | majority | block mean SD | worst | best |
|---|---:|---:|---|---:|---:|---:|
| 50 | 8 | 4 | False | 0.115538 | 0.740000 | 1.120000 |
| 100 | 4 | 2 | False | 0.108045 | 0.820000 | 1.097561 |
| 150 | 3 | 2 | True | 0.080421 | 0.906667 | 1.097561 |

## Robustness

| Check | n | mean | at/above baseline |
|---|---:|---:|---|
| Exclude hit_count≥3 (10 removed) | 372 | 0.911290 | False |
| Exclude strongest 100-block (#2) | — | 0.875000 | False |

## Year Splits (backward window 2008-2011)

| Year | n | mean | direction | one-sided p |
|---|---:|---:|---|---:|
| 2008 | 68 | 0.808824 | below | 0.950752 |
| 2009 | 105 | 1.019048 | above | 0.169502 |
| 2010 | 104 | 0.951923 | above | 0.475772 |
| 2011 | 104 | 1.038462 | above | 0.153275 |
| 2012 | 1 | 1.000000 | above | n/a |

## Second Zone (special) — DISPLAY ONLY

> Reported separately; **never** used in first-zone scoring or the final classification.

| Metric | Backward-OOS special |
|---|---:|
| n | 382 |
| special_hit rate | 0.109948 |
| baseline (1/8) | 0.125000 |
| direction | below |
| one-sided p vs baseline | 0.826506 |

## Decision

- **Final classification:** `P231B_POWERLOTTO_FIRST_ZONE_BACKWARD_OOS_DRYRUN_NULL`
- **Rationale:** backward-OOS mean 0.968586 ~ baseline 0.947368 (CI crosses, one-sided p=0.3018 not significant) -> NULL
- DB write performed: **False** (rows 94924 → 94924).
- Caveat: Backward-OOS is older-regime (2008-2011) robustness/falsification, NOT true future OOS. It can FALSIFY a candidate if below baseline, but cannot confirm deployment. The independent older slice (~312-382) is far smaller than DAILY_539's 4,265, so power is limited. Only deterministic bet-1 is tested. NOT betting advice, NOT a guaranteed edge.
- DB-write/backfill, registry, production, recommendation change, second-zone promotion, and strategy promotion remain **NOT AUTHORIZED** regardless of outcome.
