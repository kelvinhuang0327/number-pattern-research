# P127 — Adapter Build Specs for Remaining Multi-Bet Strategies

**Generated:** 2026-05-28T11:44:42.684688+00:00  
**Task ID:** P127  
**Classification:** `P127_ADAPTER_BUILD_SPECS_READY`  
**Worktree:** `zen-gates-ff6802`  
**Branch:** `claude/zen-gates-ff6802`  

---

## 1. Executive Summary

P127 delivers adapter build specifications for the **12 remaining multi-bet strategies** that are classified as `adapter_build` in the P125 gap plan. This is a **spec-only phase** — no DB writes, no controlled_apply, no replay rows inserted.

- Production DB replay rows: **72462** (unchanged)
- P126 Tier-B wave: **CLOSED** (P126G confirmed)
- Adapter specs produced: **12**
- Apply gate status: **CLOSED** — pending adapter implementation + per-strategy authorization

---

## 2. P126G Closure Recap

| Field | Value |
|---|---|
| P126G Classification | `P126G_ALL_TIER_B_MULTI_BET_APPLY_CLOSED` |
| Applied Candidates | 5 / 5 |
| Total Inserted Rows (P126B→F) | 18,000 |
| Baseline Before P126 Apply | 54,462 |
| Final DB Rows | 72,462 |
| Drift Guard | REPLAY_LIFECYCLE_DRIFT_GUARD_PASS |

---

## 3. Why P127 Is Adapter Spec Only

The 12 remaining strategies have only bet_index=1 rows in the DB (or in two cases, orphaned partial rows). They cannot be applied in a controlled_apply wave until:

1. A `get_all_bets()` adapter is implemented for each strategy.
2. The adapter passes all 8 unit tests (output count, no future data, determinism,    valid range, no intra-bet duplicates, no inter-bet duplicates, historical context, provenance).
3. A dry_run confirms zero duplicate rows in the DB.
4. Per-strategy apply authorization is granted (following P126A pattern).

P127 produces the specifications. Implementation is the next phase.

---

## 4. Remaining Adapter-Build Strategy Matrix

| # | strategy_id | lottery_type | target_bets | current_rows | bet_index_dist | quality |
|---|---|---|---|---|---|---|
| 1 | `midfreq_acb_2bet` | DAILY_539 | 2 | 1500 | b1=1500 | watchlist |
| 2 | `midfreq_fourier_2bet` | DAILY_539 | 2 | 1500 | b1=1500 | watchlist |
| 3 | `zonal_entropy_2bet` | POWER_LOTTO | 2 | 1500 | b1=1500 | fallback_equivalent |
| 4 | `cold_complement_2bet` | POWER_LOTTO | 2 | 1500 | b1=1500 | fallback_equivalent |
| 5 | `midfreq_fourier_2bet` | POWER_LOTTO | 2 | 1500 | b1=1500 | watchlist |
| 6 | `fourier30_markov30_2bet` | POWER_LOTTO | 2 | 1501 | b1=1501 | watchlist |
| 7 | `acb_markov_midfreq_3bet` | DAILY_539 | 3 | 1500 | b1=1500 | watchlist |
| 8 | `midfreq_fourier_mk_3bet` | POWER_LOTTO | 3 | 1500 | b1=1500 | prediction_helpful |
| 9 | `fourier_rhythm_3bet` | POWER_LOTTO | 3 | 1501 | b1=1501 | watchlist |
| 10 | `power_precision_3bet` | POWER_LOTTO | 3 | 1570 | b1=1550, b2=20 | watchlist |
| 11 | `pp3_freqort_4bet` | POWER_LOTTO | 4 | 1500 | b1=1500 | prediction_helpful |
| 12 | `power_orthogonal_5bet` | POWER_LOTTO | 5 | 1570 | b1=1550, b2=20 | watchlist |

---

## 5. Proposed `get_all_bets()` Contract

