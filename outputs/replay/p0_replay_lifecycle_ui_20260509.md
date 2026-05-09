# P0 Replay Lifecycle UI — Execution Report
**Date:** 2026-05-09  
**Branch:** codex/p0-replay-lifecycle-ui-20260509  
**Worker:** P0-Replay-UI Executor  
**Report to:** CTO Agent

---

## Completed

| Step | Status | Description |
|------|--------|-------------|
| P0-A | ✅ DONE | Strategy Lifecycle SSOT — enum expanded, list_strategies() updated |
| P0-B | ✅ DONE | Coverage Audit — 0 coverage gaps; all 6 ONLINE strategies have replay rows |
| P0-C | ✅ DONE | API lifecycle filter — /strategies + /history both support lifecycle_status param |
| P0-D | ✅ DONE | Frontend UI — lifecycle filter dropdown + badge column + reject_reason column |
| P0-E | ✅ DONE | Branch: codex/p0-replay-lifecycle-ui-20260509 (from main @ 32fc1c8) |

---

## Lifecycle SSOT Schema

**File:** `lottery_api/models/replay_strategy_registry.py`

Expanded `status` enum from `ACTIVE / RETIRED` to:

| New Value   | Meaning | Maps from |
|-------------|---------|-----------|
| `ONLINE`    | Deployed and active in replay generation | `ACTIVE` (normalised) |
| `OFFLINE`   | Suspended; rows preserved | (new) |
| `REJECTED`  | Rejected during governance review | (new) |
| `OBSERVATION` | Shadow evaluation period | (new) |
| `RETIRED`   | Formally retired | (unchanged) |

**Backward compat:** `ACTIVE` is accepted as alias and normalised to `ONLINE` in all outputs via `normalise_lifecycle_status()`. No existing caller is broken.

**Current adapter states:** All 6 existing adapters changed from `status="ACTIVE"` → `status="ONLINE"` (canonical rename only; no governance state changed).

**Migration plan (not executed):** See `outputs/replay/p0_replay_lifecycle_schema_diff_20260509.json` §db_schema_diff. DB schema is unchanged; lifecycle is in-memory.

---

## Coverage Audit

See full detail: `outputs/replay/p0_replay_lifecycle_coverage_20260509.md`

| lottery_type | strategy count | ONLINE | coverage gaps |
|-------------|---------------|--------|---------------|
| BIG_LOTTO   | 2 | 2 | 0 |
| POWER_LOTTO | 2 | 2 | 0 |
| DAILY_539   | 2 | 2 | 0 |

**Total coverage gaps: 0**

Note: 20 `REPLAY_ERROR` rows exist for `daily539_f4cold` and `daily539_markov_cold` from FAILED_LEGACY run #3 — retained for audit traceability per `replay_data_hygiene.md §2`. Not a gap.

Lifecycles with 0 strategies currently: OFFLINE, REJECTED, OBSERVATION, RETIRED — infrastructure is in place.

---

## API Contract Diff

### GET /api/replay/strategies
**New params:** `lifecycle_status` (ONLINE | OFFLINE | REJECTED | OBSERVATION | RETIRED; default: all)  
**New response fields per strategy:** `strategy_lifecycle_status` (canonical normalised value)  
**New top-level fields:** `filter_lifecycle_status`, `filter_lottery_type`  
**Backward compat:** `filter` key retained as alias for `filter_lottery_type`  
**Behaviour change:** Now returns ALL lifecycle states by default (was: ACTIVE-only)

### GET /api/replay/history
**New params:** `lifecycle_status` (optional filter; resolves to strategy_id IN clause)  
**New response field per record:** `strategy_lifecycle_status`  
**New top-level field:** `filter_lifecycle_status`  
**No change to:** disclaimer, data_scope, read-only semantics, causal integrity fields

---

## Frontend Changes

**File:** `index.html` → `#replay-section`

1. **Lifecycle filter dropdown** added to filter bar (between 彩種 and 策略):
   - Options: 全部 / 🟢 上線 (ONLINE) / ⚫ 下線 (OFFLINE) / 🔴 拒絕 (REJECTED) / 🟡 觀察 (OBSERVATION) / ⚪ 退役 (RETIRED)
   - Element id: `rp-lifecycle-select`
   - Changing this filter refreshes the strategy dropdown (calls `rpLoadStrategies()`)
   
2. **生命週期 (lifecycle badge) column** added to history table — renders coloured badge via `rpLifecycleBadge()`:
   - ONLINE: green, 上線
   - OFFLINE: dark, 下線
   - REJECTED: red, 拒絕
   - OBSERVATION: amber, 觀察
   - RETIRED: grey, 退役

