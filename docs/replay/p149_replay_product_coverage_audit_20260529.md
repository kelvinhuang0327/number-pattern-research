# P149: Replay Product Coverage Audit

**Generated**: 2026-05-30T10:47:46.836801+00:00
**Classification**: `P149_REPLAY_PRODUCT_COVERAGE_AUDIT_READY`

## 1. Executive Summary

P149 audit complete. 40 strategy IDs discovered (18 in registry, 35 in DB, 13 in both). 94924 replay rows across 36 strategy-lottery pairs. 9 product gaps identified. Critical gaps: 1. High gaps: 3. Recommended next task: P150_REPLAY_API_ALL_STRATEGY_COVERAGE. No DB write, no controlled_apply, no champion promotion in P149.

This audit shifts the mainline focus from champion/live-evidence governance (P147-P148C) back to full-strategy historical replay product coverage. The goal is to identify all gaps between what the replay store contains and what the replay product (API + UI + catalog) exposes to end users.

## 2. Canonical Repo / Branch Confirmation

- Repo: `/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802` → **OK**
- Branch: `claude/zen-gates-ff6802` → **OK**
- DB rows: `94924` → **OK**
- Drift guard: **PASS**

## 3. Why P148C blocks champion but not replay product

P148C confirmed that all DB actual_numbers for candidate strategies are historical backfill (Wave1/Wave2/Wave4/P131/P134), not LIVE_MONITORING_VERIFIED. This blocks champion evaluation (P147) but does NOT block replay product display: historical actual_numbers are the correct source of truth for replay hit-rate statistics. LEGACY_UNVERIFIED rows (100 rows, power_precision_3bet and power_orthogonal_5bet) are kept as governed baseline per P144D and can be displayed with a LEGACY badge. The replay product is orthogonal to champion promotion: replay shows historical evidence while champion evaluation requires post-apply live draw evidence.

| Dimension | Replay Product | Champion Evaluation |
|-----------|---------------|---------------------|
| actual_numbers source | Historical backfill (Wave1/Wave2/Wave4/P131/P134) | Requires LIVE_MONITORING_VERIFIED |
| P148C impact | NOT blocked — historical actual_numbers are valid for display | BLOCKED — historical backfill ≠ live evidence |
| LEGACY_UNVERIFIED rows | Displayable with badge per P144D governed baseline | Excluded from champion evaluation |
| Gate | None — display is always allowed | P147/P148/P148B/P148C gates |

## 4. Strategy Inventory Audit

- Total strategy IDs discovered: **40**
- In registry: 18
- In DB: 35
- In both: 13
- Registry only (no replay rows): 5 — ['biglotto_ts3_acb_4bet', 'biglotto_ts3_markov_freq_5bet', 'h6_gate_mk20_ew85', 'p1_deviation_2bet_539', 'power_shlc_midfreq']
- DB only (no registry lifecycle): 22 — ['539_3bet_orthogonal', 'acb_single_539', 'bet2_fourier_expansion_biglotto', 'biglotto_echo_aware_3bet', 'biglotto_ts3_markov_4bet_w30', 'cold_complement_2bet', 'cold_complement_biglotto', 'coldpool15_biglotto', 'daily539_f4cold_3bet', 'daily539_f4cold_5bet', 'fourier30_markov30_2bet', 'fourier30_markov30_biglotto', 'markov_1bet_539', 'markov_2bet_biglotto', 'markov_single_biglotto', 'midfreq_fourier_mk_3bet', 'p0b_539_3bet_f_cold_fmid', 'p0c_539_3bet_f_cold_x2', 'power_fourier_rhythm_2bet', 'pp3_freqort_4bet', 'zonal_entropy_2bet', 'zone_gap_3bet_539']

**Inventory sources:**
- `lottery_api/models/replay_strategy_registry.py`
- `strategies/ (18 json files)`
- `rejected/ (42 json files)`
- `strategies/**/*.yaml (9 files)`
- `lottery_api/models/p*_adapters.py (8 files)`

**Strategy list (registry + DB union):**

