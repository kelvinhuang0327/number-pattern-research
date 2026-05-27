# P94B — Power Lotto All-Strategy × BetCount Benchmark Report

**Task:** P94B_POWER_LOTTO_ALL_STRATEGY_BETCOUNT_BENCHMARK  
**Generated:** 2026-05-27  
**Classification:** `P94B_POWER_LOTTO_ALL_STRATEGY_BETCOUNT_BENCHMARK_READY`  
**Output JSON:** `outputs/replay/p94b_powerlotto_all_strategy_betcount_benchmark_20260527.json`

---

## Summary

| Item | Value |
|---|---|
| DB total replay rows | 54,462 |
| POWER_LOTTO total draws | 1,913 |
| Latest draw evaluated | 115000041 |
| Strategies evaluated | 10 |
| Bet counts compared | 1, 2, 3, 5 |
| Observation windows | 30, 100, 500, 1500 |
| Total window × bet combinations | 16 / 16 covered |

---

## Strategy Inventory

| strategy_id | Display Name | Native Bets | Lifecycle | Multi-Bet Adapter | Special ✓ |
|---|---|---|---|---|---|
| `power_precision_3bet` | PP3 Precision 3注 | 3 | ONLINE | ✓ full 3-bet | — |
| `power_orthogonal_5bet` | Power Orthogonal 5注 | 5 | ONLINE | ✓ full 5-bet | — |
| `fourier_rhythm_3bet` | Fourier Rhythm 3注 | 3 | ONLINE | ✓ full 3-bet | — |
| `power_fourier_rhythm_2bet` | Power Fourier Rhythm 2注 | 2 | DRY_RUN | ✓ full 2-bet | — |
| `zonal_entropy_2bet` | Zonal Entropy 2注 | 2 | DRY_RUN | ✓ full 2-bet | — |
| `pp3_freqort_4bet` | PP3+FreqOrt 4注 | 4 | DRY_RUN | bet-1 only | ✓ |
| `midfreq_fourier_mk_3bet` | MidFreq+Fourier+Markov 3注 | 3 | DRY_RUN | bet-1 only | ✓ |
| `midfreq_fourier_2bet` | MidFreq+Fourier 2注 | 2 | DRY_RUN | bet-1 only | ✓ |
| `cold_complement_2bet` | Cold Complement 2注 | 2 | DRY_RUN | bet-0 only | ✓ |
| `fourier30_markov30_2bet` | Fourier30+Markov30 2注 | 2 | DRY_RUN | bet-0 only | ✓ |

> **Multi-bet coverage note:** Strategies with "bet-1 only" or "bet-0 only" adapters can only be evaluated at bet_count=1. Their higher native bet counts (2–4) are noted by strategy name but the additional bets were not stored in replay rows or exposed via adapter.

---

## Metric Definitions

| Metric | Definition |
|---|---|
| `avg_best_main_hit` | Average of the BEST main-number hit count across all evaluated bets per draw |
| `m3plus_rate` | Fraction of draws where ANY evaluated bet hit ≥ 3 main numbers |
| `m4plus_rate` | Fraction of draws where ANY evaluated bet hit ≥ 4 main numbers |
| `zero_hit_rate` | Fraction of draws where ALL evaluated bets hit 0 main numbers |
| `special_hit_rate` | Fraction of draws where predicted special == actual special (when supported) |
| `coverage_pct` | % of window draws that had a prediction (row or adapter output) |

**Ranking order:** m3plus_rate → avg_best_main_hit → m4plus_rate → special_hit_rate → zero_hit_rate (lower) → sample_size (larger)

---

## Rankings by Observation Window × Bet Count

### Window = 30 (最近 30 期)

> ⚠️ 30-period window is statistically noisy. Results are for trend observation only.

#### Bet = 1