```python
def get_all_bets_<strategy>(draw_context: dict) -> list[list[int]]:
    """
    Returns N bet combinations for a single draw, ordered by descending
    model confidence. Each sub-list contains the predicted numbers for
    one bet (e.g. 6 numbers for POWER_LOTTO, 5 for DAILY_539).

    Args:
        draw_context: dict with keys:
            - 'history_cutoff_draw': str  (draw ID, no future data beyond this)
            - 'historical_draws': list    (sorted ascending by draw date)
            - 'lottery_type': str         ('POWER_LOTTO' | 'DAILY_539')

    Returns:
        List of N sub-lists. Sub-list[0] = bet_index 1 (highest confidence).
        Deterministic: same draw_context → same output.
        No future data permitted beyond history_cutoff_draw.
        No fabricated numbers.
    """
```

**Deterministic ordering rule:**  
Bets ordered by descending model confidence score.  
Ties broken by ascending number sum, then lexicographic sort.  
Seed = SHA256(strategy_id + target_draw + draw_context hash)[:8].

---

## 6. Per-Strategy Implementation Specs

### 1. `midfreq_acb_2bet` (DAILY_539)

| Field | Value |
|---|---|
| Algorithm Family | mid_frequency |
| Target Bet Count | 2 |
| Current DB Rows | 1500 |
| Current Distribution | bet_index=1: 1500 rows |
| Missing Component | `midfreq_multi_bet_adapter` |
| Adapter Function | `def get_all_bets_midfreq_acb(draw_context: dict) -> list[list[int]]` |
| Output | List of 2 sub-lists, each 2 integers |
| Lottery Range | 1–39 |
| Must Not Fabricate | `True` |
| Historical Data Only | `True` |
| Risk Level | medium |
| Quality Label | watchlist |
| P125 Rank Score | 39 |
| DB Write in P127 | `False` |
| Apply Auth Required Later | `True` |

**Duplicate guard:** `UNIQUE(lottery_type, target_draw, strategy_id, bet_index)`  
Pre-insert check: `SELECT COUNT(*) = 0 WHERE bet_index IN (2..2)`  

**Provenance:** hash = SHA256(strategy_id + target_draw + bet_index + predicted_numbers)  

**Tests required:**
- `test_midfreq_acb_2bet_adapter_output_count_eq_2`
- `test_midfreq_acb_2bet_no_future_data_in_draw_context`
- `test_midfreq_acb_2bet_deterministic_output_same_seed`
- `test_midfreq_acb_2bet_all_numbers_in_valid_range`
- `test_midfreq_acb_2bet_no_duplicate_numbers_within_bet`
- `test_midfreq_acb_2bet_no_duplicate_bets_across_outputs`
- `test_midfreq_acb_2bet_integration_with_historical_draw_context`
- `test_midfreq_acb_2bet_provenance_hash_matches_inputs`

### 2. `midfreq_fourier_2bet` (DAILY_539)

| Field | Value |
|---|---|
| Algorithm Family | fourier |
| Target Bet Count | 2 |
| Current DB Rows | 1500 |
| Current Distribution | bet_index=1: 1500 rows |
| Missing Component | `fourier_multi_bet_adapter` |
| Adapter Function | `def get_all_bets_fourier_d539(draw_context: dict) -> list[list[int]]` |
| Output | List of 2 sub-lists, each 2 integers |
| Lottery Range | 1–39 |
| Must Not Fabricate | `True` |
| Historical Data Only | `True` |
| Risk Level | medium |
| Quality Label | watchlist |
| P125 Rank Score | 39 |
| DB Write in P127 | `False` |
| Apply Auth Required Later | `True` |

**Duplicate guard:** `UNIQUE(lottery_type, target_draw, strategy_id, bet_index)`  
Pre-insert check: `SELECT COUNT(*) = 0 WHERE bet_index IN (2..2)`  

**Provenance:** hash = SHA256(strategy_id + target_draw + bet_index + predicted_numbers)  

