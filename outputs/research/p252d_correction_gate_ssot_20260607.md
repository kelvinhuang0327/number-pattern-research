# P252D — Multiple Testing Correction Gate SSOT

**Date:** 2026-06-07 16:21:31  
**Task:** P252D  
**Classification:** CORRECTION_GATE_SSOT_IMPLEMENTED  
**Module:** `lottery_api/utils/correction_gate.py`  

## Executive Summary

P252D implements the second P0 consolidation item from P252B: a unified multiple testing correction gate SSOT module. Bonferroni and BH-FDR logic existed in at least 5 research scripts (P211R, P214C, P222, P227C, P219) with inconsistent field names and no shared schema. This module centralises correct implementations in pure Python with no DB access.

## Why M6 Correction Gate SSOT Is Needed

| Issue | Detail |
|-------|--------|
| **Dispersed implementations** | Bonferroni/BH-FDR in P211R, P214C, P222, P227C, P219 — each defines its own logic |
| **No shared schema** | `bonferroni_pass`, `bh_fdr_pass`, `corrected_p`, `is_corrected_significant` — inconsistent field names |
| **No family-size gate** | No enforcement that family_size is declared before data inspection |
| **No no_edge_claim flag** | Correction outputs lacked explicit no_edge_claim metadata |

## Implemented Module & Functions

**Module:** `lottery_api/utils/correction_gate.py`  
**Deps:** Python stdlib only (`math`, `typing`)  
**DB access:** NONE  
**Strategy registry:** NONE  

| Function | Signature | Purpose |
|----------|-----------|---------|
| `validate_p_values` | `(p_values) -> dict` | Validate input p-values; returns {valid, errors, n}; never raises |
| `bonferroni_correction` | `(p_values, alpha=0.05) -> dict` | Bonferroni: adjusted_p[i] = min(p[i] × m, 1.0); rejected ← adj < alpha |
| `benjamini_hochberg_fdr` | `(p_values, alpha=0.05) -> dict` | BH-FDR: step-down monotone q-values; rejected ← q < alpha |
| `correction_summary` | `(raw_p, adj_p, rejected, method, alpha, family_label=None) -> dict` | Build standard correction summary from pre-computed results |
| `correction_gate_summary` | `(p_values, alpha=0.05, methods=('bonferroni','bh_fdr'), family_label=None) -> dict` | Run one or more corrections and return combined canonical summary |

## Correction Summary Schema

Every `correction_summary()` output includes:

```
schema_version          — '1.0'
gate_type               — 'multiple_testing_correction'
family_label            — declared family name (audit trail)
alpha                   — target error rate
method                  — 'bonferroni' or 'bh_fdr'
n_tests                 — number of hypotheses in family
raw_p_values            — original p-values
adjusted_p_values       — Bonferroni adj or BH q-values (monotone)
rejected                — list[bool] — True = H₀ rejected
survivor_count          — number of rejections
null_count              — n_tests − survivor_count
correction_required = true
no_edge_claim = true    — always present
no_betting_advice = true
assumptions / limitations
```

## Example Usage

```python
from lottery_api.utils.correction_gate import correction_gate_summary

# 7 position tests (P214C scenario)
report = correction_gate_summary(
    p_values=[0.03, 0.12, 0.001, 0.045, 0.22, 0.08, 0.009],
    alpha=0.05,
    methods=('bonferroni', 'bh_fdr'),
    family_label='P214C_position_7tests',
)
assert report['no_edge_claim'] is True
# Bonferroni threshold = 0.05/7 ≈ 0.00714
# Survivor (p=0.001 × 7 = 0.007 < 0.05): 1
```

## Verified Reference Values

| Test | Expected | Actual | OK |
|------|----------|--------|----|
| Bonferroni threshold (7 tests) | 0.05/7 ≈ 0.007143 | 0.00714286 | ✓ |
| Bonferroni survivors (7 tests) | 1 | 1 | ✓ |
| BH-FDR survivors (10 tests, α=0.05) | 2 | 2 | ✓ |
| BH adj p-values monotone | true | True | ✓ |
| Deterministic output | true | True | ✓ |

## Non-Goals

- Does **not** claim any correction raises P(win)
- Does **not** recommend betting on any lottery
- Does **not** modify the production strategy registry
- Does **not** connect to any database
- Does **not** change any existing script or strategy logic
- A rejection (p < corrected threshold) does **not** imply a deployable prediction edge

## No-Overclaim Statement

> This module applies statistical corrections to control false-discovery rates. A hypothesis surviving Bonferroni or BH-FDR correction means the raw p-value is unusually small relative to the family of tests — **it does not imply a deployable prediction edge, a betting strategy, or any exploitable lottery signal.** All completed research arcs remain NULL/REJECTED/UNDERPOWERED.

## Compliance

- **No DB write performed in P252D.**
- **No registry mutation.** Module has zero import of database/registry/routes.
- **No strategy promotion.** All edge-search results remain NULL/REJECTED/UNDERPOWERED.
- **No betting advice** is given or implied.

## Recommended Next Task

**P252E — Implement M5 permutation_test.py SSOT (P0)**

- Third P0 gap from P252B: permutation test has known L96 bug (shuffle preserves mean → p=1.0)
- Need: `lottery_api/utils/permutation_test.py` with correct Binomial MC null
- Type C small additive implementation — no DB write, no registry, no strategy promotion

---
*Generated by P252D — Multiple Testing Correction Gate SSOT*