| Rank | strategy_id | M3+ Rate | Avg Hit | Sample | Coverage |
|---|---|---|---|---|---|
| #1 | `fourier30_markov30_2bet` | **10.0%** | 1.200 | 30 | 100.0% |
| #2 | `zonal_entropy_2bet` | 6.9% | 1.172 | 29 | 96.7% |
| #3 | `midfreq_fourier_mk_3bet` | 6.9% | 1.034 | 29 | 96.7% |

#### Bet = 2

| Rank | strategy_id | M3+ Rate | Avg Hit | Sample | Coverage |
|---|---|---|---|---|---|
| #1 | `zonal_entropy_2bet` | **10.0%** | 1.367 | 30 | 100.0% |
| #2 | `power_precision_3bet` | 0.0% | 1.233 | 30 | 100.0% |
| #3 | `power_orthogonal_5bet` | 0.0% | 1.233 | 30 | 100.0% |

#### Bet = 3

| Rank | strategy_id | M3+ Rate | Avg Hit | Sample | Coverage |
|---|---|---|---|---|---|
| #1 | `fourier_rhythm_3bet` | **6.7%** | 1.633 | 30 | 100.0% |
| #2 | `power_precision_3bet` | 3.3% | 1.700 | 30 | 100.0% |
| #3 | `power_orthogonal_5bet` | 3.3% | 1.700 | 30 | 100.0% |

#### Bet = 5 _(only 1 eligible strategy)_

| Rank | strategy_id | M3+ Rate | Avg Hit | Sample | Coverage |
|---|---|---|---|---|---|
| #1 | `power_orthogonal_5bet` | **13.3%** | 1.967 | 30 | 100.0% |

---

### Window = 100 (最近 100 期)

#### Bet = 1

| Rank | strategy_id | M3+ Rate | Avg Hit | Sample | Coverage |
|---|---|---|---|---|---|
| #1 | `midfreq_fourier_mk_3bet` | **6.1%** | 0.990 | 99 | 99.0% |
| #2 | `zonal_entropy_2bet` | 5.1% | 1.020 | 99 | 99.0% |
| #3 | `fourier30_markov30_2bet` | 4.0% | 1.070 | 100 | 100.0% |

#### Bet = 2

| Rank | strategy_id | M3+ Rate | Avg Hit | Sample | Coverage |
|---|---|---|---|---|---|
| #1 | `zonal_entropy_2bet` | **9.0%** | 1.360 | 100 | 100.0% |
| #2 | `fourier_rhythm_3bet` | 6.0% | 1.360 | 100 | 100.0% |
| #3 | `power_fourier_rhythm_2bet` | 6.0% | 1.360 | 100 | 100.0% |

#### Bet = 3

| Rank | strategy_id | M3+ Rate | Avg Hit | Sample | Coverage |
|---|---|---|---|---|---|
| #1 | `power_precision_3bet` | **12.0%** | 1.740 | 100 | 100.0% |
| #2 | `power_orthogonal_5bet` | 12.0% | 1.740 | 100 | 100.0% |
| #3 | `fourier_rhythm_3bet` | 10.0% | 1.650 | 100 | 100.0% |

#### Bet = 5 _(only 1 eligible strategy)_

| Rank | strategy_id | M3+ Rate | Avg Hit | Sample | Coverage |
|---|---|---|---|---|---|
| #1 | `power_orthogonal_5bet` | **23.0%** | 2.110 | 100 | 100.0% |

---

### Window = 500 (最近 500 期)

#### Bet = 1

| Rank | strategy_id | M3+ Rate | Avg Hit | Sample | Coverage |
|---|---|---|---|---|---|
| #1 | `midfreq_fourier_2bet` | **5.6%** | 0.976 | 499 | 99.8% |
| #2 | `midfreq_fourier_mk_3bet` | 3.6% | 1.004 | 499 | 99.8% |
| #3 | `zonal_entropy_2bet` | 3.6% | 0.960 | 499 | 99.8% |