**Tests required:**
- `test_midfreq_fourier_2bet_adapter_output_count_eq_2`
- `test_midfreq_fourier_2bet_no_future_data_in_draw_context`
- `test_midfreq_fourier_2bet_deterministic_output_same_seed`
- `test_midfreq_fourier_2bet_all_numbers_in_valid_range`
- `test_midfreq_fourier_2bet_no_duplicate_numbers_within_bet`
- `test_midfreq_fourier_2bet_no_duplicate_bets_across_outputs`
- `test_midfreq_fourier_2bet_integration_with_historical_draw_context`
- `test_midfreq_fourier_2bet_provenance_hash_matches_inputs`

### 3. `zonal_entropy_2bet` (POWER_LOTTO)

| Field | Value |
|---|---|
| Algorithm Family | zonal_entropy |
| Target Bet Count | 2 |
| Current DB Rows | 1500 |
| Current Distribution | bet_index=1: 1500 rows |
| Missing Component | `zonal_multi_bet_adapter` |
| Adapter Function | `def get_all_bets_zonal_entropy(draw_context: dict) -> list[list[int]]` |
| Output | List of 2 sub-lists, each 2 integers |
| Lottery Range | 1–39 (special 1–10) |
| Must Not Fabricate | `True` |
| Historical Data Only | `True` |
| Risk Level | medium |
| Quality Label | fallback_equivalent |
| P125 Rank Score | 39 |
| DB Write in P127 | `False` |
| Apply Auth Required Later | `True` |

**Duplicate guard:** `UNIQUE(lottery_type, target_draw, strategy_id, bet_index)`  
Pre-insert check: `SELECT COUNT(*) = 0 WHERE bet_index IN (2..2)`  

**Provenance:** hash = SHA256(strategy_id + target_draw + bet_index + predicted_numbers)  

**Tests required:**
- `test_zonal_entropy_2bet_adapter_output_count_eq_2`
- `test_zonal_entropy_2bet_no_future_data_in_draw_context`
- `test_zonal_entropy_2bet_deterministic_output_same_seed`
- `test_zonal_entropy_2bet_all_numbers_in_valid_range`
- `test_zonal_entropy_2bet_no_duplicate_numbers_within_bet`
- `test_zonal_entropy_2bet_no_duplicate_bets_across_outputs`
- `test_zonal_entropy_2bet_integration_with_historical_draw_context`
- `test_zonal_entropy_2bet_provenance_hash_matches_inputs`

### 4. `cold_complement_2bet` (POWER_LOTTO)

| Field | Value |
|---|---|
| Algorithm Family | cold_number_complement |
| Target Bet Count | 2 |
| Current DB Rows | 1500 |
| Current Distribution | bet_index=1: 1500 rows |
| Missing Component | `cold_complement_multi_bet_adapter` |
| Adapter Function | `def get_all_bets_cold_complement(draw_context: dict) -> list[list[int]]` |
| Output | List of 2 sub-lists, each 2 integers |
| Lottery Range | 1–39 (special 1–10) |
| Must Not Fabricate | `True` |
| Historical Data Only | `True` |
| Risk Level | medium |
| Quality Label | fallback_equivalent |
| P125 Rank Score | 39 |
| DB Write in P127 | `False` |
| Apply Auth Required Later | `True` |

**Duplicate guard:** `UNIQUE(lottery_type, target_draw, strategy_id, bet_index)`  
Pre-insert check: `SELECT COUNT(*) = 0 WHERE bet_index IN (2..2)`  

**Provenance:** hash = SHA256(strategy_id + target_draw + bet_index + predicted_numbers)  

**Tests required:**
- `test_cold_complement_2bet_adapter_output_count_eq_2`
- `test_cold_complement_2bet_no_future_data_in_draw_context`
- `test_cold_complement_2bet_deterministic_output_same_seed`
- `test_cold_complement_2bet_all_numbers_in_valid_range`
- `test_cold_complement_2bet_no_duplicate_numbers_within_bet`
- `test_cold_complement_2bet_no_duplicate_bets_across_outputs`
- `test_cold_complement_2bet_integration_with_historical_draw_context`
- `test_cold_complement_2bet_provenance_hash_matches_inputs`

### 5. `midfreq_fourier_2bet` (POWER_LOTTO)

