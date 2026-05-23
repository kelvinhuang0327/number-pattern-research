# P30 — Reconstructible-Candidacy Evaluation

**Date:** 2026-05-21  
**Phase:** P30_RECONSTRUCTIBLE_CANDIDACY_EVALUATION  
**Branch:** p30-reconstructible-candidacy-evaluation  
**Classification:** READ-ONLY (no DB write, no adapter execution, no registry change)

---

## 1. Objective

Evaluate which of the 51 non-row-backed strategies in the P28/P29 catalog are
candidates for replay backfill in a future P31 phase. Produce a ranked candidate
list so CTO can decide the scope of the next backfill wave.

---

## 2. Input

- `/api/replay/strategy-catalog` (P28) — 59 strategies total, 8 row-backed, 51 non-row-backed
- `lottery_api/models/replay_strategy_registry.py` — _LifecycleStub definitions
- `rejected/*.json` — artifact files for Artifact-Only strategies
- `tools/` and `lottery_api/` — code scan for underlying implementations

---

## 3. Classification Summary

| Classification | Count | Description |
|----------------|-------|-------------|
| **needs_promotion** | **24** | Code exists; thin ReplayStrategyAdapter wrapper needed |
| **manual_review** | **15** | Code unclear or composite; human judgment required |
| **executable_no** | **12** | Statistically rejected or no viable implementation |
| **TOTAL** | **51** | All non-row-backed strategies |

---

## 4. needs_promotion Strategies (24) — P31 Candidates

These strategies have underlying Python code that can produce `predicted_numbers`. Each requires only a thin `ReplayStrategyAdapter` wrapper — no strategy logic changes.

### DAILY_539 — 5 Retired + 3 Artifact (8 candidates)

| strategy_id | Effort | Underlying Code | Notes |
|-------------|--------|----------------|-------|
| `acb_1bet` | LOW | `tools/quick_predict.py::predict_539` ACB variant | Adapter shell exists |
| `acb_markov_midfreq` | LOW | `tools/quick_predict.py` + `tools/backtest_39lotto_comprehensive.py::MarkovStrategy` | Adapter shell exists |
| `acb_markov_midfreq_3bet` | LOW | Same as above (3-bet variant) | Adapter shell exists |
| `midfreq_acb_2bet` | LOW | MidFreq+ACB 2-bet | Adapter shell exists |
| `midfreq_fourier_2bet` | LOW | MidFreq+Fourier 2-bet | Adapter shell exists |
| `markov_1bet_539` | LOW | `tools/backtest_39lotto_comprehensive.py::MarkovStrategy` | Artifact artifact |
| `acb_single_539` | LOW | `tools/quick_predict.py` | Artifact artifact |
| `p0b_539_3bet_f_cold_fmid` / `p0c_539_3bet_f_cold_x2` | LOW | `tools/predict_539_5bet_f4cold.py` | F4Cold variants |
| `zone_gap_3bet_539` | LOW | `tools/backtest_39lotto_comprehensive.py::ZoneBalanceStrategy` | Zone+gap |
| `539_3bet_orthogonal` | LOW | `tools/backtest_39lotto_comprehensive.py` composite | 3-bet orthogonal |

### BIG_LOTTO — Artifact (10 candidates)

| strategy_id | Effort | Underlying Code | Notes |
|-------------|--------|----------------|-------|
| `cluster_pivot_biglotto` | LOW | `tools/backtest_biglotto_portfolio.py::ClusterPivot` | SHORT_MOMENTUM flag; edge=-0.45% |
| `fourier30_markov30_biglotto` | LOW | `tools/backtest_biglotto_comprehensive.py::strat_fourier30_markov30` | |
| `cold_complement_biglotto` | LOW | `tools/backtest_biglotto_enhancements.py::cold_numbers_bet` | |
| `markov_single_biglotto` | LOW | `lottery_api/models/unified_predictor.py::markov_predict` | |
| `markov_2bet_biglotto` | LOW | Same, 2-bet variant | |
| `coldpool15_biglotto` | LOW | `tools/backtest_biglotto_enhancements.py::cold_numbers_bet(pool=15)` | |
| `bet2_fourier_expansion_biglotto` | LOW | `tools/backtest_biglotto_comprehensive.py::FourierRhythmStrategy` | |
| `acb_hot_fourier_3bet_biglotto` | MEDIUM | Composite of enhancements + comprehensive | |
| `gap_dynamic_threshold_biglotto` | MEDIUM | `tools/backtest_biglotto_comprehensive.py::GapAnalysisStrategy` | |
| `hot_gap_return_biglotto` + `hot_stop_rebound_biglotto` | MEDIUM | Dedicated backtest files | |
| `multiwindow_fourier_biglotto` | MEDIUM | FourierRhythmStrategy multi-window | |