| strategy_id | lottery_type | lifecycle | in_registry | in_db | replay_rows |
|-------------|--------------|-----------|------------|-------|-------------|
| 539_3bet_orthogonal | DAILY_539 | UNKNOWN | False | True | 1500 |
| acb_1bet | DAILY_539 | RETIRED | True | True | 1500 |
| acb_markov_midfreq | DAILY_539 | RETIRED | True | True | 1500 |
| acb_markov_midfreq_3bet | DAILY_539 | RETIRED | True | True | 4500 |
| acb_single_539 | DAILY_539 | UNKNOWN | False | True | 1500 |
| bet2_fourier_expansion_biglotto | BIG_LOTTO | UNKNOWN | False | True | 1500 |
| biglotto_deviation_2bet | BIG_LOTTO | ONLINE | True | True | 1570 |
| biglotto_echo_aware_3bet | BIG_LOTTO | UNKNOWN | False | True | 4500 |
| biglotto_triple_strike | BIG_LOTTO | ONLINE | True | True | 1570 |
| biglotto_ts3_acb_4bet | BIG_LOTTO | REJECTED | True | False | 0 |
| biglotto_ts3_markov_4bet_w30 | BIG_LOTTO | UNKNOWN | False | True | 6000 |
| biglotto_ts3_markov_freq_5bet | BIG_LOTTO | REJECTED | True | False | 0 |
| cold_complement_2bet | POWER_LOTTO | UNKNOWN | False | True | 1500 |
| cold_complement_biglotto | BIG_LOTTO | UNKNOWN | False | True | 1500 |
| coldpool15_biglotto | BIG_LOTTO | UNKNOWN | False | True | 1500 |
| daily539_f4cold | DAILY_539 | ONLINE | True | True | 1590 |
| daily539_f4cold_3bet | DAILY_539 | UNKNOWN | False | True | 4500 |
| daily539_f4cold_5bet | DAILY_539 | UNKNOWN | False | True | 7500 |
| daily539_markov_cold | DAILY_539 | ONLINE | True | True | 1590 |
| fourier30_markov30_2bet | POWER_LOTTO | UNKNOWN | False | True | 1501 |
| fourier30_markov30_biglotto | BIG_LOTTO | UNKNOWN | False | True | 1500 |
| fourier_rhythm_3bet | POWER_LOTTO | ONLINE | True | True | 4503 |
| h6_gate_mk20_ew85 | POWER_LOTTO | OBSERVATION | True | False | 0 |
| markov_1bet_539 | DAILY_539 | UNKNOWN | False | True | 1500 |
| markov_2bet_biglotto | BIG_LOTTO | UNKNOWN | False | True | 1500 |
| markov_single_biglotto | BIG_LOTTO | UNKNOWN | False | True | 1500 |
| midfreq_acb_2bet | DAILY_539 | RETIRED | True | True | 1500 |
| midfreq_fourier_2bet | DAILY_539 | RETIRED | True | True | 3000 |
| midfreq_fourier_mk_3bet | POWER_LOTTO | UNKNOWN | False | True | 4500 |
| p0b_539_3bet_f_cold_fmid | DAILY_539 | UNKNOWN | False | True | 1500 |
| p0c_539_3bet_f_cold_x2 | DAILY_539 | UNKNOWN | False | True | 1500 |
| p1_deviation_2bet_539 | DAILY_539 | REJECTED | True | False | 0 |
| power_fourier_rhythm_2bet | POWER_LOTTO | UNKNOWN | False | True | 3000 |
| power_orthogonal_5bet | POWER_LOTTO | ONLINE | True | True | 7550 |
| power_precision_3bet | POWER_LOTTO | ONLINE | True | True | 4550 |
| power_shlc_midfreq | POWER_LOTTO | REJECTED | True | False | 0 |
| pp3_freqort_4bet | POWER_LOTTO | UNKNOWN | False | True | 6000 |
| ts3_regime_3bet | BIG_LOTTO | ONLINE | True | True | 1500 |
| zonal_entropy_2bet | POWER_LOTTO | UNKNOWN | False | True | 1500 |
| zone_gap_3bet_539 | DAILY_539 | UNKNOWN | False | True | 1500 |

## 5. Replay Row Coverage Summary

- **Total replay rows**: 94924
- Strategies with replay rows: 35
- Strategies without replay rows: 5
- Strategies with no_data_reason: 0
- Strategies missing no_data_reason: 5
- Strategy-lottery pairs with rows: 36

## 6. Lifecycle Coverage Summary

| Lifecycle | Count |
|-----------|-------|
| ONLINE | 8 |
| REJECTED | 4 |
| OBSERVATION | 1 |
| UNKNOWN | 22 |
| RETIRED | 5 |

## 7. Replay API Capability Audit

