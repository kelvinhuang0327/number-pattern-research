# P252B — Unified External Method Coverage Audit

**Date:** 2026-06-07 11:11:27  
**Task:** P252B  
**Classification:** UNIFIED_EXTERNAL_METHOD_COVERAGE_AUDIT  

## Executive Summary

P252B audits the 8 scientific/external methods intended to support valid prediction research. The audit answers two distinct questions clearly:

1. **Did external methods find a deployable prediction edge?** → **NO** — all completed research arcs (P222/P230C/P231B/P227C/P214C) returned NULL/REJECTED/UNDERPOWERED.
2. **Are the 8 methods fully engineered as a unified core layer/SSOT?** → **NO** — 7 are CONFIRMED_PARTIAL and 1 (M8 feature bottleneck) is PARTIAL with no implementation.

## Direct Answers

> **External methods have NOT found a deployable prediction edge.** All research arcs are NULL, REJECTED, or UNDERPOWERED. GREEN canonical randomness (P246K) confirms random-compatibility of 2,113 BIG_LOTTO draws — **this does not imply any exploitable prediction signal.** No strategy promotion. No betting advice.

> **The 8-method core coverage is NOT fully unified.** Critical gaps exist in null simulation SSOT (M4), permutation test SSOT (M5), and multiple testing correction enforcement (M6). These are P0 priorities.

## 8-Method Coverage Table

| ID | Method | Category | Status | Priority | Key Gap |
|----|--------|----------|--------|----------|---------|
| M1 | Historical Draw Parser | data quality control | CONFIRMED_PARTIAL | P1 | No unified parser SSOT module — per-lottery ad-hoc… |
| M2 | Number / Position Frequency | data quality control | CONFIRMED_PARTIAL | P2 | Number frequency: exists in many scripts but no SS… |
| M3 | Rolling Window Statistics | reporting interpretability | CONFIRMED_PARTIAL | P0 | RSM has SSOT for production rolling stats but sche… |
| M4 | Null Simulation / Random Baseline | false positive control | CONFIRMED_PARTIAL | P0 | Baseline formula 1-(1-p)^N is in individual script… |
| M5 | Permutation Test | false positive control | CONFIRMED_PARTIAL | P0 | Known past bug (L96): shuffling hit labels preserv… |
| M6 | Multiple Testing Correction | false positive control | CONFIRMED_PARTIAL | P0 | CorrectionMethod enum exists in schema but not enf… |
| M7 | Signal Stability Diagnostics | reporting interpretability | CONFIRMED_PARTIAL | P1 | Label inconsistency: 'block', 'year', 'era', 'robu… |
| M8 | Feature Bottleneck Report | reporting interpretability | PARTIAL | P1 | No dedicated feature_bottleneck_report.py SSOT mod… |

## Evidence Links

| Artifact | Task | Relevance |
|----------|------|-----------|
| `lottery_api/diagnostics/statistical_diagnostics_schema.py` | P242 | M3/M4/M5/M6/M7/M8 schema fields |
| `lottery_api/engine/rolling_strategy_monitor.py` | RSM | M3 rolling window SSOT (partial) |
| `lottery_api/engine/drift_detector.py` | P246G | M3/M7 signal stability (production) |
| `tools/p3_shuffle_permutation_test.py` | P3 | M5 permutation test (per-lottery) |
| `outputs/research/p245b_bias_gate_layer*.json` | P245B | M6 correction gate design |
| `outputs/research/p241b_p234_statistical_diagnostics_inventory*.json` | P241B | All 8 methods inventoried |
| `outputs/research/p244c_diagnostics_integration_plan*.json` | P244C | Integration checkpoints |
| `scripts/p213g_3star_4star_dry_run_source_parser.py` | P213G | M1 parser (3_STAR/4_STAR) |

## P0/P1/P2 Consolidation Plan

### P0 — Mandatory Gates (implement before next research arc)

These gaps have caused false positives (L14) or false negatives (L96) before.

