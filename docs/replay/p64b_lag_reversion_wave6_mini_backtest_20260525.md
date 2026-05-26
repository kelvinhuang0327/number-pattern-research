# P64b: lag_reversion_2bet Wave 6 Mini-Backtest

**Classification**: `P64B_LAG_REVERSION_WAVE6_MINI_BACKTEST_GATE_FAIL`
**Marker**: `P64B_LAG_REVERSION_WAVE6_MINI_BACKTEST_20260525`
**Generated**: 2026-05-25T08:58:00.218516+00:00

---

## Executive Summary

Mini-backtest for `lag_reversion_2bet` (Wave 6 candidate, rank 2, score 80/100).
Algorithm: per-ball median interval overdue ranking.

| Evidence Gate | Result |
|---|---|
| Threshold M3+ | 3.87% |
| Gate Result | ❌ GATE FAIL |
| Best M3+ | 3.73% (window-1500) |
| Best vs Baseline | -0.14pp |
| Adapter Decision | `DEFER_ADAPTER_BUILD` |

---

## Algorithm

```
score(n) = current_lag(n) / (median_interval(n) + 0.1)
Bet-0: top 6 numbers by score
Lag window: 500 draws (mirrors tools/power_lag_reversion.py)
Special: frequency mean-reversion over 100 draws
```

- **Source model**: `lottery_api/models/lag_reversion.py`
- **Source tool**: `tools/power_lag_reversion.py`
- **Deterministic**: Yes (no random.seed)
- **Pool**: 1–38 (first zone), pick 6
- **Special pool**: 1–8

---

## Window Results

| Window | Predicted | M3+ Count | M3+ Rate | Baseline | vs Baseline | Special Hit | Gate |
|---|---|---|---|---|---|---|---|
|    150 |       150 |         1 | 0.67% | 3.87% | -3.20pp | 10.67% | ❌ |
|    500 |       500 |        10 | 2.00% | 3.87% | -1.87pp | 12.40% | ❌ |
|   1500 |      1500 |        56 | 3.73% | 3.87% | -0.14pp | 11.87% | ❌ |

### Hit Distributions

**Window 150** (n=150):

| Hits | Count | % |
|---|---|---|
| 0 | 43 | 28.67% |
| 1 | 79 | 52.67% |
| 2 | 27 | 18.00% |
| 3 | 1 | 0.67% |
| 4 | 0 | 0.00% |
| 5 | 0 | 0.00% |
| 6 | 0 | 0.00% |

**Window 500** (n=500):

| Hits | Count | % |
|---|---|---|
| 0 | 149 | 29.80% |
| 1 | 245 | 49.00% |
| 2 | 96 | 19.20% |
| 3 | 10 | 2.00% |
| 4 | 0 | 0.00% |
| 5 | 0 | 0.00% |
| 6 | 0 | 0.00% |

**Window 1500** (n=1500):

| Hits | Count | % |
|---|---|---|
| 0 | 456 | 30.40% |
| 1 | 699 | 46.60% |
| 2 | 289 | 19.27% |
| 3 | 55 | 3.67% |
| 4 | 1 | 0.07% |
| 5 | 0 | 0.00% |
| 6 | 0 | 0.00% |

---

## Evidence Gate Decision

**Threshold**: M3+ >= 3.87% in at least one window

**Result**: ❌ GATE FAIL

**Rationale**: M3+ < 3.87% in all windows. Best: 3.73% in window-1500 (-0.14pp). Adapter build deferred.

**Adapter Decision**: `DEFER_ADAPTER_BUILD`

> Adapter build deferred. Consider re-testing after parameter tuning or
> proceed to P64c (zonal_entropy_2bet determinism fix).

---

## Governance

| Check | Value |
|---|---|
| DB writes | `false` |
| Temp DB | None (in-memory only) |
| Production rows before | 43960 |
| Production rows after | 43960 |
| Drift guard | Not run (no DB writes) |

---

## Artifacts

| Artifact | Path |
|---|---|
| Script | `scripts/p64b_lag_reversion_wave6_mini_backtest.py` |
| JSON output | `outputs/replay/p64b_lag_reversion_wave6_mini_backtest_20260525.json` |
| This doc | `docs/replay/p64b_lag_reversion_wave6_mini_backtest_20260525.md` |
| Tests | `tests/test_p64b_lag_reversion_wave6_mini_backtest.py` |

---

## Sequencing

| Task | Description | Status |
|---|---|---|
| P64a | cold_complement_2bet dry-run rehearsal | ✅ COMPLETE |
| **P64b** | **lag_reversion_2bet mini-backtest** | **THIS TASK** |
| P64c | Adapter build (conditional on gate) | Deferred |

**Preceding task**: P64a (commit `80611f3`)
**Next task**: P64c (zonal_entropy_2bet determinism fix or defer)
**Base commit**: `80611f3`

---

*Classification: `P64B_LAG_REVERSION_WAVE6_MINI_BACKTEST_GATE_FAIL`*
*NOT staged: no DB changes, no production writes*