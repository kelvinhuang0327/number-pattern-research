# P124 Multi-Bet Replay Truth Model + Coverage Matrix

**Generated:** 2026-05-28T03:00:02.622774+00:00  
**Task ID:** P124  
**Classification:** P124_MULTI_BET_TRUTH_AND_COVERAGE_MATRIX_READY

---

## Executive Summary

**Key finding:** All 36 implemented strategy×lottery pairs store exactly **1 predicted_numbers list per row**. Zero strategies currently achieve `native_multi_bet` storage.

Of 36 strategy×lottery pairs in the matrix:
- 12 are rejected (expansion forbidden)
- 19 multi-bet strategies use `first_bet_only_fallback`
- 5 have Tier-B adapters ready for `controlled_apply`
- 12 require new adapter builds

**CEO mandate status:** Historical replay of all implemented strategies across all lottery types and 1-5 bet counts cannot be achieved without first resolving the `first_bet_only_fallback` gap for multi-bet strategies.

---

## DB Snapshot (Read-Only Pre-Flight)

| Key | Value |
|-----|-------|
| strategy_prediction_replays | 54462 |
| 3_STAR draws | 4179 (max 115000106) |
| 4_STAR draws | 2922 (max 115000103) |
| POWER_LOTTO draws | 1913 (max 115000041) |
| BIG_LOTTO draws | 22235 (max 115000055) |
| DAILY_539 draws | 5865 (max 115000121) |

---

## Truth Model

### Storage Convention (Current)

- **One replay row per strategy per draw** is the dominant convention.
- `predicted_numbers` stores a **single list** of ball numbers (one bet) per row.
- All 36 strategy×lottery_type pairs follow this convention as of P94.
- **No strategy currently achieves `native_multi_bet` storage.**

### POWER_LOTTO Special Number Semantics

- `predicted_special` field stores the bonus ball (1-8).
- Some strategies populate it (`pp3_freqort_4bet`, `fourier30_markov30_2bet`).
- Others leave it NULL (`fourier_rhythm_3bet`, `power_precision_3bet`, `power_orthogonal_5bet`).
- Replay scoring must handle NULL `predicted_special` gracefully.

### Native Multi-Bet Requirement

For a strategy to qualify as `native_multi_bet`:
1. Adapter must expose all N bets (e.g. `get_all_bets()` method), **AND**
2. Replay storage must record each of the N bets distinguishably
   (e.g. separate rows per bet, or a JSON array of N sublists).

### Label Definitions

