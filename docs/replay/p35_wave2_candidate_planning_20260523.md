# P35: Wave 2 Candidate Planning — Remaining needs_promotion Strategies

**Phase**: P35  
**Branch**: `p35-wave2-candidate-planning`  
**Base Commit**: `4e301b3` (P34 merge)  
**Generated**: 2026-05-23  
**Classification**: `P35_WAVE2_CANDIDATE_PLANNING_MERGED_TO_MAIN`  
**Production Rows**: 19960 (unchanged — no DB write in P35)

---

## Summary

P35 is a **read-only planning phase**. No DB write, no adapter implementation, no registry mutation, no lifecycle promotion.

Starting point:
- P30 classified 51 non-row-backed strategies → 24 `needs_promotion`
- P31B Wave 1 applied 5 DAILY_539 RETIRED strategies (+7500 rows)
- Remaining `needs_promotion` = **19 strategies**

This document evaluates all 19, recommends a Wave 2 batch, and defines the P36 scope.

---

## Pre-flight Results

| Check | Result |
|-------|--------|
| Repo | `/Users/kelvin/Kelvin-WorkSpace/LotteryNew` ✓ |
| Branch | `main` (at P35 start) ✓ |
| HEAD | `4e301b3` (P34) ✓ |
| Production rows | 19960 ✓ |
| Drift guard | `REPLAY_LIFECYCLE_DRIFT_GUARD_PASS` ✓ |
| Branch governance | `BRANCH_GOVERNANCE_PASS` ✓ |

---

## P31B Wave 1 (Excluded from Wave 2)

The following 5 strategies were applied in P31B and are **excluded from all Wave 2 consideration**:

| strategy_id | lottery_type | rows |
|-------------|-------------|------|
| `acb_1bet` | DAILY_539 | 1500 |
| `acb_markov_midfreq` | DAILY_539 | 1500 |
| `acb_markov_midfreq_3bet` | DAILY_539 | 1500 |
| `midfreq_acb_2bet` | DAILY_539 | 1500 |
| `midfreq_fourier_2bet` | DAILY_539 | 1500 |

---

## Remaining 19 needs_promotion — Full Evaluation

### DAILY_539 (6 strategies)

| # | strategy_id | sub_class | effort | complexity | risk | action | rank |
|---|-------------|-----------|--------|-----------|------|--------|------|
| 1 | `539_3bet_orthogonal` | artifact_with_code | LOW | LOW | LOW | **wave2_candidate** | 4 |
| 2 | `acb_single_539` | artifact_with_code | LOW | LOW | LOW | **wave2_candidate** | 2 |
| 3 | `markov_1bet_539` | artifact_with_code | LOW | LOW | LOW | **wave2_candidate** | 1 |
| 4 | `p0b_539_3bet_f_cold_fmid` | artifact_with_code | LOW | LOW | LOW | **wave2_candidate** | 5 |
| 5 | `p0c_539_3bet_f_cold_x2` | artifact_with_code | LOW | LOW | LOW | **wave2_candidate** | 6 |
| 6 | `zone_gap_3bet_539` | artifact_with_code | LOW | LOW | LOW | **wave2_candidate** | 3 |

### BIG_LOTTO LOW Effort (6 strategies — deferred Wave 3)

| # | strategy_id | effort | risk | action | reason |
|---|-------------|--------|------|--------|--------|
| 1 | `bet2_fourier_expansion_biglotto` | LOW | MEDIUM | **defer_wave3** | BIG_LOTTO RETIRED adapter framework not yet established |
| 2 | `cold_complement_biglotto` | LOW | MEDIUM | **defer_wave3** | Same — BIG_LOTTO scaffold needed first |
| 3 | `coldpool15_biglotto` | LOW | MEDIUM | **defer_wave3** | Pair with cold_complement for coherent BIG_LOTTO batch |
| 4 | `fourier30_markov30_biglotto` | LOW | MEDIUM | **defer_wave3** | Hold for BIG_LOTTO bootstrap wave |
| 5 | `markov_2bet_biglotto` | LOW | MEDIUM | **defer_wave3** | Source in unified_predictor; first candidate in Wave 3 |
| 6 | `markov_single_biglotto` | LOW | MEDIUM | **defer_wave3** | 1-bet variant; pair with markov_2bet |

### BIG_LOTTO MEDIUM Effort (5 strategies — deferred Wave 4)

