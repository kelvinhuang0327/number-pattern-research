# P170 — POWER_LOTTO Threshold Sensitivity and Signal Tracking

**Task**: P170_POWER_LOTTO_THRESHOLD_SENSITIVITY_AND_SIGNAL_TRACKING_READ_ONLY  
**Date**: 2026-06-01  
**Final Classification**: `P170_POWER_LOTTO_SENSITIVITY_DOES_NOT_SUPPORT_TRACKING`  
**Authorization**: YES execute P170 threshold sensitivity and signal tracking read-only, no DB write, no P167 verdict change

---

## Phase 0 Verification — ALL PASS

| Check | Result |
|---|---|
| Authorization phrase | PRESENT ✓ |
| DB rows before | 94,924 ✓ |
| DB rows after | 94,924 (unchanged) ✓ |
| Drift guard | PASS ✓ |
| P161–P169 tests | PASS (427/427) ✓ |
| P167 script | PASS ✓ |
| P167 classification | P167_POWER_LOTTO_NO_DEFENSIBLE_EDGE_FOUND (preserved) ✓ |
| P169 classification | P169_POWER_LOTTO_SIGNAL_REVIEW_AND_THRESHOLD_SENSITIVITY_PLAN_READY ✓ |

---

## P167 NULL Conclusion — PRESERVED (NOT CHANGED)

**P167 classification: `P167_POWER_LOTTO_NO_DEFENSIBLE_EDGE_FOUND`**  
`p167_verdict_changes: false`

No retroactive reclassification of OOS Window 2 (499 draws) as meeting the 500-draw minimum.

---

## Part 1 — Threshold Sensitivity Results

Pre-declared scenarios from P169 plan, executed read-only on existing 1,499 draws.

### Summary Table

| Scenario | Threshold | Window 1 (draws 500–999) | Window 2 result | Both positive? | Label |
|---|---|---|---|---|---|
| S1 | 450 | mean=1.047 ✓ | mean=0.938 ✗ (BELOW random) | **NO** | RETROSPECTIVE_SENSITIVITY_ONLY |
| S2 | 475 | mean=1.036 ✓ | mean=0.941 ✗ (BELOW random) | **NO** | RETROSPECTIVE_SENSITIVITY_ONLY |
| S3 | 499 | mean=1.042 ✓ | mean=0.930 ✗ (BELOW random) | **NO** | RETROSPECTIVE_SENSITIVITY_ONLY |
| **S4** | **500** | **mean=1.040 ✓** | **499 draws — INSUFFICIENT** | **N/A (original)** | **ORIGINAL_PROTOCOL** |
| S5 | 525 | mean=1.034 ✓ | 499 < 525 — INSUFFICIENT | N/A | RETROSPECTIVE_SENSITIVITY_ONLY |

### Key Finding

**OOS Window 1 (draws 500–999) is consistently positive across ALL scenarios.**  
**OOS Window 2 (draws 1000–1449/1498) is consistently negative across S1/S2/S3.**

This reveals that the positive ensemble signal is **not uniform across the draw range**. The effect is concentrated in draws 500–1000 and reverses (or disappears) in more recent draws 1000–1499.

| Period | Mean hit count | vs Random (0.9474) | vs Best single (0.9749) |
|---|---|---|---|
| Draws 500–999 (OOS Window 1) | **1.040–1.047** | +0.09–0.10 above | +0.07–0.07 above |
| Draws 1000–1449 (OOS Window 2) | **0.930–0.941** | **−0.007–−0.018 BELOW** | **−0.034–0.045 BELOW** |
| Last 200 draws (held-out) | **0.865** | **−0.082 BELOW** | **−0.110 BELOW** |

**The signal is non-stationary and weakens substantially in the most recent draw period.** This is not a data-volume problem — it is an effect that exists in one period but reverses in another.

### Interpretation

- The P167 Module F final gate failure was not merely due to 1 missing draw
- Even at S3 (499-draw threshold), Window 2 is negative — the gate would still fail on stability grounds
- The ensemble voting effect appears to be **period-specific, not persistent**
- Lowering the OOS threshold would not rescue the result — Window 2 is negative at ANY qualifying threshold

---

## Part 2 — Signal Tracking Results

### Prospective Draw Availability

| Metric | Value |
|---|---|
| Prospective draws available (> draw 115000041) | **0** |
| Minimum required for tracking | 100 |
| Status | **AWAITING_PROSPECTIVE_DATA** |