| Field | Value |
|---|---|
| Algorithm Family | fourier |
| Target Bet Count | 2 |
| Current DB Rows | 1500 |
| Current Distribution | bet_index=1: 1500 rows |
| Missing Component | `fourier_multi_bet_adapter` |
| Adapter Function | `def get_all_bets_fourier_power(draw_context: dict) -> list[list[int]]` |
| Output | List of 2 sub-lists, each 2 integers |
| Lottery Range | 1–39 (special 1–10) |
| Must Not Fabricate | `True` |
| Historical Data Only | `True` |
| Risk Level | medium |
| Quality Label | watchlist |
| P125 Rank Score | 29 |
| DB Write in P127 | `False` |
| Apply Auth Required Later | `True` |

**Duplicate guard:** `UNIQUE(lottery_type, target_draw, strategy_id, bet_index)`  
Pre-insert check: `SELECT COUNT(*) = 0 WHERE bet_index IN (2..2)`  

**Provenance:** hash = SHA256(strategy_id + target_draw + bet_index + predicted_numbers)  

**Tests required:**
- `test_midfreq_fourier_2bet_adapter_output_count_eq_2`
- `test_midfreq_fourier_2bet_no_future_data_in_draw_context`
- `test_midfreq_fourier_2bet_deterministic_output_same_seed`
- `test_midfreq_fourier_2bet_all_numbers_in_valid_range`
- `test_midfreq_fourier_2bet_no_duplicate_numbers_within_bet`
- `test_midfreq_fourier_2bet_no_duplicate_bets_across_outputs`
- `test_midfreq_fourier_2bet_integration_with_historical_draw_context`
- `test_midfreq_fourier_2bet_provenance_hash_matches_inputs`

### 6. `fourier30_markov30_2bet` (POWER_LOTTO)

| Field | Value |
|---|---|
| Algorithm Family | fourier_markov_composite |
| Target Bet Count | 2 |
| Current DB Rows | 1501 |
| Current Distribution | bet_index=1: 1501 rows |
| Missing Component | `fourier_markov_multi_bet_adapter` |
| Adapter Function | `def get_all_bets_fourier30_markov30(draw_context: dict) -> list[list[int]]` |
| Output | List of 2 sub-lists, each 2 integers |
| Lottery Range | 1–39 (special 1–10) |
| Must Not Fabricate | `True` |
| Historical Data Only | `True` |
| Risk Level | medium |
| Quality Label | watchlist |
| P125 Rank Score | 29 |
| DB Write in P127 | `False` |
| Apply Auth Required Later | `True` |
| ⚠️ Notes | Non-standard row count: 1501 (expected 1500 for bet_index=1 only) |

**Duplicate guard:** `UNIQUE(lottery_type, target_draw, strategy_id, bet_index)`  
Pre-insert check: `SELECT COUNT(*) = 0 WHERE bet_index IN (2..2)`  

**Provenance:** hash = SHA256(strategy_id + target_draw + bet_index + predicted_numbers)  

**Tests required:**
- `test_fourier30_markov30_2bet_adapter_output_count_eq_2`
- `test_fourier30_markov30_2bet_no_future_data_in_draw_context`
- `test_fourier30_markov30_2bet_deterministic_output_same_seed`
- `test_fourier30_markov30_2bet_all_numbers_in_valid_range`
- `test_fourier30_markov30_2bet_no_duplicate_numbers_within_bet`
- `test_fourier30_markov30_2bet_no_duplicate_bets_across_outputs`
- `test_fourier30_markov30_2bet_integration_with_historical_draw_context`
- `test_fourier30_markov30_2bet_provenance_hash_matches_inputs`

### 7. `acb_markov_midfreq_3bet` (DAILY_539)

| Field | Value |
|---|---|
| Algorithm Family | markov_chain |
| Target Bet Count | 3 |
| Current DB Rows | 1500 |
| Current Distribution | bet_index=1: 1500 rows |
| Missing Component | `markov_multi_bet_adapter` |
| Adapter Function | `def get_all_bets_acb_markov(draw_context: dict) -> list[list[int]]` |
| Output | List of 3 sub-lists, each 3 integers |
| Lottery Range | 1–39 |
| Must Not Fabricate | `True` |
| Historical Data Only | `True` |
| Risk Level | medium |
| Quality Label | watchlist |
| P125 Rank Score | 41 |
| DB Write in P127 | `False` |
| Apply Auth Required Later | `True` |

