# P107A: Special3 100-Draw Monitoring Gate

**Date**: 2026-05-27  
**Classification**: `P107A_SPECIAL3_100DRAW_WAIT_MORE_DRAWS`  
**Branch**: `p107a-special3-100draw-monitoring-gate`

---

## PROJECT_CONTEXT_LOCK

```
Project = LotteryNew
Canonical Repo = /Users/kelvin/Kelvin-WorkSpace/LotteryNew
Canonical Branch = main
```

This report applies **only** to LotteryNew.  
Any reference to Betting-pool, Stock-Prediction-System, Stock, Novel, SCB, or any
other project is out of scope and must not influence this evaluation.

---

## Purpose

P106 produced a partial result. This monitoring gate checks whether enough new
3_STAR prospective draws have accumulated since P106 to justify a 100-draw
re-evaluation.

This task is **read-only**. No DB writes, no ingestion, no strategy promotion.

---

## Source-Unknown Caveat

> **SOURCE_UNKNOWN caveat is active.**  
> The 3_STAR draws ingested in P104 were acquired through an undisclosed source.
> Source provenance has not been verified. All prospective evaluations must carry
> this caveat until the source is formally documented and authorized.  
> The caveat applies to all P99–P107A artifacts.

---

## P106 Summary

| Field | Value |
|-------|-------|
| Classification | `P106_SPECIAL3_PROSPECTIVE_EVALUATION_PARTIAL` |
| PR | #235 (merged) |
| P100 criteria passed | 5 / 6 |
| ensemble_v2 top20 hit rate | 14.29% |
| P100 threshold (top20) | 15.00% |
| Gap to threshold | 1 hit short |
| p-value | 5×10⁻⁶ |
| ensemble_v2 edge over null | +12.29 pp |
| Info Ratio | 6.97 |
| Best individual strategy | `sum_band_frequency` at 19.05% top20 |
| Prospective draws evaluated | 63 (115000028–115000106) |
| P99 training cutoff | 115000024 |
| DB writes | None |
| replay_rows | 54462 (unchanged) |

---

## Current DB Snapshot

| Field | Value |
|-------|-------|
| replay_rows | 54462 |
| 3_STAR count | 4179 |
| 3_STAR max draw | 115000106 |
| 4_STAR count | 2922 |
| 4_STAR max draw | 115000103 |
| POWER_LOTTO count | 1913 |
| POWER_LOTTO max draw | 115000041 |

Snapshot taken: 2026-05-27 (post P106 merge).

---

## Prospective Draw Count Analysis

| Metric | Value |
|--------|-------|
| P99 training cutoff | 115000024 |
| Total 3_STAR draws after P99 cutoff | **63** |
| P106 evaluated range | 115000028–115000106 |
| P106 evaluated draws | 63 |
| Additional draws after P106 max | **0** |
| Draws needed to reach 100 | **37** |
| 100-draw threshold reached | ❌ NO |

**Interpretation**: No new 3_STAR draws have been added since P106. The total
prospective sample remains at 63, which is 37 draws short of the 100-draw
threshold.

---

## Readiness Assessment

| Check | Status |
|-------|--------|
| ≥100 prospective draws after P99 cutoff | ❌ 63 / 100 |
| replay_rows unchanged | ✅ 54462 |
| DB writes performed | ✅ None |
| Strategy promoted | ✅ None |
| 4_STAR backtest run | ✅ None |
| source_unknown caveat preserved | ✅ Yes |

**Readiness**: NOT READY — 37 more draws needed.

---

## Recommendation

**`wait_for_more_draws`**

1. **Do not re-run the prospective evaluation yet.** The 100-draw threshold has not
   been reached. Running at 63 draws would re-produce the same partial result.

2. **Monitor for new 3_STAR draws.** Once total prospective count after draw
   115000024 reaches ≥100, re-run P106 methodology as P107A_RERUN (or a new P
   task).

3. **Priority target for 100-draw retest**: `sum_band_frequency` (best individual,
   19.05% top20 at N=63). This strategy showed consistent above-null performance
   and warrants a focused individual retest alongside the ensemble when 100 draws
   are available.

4. **Source authorization still required.** Before any production promotion, the
   source of 3_STAR draws ingested in P104 must be formally documented and the
   SOURCE_UNKNOWN caveat cleared.

---

## Explicit Governance Notes

> **This task does not perform stale baseline repair.**  
> Stale baseline repair, if needed, is classified as a separate future task:
> `P107B_STALE_BASELINE_GUARD_REPAIR`.

> **This task does not run a 4_STAR backtest.**  
> 4_STAR backtest requires a separate authorized task with explicitly approved
> data source.

> **This task does not promote any strategy.**  
> No strategy has been moved to observation, production, or champion status in this
> task. Promotion requires the full P100 pass gate.

---

## Next Recommended Action

When 3_STAR draws after 115000024 reach ≥100:

1. Create branch `p107a-rerun` (or next P-number task).
2. Re-run walk-forward evaluation using the same P106 methodology.
3. Include `sum_band_frequency` as a priority individual strategy test.
4. Re-evaluate all 6 P100 criteria with the larger sample.
5. If `ensemble_v2` hit rate crosses 15% with p < 0.05 and IR > 0, classify as
   `P100_PASS` and proceed to observation gate.

---

## Governance Checklist

- [x] Read-only — zero DB writes
- [x] replay_rows = 54462 (before = after)
- [x] No new files staged except the 4 whitelist files
- [x] source_unknown caveat documented and preserved
- [x] P106 reference included in artifact
- [x] 4_STAR backtest not run
- [x] Strategy promotion not performed
- [x] Stale baseline repair not performed
- [x] Lifecycle / champion / registry metadata not mutated

---

## Artifact References

| File | Description |
|------|-------------|
| `outputs/replay/p107a_special3_100draw_monitoring_gate_20260527.json` | Machine-readable governance artifact |
| `docs/replay/p107a_special3_100draw_monitoring_gate_20260527.md` | This report |
| `scripts/p107a_special3_100draw_monitoring_gate.py` | Read-only gate script |
| `tests/test_p107a_special3_100draw_monitoring_gate.py` | Test suite (≥25 tests) |

---

## Final Classification

```
P107A_SPECIAL3_100DRAW_WAIT_MORE_DRAWS
```

37 more 3_STAR prospective draws needed before re-evaluation is warranted.  
No action required until new draws are available.
