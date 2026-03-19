# Structural Optimization Research Report
## Beyond Signal Ceiling: 6-Direction Strategy Design Research
### 2026-03-15

---

## Executive Summary

Six structural optimization directions explored beyond the validated signal ceiling (+4.73% 1-bet edge). Key findings:

| Direction | Classification | Finding |
|-----------|---------------|---------|
| 1. Bet Portfolio | **VALIDATED** | Optimal portfolio: 3-bet MF+MidFreq+Markov (+8.22%); 5-bet reaches +10.20% |
| 2. Coverage Matrix | **FUTURE RESEARCH** | Wheeling costs prohibitive; partial coverage not superior to signal-guided picks |
| 3. Anti-Crowd | **REJECTED** | Negligible impact on fixed-prize games; only matters for M5 jackpot (1-in-575K) |
| 4. Cross-Transfer | **WEAK SIGNAL** | ACB transfers weakly to BIG_LOTTO (+0.67%); no robust cross-game signals |
| 5. Kelly Allocation | **VALIDATED** | 539 is the ONLY game with positive Kelly; BIG_LOTTO and POWER_LOTTO are negative EV |
| 6. Game Structure | **VALIDATED** | 539 has +41% ROI (positive EV); BIG_LOTTO needs 1163x jackpot for breakeven |

---

## 1. Bet Portfolio Optimization

### VALIDATED — Optimal Portfolio Structure Found

#### Results

| Config | Bets | Edge | z | Edge/NTD | 150p | 500p | 1500p |
|--------|------|------|---|----------|------|------|-------|
| MicroFish | 1 | +4.60% | 5.61 | 0.0920 | +5.93% | +6.00% | +4.60% |
| **MF+MidFreq** | **2** | **+6.77%** | **6.38** | **0.0677** | +13.17% | +9.90% | +6.77% |
| **MF+MidFreq+Markov** | **3** | **+8.22%** | **6.92** | **0.0548** | +12.88% | +10.95% | +8.22% |
| All 4 | 4 | +9.42% | 7.50 | 0.0471 | +15.62% | +10.22% | +9.42% |
| All + RRF | 5 | +10.20% | 7.93 | 0.0408 | +16.60% | +11.00% | +10.20% |

#### Marginal Utility Curve

```
Bet 1→2: +2.17pp marginal  (47% of first bet's edge)
Bet 2→3: +1.45pp marginal  (31%)
Bet 3→4: +1.20pp marginal  (26%)
Bet 4→5: +0.78pp marginal  (17%)  ← diminishing returns
```

#### Key Findings
1. **MicroFish+MidFreq** is the optimal 2-bet combination (confirmed by McNemar p=0.0423)
2. **MicroFish+MidFreq+Markov** is the new optimal 3-bet (+8.22%), surpassing ACB+Markov+Fourier (+6.70%)
3. Edge/NTD efficiency drops monotonically: 1-bet is most cost-efficient
4. All configurations are three-window STABLE

#### Recommendation
- Budget-constrained: 1-bet MicroFish (best edge/NTD)
- Performance-constrained: 3-bet MF+MidFreq+Markov (best absolute edge with reasonable cost)
- 4+ bets show diminishing returns below 1.5pp marginal

---

## 2. Coverage Matrix Optimization

### FUTURE RESEARCH — Costs Exceed Practical Thresholds

#### 539 (C(39,5) = 575,757 combinations)

| Coverage Target | Bets Needed | Cost (NTD) |
|----------------|-------------|------------|
| 50% hit | 6 | 300 |
| 75% hit | 12 | 600 |
| 90% hit | 20 | 1,000 |
| 95% hit | 25 | 1,250 |
| 99% hit | 39 | 1,950 |

#### Wheeling Systems (539)

| Pool Size | Bets | Cost | P(≥2 in pool) |
|-----------|------|------|---------------|
| 8 | 56 | 2,800 | 26.77% |
| 10 | 252 | 12,600 | 38.12% |
| 12 | 792 | 39,600 | 49.40% |

#### Verdict
Full coverage (28.8M NTD) is unfeasible. Wheeling with pool=10 requires 252 bets (12,600 NTD) for 38.12% M2+ coverage — worse than 5 signal-guided bets (45.4% coverage for 250 NTD). **Signal-guided betting dominates wheeling by 100x cost efficiency.**

---

## 3. Anti-Crowd Strategy

### REJECTED — Negligible Impact

#### Popularity Analysis
- Birthday bias (numbers 1-31) inflates popularity ~1.3x
- Lucky numbers (7, 8) inflated ~1.15x
- High numbers (32+) ~0.85x popularity

#### Split Risk Impact

| Strategy | Expected Jackpot Share |
|----------|----------------------|
| Anti-crowd pick (32-37 range) | ~42% of pot |
| Crowd-favorite pick (5-10 range) | ~3% of pot |
| Difference | NTD 5,309,300 |

#### Verdict
Split risk only affects M5 jackpot (probability 1-in-575,757). For M2/M3/M4 prizes (fixed NTD 300/2,000/20,000), split risk is zero. Since 99.9998% of hits are M2-M4, anti-crowd strategy has **no practical impact**.

---

## 4. Cross-Lottery Signal Transfer

### WEAK SIGNAL — No Robust Cross-Game Signals

#### Transfer Matrix