3. **拒絕原因 (reject_reason) column** added — truncated to 30 chars with full tooltip on hover

4. **table colspan** updated: 9 → 11 (for all empty-state and detail rows)

5. **rpQuery()** passes `lifecycle_status` to `/api/replay/history`

6. **rpLoadStrategies()** passes `lifecycle_status` to `/api/replay/strategies`

7. **rpUpdateURL() / rpRestoreFromURL()** persist `rp_lc` param in URL state

8. **All existing disclaimers, coverage notes, and UX preserved** — no wording changed or removed

---

## Validation Results

```
tests/test_replay_api_contract.py      — 25 passed
tests/test_replay_freshness_cadence.py — 8 passed
tests/test_replay_browser_smoke.py     — 30 passed
TOTAL                                  — 63 passed / 0 failed
```

Baseline before P0 work: 63 passed. **No regression.**

Browser smoke test (`pytest tests/test_replay_browser_smoke.py`): **PASSED** (static HTML/JS inspection; no browser environment needed — all 30 checks pass).

---

## Files Created / Modified

| File | Action | Notes |
|------|--------|-------|
| `lottery_api/models/replay_strategy_registry.py` | Modified | P0-A: lifecycle enum, list_strategies, normalise_lifecycle_status, get_strategy_lifecycle_status |
| `lottery_api/routes/replay.py` | Modified | P0-C: lifecycle_status query params on /strategies + /history |
| `index.html` | Modified | P0-D: lifecycle filter, badge column, reject_reason column |
| `outputs/replay/p0_replay_lifecycle_ui_20260509.md` | Created | This report |
| `outputs/replay/p0_replay_lifecycle_coverage_20260509.md` | Created | P0-B coverage audit |
| `outputs/replay/p0_replay_lifecycle_schema_diff_20260509.json` | Created | P0-A schema diff + migration plan |

---

## Commit / PR Result

Branch: `codex/p0-replay-lifecycle-ui-20260509` (created from `main` @ `32fc1c8`)

Commit files (per COMMIT RULES):
- `lottery_api/routes/replay.py`
- `lottery_api/models/replay_strategy_registry.py`
- `index.html`
- `outputs/replay/p0_replay_lifecycle_*`

Excluded from commit (per HARD SCOPE):
- `*.db` / `*.db-wal` / `*.db-shm`
- Any active strategy state files
- Any unrelated frontend changes

PR to be raised against `main` via `codex/p0-replay-lifecycle-ui-20260509` with required checks.

---

## What Was Not Changed

- Active strategy states — all 6 remain functionally equivalent to before (ONLINE = ACTIVE)
- Branch protection settings — unchanged
- Production DB — not touched; no rows written, deleted, or updated
- Replay API disclaimer wording — preserved verbatim
- Replay API read-only semantics — no write operations added
- H6 / active strategy state files — not modified
- `strategy_replay_runs` table — not modified
- `strategy_prediction_replays` table — not modified
- `docs/archive/` — not modified
- `memory/`, `wiki/` — not modified
- PR #2 (`codex/p1-6g-branch-protection-execution`) — not touched; parallel flow

---

## Remaining Risks

1. **All 6 strategies currently ONLINE** — the UI lifecycle filter for OFFLINE/REJECTED/OBSERVATION/RETIRED shows 0 results until those states are populated. This is expected; the infrastructure is in place.

2. **Lifecycle state is in-memory only** — if a new strategy is added to the registry file in a different lifecycle state, it is immediately visible in the UI. A DB-persisted `strategy_lifecycle` table (see migration plan) would provide audit trail for state transitions. Not implemented in P0.

3. **`test_replay_api_contract.py` history test wrapper** — the test calls `get_replay_history()` directly (bypasses FastAPI routing). The `Query()` object guard added (`isinstance(..., str)`) works but is a non-standard pattern. A future refactor could use a pure function that FastAPI wraps.

4. **Browser smoke test** — all 30 checks pass via static HTML/JS inspection. Live E2E browser automation deferred to `P1-replay-ui-e2e`.

---

## Follow-up Tasks

| ID | Title | Priority |
|----|-------|----------|
| P1-replay-ui-e2e | End-to-end browser test for lifecycle filter interaction | P1 |
| P1-lifecycle-drift-guard | CI check: warn if registry lifecycle_status diverges from a DB-persisted state | P1 |
| P1-lifecycle-db-migration | Implement `strategy_lifecycle` DB table and migration script | P1 |
| P1-lifecycle-all-states-demo | Add at least one OFFLINE/REJECTED/OBSERVATION strategy to exercise the full UI | P1 |

---

## Final Marker

P0_REPLAY_LIFECYCLE_UI_READY_FOR_REVIEW
