# P252C — Baseline Calculator SSOT

**Date:** 2026-06-07 16:02:09  
**Task:** P252C  
**Classification:** BASELINE_CALCULATOR_SSOT_IMPLEMENTED  
**Module:** `lottery_api/utils/baseline_calculator.py`  

## Executive Summary

P252C implements the first P0 consolidation item from P252B: a unified null/random baseline SSOT module. Baseline logic was previously scattered across 10+ scripts with inconsistent formulas, and a historical bug (L14) caused two false positives (Attention LSTM and Zonal Pruning). This module centralises correct analytical computation in pure Python with no DB access.

## Why M4 Baseline SSOT Is Needed

| Issue | Detail |
|-------|--------|
| **L14 false positives** | Per-ticket baseline used instead of N-ticket formula → two strategies wrongly accepted |
| **Dispersed implementations** | `exhaustive_nbet_benchmark.py`, `scientific_baseline_report.py`, `benchmark_framework.py`, and 7+ others each define their own baseline |
| **No validation gate** | Scripts silently accept invalid configs (pick_count ≥ pool_size, etc.) |
| **No SSOT output shape** | Comparison of backtest results across tasks is inconsistent |

## Implemented Module & Functions

**Module:** `lottery_api/utils/baseline_calculator.py`  
**Deps:** Python stdlib only (`math`, `typing`)  
**DB access:** NONE  
**Strategy registry:** NONE  

| Function | Signature | Purpose |
|----------|-----------|---------|
| `combination_count` | `(pool_size, pick_count) -> int` | C(pool_size, pick_count) via math.comb — number of ways to choose k from n |
| `single_ticket_probability` | `(pool_size, pick_count, match_threshold=3) -> float` | P(≥ match_threshold matches) for one ticket — hypergeometric model |
| `n_ticket_probability` | `(pool_size, pick_count, n_tickets, match_threshold=3) -> float` | P(at least one of N tickets hits) = 1 - (1-p_single)^N |
| `expected_hits` | `(n_trials, probability) -> float` | Expected hit count = n_trials × probability |
| `baseline_hit_rate` | `(n_hits, n_trials) -> float` | Observed hit rate = n_hits / n_trials with bounds checking |
| `validate_lottery_config` | `(pool_size, pick_count, n_tickets=1, match_threshold=3) -> dict` | Validate config parameters; returns {valid, errors, warnings} |
| `random_baseline_summary` | `(pool_size, pick_count, n_tickets, n_trials, ...) -> dict` | Canonical structured baseline summary with no_edge_claim=True |

## Baseline Summary Schema

Required fields in every `random_baseline_summary()` output:

```
schema_version          — '1.0'
baseline_type           — 'analytical_hypergeometric'
lottery_type            — e.g. 'BIG_LOTTO'
pool_size / pick_count  — lottery config
n_tickets               — tickets per draw
match_threshold         — e.g. 3 for M3+
trials                  — backtest length
single_ticket_probability
n_ticket_probability    — the baseline (correct N-bet formula)
expected_hits           — n_trials × n_ticket_probability
baseline_hit_rate       — same as n_ticket_probability
assumptions             — list of modelling assumptions
limitations             — list of known limitations
no_edge_claim = true    — always present
no_betting_advice = true

# Optional (when observed_hits provided):
observed_hits / observed_hit_rate / edge_vs_baseline
```

## Reference Values Verified

| Lottery | Pool / Pick | M3+ (1 ticket) | Source |
|---------|-------------|----------------|--------|
| BIG_LOTTO | 49/6 | 1.8638% | lottery_api/CLAUDE.md 1.86% ✓ |
| POWER_LOTTO | 38/6 | 3.8698% | lottery_api/CLAUDE.md 3.87% ✓ |
| DAILY_539 | 39/5 | 1.0041% | computed analytically |

## Example Usage

```python
from lottery_api.utils.baseline_calculator import (
    single_ticket_probability,
    n_ticket_probability,
    random_baseline_summary,
)

# Correct N-bet baseline (L14 fix)
p4 = n_ticket_probability(pool_size=49, pick_count=6, n_tickets=4, match_threshold=3)
# → 0.0725...

# Full structured summary
summary = random_baseline_summary(
    pool_size=49, pick_count=6, n_tickets=4, n_trials=1500,
    match_threshold=3, lottery_type='BIG_LOTTO', observed_hits=112
)
assert summary['no_edge_claim'] is True
```

## Non-Goals

- Does **not** claim any baseline improvement raises P(win)
- Does **not** recommend betting on any lottery
- Does **not** modify the production strategy registry
- Does **not** connect to any database
- Does **not** change any existing strategy logic
- Position frequency (M2) remains BLOCKED by sorted DB storage — this module does not address it

## No-Overclaim Statement

> This module computes null/random baselines — the expected performance of a **random** strategy. A strategy exceeding its baseline does **not** imply a deployable prediction edge. All completed research arcs remain NULL/REJECTED/UNDERPOWERED. GREEN canonical randomness (P246K) does not imply any exploitable signal.

## Compliance

- **No DB write performed in P252C.**
- **No registry mutation.** Module has zero import of database/registry/routes.
- **No strategy promotion.** All edge-search results remain NULL/REJECTED/UNDERPOWERED.
- **No betting advice** is given or implied.

## Recommended Next Task

**P252D — Implement M5 permutation_test.py SSOT (P0)**

- Second P0 gap from P252B: permutation test has known L96 bug (shuffle preserves mean → p=1.0)
- Need: `lottery_api/utils/permutation_test.py` with correct Binomial MC null
- Type C small additive implementation — no DB write, no registry, no strategy promotion

---
*Generated by P252C — Baseline Calculator SSOT*