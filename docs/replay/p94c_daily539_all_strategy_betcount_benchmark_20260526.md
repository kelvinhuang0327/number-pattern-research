# P94C Daily539 All-Strategy Bet-Count Benchmark

**Date**: 2026-05-26  
**Classification**: `P94C_DAILY539_ALL_STRATEGY_BETCOUNT_BENCHMARK_READY`  
**Mode**: FAST (multibet adapter computed for windows 30 and 100; windows 500/1500 use 1-bet DB fallback with caveat)

---

## 1. Governance

| Check | Result |
|---|---|
| DB writes to lottery_v2.db | ❌ NONE |
| Production replay row changes | 0 |
| lifecycle/champion/registry mutations | NONE |
| Rejected/offline strategies promoted | NONE |
| Fabricated bets | NONE |
| Causal isolation | ✅ history ends strictly before target draw |

---

## 2. DAILY_539 Semantics

| Field | Value |
|---|---|
| Lottery type | DAILY_539 |
| Pick | 5 numbers |
| Pool | 1–39 (39 numbers) |
| Special number | None |
| Baseline M3+ (1 bet) | ~1.004% |

> All bets must contain exactly 5 numbers in range 1–39. No special number applies.

---

## 3. Candidate Summary

| Metric | Count |
|---|---|
| Total DAILY_539 strategies | 15 |
| Benchmarkable (row-backed) | 15 |
| Unsupported / no-data | 0 |
| Tier A row-backed | 13 |
| Tier B P94-applied (adapter-backed) | 2 |
| Native 1-bet strategies | 6 |
| Native 2-bet strategies | 2 |
| Native 3-bet strategies | 6 |
| Native 5-bet strategies | 1 |

### Strategy Catalog

| Strategy ID | Display Name | Lifecycle | Perf Label | Native Bets | Source |
|---|---|---|---|---|---|
| acb_1bet | 今彩539 ACB 1注 | PRODUCTION | RETIRED | 1 | tier_a_row_backed |
| acb_markov_midfreq | 今彩539 ACB+Markov 中頻 | NOT_IN_P0 | RETIRED | 1 | tier_a_row_backed |
| acb_single_539 | 今彩539 ACB Single 1注 | REJECTED | WAVE2 | 1 | tier_a_row_backed |
| acb_markov_midfreq_3bet | 今彩539 ACB+Markov 中頻 3注 | PRODUCTION | RETIRED | 3 | tier_a_row_backed |
| 539_3bet_orthogonal | 今彩539 ACB+Markov+Fourier 正交 3注 | REJECTED | WAVE2_ACTIVE | 3 | tier_a_row_backed |
| daily539_f4cold | 今彩539 F4 Cold (legacy) | PRODUCTION | ONLINE_LEGACY | 1 | tier_a_row_backed |
| p0b_539_3bet_f_cold_fmid | 今彩539 Fourier4正交 cold+midfreq 3注 | REJECTED | WAVE2_ACTIVE | 3 | tier_a_row_backed |
| p0c_539_3bet_f_cold_x2 | 今彩539 Fourier4正交 x2 cold 3注 | REJECTED | WAVE2_ACTIVE | 3 | tier_a_row_backed |
| markov_1bet_539 | 今彩539 Markov 1注 | REJECTED | WAVE2_ACTIVE | 1 | tier_a_row_backed |
| daily539_markov_cold | 今彩539 Markov Cold | PRODUCTION | ONLINE_LEGACY | 1 | tier_a_row_backed |
| zone_gap_3bet_539 | 今彩539 Zone+Gap 3注 | REJECTED | WAVE2_ACTIVE | 3 | tier_a_row_backed |
| midfreq_acb_2bet | 今彩539 中頻 ACB 2注 | PRODUCTION | RETIRED | 2 | tier_a_row_backed |
| midfreq_fourier_2bet | 今彩539 中頻 Fourier 2注 | PRODUCTION | RETIRED | 2 | tier_a_row_backed |
| daily539_f4cold_3bet | 今彩539 F4Cold 3注 | PRODUCTION | P94_TIER_B | 3 | tier_b_p94_applied |
| daily539_f4cold_5bet | 今彩539 F4Cold 5注 | PRODUCTION | P94_TIER_B | 5 | tier_b_p94_applied |

---

## 4. Bet-Count Support Matrix

