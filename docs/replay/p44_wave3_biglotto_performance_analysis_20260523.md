# P44 Wave 3 BIG_LOTTO Performance Analysis

**Date**: 2026-05-23  
**Classification**: P44_WAVE3_BIGLOTTO_PERFORMANCE_ANALYSIS_MERGED_TO_MAIN  
**Branch**: p44-wave3-biglotto-performance-analysis  
**Production rows**: 37960 (unchanged, read-only analysis)

---

## Scope

P44 is a read-only performance analysis of 6 Wave 3 BIG_LOTTO strategies loaded in P43
(28960 → 37960 rows, +9000 rows, 6 strategies × 1500 draws each).

**Governance**: No DB writes, no lifecycle changes, no ONLINE promotion. Analysis only.

---

## BIG_LOTTO Baseline Expectations (6/49)

Each strategy predicts 6 numbers from a pool of 49. The random baseline is:

| Metric | Value |
|--------|-------|
| Expected avg hits per draw | 6 × 6/49 = **0.7347** |
| P(0 hits) | ≈ 43.5% |
| P(1 hit) | ≈ 39.8% |
| P(2 hits) | ≈ 14.3% |
| P(3 hits) | ≈ 2.1% |
| P(4+ hits) | ≈ 0.1% |

---

## L91 Signal Boundary Context

Per **L91** (BIG_LOTTO signal boundary research, 2026-03-16):

- 6 independent randomness tests all PASS (Shannon entropy, Ljung-Box, Chi-squared, Runs, Pairwise, Permutation Entropy)
- Maximum mutual information observed: 0.006 bits (1.18% of baseline entropy)
- 10K MC simulations: 99th percentile edge = +0.778%; best observed = +0.414% (within noise)
- Detection power analysis: minimum detectable edge at N=1817 = +0.789% (never observed)
- 1000 random strategies: 0.0% survived Bonferroni/BH correction at p<0.05
- **Conclusion**: BIG_LOTTO 49C6 is indistinguishable from a fair random process

All Wave 3 strategies are therefore expected to show near-random performance. Any positive edge
in short windows is consistent with sampling variance, not a genuine signal.

---

## Wave 3 Strategies Analyzed

| # | Strategy ID | Total Rows | Lifecycle |
|---|-------------|-----------|-----------|
| 1 | markov_single_biglotto | 1500 | DRY_RUN (replay_status=PREDICTED) |
| 2 | markov_2bet_biglotto | 1500 | DRY_RUN (replay_status=PREDICTED) |
| 3 | bet2_fourier_expansion_biglotto | 1500 | DRY_RUN (replay_status=PREDICTED) |
| 4 | fourier30_markov30_biglotto | 1500 | DRY_RUN (replay_status=PREDICTED) |
| 5 | cold_complement_biglotto | 1500 | DRY_RUN (replay_status=PREDICTED) |
| 6 | coldpool15_biglotto | 1500 | DRY_RUN (replay_status=PREDICTED) |

---

## Three-Window Performance Tables

### Permutation Test Config
- Method: Monte Carlo null (Binomial draws, n_perm=2000, seed=42)
- Null model: hit_count ~ Binomial(6, 6/49)
- Gate: PASS if p_value < 0.05

### markov_single_biglotto

| Window | n | Avg Hits | Edge | Edge% | Perm p | Gate | Sharpe |
|--------|---|----------|------|-------|--------|------|--------|
| 150 | 150 | 0.6867 | -0.0480 | -6.54% | 0.7825 | FAIL | -0.0671 |
| 500 | 500 | 0.6920 | -0.0427 | -5.81% | 0.9030 | FAIL | -0.0582 |
| 1500 | 1500 | 0.7280 | -0.0067 | -0.91% | 0.6380 | FAIL | -0.0089 |

### markov_2bet_biglotto

| Window | n | Avg Hits | Edge | Edge% | Perm p | Gate | Sharpe |
|--------|---|----------|------|-------|--------|------|--------|
| 150 | 150 | 0.6867 | -0.0480 | -6.54% | 0.7825 | FAIL | -0.0671 |
| 500 | 500 | 0.6920 | -0.0427 | -5.81% | 0.9030 | FAIL | -0.0582 |
| 1500 | 1500 | 0.7280 | -0.0067 | -0.91% | 0.6380 | FAIL | -0.0089 |

*Note: markov_single and markov_2bet share identical hit_count sequences, indicating they use
the same underlying number selection logic (single bet vs two bets from same pool).*

### bet2_fourier_expansion_biglotto

| Window | n | Avg Hits | Edge | Edge% | Perm p | Gate | Sharpe |
|--------|---|----------|------|-------|--------|------|--------|
| 150 | 150 | 0.7600 | +0.0253 | +3.44% | 0.3640 | FAIL | +0.0313 |
| 500 | 500 | 0.7200 | -0.0147 | -2.00% | 0.6855 | FAIL | -0.0189 |
| 1500 | 1500 | 0.7240 | -0.0107 | -1.46% | 0.7090 | FAIL | -0.0139 |

### fourier30_markov30_biglotto

| Window | n | Avg Hits | Edge | Edge% | Perm p | Gate | Sharpe |
|--------|---|----------|------|-------|--------|------|--------|
| 150 | 150 | 0.7333 | -0.0014 | -0.19% | 0.5315 | FAIL | -0.0019 |
| 500 | 500 | 0.7300 | -0.0047 | -0.64% | 0.5685 | FAIL | -0.0066 |
| 1500 | 1500 | 0.7213 | -0.0134 | -1.82% | 0.7455 | FAIL | -0.0180 |

