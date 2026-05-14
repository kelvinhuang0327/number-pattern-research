# Post-V3 Cleanup & Tag Gate Report

**Date**: 2026-05-14  
**Audit Agent**: Post-V3 Release Audit Cleanup & API Truth-Level Gate Agent  
**Base Commit**: f780933 (post-V3 audit & rollback rehearsal)  
**Branch**: main

---

## PHASE 0 — Baseline Verification ✅

| Check | Result |
|-------|--------|
| Branch | `main` |
| Audit commit (f780933) | Confirmed — 10 files, audit/post-v3 artifacts |
| Working tree `.pid` modified | `backend.pid`, `frontend.pid` (runtime artifacts, NOT committable) |
| `data/lottery_v2.db` modified | YES — runtime state, NOT committable |
| `scripts/v2_artifact_only_apply_rows.py` modified | Pre-existing modification, NOT from this session |
| Untracked files | 20+ outputs/ and scripts/ files (see PHASE 3) |

### f780933 committed files

```
outputs/replay/post_v3_api_regression_report_20260514.md
outputs/replay/post_v3_release_audit_report_20260514.md
outputs/replay/post_v3_release_tag_readiness_20260514.md
outputs/replay/post_v3_rollback_rehearsal_plan_20260514.md
outputs/replay/post_v3_strategy_state_matrix_20260514.json
outputs/replay/post_v3_strategy_state_matrix_20260514.md
outputs/replay/post_v3_test_sweep_report_20260514.md
outputs/replay/post_v3_ui_regression_checklist_20260514.md
scripts/post_v3_replay_api_regression.py
scripts/post_v3_replay_api_regression.sh
```

---

## PHASE 1 — DB Row Verification ✅

| Label | controlled_apply_id | truth_level | Expected | Actual |
|-------|---------------------|-------------|----------|--------|
| V1 | 20260514033100-13acaf34996e | REGENERATED_RETROSPECTIVE | 300 | **300** ✅ |
| V2 | 20260514134953-cf683424 | ARTIFACT_RECONSTRUCTED_RETROSPECTIVE | 200 | **200** ✅ |
| Legacy | NULL | NULL | 460 | **460** ✅ |
| Total | — | — | 960 | **960** ✅ |

**DB state: VERIFIED CORRECT**. No modifications made.

---

## PHASE 2 — Python Regression Script Fix ✅

### Changes applied to `scripts/post_v3_replay_api_regression.py`

1. **Replaced `import requests`** → `import urllib.request, urllib.parse, urllib.error`
2. **Replaced `requests.get()`** → `urllib.request.urlopen()` with proper query encoding
3. **Replaced `requests.exceptions.RequestException`** → `(urllib.error.URLError, OSError)`
4. **Added `argparse`** — supports `--strict` flag and `--json-out` override
5. **Fixed `_verify_no_fake_data` bug** — `predicted_numbers=None` raises `TypeError` on legacy code; now uses `or []` guard and skips REJECTED/REPLAY_ERROR rows (which legitimately have no predictions)
6. **py_compile**: PASS

### Regression Run Result (backend live at http://127.0.0.1:8002/api)

```
V1 (EXECUTABLE_NOW):  0/6  ❌
V2 (ARTIFACT_ONLY):   4/4  ✅
V3 (CODE_MISSING):    6/6  ✅
Total:               10/16
Exit code: 1 (--strict)
```

### V1 Root Cause Analysis

- **API field presence**: `truth_level` IS included in `/api/replay/history` response (field exists, not missing)
- **Actual gap**: API returns ALL rows for a strategy across all replay_run_ids; legacy rows (truth_level=NULL) dominate page 1 because they were generated first (lower IDs)
- **Example** (`biglotto_deviation_2bet`): 120 total rows (70 legacy + 50 V1); page 1 returns 50 legacy rows only
- **Test logic**: `_verify_truth_level` checks page-1 records → ALL null → FAIL
- **V1 rows ARE correct in DB** (300 rows with REGENERATED_RETROSPECTIVE) — data integrity is sound
- **Fix required**: API needs to filter or prioritize V1 rows (e.g., ORDER BY truth_level IS NULL, or add `truth_level` query param filter) — requires PHASE 4 authorization

---

## PHASE 3 — Completion Summary Decision

**File**: `outputs/replay/post_v3_release_completion_summary_20260514.md`  
**Status**: Uncommitted, untracked

