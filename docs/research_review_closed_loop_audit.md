# Research Review System — Closed-Loop Audit

**Date:** 2026-03-31
**Auditor:** Automated verification
**Scope:** Full closed-loop verification of Review System CRUD/UI skeleton

---

## 1. Review-to-Prediction Linkage

### 1.1 DB Relation: `prediction_review_status`
- **EXISTS**: Table with `prediction_run_id`, `review_session_id`, `review_status`
- **FK**: References both `prediction_runs(id)` and `review_sessions(id)`
- **Write path**: `create_review_session()` writes rows when `prediction_run_ids` is provided

### 1.2 Linkage Gaps

| Check | Result | Severity |
|-------|--------|----------|
| Prediction → Review Session navigation | **MISSING** | HIGH |
| PredictionTracker badge source | Uses `prediction_runs.analyzed` column, NOT `prediction_review_status` table | HIGH |
| Review session links to prediction_runs | Via `prediction_review_status` | OK |
| PredictionTracker detail → review section link | **MISSING** — no clickable link to ReviewManager | MEDIUM |
| `prediction_tracker.py` references `prediction_review_status` | **ZERO references** — completely disconnected | HIGH |

### 1.3 Root Cause
Two parallel systems exist:
1. **Legacy system**: `prediction_runs.analyzed` text column (`'已研究'`/`'未研究'`) + `review_json` column — used by PredictionTracker
2. **New system**: `prediction_review_status` table — used by ReviewManager

These are **NOT connected**. A prediction marked `'已研究'` via the old system has no corresponding `prediction_review_status` row. A review session created via the new system does not update `prediction_runs.analyzed`.

### 1.4 Verdict: ❌ BROKEN LINKAGE

---

## 2. Shadow Isolation

### 2.1 Data Isolation

| Check | Result |
|-------|--------|
| Shadow data lives in separate table (`shadow_experiments`) | ✅ YES |
| `prediction_tracker.py` references shadow tables | ✅ ZERO references |
| Performance metrics queries include shadow data | ✅ NO — production queries only touch `prediction_runs`/`prediction_items` |
| Shadow API endpoints are separate from production | ✅ All under `/api/reviews/shadow-experiments/*` |
| Shadow creation never writes to `prediction_runs` | ✅ Confirmed |

### 2.2 Comparison Function

| Check | Result | Severity |
|-------|--------|----------|
| `get_shadow_vs_production_comparison()` returns real data | **NO** — returns placeholder with `null` values | MEDIUM |
| Shadow experiments generate actual predictions | **NO** — schema stores config only, no prediction engine integration | MEDIUM |

### 2.3 Verdict: ✅ ISOLATED (but comparison is stub-only)

---

## 3. Action Lifecycle

### 3.1 State Machine

Backend allowed states: `OPEN`, `IN_PROGRESS`, `DONE`, `CANCELLED`
Frontend offered states: `OPEN`, `IN_PROGRESS`, `DONE`, `WONT_DO`

| Check | Result | Severity |
|-------|--------|----------|
| P0/P1/P2 priority supported | ✅ YES |
| Lifecycle state transitions | Backend validates against allowed set | OK |
| **`WONT_DO` vs `CANCELLED` mismatch** | Frontend sends `WONT_DO`, backend rejects (not in allowed list) | **HIGH — BROKEN** |
| Actions visible in dashboard | `open_actions` count returned | OK |
| Actions linked to validation outcomes | **NO explicit mechanism** — action has `validation_method` text but no outcome field | LOW |
| Top priority actions in dashboard | Backend never returns `top_actions` list | MEDIUM |

### 3.2 Hypothesis State Mismatch

Backend allowed states: `PENDING`, `TESTING`, `ACCEPTED`, `REJECTED`, `EXPIRED`
Frontend offered states: `CONFIRMED`, `REJECTED`, `PENDING`

| Check | Result | Severity |
|-------|--------|----------|
| **`CONFIRMED` vs `ACCEPTED`** | Frontend sends `CONFIRMED`, backend rejects (not in allowed list) | **HIGH — BROKEN** |

### 3.3 Verdict: ❌ TWO CRITICAL STATE MISMATCHES

---

## 4. Parser / Persistence Robustness

### 4.1 Raw Text Preservation

| Check | Result |
|-------|--------|
| `raw_report_text` column exists | ✅ YES |
| `create_review_session()` stores raw text | ✅ YES |
| Fallback on parse failure saves raw text | ✅ YES — explicit fallback with `parsed_successfully=0` |
| `raw_report_text` included in export | ✅ YES — both JSON and Markdown exports |

### 4.2 Partial Parse Handling

