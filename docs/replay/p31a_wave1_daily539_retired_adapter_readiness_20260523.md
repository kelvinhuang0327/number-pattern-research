# P31A Wave 1 — DAILY_539 Retired Adapter Promotion Readiness

**Phase**: P31A  
**Date**: 2026-05-23  
**Branch**: `p31a-wave1-daily539-retired-adapter-readiness`  
**Status**: `READY_NO_DB_WRITE`  
**Production DB rows**: 12460 (unchanged)

---

## Overview

P31A wires replay adapter wrappers for 5 RETIRED DAILY_539 strategies, validates them
via a 1500-period dry-run into a temp SQLite DB, and makes the lifecycle semantics
decision for Wave 1 promotion readiness.

**Production DB is untouched.** All dry-run rows go to `/tmp/p31a_temp.db` only.

---

## Wave 1 Strategies

| Strategy ID | Display Name | Algorithm | Replay Bet | Status |
|---|---|---|---|---|
| `acb_1bet` | 今彩539 ACB 1注 | Pure ACB | bet-1 (ACB) | RETIRED |
| `acb_markov_midfreq` | 今彩539 ACB+Markov 中頻 | ACB+Markov fused, midfreq-filtered | bet-1 (fused) | RETIRED |
| `acb_markov_midfreq_3bet` | 今彩539 ACB+Markov 中頻 3注 | 3-bet orthogonal — bet-1=ACB | bet-1 (ACB) | RETIRED |
| `midfreq_acb_2bet` | 今彩539 中頻 ACB 2注 | 2-bet — bet-1=MidFreq | bet-1 (MidFreq) | RETIRED |
| `midfreq_fourier_2bet` | 今彩539 中頻 Fourier 2注 | 2-bet — bet-1=MidFreq | bet-1 (MidFreq) | RETIRED |

**Multi-bet rule**: For multi-bet strategies, replay records **bet-1 only** (one row per draw per strategy).

---

## Adapter Implementation

**Module**: `lottery_api/models/p31a_wave1_retired_adapters.py`

The 5 adapters implement ACB, MidFreq, Markov, and ACB+Markov-midfreq fusion **inline**
(no separate tool files). Algorithm spec from `lottery_api/CLAUDE.md §ACB §MidFreq`.

### ACB Algorithm (pool=39, window=100)
```
score = (freq_deficit×0.4 + gap_score×0.6) × boundary_bonus × mod3_bonus

freq_deficit   = (expected_count - actual_count) / expected_count
gap_score      = (w - 1 - last_seen_idx) / w
boundary_bonus = 1.2 if n≤5 or n≥35 else 1.0
mod3_bonus     = 1.1 if n%3==0 else 1.0

Cross-zone constraint: select ≥2 of Z1(1-13), Z2(14-26), Z3(27-39)
```

### MidFreq Algorithm (window=100)
```
score = -|actual_count - expected_count|   # closest to expected frequency
```

### Adapters NOT registered in main registry
These adapters are **not** added to `_ALL_ADAPTERS` or `_REGISTRY` in
`replay_strategy_registry.py`. They exist exclusively in the P31A module.

---

## Dry-Run Results

| Metric | Value |
|---|---|
| Target window | Last 1500 DAILY_539 draws (2021/08/10 → 2026/05/18) |
| Strategies | 5 |
| Total dry-run rows | 7500 |
| Expected rows | 7500 |
| All predicted (0 errors) | ✓ |
| Temp DB path | `/tmp/p31a_temp.db` |

---

## R1 / R2 / R3 Rehearsal

| Step | Result |
|---|---|
| R1 Apply | 7500 rows inserted → total=7500 ✓ |
| R2 Rerun (idempotency) | 0 new inserts (idempotent=True) ✓ |
| R3 Rollback | before=7500, after=0, rollback_ok=True ✓ |
| All rehearsals pass | **True** ✓ |

---

