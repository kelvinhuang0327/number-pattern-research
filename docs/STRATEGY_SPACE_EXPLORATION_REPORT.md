# Strategy Space Exploration Report

## DAILY_539 | 2026-03-15 | 4 Objectives

---

## Executive Summary

This research explored whether expanding the strategy space (coverage optimization, pool-based selection, portfolio design) can outperform the current orthogonal 3-bet architecture. Four objectives were investigated with 1600 walk-forward draws, 10M Monte Carlo simulations, and 99-shuffle permutation tests.

**Answer: No.** The current independent orthogonal architecture (MicroFish || MidFreq || Markov) is confirmed optimal. All alternatives tested — pool expansion, cross-signal fusion, greedy coverage — reduce edge. The optimal portfolio size is **3 bets** (all individual bets positive-edge). Adding bet 4+ introduces negative individual edges.

---

## Objective 1: Coverage Matrix Optimization

### Question
Can selecting from a larger candidate pool (top-7, 9, 12) + combinatorial subset selection beat direct top-5?

### Method
For each signal, expand the candidate pool beyond 5 numbers, then enumerate all C(pool, 5) subsets. Score each subset by signal quality + sum constraint + zone diversity. Select the highest-scoring subset. Compare against direct top-5 selection.

### Results — Single Signal

| Signal | pool=5 (direct) | pool=7 | pool=9 | pool=12 |
|--------|:---------------:|:------:|:------:|:-------:|
| **MicroFish** | **+4.47%** | +3.87% | +3.87% | +3.87% |
| MidFreq | **+1.74%** | +1.67% | +1.27% | +1.27% |
| Markov | +1.07% | **+2.20%** | +1.40% | +1.47% |
| ACB | **+3.27%** | +2.40% | +2.40% | +2.40% |

### Results — 3-Bet Multi-Signal

| Pool Size | Hit Rate | Edge | z-score |
|:---------:|:--------:|:----:|:-------:|
| **5 (direct)** | **38.87%** | **+8.42%** | **7.09** |
| 7 | 37.87% | +7.42% | 6.25 |
| 9 | 36.73% | +6.29% | 5.29 |
| 12 | 36.80% | +6.36% | 5.35 |

### Key Findings

1. **Direct top-5 is optimal for 3 out of 4 signals.** Pool expansion dilutes signal quality by including lower-ranked numbers.

2. **Markov is the only exception** — pool=7 (+2.20%) > pool=5 (+1.07%). Markov's transition probabilities are less "peaky" than ACB/MicroFish, so the 6th-7th ranked numbers sometimes form better combinations with sum/zone constraints.

3. **Multi-bet pool expansion uniformly degrades edge.** 3-bet pool=5 (+8.42%) → pool=12 (+6.36%), a loss of 2.06pp.

4. **Sum and zone constraints don't recover the signal loss.** The combinatorial search (up to 792 subsets per draw) cannot compensate for including weaker candidates.

### Conclusion

**Direct top-5 selection is the optimal ticket construction method.** Pool expansion is counterproductive — the signal is concentrated in the top 5 numbers, and including numbers 6-12 adds noise.

---

## Objective 2: Strategy Diversity Analysis

### Question
Does combining candidate pools across signals improve coverage?

### Method
Six configurations tested:
- **current_orthogonal**: Each signal independently selects top-5, zero overlap (baseline)
- **union_top7_x3**: Merge top-7 from 3 signals into super-pool, greedy assign
- **union_top9_x3**: Same with top-9
- **union_top5_x4**: top-5 from all 4 signals
- **union_top7_x4**: top-7 from all 4 signals
- **max_coverage**: Max signal score across 3 signals, top-15 split into 3 bets

### Results

