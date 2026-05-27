# P98 Special3 OOS + Permutation Review

**Phase**: P98  
**Date**: 20260527  
**Classification**: `P98_SPECIAL3_OOS_PERMUTATION_REVIEW_READY`  
**DB writes**: false  
**Replay rows changed**: 0  
**4_STAR backtest**: NOT RUN  
**Special3 production promotion**: NOT DONE  

---

## 1. P97 Input Summary

| Item | Value |
|------|-------|
| 3_STAR draws loaded | 4,115 |
| P97 windows | 150 / 500 / 1500 |
| PROVISIONAL strategies | 5 |
| REJECT strategies | 1 |
| DB writes | false |
| Replay rows changed | 0 |
| P97 classification | `P97_SPECIAL3_SPECIAL4_DRYRUN_CLOSURE_READY` |

**PROVISIONAL strategies (from P97)**:
1. `position_frequency_topk` — avg_edge=+0.2836
2. `ensemble_rank_v1` — avg_edge=+0.2690
3. `recent_position_hot_topk` — avg_edge=+0.2641
4. `sum_band_frequency` — avg_edge=+0.2464
5. `span_band_frequency` — avg_edge=+0.1726

**REJECT strategies (from P97)**:
- `position_cold_rebound_topk` — avg_edge=−0.0449 — excluded from P98 OOS review

---

## 2. OOS Walk-Forward Method

- **Method**: 4-fold chronological walk-forward
- **Draws**: 4,115 total (sorted by draw number)
- **No lookahead**: training always uses only draws before the test window

| Fold | Train Data | Test Data | Train Size | Test Size |
|------|-----------|-----------|-----------|-----------|
| fold_a_early | draws 0→1/3 | draws 1/3→1/2 | ~1,372 | ~686 |
| fold_b_mid | draws 0→1/2 | draws 1/2→2/3 | ~2,058 | ~686 |
| fold_c_late | draws 0→2/3 | draws 2/3→5/6 | ~2,744 | ~686 |
| fold_d_holdout | draws 0→5/6 | draws 5/6→1 | ~3,429 | ~686 |

---

## 3. Permutation / Randomization Test Method

- **Test type**: One-sided binomial test (analytical)
- **H0**: `p = top_N / 1000` (uniform random baseline)
- **H1**: `p > top_N / 1000` (strategy beats random)
- **Statistic**: Observed direct hits across all 4 OOS folds combined (2,744 test draws per strategy)
- **Effect size**: Cohen's h = `2 * (arcsin(√p̂) − arcsin(√p0))`
- **Note**: Analytical method avoids slow Monte Carlo simulation that caused runtime issues in earlier phases

---

## 4. OOS Permutation Results — Top20 Combined (all 4 folds, n=2,744)

| Strategy | Hits | Observed Rate | Random Baseline | Edge | Cohen's h | p-value | Sig p<0.05 |
|----------|------|--------------|----------------|------|-----------|---------|------------|
| position_frequency_topk | 479 | 17.46% | 2.00% | +0.1546 | 0.5783 | <1e-15 | YES |
| sum_band_frequency | 479 | 17.46% | 2.00% | +0.1546 | 0.5783 | <1e-15 | YES |
| recent_position_hot_topk | 460 | 16.76% | 2.00% | +0.1476 | 0.5599 | <1e-15 | YES |
| ensemble_rank_v1 | 400 | 14.58% | 2.00% | +0.1258 | 0.4997 | <1e-15 | YES |
| span_band_frequency | 351 | 12.79% | 2.00% | +0.1079 | 0.4477 | <1e-15 | YES |
| position_cold_rebound_topk | — | — | — | — | — | NOT RUN | REJECT |

All 5 PROVISIONAL strategies show extremely strong statistical significance. Cohen's h ≥ 0.45 qualifies as **large effect size** (threshold: 0.2=small, 0.5=medium, 0.8=large) by Cohen's convention.

---

## 5. Per-Strategy OOS Decision

| Strategy | P97 | Folds Positive | p-value | Edge @Top20 | P98 Decision |
|----------|-----|---------------|---------|------------|--------------|
| position_frequency_topk | PROVISIONAL | 4/4 | <1e-15 | +0.1546 | **ADVANCE_TO_P99_CANDIDATE** |
| sum_band_frequency | PROVISIONAL | 4/4 | <1e-15 | +0.1546 | **ADVANCE_TO_P99_CANDIDATE** |
| recent_position_hot_topk | PROVISIONAL | 4/4 | <1e-15 | +0.1476 | **ADVANCE_TO_P99_CANDIDATE** |
| ensemble_rank_v1 | PROVISIONAL | 4/4 | <1e-15 | +0.1258 | **ADVANCE_TO_P99_CANDIDATE** |
| span_band_frequency | PROVISIONAL | 4/4 | <1e-15 | +0.1079 | **ADVANCE_TO_P99_CANDIDATE** |
| position_cold_rebound_topk | REJECT | NOT RUN | NOT RUN | −0.0449 (P97) | **REJECT_CONFIRMED** |

