# P33 Display-Only Catalog Stabilization Plan
**Date:** 2026-05-13  
**Session:** P33 — Post-P32 Closure & Stabilization  
**Status:** ✅ STABLE — DISPLAY-ONLY CATALOG LIVE ON MAIN

---

## 1. Current Main State

| Item | Value |
|------|-------|
| Branch | `main` |
| HEAD SHA | `2e4c1e7` |
| HEAD commit | `feat(replay/p25): display-only catalog for non-ONLINE strategies [UI-only, no DB write] (#66)` |
| Workspace | CLEAN |
| `data/lottery_v2.db` | CLEAN (restored after P33 smoke run) |

**Merge history:**
```
2e4c1e7  feat(replay/p25): display-only catalog (#66)  ← PRODUCT
01bbc2a  docs(replay/p30): waiting YES recheck (#69)
869358b  docs(replay/p29): waiting YES recheck (#68)
066d287  docs(replay/p27): pre-merge gate snapshot (#67)
8ad8a4b  docs(replay): strategy inventory + display-only catalog (#65)
1bf0204  docs(replay): validate fixture mode ui toggle (#64)
```

---

## 2. PR #70 Status & Recommendation

| Field | Value |
|-------|-------|
| PR | #70 `docs(replay/p32): final post-merge acceptance` |
| State | OPEN |
| `mergeStateStatus` | CLEAN |
| CI | All checks successful (2 pass, 1 skip) |

**Recommendation:** Docs-only PR, CLEAN, safe to merge. Awaiting explicit CTO YES.

---

## 3. P33 Smoke Test Results

Run on `main` `2e4c1e7`:

| Test File | Result |
|-----------|--------|
| `test_p25_display_only_catalog.py` | ✅ PASS |
| `test_replay_browser_smoke.py` | ✅ PASS (1 playwright skip — expected) |
| `test_replay_api_contract.py` | ✅ PASS |
| **Total** | **128 passed, 1 skipped** |

---

## 4. DB Hygiene

| Event | Status |
|-------|--------|
| Pre-test | CLEAN |
| Post-test (tests dirtied) | DIRTY → `git checkout -- data/lottery_v2.db` |
| Final | ✅ CLEAN |

---

## 5. Display-Only Catalog Product Behavior (Verified in index.html)

### Routing (line 3140)
```javascript
if (lc && lc !== 'ONLINE') {
  await rpRenderCatalogDisplayMode(lc, lt);
}
```

### Lifecycle Mode UI Behavior

| Lifecycle | UI Behavior | Verified |
|-----------|------------|---------|
| ONLINE | Standard replay (unchanged) | ✅ |
| REJECTED | 🔴 badge + catalog rows + "無歷史回放資料" | ✅ |
| RETIRED | ⚪ badge + catalog rows + disclaimer | ✅ |
| OBSERVATION | 🟡 badge + catalog rows + disclaimer | ✅ |
| OFFLINE | ⚫ "coming soon" message | ✅ |

### Safety Scan (Stage D)

| Check | Result |
|-------|--------|
| DB write in `index.html` | ✅ 0 hits |
| Backfill execution | ✅ 0 hits |
| Win guarantee claim | ✅ 0 hits (all are disclaimers) |
| XSS (`rpEscapeHtml`) | ✅ Active |

---

## 6. Next Three Product Direction Options

### Option A — Operator SOP + Screenshot Walkthrough ⭐ RECOMMENDED FIRST
**Scope:** Docs only. Zero code change.  
**Deliverable:** `docs/operator_sop_display_only_catalog_20260513.md`  
Walk each lifecycle mode, define what operators see, document fixture mode usage.  
**Why first:** No risk. Validates shipped feature against operator expectations.

### Option B — No-Write Replay Backfill Dry-Run Manifest v2
**Scope:** Manifest file only. No real backfill.  
**Deliverable:** `outputs/replay/p33_no_write_backfill_dry_run_manifest_20260513.md`  
Define what a production backfill *would* cover — draw range, strategy candidates, data quality gates — without executing.  
**Why second:** Planning artifact, sets stage for future decision without committing.

### Option C — Production Replay Backfill Decision Memo v2
**Scope:** Decision memo only. Still no backfill.  
**Deliverable:** `outputs/replay/p33_production_backfill_decision_memo_v2_20260513.md`  
CTO/CEO-level memo: should any lifecycle get production backfill? Recommendation: defer all.  
**Why last:** Policy decision, should follow A + B.

---

## 7. Recommended Priority

```
PRIORITY 1 → Option A: Operator SOP (zero code risk, enables ops validation)
PRIORITY 2 → Option B: Dry-Run Manifest (planning only, no execution)
PRIORITY 3 → Option C: Backfill Decision Memo v2 (informed by A+B)
```

---

## 8. Explicitly Deferred

| Item | Status |
|------|--------|
| Real production backfill | ⛔ DEFERRED |
| OFFLINE strategy introduction | ⛔ DEFERRED |
| New strategy mining / edge discovery | ⛔ DEFERRED |
| Promoting any lifecycle to ONLINE | ⛔ DEFERRED |
| Lifecycle taxonomy changes | ⛔ DEFERRED |

---

## Markers

```
P33_MAIN_POST_MERGE_STATE_VERIFIED
P33_PR70_FINAL_DOCS_GATE_CHECKED
P33_POST_MERGE_SMOKE_PASS
P33_DISPLAY_ONLY_CATALOG_STABLE_ON_MAIN
P33_POST_RUN_DB_CLEAN
P33_STABILIZATION_PLAN_CREATED
```
