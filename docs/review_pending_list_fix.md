# Review Pending List Fix Report
Generated: 2026-04-05

## Changed Files

| File | Change |
|------|--------|
| `lottery_api/engine/prediction_tracker.py` | Added 2 exclusion conditions to `get_history()` when `analyzed=UNREVIEWED` |
| `src/ui/ReviewManager.js` | Removed duplicate `rv-observer-note` header from `_renderDashboard()` |
| `docs/review_pending_list_fix.md` | This document |

---

## Root Cause

### Inconsistency: BIG_LOTTO 115000041 appeared in both panels simultaneously

**Panel 1 — "最近檢討結果"**: showed `review_sessions id=1` (BIG_LOTTO draw=115000041, status=COMPLETED)

**Panel 2 — "尚未檢討期數"**: showed `prediction_runs id=133` (lottery_type=BIG_LOTTO, `latest_known_draw='115000041'`, analyzed=`未研究`)

The two rows refer to **different prediction cycles**:
- Run 122 (`latest_known_draw=115000040`) → predicted **draw 115000041** → reviewed, session id=1
- Run 133 (`latest_known_draw=115000041`) → predicts **draw 115000042** → unreviewed

But the pending panel displays `latest_known_draw` as the label ("115000041 未檢討"), which made it appear that draw 115000041 was simultaneously COMPLETED and unreviewed.

### Why run 133 appeared in pending

`get_history(analyzed='UNREVIEWED')` only checked:

```sql
COALESCE(pr.analyzed, '未研究') = '未研究'
```

This returned run 133 correctly by that metric (`analyzed='未研究'`), but had **no awareness** of:
- `prediction_review_status` table (run 122's REVIEWED status)
- `review_sessions` table (draw 115000041 already has a COMPLETED session)

---

## Single Source of Truth

A draw is considered **reviewed** (must be excluded from the pending list) when ANY of:
1. The `prediction_run.id` appears in `prediction_review_status` with `review_status IN ('REVIEWED', 'RESOLVED')`
2. A `review_sessions` row exists for the same `game` and `draw = prediction_run.latest_known_draw`

A draw is **unreviewed** (eligible for the pending list) only when BOTH conditions are false.

---

## Fix #1 — `prediction_tracker.py`: Dual exclusion in `get_history()`

Added immediately after the `analyzed='未研究'` condition:

```python
if analyzed_value == "未研究":
    base_conditions.append(
        "pr.id NOT IN ("
        "  SELECT prediction_run_id FROM prediction_review_status"
        "  WHERE review_status IN ('REVIEWED', 'RESOLVED')"
        ")"
    )
    base_conditions.append(
        "NOT EXISTS ("
        "  SELECT 1 FROM review_sessions rs"
        "  WHERE rs.game = pr.lottery_type"
        "    AND rs.draw = pr.latest_known_draw"
        ")"
    )
```

These conditions only activate when the caller passes `analyzed=UNREVIEWED`. Non-UNREVIEWED calls are unaffected.

---

## Fix #2 — `ReviewManager.js`: Remove duplicate observer-mode header

`index.html` (line 1753) already contains the static header:
```html
<p>本頁為檢討觀測台，顯示 AI Agent 自動產生之檢討結果與狀態。</p>
```

`_renderDashboard()` was also rendering:
```html
<div class="rv-observer-note">
    <strong>本頁為檢討觀測台</strong>
    <span>顯示 AI Agent 自動產生之檢討結果與狀態</span>
</div>
```

**Fix**: removed the dynamic `.rv-observer-note` block from `_renderDashboard()`. The static `index.html` header remains as the single source.

---

## Proof: BIG_LOTTO 115000041 Not in Pending

Before fix — UNREVIEWED query returned:
```
run_id=133  latest_known_draw=115000041  analyzed=未研究  ← appeared in pending
```

After fix — same query returns no row for `latest_known_draw=115000041`:
```
(run_id=133 excluded by: NOT EXISTS review_sessions WHERE game='BIG_LOTTO' AND draw='115000041')
```

`review_sessions id=1` (game=BIG_LOTTO, draw=115000041, status=COMPLETED) acts as the exclusion trigger.

---

## Final Behavior

| UI Panel | Before Fix | After Fix |
|----------|-----------|-----------|
| 最近檢討結果 | BIG_LOTTO 115000041 COMPLETED | BIG_LOTTO 115000041 COMPLETED |
| 尚未檢討期數 | BIG_LOTTO **115000041** 未檢討 (run 133) | run 133 **excluded** — no duplicate |
| Observer header | Appears **twice** (static + dynamic) | Appears **once** (static only) |