### POWER_LOTTO — none in needs_promotion

---

## 5. executable_no Strategies (12) — Permanently Deferred

These strategies are either statistically rejected, superseded, or have no viable implementation path.

| strategy_id | Reason |
|-------------|--------|
| `biglotto_ts3_acb_4bet` | Registry REJECTED; McNemar p>0.05; no adapter |
| `biglotto_ts3_markov_freq_5bet` | Superseded by p1_dev_sum5bet; registry REJECTED |
| `power_shlc_midfreq` | SHLC tested -2.92%; no code; registry REJECTED |
| `p1_deviation_2bet_539` | Zero edge on full dataset; registry REJECTED |
| `apriori_3bet_biglotto` | 1500p edge=-1.53%; permanently rejected |
| `core_satellite_biglotto` | Edge -0.89%~-2.39%; permanently rejected |
| `shlc_midfreq_power` | Tested -2.92% POWER_LOTTO; rejected |
| `sgp_power_017_research` / `sgp_v9_apex_powerlotto` | SGP research artifacts; no implementation |
| `special_mab_decay_adjustment_power` | MAB decay; rejected special number concept |
| `consecutive_pair_detector_539` | chi2 p=0.565; rejected |
| `neighbor_acb_2bet_539` | McNemar p=0.074; rejected |

---

## 6. manual_review Strategies (15) — Human Judgment Required

These strategies need manual investigation before a promotion decision:
- `h6_gate_mk20_ew85` (OBSERVATION) — H6 is a monitoring framework, not a prediction strategy
- `ts3_acb_4bet_biglotto` — Complex composite; no direct adapter
- `markov_repeat_exception_biglotto` — Has backtest file but no clear adapter pattern
- `neighbor_injection_biglotto` — No tool implementation found
- `gap_rebound_powerlotto` / `p1_conditional_branch_powerlotto` / `structural_zone_guard_pp3_power` — POWER_LOTTO artifacts with insufficient code
- `bandit_ucb1_2bet_539` / `lift_pair_single_539` — 539 artifacts without code
- `p0_neighbor_injection` / `p2_mab_fusion` / `p3_state_aware` / `short_term_hot_independent_bet` / `streak_boost_neighbor_bet1` / `zone_constraint_cold_bet2` — UNSPECIFIED lottery type; scope unclear

---

## 7. Production DB

Production rows: **12460** (unchanged — no DB writes, no adapter execution).

---

## 8. Recommended Next Phase: P31 Backfill Apply Pipeline

### Recommended P31 Wave 1 (LOW effort, high confidence)

Focus on **5 RETIRED DAILY_539 strategies** — all have adapter shells and underlying code:

1. `acb_1bet` → wrap predict_539 ACB variant
2. `acb_markov_midfreq` → wrap MidFreq+ACB predict
3. `acb_markov_midfreq_3bet` → wrap 3-bet variant
4. `midfreq_acb_2bet` → wrap MidFreq+ACB 2-bet
5. `midfreq_fourier_2bet` → wrap MidFreq+Fourier 2-bet

Expected rows after P31 Wave 1: 12460 + (5 × 1500) = **19960**  
(subject to duplicate detection; DAILY_539 legacy rows outside 1500-window → ~0 dups)

### Recommended P31 Wave 2 (LOW/MEDIUM effort)

- `markov_1bet_539` + `acb_single_539` + `p0b_539_3bet_f_cold_fmid` (DAILY_539)
- `markov_single_biglotto` + `markov_2bet_biglotto` + `fourier30_markov30_biglotto` (BIG_LOTTO)

### Decision gate for manual_review

Before promoting any `manual_review` strategy, a CTO read-only session should:
- Confirm the strategy can produce a deterministic `get_one_bet(history, lottery_type)` output
- Verify it is not a monitoring/alerting framework (e.g., h6_gate)
- Confirm lottery_type for UNSPECIFIED entries

---

## 9. Timeline Estimate

| Phase | Scope | Effort | Expected rows |
|-------|-------|--------|---------------|
| P31 Wave 1 | 5 retired DAILY_539 | ~2 sessions | +7500 = 19960 |
| P31 Wave 2 | 6 more LOW strategies | ~2 sessions | +9000 = 28960 |
| P31 Wave 3 | MEDIUM effort BIG_LOTTO | ~3 sessions | +~6000 = ~35000 |
| P32 | manual_review resolved | ~5 sessions | variable |

Full universe coverage (59 strategies, 1500 draws each) ≈ **88,500 rows**.