### cold_complement_biglotto

| Window | n | Avg Hits | Edge | Edge% | Perm p | Gate | Sharpe |
|--------|---|----------|------|-------|--------|------|--------|
| 150 | 150 | 0.7467 | +0.0120 | +1.63% | 0.4440 | FAIL | +0.0167 |
| 500 | 500 | 0.7820 | +0.0473 | +6.44% | 0.1040 | FAIL | +0.0611 |
| 1500 | 1500 | 0.7353 | +0.0006 | +0.09% | 0.5065 | FAIL | +0.0009 |

### coldpool15_biglotto

| Window | n | Avg Hits | Edge | Edge% | Perm p | Gate | Sharpe |
|--------|---|----------|------|-------|--------|------|--------|
| 150 | 150 | 0.7467 | +0.0120 | +1.63% | 0.4440 | FAIL | +0.0167 |
| 500 | 500 | 0.7820 | +0.0473 | +6.44% | 0.1040 | FAIL | +0.0611 |
| 1500 | 1500 | 0.7353 | +0.0006 | +0.09% | 0.5065 | FAIL | +0.0009 |

*Note: cold_complement and coldpool15 share identical hit_count sequences.*

---

## Edge Summary (1500-Window)

| Strategy | Avg Hits | Edge | Edge% | Perm p | Gate |
|----------|----------|------|-------|--------|------|
| markov_single_biglotto | 0.7280 | -0.0067 | -0.91% | 0.6380 | FAIL |
| markov_2bet_biglotto | 0.7280 | -0.0067 | -0.91% | 0.6380 | FAIL |
| bet2_fourier_expansion_biglotto | 0.7240 | -0.0107 | -1.46% | 0.7090 | FAIL |
| fourier30_markov30_biglotto | 0.7213 | -0.0134 | -1.82% | 0.7455 | FAIL |
| cold_complement_biglotto | 0.7353 | +0.0006 | +0.09% | 0.5065 | FAIL |
| coldpool15_biglotto | 0.7353 | +0.0006 | +0.09% | 0.5065 | FAIL |
| **Baseline** | **0.7347** | 0.0000 | 0.00% | — | — |

Closest to baseline: cold_complement / coldpool15 at +0.09%. All within noise per L91.

---

## Promotion Candidate Assessment

**Promotion candidates**: NONE (empty list)

**Criteria for promotion consideration**:
1. Three-window all positive edges (150 / 500 / 1500)
2. Best permutation p < 0.05
3. McNemar gate vs existing production strategy

| Strategy | Three-Window Positive | Best Perm p | Promotion |
|----------|----------------------|-------------|-----------|
| markov_single_biglotto | No (all negative) | 0.6380 | Keep DRY_RUN |
| markov_2bet_biglotto | No (all negative) | 0.6380 | Keep DRY_RUN |
| bet2_fourier_expansion_biglotto | No (w150 positive, w500/w1500 negative) | 0.3640 | Keep DRY_RUN |
| fourier30_markov30_biglotto | No (all negative) | 0.5315 | Keep DRY_RUN |
| cold_complement_biglotto | No (w1500 barely +0.09%) | 0.1040 | Keep DRY_RUN |
| coldpool15_biglotto | No (w1500 barely +0.09%) | 0.1040 | Keep DRY_RUN |

Result is fully consistent with L91 — BIG_LOTTO 49C6 signal space is exhausted.

---

## McNemar Gate

**Status**: INCONCLUSIVE_NO_BASELINE_STRATEGY for all Wave 3 strategies.

Wave 3 strategies are first-generation BIG_LOTTO entries with no head-to-head comparison
strategy established. The existing production strategies (regime_2bet, ts3_regime_3bet, etc.)
operate under different bet-count assumptions. McNemar gate requires a matched-pairs
production comparison; none of the Wave 3 strategies meet this precondition.

---

## Permutation Test Results Summary

All 6 strategies × all 3 windows = 18 tests. All 18 returned FAIL (p >> 0.05).

- Best p-value observed: 0.1040 (cold_complement / coldpool15, w500)
- All far above the p < 0.05 gate
- Consistent with MC noise envelope per L91 (99th pct = +0.778% edge)

---

## Recommended Next Phase

1. **Maintain DRY_RUN**: All 6 strategies remain at replay_status=PREDICTED.  
   No lifecycle advancement is warranted under L91.

2. **Maintenance mode**: BIG_LOTTO research is formally in maintenance mode per L91 / L90.  
   Continue monitoring production strategies (regime_2bet, ts3_regime_3bet) via RSM.

3. **Wave 3 closure**: P44 formally closes the Wave 3 BIG_LOTTO analysis loop.  
   Next trigger for BIG_LOTTO research: external rule change, draw anomaly, or
   discovery of a new signal class not covered by H001–H010.

4. **System health**: Production rows stable at 37960. All drift guards PASS.

---

## Files

| File | Description |
|------|-------------|
| `scripts/p44_wave3_biglotto_performance_analysis.py` | Read-only analysis script |
| `outputs/replay/p44_wave3_biglotto_performance_analysis_20260523.json` | Full results JSON |
| `tests/test_p44_wave3_biglotto_performance_analysis.py` | Test suite |
| `docs/replay/p44_wave3_biglotto_performance_analysis_20260523.md` | This document |
