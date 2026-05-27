# P106 Special3 Prospective Evaluation Rerun

**Phase**: P106  
**Date**: 2026-05-27  
**Author**: Autonomous Agent  
**Status**: COMPLETE  
**Classification**: `P106_SPECIAL3_PROSPECTIVE_EVALUATION_PARTIAL`  

---

## PROJECT_CONTEXT_LOCK

```
PROJECT  : LotteryNew Special3 Prediction Research
PHASE    : P106 — Prospective Evaluation Rerun
SCOPE    : 3_STAR lottery only (Special3 subset)
DB       : lottery_api/data/lottery_v2.db  (READ-ONLY)
REPLAY_ROWS : 54462  (unchanged before and after)
DB_WRITES   : FALSE
PROMOTION   : NONE — no strategy deployed to production
4_STAR_BT   : NOT CONDUCTED — out of scope for P106
STAR3_CAV   : SOURCE_UNKNOWN — rows accepted for Special3 eval only (P105)
```

---

## Source-Unknown Caveat

> **IMPORTANT**: All 3_STAR draws used in this evaluation carry the
> `SOURCE_UNKNOWN` classification from P104/P105. Their origin has not been
> independently verified. The P105 governance decision authorised these rows
> for **Special3 evaluation purposes only**, and that scope is respected here.
> No downstream promotion, production deployment, or cross-lottery inference is
> authorised based solely on this P106 evaluation.

---

## Pre-Flight Status

| Check | Value | Status |
|-------|-------|--------|
| Branch | `p106-special3-prospective-evaluation-rerun` | ✅ |
| Base commit | `ceea6e9` (P105 merge) | ✅ |
| `strategy_prediction_replays` count | 54,462 | ✅ |
| 3_STAR count | 4,179 | ✅ |
| 3_STAR max draw | 115000106 | ✅ |
| 4_STAR count | 2,922 | ✅ |
| 4_STAR max draw | 115000103 | ✅ |
| POWER_LOTTO max draw | 115000041 | ✅ |
| Drift guard | PASS | ✅ |
| Governance guard | PASS | ✅ |

---

## Walk-Forward Methodology

This evaluation uses a strict walk-forward (expanding window) protocol to
avoid any look-ahead bias:

1. **Training set** for prospective draw *d*: all 3_STAR draws with
   `draw_int < d` (strictly less than).
2. **Predictions** are generated fresh for each draw using only the training
   window available at that point in time.
3. **Scoring**: a draw counts as a **HIT** if the actual digit triplet appears
   in the top-N prediction set.
4. **No data from prospective draws** ever enters the training window —
   verified programmatically via assertion in the runner.

| Parameter | Value |
|-----------|-------|
| History end draw | `115000024` |
| First prospective draw | `115000028` (2026-02-02) |
| Last prospective draw | `115000106` (2026-04-30) |
| Draws evaluated | **63** |
| Min training window | 4,116 draws |
| Max training window | 4,178 draws |
| Top-N variants tested | 10, 20, 50, 100 |
| Strategies evaluated | 5 P99 candidates + `ensemble_rank_v2` |

> Note: Draw numbers 115000025–115000027 do not exist in the DB; the first
> actual prospective draw is 115000028.

---

## P99 Candidate Strategy Results (top-20)

| Strategy | Hits | Hit Rate | p-value | Info Ratio | Edge vs Null |
|----------|------|----------|---------|------------|--------------|
| `position_frequency_topk` | 9/63 | 14.29% | 5.0×10⁻⁶ | 6.97 | +12.29 pp |
| `recent_position_hot_topk` | 5/63 | 7.94% | 8.6×10⁻³ | 3.37 | +5.94 pp |
| `sum_band_frequency` | 12/63 | **19.05%** | <1×10⁻⁸ | 9.67 | **+17.05 pp** |
| `span_band_frequency` | 10/63 | 15.87% | <1×10⁻⁸ | 7.87 | +13.87 pp |
| `ensemble_rank_v1` | 9/63 | 14.29% | 5.0×10⁻⁶ | 6.97 | +12.29 pp |
| **Null baseline** | — | **2.00%** | — | — | — |

*Information Ratio = (hit\_rate − p\_null) / √(p\_null·(1−p\_null)) · √N*  
*Edge vs Null = observed hit rate − 2% null baseline*

All 5 P99 candidates beat the random baseline at top20. Four of five achieve
p < 0.01. The strongest single strategy is `sum_band_frequency` at 19.05%.

---

## Ensemble_v2 Results

Members: `position_frequency_topk`, `recent_position_hot_topk`,
`sum_band_frequency`, `span_band_frequency`  
Fusion method: Reciprocal Rank Fusion (k=60)

