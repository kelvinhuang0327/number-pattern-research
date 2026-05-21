# P26: Non-ONLINE Strategy State Labels

**Phase**: P26  
**Date**: 2026-05-21  
**Branch**: `p26-non-online-strategy-state-labels`  
**Base**: `main` @ `aa46375` (P25a merged)  
**Classification**: `P26_NON_ONLINE_STRATEGY_STATE_LABELS_READY`

---

## Summary

P26 introduces a **read-only label mapping system** (`replay_strategy_state_labels.py`) so the replay system can display all 59 developed strategies with safe, accurate user-facing labels — without pretending that artifact-only / retired / rejected / observation strategies have live replay rows.

**Scope is strictly read-only:**
- No DB writes
- No migrations
- No new tables
- No strategy execution
- Production rows locked at **12460**

---

## Label Definitions (9 canonical labels)

| Label Key | Display | Queryable | Description |
|---|---|---|---|
| `row-backed` | Row-Backed (Live) | ✅ Yes | Strategy has production replay rows; fully queryable |
| `artifact-only` | Artifact-Only | ❌ No | Strategy exists as configuration artifact only; no production rows |
| `no-data` | No Data | ❌ No | Strategy is registered but has no production rows |
| `reconstructible` | Reconstructible | ❌ No | Artifact-only strategy that can be replayed from historical data |
| `manual-review` | Manual Review Required | ❌ No | Strategy needs human review before classification |
| `unsupported` | Unsupported | ❌ No | Strategy cannot be replayed due to technical limitations |
| `retired` | Retired | ❌ No | Strategy was previously active; deliberately retired |
| `rejected-registered` | Rejected (Registered) | ❌ No | Strategy failed validation but has registered configuration |
| `observation` | Observation Mode | ❌ No | Strategy under observation; not yet promoted to production |

---

## Label Precedence Logic

```
assign_label(replay_visibility_state, row_count=0, reconstructible_candidate=False,
             needs_manual_review=False, unsupported_reason=None) -> str
```

Precedence (first match wins):
1. `ONLINE_ROW_BACKED` + `row_count > 0` → **row-backed**
2. `ONLINE_ROW_BACKED` + `row_count == 0` → **no-data**
3. `needs_manual_review = True` → **manual-review**
4. `unsupported_reason is not None` → **unsupported**
5. `ARTIFACT_ONLY` + `reconstructible_candidate=True` → **reconstructible**
6. `ARTIFACT_ONLY` → **artifact-only**
7. `RETIRED` → **retired**
8. `REJECTED_REGISTERED` → **rejected-registered**
9. `OBSERVATION` → **observation**
10. (fallback) → **no-data**

> Note: `RETIRED` and `REJECTED_REGISTERED` strategies with `reconstructible_candidate=True` keep their own labels (retired/rejected-registered), not `reconstructible`. The `reconstructible` label is reserved for `ARTIFACT_ONLY` strategies only.

---

## P24 Inventory Results

Based on `p24_full_strategy_universe_inventory_20260521.json` (59 strategies):

| Label | Count |
|---|---|
| `row-backed` | 8 |
| `artifact-only` | 41 |
| `retired` | 5 |
| `rejected-registered` | 4 |
| `observation` | 1 |
| `reconstructible` | 0 (label defined, no current candidates) |
| `manual-review` | 0 (label defined, none flagged) |
| `unsupported` | 0 (label defined, none flagged) |
| `no-data` | 0 |
| **TOTAL** | **59** |

---

## Module: `lottery_api/models/replay_strategy_state_labels.py`

### Exported API

```python
# Constants
LABEL_DEFINITIONS: dict[str, dict]   # 9 canonical label definitions
ALL_LABEL_KEYS: frozenset[str]        # frozenset of all 9 label keys

# Pure functions
assign_label(replay_visibility_state, row_count=0, reconstructible_candidate=False,
             needs_manual_review=False, unsupported_reason=None) -> str
is_row_backed(replay_visibility_state, row_count=0) -> bool
get_label_definition(label_key) -> Optional[dict]  # returns copy
build_label_entry(strategy: dict) -> dict

# Data access (reads P24 JSON; no DB access)
get_full_label_catalog() -> list[dict]        # all 59 entries with labels
get_label_for_strategy(strategy_id) -> Optional[dict]
get_label_summary() -> dict                   # label_key → count
```

### Catalog Entry Schema

Each entry returned by `get_full_label_catalog()` / `get_label_for_strategy()`:

```json
{
  "strategy_id": "...",
  "display_name": "...",
  "lottery_type": "...",
  "lifecycle_state": "...",
  "replay_visibility_state": "...",
  "row_count": 0,
  "reconstructible_candidate": false,
  "primary_label": "artifact-only",
  "label_display": "Artifact-Only",
  "label_description": "...",
  "is_row_backed": false,
  "queryable": false,
  "reason_text": "..."
}
```

---

## Test Suite

**File**: `tests/test_p26_non_online_strategy_state_labels.py`

| Class | Tests | Coverage |
|---|---|---|
| `TestLabelDefinitions` | 10 | All 9 labels defined, fields present, queryable rules |
| `TestAssignLabel` | 20 | All 9 label paths, precedence, purity, unknown state |
| `TestIsRowBacked` | 7 | All 5 visibility states + edge cases |
| `TestP24Integration` | 18 | 59 strategies, distribution counts, field preservation |
| `TestGetLabelForStrategy` | 5 | Known strategies, unknown→None |
| `TestGetLabelSummary` | 8 | Dict shape, all 9 keys, correct counts |
| `TestBuildLabelEntry` | 3 | Online / artifact / rejected-registered |
| `TestAntiContamination` | 6 | No sqlite3, no DatabaseManager, no SQL writes, rows=12460 |
| **TOTAL** | **83** | **83/83 PASS** |

---

## Regression Verification

| Suite | Passed | Total | Result |
|---|---|---|---|
| P26 label suite | 83 | 83 | ✅ PASS |
| Canonical regression (API contract, drift guard, governance) | 98 | 98 | ✅ PASS |
| Lifecycle drift guard | — | — | ✅ PASS |
| Branch governance guard | — | — | ✅ PASS |

---

## Safety Record

- `lottery_api/data/lottery_v2.db` — **12460 rows, unchanged**
- No migrations executed
- No new tables created
- No strategy execution triggered
- Module contains no `sqlite3`, no `DatabaseManager`, no SQL writes

---

## Files Changed

| File | Type | Description |
|---|---|---|
| `lottery_api/models/replay_strategy_state_labels.py` | NEW | P26 label module (pure functions, no DB) |
| `tests/test_p26_non_online_strategy_state_labels.py` | NEW | 83-test verification suite |
| `outputs/replay/p26_non_online_strategy_state_labels_20260521.json` | NEW | Evidence artifact |
| `docs/replay/p26_non_online_strategy_state_labels_20260521.md` | NEW | This document |

---

## Next Phase

**P27**: Integrate P26 labels into the `/api/replay/strategies` and `/api/replay/strategy-lifecycle` endpoints so the frontend can display all 59 strategies with their state labels.
