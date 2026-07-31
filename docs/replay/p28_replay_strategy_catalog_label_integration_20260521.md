# P28: Replay Strategy Catalog Label Integration

**Date:** 2026-05-21
**Branch:** p28-replay-strategy-catalog-label-integration
**Classification:** P28_REPLAY_STRATEGY_CATALOG_LABEL_INTEGRATION_READY

---

## Purpose

Integrate P26 read-only strategy state labels into a new replay strategy catalog API endpoint so consumers can see all 59 developed strategies with safe, explicit status labels.

Makes it unambiguous which strategies are queryable (row-backed) vs artifact-only / retired / rejected / observation / no-data.

---

## Baseline

- P27B post-merge real browser smoke verified
- Backend 8002 healthy, Frontend 8081 operational
- Production rows: 12460
- DB writes: 0

---

## Implemented API Behavior

### `GET /api/replay/strategy-catalog`

**File:** `lottery_api/routes/replay.py`

Read-only endpoint returning all 59 P24 strategies with P26 safety labels.

No DB write. No migrations. No strategy execution.

**Response shape:**

```json
{
  "generated_at": "<ISO timestamp>",
  "phase": "P28",
  "total_strategies": 59,
  "label_summary": {
    "row-backed": 8,
    "artifact-only": 41,
    "retired": 5,
    "rejected-registered": 4,
    "observation": 1,
    ...
  },
  "row_backed_count": 8,
  "non_row_backed_count": 51,
  "no_db_write": true,
  "p26_label_module": "lottery_api/models/replay_strategy_state_labels.py",
  "strategies": [ ... ],
  "disclaimer": "..."
}
```

**Per-strategy entry:**

| Field | Type | Notes |
|-------|------|-------|
| `strategy_id` | str | Unique ID |
| `display_name` | str | Human-readable |
| `lottery_type` | str | BIG_LOTTO / POWER_LOTTO / DAILY_539 |
| `lifecycle_state` | str | ONLINE / ARTIFACT_ONLY / RETIRED / etc. |
| `replay_visibility_state` | str | ONLINE_ROW_BACKED / ARTIFACT_ONLY / etc. |
| `primary_label` | str | P26 canonical label key |
| `label_display_name` | str | User-facing label name |
| `label_description` | str | Label semantics |
| `row_count` | int | Production replay rows |
| `verified_row_count` | int | Verified replay rows |
| `is_row_backed` | bool | True if has production DB rows |
| `is_queryable` | bool | True only for row-backed strategies |
| `reconstructible_candidate` | bool | Logic recoverable from archive |
| `needs_manual_review` | bool | Requires manual evaluation |
| `unsupported_reason` | str\|null | Reason if unsupported |
| `safe_user_message` | str | User-facing status message |
| `source_artifact` | str\|null | Artifact path if known |
| `source_path` | str\|null | Source code path if known |

---

## Label Mapping Source

Single source of truth: `lottery_api/models/replay_strategy_state_labels.py` (P26 module).

The route calls:
- `get_full_label_catalog()` — builds per-strategy label entries from P24 inventory
- `get_label_summary()` — counts per label key
- `_load_p24_inventory()` — raw P24 data for enrichment fields

No label logic is duplicated in the route.

---

## Strategy Count Summary

| Label | Count |
|-------|-------|
| row-backed | 8 |
| artifact-only | 41 |
| retired | 5 |
| rejected-registered | 4 |
| observation | 1 |
| **Total** | **59** |

---

## User-Facing Safety Rules

| Label | Safe User Message |
|-------|------------------|
| row-backed | Replay rows available in DB — queryable via /api/replay/history |
| artifact-only | 尚無 replay rows / artifact-only — 僅目錄展示 |
| retired | 已退役 — lifecycle preserved for reference only |
| rejected-registered | 已拒絕 / registered stub — MUST NOT be executed |
| observation | 觀察中 — shadow evaluation, not in active production |

---

## UI Integration

UI catalog section **not implemented** in this phase (API-only).

The endpoint is ready for frontend consumption. Suggested next phase (P29):
- Add 「策略狀態總覽」 section to replay page
- Show label summary counts
- Per-strategy badge with `label_display_name`
- Row-backed entries link to replay history filter
- Non-queryable entries show `safe_user_message` without triggering history query

---

## Verification Commands

```bash
# P28 tests
.venv/bin/python -m pytest -q tests/test_p28_replay_strategy_catalog_label_integration.py

# Regression
.venv/bin/python -m pytest -q \
  tests/test_p26_non_online_strategy_state_labels.py \
  tests/test_replay_api_contract.py \
  tests/test_p28_replay_strategy_catalog_label_integration.py

# Guards
sqlite3 lottery_api/data/lottery_v2.db "SELECT COUNT(*) FROM strategy_prediction_replays;"
.venv/bin/python scripts/replay_lifecycle_drift_guard.py --strict
.venv/bin/python scripts/replay_branch_governance_guard.py \
  --expected-branch p28-replay-strategy-catalog-label-integration \
  --expected-rows 12460
```

---

## Test Results

| Suite | Result |
|-------|--------|
| P28 catalog tests | 21/21 PASS |
| P26 regression | PASS |
| Replay API contract | PASS |
| Total | 148 PASS |
| Browser smoke | N/A (no UI changes) |

---

## Guards

| Guard | Status |
|-------|--------|
| Pre-flight drift guard | PASS |
| Post-implementation drift guard | PASS |
| Pre-flight governance guard | PASS (branch=main) |
| Post-implementation governance guard | PASS (branch=p28-..., rows=12460) |
| Production rows before | 12460 |
| Production rows after | 12460 |

---

## Risks / Limitations

1. **API-only** — no UI catalog display in this phase
2. **Static inventory** — catalog is read from P24 file, not live DB query
3. **Browser smoke** not run — no frontend changes made

---

## Final Classification

`P28_REPLAY_STRATEGY_CATALOG_LABEL_INTEGRATION_READY`

Next: P29 UI catalog section integration.
