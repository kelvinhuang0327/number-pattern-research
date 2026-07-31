# P254B — Fetcher Repair Governance Closure

**Date:** 2026-06-08  
**Task type:** Type B governance closure  
**Classification:** `FETCHER_REPAIR_GOVERNANCE_CLOSURE_COMPLETE`

---

## Executive Summary

The fetcher/backfill incident chain opened on 2026-06-08 is now fully closed:

- **PR #360** (ACCEPT_BACKFILL_DB_DRIFT_2026_0608) — merged. DB drift accepted as new baseline (raw=22,239, canonical=2,114). P247G guard constants updated.
- **PR #361** (P254A repair fetcher backfill modules) — merged. All five `lottery_api/fetcher/*` modules restored. ADD_ON draw-ID crash fixed.
- **P254B** — this governance closure. Documents the incident chain, lessons, and accepted baseline. Returns system to `WAITING_FOR_USER_AUTHORIZATION`.

No DB write, registry mutation, strategy promotion, or betting advice in P254B.

---

## Incident Chain Summary

```
1. commit 7306264 accidentally deleted lottery_api/fetcher/*
2. ModuleNotFoundError in routes/ingest.py propagated before CORS headers
   → /api/ingest/log + /api/ingest/backfill returned 500 with no CORS headers
   → browser: "Origin http://localhost:8081 is not allowed"
3. Fetcher repair session 2026-06-08: files restored from commit 997e07a
4. Backend restarted → frontend auto-backfill (non-dry-run) triggered
5. 5 draws inserted into lottery_v2.db
6. Regression gate: P247G FAIL (22239 ≠ 22238, 2114 ≠ 2113)
7. Worker STOPPED → user chose DATA_ACCEPTANCE path
8. PR #360 accepted drift (no rollback — all backups predate P247G canonical table)
9. PR #361 restored fetcher modules + ADD_ON safety fix
10. P254B closes incident chain
```

---

## PR #360 — Baseline Acceptance

| Item | Value |
|------|-------|
| PR | #360 |
| State | MERGED |
| Merge commit | `234cc02` |
| What changed | P247G guard constants updated: EXPECTED_CANONICAL 2113→2114, EXPECTED_RAW 22238→22239 |
| DB write in PR #360 | No |
| Rollback chosen | No |
| Why no rollback | All named backups predate P247G canonical table (`draws_big_lotto_canonical_main`). Any restore would destroy the canonical table — a worse regression than accepting the +1 draw. |

**Accepted draws (inserted by frontend auto-backfill during repair session):**

| Lottery | Draw | Date |
|---------|------|------|
| BIG_LOTTO | 115000059 | 2026/06/05 |
| POWER_LOTTO | 115000045 | 2026/06/04 |
| DAILY_539 | 115000136 | 2026/06/04 |
| DAILY_539 | 115000137 | 2026/06/05 |
| DAILY_539 | 115000138 | 2026/06/06 |

---

## PR #361 — Fetcher Repair

| Item | Value |
|------|-------|
| PR | #361 |
| State | MERGED |
| Merge commit | `36f6862` (= current HEAD = origin/main) |
| Files restored | `lottery_api/fetcher/__init__.py`, `backfill_engine.py`, `ingest_logger.py`, `missing_issue_detector.py`, `taiwan_lottery_fetcher.py` |
| Code fix | `_detect_internal_gaps()` now skips ADD_ON draw IDs via `isdigit()` guard |
| DB write | No |

---

## Current Accepted DB Baseline

> **⚠ Stale values 22,238 / 2,113 are invalidated as of 2026-06-08. Do not reuse.**

| Metric | Value |
|--------|-------|
| BIG_LOTTO raw rows | **22,239** |
| BIG_LOTTO canonical (`draws_big_lotto_canonical_main`) | **2,114** |
| BIG_LOTTO ADD_ON rows | 19,100 |
| POWER_LOTTO raw rows | 1,917 |
| DAILY_539 raw rows | 5,882 |
| `strategy_prediction_replays` | 94,924 |
| DB integrity | ok |

---

## Endpoint Verification Summary (via .venv TestClient)

