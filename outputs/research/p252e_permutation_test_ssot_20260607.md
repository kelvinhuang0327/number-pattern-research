# P252E — Permutation Test SSOT

**Date:** 2026-06-07 16:30:17  
**Task:** P252E  
**Classification:** PERMUTATION_TEST_SSOT_IMPLEMENTED  
**Module:** `lottery_api/utils/permutation_test.py`  

## Executive Summary

P252E implements the third P0 consolidation item from P252B: a unified permutation test SSOT module. Permutation logic existed in P219 (empirical_p), Special3 (binomial analytical), P51, and P3 with inconsistent naming, formula, and null-generation approaches. This module provides a deterministic, schema-driven SSOT with the correct Phipson-Smyth plus-one formula and an embedded L96 warning.

## Why M5 Permutation Test SSOT Is Needed

| Issue | Detail |
|-------|--------|
| **Dispersed empirical_p** | p219, P3, P51, Special3 each implement their own formula |
| **L96 bug risk** | Shuffling binary hit-labels preserves mean → null overlaps observed → p≈1.0 |
| **No schema** | p-value returned as bare float with no no_edge_claim, seed, or null statistics |
| **Naming inconsistency** | 'permutation test', 'shuffle test', 'P3', 'empirical p' used interchangeably |

## Implemented Module & Functions

**Module:** `lottery_api/utils/permutation_test.py`  
**Deps:** Python stdlib only (`math`, `random`, `statistics`, `typing`)  
**DB access:** NONE  
**Strategy registry:** NONE  

| Function | Signature | Purpose |
|----------|-----------|---------|
| `validate_permutation_inputs` | `(observed_statistic, null_distribution, alternative) -> dict` | Validate inputs; returns {valid, errors, n_null}; never raises |
| `empirical_p_value` | `(observed, null_distribution, alternative='greater', plus_one=True) -> float` | Empirical p = (1 + count_extreme) / (B + 1) — Phipson-Smyth formula |
| `compare_observed_to_null` | `(observed_statistic, null_distribution) -> dict` | Compute null_min/max/mean/std/median and obs_percentile for audit |
| `permutation_summary` | `(observed, null_distribution, alternative='greater', plus_one=True, seed=None, family_label=None) -> dict` | Canonical SSOT output dict with no_edge_claim=True |
| `deterministic_shuffle` | `(values, seed) -> list` | Return seeded-shuffled copy of values for reproducible null generation |

## Permutation Summary Schema

Every `permutation_summary()` output includes:

```
schema_version          — '1.0'
test_type               — 'permutation_test'
family_label            — declared family name (audit trail)
alternative             — 'greater' | 'less' | 'two-sided'
observed_statistic      — real-data test statistic
null_count / null_min / null_max / null_mean / null_std / null_median
obs_percentile          — position of observed in null distribution
empirical_p_value       — (1 + count_extreme) / (B + 1)
plus_one_correction     — True (default)
seed                    — RNG seed used for null generation (audit trail)
no_edge_claim = true    — always present
no_betting_advice = true
assumptions / limitations
  └── limitations[0] contains L96 warning
```

## Example Usage

```python
from lottery_api.utils.permutation_test import (
    empirical_p_value, permutation_summary, deterministic_shuffle
)

# Generate null distribution (caller's responsibility)
rng = __import__('random').Random(42)
null = [rng.gauss(0.02, 0.005) for _ in range(200)]

# Compute empirical p-value
p = empirical_p_value(observed=0.035, null_distribution=null, alternative='greater')
# p = (1 + count(null >= 0.035)) / 201

# Full summary
summary = permutation_summary(0.035, null, 'greater', seed=42,
                              family_label='DAILY_539_midfreq')
assert summary['no_edge_claim'] is True
assert 'L96' in summary['limitations'][0]
```

## Verified Reference Values

| Test | Expected | Actual | OK |
|------|----------|--------|----|
| empirical_p greater (obs=0.035, null=[0.01..0.05]) | 3/6 = 0.5 | 0.5 | ✓ |
| plus-one: most extreme obs never gives p=0 | >0 | 0.16666667 | ✓ |
| plus-one=False most extreme → p=0 | 0.0 | True | ✓ |
| p_less correct | 4/6 | 0.66666667 | ✓ |
| Deterministic output | true | True | ✓ |
| Shuffle deterministic | true | True | ✓ |

## Non-Goals

- Does **not** generate null distributions — caller provides them
- Does **not** claim any p-value implies a deployable prediction edge
- Does **not** connect to any database
- Does **not** modify the production strategy registry
- Does **not** implement the analytical binomial test (that is `special3_oos_permutation_review.binomial_permutation_test`)

## No-Overclaim Statement

> A significant empirical p-value means the observed test statistic is unlikely under the null hypothesis as simulated — **it does not imply a deployable prediction edge, a betting strategy, or any exploitable lottery signal.** All completed research arcs remain NULL/REJECTED/UNDERPOWERED.

## Compliance

- **No DB write performed in P252E.**
- **No registry mutation.** Module imports only stdlib.
- **No strategy promotion.** All edge-search results remain NULL/REJECTED/UNDERPOWERED.
- **No betting advice** is given or implied.

## Recommended Next Task

**P252F — Implement M7 Signal Stability Diagnostics SSOT (P1)**

- Next P252 consolidation item from P252B
- Vocabulary gap: 'block', 'year', 'era', 'robustness' used inconsistently across scripts
- Need: shared stability threshold constants and block-split diagnostic helper
- Type B/C — no DB write, no registry, no strategy promotion

---
*Generated by P252E — Permutation Test SSOT*