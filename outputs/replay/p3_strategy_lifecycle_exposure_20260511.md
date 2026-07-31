# P3 Strategy Lifecycle Exposure — Governance Report

**Date:** 2026-05-11  
**Branch:** `feature/p3-strategy-lifecycle-exposure-20260511`  
**Stacked On:** PR #36 (`feature/p2-non-online-strategy-lifecycle-registry-20260511`)

---

## Objective

Expose the lifecycle metadata populated in P2 via a public API layer and CLI report tool.  
All operations are read-only against the in-memory registry — no DB writes, no replay execution,  
no adapter instances returned to callers.

---

## PR #36 Readiness at P3 Start

| Check | Status |
|-------|--------|
| PR state | OPEN |
| Mergeable | MERGEABLE |
| Merge state | CLEAN |
| CI checks | 2 passing, 1 skipped, 0 failing |
| Head branch | `feature/p2-non-online-strategy-lifecycle-registry-20260511` |

P3 branch created directly from the P2 branch tip (commit `4184998`), so all P2 registry work is included.

---

## New Public API — `lottery_api/models/replay_strategy_registry.py`

Five functions added after `get_adapters_for_lottery()`:

| Function | Purpose |
|----------|---------|
| `list_strategy_lifecycle_metadata(lifecycle_status=None)` | All 16 metadata dicts, filterable by status |
| `get_strategy_lifecycle_metadata(strategy_id)` | Single-ID lookup; raises `KeyError` if unknown |
| `summarize_strategy_lifecycle_counts()` | `{status: count}` in canonical declaration order |
| `list_executable_strategy_ids()` | Sorted ONLINE-only IDs; equals `_REGISTRY` keys |
| `list_non_executable_strategy_ids()` | Sorted non-ONLINE IDs (stubs only) |

**Hard constraints respected by all functions:**
- No `sqlite3` import or connection
- No `replay_history` modification
- No adapter instances returned to callers
- Non-ONLINE stubs cannot gain executable capability through these APIs

---

## CLI Report — `scripts/report_strategy_lifecycle_registry.py`

```
python3 scripts/report_strategy_lifecycle_registry.py           # text report
python3 scripts/report_strategy_lifecycle_registry.py --json    # JSON stdout
python3 scripts/report_strategy_lifecycle_registry.py --json --output path/out.json
```

CLI sources data **only** from the 5 new API functions — no direct DB access, no file reads beyond the module import.

**JSON output schema:**
```json
{
  "generated_at": "<ISO-8601 UTC>",
  "lifecycle_counts": {"ONLINE": 6, "REJECTED": 4, "OBSERVATION": 1, "RETIRED": 5},
  "total": 16,
  "executable_strategy_ids": ["biglotto_deviation_2bet", ...],
  "non_executable_strategy_ids_by_status": {"REJECTED": [...], ...},
  "no_db_write": true,
  "no_db_write_note": "...",
  "marker": "P3_LIFECYCLE_REPORT_CLI_READY"
}
```

---

## Lifecycle Counts (as of P3 implementation)

| Status | Count | Executable? |
|--------|-------|-------------|
| ONLINE | 6 | YES — registered in `_REGISTRY` |
| REJECTED | 4 | NO — `LifecycleNotExecutable` raised |
| RETIRED | 5 | NO — `LifecycleNotExecutable` raised |
| OBSERVATION | 1 | NO — `LifecycleNotExecutable` raised |
| **TOTAL** | **16** | |

---

## Strategy IDs by Status

### ONLINE (executable, 6)
- `biglotto_deviation_2bet`
- `biglotto_triple_strike`
- `daily539_f4cold`
- `daily539_markov_cold`
- `power_orthogonal_5bet`
- `power_precision_3bet`

### REJECTED (metadata stub, 4)
- `biglotto_ts3_acb_4bet`
- `biglotto_ts3_markov_freq_5bet`
- `p1_deviation_2bet_539`
- `power_shlc_midfreq`

### RETIRED (metadata stub, 5)
- `acb_1bet`
- `acb_markov_midfreq`
- `acb_markov_midfreq_3bet`
- `midfreq_acb_2bet`
- `midfreq_fourier_2bet`

### OBSERVATION (metadata stub, 1)
- `h6_gate_mk20_ew85`

---

## No-DB-Write Evidence

1. `TestNoDbWrite::test_no_db_write_on_exposure_api_calls` — patches `sqlite3.connect`, calls all 5 API functions, asserts zero connections.
2. `TestNoDbWrite::test_no_db_write_on_cli_text_mode` — patches `sqlite3.connect`, runs CLI text mode, asserts zero connections.
3. `TestNoDbWrite::test_no_db_write_on_cli_json_mode` — patches `sqlite3.connect`, runs CLI JSON mode, asserts zero connections.

All three pass.

---

## No-Backfill Evidence

P3 adds zero DB writes, zero DB reads, zero modifications to `replay_history`.  
CLI script imports only from `lottery_api.models.replay_strategy_registry`.  
Scripts directory has no DB connection logic.

---

## Online Strategies Remain Unchanged

`_REGISTRY` still contains exactly the same 6 ONLINE strategy IDs as before P3.  
`list_executable_strategy_ids()` is guaranteed to equal `sorted(_REGISTRY.keys())`.  
P2 test class `TestOnlineStrategiesUnchanged` (22 tests) continues to pass.

---

## Test Results

```
tests/test_replay_strategy_lifecycle_registry.py   22 passed
tests/test_replay_strategy_lifecycle_exposure.py   39 passed
─────────────────────────────────────────────────────────────
TOTAL:  61 passed in 0.08s
```

P3 adds 39 new tests across 4 classes:
- `TestListStrategyLifecycleMetadata` (8 tests)
- `TestGetStrategyLifecycleMetadata` (7 tests)
- `TestSummarizeStrategyLifecycleCounts` (4 tests)
- `TestListExecutableNonExecutableIds` (8 tests)
- `TestNoDbWrite` (3 tests)
- `TestCLIReport` (8 tests)

---

## Files Changed

| File | Change |
|------|--------|
| `lottery_api/models/replay_strategy_registry.py` | +5 public functions (P3 Exposure API section) |
| `scripts/report_strategy_lifecycle_registry.py` | NEW — CLI report tool |
| `tests/test_replay_strategy_lifecycle_exposure.py` | NEW — 39 tests |
| `outputs/replay/p3_strategy_lifecycle_exposure_20260511.md` | NEW — this file |

---

## P4 Suggestions (out of scope for P3)

- HTTP endpoint: `GET /api/v1/strategies/lifecycle` to expose `list_strategy_lifecycle_metadata()` output
- Drift detection: CI check that alerts if `list_executable_strategy_ids()` diverges from DB's ONLINE set
- Promotion gate: automated PR that moves an OBSERVATION strategy to ONLINE after sustained positive EV
- Deprecation gate: automated PR that moves an ONLINE strategy to RETIRED after sustained negative performance

---

## Governance Markers

```
P3_STRATEGY_LIFECYCLE_EXPOSURE_READY
P3_LIFECYCLE_METADATA_NO_DB_WRITE_CONFIRMED
P3_EXECUTABLE_STRATEGIES_REMAIN_ONLINE_ONLY
P3_STRATEGY_LIFECYCLE_EXPOSURE_TESTS_PASS
P3_LIFECYCLE_REPORT_CLI_READY
```
