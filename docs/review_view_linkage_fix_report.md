# Review 「查看」Linkage Fix Report
Generated: 2026-04-05

## Changed Files

| File | Change |
|------|--------|
| `src/ui/ReviewManager.js` | 3 fixes: event delegation, scroll, disabled state |
| `docs/review_view_linkage_trace.md` | New trace document |
| `docs/review_view_linkage_fix_report.md` | This document |

---

## Identifier Used for Navigation

**`review_session_id`** (integer, stored as `data-sid` on each `<button>`)

Flow:
```
API /api/reviews/history → session.id
→ _renderSessionRow(s): <button data-sid="${s.id}">查看</button>
→ click event: btn.dataset.sid → loadSession(Number(sid))
→ GET /api/reviews/{sid}
→ _renderDetail(data) + _showDetail()
```

No `prediction_run_id` fallback needed in the list view (it's already handled in `openPredictionRun()` for deep-link entry).

---

## Bug #1 — Dashboard "查看詳情" buttons: NO HANDLER

**Root cause**: `_renderRecentSessionCard()` renders `.rv-view-btn` buttons inside `#rv-dashboard`. `_bindEvents()` only listened on `#rv-session-tbody` and `#rv-actions-panel` — NOT on `#rv-dashboard`.

**Fix** — added to `_bindEvents()`:
```javascript
document.getElementById('rv-dashboard')?.addEventListener('click', e => {
    const btn = e.target.closest('.rv-view-btn');
    if (btn) this.loadSession(Number(btn.dataset.sid));
});
```

---

## Bug #2 — Export buttons in detail view: NO HANDLER

**Root cause**: `_renderDetail()` dynamically renders `.rv-export-json` and `.rv-export-md` buttons inside `#rv-detail`, which is wiped and recreated on each `loadSession()` call. No event was ever bound to them.

**Fix** — added to `_bindEvents()` (delegated to the stable `#rv-detail-view` container):
```javascript
document.getElementById('rv-detail-view')?.addEventListener('click', e => {
    if (e.target.closest('.rv-export-json')) {
        if (this._currentSession?.id) this._exportJson(this._currentSession.id);
    } else if (e.target.closest('.rv-export-md')) {
        if (this._currentSession?.id) this._exportMd(this._currentSession.id);
    }
});
```

---

## Bug #3 — Detail view not scrolled into view

**Root cause**: After `_showDetail()` hides the list and shows the detail div, the user's viewport stays at the top where the (now hidden) list was, so the detail appears below the fold with no visible transition.

**Fix**:
```javascript
_showDetail() {
    document.getElementById('rv-list-view')?.classList.add('rv-hidden');
    const dv = document.getElementById('rv-detail-view');
    if (dv) {
        dv.classList.remove('rv-hidden');
        dv.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
}
```

---

## Bug #4 — No disabled state when session ID is missing

**Root cause**: If `s.id` were somehow falsy, the button would render as `<button data-sid="0">查看</button>` and `loadSession(0)` would silently fail with a 404.

**Fix** — defensive rendering in `_renderSessionRow()`:
```javascript
const viewBtn = s.id
    ? `<button class="btn-sm btn-primary rv-view-btn" data-sid="${s.id}" style="cursor:pointer">查看</button>`
    : `<span class="rv-no-record" title="無對應紀錄" style="color:#484f58;font-size:12px">無對應紀錄</span>`;
```

Same pattern applied in `_renderRecentSessionCard()`.

---

## End-to-End Verification: Real Row Click Flow

**Row**: BIG_LOTTO | 115000041 | 2026/04/03 | MAINTAIN | HIGH | COMPLETED | [查看]

1. User clicks `<button class="rv-view-btn" data-sid="1">查看</button>`
2. Click bubbles to `#rv-session-tbody` listener
3. `e.target.closest('.rv-view-btn')` → finds button, `btn.dataset.sid = "1"`
4. `this.loadSession(1)` called
5. `GET /api/reviews/1` → HTTP 200, returns session with 6 findings + 3 actions
6. `detail.innerHTML = this._renderDetail(data)` → renders full detail HTML
7. `this._showDetail()`:
   - `#rv-list-view` gets `rv-hidden` class → hides
   - `#rv-detail-view` loses `rv-hidden` class → shows
   - `scrollIntoView()` → user viewport scrolls to detail
8. User sees: 大樂透 第115000041期, status COMPLETED, 6 findings, 3 actions (P0/P1/P2)

---

## Final Behavior Description

| Location | Button | Before Fix | After Fix |
|----------|--------|------------|-----------|
| Session list table | 查看 | Works (was correct) | Works + `cursor:pointer` |
| Dashboard recent cards | 查看詳情 | **No effect** | Opens correct session |
| Actions tab | 查看 | Works (was correct) | Works |
| Detail view | 匯出 JSON/MD | **No effect** | Calls `_exportJson/Md` |
| Missing session ID | — | Fake clickable text | Shows "無對應紀錄" |

---

## Deep Link Support (Already Implemented)

`?prediction_run_id=122` → `ReviewManager.init()` → `openPredictionRun(122)` → resolves `review_session_id=1` → `loadSession(1)` → opens correct detail.

This was already working. No changes needed.

`?review_session_id=N` direct deep link is NOT supported (would require App.js change). The existing `?prediction_run_id=N` covers the use case.
