# PredictionTracker Review Badge Fix Report
Generated: 2026-04-06

## Changed Files

| File | Change |
|------|--------|
| `lottery_api/engine/prediction_tracker.py` | `get_history()`: added `LEFT JOIN prediction_review_status`, emit `review_status` + `review_session_id` fields |
| `lottery_api/engine/prediction_tracker.py` | `get_run_detail()`: same JOIN added, same fields emitted |
| `src/ui/PredictionTracker.js` | `_renderHistory()`: badge derived from `r.review_status` (real linkage) first, `r.analyzed` as fallback |
| `src/ui/PredictionTracker.js` | `_renderReviewBlock()`: same priority logic for detail-panel header badge |

---

## Root Cause

`_renderHistory()` used `r.analyzed === '已研究'` as the **sole** condition to show `已檢討 ✅`.

For BIG_LOTTO draw 115000041 the relevant run is **run_id=122** (`latest_known_draw=115000040` → predicted draw 115000041). That run was written with `analyzed='已分析'` (not `'已研究'`), so the badge evaluated to `未檢討`.

The real review linkage — `prediction_review_status` row `(prediction_run_id=122, review_status=REVIEWED, review_session_id=1)` — was never consulted.

---

## Review-Status Derivation Rule

### Priority (both list row and detail panel):

```
1. prediction_review_status.review_status IN ('REVIEWED', 'RESOLVED')
   for this prediction_run.id
   → isReviewed = true

2. Else if prediction_runs.analyzed == '已研究'   (legacy fallback)
   → isReviewed = true

3. Else
   → isReviewed = false
```

`analyzed` is kept as a secondary fallback only — it may NOT override real review linkage.

### Backend emits (in both `get_history()` and `get_run_detail()`):

```python
"review_status":    "REVIEWED" | "RESOLVED" | null
"review_session_id": <int> | null
```

### Frontend evaluates:

```javascript
const isReviewed = r.review_status === 'REVIEWED' || r.review_status === 'RESOLVED'
    || r.analyzed === '已研究';
```

---

## Before / After — BIG_LOTTO 115000041

| Field | Before fix | After fix |
|-------|-----------|-----------|
| `r.review_status` (not in API) | — | `"REVIEWED"` |
| `r.analyzed` | `"已分析"` | `"已分析"` (unchanged) |
| `isReviewed` | `false` | `true` |
| Badge shown | `未檢討 MED` | `已檢討 ✅ [wqBadge]` |
| "查看檢討 →" link | absent | present (`?prediction_run_id=122`) |

---

## Validation

Backend query result:
```
run_id=122  latest_known_draw=115000040  review_status=REVIEWED  session=1
  → predicted draw: 115000041
  → badge: 已檢討 ✅ ← CORRECT
```

No contradiction:
- Review detail page: session id=1, game=BIG_LOTTO, draw=115000041, status=COMPLETED ✅
- PredictionTracker row: run_id=122 (predicts 115000041) → badge 已檢討 ✅ ✅

---

## Audit: Places That Still Read `prediction_runs.analyzed` Directly

| Location | Line | Usage | Status |
|----------|------|-------|--------|
| `lottery_api/engine/prediction_tracker.py` | `get_history()` SQL | `COALESCE(pr.analyzed, '未研究') as analyzed` — still emitted for backward compat | ✅ Safe — display only, not badge primary |
| `lottery_api/engine/prediction_tracker.py` | `get_history()` WHERE | `COALESCE(pr.analyzed,'未研究') = ?` for `analyzed=UNREVIEWED` filter | ✅ Safe — paired with review exclusion guards added in pending-list fix |
| `lottery_api/engine/prediction_tracker.py` | `get_run_detail()` SQL | `COALESCE(pr.analyzed,'未研究') as run_analyzed` — emitted as `analyzed` | ✅ Safe — overridden by `isDetailReviewed` logic in frontend |
| `lottery_api/engine/prediction_tracker.py` | `submit_run_analysis()` | Returns `{"analyzed": "已研究", …}` — sets DB field when LLM analysis posted | ✅ Safe — this is the write path; now supplemented by `prediction_review_status` |
| `lottery_api/routes/prediction_tracking.py` | line 344 | Returns `{"analyzed": new_val}` from submit/clear endpoints | ✅ Safe — route return value, no badge logic |
| `src/ui/PredictionTracker.js` | `_renderHistory()` line 385 | `r.analyzed === '已研究'` — fallback condition | ✅ Safe — only triggers if real linkage absent |
| `src/ui/PredictionTracker.js` | `_renderReviewBlock()` line 537 | `detail.analyzed` — used after `isDetailReviewed` override | ✅ Safe — overridden before use |
| `tmp/query_039.py`, `tmp/check_539.py`, etc. | various | Read-only diagnostic scripts | ✅ Safe — not production code |

### Summary

No remaining place uses `analyzed` as the **primary badge truth**. All badge-critical paths now check `review_status` first.

The `analyzed` field is retained as:
- A legacy write path (LLM analysis POST writes `'已研究'`)
- A backward-compatible display fallback for old runs without `prediction_review_status` rows
- An UNREVIEWED filter input (used alongside review-system exclusions)
