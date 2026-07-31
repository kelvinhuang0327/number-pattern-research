# P8 Governance Report — PR #40 Readiness Review

**Report ID:** p8_pr40_readiness_review_20260511  
**Date:** 2026-05-11  
**Reviewer:** Senior Governance UI Review Agent  
**PR:** [#40 — feat(replay): expose strategy lifecycle via read-only endpoint and dashboard (P7)](https://github.com/kelvinhuang0327/number-pattern-research/pull/40)

---

## 1. Objective

Execute a merge readiness review of PR #40 (P7 read-only lifecycle endpoint + dashboard). Confirm the PR is safe, scoped, and testable before presenting to user YES gate.

---

## 2. PR #40 Status

| Field | Value |
|---|---|
| Number | #40 |
| Title | feat(replay): expose strategy lifecycle via read-only endpoint and dashboard (P7) |
| State | OPEN |
| Base | main |
| Head | feature/p7-strategy-lifecycle-readonly-dashboard-20260511 |
| Mergeable | MERGEABLE |
| mergeStateStatus | CLEAN |
| CI | ✅ All checks successful (2 passed, 1 skipped, 0 failing) |

---

## 3. Diff Scope Review — PASS

### Files changed (4 total)

| File | Change | P7 scope? |
|---|---|---|
| `lottery_api/routes/replay.py` | +56 lines — new endpoint + imports | ✅ YES |
| `tests/test_replay_strategy_lifecycle_endpoint.py` | +176 lines — new test file | ✅ YES |
| `outputs/replay/p7_strategy_lifecycle_readonly_endpoint_dashboard_20260511.md` | +133 lines — governance report | ✅ YES |
| `index.html` | +99 lines — lifecycle registry card + JS | ✅ YES |

**`lottery_v2.db` — NOT in diff.** ✅  
**All 4 files are expected P7 scope. No unrelated files.** ✅

---

## 4. Backend Endpoint Review — PASS

### Endpoint: `GET /api/replay/strategy-lifecycle`

| Check | Result |
|---|---|
| Path is GET (read-only) | ✅ |
| Uses only P3 in-memory API | ✅ (`list_strategy_lifecycle_metadata`, `summarize_strategy_lifecycle_counts`, `list_executable_strategy_ids`, `list_non_executable_strategy_ids`) |
| No direct DB read from endpoint | ✅ |
| No `sqlite3.connect()` call in endpoint body | ✅ (file imports `sqlite3` for other existing endpoints; new endpoint does not call it) |
| No `get_one_bet()` call | ✅ |
| No `get_adapter()` call for non-ONLINE | ✅ |
| `no_db_write = True` in response | ✅ |
| `marker = "P7_STRATEGY_LIFECYCLE_ENDPOINT_READY"` | ✅ |
| Non-ONLINE strategies listed but not executable | ✅ (`is_executable` = `strategy_id in set(exec_ids)`, only ONLINE qualify) |
| Exception handler returns HTTP 500, no data leak | ✅ |

### Registry Invariants Smoke Test

```
metadata: 16
counts: {'ONLINE': 6, 'REJECTED': 4, 'OBSERVATION': 1, 'RETIRED': 5}
exec: 6
non_exec: 10
P8_BACKEND_REGISTRY_INVARIANTS_PASS
```

---

## 5. Backend Tests Result — PASS

### Targeted P7 endpoint tests

```
tests/test_replay_strategy_lifecycle_endpoint.py  26 passed in 0.28s
```

### Full lifecycle suite (P2 + P3 + P7)

```
tests/test_replay_strategy_lifecycle_registry.py
tests/test_replay_strategy_lifecycle_exposure.py
tests/test_replay_strategy_lifecycle_endpoint.py
87 passed in 0.23s
```

---

## 6. Full Suite Result and Pre-existing Failure Analysis

### PR branch (feature/p7-strategy-lifecycle-readonly-dashboard-20260511)

```
11 failed, 204 passed in 15.11s
```

### main branch (ff11226)

```
11 failed, 178 passed in 40.78s
```

**Delta: 204 - 178 = 26 new passing tests** — matches P7 test file exactly.

### Pre-existing failure classification

| Test file | Count | Type | Cause | Blocks PR #40? |
|---|---|---|---|---|
| `test_mab_ensemble.py::TestThompsonSamplingEnsemble` | 6 | Unit | MAB ensemble implementation divergence | ❌ NO — unrelated to P7 |
| `test_replay_lifecycle_browser_e2e.py` | 5 | Browser E2E | Requires live HTTP server; no server running | ❌ NO — infrastructure requirement |

**All 11 failures are identical on main and on PR branch.** PR #40 introduced zero new failures.

---

## 7. Frontend Read-only Review — PASS

### Lifecycle registry card (`#rp-lifecycle-registry-card`)

| Check | Result |
|---|---|
| No `<button>` inside lifecycle card | ✅ |
| No promote button | ✅ |
| No backfill button | ✅ |
| No run-replay button | ✅ |
| No scheduler trigger | ✅ (scheduler buttons exist in unrelated Orchestration/CTO sections) |
| All server data HTML-escaped via `_esc()` | ✅ (`strategy_id`, `strategy_name`, `supported_lottery_types`, `lifecycle_status` all escaped) |
| `statusColor` sourced from internal hardcoded map | ✅ (no user-data injection path) |
| Count badges use `textContent` (not innerHTML) | ✅ |
| Error state shows safe hard-coded message | ✅ (`⚠️ 生命週期資料讀取失敗`) |
| Auto-loaded on replay section nav | ✅ (`rpLoadLifecycleRegistry()` called in nav click handler) |

---

## 8. No DB Write Evidence

- `no_db_write = True` field in API response
- Endpoint body contains no `sqlite3.connect()` call
- Endpoint calls only in-memory P3 functions
- `sqlite3.connect` spy test (TestNoDbWrite) PASS
- `lottery_v2.db` not staged, not committed, not in PR diff

---

## 9. No Backfill Evidence

- No backfill function called in endpoint
- No scheduler/cron added
- No DB write path added in frontend
- Frontend card is display-only; no action buttons

---

## 10. Blockers

**None.** No blockers found.

---

## 11. Merge Recommendation

```
Recommendation: READY_WITH_PRE_EXISTING_FULL_SUITE_FAILURES

PR #40 targeted scope is ready.
Full suite failures are pre-existing (identical on main) and must be handled separately.

DO NOT MERGE PR #40 until user explicitly says YES.
```

---

## 12. Final Markers

```
P8_PR40_READINESS_REVIEWED
P8_PR40_DIFF_SCOPE_CONFIRMED
P8_PR40_BACKEND_ENDPOINT_REVIEWED
P8_PR40_FRONTEND_READONLY_CONFIRMED
P8_PR40_NO_DB_WRITE_NO_BACKFILL_CONFIRMED
P8_PR40_TARGETED_TESTS_PASS
P8_FULL_SUITE_PRE_EXISTING_FAILURES_CONFIRMED
P8_PR40_READY_FOR_USER_YES_GATE
```