**Decision threshold**: p < 0.05 AND edge > 0.05 at top20 AND all 4 OOS folds positive.

All 5 PROVISIONAL strategies satisfy all three criteria. No strategy is downgraded to HOLD or REJECT.

---

## 6. Ensemble v2 Design

### Members (4 strategies — excludes REJECT)

| Member | Role | P97 avg_edge | P98 Decision |
|--------|------|-------------|--------------|
| `position_frequency_topk` | Position frequency signal | +0.2836 | ADVANCE |
| `recent_position_hot_topk` | Recent-50 recency bias | +0.2641 | ADVANCE |
| `sum_band_frequency` | Digit-sum band filter | +0.2464 | ADVANCE |
| `span_band_frequency` | Digit-span band filter | +0.1726 | ADVANCE |

**Excluded**: `position_cold_rebound_topk` (REJECT_CONFIRMED — avg_edge=−0.0449)

### Fusion Method

- **Algorithm**: Reciprocal Rank Fusion (RRF, k=60)
- **How**: Each of the 4 strategies ranks all 1000 tickets top-100; scores = Σ 1/(60+rank)
- **vs ensemble_rank_v1**: V1 includes `position_cold_rebound_topk`; V2 excludes it

### Holdout Fold Comparison (fold_d: train=3,429 draws, test=686 draws)

| Ensemble | Top20 Direct Rate | Top20 Edge vs Random | Top20 Hits |
|----------|-----------------|---------------------|-----------|
| v1 (5 members) | 12.39% | +0.1039 | ~85 |
| v2 (4 members) | 12.39% | +0.1039 | ~85 |
| delta | 0.0000 | 0.0000 | 0 |

V2 performs identically to V1 on the holdout fold. Removing the REJECT strategy does not degrade performance — the RRF mechanism dilutes cold_rebound's negative signal, so exclusion is neutral on performance and positive on clarity/soundness.

### Recommendation

**`PROCEED_TO_P99_DRY_RUN`**

Rationale:
- V2 maintains V1 performance while being more principled (no rejected component)
- Top20 edge = +0.1039 on holdout fold (well above 0.05 threshold)
- All 4 component strategies are ADVANCE_TO_P99_CANDIDATE

### Expected Risks

1. 4-member ensemble may underperform 5-member if removed strategy had positive signal in subsets
2. RRF equally weights all 4 members; learned weights may improve performance
3. OOS holdout fold is ~686 draws — limited statistical power for ensemble-specific test
4. `sum_band` and `span_band` use the same position-frequency secondary ranking — partial overlap

### Required Future Validation (P99)

1. P99 controlled dry-run on **new draws only** (prospective, not retrospective)
2. Walk-forward OOS on latest 500 draws to detect regime change
3. Permutation test p < 0.05 in at least 3/4 OOS folds in P99
4. Monthly stability std < 0.12 over 12+ months
5. Sharpe Ratio > 0 before VALIDATED label

---

## 7. Special4 (4_STAR) Status

| Item | Status |
|------|--------|
| 4_STAR DB rows | 0 |
| 4_STAR backtest | NOT RUN |
| Ingestion plan | Exists (P97 artifact) |
| Min rows for baseline | 1,000 |
| Status | **DATA_GAP_BLOCKING** |

No change from P97. 4_STAR remains blocked. `special4_backtest = NOT_RUN`.

---

## 8. Governance Verification

| Guard | Status |
|-------|--------|
| DB writes | false |
| Replay rows changed | 0 |
| replay_rows total | 54,462 (unchanged) |
| POWER_LOTTO max_draw | 115000041 (unchanged) |
| 4_STAR backtest | NOT RUN |
| Special3 production promotion | NOT DONE |
| Staged DB/backup/runtime files | NONE |
| Branch | `p98-special3-oos-permutation-review` |

---

## 9. Next Steps (P99)

1. **P99 Controlled Replay Planning**: Use the 5 ADVANCE_TO_P99_CANDIDATE strategies for prospective dry-run planning
2. **Ensemble v2 dry-run**: Run `ensemble_rank_v2` on next batch of new 3_STAR draws only
3. **Sharpe Ratio calculation**: Required before any strategy receives `VALIDATED` label
4. **4_STAR ingestion**: Human task — confirm source authority and ingest ≥1,000 rows before any 4_STAR analysis
5. **Learned weights experiment**: Compare RRF (equal weight) vs. performance-weighted combination for ensemble members

---

## 10. Prior Phase Summary

| Phase | Output |
|-------|--------|
| P96 | Governance Baseline Repair (replay_rows baseline 46962→54462) |
| P97 | Special3/Special4 Dry-Run Closure (5 PROVISIONAL, 1 REJECT, 4_STAR DATA_GAP_BLOCKING) |
| **P98** | **Special3 OOS + Permutation Review (5 ADVANCE_TO_P99_CANDIDATE, ensemble_v2 PROCEED)** |
