# Review 「查看」Linkage Trace Report
Generated: 2026-04-05

## Phase 1 — Data Flow Trace

### Row Data Fields (from `/api/reviews/history`)
Each session row contains:
| Field | Type | Used for |
|-------|------|----------|
| `id` | int | `data-sid` on button — passed to `loadSession()` |
| `game` | string | Display column |
| `draw` | string | Display column |
| `draw_date` | string | Display column |
| `final_decision` | string | Display column (mapped via `_decisionLabel`) |
| `confidence_level` | string | Display column |
| `status` | string | Display column |

The button rendered in `_renderSessionRow(s)`:
```html
<button class="btn-sm btn-primary rv-view-btn" data-sid="${s.id}">查看</button>
```

`review_session_id` = `s.id` — is correctly embedded in `data-sid`.

---

## Phase 2 — Event Binding Inventory

### Elements with `.rv-view-btn` click handlers (as of pre-fix):

| Container | Handler? | Buttons Inside |
|-----------|----------|----------------|
| `#rv-session-tbody` | ✅ YES — `_bindEvents()` line 62 | Session list "查看" buttons |
| `#rv-actions-panel` | ✅ YES — `_bindEvents()` line 67 | Action tab "查看" buttons |
| `#rv-dashboard` | ❌ **NO** | Dashboard "查看詳情" cards ← **BUG #1** |
| `#rv-detail` (dynamic) | ❌ **NO** | Export buttons ← **BUG #2** |

---

## Phase 3 — Root Cause Analysis

### Bug #1: Dashboard "查看詳情" buttons — NO HANDLER
- `_renderRecentSessionCard(s)` renders `<button class="rv-view-btn" data-sid="${s.id}">查看詳情</button>` inside `#rv-dashboard`
- `_bindEvents()` does NOT attach any listener to `#rv-dashboard`
- **Result**: Clicking "查看詳情" in the dashboard panel → **NO EFFECT**
- This is the most visible failure because the dashboard is shown immediately when arriving on the page

### Bug #2: Session list "查看" — has handler but table listener is correct
- `_bindEvents()` attaches a click listener on `#rv-session-tbody`
- Dynamically rendered `.rv-view-btn` buttons inside the tbody ARE covered by event delegation
- **BUT**: If the user first interacts with dashboard cards (no effect), they may conclude "查看" is broken

### Bug #3: Export buttons in detail view — NO HANDLER
- `_renderDetail()` renders `rv-export-json` and `rv-export-md` buttons dynamically inside `#rv-detail`
- No event listener is ever attached to these buttons
- `_exportJson(id)` and `_exportMd(id)` methods exist but are never called

---

## Phase 4 — Navigation Pattern

The app uses **internal state switch** (not URL routing):
- Identifier: `review_session_id` (the `s.id` from the session list)
- Path: `data-sid="${s.id}"` → click → `loadSession(id)` → `GET /api/reviews/{id}` → `_showDetail()`
- Deep link via `?prediction_run_id=N` is already implemented via `openPredictionRun()`

No missing identifier — the `review_session_id` flows correctly through all stages.

---

## Phase 5 — Fix Plan

1. Add `#rv-dashboard` `.rv-view-btn` click delegation in `_bindEvents()`
2. Add `#rv-detail-view` delegation for export buttons (`rv-export-json`, `rv-export-md`)
3. Scroll detail into view after `_showDetail()` so user sees the transition
4. Disable-style for any button where `data-sid` is missing (defensive)