**Duplicate guard:** `UNIQUE(lottery_type, target_draw, strategy_id, bet_index)`  
Pre-insert check: `SELECT COUNT(*) = 0 WHERE bet_index IN (2..3)`  

**Provenance:** hash = SHA256(strategy_id + target_draw + bet_index + predicted_numbers)  

**Tests required:**
- `test_acb_markov_midfreq_3bet_adapter_output_count_eq_3`
- `test_acb_markov_midfreq_3bet_no_future_data_in_draw_context`
- `test_acb_markov_midfreq_3bet_deterministic_output_same_seed`
- `test_acb_markov_midfreq_3bet_all_numbers_in_valid_range`
- `test_acb_markov_midfreq_3bet_no_duplicate_numbers_within_bet`
- `test_acb_markov_midfreq_3bet_no_duplicate_bets_across_outputs`
- `test_acb_markov_midfreq_3bet_integration_with_historical_draw_context`
- `test_acb_markov_midfreq_3bet_provenance_hash_matches_inputs`

### 8. `midfreq_fourier_mk_3bet` (POWER_LOTTO)

| Field | Value |
|---|---|
| Algorithm Family | fourier_markov |
| Target Bet Count | 3 |
| Current DB Rows | 1500 |
| Current Distribution | bet_index=1: 1500 rows |
| Missing Component | `fourier_multi_bet_adapter` |
| Adapter Function | `def get_all_bets_fourier_mk(draw_context: dict) -> list[list[int]]` |
| Output | List of 3 sub-lists, each 3 integers |
| Lottery Range | 1–39 (special 1–10) |
| Must Not Fabricate | `True` |
| Historical Data Only | `True` |
| Risk Level | medium |
| Quality Label | prediction_helpful |
| P125 Rank Score | 51 |
| DB Write in P127 | `False` |
| Apply Auth Required Later | `True` |

**Duplicate guard:** `UNIQUE(lottery_type, target_draw, strategy_id, bet_index)`  
Pre-insert check: `SELECT COUNT(*) = 0 WHERE bet_index IN (2..3)`  

**Provenance:** hash = SHA256(strategy_id + target_draw + bet_index + predicted_numbers)  

**Tests required:**
- `test_midfreq_fourier_mk_3bet_adapter_output_count_eq_3`
- `test_midfreq_fourier_mk_3bet_no_future_data_in_draw_context`
- `test_midfreq_fourier_mk_3bet_deterministic_output_same_seed`
- `test_midfreq_fourier_mk_3bet_all_numbers_in_valid_range`
- `test_midfreq_fourier_mk_3bet_no_duplicate_numbers_within_bet`
- `test_midfreq_fourier_mk_3bet_no_duplicate_bets_across_outputs`
- `test_midfreq_fourier_mk_3bet_integration_with_historical_draw_context`
- `test_midfreq_fourier_mk_3bet_provenance_hash_matches_inputs`

### 9. `fourier_rhythm_3bet` (POWER_LOTTO)

| Field | Value |
|---|---|
| Algorithm Family | fourier_rhythm |
| Target Bet Count | 3 |
| Current DB Rows | 1501 |
| Current Distribution | bet_index=1: 1501 rows |
| Missing Component | `fourier_multi_bet_adapter` |
| Adapter Function | `def get_all_bets_fourier_rhythm(draw_context: dict) -> list[list[int]]` |
| Output | List of 3 sub-lists, each 3 integers |
| Lottery Range | 1–39 (special 1–10) |
| Must Not Fabricate | `True` |
| Historical Data Only | `True` |
| Risk Level | medium |
| Quality Label | watchlist |
| P125 Rank Score | 31 |
| DB Write in P127 | `False` |
| Apply Auth Required Later | `True` |
| ⚠️ Notes | Non-standard row count: 1501 (expected 1500 for bet_index=1 only) |

