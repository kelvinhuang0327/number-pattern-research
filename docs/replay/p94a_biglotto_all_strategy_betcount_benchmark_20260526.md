# P94A: BIG_LOTTO All-Strategy Betcount Benchmark

**Date**: 2026-05-27  
**Final Classification**: `P94A_BIG_LOTTO_ALL_STRATEGY_BETCOUNT_BENCHMARK_READY`  
**Baseline Note**: P94A baseline adjusted from pre-P94 46962 to post-P94 54462 because P94 controlled apply had already completed before P94A execution.

## 1. Governance

| Item | Value |
|------|-------|
| DB writes | `False` |
| Replay row changes | `0` |
| Lifecycle promotions | `0` |
| Production rows before | `54462` |
| Production rows after | `54462` |
| Ranking metric | `m3_plus_rate` |

## 2. BIG_LOTTO Candidate Summary

| Category | Count |
|----------|-------|
| Total Biglotto Strategies | 13 |
| Benchmarkable Count | 11 |
| Unsupported Blocked Count | 2 |
| Rejected Offline Count | 6 |
| Row Backed Count | 5 |
| Adapter Backed Count | 4 |
| No Data Count | 0 |

## 3. Strategy Universe

### 3a. Benchmarkable Strategies

| strategy_id | lifecycle | source | native_bets | 1-bet | 2-bet | 3-bet | 5-bet |
|-------------|-----------|--------|-------------|-------|-------|-------|-------|
| `ts3_regime_3bet` | PRODUCTION | row-backed | 1 | ✓ | ✗ (native_bets=1_lt_2) | ✗ (native_bets=1_lt_3) | ✗ (native_bets=1_lt_5) |
| `biglotto_deviation_2bet` | PRODUCTION | row-backed+adapter | 2 | ✓ | ✓ | ✗ (native_bets=2_lt_3) | ✗ (native_bets=2_lt_5) |
| `biglotto_triple_strike` | PRODUCTION | row-backed+adapter | 3 | ✓ | ✓ | ✓ | ✗ (native_bets=3_lt_5) |
| `biglotto_echo_aware_3bet` | TIERB_DRYRUN_VALIDATED | row-backed+adapter | 3 | ✓ | ✓ | ✓ | ✗ (native_bets=3_lt_5) |
| `biglotto_ts3_markov_4bet_w30` | TIERB_DRYRUN_VALIDATED | row-backed+adapter | 4 | ✓ | ✓ | ✓ | ✗ (native_bets=4_lt_5) |
| `cold_complement_biglotto` | REJECTED | rejected-replay-only | 1 | ✓ | ✗ (native_bets=1_lt_2) | ✗ (native_bets=1_lt_3) | ✗ (native_bets=1_lt_5) |
| `coldpool15_biglotto` | REJECTED | rejected-replay-only | 1 | ✓ | ✗ (native_bets=1_lt_2) | ✗ (native_bets=1_lt_3) | ✗ (native_bets=1_lt_5) |
| `fourier30_markov30_biglotto` | REJECTED | rejected-replay-only | 1 | ✓ | ✗ (native_bets=1_lt_2) | ✗ (native_bets=1_lt_3) | ✗ (native_bets=1_lt_5) |
| `markov_2bet_biglotto` | REJECTED | rejected-replay-only | 1 | ✓ | ✗ (native_bets=1_lt_2) | ✗ (native_bets=1_lt_3) | ✗ (native_bets=1_lt_5) |
| `markov_single_biglotto` | REJECTED | rejected-replay-only | 1 | ✓ | ✗ (native_bets=1_lt_2) | ✗ (native_bets=1_lt_3) | ✗ (native_bets=1_lt_5) |
| `bet2_fourier_expansion_biglotto` | REJECTED | rejected-replay-only | 1 | ✓ | ✗ (native_bets=1_lt_2) | ✗ (native_bets=1_lt_3) | ✗ (native_bets=1_lt_5) |

### 3b. Blocked / Unsupported Strategies

| strategy_id | status | blocker |
|-------------|--------|---------|
| `biglotto_fourier_rhythm_2bet` | ADAPTER_PARTIAL | No ReplayStrategyAdapter subclass for composite fourier_rhythm_bet + c |
| `ts3_markov_freq_5bet_w30` | SUPERSEDED | SUPERSEDED per lottery_api/CLAUDE.md lines 511/534-536. Replaced 2026- |

## 4. Random Baseline Rates