**M4 — Null Simulation / Random Baseline — SSOT baseline_calculator.py**  
Why P0: Historical bug (L14) caused false positives. Correct N-bet baseline must be enforced.  
Action: Create baseline_calculator.py with correct 1-(1-p)^N formula + per-lottery table + tests  
Type: Type B/C

**M5 — Permutation Test — Fix L96 bug SSOT permutation_test.py**  
Why P0: L96 bug (shuffle preserves mean → p=1.0) caused critical false-negatives. Must be fixed centrally.  
Action: Create permutation_test.py with correct Binomial(1, baseline_i) MC null + hypothesis declaration  
Type: Type B/C

**M6 — Multiple Testing Correction — mandatory correction_gate.py**  
Why P0: Without correction gate, future research may report uncorrected p-values and promote false positives.  
Action: Implement correction_gate.py enforcing family_size + correction_method in research artifact output  
Type: Type B/C

**M3 — Rolling Window Statistics — promote P221F constants to shared module**  
Why P0: Window semantic consistency (short=150, medium=500, long=1500) must be enforced across all research scripts.  
Action: Create window_constants.py importing from P221F definition; enforce in RSM and research templates  
Type: Type B

### P1 — Inventory and Parser (engineering hygiene)

**M1 — Historical Draw Parser — unified parser SSOT**  
Action: Design parser SSOT with per-lottery schema, validation contract, post-parse assertions (Type B)

**M7 — Signal Stability Diagnostics — vocabulary and threshold SSOT**  
Action: Define block/era/year/robustness synonyms; add stability_threshold to shared constants (Type B)

**M8 — Feature Bottleneck Report — design + Type C implementation**  
Action: Design feature_bottleneck_report.py (MI per feature, null rate, bottleneck score) (Type B + Type C)

### P2 — Blocked or Diagnostics-Only

**M2 — Position Frequency — BLOCKED by sorted DB storage**  
Blocked reason: database.py:463 sorts numbers at write time; positional order lost for all lotteries except 3_STAR/4_STAR after P213H/L  
Action: Design position_frequency_calculator.py for number frequency only; position frequency remains BLOCKED

### Non-Goals

- Do not claim any consolidation raises P(win)
- Do not start new prediction research arcs in this consolidation
- Do not modify production strategy registry
- Position frequency BLOCKED — do not attempt DB schema change without separate Type D authorization
- Feature bottleneck report is interpretability only — not a predictor

## Risks

| Method | Risk If Left Inconsistent |
|--------|--------------------------|
| M1 — Historical Draw Parser | Silent data quality drift — new draws may be ingested with wrong format without … |
| M2 — Number / Position Frequency | Different frequency windows/definitions used in different scripts. Position freq… |
| M3 — Rolling Window Statistics | Research scripts may use different window sizes than RSM production paths, creat… |
| M4 — Null Simulation / Random Baseline | CRITICAL: baseline bug (L14) has caused false positives before. Without a SSOT, … |
| M5 — Permutation Test | HIGH: The L96 bug (shuffle preserves mean → p=1.0) was a critical false-negative… |
| M6 — Multiple Testing Correction | CRITICAL: Without correction gate, future research may report uncorrected p-valu… |
| M7 — Signal Stability Diagnostics | Research results may use inconsistent stability criteria — 'block stability' in … |
| M8 — Feature Bottleneck Report | Feature selection is done implicitly/ad-hoc in research scripts. Without bottlen… |

## Recommended Next Task

**P252C — Implement M4 baseline_calculator.py SSOT (Type C)**

- Highest risk gap: L14 baseline bug caused two false positives (Attention LSTM, Zonal Pruning)
- Correct formula: `baseline(n, p_single) = 1 - (1 - p_single) ** n`
- Output: shared module `lottery_api/utils/baseline_calculator.py` with per-lottery table + tests
- Type C small additive implementation — no DB write, no registry change, no strategy promotion

## Compliance Statements

- **No DB write performed in P252B.**
- **No strategy promotion.** All edge-search results remain NULL/REJECTED/UNDERPOWERED.
- **No betting advice** is given or implied in this audit.
- GREEN canonical randomness (P246K) does not authorize any prediction direction.

---
*Generated by P252B — Unified external method coverage audit*