No genuinely prospective draws are available in the zen-gates canonical DB. The tracking protocol cannot be executed on future data.

### Held-Out Retrospective Window (NOT truly prospective)

To characterize recent signal direction, P170 evaluated the last 200 draws of the P167 dataset as a held-out window. **These draws were part of the P167 dataset** — this is RETROSPECTIVE, not prospective.

| Signal | Config | Held-out N | Mean | vs Random | vs Best single | Status |
|---|---|---|---|---|---|---|
| A: Consensus Voting | P167 Module A equal-weight top-6 | 200 | **0.865** | **−0.082 BELOW** | **−0.110 BELOW** | WEAKENED |
| E: Main-Number | P167 Module E per-draw mean | 200 | **0.920** | **−0.027 BELOW** | **−0.055 BELOW** | WEAKENED |

**Both signals are below random in the most recent 200 draws.** This is consistent with the Window 2 findings from the sensitivity analysis.

### Tracking Recommendation: `SIGNAL_WEAKENED_IN_HELD_OUT`

The signals that appeared positive in the full P167 in-sample analysis (Modules A and E) are **below random in the most recent 200 draws**. This reduces the case for prospective tracking — the signal has weakened in the direction that matters most (recent draws).

---

## Final Classification: `P170_POWER_LOTTO_SENSITIVITY_DOES_NOT_SUPPORT_TRACKING`

### Why this classification

1. **Threshold sensitivity (S1–S3)**: Window 2 is negative at ALL sensitivity thresholds. The 499 vs 500 boundary is NOT the issue — even at 450-draw threshold, Window 2 mean=0.938 is below random. The signal is period-specific, not threshold-sensitive.

2. **Held-out signals**: Both Signal A and Signal E are below random in the most recent 200 draws (−0.082 and −0.027 respectively).

3. **Zero prospective draws**: Genuine prospective tracking cannot begin.

4. **Conclusion**: The P167 positive signal in OOS Window 1 appears to be a local effect concentrated in draws 500–1000, not a persistent generalizable pattern. Continued tracking on future draws is unlikely to confirm the signal unless it re-emerges in the new data.

### Honest Interpretation

The P167 Module A and E signals that appeared promising in in-sample and OOS Window 1 analysis do NOT persist in the second half of the draw history. This is important additional evidence that:
- The P167 NULL result (`P167_POWER_LOTTO_NO_DEFENSIBLE_EDGE_FOUND`) was correct
- The positive signals in P167 were likely period-specific noise, not generalizable patterns
- Continued POWER_LOTTO research may need a fundamentally different hypothesis or significantly more data showing signal re-emergence

---

## What This Means for P171

**P171 (CEO Decision Review)** should consider:

1. **Halt R1 POWER_LOTTO research**: The sensitivity analysis reveals non-stationarity in the signal. The most recent period is below random. Continuing to search for an ensemble edge in this dataset is unlikely to be productive.

2. **Wait for significantly more draws**: If the signal re-emerges in future draws (shows consistently above random in a new period), that would be evidence worth revisiting. The threshold is NOT "1 more draw" — it requires a genuinely new positive period of ≥ 500 draws.

3. **Do not deploy**: No deployment, no champion promotion, no controlled_apply regardless of sensitivity findings.

**Sensitivity-only results are NOT deployment evidence.** The consistent negative direction of Window 2 across all sensitivity thresholds strengthens, not weakens, the case for the P167 NULL result.

---

## No-Action Confirmations

- **Zero DB writes** — DB unchanged at 94,924 rows
- **Zero P167 verdict changes** — classification preserved
- **Zero retroactive 499-draw reclassifications**
- **Zero registry mutations, champion promotions, controlled_apply**
- **Zero commits or pushes**
- **No win guarantees, no real-money guidance**

---

## Next Task — P171_POWER_LOTTO_RESEARCH_CEO_DECISION_REVIEW

P170 results require CEO/user review. P171 is a decision review — no autonomous deployment.

---

## Governance Invariants

| Invariant | Value |
|---|---|
| DB rows | 94,924 (unchanged) |
| Drift guard | PASS |
| main/zen-gates split | UNRESOLVED |
| P167 NULL result | **STANDS — not changed by P170** |
| Defensible edge found | **NO** |
| Sensitivity supports tracking | **NO** |