| bet_count | M2+ | M3+ | M4+ |
|-----------|-----|-----|-----|
| 1 | 0.1510 | 0.0186 | 0.000987 |
| 2 | 0.2792 | 0.0369 | 0.001973 |
| 3 | 0.3881 | 0.0549 | 0.002959 |
| 5 | 0.5589 | 0.0898 | 0.004926 |

## 5. Top-3 Rankings by Window × Bet Count

> **Primary metric**: M3+ rate  
> **Tie-breakers**: avg_hit_count > M4+ rate > lower zero_hit_rate > larger sample_size

### Window = Latest 30 draws

#### Bet count = 1

Random M3+ baseline (1-bet): `0.0186`

| Rank | strategy_id | lifecycle | M3+ | vs baseline | avg_hit | M4+ | zero_hit% | n | source |
|------|-------------|-----------|-----|-------------|---------|-----|-----------|---|--------|
| 1 | `ts3_regime_3bet` | PRODUCTION | 0.1071 | +0.0885 | 1.0357 | 0.000000 | 28.6% | 28 | db_rows |
| 2 | `biglotto_triple_strike` | PRODUCTION | 0.1071 | +0.0885 | 1.0357 | 0.000000 | 28.6% | 28 | db_rows |
| 3 | `bet2_fourier_expansion_biglotto` | REJECTED | 0.1034 | +0.0848 | 1.0000 | 0.000000 | 31.0% | 29 | db_rows |

#### Bet count = 2

Random M3+ baseline (2-bet): `0.0369`

| Rank | strategy_id | lifecycle | M3+ | vs baseline | avg_hit | M4+ | zero_hit% | n | source |
|------|-------------|-----------|-----|-------------|---------|-----|-----------|---|--------|
| 1 | `biglotto_triple_strike` | PRODUCTION | 0.1000 | +0.0631 | 1.3000 | 0.000000 | 10.0% | 30 | adapter_2bet |
| 2 | `biglotto_ts3_markov_4bet_w30` | TIERB_DRYRUN_VALIDATED | 0.1000 | +0.0631 | 1.3000 | 0.000000 | 10.0% | 30 | adapter_2bet |
| 3 | `biglotto_echo_aware_3bet` | TIERB_DRYRUN_VALIDATED | 0.0667 | +0.0297 | 1.0667 | 0.000000 | 23.3% | 30 | adapter_2bet |

#### Bet count = 3

Random M3+ baseline (3-bet): `0.0549`

| Rank | strategy_id | lifecycle | M3+ | vs baseline | avg_hit | M4+ | zero_hit% | n | source |
|------|-------------|-----------|-----|-------------|---------|-----|-----------|---|--------|
| 1 | `biglotto_triple_strike` | PRODUCTION | 0.1000 | +0.0451 | 1.5333 | 0.000000 | 0.0% | 30 | adapter_3bet |
| 2 | `biglotto_ts3_markov_4bet_w30` | TIERB_DRYRUN_VALIDATED | 0.1000 | +0.0451 | 1.5333 | 0.000000 | 0.0% | 30 | adapter_3bet |
| 3 | `biglotto_echo_aware_3bet` | TIERB_DRYRUN_VALIDATED | 0.1000 | +0.0451 | 1.4333 | 0.000000 | 6.7% | 30 | adapter_3bet |

#### Bet count = 5

Random M3+ baseline (5-bet): `0.0898`

*No strategies with valid data for this combination.*

### Window = Latest 100 draws

#### Bet count = 1

Random M3+ baseline (1-bet): `0.0186`

| Rank | strategy_id | lifecycle | M3+ | vs baseline | avg_hit | M4+ | zero_hit% | n | source |
|------|-------------|-----------|-----|-------------|---------|-----|-----------|---|--------|
| 1 | `ts3_regime_3bet` | PRODUCTION | 0.0510 | +0.0324 | 0.7755 | 0.000000 | 43.9% | 98 | db_rows |
| 2 | `biglotto_triple_strike` | PRODUCTION | 0.0510 | +0.0324 | 0.7755 | 0.000000 | 43.9% | 98 | db_rows |
| 3 | `bet2_fourier_expansion_biglotto` | REJECTED | 0.0505 | +0.0319 | 0.7677 | 0.000000 | 44.4% | 99 | db_rows |

#### Bet count = 2

Random M3+ baseline (2-bet): `0.0369`