| Feature | Status |
|---------|--------|
| all_strategies_queryable | ✓ |
| single_strategy_queryable | ✓ |
| lifecycle_filter_supported | ✓ |
| target_draw_filter_supported | ✓ |
| predicted_numbers_returned | ✓ |
| actual_numbers_returned | ✓ |
| hit_count_returned | ✓ |
| bet_index_returned | ✗ |
| truth_level_returned | ✓ |
| source_returned | ✓ |
| controlled_apply_id_returned | ✓ |
| no_data_reason_returned | ✗ |

**API Gaps:**
- bet_index not returned in /api/replay/history response — multi-bet rows indistinguishable
- no_data_reason field not returned — NO_DATA strategies cannot explain absence

## 8. Replay UI Capability Audit

| Feature | Status |
|---------|--------|
| all_strategies_list_exists | ✓ |
| lifecycle_filter_exists | ✓ |
| no_data_row_display_exists | ✗ |
| multi_bet_display_exists | ✗ |
| truth_level_badge_exists | ✓ |
| prediction_vs_actual_comparison_exists | ✓ |

**UI Gaps:**
- No multi-bet / bet_index display — multi-bet rows show as single bet 1
- No NO_DATA row display — strategies with zero replay rows not shown in catalog

## 9. NO_DATA Strategy Handling

- `no_data_reason` field in DB schema: **NO**
- Catalog shows NO_DATA entries: **NO**
- Strategies with zero replay rows: 5
  - `power_shlc_midfreq`
  - `biglotto_ts3_markov_freq_5bet`
  - `p1_deviation_2bet_539`
  - `biglotto_ts3_acb_4bet`
  - `h6_gate_mk20_ew85`

## 10. Multi-Bet / bet_index Display Readiness

- bet_index column in DB: **YES**
- bet_index returned in API: **NO**
- bet_index displayed in UI: **NO**

**bet_index distribution (DB):**

| bet_index | row_count |
|-----------|-----------|
| 1 | 54302 |
| 2 | 16581 |
| 3 | 15041 |
| 4 | 6000 |
| 5 | 3000 |

**Multi-bet strategies (15):**

| strategy_id | lottery_type | max_bet_index |
|-------------|--------------|---------------|
| daily539_f4cold_5bet | DAILY_539 | 5 |
| power_orthogonal_5bet | POWER_LOTTO | 5 |
| biglotto_ts3_markov_4bet_w30 | BIG_LOTTO | 4 |
| pp3_freqort_4bet | POWER_LOTTO | 4 |
| acb_markov_midfreq_3bet | DAILY_539 | 3 |
| biglotto_echo_aware_3bet | BIG_LOTTO | 3 |
| daily539_f4cold | DAILY_539 | 3 |
| daily539_f4cold_3bet | DAILY_539 | 3 |
| daily539_markov_cold | DAILY_539 | 3 |
| fourier_rhythm_3bet | POWER_LOTTO | 3 |
| midfreq_fourier_mk_3bet | POWER_LOTTO | 3 |
| power_precision_3bet | POWER_LOTTO | 3 |
| biglotto_deviation_2bet | BIG_LOTTO | 2 |
| biglotto_triple_strike | BIG_LOTTO | 2 |
| power_fourier_rhythm_2bet | POWER_LOTTO | 2 |

## 11. Truth Level / Source Display Readiness

- truth_level column in DB: **YES**
- truth_level returned in API: **YES**
- truth_level badge in UI: **YES**

**Truth levels found in DB:**
- `BIGLOTTO_REMAINING_STRATEGIES_BACKFILL_VERIFIED`
- `BIGLOTTO_SINGLE_STRATEGY_BACKFILL_VERIFIED`
- `BIGLOTTO_WAVE3_STRATEGY_BACKFILL_VERIFIED`
- `DAILY539_BACKFILL_VERIFIED`
- `DAILY539_RETIRED_STRATEGY_BACKFILL_VERIFIED`
- `DAILY539_WAVE2_STRATEGY_BACKFILL_VERIFIED`
- `LEGACY_UNVERIFIED`
- `POWERLOTTO_DRAW_EXT_VERIFIED`
- `POWERLOTTO_REMAINING_STRATEGIES_BACKFILL_VERIFIED`
- `POWERLOTTO_SINGLE_STRATEGY_BACKFILL_VERIFIED`
- `POWERLOTTO_WAVE4_STRATEGY_BACKFILL_VERIFIED`
- `POWER_LOTTO_WAVE5_CONTROLLED_APPLY_VERIFIED`
- `POWER_LOTTO_WAVE6_CONTROLLED_APPLY_VERIFIED`
- `TIERB_DRYRUN_VALIDATED`