| Strategy | 1-bet | 2-bet | 3-bet | 5-bet |
|---|---|---|---|---|
| acb_1bet | ✅ DB_ROW | ❌ exceeds native | ❌ exceeds native | ❌ exceeds native |
| acb_markov_midfreq | ✅ DB_ROW | ❌ exceeds native | ❌ exceeds native | ❌ exceeds native |
| acb_single_539 | ✅ DB_ROW | ❌ exceeds native | ❌ exceeds native | ❌ exceeds native |
| acb_markov_midfreq_3bet | ✅ DB_ROW (bet-1) | ❌ DB single bet only | ✅ DB_ROW (bet-1)* | ❌ exceeds native |
| 539_3bet_orthogonal | ✅ DB_ROW (bet-1) | ❌ DB single bet only | ✅ DB_ROW (bet-1)* | ❌ exceeds native |
| daily539_f4cold | ✅ DB_ROW | ❌ exceeds native | ❌ exceeds native | ❌ exceeds native |
| p0b_539_3bet_f_cold_fmid | ✅ DB_ROW (bet-1) | ❌ DB single bet only | ✅ DB_ROW (bet-1)* | ❌ exceeds native |
| p0c_539_3bet_f_cold_x2 | ✅ DB_ROW (bet-1) | ❌ DB single bet only | ✅ DB_ROW (bet-1)* | ❌ exceeds native |
| markov_1bet_539 | ✅ DB_ROW | ❌ exceeds native | ❌ exceeds native | ❌ exceeds native |
| daily539_markov_cold | ✅ DB_ROW | ❌ exceeds native | ❌ exceeds native | ❌ exceeds native |
| zone_gap_3bet_539 | ✅ DB_ROW (bet-1) | ❌ DB single bet only | ✅ DB_ROW (bet-1)* | ❌ exceeds native |
| midfreq_acb_2bet | ✅ DB_ROW (bet-1) | ❌ DB single bet only | ❌ exceeds native | ❌ exceeds native |
| midfreq_fourier_2bet | ✅ DB_ROW (bet-1) | ❌ DB single bet only | ❌ exceeds native | ❌ exceeds native |
| **daily539_f4cold_3bet** | ✅ DB_ROW | ✅ ADAPTER (w≤100) / FALLBACK (w>100) | ✅ ADAPTER (w≤100) / FALLBACK (w>100) | ❌ exceeds native |
| **daily539_f4cold_5bet** | ✅ DB_ROW | ✅ ADAPTER (w≤100) / FALLBACK (w>100) | ✅ ADAPTER (w≤100) / FALLBACK (w>100) | ✅ ADAPTER (w≤100) / FALLBACK (w>100) |

> `*` = for native 3-bet strategies without get_all_bets(), DB stores only bet-1. When ranked as "3-bet" the DB bet-1 metrics appear but DO NOT reflect true 3-bet coverage.
> `FALLBACK` = 1-bet DB row metrics shown with caveat for windows 500/1500. Use `--full` to run adapter for all windows.

---

## 5. Top-3 Rankings

**Primary metric**: M3+ rate. Tiebreakers: avg_hit, M4+, M5, lower zero_hit_rate, larger sample_size.  
**Baseline M3+ (1 bet)**: ~1.004%

### Window = 30 draws

| Rank | Strategy | Lifecycle | M3+% | avg_hit | n | Source | Note |
|---|---|---|---|---|---|---|---|
| **bet_count = 1** |
| #1 | zone_gap_3bet_539 | REJECTED | 0.00% | 0.867 | 30 | DB_ROW | All M3+= 0% in last 30 draws |
| #2 | midfreq_acb_2bet | PRODUCTION | 0.00% | 0.700 | 30 | DB_ROW | |
| #3 | midfreq_fourier_2bet | PRODUCTION | 0.00% | 0.700 | 30 | DB_ROW | |
| **bet_count = 2** |
| #1 | daily539_f4cold_3bet | PRODUCTION | 0.00% | 1.267 | 30 | ADAPTER_MULTIBET | |
| #2 | daily539_f4cold_5bet | PRODUCTION | 0.00% | 1.267 | 30 | ADAPTER_MULTIBET | |
| — | (no other strategies) | | | | | | |
| **bet_count = 3** |
| #1 | daily539_f4cold_3bet | PRODUCTION | 0.00% | 1.267 | 30 | ADAPTER_MULTIBET | |
| #2 | daily539_f4cold_5bet | PRODUCTION | 0.00% | 1.267 | 30 | ADAPTER_MULTIBET | |
| — | (no other strategies) | | | | | | |
| **bet_count = 5** |
| #1 | daily539_f4cold_5bet | PRODUCTION | **3.33%** | 1.533 | 30 | ADAPTER_MULTIBET | Only 5-bet adapter |

### Window = 100 draws

