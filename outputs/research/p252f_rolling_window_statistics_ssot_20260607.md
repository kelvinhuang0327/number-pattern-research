# P252F — Rolling Window Statistics SSOT

**Date:** 2026-06-07 16:39:13  
**Task:** P252F  
**Classification:** ROLLING_WINDOW_STATISTICS_SSOT_IMPLEMENTED  
**Module:** `lottery_api/utils/rolling_window.py`  

## Executive Summary

P252F implements the remaining P0 consolidation item from P252B: a unified rolling window statistics SSOT. Rolling logic existed in RSM, P211R, P221F, P222, P224, P230, P231 with different window sizes, inconsistent labels, and no shared output schema. This module exposes both P221F frozen research windows and RSM production windows as named constants, and provides a deterministic schema-driven summary.

## Why M3 Rolling Window SSOT Is Needed

| Issue | Detail |
|-------|--------|
| **Inconsistent constants** | RSM uses {short:30, medium:100, long:300}; P221F research uses 150/500/1000 |
| **No canonical labels** | 'w150', 'short_150', 'window_150', 'w=150' all appear in different scripts |
| **No UNDERPOWERED flag** | Scripts silently produce stats for too-short windows |
| **No schema** | Window results lack no_edge_claim, family_label, step_size metadata |

## Implemented Module & Functions

**Module:** `lottery_api/utils/rolling_window.py`  
**Deps:** Python stdlib only (`math`, `statistics`, `typing`)  
**DB access:** NONE  

| Function | Signature | Purpose |
|----------|-----------|---------|
| `validate_window_config` | `(total_count, window_size, step_size=1, min_count=None) -> dict` | Validate window parameters; returns {valid, errors, warnings, window_count, underpowered} |
| `rolling_slices` | `(items, window_size, step_size=1, include_partial=False) -> list[list]` | Forward sliding window slices; step_size controls stride |
| `tail_window` | `(items, window_size) -> list` | RSM pattern: items[-window_size:] or all items if fewer available |
| `rolling_window_labels` | `(total_count, window_size, step_size=1) -> list[str]` | Labels like 'w150[0:150]' for each full window position |
| `tail_window_label` | `(total_count, window_size) -> str` | Label for tail window: 'tail_150' or 'partial_80_of_150' |
| `summarize_window` | `(values, label=None, start_index=0) -> dict` | Compute count/mean/min/max/std for a single window of values |
| `rolling_summary` | `(items, window_sizes, step_size=1, value_getter=None, family_label=None, ...) -> dict` | Canonical SSOT output: all window series with no_edge_claim=True |

## Window Constants

```python
from lottery_api.utils.rolling_window import P221F_WINDOWS, RSM_WINDOWS

P221F_WINDOWS = {
    'short':  (100, 125, 150),   # frozen by P221F governance (2026-05)
    'mid':    (500, 750, 1000),   # frozen by P221F governance
    'all_history': (),            # use full dataset; reference-context only
}

RSM_WINDOWS = {'short': 30, 'medium': 100, 'long': 300}  # production RSM
```

## Rolling Summary Schema

```
schema_version          — '1.0'
summary_type            — 'rolling_window_statistics'
family_label            — declared family name
total_count             — total items in dataset
step_size / include_partial / min_count
window_sizes_requested  — list of requested window sizes
window_series: list of per-size results, each containing:
  window_size / window_count / underpowered / warnings
  windows: list of per-window dicts:
    label / start_index / end_index / count / value_count
    mean / min / max / std  (None if non-numeric)
no_edge_claim = true
no_betting_advice = true
assumptions / limitations
```

## Example Usage

```python
from lottery_api.utils.rolling_window import (
    P221F_WINDOWS, rolling_summary, tail_window
)

# P221F research: three short windows
report = rolling_summary(
    items=draw_hit_rates,          # list of per-draw hit rates
    window_sizes=P221F_WINDOWS['short'],  # (100, 125, 150)
    family_label='DAILY_539_midfreq',
)
assert report['no_edge_claim'] is True

# RSM production: tail window
recent = tail_window(records, window_size=150)
```

## Non-Goals

- Does **not** claim rolling window edge implies a deployable prediction edge
- Does **not** connect to any database
- Does **not** modify the production RSM or strategy registry
- Does **not** generate p-values (use permutation_test.py for that)
- Does **not** apply multiple-testing correction (use correction_gate.py for that)

## No-Overclaim Statement

> A rolling window that outperforms the baseline in one window does **not** imply a deployable prediction edge. All completed research arcs remain NULL/REJECTED/UNDERPOWERED.

## Compliance

- **No DB write performed in P252F.**
- **No registry mutation.**
- **No strategy promotion.** All edge-search results remain NULL/REJECTED/UNDERPOWERED.
- **No betting advice** is given or implied.

## Recommended Next Task

**P252G — Implement M7 signal stability diagnostics SSOT (P1)**

- Next P252 item from P252B: 'block', 'year', 'era', 'robustness' labels inconsistent
- Need: shared stability vocabulary, threshold constants, block-split helper
- Type B/C — no DB write, no registry, no strategy promotion

---
*Generated by P252F — Rolling Window Statistics SSOT*