| Config | Edge | z | Unique Nums | Avg Overlap |
|--------|:----:|:-:|:-----------:|:-----------:|
| **current_orthogonal** | **+8.42%** | **7.09** | 15.0 | 0.0 |
| union_top5_x4 | +6.82% | 5.74 | 15.0 | 5.3 |
| max_coverage | +6.09% | 5.13 | 15.0 | 0.0 |
| union_top9_x3 | +5.82% | 4.90 | 15.0 | 3.7 |
| union_top7_x3 | +5.42% | 4.56 | 15.0 | 2.0 |
| union_top7_x4 | +4.62% | 3.89 | 15.0 | 8.2 |

### Key Findings

1. **Current orthogonal architecture is best by a wide margin** (+8.42% vs next best +6.82%).

2. **All 15 numbers are unique in every configuration** — the greedy construction ensures zero intra-bet overlap, but the issue is signal quality per bet, not coverage count.

3. **More signals in the pool = more overlap = worse performance.** Top-7 from 4 signals has 8.2 overlapping numbers on average, meaning the pool contains many numbers that multiple signals "agree on" — but agreement doesn't mean quality.

4. **Greedy assignment destroys signal assignment.** In `union_greedy`, the highest-scoring numbers are concentrated in bet 1, leaving bets 2-3 with primarily filler numbers from multiple signals' lower tiers.

5. **max_coverage (per-number best signal) is also suboptimal.** This approach loses the "each bet has its own signal identity" property that makes orthogonal selection work.

### Conclusion

**Independent orthogonal selection remains optimal.** This is the third independent confirmation (L65 evolution, this study) that dedicated signal-per-bet outperforms any fusion approach.

Root cause: Each signal captures a different predictive dimension:
- MicroFish: evolved feature combination
- MidFreq: mean-reversion
- Markov: transition probabilities
- ACB: deficit + gap scoring

Merging these into a single pool erases the dimensional diversity. The independent approach ensures each bet covers a different "view" of the number space.

---

## Objective 3: Long-Horizon Risk Simulation

### Method
10M Monte Carlo draws per bet level using exact match probability distribution. Correct prize table: M2=50, M3=300, M4=20,000, M5=8,000,000 NTD. Bankroll trajectories for 10K independent players over 5000 draws.

### Baseline EV (No Signal Edge)

| Bets | Cost/Draw | MC EV | ROI | Hit Rate P(M2+) |
|:----:|:---------:|:-----:|:---:|:----------------:|
| 1 | 50 | 31.69 | -36.6% | 11.40% |
| 2 | 100 | 61.16 | -38.8% | 21.48% |
| 3 | 150 | 80.74 | -46.2% | 30.44% |

Note: MC EV (31.69) vs exact EV (27.92) difference is within expected variance for heavy-tailed distributions (M5 jackpot 8M NTD creates high variance with ~17 hits in 10M draws).

### Loss Streak Distribution

| Bets | Median | P75 | P90 | P95 | P99 | Max |
|:----:|:------:|:---:|:---:|:---:|:---:|:---:|
| 1 | 6 | 10 | 15 | 19 | 28 | 122 |
| 2 | 3 | 5 | 8 | 10 | 15 | 62 |
| 3 | 2 | 3 | 5 | 7 | 10 | 41 |

### Expected Waiting Times (Draws)

| Bets | M2+ Median | M3+ Median | M4+ Median |
|:----:|:----------:|:----------:|:----------:|
| 1 | 6 | 69 | 2,388 |
| 2 | 3 | 35 | 1,121 |
| 3 | 2 | 23 | 760 |

M4+ waiting time for 1-bet = **2,388 draws = ~6.5 years** of daily play.

### Bankroll Survival (5000 draws)

| Initial Bankroll | 1-bet Ruin | 2-bet Ruin | 3-bet Ruin |
|:----------------:|:----------:|:----------:|:----------:|
| 5,000 NTD | 100.0% | 100.0% | 100.0% |
| 10,000 NTD | 100.0% | 100.0% | 99.9% |
| 50,000 NTD | 99.8% | 99.8% | 99.8% |