| Test | Result |
|------|--------|
| `GET /api/ingest/log?limit=5` → 200 + `entries` key | ✅ PASS |
| `GET /api/ingest/log` CORS header (`*`) | ✅ PASS |
| `POST /api/ingest/backfill` `dry_run=true` → 200 + `success=true` | ✅ PASS |
| `POST /api/ingest/backfill` CORS header | ✅ PASS |
| `OPTIONS /api/ingest/backfill` preflight → `Allow-Origin: http://localhost:8081` | ✅ PASS |
| `_detect_internal_gaps(['103000008','103000009-01','103000010'])` → no crash | ✅ PASS |

---

## Skipped-Test Explanation

P254A test run: **249 passed / 7 skipped / 0 failed**

The 7 skipped tests are in `TestIngestEndpoints` (FastAPI TestClient endpoint tests). The `/opt/homebrew/bin/pytest` environment uses Python 3.13, which does not have `numpy` installed (PEP 668 blocks system-level `pip install`). The fixture calls `pytest.skip()` gracefully — these are **not failures**.

Compensating verification: `.venv` (Python 3.9 + fastapi + numpy) TestClient was invoked directly and confirmed all three endpoint behaviors PASS.

---

## Governance Lesson Learned

### L_P254_01 — Separate DB baseline acceptance from fetcher code repair

When a fetcher endpoint is repaired, the **first non-dry-run UI call** can insert legitimately missing draws before the regression gate has completed — silently shifting DB counts. The code repair PR and the DB drift acceptance **must be separate commits and PRs** with clean audit trails.

**Future rule:** Always verify with `dry_run=true` during regression checks. Block non-dry-run calls until the regression gate is complete. If baseline counts change unexpectedly during a regression session, `STOP` immediately and classify as `OUT_OF_SCOPE_DB_WRITE`.

### L_P254_02 — Stale baseline values 22,238 / 2,113 are invalidated

As of 2026-06-08, any agent, test, or artifact referencing BIG_LOTTO raw=22,238 or canonical=2,113 is using stale values. The P247G guard was updated in PR #360.

### L_P254_03 — ADD_ON draw IDs must not be passed to `int()` conversion

Draw IDs like `103000009-01` (ADD_ON_PRIZE_EXCLUDED records) will crash with `ValueError` if passed to `int(draw)` or `int(draw[-6:])`. Always guard with `draw.isdigit()` before numeric conversion.

---

## Explicit Non-Actions

The following were explicitly **NOT** done in P254B:

- No DB write
- No row insert / update / delete
- No DB migration
- No CREATE TABLE / CREATE VIEW
- No registry mutation
- No strategy promotion
- No betting advice
- No prediction improvement claimed
- No lottery research reopened
- No non-dry-run backfill triggered
- No fetcher code changed
- No P247G constants changed
- No frontend/UI changed
- No API route behavior changed

---

## Recommended Next Action

**HOLD — `WAITING_FOR_USER_AUTHORIZATION`**

The fetcher/backfill incident chain is fully closed. No active research candidate or system component requires follow-up. The system is stable.

If the user requests ingest UI/monitoring improvements (e.g., preventing future auto-backfill on endpoint repair, dry-run-only mode enforcement, or a regression gate that blocks non-dry-run calls), a new explicit authorization task should be opened.

---

## Required Completion Check

| Item | Status |
|------|--------|
| Completed | YES |
| Test Result | PASS (249/249 + 7 skipped explained) |
| Single Blocking Issue | NONE |
| Modified Files | outputs/research/p254b_*.json, outputs/research/p254b_*.md, tests/test_p254b_*.py, analysis/p254b_*.py, 00-Plan/roadmap/active_task.md, CURRENT_STATE.md, roadmap.md, memory/lessons.md, memory/todo.md |
| Staged | YES |
| Commit | YES |
| Push | YES |
| PR | YES |
| Merge | PENDING CI |
| Next Round Allowed | YES — if user explicitly authorizes |
| Final Classification | `FETCHER_REPAIR_GOVERNANCE_CLOSURE_COMPLETE` |
| Strong Model Needed | NO |