| Rank | Strategy | Lifecycle | M3+% | avg_hit | n | Source | Note |
|---|---|---|---|---|---|---|---|
| **bet_count = 1** |
| #1 | midfreq_acb_2bet | PRODUCTION | **2.00%** | 0.720 | 100 | DB_ROW | |
| #2 | midfreq_fourier_2bet | PRODUCTION | **2.00%** | 0.720 | 100 | DB_ROW | |
| #3 | markov_1bet_539 | REJECTED | 1.00% | 0.600 | 100 | DB_ROW | |
| **bet_count = 2** |
| #1 | daily539_f4cold_3bet | PRODUCTION | 1.00% | 0.940 | 100 | ADAPTER_MULTIBET | |
| #2 | daily539_f4cold_5bet | PRODUCTION | 1.00% | 0.940 | 100 | ADAPTER_MULTIBET | |
| — | (no other strategies) | | | | | | |
| **bet_count = 3** |
| #1 | daily539_f4cold_3bet | PRODUCTION | **2.00%** | 1.150 | 100 | ADAPTER_MULTIBET | |
| #2 | daily539_f4cold_5bet | PRODUCTION | **2.00%** | 1.150 | 100 | ADAPTER_MULTIBET | |
| — | (no other strategies) | | | | | | |
| **bet_count = 5** |
| #1 | daily539_f4cold_5bet | PRODUCTION | **5.00%** | 1.340 | 100 | ADAPTER_MULTIBET | Only 5-bet adapter |

### Window = 500 draws

| Rank | Strategy | Lifecycle | M3+% | avg_hit | n | Source | Note |
|---|---|---|---|---|---|---|---|
| **bet_count = 1** |
| #1 | acb_markov_midfreq | NOT_IN_P0 | **1.40%** | 0.640 | 500 | DB_ROW | |
| #2 | markov_1bet_539 | REJECTED | 1.20% | 0.664 | 500 | DB_ROW | |
| #3 | daily539_markov_cold | PRODUCTION | 1.20% | 0.664 | 500 | DB_ROW | |
| **bet_count = 2** |
| #1 | daily539_f4cold_3bet | PRODUCTION | 0.60% | 0.664 | 500 | DB_ROW_1BET_FALLBACK | ⚠️ 1-bet fallback |
| #2 | daily539_f4cold_5bet | PRODUCTION | 0.60% | 0.664 | 500 | DB_ROW_1BET_FALLBACK | ⚠️ 1-bet fallback |
| **bet_count = 3** |
| #1 | daily539_f4cold_3bet | PRODUCTION | 0.60% | 0.664 | 500 | DB_ROW_1BET_FALLBACK | ⚠️ 1-bet fallback |
| #2 | daily539_f4cold_5bet | PRODUCTION | 0.60% | 0.664 | 500 | DB_ROW_1BET_FALLBACK | ⚠️ 1-bet fallback |
| **bet_count = 5** |
| #1 | daily539_f4cold_5bet | PRODUCTION | 0.60% | 0.664 | 500 | DB_ROW_1BET_FALLBACK | ⚠️ 1-bet fallback |

### Window = 1500 draws

| Rank | Strategy | Lifecycle | M3+% | avg_hit | n | Source | Note |
|---|---|---|---|---|---|---|---|
| **bet_count = 1** |
| #1 | acb_markov_midfreq | NOT_IN_P0 | **1.33%** | 0.637 | 1500 | DB_ROW | |
| #2 | midfreq_acb_2bet | PRODUCTION | 1.27% | 0.669 | 1500 | DB_ROW | |
| #3 | midfreq_fourier_2bet | PRODUCTION | 1.27% | 0.669 | 1500 | DB_ROW | |
| **bet_count = 2** |
| #1 | daily539_f4cold_3bet | PRODUCTION | 0.87% | 0.673 | 1500 | DB_ROW_1BET_FALLBACK | ⚠️ 1-bet fallback |
| #2 | daily539_f4cold_5bet | PRODUCTION | 0.87% | 0.673 | 1500 | DB_ROW_1BET_FALLBACK | ⚠️ 1-bet fallback |
| **bet_count = 3** |
| #1 | daily539_f4cold_3bet | PRODUCTION | 0.87% | 0.673 | 1500 | DB_ROW_1BET_FALLBACK | ⚠️ 1-bet fallback |
| #2 | daily539_f4cold_5bet | PRODUCTION | 0.87% | 0.673 | 1500 | DB_ROW_1BET_FALLBACK | ⚠️ 1-bet fallback |
| **bet_count = 5** |
| #1 | daily539_f4cold_5bet | PRODUCTION | 0.87% | 0.673 | 1500 | DB_ROW_1BET_FALLBACK | ⚠️ 1-bet fallback |