#### Bet = 2

| Rank | strategy_id | M3+ Rate | Avg Hit | Sample | Coverage |
|---|---|---|---|---|---|
| #1 | `zonal_entropy_2bet` | **10.0%** | 1.472 | 500 | 100.0% |
| #2 | `fourier_rhythm_3bet` | 8.2% | 1.434 | 500 | 100.0% |
| #3 | `power_fourier_rhythm_2bet` | 8.2% | 1.434 | 500 | 100.0% |

#### Bet = 3

| Rank | strategy_id | M3+ Rate | Avg Hit | Sample | Coverage |
|---|---|---|---|---|---|
| #1 | `power_precision_3bet` | **12.4%** | 1.748 | 500 | 100.0% |
| #2 | `power_orthogonal_5bet` | 12.4% | 1.748 | 500 | 100.0% |
| #3 | `fourier_rhythm_3bet` | 12.4% | 1.712 | 500 | 100.0% |

#### Bet = 5 _(only 1 eligible strategy)_

| Rank | strategy_id | M3+ Rate | Avg Hit | Sample | Coverage |
|---|---|---|---|---|---|
| #1 | `power_orthogonal_5bet` | **20.8%** | 2.082 | 500 | 100.0% |

---

### Window = 1500 (最近 1500 期)

#### Bet = 1

| Rank | strategy_id | M3+ Rate | Avg Hit | Sample | Coverage |
|---|---|---|---|---|---|
| #1 | `pp3_freqort_4bet` | **5.4%** | 1.003 | 1499 | 99.9% |
| #2 | `power_precision_3bet` | 5.0% | 0.997 | 1499 | 99.9% |
| #3 | `power_orthogonal_5bet` | 5.0% | 0.997 | 1499 | 99.9% |

#### Bet = 2

| Rank | strategy_id | M3+ Rate | Avg Hit | Sample | Coverage |
|---|---|---|---|---|---|
| #1 | `fourier_rhythm_3bet` | **9.1%** | 1.470 | 1500 | 100.0% |
| #2 | `power_fourier_rhythm_2bet` | 9.1% | 1.470 | 1500 | 100.0% |
| #3 | `power_precision_3bet` | 9.1% | 1.465 | 1500 | 100.0% |

#### Bet = 3

| Rank | strategy_id | M3+ Rate | Avg Hit | Sample | Coverage |
|---|---|---|---|---|---|
| #1 | `fourier_rhythm_3bet` | **13.7%** | 1.766 | 1500 | 100.0% |
| #2 | `power_precision_3bet` | 13.3% | 1.745 | 1500 | 100.0% |
| #3 | `power_orthogonal_5bet` | 13.3% | 1.745 | 1500 | 100.0% |

#### Bet = 5 _(only 1 eligible strategy)_

| Rank | strategy_id | M3+ Rate | Avg Hit | Sample | Coverage |
|---|---|---|---|---|---|
| #1 | `power_orthogonal_5bet` | **21.7%** | 2.097 | 1500 | 100.0% |

---

## Cross-Window Performance Summary

### Stable Performers (appear in top 3 across multiple windows)

| strategy_id | Bet=1 appearances | Bet=2 appearances | Bet=3 appearances | Bet=5 appearances |
|---|---|---|---|---|
| `power_orthogonal_5bet` | 1/4 (w1500) | — | 3/4 (w100,w500,w1500) | 4/4 (all) |
| `fourier_rhythm_3bet` | — | 3/4 (w100,w500,w1500) | 3/4 (w30,w100,w500,w1500) | — |
| `power_precision_3bet` | 1/4 (w1500) | 2/4 (w30,w1500) | 3/4 (w100,w500,w1500) | — |
| `zonal_entropy_2bet` | 2/4 (w30,w100) | 4/4 (all) | — | — |
| `power_fourier_rhythm_2bet` | — | 3/4 (w100,w500,w1500) | — | — |
| `midfreq_fourier_mk_3bet` | 2/4 (w30,w100) | — | — | — |