| # | strategy_id | effort | risk | action | blocking |
|---|-------------|--------|------|--------|---------|
| 1 | `acb_hot_fourier_3bet_biglotto` | MEDIUM | HIGH | **defer_wave4** | Multi-component ACB+Hot+Fourier; integration test required |
| 2 | `gap_dynamic_threshold_biglotto` | MEDIUM | HIGH | **defer_wave4** | Dynamic threshold parameter validation needed |
| 3 | `hot_gap_return_biglotto` | MEDIUM | HIGH | **defer_wave4** | Window size calibration for RETIRED replay |
| 4 | `hot_stop_rebound_biglotto` | MEDIUM | HIGH | **defer_wave4** | State-dependent stop-rebound logic |
| 5 | `multiwindow_fourier_biglotto` | MEDIUM | HIGH | **defer_wave4** | Multi-window config doc needed; sequence after fourier30_markov30 |

### Special Cases

| # | strategy_id | effort | risk | action | reason |
|---|-------------|--------|------|--------|--------|
| 1 | `cluster_pivot_biglotto` | LOW | HIGH | **manual_review_first** | edge=-0.45%, SHORT_MOMENTUM flag — likely REJECTED after backfill |
| 2 | `ts3_markov_freq_5bet_biglotto` | MEDIUM | HIGH | **block** | SUPERSEDED by `p1_dev_sum5bet` (ONLINE); re-promotion not recommended |

---

## Wave 2 Recommended Batch

**Batch Name**: Wave 2 — DAILY_539 Completion  
**Batch Size**: 6 strategies  
**Lottery Type**: DAILY_539 (coherent single-type batch)

### Rationale

1. DAILY_539 adapter pattern fully established by P31A/P31B — zero framework overhead
2. All 6 have `artifact_with_code` — only thin wrapper needed
3. All 6 are LOW effort + LOW risk
4. Completing the DAILY_539 sweep before starting BIG_LOTTO minimizes cross-type complexity
5. BIG_LOTTO RETIRED adapter framework must be bootstrapped separately (analogous to P31A)

### Ranked Candidate List

| rank | strategy_id | source artifact | expected format |
|------|-------------|-----------------|-----------------|
| 1 | `markov_1bet_539` | `backtest_39lotto_comprehensive.py::MarkovStrategy(n=1)` | 1-bet Markov |
| 2 | `acb_single_539` | `quick_predict.py::predict_539_acb` | 1-bet ACB single |
| 3 | `zone_gap_3bet_539` | `backtest_39lotto_comprehensive.py::ZoneBalanceStrategy` | 3-bet zone+gap |
| 4 | `539_3bet_orthogonal` | `backtest_39lotto_comprehensive.py` (orthogonal) | 3-bet orthogonal |
| 5 | `p0b_539_3bet_f_cold_fmid` | `predict_539_5bet_f4cold.py` (cold+midfreq) | 3-bet F4Cold variant |
| 6 | `p0c_539_3bet_f_cold_x2` | `predict_539_5bet_f4cold.py` (x2 multiplier) | 3-bet F4Cold x2 |

---

## Expected Row Impact (Estimate Only)

> **⚠ ESTIMATE ONLY — No DB write in P35. Rows will only be added if P36 dry-run passes and production apply is explicitly authorized.**

| item | value |
|------|-------|
| Rows per strategy | 1500 |
| Wave 2 strategies | 6 |
| Estimated new rows | **9,000** |
| Current production rows | 19,960 |
| Projected total (if applied) | **28,960** |

---

## P36 Recommended Scope

**Phase**: P36 — Wave 2 DAILY_539 Dry-run + Temp Rehearsal  
**Candidates**: All 6 Wave 2 candidates listed above  
**Expected dry-run rows**: 9,000  
**Adapter pattern reference**: `lottery_api/models/p31a_wave1_retired_adapters.py`

### P36 Execution Plan

1. Create `_P36AdapterMeta` + `_P36BaseAdapter` (no registry registration, no `_ALL_ADAPTERS` mutation)
2. Implement 6 thin adapter wrappers following P31A pattern
3. Run temp rehearsal for all 6 (dry_run=True)
4. Validate row counts: 6 × 1500 = 9000 dry-run rows
5. Verify predicted_numbers format (pick-5 for DAILY_539)
6. Run guard suite (drift + governance)
7. **STOP before production apply**

Production apply requires separate authorization (P37).

---

## Guard Results

| guard | status |
|-------|--------|
| Drift guard (pre) | `REPLAY_LIFECYCLE_DRIFT_GUARD_PASS` |
| Branch governance (pre) | `BRANCH_GOVERNANCE_PASS` (rows=19960) |
| Forbidden file scan | `CLEAN` |

---

## Production Data Integrity

- Production rows before P35: **19960**
- Production rows after P35: **19960** (unchanged)
- No DB write performed
- No lifecycle promotion
- No adapter implementation
- No registry mutation

---

## Next Phase

**P36**: Wave 2 DAILY_539 Dry-run + Temp Rehearsal  
- 6 candidate adapters  
- 9000 dry-run rows  
- Follow P31A adapter pattern  
- STOP before production apply