| Strategy | 539 Edge | BIG_LOTTO Edge | POWER_LOTTO Edge |
|----------|---------|----------------|-----------------|
| ACB | +2.60% (WEAK) | +0.67% (WEAK) | -0.40% (REJECTED) |
| MidFreq | +1.47% (WEAK) | -0.46% (REJECTED) | +0.86% (WEAK) |
| Markov | +1.53% (WEAK) | +0.34% (WEAK) | -0.14% (REJECTED) |

#### Findings
1. ACB shows weak positive transfer to BIG_LOTTO (+0.67%, z=1.93) but fails on POWER_LOTTO
2. MidFreq fails on BIG_LOTTO but shows weak positive for POWER_LOTTO
3. No strategy achieves VALIDATED status (z>1.96 + all-window positive + perm p<0.05) on any cross-game
4. Signal permutation tests all show p=1.0 (block permutation doesn't disturb rate — methodology limitation)

#### Verdict
Signals are **game-specific**. The ACB/MidFreq/Markov signals exploit frequency-deficit and mean-reversion patterns that depend on game-specific number space and draw frequency. Cross-transfer does not produce actionable edge.

---

## 5. Capital Allocation (Kelly)

### VALIDATED — 539 is the Only Positive-EV Game

#### EV per Random Bet

| Game | EV | Cost | ROI | House Edge |
|------|-----|------|-----|-----------|
| **DAILY_539** | **NTD 70.47** | **NTD 50** | **+40.93%** | **-40.93%** |
| BIG_LOTTO | NTD 8.43 | NTD 50 | -83.13% | 83.13% |
| POWER_LOTTO | NTD 8.59 | NTD 100 | -91.41% | 91.41% |

**Critical finding**: 539 is inherently positive EV even **without** any prediction edge. The base EV of NTD 70.47 vs NTD 50 cost means the house edge is **negative** (-40.93%). This is structural: the prize table (M2=300, M3=2000, M4=20000) exceeds the cost.

#### Kelly Prescription (current +4.7% edge)

| Bankroll | Kelly Bets | Cost |
|----------|-----------|------|
| 10,000 NTD | 18 | 900 NTD |
| 50,000 NTD | 93 | 4,650 NTD |
| 100,000 NTD | 186 | 9,300 NTD |

Kelly recommends **9.3% of bankroll** on 539. For BIG_LOTTO and POWER_LOTTO, Kelly prescribes **zero bets** (negative EV even with maximum achievable edge).

---

## 6. Game Structure Exploitation

### VALIDATED — 539 Has Unique Structural Advantage

#### Jackpot Breakeven Analysis

| Game | Base JP | JP for EV=0 | Multiplier |
|------|---------|-------------|-----------|
| **539** | **8M NTD** | **Already positive** | **N/A** |
| BIG_LOTTO | 500K NTD | 582M NTD | 1,163x |
| POWER_LOTTO | 4M NTD | 256M NTD | 64x |

- BIG_LOTTO needs its jackpot to reach NTD 582M before random betting becomes EV-neutral
- POWER_LOTTO needs NTD 256M
- **539 is EV-positive at base prize levels** (no jackpot needed)

#### Statistical Properties

| Property | 539 | BIG_LOTTO | POWER_LOTTO |
|----------|-----|-----------|-------------|
| Draw sum mean (obs/theory) | 99.9/100.0 | 150.2/150.0 | 116.6/117.0 |
| Max freq deviation | 8.21% | 12.82% | 13.68% |
| Consecutive pairs (obs/exp) | 43.7%/43.6% | 50.6%/49.5% | 59.1%/59.9% |
| Uniformity | UNIFORM | NON-UNIFORM | NON-UNIFORM |

539 shows the most uniform frequency distribution (max 8.21% deviation), consistent with its larger sample size (5,810 draws). BIG_LOTTO and POWER_LOTTO show mild non-uniformity within expected sampling variance.

---

## Final Classification

| Direction | Status | Practical Impact |
|-----------|--------|-----------------|
| 1. Portfolio | **VALIDATED** | Deploy 3-bet MF+MidFreq+Markov (+8.22%) |
| 2. Coverage | FUTURE RESEARCH | Signal-guided beats wheeling 100x |
| 3. Anti-Crowd | **REJECTED** | No impact on fixed prizes |
| 4. Transfer | WEAK SIGNAL | Signals are game-specific |
| 5. Kelly | **VALIDATED** | Only bet 539; Kelly f*=9.3% |
| 6. Structure | **VALIDATED** | 539 is uniquely positive EV |

## Actionable Recommendations

1. **Deploy 3-bet MF+MidFreq+Markov** as the new optimal portfolio (replaces ACB+Markov+Fourier)
2. **Concentrate capital on 539** — the only game with positive base EV and validated signal edge
3. **Do not bet BIG_LOTTO or POWER_LOTTO** unless jackpot exceeds breakeven threshold
4. **Kelly allocation**: ~9.3% of bankroll per draw on 539
5. **Skip wheeling/coverage** — signal-guided betting is 100x more cost-efficient
6. **Ignore anti-crowd** — fixed prizes make split risk irrelevant

---

## Deliverables

| File | Content |
|------|---------|
| `tools/structural_optimization.py` | 6-direction research engine |
| `structural_optimization_results.json` | All numerical results |
| `structural_optimization_report.md` | This report |

---

*Generated by Structural Optimization Research Engine v1.0 | 2026-03-15 | 59s computation*