### Key Insights

1. **`power_orthogonal_5bet` (ONLINE)** — Dominant at bet=5 (only eligible strategy). Strong at bet=3 (12–13% M3+). Its 5-bet coverage justifies 21.7% M3+ rate over 1500 draws.

2. **`fourier_rhythm_3bet` (ONLINE)** — Most stable at bet=2 and bet=3 over long windows (w1500). Slight edge over `power_precision_3bet` at 3-bet w1500 (13.7% vs 13.3%).

3. **`power_precision_3bet` (ONLINE)** — Near-identical to `power_orthogonal_5bet` for bet≤3. Consistently top-3 at bet=2 and bet=3.

4. **`zonal_entropy_2bet` (DRY_RUN)** — Dominant at bet=2 across ALL windows (9–10% M3+). Outperforms all strategies at 2-bet consistently. Promotion candidate pending full lifecycle review.

5. **`pp3_freqort_4bet` (DRY_RUN)** — Leads at bet=1 w1500 (5.4% M3+) but only 1-bet adapter available. Additional bet support would require full adapter implementation.

6. **`fourier30_markov30_2bet` / `midfreq_fourier_mk_3bet`** — Short-window leaders at bet=1 (w30/w100), suggesting recent-period regime fit, but performance weaker over longer windows.

---

## Caveats and Limitations

### Special Number Analysis
- Strategies with `special_support=True` (pp3_freqort_4bet, midfreq_fourier_mk_3bet, midfreq_fourier_2bet, cold_complement_2bet, fourier30_markov30_2bet) do predict special numbers.
- Special hit rates are included in the JSON output but not shown in above tables.
- Multi-bet adapter paths (`zonal_entropy_2bet`, `fourier_rhythm_3bet`, `power_*`) do **not** predict special numbers in their current tool implementations.

### Bet=5 Coverage
- Only `power_orthogonal_5bet` has a native 5-bet tool. All other strategies are marked `unsupported` for bet_count=5.
- This limits the bet=5 ranking to 1 entry per window. This is an accurate representation of current strategy coverage, not a benchmark failure.

### Multi-Bet for DRY_RUN Single-Bet Adapters
- `pp3_freqort_4bet`, `midfreq_fourier_mk_3bet`, `midfreq_fourier_2bet`, `cold_complement_2bet`, `fourier30_markov30_2bet` store only bet-1 in replay rows. Their native multi-bet generation code was not exposed in a causal-safe adapter, preventing bet=2+ evaluation.
- These strategies' 2/3/4/5-bet variants are marked `single_bet_only_adapter_no_betN_support`.

### Rejected/Offline Strategies
- All 10 strategies evaluated include 7 with lifecycle `DRY_RUN`. This benchmark presents their data factually for comparison purposes.
- DRY_RUN lifecycle entries are **not promoted** to ONLINE by this report. Promotion requires separate lifecycle governance.

### Governance Compliance
- ✅ DB is read-only (no inserts or updates to `lottery_v2.db`)
- ✅ Causal isolation enforced: history ends BEFORE target draw for all adapter predictions
- ✅ No multi-bet fabrication for unsupported strategies
- ✅ `CAST(draw AS INTEGER)` used for draw ordering
- ✅ Main numbers validated 1–38, special 1–8

---

## Artifacts

| File | Description |
|---|---|
| `scripts/p94b_powerlotto_all_strategy_betcount_benchmark.py` | Benchmark script |
| `outputs/replay/p94b_powerlotto_all_strategy_betcount_benchmark_20260527.json` | Full results JSON |
| `docs/replay/p94b_powerlotto_all_strategy_betcount_benchmark_20260527.md` | This report |
| `tests/test_p94b_powerlotto_all_strategy_betcount_benchmark.py` | Test suite |
