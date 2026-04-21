# Best Strategy Ranking Reconciliation Report

**Date**: 2025-01  
**Audit Scope**: All 3 lotteries — DAILY_539, BIG_LOTTO, POWER_LOTTO

---

## Overview

This document tracks the authoritative best-strategy ranking per lottery and per num_bets,
and reconciles the backend code ranking with the strategy_states JSON ground truth.

---

## Ranking Rules (Spec)

Priority order for ranking:

1. `validated_status`: VALIDATED (2) > WATCH (1) > REJECT (0)  
2. `composite_score` (descending)  
3. `edge_1500p` (descending)  
4. `sharpe` (descending)  
5. `max_drawdown_rate` (ascending — lower is better)

REJECT strategies must never appear as `best_strategy` in any API response.

---

## DAILY_539 — Best Strategy Ranking

### Best Overall
| Rank | Strategy | n | Status | cs |
|------|----------|---|--------|----|
| 1 | **f4cold_5bet** | 5 | VALIDATED | 0.0936 |
| 2 | acb_markov_midfreq_3bet | 3 | VALIDATED | 0.0705 |
| 3 | acb_markov_fourier_3bet | 3 | VALIDATED | 0.0665 |
| 4 | midfreq_acb_2bet | 2 | VALIDATED | 0.0575 |
| 5 | f4cold_3bet | 3 | VALIDATED | 0.0520 |
| 6 | acb_1bet | 1 | WATCH | 0.0349 |

### Best Per num_bets
| n | Best Strategy | Status | cs |
|---|--------------|--------|----|
| 1 | acb_1bet | WATCH | 0.0349 |
| 2 | midfreq_acb_2bet | VALIDATED | 0.0575 |
| 3 | acb_markov_midfreq_3bet | VALIDATED | 0.0705 |
| 4 | *(no n=4 strategy)* | — | — |
| 5 | f4cold_5bet | VALIDATED | 0.0936 |

---

## BIG_LOTTO — Best Strategy Ranking

### Best Overall
| Rank | Strategy | n | Status | cs |
|------|----------|---|--------|----|
| 1 | **p1_deviation_4bet** | 4 | VALIDATED | 0.0343 |
| 2 | p1_dev_sum5bet | 5 | WATCH | 0.0386 |
| 3 | regime_2bet | 2 | WATCH | 0.0234 |
| 4 | p1_neighbor_cold_2bet | 2 | WATCH | 0.0223 |
| 5 | fourier_rhythm_2bet | 2 | WATCH | 0.0203 |
| 6 | ts3_markov_freq_5bet_w30 | 5 | WATCH | 0.0198 |
| 7 | ts3_regime_3bet | 3 | WATCH | 0.0182 |
| 8 | ts3_markov_4bet_w30 | 4 | WATCH | 0.0175 |
| 9 | triple_strike_3bet | 3 | WATCH | 0.0161 |
| 10 | echo_aware_3bet | 3 | WATCH | 0.0152 |
| — | deviation_complement_2bet | 2 | ❌ REJECT | — |

Note: `p1_deviation_4bet` is VALIDATED and ranks #1 despite `p1_dev_sum5bet` having a higher cs (0.0386 vs 0.0343), because VALIDATED > WATCH in the priority ordering.

### Best Per num_bets
| n | Best Strategy | Status | cs |
|---|--------------|--------|----|
| 2 | regime_2bet | WATCH | 0.0234 |
| 3 | ts3_regime_3bet | WATCH | 0.0182 |
| 4 | p1_deviation_4bet | VALIDATED | 0.0343 |
| 5 | p1_dev_sum5bet | WATCH | 0.0386 |

---

## POWER_LOTTO — Best Strategy Ranking

### Best Overall
| Rank | Strategy | n | Status | cs |
|------|----------|---|--------|----|
| 1 | **orthogonal_5bet** | 5 | WATCH | 0.0419 |
| 2 | midfreq_fourier_mk_3bet | 3 | WATCH | 0.0347 |
| 3 | pp3_freqort_4bet | 4 | WATCH | 0.0338 |
| 4 | fourier_rhythm_3bet | 3 | WATCH | 0.0283 |
| 5 | midfreq_fourier_2bet | 2 | WATCH | 0.0279 |
| 6 | fourier_rhythm_2bet | 2 | WATCH | 0.0189 |
| — | fourier30_markov30_2bet | 2 | ❌ REJECT | — |

**Important**: POWER_LOTTO has **0 VALIDATED strategies**. All active strategies are WATCH.

### Best Per num_bets
| n | Best Strategy | Status | cs |
|---|--------------|--------|----|
| 2 | midfreq_fourier_2bet | WATCH | 0.0279 |
| 3 | midfreq_fourier_mk_3bet | WATCH | 0.0347 |
| 4 | pp3_freqort_4bet | WATCH | 0.0338 |
| 5 | orthogonal_5bet | WATCH | 0.0419 |

---

## Changes Made to Backend Ranking Code

### `lottery_api/routes/decision.py` — `_rank_key()` (line 128)

**Before**: Only sorted by `(priority, composite_score)`, with fallback to `cp_score`  
**After**: Full spec-compliant ranking `(priority, cs, edge_1500p, sharpe, -max_drawdown_rate)`  
**Also**: REJECT strategies explicitly excluded from `best_strategy` selection

### `lottery_api/engine/prediction_tracker.py` — `_rank_key_phase_v()` (line 86)

**Before**: Only sorted by `(priority, composite_score)`  
**After**: Full spec-compliant ranking `(priority, cs, edge_1500p, sharpe, -max_drawdown_rate)`  
**Also**: REJECT strategies excluded from `_get_current_best_strategy_refs()` pool, removing
the legacy `edge_300p` fallback

---

## Reconciliation Notes

### Why `p1_dev_sum5bet` doesn't overtake `p1_deviation_4bet` in BIG_LOTTO
`p1_dev_sum5bet` has cs=0.0386 > p1_deviation_4bet cs=0.0343, BUT validated_status for  
`p1_deviation_4bet` is VALIDATED (priority=2) vs WATCH (priority=1) — so p1_deviation_4bet  
correctly ranks #1 per spec.

### Why `deviation_complement_2bet` was previously WATCH
Legacy labeling — the strategy was never re-audited after Phase V criteria hardened.
perm_p=0.0637 is slightly above the 0.05 threshold. Fixed in Phase R.

### Why `fourier30_markov30_2bet` was previously WATCH
Same legacy labeling issue. perm_p=0.3762 is far above threshold, AND all three window
edges are negative. Fixed in Phase R.

---

## API Consistency Check

The `/api/decision` endpoint now returns:
- `best_strategy`: null if only REJECT strategies exist for a lottery+num_bets combo
- `all_strategies`: still includes REJECT entries for transparency, sorted to bottom
- `strategy_status`: "PRODUCTION" for VALIDATED, "WATCH" for WATCH, "ADVISORY_ONLY" for REJECT