---

## 6. Stable Top Performers (top-3 in ≥2 windows)

| Strategy | Bet Count | Appearances |
|---|---|---|
| daily539_f4cold_3bet | 2 | 4/4 windows |
| daily539_f4cold_5bet | 2 | 4/4 windows |
| daily539_f4cold_3bet | 3 | 4/4 windows |
| daily539_f4cold_5bet | 3 | 4/4 windows |
| daily539_f4cold_5bet | 5 | 4/4 windows |

> **Caveat**: For windows 500 and 1500, bet>1 metrics are 1-bet DB fallbacks (FAST mode). The adapter-based true multibet performance for these windows requires `--full` rerun.
>
> For 1-bet rankings, **acb_markov_midfreq** and **midfreq_acb_2bet / midfreq_fourier_2bet** are the most stable performers over 1500 draws.

---

## 7. Short-Window-Only Performers Warning

| Strategy | Bet Count | Note |
|---|---|---|
| zone_gap_3bet_539 | 1 | Only appears in top-3 for w=30. Not stable over longer windows. REJECTED lifecycle. |

> **Warning**: zone_gap_3bet_539 ranks #1 in the 30-draw window solely because it has the highest avg_hit_count (0.867) when all M3+ rates are 0%. This is a cold-period artifact, not a signal.

---

## 8. Rejected / Offline Replay-Only Caveat

The following strategies are REJECTED or RETIRED but included for replay-only analysis:

- `acb_single_539` (REJECTED)
- `539_3bet_orthogonal` (REJECTED)
- `p0b_539_3bet_f_cold_fmid` (REJECTED)
- `p0c_539_3bet_f_cold_x2` (REJECTED)
- `markov_1bet_539` (REJECTED)
- `zone_gap_3bet_539` (REJECTED)
- `acb_markov_midfreq` (NOT_IN_P0 / RETIRED)
- `acb_markov_midfreq_3bet` (RETIRED)
- `midfreq_acb_2bet` (RETIRED)
- `midfreq_fourier_2bet` (RETIRED)

**None of these have been promoted, re-activated, or inserted to production DB in this benchmark.**  
Benchmark metrics are read-only observations for historical context only.

---

## 9. No-Data / Unsupported Policy

**Unsupported strategies in this benchmark**: 0 (all 15 candidates have DB rows)

**Unsupported bet-count variants** are handled as follows:
- `bet_count > native_bet_count` → blocker: `BET_COUNT_EXCEEDS_NATIVE` (no fabrication)
- `native_bet_count > 1` but `has_multibet_adapter = False` → blocker: `DB_SINGLE_BET_ONLY`
- DB stores bet-1 only for all Tier-A multi-bet strategies (wave-1/wave-2 adapters use `_extract_first_bet()`)

**Multi-bet note**: Only `daily539_f4cold_3bet` and `daily539_f4cold_5bet` have `get_all_bets()` adapters (P93 Tier B). For windows 500/1500 in FAST mode, multibet shows 1-bet fallback. Run with `--full` for complete multibet at all windows.

---

## 10. Production Invariants

| Invariant | Before | After | Status |
|---|---|---|---|
| `strategy_prediction_replays` rows | 54462 | 54462 | ✅ UNCHANGED |
| `POWER_LOTTO` max draw | 115000041 | 115000041 | ✅ UNCHANGED |

---

## 11. Recommended Next Step

**P94D**: Controlled benchmark review across BIG_LOTTO / POWER_LOTTO / DAILY_539 for cross-game comparison of top stable performers.

**OR**

**P95**: Selected strategy dry-run/apply plan for:
- `midfreq_acb_2bet` — 1500p M3+=1.27%, stable across windows, RETIRED lifecycle
- `midfreq_fourier_2bet` — 1500p M3+=1.27%, stable, RETIRED lifecycle
- `acb_markov_midfreq` — 1500p M3+=1.33%, highest stable 1-bet performer
- `daily539_f4cold_5bet` — 5-bet adapter available, w100 M3+=5.00% (ADAPTER_MULTIBET)

---

## Artifacts

| File | Description |
|---|---|
| `outputs/replay/p94c_daily539_all_strategy_betcount_benchmark_20260526.json` | Full benchmark data with all results |
| `docs/replay/p94c_daily539_all_strategy_betcount_benchmark_20260526.md` | This report |
| `scripts/p94c_daily539_all_strategy_betcount_benchmark.py` | Benchmark script |
| `tests/test_p94c_daily539_all_strategy_betcount_benchmark.py` | Test suite |