**Duplicate guard:** `UNIQUE(lottery_type, target_draw, strategy_id, bet_index)`  
Pre-insert check: `SELECT COUNT(*) = 0 WHERE bet_index IN (2..3)`  

**Provenance:** hash = SHA256(strategy_id + target_draw + bet_index + predicted_numbers)  

**Tests required:**
- `test_fourier_rhythm_3bet_adapter_output_count_eq_3`
- `test_fourier_rhythm_3bet_no_future_data_in_draw_context`
- `test_fourier_rhythm_3bet_deterministic_output_same_seed`
- `test_fourier_rhythm_3bet_all_numbers_in_valid_range`
- `test_fourier_rhythm_3bet_no_duplicate_numbers_within_bet`
- `test_fourier_rhythm_3bet_no_duplicate_bets_across_outputs`
- `test_fourier_rhythm_3bet_integration_with_historical_draw_context`
- `test_fourier_rhythm_3bet_provenance_hash_matches_inputs`

### 10. `power_precision_3bet` (POWER_LOTTO)

| Field | Value |
|---|---|
| Algorithm Family | precision_scoring |
| Target Bet Count | 3 |
| Current DB Rows | 1570 |
| Current Distribution | bet_index=1: 1550 rows, bet_index=2: 20 rows |
| Missing Component | `precision_multi_bet_adapter` |
| Adapter Function | `def get_all_bets_power_precision(draw_context: dict) -> list[list[int]]` |
| Output | List of 3 sub-lists, each 3 integers |
| Lottery Range | 1–39 (special 1–10) |
| Must Not Fabricate | `True` |
| Historical Data Only | `True` |
| Risk Level | medium |
| Quality Label | watchlist |
| P125 Rank Score | 31 |
| DB Write in P127 | `False` |
| Apply Auth Required Later | `True` |
| ⚠️ Notes | Non-standard row count: 1570 (expected 1500 for bet_index=1 only); Partial bet_index rows already present: bet_index [2] (20 rows) — may indicate prior incomplete apply |

**Duplicate guard:** `UNIQUE(lottery_type, target_draw, strategy_id, bet_index)`  
Pre-insert check: `SELECT COUNT(*) = 0 WHERE bet_index IN (2..3)`  

**Provenance:** hash = SHA256(strategy_id + target_draw + bet_index + predicted_numbers)  

**Tests required:**
- `test_power_precision_3bet_adapter_output_count_eq_3`
- `test_power_precision_3bet_no_future_data_in_draw_context`
- `test_power_precision_3bet_deterministic_output_same_seed`
- `test_power_precision_3bet_all_numbers_in_valid_range`
- `test_power_precision_3bet_no_duplicate_numbers_within_bet`
- `test_power_precision_3bet_no_duplicate_bets_across_outputs`
- `test_power_precision_3bet_integration_with_historical_draw_context`
- `test_power_precision_3bet_provenance_hash_matches_inputs`

### 11. `pp3_freqort_4bet` (POWER_LOTTO)

| Field | Value |
|---|---|
| Algorithm Family | frequency_sort |
| Target Bet Count | 4 |
| Current DB Rows | 1500 |
| Current Distribution | bet_index=1: 1500 rows |
| Missing Component | `pp3_freqort_multi_bet_adapter` |
| Adapter Function | `def get_all_bets_pp3_freqort(draw_context: dict) -> list[list[int]]` |
| Output | List of 4 sub-lists, each 4 integers |
| Lottery Range | 1–39 (special 1–10) |
| Must Not Fabricate | `True` |
| Historical Data Only | `True` |
| Risk Level | medium |
| Quality Label | prediction_helpful |
| P125 Rank Score | 53 |
| DB Write in P127 | `False` |
| Apply Auth Required Later | `True` |

**Duplicate guard:** `UNIQUE(lottery_type, target_draw, strategy_id, bet_index)`  
Pre-insert check: `SELECT COUNT(*) = 0 WHERE bet_index IN (2..4)`  

**Provenance:** hash = SHA256(strategy_id + target_draw + bet_index + predicted_numbers)  