| Label | Meaning |
|-------|---------|
| `native_multi_bet` | Strategy has an adapter that natively produces N bets for the specified bet_count, AND replay rows e... |
| `first_bet_only_fallback` | Strategy is named or marketed as N-bet, but current replay rows store only bet-1. The remaining bets... |
| `adapter_missing` | Strategy is implemented but no adapter currently produces replay rows for this bet_count. |
| `already_covered` | This bet_count is the strategy's native bet count and replay rows are present and honest. |
| `unsupported` | Strategy logically cannot produce this bet_count (e.g. a 2-bet strategy cannot expand to 5-bet witho... |
| `rejected` | Strategy was rejected by prior governance and must not be expanded. |
| `retired` | Strategy was retired; recorded by id only, not expanded to 1-5 bet columns. |
| `source_unknown` | Strategy or lottery is currently source_unknown (e.g. 4_STAR); analysis is forbidden. |
| `fabrication_prohibited` | Producing rows for this bet_count would require fabricated bets. This label MUST NOT be promoted to ... |

---

## Coverage Matrix — DAILY_539

| strategy_id | native | adapter | bet1 | bet2 | bet3 | bet4 | bet5 | rows | quality | next_action |
|-------------|--------|---------|------|------|------|------|------|------|---------|-------------|
| acb_1bet | 1 | missing | already_covered | unsupported | unsupported | unsupported | unsupported | 1500 | watchlist | no_action |
| acb_markov_midfreq | 1 | missing | already_covered | unsupported | unsupported | unsupported | unsupported | 1500 | fallback_equivalent | no_action |
| acb_single_539 | 1 | rejected | rejected | rejected | rejected | rejected | rejected | 1500 | coverage_only | no_action |
| acb_markov_midfreq_3bet | 3 | missing | first_bet_only_fallback | first_bet_only_fallback | first_bet_only_fallback | unsupported | unsupported | 1500 | watchlist | adapter_build |
| 539_3bet_orthogonal | 3 | rejected | rejected | rejected | rejected | rejected | rejected | 1500 | coverage_only | no_action |
| daily539_f4cold | 1 | missing | already_covered | unsupported | unsupported | unsupported | unsupported | 1590 | watchlist | no_action |
| p0b_539_3bet_f_cold_fmid | 3 | rejected | rejected | rejected | rejected | rejected | rejected | 1500 | coverage_only | no_action |
| p0c_539_3bet_f_cold_x2 | 3 | rejected | rejected | rejected | rejected | rejected | rejected | 1500 | coverage_only | no_action |
| markov_1bet_539 | 1 | rejected | rejected | rejected | rejected | rejected | rejected | 1500 | coverage_only | no_action |
| daily539_markov_cold | 1 | missing | already_covered | unsupported | unsupported | unsupported | unsupported | 1590 | fallback_equivalent | no_action |
| zone_gap_3bet_539 | 3 | rejected | rejected | rejected | rejected | rejected | rejected | 1500 | coverage_only | no_action |
| midfreq_acb_2bet | 2 | missing | first_bet_only_fallback | first_bet_only_fallback | unsupported | unsupported | unsupported | 1500 | watchlist | adapter_build |
| midfreq_fourier_2bet | 2 | missing | first_bet_only_fallback | first_bet_only_fallback | unsupported | unsupported | unsupported | 1500 | watchlist | adapter_build |
| daily539_f4cold_3bet | 3 | available | first_bet_only_fallback | first_bet_only_fallback | first_bet_only_fallback | unsupported | unsupported | 1500 | watchlist | controlled_apply |
| daily539_f4cold_5bet | 5 | available | first_bet_only_fallback | first_bet_only_fallback | first_bet_only_fallback | first_bet_only_fallback | first_bet_only_fallback | 1500 | watchlist | controlled_apply |

---

## Coverage Matrix — BIG_LOTTO

| strategy_id | native | adapter | bet1 | bet2 | bet3 | bet4 | bet5 | rows | quality | next_action |
|-------------|--------|---------|------|------|------|------|------|------|---------|-------------|
| ts3_regime_3bet | 1 | missing | already_covered | unsupported | unsupported | unsupported | unsupported | 1500 | sub_baseline | no_action |
| biglotto_deviation_2bet | 2 | partial | first_bet_only_fallback | first_bet_only_fallback | unsupported | unsupported | unsupported | 1570 | watchlist | relabel_first_bet_only |
| biglotto_triple_strike | 3 | partial | first_bet_only_fallback | first_bet_only_fallback | first_bet_only_fallback | unsupported | unsupported | 1570 | fallback_equivalent | relabel_first_bet_only |
| biglotto_echo_aware_3bet | 3 | available | first_bet_only_fallback | first_bet_only_fallback | first_bet_only_fallback | unsupported | unsupported | 1500 | fallback_equivalent | controlled_apply |
| biglotto_ts3_markov_4bet_w30 | 4 | available | first_bet_only_fallback | first_bet_only_fallback | first_bet_only_fallback | first_bet_only_fallback | unsupported | 1500 | sub_baseline | controlled_apply |
| cold_complement_biglotto | 1 | rejected | rejected | rejected | rejected | rejected | rejected | 1500 | coverage_only | no_action |
| coldpool15_biglotto | 1 | rejected | rejected | rejected | rejected | rejected | rejected | 1500 | coverage_only | no_action |
| fourier30_markov30_biglotto | 1 | rejected | rejected | rejected | rejected | rejected | rejected | 1500 | coverage_only | no_action |
| markov_2bet_biglotto | 1 | rejected | rejected | rejected | rejected | rejected | rejected | 1500 | coverage_only | no_action |
| markov_single_biglotto | 1 | rejected | rejected | rejected | rejected | rejected | rejected | 1500 | coverage_only | no_action |
| bet2_fourier_expansion_biglotto | 1 | rejected | rejected | rejected | rejected | rejected | rejected | 1500 | coverage_only | no_action |

---

## Coverage Matrix — POWER_LOTTO

| strategy_id | native | adapter | bet1 | bet2 | bet3 | bet4 | bet5 | rows | quality | next_action |
|-------------|--------|---------|------|------|------|------|------|------|---------|-------------|
| power_precision_3bet | 3 | missing | first_bet_only_fallback | first_bet_only_fallback | first_bet_only_fallback | unsupported | unsupported | 1570 | watchlist | adapter_build |
| power_orthogonal_5bet | 5 | missing | first_bet_only_fallback | first_bet_only_fallback | first_bet_only_fallback | first_bet_only_fallback | first_bet_only_fallback | 1570 | watchlist | adapter_build |
| fourier_rhythm_3bet | 3 | missing | first_bet_only_fallback | first_bet_only_fallback | first_bet_only_fallback | unsupported | unsupported | 1501 | watchlist | adapter_build |
| power_fourier_rhythm_2bet | 2 | available | first_bet_only_fallback | first_bet_only_fallback | unsupported | unsupported | unsupported | 1500 | watchlist | controlled_apply |
| zonal_entropy_2bet | 2 | missing | first_bet_only_fallback | first_bet_only_fallback | unsupported | unsupported | unsupported | 1500 | fallback_equivalent | adapter_build |
| pp3_freqort_4bet | 4 | missing | first_bet_only_fallback | first_bet_only_fallback | first_bet_only_fallback | first_bet_only_fallback | unsupported | 1500 | prediction_helpful | adapter_build |
| midfreq_fourier_mk_3bet | 3 | missing | first_bet_only_fallback | first_bet_only_fallback | first_bet_only_fallback | unsupported | unsupported | 1500 | prediction_helpful | adapter_build |
| midfreq_fourier_2bet | 2 | missing | first_bet_only_fallback | first_bet_only_fallback | unsupported | unsupported | unsupported | 1500 | watchlist | adapter_build |
| cold_complement_2bet | 2 | missing | first_bet_only_fallback | first_bet_only_fallback | unsupported | unsupported | unsupported | 1500 | fallback_equivalent | adapter_build |
| fourier30_markov30_2bet | 2 | missing | first_bet_only_fallback | first_bet_only_fallback | unsupported | unsupported | unsupported | 1501 | watchlist | adapter_build |

---

## Excluded Listings

### Rejected Strategies (no 1-5 bet expansion)

- `acb_single_539`
- `539_3bet_orthogonal`
- `p0b_539_3bet_f_cold_fmid`
- `p0c_539_3bet_f_cold_x2`
- `markov_1bet_539`
- `zone_gap_3bet_539`
- `cold_complement_biglotto`
- `coldpool15_biglotto`
- `fourier30_markov30_biglotto`
- `markov_2bet_biglotto`
- `markov_single_biglotto`
- `bet2_fourier_expansion_biglotto`

### Source-Unknown (4_STAR)

- `4_STAR` lottery is `source_unknown` per P105-P107. Analysis and adapter build forbidden.

---

## Gap Severity Analysis

### Priority 1 — Controlled Apply Ready (Tier-B adapters available)

| strategy_id | lottery_type | native_bets | quality |
|-------------|-------------|------------|---------|
| daily539_f4cold_3bet | DAILY_539 | 3 | watchlist |
| daily539_f4cold_5bet | DAILY_539 | 5 | watchlist |
| biglotto_echo_aware_3bet | BIG_LOTTO | 3 | fallback_equivalent |
| biglotto_ts3_markov_4bet_w30 | BIG_LOTTO | 4 | sub_baseline |
| power_fourier_rhythm_2bet | POWER_LOTTO | 2 | watchlist |

### Priority 2 — Adapter Build Required

| strategy_id | lottery_type | native_bets | quality |
|-------------|-------------|------------|---------|
| acb_markov_midfreq_3bet | DAILY_539 | 3 | watchlist |
| midfreq_acb_2bet | DAILY_539 | 2 | watchlist |
| midfreq_fourier_2bet | DAILY_539 | 2 | watchlist |
| power_precision_3bet | POWER_LOTTO | 3 | watchlist |
| power_orthogonal_5bet | POWER_LOTTO | 5 | watchlist |
| fourier_rhythm_3bet | POWER_LOTTO | 3 | watchlist |
| zonal_entropy_2bet | POWER_LOTTO | 2 | fallback_equivalent |
| pp3_freqort_4bet | POWER_LOTTO | 4 | prediction_helpful |
| midfreq_fourier_mk_3bet | POWER_LOTTO | 3 | prediction_helpful |
| midfreq_fourier_2bet | POWER_LOTTO | 2 | watchlist |
| cold_complement_2bet | POWER_LOTTO | 2 | fallback_equivalent |
| fourier30_markov30_2bet | POWER_LOTTO | 2 | watchlist |

### Priority 3 — Relabel First-Bet-Only (partial adapters)

| strategy_id | lottery_type | native_bets | quality |
|-------------|-------------|------------|---------|
| biglotto_deviation_2bet | BIG_LOTTO | 2 | watchlist |
| biglotto_triple_strike | BIG_LOTTO | 3 | fallback_equivalent |

---

## Proposed P125 Follow-Up

**Recommended next task:** `P125_ADAPTER_GAP_PLAN`

P125 should:
1. Plan controlled_apply passes for the 5 Tier-B adapter-ready strategies
   (closes highest-value gap with lowest implementation risk).
2. Define adapter build spec for remaining multi-bet strategies.
3. Specify the storage schema change needed: each bet gets its own replay row
   OR predicted_numbers stores a JSON array of N sublists.
4. Confirm POWER_LOTTO predicted_special handling before any apply.

---

## Governance Confirmations

- No DB writes performed
- No strategy promotion or demotion
- No lifecycle mutation
- No registry mutation
- No 4_STAR backtest
- No P108 / P117 / P118 execution
- No scheduler install
- replay_rows before = 54462, after = 54462 (unchanged)