| Top-N | Hits | Hit Rate | p-value | Info Ratio |
|-------|------|----------|---------|------------|
| Top-10 | 6/63 | 9.52% | 4.2×10⁻⁵ | 6.80 |
| **Top-20** | **9/63** | **14.29%** | **5.0×10⁻⁶** | **6.97** |
| Top-50 | 22/63 | 34.92% | ≈0 | 10.90 |
| Top-100 | 41/63 | 65.08% | ≈0 | 14.57 |

The ensemble_v2 shows consistent positive edge across all top-N variants with
very high statistical significance (p≤4.2×10⁻⁵ at every level).

---

## P100 Readiness Criteria Evaluation

| # | Criterion | Threshold | Actual | Status |
|---|-----------|-----------|--------|--------|
| 1 | Minimum 10 prospective draws | ≥ 10 | **63** | ✅ PASS |
| 2 | Hit rate top20 > 15% | > 15% | 14.29% | ❌ FAIL |
| 3 | p-value < 0.05 (ensemble_v2 top20) | < 0.05 | **5×10⁻⁶** | ✅ PASS |
| 4 | ensemble_v2 edge > 0 at top20 | > 0 | **+12.29 pp** | ✅ PASS |
| 5 | No regime change (10-draw, 3σ) | stable | **stable** | ✅ PASS |
| 6 | Sharpe / Info Ratio > 0 (ensemble_v2 top20) | > 0 | **6.97** | ✅ PASS |

**Criteria passed: 5/6**

### Notes on Failing Criterion

- **Criterion 2 (hit rate top20 > 15%)**: The observed rate of 14.29% is
  0.71 percentage points below the threshold. This corresponds to just **one
  additional hit** in 63 draws being required to cross the threshold
  (10/63 = 15.87% would pass). The strategy has clear statistical significance
  (p=5×10⁻⁶) and strong information ratio (IR=6.97), confirming genuine edge
  that narrowly misses this particular threshold.

---

## Final Classification

```
P106_SPECIAL3_PROSPECTIVE_EVALUATION_PARTIAL
```

**Rationale**: 5 of 6 P100 readiness criteria are satisfied. The ensemble_v2
demonstrates statistically significant edge (p=5×10⁻⁶, IR=6.97) on 63
prospective draws. The sole failing criterion (hit_rate top20 > 15%) misses by
0.71 pp — a margin of one draw. The `PARTIAL` result does **not** authorise
production deployment; it does warrant continuation to P107 with additional
prospective draws to confirm stability.

---

## Governance Checklist

| Item | Status |
|------|--------|
| DB writes | ✅ None (read-only) |
| `strategy_prediction_replays` rows unchanged (54,462) | ✅ Verified |
| Staged files | Whitelist-only (4 files) |
| No lookahead in walk-forward | ✅ Asserted in code |
| lottery_v2.db NOT staged | ✅ |
| lottery_history.json NOT staged | ✅ |
| SOURCE_UNKNOWN caveat documented | ✅ |
| 4_STAR backtest conducted | ✅ Not conducted (out of scope) |
| Production promotion | ✅ Not performed |

---

## Artifact References

| Artifact | Path |
|----------|------|
| P106 JSON (machine-readable) | `outputs/replay/p106_special3_prospective_evaluation_rerun_20260527.json` |
| P106 MD (this file) | `docs/replay/p106_special3_prospective_evaluation_rerun_20260527.md` |
| P106 runner script | `scripts/p106_special3_prospective_evaluation_rerun.py` |
| P106 test suite | `tests/test_p106_special3_prospective_evaluation_rerun.py` |
| P99 input artifact | `outputs/replay/special3_prospective_dryrun_plan_20260527.json` |
| P105 DB acceptance | `outputs/replay/p105_db_state_acceptance_decision_20260527.json` |

---

## Next Actions

1. **P107**: Continue prospective evaluation as new 3_STAR draws arrive.
   Accumulate more draws to improve statistical power. Target: ≥100 draws.
2. **Monitor**: Track criterion 2 (hit_rate > 15%) as the primary promotion
   gate. `sum_band_frequency` at 19.05% is the strongest single candidate.
3. **ensemble_v2 composition review**: Consider whether `sum_band_frequency`
   should have higher RRF weight given its superior individual performance.
4. **Do NOT promote** any strategy to production on the basis of this P106
   evaluation alone (PARTIAL classification).

---

*Generated: 2026-05-27T07:16:41Z by autonomous P106 evaluation agent.*  
*Replay rows (before/after): 54,462 / 54,462 — no mutation.*
