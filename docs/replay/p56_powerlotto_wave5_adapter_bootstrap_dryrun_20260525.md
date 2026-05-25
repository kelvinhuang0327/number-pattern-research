# P56: Wave 5 POWER_LOTTO Adapter Bootstrap + Dry-Run Rehearsal

**Branch**: `p56-powerlotto-wave5-adapter-bootstrap-dryrun`  
**Base**: `776c173` (P55-A merged to main)  
**Date**: 2026-05-25  
**Classification**: `P56_POWERLOTTO_WAVE5_ADAPTER_BOOTSTRAP_DRYRUN_COMPLETED`  
**Status**: ✅ COMPLETED

---

## Wave 5 Candidate Shortlist

| Strategy ID | Score | Priority | Source Tool |
|---|---|---|---|
| `cold_complement_2bet` | 75 | HIGH | `tools/power_twin_strike.py` |
| `fourier30_markov30_2bet` | 72 | HIGH | `tools/power_2bet_hedging.py` |
| `zonal_entropy_2bet` | 64 | MEDIUM | `tools/power_scientific_zonal.py` |

Shortlist sourced from P55 candidate planning output:  
`outputs/replay/p55_powerlotto_wave5_candidate_planning_20260525.json`

---

## Adapter Design

### POWER_LOTTO Format Semantics

| Parameter | Value |
|---|---|
| First-zone pool | `[1, 38]` |
| First-zone pick count | `6 unique numbers` |
| Special-zone pool | `[1, 8]` |
| Special-zone pick count | `1 number` |
| `hit_count` | First-zone matches only (0–6) |
| `special_hit` | `1` if predicted_special == actual_special, else `0` |

### cold_complement_2bet

**Algorithm**: Cold numbers strategy — select the 6 numbers with the lowest
appearance frequency within the last 100 draws. Ties broken by ascending number
value (lowest number wins among equal-frequency numbers).

```python
pool = range(1, 39)           # [1, 38] inclusive
freq = Counter(last 100 draws)
predicted = sorted(pool, key=lambda n: (freq.get(n, 0), n))[:6]
```

**Window**: 100 draws  
**Min history**: 10 draws  
**Determinism**: ✅ Fully deterministic — Counter + sort, no randomness

### fourier30_markov30_2bet

**Algorithm**: Frequency-weighted strategy — each draw in the last 30 draws
is weighted by its recency using a linear ramp (`weight = 1.0 + 2.0*(i/n)`
where `i=0` is the oldest draw and `i=n-1` is the newest). Numbers are ranked
by cumulative weighted frequency; top 6 selected.

```python
pool = range(1, 39)
window = last 30 draws
for i, draw in enumerate(window):
    weight = 1.0 + 2.0 * (i / len(window))   # linear recency ramp
    for num in draw["numbers"]:
        weighted_freq[num] += weight
predicted = sorted(pool, key=lambda n: (-weighted_freq.get(n, 0.0), n))[:6]
```

**Window**: 30 draws  
**Min history**: 30 draws  
**Determinism**: ✅ Fully deterministic — weighted sort, no randomness

### zonal_entropy_2bet

**Algorithm**: Entropy-gated adaptive strategy. The Shannon entropy of the
zone distribution over the last 30 draws is computed. If entropy exceeds the
chaos threshold (2.2 bits), the distribution is too unpredictable and the
strategy falls back to cold numbers (window=100). Otherwise, it selects the
hottest numbers (highest frequency in window=30).

```python
ZONES = 8   # zone(n) = 7 if n > 35 else (n-1) // 5
entropy = shannon_entropy(zone_counts, last 30 draws)   # bits

if entropy > 2.2:   # chaotic — cold fallback
    predicted = coldest 6 in [1,38] over last 100 draws
else:               # structured — hot mode
    predicted = hottest 6 in [1,38] over last 30 draws
```

**Window**: 30/100 draws (regime-dependent)  
**Min history**: 30 draws  
**Determinism**: ✅ Fully deterministic — no `random.seed()`, no `random.sample()`

---

## Bugs Fixed from Source Tools

| Source File | Bug | Fix Applied in P56 |
|---|---|---|
| `tools/power_scientific_zonal.py` | `range(1, 38)` — pool missing number 38 | Changed to `range(1, 39)` |
| `tools/power_scientific_zonal.py` | `random.seed(42)` + `random.sample()` — non-deterministic | Replaced with deterministic sorted ranking |

---

## Determinism Guarantees

All three adapters are fully deterministic:
- No `import random` in the adapter module
- No `random.seed()` calls
- No `random.sample()` calls
- All tie-breaking by ascending number value (deterministic sort key)
- Same history → same prediction, always

Verified by `TestP56Determinism` in the test suite.

---

## Dry-Run Rehearsal Results

