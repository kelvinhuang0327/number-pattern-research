# P258O0 — Pre-existing Dirty File Isolation Before D3 Strategy Status Audit UI

**Task ID:** P258O0  
**Date:** 2026-06-09  
**Status:** `P258O0_DIRTY_FILE_ISOLATION_BEFORE_D3_UI_READY`

---

## Blocker Resolved

P258O was blocked because `index.html` was dirty and required for the D3 Strategy Status Audit UI. This cleanup task isolates the pre-existing unrelated dirty changes into their own commit so P258O can safely begin with a clean baseline.

---

## Dirty Files Isolated

### `index.html` (+6 / -6)

Adds `ui-hidden` CSS class to 6 nav buttons that were already hidden by configuration:

| Section | Before | After |
|---|---|---|
| `simulation` | `class="nav-btn"` | `class="nav-btn ui-hidden"` |
| `next-draw` | `class="nav-btn"` | `class="nav-btn ui-hidden"` |
| `tracking` | `class="nav-btn"` | `class="nav-btn ui-hidden"` |
| `reviews` | `class="nav-btn"` | `class="nav-btn ui-hidden"` |
| `orchestration` | `class="nav-btn"` | `class="nav-btn ui-hidden"` |
| `cto-review` | `class="nav-btn"` | `class="nav-btn ui-hidden"` |

**Relation to P258O:** UNRELATED — nav visibility cleanup only.

### `src/ui/AutoFetchManager.js` (+17 / -6)

Extends ingest backfill fetch payload to include `apply_confirmed`, `confirm_token`, `requested_by`, `reason` fields when the user has confirmed a non-dry-run write. Also improves error message extraction from JSON detail objects.

**Relation to P258O:** UNRELATED — ingest write guard UI (P255 arc follow-up).

---

## Files Intentionally Left Unstaged

| File | Reason |
|---|---|
| `lottery_api/data/performance_history.json` | Runtime data output — 1 line delta |
| `backend.pid` / `frontend.pid` | Process ID files — runtime |
| `data/lottery_v2.db` | Live database — runtime |
| `claude-code-showcase` | Runtime artifact |

---

## Scope Confirmation

- No D3 UI implemented
- No API route modified
- No DB query or write
- No recommendation/production/registry/controlled_apply/deployment changes
- `GET /api/replay/d3-strategy-status-audit` confirmed intact (63/63 P258N tests PASS)

---

## Next Step

P258O (read-only UI display) may now proceed. Requires separate explicit authorization.