**Tests required:**
- `test_pp3_freqort_4bet_adapter_output_count_eq_4`
- `test_pp3_freqort_4bet_no_future_data_in_draw_context`
- `test_pp3_freqort_4bet_deterministic_output_same_seed`
- `test_pp3_freqort_4bet_all_numbers_in_valid_range`
- `test_pp3_freqort_4bet_no_duplicate_numbers_within_bet`
- `test_pp3_freqort_4bet_no_duplicate_bets_across_outputs`
- `test_pp3_freqort_4bet_integration_with_historical_draw_context`
- `test_pp3_freqort_4bet_provenance_hash_matches_inputs`

### 12. `power_orthogonal_5bet` (POWER_LOTTO)

| Field | Value |
|---|---|
| Algorithm Family | orthogonal_diversification |
| Target Bet Count | 5 |
| Current DB Rows | 1570 |
| Current Distribution | bet_index=1: 1550 rows, bet_index=2: 20 rows |
| Missing Component | `orthogonal_multi_bet_adapter` |
| Adapter Function | `def get_all_bets_power_orthogonal(draw_context: dict) -> list[list[int]]` |
| Output | List of 5 sub-lists, each 5 integers |
| Lottery Range | 1–39 (special 1–10) |
| Must Not Fabricate | `True` |
| Historical Data Only | `True` |
| Risk Level | medium |
| Quality Label | watchlist |
| P125 Rank Score | 35 |
| DB Write in P127 | `False` |
| Apply Auth Required Later | `True` |
| ⚠️ Notes | Non-standard row count: 1570 (expected 1500 for bet_index=1 only); Partial bet_index rows already present: bet_index [2] (20 rows) — may indicate prior incomplete apply |

**Duplicate guard:** `UNIQUE(lottery_type, target_draw, strategy_id, bet_index)`  
Pre-insert check: `SELECT COUNT(*) = 0 WHERE bet_index IN (2..5)`  

**Provenance:** hash = SHA256(strategy_id + target_draw + bet_index + predicted_numbers)  

**Tests required:**
- `test_power_orthogonal_5bet_adapter_output_count_eq_5`
- `test_power_orthogonal_5bet_no_future_data_in_draw_context`
- `test_power_orthogonal_5bet_deterministic_output_same_seed`
- `test_power_orthogonal_5bet_all_numbers_in_valid_range`
- `test_power_orthogonal_5bet_no_duplicate_numbers_within_bet`
- `test_power_orthogonal_5bet_no_duplicate_bets_across_outputs`
- `test_power_orthogonal_5bet_integration_with_historical_draw_context`
- `test_power_orthogonal_5bet_provenance_hash_matches_inputs`

---

## 7. Recommended Implementation Order

Priority is: lower bet_count → lower DB risk → easier testability → higher product value.

| Priority | strategy_id | lottery_type | bets | rationale |
|---|---|---|---|---|
| 1 | `midfreq_acb_2bet` | DAILY_539 | 2 | bet_count=2, quality=watchlist, rank_score=39 |
| 2 | `midfreq_fourier_2bet` | DAILY_539 | 2 | bet_count=2, quality=watchlist, rank_score=39 |
| 3 | `zonal_entropy_2bet` | POWER_LOTTO | 2 | bet_count=2, quality=fallback_equivalent, rank_score=39 |
| 4 | `cold_complement_2bet` | POWER_LOTTO | 2 | bet_count=2, quality=fallback_equivalent, rank_score=39 |
| 5 | `midfreq_fourier_2bet` | POWER_LOTTO | 2 | bet_count=2, quality=watchlist, rank_score=29 |
| 6 | `fourier30_markov30_2bet` | POWER_LOTTO | 2 | bet_count=2, quality=watchlist, rank_score=29 |
| 7 | `acb_markov_midfreq_3bet` | DAILY_539 | 3 | bet_count=3, quality=watchlist, rank_score=41 |
| 8 | `midfreq_fourier_mk_3bet` | POWER_LOTTO | 3 | bet_count=3, quality=prediction_helpful, rank_score=51 |
| 9 | `fourier_rhythm_3bet` | POWER_LOTTO | 3 | bet_count=3, quality=watchlist, rank_score=31 |
| 10 | `power_precision_3bet` | POWER_LOTTO | 3 | bet_count=3, quality=watchlist, rank_score=31 |
| 11 | `pp3_freqort_4bet` | POWER_LOTTO | 4 | bet_count=4, quality=prediction_helpful, rank_score=53 |
| 12 | `power_orthogonal_5bet` | POWER_LOTTO | 5 | bet_count=5, quality=watchlist, rank_score=35 |