| Rank | strategy_id | lifecycle | M3+ | vs baseline | avg_hit | M4+ | zero_hit% | n | source |
|------|-------------|-----------|-----|-------------|---------|-----|-----------|---|--------|
| 1 | `biglotto_triple_strike` | PRODUCTION | 0.0500 | +0.0131 | 1.1200 | 0.000000 | 19.0% | 100 | adapter_2bet |
| 2 | `biglotto_ts3_markov_4bet_w30` | TIERB_DRYRUN_VALIDATED | 0.0500 | +0.0131 | 1.1200 | 0.000000 | 19.0% | 100 | adapter_2bet |
| 3 | `biglotto_echo_aware_3bet` | TIERB_DRYRUN_VALIDATED | 0.0300 | -0.0069 | 1.1300 | 0.000000 | 18.0% | 100 | adapter_2bet |

#### Bet count = 3

Random M3+ baseline (3-bet): `0.0549`

| Rank | strategy_id | lifecycle | M3+ | vs baseline | avg_hit | M4+ | zero_hit% | n | source |
|------|-------------|-----------|-----|-------------|---------|-----|-----------|---|--------|
| 1 | `biglotto_triple_strike` | PRODUCTION | 0.0700 | +0.0151 | 1.4200 | 0.000000 | 4.0% | 100 | adapter_3bet |
| 2 | `biglotto_ts3_markov_4bet_w30` | TIERB_DRYRUN_VALIDATED | 0.0700 | +0.0151 | 1.4200 | 0.000000 | 4.0% | 100 | adapter_3bet |
| 3 | `biglotto_echo_aware_3bet` | TIERB_DRYRUN_VALIDATED | 0.0500 | -0.0049 | 1.3700 | 0.000000 | 6.0% | 100 | adapter_3bet |

#### Bet count = 5

Random M3+ baseline (5-bet): `0.0898`

*No strategies with valid data for this combination.*

### Window = Latest 500 draws

#### Bet count = 1

Random M3+ baseline (1-bet): `0.0186`

| Rank | strategy_id | lifecycle | M3+ | vs baseline | avg_hit | M4+ | zero_hit% | n | source |
|------|-------------|-----------|-----|-------------|---------|-----|-----------|---|--------|
| 1 | `biglotto_deviation_2bet` | PRODUCTION | 0.0341 | +0.0155 | 0.8273 | 0.000000 | 41.0% | 498 | db_rows |
| 2 | `bet2_fourier_expansion_biglotto` | REJECTED | 0.0281 | +0.0094 | 0.7214 | 0.002004 | 44.7% | 499 | db_rows |
| 3 | `ts3_regime_3bet` | PRODUCTION | 0.0241 | +0.0055 | 0.7068 | 0.000000 | 45.4% | 498 | db_rows |

#### Bet count = 2

Random M3+ baseline (2-bet): `0.0369`

| Rank | strategy_id | lifecycle | M3+ | vs baseline | avg_hit | M4+ | zero_hit% | n | source |
|------|-------------|-----------|-----|-------------|---------|-----|-----------|---|--------|
| 1 | `biglotto_echo_aware_3bet` | TIERB_DRYRUN_VALIDATED | 0.0520 | +0.0151 | 1.2000 | 0.004000 | 15.6% | 500 | adapter_2bet |
| 2 | `biglotto_triple_strike` | PRODUCTION | 0.0500 | +0.0131 | 1.1380 | 0.000000 | 17.6% | 500 | adapter_2bet |
| 3 | `biglotto_ts3_markov_4bet_w30` | TIERB_DRYRUN_VALIDATED | 0.0500 | +0.0131 | 1.1380 | 0.000000 | 17.6% | 500 | adapter_2bet |

#### Bet count = 3

Random M3+ baseline (3-bet): `0.0549`

| Rank | strategy_id | lifecycle | M3+ | vs baseline | avg_hit | M4+ | zero_hit% | n | source |
|------|-------------|-----------|-----|-------------|---------|-----|-----------|---|--------|
| 1 | `biglotto_echo_aware_3bet` | TIERB_DRYRUN_VALIDATED | 0.0780 | +0.0231 | 1.4420 | 0.006000 | 5.8% | 500 | adapter_3bet |
| 2 | `biglotto_triple_strike` | PRODUCTION | 0.0720 | +0.0171 | 1.4200 | 0.002000 | 5.2% | 500 | adapter_3bet |
| 3 | `biglotto_ts3_markov_4bet_w30` | TIERB_DRYRUN_VALIDATED | 0.0720 | +0.0171 | 1.4200 | 0.002000 | 5.2% | 500 | adapter_3bet |

#### Bet count = 5

Random M3+ baseline (5-bet): `0.0898`

*No strategies with valid data for this combination.*

### Window = Latest 1500 draws

#### Bet count = 1

Random M3+ baseline (1-bet): `0.0186`