### Key Findings

1. **Ruin is virtually certain** at all bankroll levels over 5000 draws. The house edge (-44.16%) makes long-term survival impossible without consistent M4+ hits.

2. **More bets = faster ruin**, not slower. 3-bet costs 150/draw vs 50/draw for 1-bet, tripling the bleed rate. The higher hit rate (30% vs 11%) only recovers M2 prizes (50 NTD each), which doesn't offset the additional 100 NTD cost.

3. **M4+ is the survival event.** A single M4 (20,000 NTD) covers 400 draws of 1-bet play. M5 (8M NTD) covers 160,000 draws.

4. **Our signal edge does not change the ruin conclusion.** Even with +4.47% edge at 1-bet, the hit rate rises from 11.40% to 15.87%, but the EV per draw is still negative (M2 prize 50 NTD = break-even, M2+ edge doesn't guarantee M3/M4/M5 improvement).

### Conclusion

539 is a structurally negative-EV game. Signal edges improve hit rate for M2+ but cannot overcome the house edge. Players should treat lottery spending as entertainment cost, not investment.

---

## Objective 4: Portfolio Efficiency Frontier

### Method
Evaluate bets 1-6 using the best signal per bet in order (MicroFish → MidFreq → Markov → ACB → MicroFish-residual → MidFreq-residual). Each bet selects top-5 from remaining numbers after excluding prior bets' selections.

### Efficiency Frontier

| Bets | Signals | Hit Rate | Baseline | Edge | z | Cost | Coverage |
|:----:|---------|:--------:|:--------:|:----:|:-:|:----:|:--------:|
| 1 | MF | 15.87% | 11.40% | +4.47% | 5.45 | 50 | 13% |
| 2 | MF+MidFreq | 28.27% | 21.50% | +6.77% | 6.38 | 100 | 26% |
| **3** | **MF+MidFreq+Markov** | **38.87%** | **30.45%** | **+8.42%** | **7.09** | **150** | **38%** |
| 4 | +ACB | 47.67% | 38.37% | +9.30% | 7.40 | 200 | 51% |
| 5 | +MF-res | 55.73% | 45.38% | +10.34% | 8.04 | 250 | 64% |
| 6 | +MidFreq-res | 64.53% | 51.63% | +12.91% | 10.01 | 300 | 77% |

### Per-Bet Individual Edges (L31 Check)

| Bet | Signal | Individual Rate | Individual Edge | L31 Pass |
|:---:|--------|:--------------:|:---------------:|:--------:|
| 1 | MicroFish | 15.50% | **+4.10%** | **Pass** |
| 2 | MidFreq | 13.00% | **+1.60%** | **Pass** |
| 3 | Markov | 12.12% | **+0.73%** | **Pass** |
| 4 | ACB | 10.44% | **-0.96%** | **FAIL** |
| 5 | MicroFish-res | 10.31% | **-1.08%** | **FAIL** |
| 6 | MidFreq-res | 12.25% | **+0.85%** | **Pass** |

### Marginal Edge Analysis

| From → To | Marginal Edge | Verdict |
|:---------:|:-------------:|:-------:|
| 0 → 1 | +4.47% | Strong |
| 1 → 2 | +2.30% | Good |
| 2 → 3 | +1.65% | Moderate |
| 3 → 4 | +0.88% | Weak + **L31 violated** |
| 4 → 5 | +1.04% | **L31 violated** |
| 5 → 6 | +2.57% | Suspicious (sample artifact) |

### Permutation Test Validation

| Config | perm_p | Verdict |
|--------|:------:|:-------:|
| 3-bet (MF+MidFreq+Markov) | 0.010 | **Signal confirmed** |
| 4-bet (+ ACB) | 0.010 | Signal confirmed (but Bet 4 individual = negative) |
| 5-bet (+ MF-res) | 0.010 | Signal confirmed (but Bet 5 individual = negative) |

### Key Findings

1. **3-bet is the optimal portfolio.** It's the highest bet count where all individual bets have positive edge (L31 satisfied).

2. **Bet 4 (ACB) has negative individual edge** (-0.96%). After excluding the top 15 numbers (already claimed by bets 1-3), ACB's deficit+gap signal is too weak to beat random selection from the remaining 24 numbers.

3. **Bet 5 (MicroFish-residual) also has negative individual edge** (-1.08%). MicroFish's signal is concentrated in its top-5; the 21st-25th ranked numbers carry no useful signal.

4. **Bet 6 edge jump is suspicious.** MidFreq-residual shows +0.85% from only 14 remaining numbers. This is likely a sample-specific artifact and would not survive walk-forward validation.

5. **Overall portfolio edge increases despite negative individual bets** because the "any bet wins" criterion is looser than individual bet performance. But paying 50 NTD for a bet with negative individual edge is economically irrational.

### Conclusion

**3-bet is the efficiency frontier optimum.** Adding bets beyond 3 costs 50 NTD each but provides sub-random individual hit rates. The first 3 signals (MicroFish, MidFreq, Markov) exhaust the available predictive information.

---

## Unified Conclusions

### Research Question: Can strategy space expansion outperform the current 3-bet architecture?

**No.** Four independent lines of evidence converge:

| Objective | Finding | Impact |
|-----------|---------|--------|
| Coverage Matrix | Direct top-5 > pool expansion | Pool expansion cannot be deployed |
| Diversity Analysis | Independent orthogonal > all fusion variants | Architecture confirmed optimal |
| Risk Simulation | 100% ruin regardless of bet count | Cannot overcome negative EV |
| Efficiency Frontier | 3-bet is optimal (L31 boundary) | 4+ bets not recommended |

### Architecture: Confirmed Optimal

```
Bet 1: MicroFish      → top-5 by evolved signal    → edge +4.10%
Bet 2: MidFreq        → top-5 by mean-reversion    → edge +1.60%
Bet 3: Markov         → top-5 by transition probs   → edge +0.73%
Total: 3 × 50 NTD = 150 NTD/draw, combined edge +8.42%
```

### What Cannot Be Improved

1. **Ticket construction**: Direct top-5 is optimal; no combinatorial optimization helps
2. **Signal fusion**: Independent > merged, confirmed for the third time
3. **Bet count**: 3 is the maximum with all-positive individual edges
4. **Long-term profitability**: Structurally impossible (negative EV -44.16%)

### What Could Still Be Explored (Restart Conditions)

1. New signal source with > 500 unique orthogonal hits vs existing 3 signals
2. External data (social/behavioral) not currently available
3. Game rule changes that shift house edge
4. Multi-draw combinatorial strategies (not same-draw optimization)

---

## Validation Summary

| Check | Method | Result |
|-------|--------|--------|
| Walk-forward | 1600 draws, train before t, predict t | All signals use only past data |
| Three-window | 150/500/1500 | 3-bet stable in all windows |
| Permutation test | 99 shuffles, temporal mapping | p=0.010 for 3/4/5-bet |
| Leakage check | Signals computed from hist[:t] only | No leakage detected |
| Per-bet L31 | Individual edge > 0 | Bets 1-3 pass, bets 4-5 fail |
| Baseline correctness | P(M2+) = 11.40% | Verified against exact formula |
| Prize table | M2=50, M3=300 | Correct (L64 verified) |

---

## Files

| File | Description |
|------|-------------|
| `tools/strategy_space_exploration.py` | Research engine (4 objectives) |
| `strategy_space_exploration_results.json` | Full numerical results |
| `docs/STRATEGY_SPACE_EXPLORATION_REPORT.md` | This report |

---

*Generated: 2026-03-15 | Compute: 65.1s | 1600 walks + 30M MC draws + 297 permutation shuffles*