**Source values found in DB (25):** (sample)
- `P126B_CONTROLLED_APPLY`
- `P126C_CONTROLLED_APPLY`
- `P126D_CONTROLLED_APPLY`
- `P126E_CONTROLLED_APPLY`
- `P126F_CONTROLLED_APPLY`
- `P131_CONTROLLED_APPLY`
- `P132_CONTROLLED_APPLY`
- `P133_CONTROLLED_APPLY`
- `P134_CONTROLLED_APPLY`
- `P138B_LEGACY_REMARK`

## 12. Replay Product Gap Matrix

Total gaps: **9**

| gap_id | area | severity | current_state | expected_state | recommended_task |
|--------|------|----------|--------------|----------------|------------------|
| GAP-001 | catalog | HIGH | 22 strategy IDs exist in DB replay rows but are NOT registered in replay_strateg... | All strategies with replay rows should have lifecycle entry  | P150_REPLAY_CATALOG_LIFECYCLE_COVERAGE |
| GAP-002 | data | CRITICAL | 1 ONLINE/OBSERVATION strategies have zero replay rows: ['h6_gate_mk20_ew85'] | ONLINE and OBSERVATION strategies should have historical rep | P150_REPLAY_API_ALL_STRATEGY_COVERAGE |
| GAP-003 | catalog | MEDIUM | 4 REJECTED strategies have no replay rows (catalog entries only): ['biglotto_ts3... | REJECTED strategies should have NO_DATA entries in catalog w | P150_REPLAY_CATALOG_LIFECYCLE_COVERAGE |
| GAP-004 | api | HIGH | bet_index column not returned in /api/replay/history response | bet_index should be returned so callers can distinguish bets | P150_REPLAY_API_ALL_STRATEGY_COVERAGE |
| GAP-005 | api | MEDIUM | no_data_reason field not returned for strategies with zero replay rows | API should surface a no_data_reason for strategies that exis | P150_REPLAY_API_ALL_STRATEGY_COVERAGE |
| GAP-006 | ui | HIGH | UI has no bet_index or multi-bet display — multi-bet rows (bet_index 2..5) are n... | UI should group or label multi-bet rows by bet_index so user | P150_REPLAY_UI_ALL_STRATEGY_COVERAGE |
| GAP-007 | ui | MEDIUM | UI does not display NO_DATA placeholder rows for strategies with zero replay row... | Strategies registered but with no rows should appear with a  | P150_REPLAY_UI_ALL_STRATEGY_COVERAGE |
| GAP-008 | data | LOW | 2 strategies have LEGACY_UNVERIFIED rows: ['power_orthogonal_5bet', 'power_preci... | LEGACY_UNVERIFIED rows are kept as governed baseline; champi | P150_REPLAY_CATALOG_LIFECYCLE_COVERAGE |
| GAP-009 | data | MEDIUM | 5 strategies have only TIERB_DRYRUN_VALIDATED truth_level rows (not production-v... | TIERB_DRYRUN_VALIDATED rows should be clearly labeled in cat | P150_REPLAY_CATALOG_LIFECYCLE_COVERAGE |

## 13. Recommended Next Task

**`P150_REPLAY_API_ALL_STRATEGY_COVERAGE`**

Rationale: The most critical gaps are strategies in DB without lifecycle registry entries and missing bet_index / NO_DATA handling in the API and UI. The next task should address all-strategy catalog coverage in the registry, add bet_index to the API history response, and add NO_DATA entries for registry-only strategies.

## 14. Explicit Non-Actions

P149 is audit-only. The following actions were explicitly NOT taken:

- **db_write_in_p149**: False ← confirmed NOT executed
- **controlled_apply_executed_in_p149**: False ← confirmed NOT executed
- **replay_rows_inserted_in_p149**: 0 ← confirmed NOT executed
- **replay_rows_updated_in_p149**: 0 ← confirmed NOT executed
- **replay_rows_deleted_in_p149**: 0 ← confirmed NOT executed
- **champion_promotion_executed_in_p149**: False ← confirmed NOT executed
- **registry_update_executed_in_p149**: False ← confirmed NOT executed
- **live_api_called**: False ← confirmed NOT executed
- **scheduler_installed**: False ← confirmed NOT executed
- **four_star_executed**: False ← confirmed NOT executed
- **p108_executed**: False ← confirmed NOT executed
- **p117_executed**: False ← confirmed NOT executed
- **p118_executed**: False ← confirmed NOT executed

## 15. Final Classification

```
P149_REPLAY_PRODUCT_COVERAGE_AUDIT_READY
```

This task is complete. No DB write, no controlled_apply, no champion promotion.