| Rank | strategy_id | lifecycle | M3+ | vs baseline | avg_hit | M4+ | zero_hit% | n | source |
|------|-------------|-----------|-----|-------------|---------|-----|-----------|---|--------|
| 1 | `biglotto_deviation_2bet` | PRODUCTION | 0.0240 | +0.0054 | 0.7583 | 0.000668 | 42.1% | 1498 | db_rows |
| 2 | `ts3_regime_3bet` | PRODUCTION | 0.0240 | +0.0054 | 0.7216 | 0.002003 | 44.2% | 1498 | db_rows |
| 3 | `biglotto_triple_strike` | PRODUCTION | 0.0240 | +0.0054 | 0.7216 | 0.002003 | 44.2% | 1498 | db_rows |

#### Bet count = 2

Random M3+ baseline (2-bet): `0.0369`

| Rank | strategy_id | lifecycle | M3+ | vs baseline | avg_hit | M4+ | zero_hit% | n | source |
|------|-------------|-----------|-----|-------------|---------|-----|-----------|---|--------|
| 1 | `biglotto_triple_strike` | PRODUCTION | 0.0493 | +0.0124 | 1.1600 | 0.003333 | 16.3% | 1500 | adapter_2bet |
| 2 | `biglotto_ts3_markov_4bet_w30` | TIERB_DRYRUN_VALIDATED | 0.0493 | +0.0124 | 1.1600 | 0.003333 | 16.3% | 1500 | adapter_2bet |
| 3 | `biglotto_echo_aware_3bet` | TIERB_DRYRUN_VALIDATED | 0.0447 | +0.0077 | 1.2073 | 0.002000 | 16.2% | 1500 | adapter_2bet |

#### Bet count = 3

Random M3+ baseline (3-bet): `0.0549`

| Rank | strategy_id | lifecycle | M3+ | vs baseline | avg_hit | M4+ | zero_hit% | n | source |
|------|-------------|-----------|-----|-------------|---------|-----|-----------|---|--------|
| 1 | `biglotto_triple_strike` | PRODUCTION | 0.0680 | +0.0131 | 1.4200 | 0.004667 | 5.1% | 1500 | adapter_3bet |
| 2 | `biglotto_ts3_markov_4bet_w30` | TIERB_DRYRUN_VALIDATED | 0.0680 | +0.0131 | 1.4200 | 0.004667 | 5.1% | 1500 | adapter_3bet |
| 3 | `biglotto_echo_aware_3bet` | TIERB_DRYRUN_VALIDATED | 0.0647 | +0.0098 | 1.4600 | 0.004000 | 5.1% | 1500 | adapter_3bet |

#### Bet count = 5

Random M3+ baseline (5-bet): `0.0898`

*No strategies with valid data for this combination.*

## 6. Stable Top Performers

Strategies appearing in top 3 across ≥2 observation windows:

**1-bet**: `ts3_regime_3bet` (4/4 windows), `biglotto_triple_strike` (3/4 windows), `bet2_fourier_expansion_biglotto` (3/4 windows), `biglotto_deviation_2bet` (2/4 windows)
**2-bet**: `biglotto_triple_strike` (4/4 windows), `biglotto_ts3_markov_4bet_w30` (4/4 windows), `biglotto_echo_aware_3bet` (4/4 windows)
**3-bet**: `biglotto_triple_strike` (4/4 windows), `biglotto_ts3_markov_4bet_w30` (4/4 windows), `biglotto_echo_aware_3bet` (4/4 windows)
**5-bet**: *(no strategy appeared in top 3 across ≥2 windows)*

## 7. Short-Window-Only Performers Warning

*No short-window-only performers detected.*

## 8. Rejected/Offline Replay-Only Caveat

Rejected/offline strategies are benchmarked for analysis only. Their performance figures do NOT imply promotion eligibility. Lifecycle remains unchanged. These strategies stay REJECTED/OFFLINE.

## 9. No-Data / Unsupported Policy

- Bet count variants exceeding a strategy's native_bets are marked **UNSUPPORTED** unless a valid multi-bet adapter exists.
- No bet counts are fabricated or duplicated to fill missing variants.
- Blocked strategies (adapter-partial, superseded) are listed in Section 3b with explicit blockers.

## 10. Recommended Next Steps

**Recommendation**: `P94B_CONTROLLED_BENCHMARK_REVIEW`

Review top performers across windows. If any strategy shows stable improvement across w500/w1500, proceed to P95 dry-run/apply plan.

If ≥1 strategy shows stable M3+ improvement across w500+w1500 vs random baseline, proceed to:
- **P94B** Controlled Benchmark Review (validate top performers with stricter statistical tests)
- **P95** Selected Strategy Dry-Run/Apply Plan (if P94B confirms a clear winner)