## Lifecycle Semantics Decision: **Option A**

**Decision**: Keep `lifecycle_status=RETIRED`. Add `replay_available=True` flag in
catalog response when replay rows exist for a retired strategy.

**Rationale**:
- RETIRED accurately reflects these strategies were formally decommissioned after evaluation.
- `replay_available=True` is an additive catalog field — it does not change the lifecycle label.
- Option B (re-label as `reconstructible`) was DEFERRED: `reconstructible` maps to
  `ARTIFACT_ONLY` in P26 label precedence (not `RETIRED`). Relabeling would conflate semantics.
- Under P26, `assign_label(RETIRED)` always returns `"retired"` regardless of row_count.

### `reconstructible` Population Spec

| Scenario | Count |
|---|---|
| Current (P31A) | 0 |
| After P31B, Option A (chosen) | 0 |
| After P31B, Option B (deferred) | 5 |

**Under Option A**: 0 strategies are labeled `reconstructible`. The 5 Wave 1 strategies
remain `"retired"` in the catalog permanently. A `replay_available` boolean field will
surface in the catalog response for frontend queryability toggle.

---

## Wave 2 Readiness Sketch

P31B (production apply) requires separate explicit authorization phrase:
`YES apply P31B production wave1 daily539 retired`

**Scope**: Apply 7500 dry-run rows from `/tmp/p31a_temp.db` to `lottery_v2.db`.
Post-apply expected production rows: **20960** (12460 + 7500 = 19960 or 20460 depends on dedup).

**Governance guards after P31B**:
```bash
.venv/bin/python scripts/replay_lifecycle_drift_guard.py --strict
.venv/bin/python scripts/replay_branch_governance_guard.py --expected-rows 19960
```

**Estimated remaining `needs_promotion` candidates**: 19 strategies (24 total from P30 minus Wave 1's 5).

**Wave 2 priorities**:
1. Survey P30 output for next 5–10 `needs_promotion` strategies
2. Prioritise DAILY_539 strategies with complete algorithm specs
3. BIG_LOTTO candidates requiring TS3/Fourier adapters
4. POWER_LOTTO candidates with existing tool bindings
5. New adapter modules follow same P31A pattern (standalone, no registry mutation)

---

## Artifact Inventory

| File | Purpose |
|---|---|
| `lottery_api/models/p31a_wave1_retired_adapters.py` | Adapter wrappers (5 strategies) |
| `scripts/p31a_wave1_daily539_retired_adapter_readiness.py` | Main orchestration script |
| `tests/test_p31a_wave1_daily539_retired_adapter_readiness.py` | 35 verification tests |
| `tests/test_p31a_lifecycle_semantics.py` | 10 lifecycle semantics tests |
| `outputs/replay/p31a_temp_rehearsal_20260523.json` | R1/R2/R3 rehearsal results |
| `outputs/replay/p31a_wave1_daily539_retired_adapter_readiness_20260523.json` | Readiness report |
| `docs/replay/p31a_wave1_daily539_retired_adapter_readiness_20260523.md` | This document |

---

## Governance Summary

| Check | Result |
|---|---|
| Production DB rows before | 12460 |
| Production DB rows after | 12460 |
| Production DB unchanged | ✓ |
| P31A is read-only w.r.t. lottery_v2.db | ✓ |
| Lifecycle drift guard (`--strict`) | PASS |
| Branch governance guard | PASS |
| Forbidden staging scan | CLEAN |
| All 45 P31A tests pass | ✓ |
| Full 234-test governance suite | ✓ |
| Wave 1 adapters NOT in `_REGISTRY` | ✓ |
| Wave 1 adapters NOT in `_ALL_ADAPTERS` | ✓ |

---

## Next Step: P31B (Requires Separate Authorization)

P31B production apply is **NOT executed in P31A**.

To authorize P31B, provide the phrase:
```
YES apply P31B production wave1 daily539 retired
```
