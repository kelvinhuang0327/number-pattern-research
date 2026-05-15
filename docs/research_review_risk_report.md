# Research Review System — Risk Report

**Date:** 2026-03-31
**Status:** SKELETON_ONLY

---

## Risk Matrix

| Risk ID | Description | Impact | Likelihood | Rating |
|---------|-------------|--------|------------|--------|
| R1 | Dashboard shows all zeros — users perceive system as non-functional | HIGH | CERTAIN | 🔴 CRITICAL |
| R2 | Action/Hypothesis status updates silently rejected | HIGH | CERTAIN | 🔴 CRITICAL |
| R3 | Two disconnected "reviewed" tracking systems cause confusion | HIGH | CERTAIN | 🔴 CRITICAL |
| R4 | Shadow comparison returns null data — misleading to analysts | MEDIUM | CERTAIN | 🟡 HIGH |
| R5 | No navigation between prediction and review — breaks workflow | MEDIUM | CERTAIN | 🟡 HIGH |
| R6 | UPSERT without UNIQUE constraint — fragile persistence | LOW | LIKELY | 🟢 LOW |

---

## Risk Details

### R1: Dashboard Renders All Zeros
**Root Cause:** Frontend reads `d.summary.*` but backend returns flat keys like `session_status_counts`, `open_actions`, etc.
**Impact:** Dashboard is the entry point for the Review System. Showing all zeros makes the entire system appear broken even when data exists.
**Fix Complexity:** LOW — either rename backend keys to match frontend, or update frontend to read correct keys.
**Recommended Fix:** Align backend response to include a `summary` wrapper object.

### R2: Silent Status Rejection
**Root Cause:** Frontend sends `WONT_DO` / `CONFIRMED` but backend validation only accepts `CANCELLED` / `ACCEPTED`.
**Impact:** Users click status buttons, UI may show optimistic update, but server rejects the change. Data inconsistency between what user sees and what's stored.
**Fix Complexity:** LOW — align enum values between frontend and backend.
**Recommended Fix:** Update frontend to use backend-canonical values (`CANCELLED`, `ACCEPTED`).

### R3: Dual Review Tracking Systems
**Root Cause:** `prediction_runs.analyzed` (TEXT column) was the original review marker in `prediction_tracker.py`. The new `prediction_review_status` table was added by the Review System but never integrated.
**Impact:** Creating a review session does NOT update the PredictionTracker badge. Marking a prediction as "已研究" in PredictionTracker does NOT create a review session. Users see conflicting states.
**Fix Complexity:** MEDIUM — needs a bridge:
1. When `create_review_session()` links prediction IDs, also update `prediction_runs.analyzed = '已研究'`
2. OR have PredictionTracker read from `prediction_review_status` instead

**Recommended Fix:** Option 1 (bridge write) is simpler and backward-compatible.

### R4: Shadow Comparison Stub
**Root Cause:** `get_shadow_vs_production_comparison()` returns placeholder nulls. Shadow experiments don't generate actual predictions.
**Impact:** The A/B testing capability is entirely non-functional. Users can create shadow experiments but can't compare results.
**Fix Complexity:** HIGH — requires integration with the prediction engine to generate shadow predictions and resolve them against outcomes.
**Recommended Fix:** Phase 2 feature. Mark as "Coming Soon" in UI.

### R5: No Cross-Navigation
**Root Cause:** PredictionTracker badge doesn't link to ReviewManager detail view. ReviewManager session list doesn't link back to prediction detail.
**Impact:** Breaks the analyst workflow. Users can't go from "this prediction was reviewed" to "see the review findings."
**Fix Complexity:** LOW — add click handler on badge to switch to ReviewManager section and load detail.
**Recommended Fix:** Add `onclick` handler on review badge in PredictionTracker that calls `ReviewManager.showSessionDetail(sessionId)`.

### R6: UPSERT Without UNIQUE Constraint
**Root Cause:** `mark_prediction_reviewed()` uses `ON CONFLICT(prediction_run_id)` but no UNIQUE index exists on that column.
**Impact:** First insertion always throws exception, falls to fallback path. Functional but fragile.
**Fix Complexity:** LOW — add `CREATE UNIQUE INDEX IF NOT EXISTS idx_prs_run_id ON prediction_review_status(prediction_run_id)`.
**Recommended Fix:** Add UNIQUE index in schema init.

---

## Fix Priority Order

### Phase 1: Reach FUNCTIONAL (4 fixes)
1. **C5** — Dashboard field alignment (backend or frontend rename)
2. **C3** — Action enum: frontend `WONT_DO` → `CANCELLED`
3. **C4** — Hypothesis enum: frontend `CONFIRMED` → `ACCEPTED`
4. **C1** — Bridge `prediction_runs.analyzed` ↔ `prediction_review_status`

### Phase 2: Reach CLOSED_LOOP_READY (4 fixes)
5. **C2** — Cross-navigation between PredictionTracker and ReviewManager
6. **C6** — Add `top_actions` query to dashboard backend
7. **C8** — Add edit endpoints for individual findings/hypotheses/actions
8. **C9** — Add UNIQUE index on `prediction_review_status.prediction_run_id`

### Phase 3: Full Feature (2 fixes)
9. **C7** — Shadow comparison with real prediction engine integration
10. **C10** — Reviewed/unreviewed prediction count aggregation

---

## Final Verdict

### 🔴 SKELETON_ONLY

**Rationale:**
- The CRUD layer exists and mostly works in isolation (create session, list sessions, export)
- But the dashboard (primary UI) renders all zeros
- Two critical status enum mismatches mean action/hypothesis workflows silently fail
- The core linkage between predictions and reviews is broken (dual tracking systems)
- Shadow comparison is stub-only

**What works:**
- ✅ Create review session + auto-parse report text
- ✅ Fallback save on parse failure (raw text preserved)
- ✅ Shadow data isolated from production
- ✅ Session list, detail, export endpoints
- ✅ 18 API endpoints registered and responding

**What's broken:**
- ❌ Dashboard (renders zeros)
- ❌ Action status transitions (`WONT_DO` rejected)
- ❌ Hypothesis status transitions (`CONFIRMED` rejected)
- ❌ Prediction-to-review linkage (two disconnected systems)
- ❌ Shadow comparison (stub returns nulls)

**Path to FUNCTIONAL:** 4 targeted fixes (estimated as LOW-MEDIUM complexity).
**Path to CLOSED_LOOP_READY:** 4 additional fixes after FUNCTIONAL.
