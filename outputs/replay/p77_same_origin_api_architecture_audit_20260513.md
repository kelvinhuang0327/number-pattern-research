# P77 Same-Origin API Architecture Audit

**Date**: 2026-05-13  
**Branch**: main (`a7c8399`)  
**Operator**: P77 Architecture Audit Agent  
**Scope**: Read-only audit + pending PR status review

---

## 1. Round Objective

1. Check pending PR merge status (gated on explicit YES)
2. Verify safety hashes unchanged
3. Audit same-origin API architecture — why P76 browser QA required a Playwright fetch proxy
4. Produce options comparison and P78 recommendation
5. Note `outputs/relay` vs `outputs/replay` path inconsistency

---

## 2. Baseline

| Item | Value |
|------|-------|
| main HEAD | `a7c8399` |
| Commit | `frontend(replay/p69): polish truth-level UI badges (#87)` |
| Dirty files (pre-existing, not staged) | `backend.pid`, `data/lottery_v2.db`, `frontend.pid` |

---

## 3. Safety Hash Verification

| File | Hash | Status |
|------|------|--------|
| `lottery_api/data/lottery_v2.db` | `de0e27bb800bc7183773a0dc596d66b8` | ✅ UNCHANGED |
| `lottery_api/models/replay_strategy_registry.py` | `3ea71cfc20c882714f3824ad68202f6e` | ✅ UNCHANGED |
| Root-level `data/lottery_v2.db` | Modified (pre-existing local dirty) | ⚠️ NOT STAGED — runtime artifact |

No DB, registry, or pid files staged. Safety gate PASSED.

---

## 4. Pending PR Status

| PR | Title | State | Mergeable | CI | mergeStateStatus |
|----|-------|-------|-----------|-----|-----------------|
| #89 | ops/p75-startup-reliability | OPEN | MERGEABLE | 2/2 PASS | CLEAN |
| #88 | docs/p70-pr87-operator-evidence | OPEN | MERGEABLE | 2/2 PASS | **BEHIND** |
| #90 | docs/p76-browser-visual-qa | OPEN | MERGEABLE | 2/2 PASS | CLEAN |

### PR Merge Results

No `YES merge` approvals received for any PR in this session.

- PR #89: **WAITING_FOR_YES_MERGE_PR89**
- PR #88: **WAITING_FOR_YES_MERGE_PR88** (note: BEHIND main — may need rebase before merge)
- PR #90: **WAITING_FOR_YES_MERGE_PR90**

### PR #89 Diff (startup reliability patch)

```
outputs/replay/p75_startup_reliability_patch_report_20260513.md
start_all.sh
```

Patch adds: `REPO_ROOT`, `PYTHON_BIN`, `PYTHONPATH` anchoring + improved port-in-use warning.

### PR #88 Diff (P70 operator evidence)

```
outputs/replay/p70_pr87_merge_and_operator_evidence_report_20260513.md
```

### PR #90 Diff (P76 browser visual QA)

```
outputs/relay/p76_browser_visual_qa_badges_detail_20260513.png
outputs/relay/p76_browser_visual_qa_dom_evidence_20260513.txt
outputs/relay/p76_browser_visual_qa_lifecycle_20260513.png
outputs/relay/p76_browser_visual_qa_report_20260513.md
```

---

## 5. P76 Evidence Status

| Check | Result |
|-------|--------|
| Lifecycle table loaded | ✅ `wrapDisplay: block` |
| Truth badges rendered | ✅ 16 badges |
| Badge types seen | `NO HISTORY`, `LIVE`, `METADATA ONLY` |
| LIVE color | `rgb(26, 127, 55)` (green) ✅ |
| METADATA ONLY color | `rgb(187, 128, 9)` (amber) ✅ |
| NO HISTORY color | `rgb(74, 74, 74)` (dark grey) ✅ |
| aria-label present | ✅ all 3 types |
| Bilingual tombstone | ✅ |
| Bilingual DISPLAY_ONLY | ✅ |
| Static 12/12 gate | ✅ |

P76 verdict: `ACCEPT_AS_MVP_WITH_EVIDENCE`

---

## 6. Same-Origin Architecture Finding

### 6.1 Root Cause

`index.html` (line 2706):
```javascript
const BASE = '/api/replay';
```

Three fetch calls in the replay UI all use relative URLs:
```javascript
// line 2922
fetch('/api/replay/summary?lottery_type=' + encodeURIComponent(lotteryType))

// line 3446
fetch('/api/replay/strategy-lifecycle')

// line 3507
fetch(BASE + '/freshness')
```

No absolute URLs or `localhost` hardcoding exists in `index.html`. **The UI assumes it will be served from the same origin as the API.**

### 6.2 Dev Environment Architecture

| Service | Server | Port | Proxy capability |
|---------|--------|------|-----------------|
| Frontend (index.html) | `python3 -m http.server 8081` | 8081 | ❌ None — static file only |
| Backend (FastAPI) | `python3 app.py` (uvicorn) | 8002 | N/A |

`python3 -m http.server` is a pure static file server. It cannot:
- Route `/api/` requests to another port
- Act as a reverse proxy
- Serve headers or rewrite URLs

### 6.3 Why P76 Required Playwright Fetch Proxy

When the browser loads `http://localhost:8081/`, all `fetch('/api/...')` calls resolve to `http://localhost:8081/api/...`. Python http.server returns **404** for any path that isn't a real file.

The backend at `http://localhost:8002/api/...` is reachable via CORS (`allow_origins: ["*"]`), but the relative URL never reaches it.