| Check | Result |
|-------|--------|
| Exception in findings/hypotheses/actions insertion triggers fallback | ✅ YES |
| Fallback returns `status: "partial_failure"` with `raw_text_saved: True` | ✅ YES |
| Manual correction via `PUT /api/reviews/{id}` | ✅ `update_review_session()` supports editing `summary`, `final_decision`, `confidence_level`, `raw_report_text` |

### 4.3 Missing Manual Correction Features

| Check | Result | Severity |
|-------|--------|----------|
| Add/edit individual findings after creation | **NOT SUPPORTED** | MEDIUM |
| Add/edit individual hypotheses after creation | **NOT SUPPORTED** | MEDIUM |
| Add/edit individual actions after creation | Only status update supported, not content edit | MEDIUM |
| Frontend manual correction UI | **NOT IMPLEMENTED** — no edit forms | MEDIUM |

### 4.4 `mark_prediction_reviewed()` UPSERT Bug

The function uses `ON CONFLICT(prediction_run_id)` but `prediction_review_status` has **no UNIQUE constraint** on `prediction_run_id`. The UPSERT always fails, falling to the catch block's manual check.

| Check | Result | Severity |
|-------|--------|----------|
| UPSERT on non-unique column | Falls to manual fallback | LOW (works but fragile) |

### 4.5 Verdict: ⚠️ ADEQUATE for raw preservation, INCOMPLETE for correction flow

---

## 5. Dashboard Usefulness

### 5.1 Backend Returns

```python
{
    "session_status_counts": {"OPEN": 3, "RESOLVED": 2},  # dict
    "decision_counts": {"NO_ACTION": 2, "WATCH": 3},      # dict
    "action_summary": {"P0_OPEN": 1, "P1_DONE": 2},       # dict
    "open_actions": 5,            # int
    "active_hypotheses": 3,       # int
    "active_shadow_experiments": 1 # int
}
```

### 5.2 Frontend Expects

```javascript
d.summary.total_sessions      // ← undefined (backend has no "summary" wrapper)
d.summary.open_sessions        // ← undefined
d.summary.resolved_sessions    // ← undefined
d.summary.total_actions        // ← undefined
d.summary.open_actions         // ← undefined
d.summary.total_hypotheses     // ← undefined
d.top_actions                  // ← undefined (backend never returns this)
```

### 5.3 Result: Dashboard renders ALL ZEROS

| Dashboard Card | Expected Source | Actual | Status |
|----------------|-----------------|--------|--------|
| 總會議 | `summary.total_sessions` | undefined → 0 | ❌ BROKEN |
| 進行中 | `summary.open_sessions` | undefined → 0 | ❌ BROKEN |
| 已解決 | `summary.resolved_sessions` | undefined → 0 | ❌ BROKEN |
| 行動項目 | `summary.total_actions` | undefined → 0 | ❌ BROKEN |
| 待處理行動 | `summary.open_actions` | undefined → 0 | ❌ BROKEN |
| 假說數 | `summary.total_hypotheses` | undefined → 0 | ❌ BROKEN |
| 優先行動 | `top_actions` | undefined → empty | ❌ BROKEN |

### 5.4 Missing Dashboard Items

| Requirement | Status |
|-------------|--------|
| Reviewed vs unreviewed prediction counts | **NOT in dashboard** — would need cross-table query |
| Shadow experiment counts by status | Backend returns `active_shadow_experiments` only (DRAFT+RUNNING), not full status breakdown |
| Hypothesis counts by type/status | Not broken down by type, only active count |

### 5.5 Verdict: ❌ DASHBOARD COMPLETELY NON-FUNCTIONAL

---

## Summary of Issues

| ID | Issue | Severity | Category |
|----|-------|----------|----------|
| C1 | `prediction_runs.analyzed` disconnected from `prediction_review_status` | HIGH | Linkage |
| C2 | No navigation from PredictionTracker to ReviewManager detail | MEDIUM | Linkage |
| C3 | Action status `WONT_DO` (frontend) vs `CANCELLED` (backend) | HIGH | Lifecycle |
| C4 | Hypothesis status `CONFIRMED` (frontend) vs `ACCEPTED` (backend) | HIGH | Lifecycle |
| C5 | Dashboard field name mismatch — all cards show zero | HIGH | Dashboard |
| C6 | `top_actions` never returned by backend | MEDIUM | Dashboard |
| C7 | Shadow comparison returns stubs | MEDIUM | Shadow |
| C8 | No edit UI for individual findings/hypotheses/actions | MEDIUM | Persistence |
| C9 | `mark_prediction_reviewed()` UPSERT on non-unique column | LOW | Persistence |
| C10 | No reviewed/unreviewed prediction count in dashboard | LOW | Dashboard |

### Issue Classification

- **Blocking (must fix before FUNCTIONAL):** C1, C3, C4, C5
- **Important (should fix before CLOSED_LOOP_READY):** C2, C6, C7, C8
- **Minor (nice-to-have):** C9, C10