| Metric | Value |
|---|---|
| Total draws loaded | 1912 POWER_LOTTO draws |
| Window periods | 1500 |
| Strategies | 3 |
| Total rows generated | 4500 (3 × 1500) |
| Schema validation | ✅ PASS (0 errors) |
| Data leakage check | ✅ PASS (0 violations) |

### Per-Strategy Row Counts

| Strategy | Rows | Predicted | M3+ Hit Rate | Special Hit Rate |
|---|---|---|---|---|
| `cold_complement_2bet` | 1500 | 1500 | 3.67% | 11.87% |
| `fourier30_markov30_2bet` | 1500 | 1500 | 4.07% | 11.87% |
| `zonal_entropy_2bet` | 1500 | 1500 | 3.67% | 11.87% |

**Expected random M3+ baseline (6/38)**: ≈ 3.87%  
**`fourier30_markov30_2bet`** outperforms baseline (+0.20%).  
**`cold_complement_2bet`** and **`zonal_entropy_2bet`** below baseline (−0.20%).

> Note: Dry-run hit rates are measured against historical actuals. Baseline
> comparison is exploratory; statistical significance requires separate analysis.

---

## R1 / R2 / R3 Rehearsal

| Check | Result |
|---|---|
| **R1** — Apply 4500 rows to temp DB | ✅ 4500 rows inserted |
| **R2** — Idempotency (re-insert same rows) | ✅ 0 duplicates inserted |
| **R3** — Rollback (delete all rows) | ✅ 0 rows remain after rollback |

Temp DB: `/tmp/p56_temp.db` (created fresh; emptied by R3)

---

## Production DB Integrity

| Check | Before | After | Status |
|---|---|---|---|
| Total replay rows | 42460 | 42460 | ✅ UNCHANGED |
| POWER_LOTTO rows | 9140 | 9140 | ✅ UNCHANGED |
| Champion `fourier_rhythm_3bet` | ONLINE | ONLINE | ✅ UNCHANGED |

**Wave 5 strategies do NOT appear in production DB** — dry-run rows are in
`/tmp/p56_temp.db` only.

---

## Governance Constraints

| Constraint | Status |
|---|---|
| Production DB write | ❌ NONE — read-only |
| Lifecycle promotion | ❌ NONE — all rows are `DRY_RUN` |
| Champion replacement | ❌ NONE — `fourier_rhythm_3bet` stays ONLINE |
| Registry registration | ❌ NONE — adapters NOT added to `replay_strategy_registry` |
| `random.seed()` in adapters | ❌ NONE — fully deterministic |
| `git add -A` / `git add .` | ❌ FORBIDDEN — whitelist commit only |

---

## Test Suite Results

**5-File Governance Suite**: 173/173 PASSED

| Test File | Tests | Status |
|---|---|---|
| `test_replay_lifecycle_drift_guard.py` | — | ✅ PASS |
| `test_replay_api_contract.py` | — | ✅ PASS |
| `test_replay_branch_governance_guard.py` | — | ✅ PASS |
| `test_p55_powerlotto_wave5_candidate_planning.py` | — | ✅ PASS |
| `test_p56_powerlotto_wave5_adapter_bootstrap_dryrun.py` | — | ✅ PASS |

---

## Artifacts

| File | Description |
|---|---|
| `lottery_api/models/p56_wave5_powerlotto_adapters.py` | Wave 5 adapter wrappers (DRY_RUN only) |
| `scripts/p56_powerlotto_wave5_adapter_bootstrap_dryrun.py` | Dry-run orchestrator (R1/R2/R3) |
| `tests/test_p56_powerlotto_wave5_adapter_bootstrap_dryrun.py` | Governance test suite (173 tests) |
| `docs/replay/p56_powerlotto_wave5_adapter_bootstrap_dryrun_20260525.md` | This document |
| `outputs/replay/p56_powerlotto_wave5_adapter_bootstrap_dryrun_20260525.json` | Machine-readable run artifact |

---

## Post-Flight Guards

| Guard | Result |
|---|---|
| `replay_lifecycle_drift_guard.py --strict` | ✅ REPLAY_LIFECYCLE_DRIFT_GUARD_PASS |
| `replay_branch_governance_guard.py --expected-rows 42460` | ✅ BRANCH_GOVERNANCE_PASS |

---

## P57 Readiness

P57 is the **production apply** phase. Before P57 can begin:

1. P56 classification must be `COMPLETED` ✅
2. All 3 adapters must pass statistical significance testing (p < 0.05)
3. All 3 adapters must pass walk-forward OOS validation
4. Sharpe Ratio > 0 required for each adapter
5. Explicit P57 authorization required — P56 completion is NOT automatic approval

**Current recommendation based on M3+ hit rates**:
- `fourier30_markov30_2bet`: above baseline (+0.20%) — most promising candidate
- `cold_complement_2bet` / `zonal_entropy_2bet`: below baseline — require further OOS testing

P57 production apply is a separate decision point with full governance review.