**Playwright workaround** (`addInitScript` before page JS):
```javascript
const orig = window.fetch.bind(window);
window.fetch = async function(url, opts) {
  const s = String(url);
  if (s.startsWith('/api/')) return orig('http://localhost:8002' + s, opts);
  return orig(url, opts);
};
```

This must be `addInitScript` (pre-execution hook), not `page.evaluate()` — by the time post-load eval runs, the lifecycle fetch has already failed and error state is set.

---

## 7. Local Dev Impact

- Operator cannot open `http://localhost:8081` in a regular browser and see the lifecycle table load — it returns 404 on `/api/replay/strategy-lifecycle`
- Must use either: Playwright fetch proxy, or a same-origin server, or manually navigate via `http://localhost:8002` (but FastAPI doesn't serve static files either)
- This creates a **gap between development QA** (Playwright) and **manual browser testing** (broken lifecycle panel)

---

## 8. Production Impact

In a typical production deployment where both frontend and backend are served behind a single reverse proxy (nginx/caddy) on the same origin, relative URLs like `/api/replay/...` work correctly. **The same-origin design is production-appropriate.**

The issue is **only in local dev** where two separate servers run on different ports without a shared proxy.

---

## 9. Options Comparison

| Option | Description | Risk | Code Change | Dev UX |
|--------|-------------|------|-------------|--------|
| A | Document local dev limitation only | ✅ Zero | None | ❌ Manual workaround needed |
| B | FastAPI serves static files (`StaticFiles`) | Medium | `app.py` + startup | ✅ Single port, no CORS |
| C | Add dev proxy (nginx/caddy/Python wrapper) | Medium | `start_all.sh` + config | ✅ Both ports proxied |
| D | Configurable `API_BASE` in `index.html` | **Lowest** | 2 lines in `index.html` | ✅ Set to `http://localhost:8002` in dev |

### Option D Detail (recommended for P78)

Add to `index.html` `<head>`:
```html
<script>window.API_BASE = '';</script>
<!-- In dev, override with: window.API_BASE = 'http://localhost:8002' -->
```

Change `index.html` JS:
```javascript
// line 2706 — change:
const BASE = (window.API_BASE || '') + '/api/replay';
// All existing fetch('/api/...') calls also prepend window.API_BASE || ''
```

For dev, a `<script>` block in `index.html` or a separate `dev-config.js` sets `window.API_BASE = 'http://localhost:8002'`. In production, `window.API_BASE` stays empty → relative URLs work.

**Risk**: Minimal. Changes are confined to `index.html` JS, no backend changes, no build tools needed.

### Recommendation

`P78_CONFIGURABLE_API_BASE_RECOMMENDED`

Option D is lowest risk, zero backend change, production-safe, and unblocks manual browser testing in local dev without requiring Playwright or a proxy server.

---

## 10. `outputs/relay` vs `outputs/replay` Path Inconsistency

| PR | Path Used |
|----|-----------|
| PR #89 | `outputs/replay/p75_...` ✅ correct |
| PR #88 | `outputs/replay/p70_...` ✅ correct |
| PR #90 (P76 evidence) | `outputs/relay/p76_...` ⚠️ typo — `relay` instead of `replay` |

**Impact**: Low. Files are in a non-tracked outputs directory and PRs are already open. Renaming in P78 would require a separate `git mv` commit to avoid breaking the evidence trail.

**Recommendation**: Do not rename in this PR. If desired, open a dedicated **P78 docs cleanup PR** to move `outputs/relay/` → `outputs/replay/` atomically with a git history note.

---

## 11. Next 24H Prompt for P78

> **P78 Mission**: Implement Option D — configurable `API_BASE` in `index.html` to fix local dev same-origin gap.
>
> 1. Add `window.API_BASE = ''` as default in `index.html`
> 2. Change `const BASE = '/api/replay'` → `const BASE = (window.API_BASE || '') + '/api/replay'`
> 3. Update all `fetch('/api/...')` calls to prepend `(window.API_BASE || '')`
> 4. Add developer comment block in `index.html` explaining dev override
> 5. Update `start_all.sh` to print the override instruction
> 6. Verify lifecycle table loads in browser from port 8081 WITHOUT Playwright fetch proxy
> 7. Verify production same-origin path still works (relative URLs with empty API_BASE)
> 8. Merge PR #89, #88, #90 if approvals received
> 9. Optionally: P78 docs cleanup — move `outputs/relay/` → `outputs/replay/`

---

## 12. Final Markers

- ✅ P77_BASELINE_VERIFIED — main `a7c8399`
- ✅ P77_DB_UNCHANGED — `de0e27bb800bc7183773a0dc596d66b8`
- ✅ P77_REGISTRY_UNCHANGED — `3ea71cfc20c882714f3824ad68202f6e`
- ⏳ WAITING_FOR_YES_MERGE_PR89 — PR #89 OPEN/MERGEABLE/CLEAN/CI 2/2
- ⏳ WAITING_FOR_YES_MERGE_PR88 — PR #88 OPEN/MERGEABLE/BEHIND/CI 2/2
- ⏳ WAITING_FOR_YES_MERGE_PR90 — PR #90 OPEN/MERGEABLE/CLEAN/CI 2/2
- ✅ P77_SAME_ORIGIN_AUDIT_COMPLETE
- ✅ P77_REPORT_CREATED — `outputs/replay/p77_same_origin_api_architecture_audit_20260513.md`
- ⏳ P77_DOCS_PR_OPENED — (Stage H)
- ⏳ P77_READY_FOR_P78