**Decision**: **DO NOT COMMIT**

**Reason**: Document contains stale/inaccurate claims:
- Claims "16/16 API regression tests: PASS" — actual result is 10/16 (V1 0/6 fails)
- Claims "V1: Added truth_level field to replay API" — truth_level field exists but V1 rows fail regression due to pagination/query ordering gap
- Claiming "RELEASE READY" and "APPROVED FOR PRODUCTION RELEASE" is premature given the V1 truth_level gate failure

The document reflects an earlier optimistic assessment that did not fully verify V1 truth_level validation end-to-end. Committing it would create misleading release documentation.

---

## PHASE 4 — API truth_level Patch Gate

**Authorization received**: NO  
**Status**: BLOCKED — awaiting `YES patch API to expose truth_level`

**Required fix scope** (minimal, for reference):
- Add `ORDER BY truth_level IS NULL ASC` to the replay history query, OR
- Add optional `?truth_level=REGENERATED_RETROSPECTIVE` filter param to `/api/replay/history`
- No schema changes; no DB modifications required
- Estimated 1–3 lines of backend query change

---

## PHASE 5 — Working Tree Forbidden Files Audit

| File | Type | Committable |
|------|------|-------------|
| `backend.pid` | Runtime PID | ❌ FORBIDDEN |
| `frontend.pid` | Runtime PID | ❌ FORBIDDEN |
| `data/lottery_v2.db` | Database | ❌ FORBIDDEN |
| `scripts/v2_artifact_only_apply_rows.py` (M) | Pre-existing mod | ⚠️ NOT from this session |
| `outputs/relay/p78_browser_smoke_lifecycle_20260513.png` | Binary artifact | ❌ DO NOT COMMIT |
| `outputs/replay/post_v3_release_completion_summary_20260514.md` | Stale doc | ❌ SEE PHASE 3 |
| `scripts/_p1_dry_call_check.py` | Unknown utility | ⚠️ OUT OF SCOPE |
| `scripts/p6_lite_apply_retrospective_rows.py` | Apply script | ⚠️ OUT OF SCOPE |

### Allowed Commit Files (from this session)

| File | Status |
|------|--------|
| `scripts/post_v3_replay_api_regression.py` | ✅ Fixed (requests→urllib, bug fixes, argparse) |
| `outputs/replay/post_v3_api_regression_result_20260514.json` | ✅ Generated — 10/16 pass |
| `outputs/replay/post_v3_cleanup_and_tag_gate_report_20260514.md` | ✅ This report |

---

## Verification Checklist

- [x] DB rows verified: V1=300, V2=200, Legacy=460, Total=960 ✅
- [x] DB truth_level values correct for all controlled rows ✅
- [x] Regression script: `requests` removed, `urllib` substituted ✅
- [x] Regression script: py_compile PASS ✅
- [x] Regression script: `--strict` flag supported ✅
- [x] Regression script: REJECTED/REPLAY_ERROR row bug fixed ✅
- [x] Regression run: V2 4/4 PASS ✅
- [x] Regression run: V3 6/6 PASS ✅
- [x] Regression run: V1 0/6 FAIL (truth_level gap — pending PHASE 4) ❌
- [x] Completion summary stale — NOT committed ✅
- [x] No forbidden files committed (DB, PID, sqlite) ✅
- [ ] API truth_level patch for V1 — AWAITING AUTHORIZATION

---

## Final Classification

```
POST_V3_CLEANUP_PARTIAL_RUNTIME_BLOCKED
```

**Reason**: V1 truth_level API gate fails (0/6). V2 and V3 pass. DB state verified correct.  
Cleanup is structurally complete (script fixed, result written, forbidden files excluded).  
Unblocking V1 requires: `YES patch API to expose truth_level`

### Release Tag Gate

```
POST_V3_RELEASE_TAG_READY_WAITING_AUTHORIZATION
```

**Conditions to advance to COMPLETE**:
1. Receive `YES patch API to expose truth_level`
2. Apply minimal backend fix (1–3 lines query change)
3. Re-run regression → V1 6/6 PASS
4. Receive `YES create Post-V3 release tag`

---

**Report generated**: 2026-05-14  
**Commit f780933**: Verified ✅  
**DB integrity**: Verified ✅ (960 rows, no mutations)  
**Scope boundary**: Maintained ✅ (no registry mutations, no new rows, no tag created)
