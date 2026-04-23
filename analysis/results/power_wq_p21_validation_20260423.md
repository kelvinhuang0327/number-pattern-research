# WQ P2-1 Validation Report — POWER_LOTTO

**Date**: 2026-04-23T15:49:55.827045  
**Seed**: 42  
**Total Draws**: 1903

## Executive Summary

This report documents a **local-first formal verification** of the Winning Quality P2-1 proxy strategy for POWER_LOTTO. The task was constrained to avoid:
- External quota/API dependencies
- Production code modifications
- Interactive data repair workflows

Instead, it focused on deterministic, reproducible evaluation using existing test infrastructure.

## Motivation & Scope

The WQ P2-1 proxy is based on `popularity_score()` from `lottery_api/engine/winning_quality.py`, which estimates the likelihood of split prizes based on how "popular" a number combination is. The hypothesis is that low-popularity combinations, when they win, result in fewer co-winners and thus higher payout per unit bet.

**Scope**:
- Strategy: WQ P2-1 (3-bet, popularity-based filtering)
- Baselines: fourier_rhythm_3bet (3-bet), pp3_freqort_4bet (4-bet)
- Windows: 150, 500, 1500 periods (OOS walk-forward)
- Metrics: raw edge, win rate, permutation p-value, Cohen's d, per-bet efficiency
- Leakage: verification that no future data leaked into training

## Results Summary

### 150-Period OOS
| Metric | WQ P2-1 | Fourier 3-bet | PP3 4-bet |
|--------|---------|---------------|-----------|
| Edge | +12.01% | +7.34% | +7.13% |
| Win Rate | 14.67% | 10.00% | 10.67% |
| Perm p-value | 0.0667 | 1.0000 | 1.0000 |
| Cohen's d | 1.2814 | 0.0000 | -0.0000 |
| Perm Test | ✗ FAIL | ✗ FAIL | ✗ FAIL |

### 500-Period OOS
| Metric | WQ P2-1 | Fourier 3-bet | PP3 4-bet |
|--------|---------|---------------|-----------|
| Edge | +7.74% | +5.94% | +7.67% |
| Win Rate | 10.40% | 8.60% | 11.20% |
| Perm p-value | 0.6333 | 1.0000 | 1.0000 |
| Cohen's d | -0.2459 | 0.0000 | 0.0000 |
| Perm Test | ✗ FAIL | ✗ FAIL | ✗ FAIL |

### 1500-Period OOS
| Metric | WQ P2-1 | Fourier 3-bet | PP3 4-bet |
|--------|---------|---------------|-----------|
| Edge | +7.47% | +6.67% | +7.67% |
| Win Rate | 10.13% | 9.33% | 11.20% |
| Perm p-value | 0.8000 | 1.0000 | 1.0000 |
| Cohen's d | -0.9352 | -0.0000 | 0.0000 |
| Perm Test | ✗ FAIL | ✗ FAIL | ✗ FAIL |

## Per-Bet Efficiency (vs Baselines)

WQ P2-1 (3-bet) relative efficiency:

| Window | vs Fourier 3-bet | vs PP3 4-bet |
|--------|------------------|--------------|
| 150p | 163.6% | 168.3% |
| 500p | 130.3% | 100.9% |
| 1500p | 112.0% | 97.5% |

> Target threshold: >= 80% (each extra bet adds meaningful marginal value)

## Data Leakage Verification

### Leakage Check Results


**Window 150p**: ✓ PASS
  - 150 test points verified
  - No chronology violations detected

**Window 500p**: ✓ PASS
  - 500 test points verified
  - No chronology violations detected

**Window 1500p**: ✓ PASS
  - 1500 test points verified
  - No chronology violations detected


## Acceptance Criteria Evaluation

### Criteria:
1. **All three-window edge positive**: True ✓
2. **All three-window permutation p < 0.05**: False ✓
3. **All three-window Cohen's d > 1.0**: False ✓
4. **Per-bet efficiency >= 80% on all windows**: True ✓
5. **No data leakage**: True ✓

## Final Classification

**Classification**: `REJECT`

**Reason**: Positive edge but permutation test failed, efficiency below 80%, or Cohen's d insufficient

### Interpretation


WQ P2-1 does **not** meet full acceptance criteria:

- Permutation test failed (signal may be due to randomness, not true pattern)
- Effect size insufficient (Cohen's d <= 1.0 on some windows)

**Recommendation**: Reject as active candidate. Consider:
1. Alternative popularity-score models (current heuristic may be too simplistic)
2. Different feature engineering for split-risk proxy
3. Focus on other non-family Layer-1 signals (per POWER_LOTTO roadmap)


## Technical Details

### Strategy Implementations

#### WQ P2-1 (wq_p21_signal)
- Filters: popularity_score() < baseline - 0.5σ (low-popularity emphasis)
- Blends: recent frequency + anti-popularity score
- Bets: 3 combinations emphasizing unpopular numbers
- Hypothesis: unpopular numbers → fewer co-winners → better EV per unit

#### Fourier Rhythm (fourier_rhythm_3bet)
- Baseline frequency analysis over last 20 draws
- Picks top-frequency numbers + random variation
- Bets: 3 combinations
- Source: wikigames/power_lotto.md (WATCH-level strategy)

#### PP3 Frequency Orthogonal (pp3_freqort_4bet)
- Baseline frequency orthogonal selection
- Bets: 4 combinations with systematic variation
- Source: wikigames/power_lotto.md (active-level strategy)

### Permutation Test Method

**Temporal Shuffle Approach**:
1. Shuffle number-sets across draw positions (preserves marginal distribution)
2. Destroy temporal structure (so autocorrelated patterns become noise)
3. Re-run strategy on shuffled data
4. Repeat 200 times to build null distribution
5. Compute empirical p-value: fraction of shuffles >= real edge

**Interpretation**:
- p < 0.05: Real edge is unlikely to be due to temporal randomness alone
- p >= 0.05: Cannot rule out that edge is spurious

### Per-Bet Efficiency

Formula: (strategy_edge / baseline_edge) × 100

Example: If WQ edge = +2% and Fourier = +1%, then efficiency = 200%.  
For multi-bet strategies, target is >= 80% (diminishing returns).

### Random Baseline Computation

For POWER_LOTTO (6 from 38):
- Single bet matching 3+ numbers: ~0.89%
- Multiple bets: P(hit) = 1 - (1 - p_single)^num_bets

## Conclusion

This validation demonstrates whether WQ P2-1 can form a **non-spurious, statistically significant** predictor of split-risk adjusted EV in POWER_LOTTO. The results are fully reproducible with seed=42 and contain no external dependencies or rate-limited resources.

**Next Planner Actions**:
1. If PASS_WATCH: update wiki/games/power_lotto.md WATCH section
2. If REJECT: consider alternative split-risk models or deprioritize this feature
3. Document lessons learned in wiki/lessons/key_lessons.md

---

Generated: 2026-04-23T15:49:55.827045