---

## 8. Test Plan

Each adapter must pass 8 tests before apply authorization:

| # | Test | Assertion |
|---|---|---|
| 1 | output_count | len(get_all_bets(...)) == target_bet_count |
| 2 | no_future_data | draw_context contains no data past history_cutoff_draw |
| 3 | deterministic | same inputs → identical outputs across 100 runs |
| 4 | valid_range | all numbers within lottery type range |
| 5 | no_intra_bet_dup | no repeated numbers within a single bet |
| 6 | no_inter_bet_dup | no identical bets across output list |
| 7 | historical_context | adapter runs correctly on real historical draw data |
| 8 | provenance_hash | SHA256(inputs) matches stored provenance_hash |

**Regression gate:** All 589 existing tests must continue to pass.

---

## 9. Apply Gate Rules After Implementation

After adapter implementation is complete for a strategy:

1. All 8 unit tests must pass.
2. Dry-run must confirm 0 duplicate rows (abort on conflict).
3. Per-strategy authorization phrase must be issued (following P126A pattern).
4. Drift guard must pass at expected count before and after.
5. Only then may controlled_apply be executed.

**Audit RSR-6 first:** `power_orthogonal_5bet` and `power_precision_3bet` have orphan bet_index=2 rows (20 rows each). These must be audited and resolved before apply.

---

## 10. Explicit Non-Actions

| Non-Action | Confirmed |
|---|---|
| No DB rows inserted | ✅ |
| No controlled_apply executed | ✅ |
| No scheduler / cron / launchd installed | ✅ |
| No 4_STAR action | ✅ |
| No P108 / P117 / P118 execution | ✅ |
| No strategy promotion / lifecycle / champion mutation | ✅ |
| No registry mutation | ✅ |
| No P126B–P126F data touched | ✅ |
| Production DB rows unchanged: 72,462 | ✅ |

---

## 11. Remaining Risks

| Risk ID | Description | Status |
|---|---|---|
| RSR-4 | API/UI consumers need WHERE bet_index = 1 filter | open |
| RSR-5 | Adapter implementations not yet built for 12 strategies | open — P127 delivers specs; implementation is next |
| RSR-6 | power_orthogonal_5bet and power_precision_3bet have orphan bet_index=2 rows (20 rows each) from prior partial apply — must audit before P128 apply wave | open — deduplication audit required |
| RSR-7 | fourier_rhythm_3bet and fourier30_markov30_2bet have 1501 rows (1 extra row each) — minor anomaly, monitor | open — low priority |
| RSR-8 | daily539_f4cold_5bet PROVISIONAL — requires stat validation before promotion | open |
| BLOCKED-P108 | P108 blocked — insufficient Special3 draws | blocked |
| BLOCKED-P117 | P117 POWER_LOTTO OOS blocked — insufficient draws | blocked |

---

## 12. Recommended Next Task

**P128_APPLY_WAVE_2** — Implement get_all_bets() adapters for the 12 remaining strategies following the P127 spec matrix. Start with 2-bet strategies (priority 1-6). Each adapter must pass unit tests before controlled_apply authorization is granted. Audit RSR-6 (orphan bet_index=2 rows) before any apply for power_orthogonal_5bet and power_precision_3bet.

**Prerequisite gate:** Adapter implementation + unit tests pass → per-strategy apply authorization

---

## 13. Final Classification

```text
P127_ADAPTER_BUILD_SPECS_READY
```

Final roadmap marker:

```text
CTO_ROADMAP_UPDATED_AFTER_P127_ADAPTER_BUILD_SPECS_20260528
```
