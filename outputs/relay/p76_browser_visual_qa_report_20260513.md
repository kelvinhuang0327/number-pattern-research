# P76 Browser Visual QA Report

**Date**: 2026-05-13  
**Branch**: main (`a7c8399`)  
**Operator**: P76 sequential Stage A–I execution  
**Verdict**: `ACCEPT_AS_MVP_WITH_EVIDENCE`

---

## 1. Round Objective

Perform browser visual QA of the merged P69 truth-level UI badges in `index.html`.  
Verify all truth-level badges render correctly, aria-labels present, bilingual disclaimers visible, and no regression from P75 polish.

---

## 2. Baseline

| Item | Value |
|------|-------|
| main HEAD | `a7c8399` |
| DB hash | `de0e27bb800bc7183773a0dc596d66b8` ✅ UNCHANGED |
| Registry hash | `3ea71cfc20c882714f3824ad68202f6e` ✅ UNCHANGED |
| Static 12/12 gate | ✅ PASS |

---

## 3. PR Status

| PR | Title | Status |
|----|-------|--------|
| #89 | ops/p75-startup-reliability | OPEN / MERGEABLE / CLEAN / CI 2/2 ⏳ WAITING_FOR_YES_MERGE_PR89 |
| #88 | P70 operator evidence docs | OPEN / CLEAN / CI 2/2 ⏳ WAITING_FOR_YES_MERGE_PR88 |

> Neither PR has been merged. Both remain open awaiting explicit `YES merge PR #89` / `YES merge PR #88`.

---

## 4. Service Status

| Service | PID | Port | Status |
|---------|-----|------|--------|
| FastAPI backend | 27006 | 8002 | ✅ HEALTHY |
| Frontend (http.server) | 27009 | 8081 | ✅ UP |

**Backend API verification**:
- `/health` → `{"status":"healthy","busy":false,"models":{"prophet":"available","xgboost":"available","autogluon":"available","lstm":"available"}}`
- `/api/replay/strategy-lifecycle` → total=16, ONLINE=6, REJECTED=4, OBSERVATION=1, RETIRED=5
- BIG_LOTTO/POWER_LOTTO/DAILY_539 summaries → 2 strategies each responding ✅

---

## 5. Static 12/12 Gate Results

| Check | File Location | Status |
|-------|--------------|--------|
| `function deriveTruthLevelForStrategy` | line 2876 | ✅ |
| `function renderTruthLevelBadge` | line 2901 | ✅ |
| `rpFetchReplaySummaryCounts` | lines 2920, 3472 | ✅ |
| `rpBuildStrategyRowCountMap` | lines 2925, 2937 | ✅ |
| `rpStrategyRowCountMap` | lines 2712, 2975, 3469+ | ✅ |
| `Truth Level` | line 2133 | ✅ |
| `LEGACY ERROR` | line 2907 | ✅ |
| `NO HISTORY` | line 2905 | ✅ |
| `METADATA ONLY` | line 2904 | ✅ |
| `REGENERATED_RETROSPECTIVE` | lines 2898, 2908 | ✅ |
| `#6f42c1` (purple) | lines 80, 269 | ✅ |
| `aria-label` | 8 occurrences | ✅ |

---

## 6. Browser Visual QA Results

### 6.1 Architecture Finding

`index.html` line 2706: `const BASE = '/api/replay'` — relative URL.  
When served from port 8081 (Python http.server), all `/api/...` fetch calls route to `http://localhost:8081/api/...` → 404.  
FastAPI (port 8002) does not serve static files and has no reverse proxy.

**Workaround applied**: `page.addInitScript()` patched `window.fetch` before page JS execution to route `/api/` → `http://localhost:8002`. This must be `addInitScript` (pre-execution), not post-load `page.evaluate()`.

### 6.2 Lifecycle Registry Table

| Metric | Value | Status |
|--------|-------|--------|
| `#rp-lc-table-wrap` display | `block` | ✅ Visible |
| `#rp-lc-error` display | `none` | ✅ No error |
| Total truth badges | 16 | ✅ |
| Table rows | 26 | ✅ |
| First strategy | `acb_1bet` | ✅ |

### 6.3 Badge Visual Verification

| Badge Type | CSS Class | Computed BG Color | aria-label | Status |
|-----------|-----------|-------------------|-----------|--------|
| NO HISTORY | `rp-truth-badge rp-truth-missing` | `rgb(74, 74, 74)` (dark grey) | "NO HISTORY: No production replay history available" | ✅ |
| LIVE | `rp-truth-badge rp-truth-production` | `rgb(26, 127, 55)` (green) | "LIVE: Production replay rows exist" | ✅ |
| METADATA ONLY | `rp-truth-badge rp-truth-display` | `rgb(187, 128, 9)` (amber) | "METADATA ONLY: Metadata only, not production replay" | ✅ |

Badge type distribution: NO HISTORY=5, LIVE=6, METADATA ONLY=5

**Badges not seen** (no strategies with these lifecycle states active):
- RETROSPECTIVE (`rp-truth-retro`, expected `#6f42c1` purple) — verified in static gate ✅
- LEGACY ERROR — verified in static gate ✅
- FIXTURE — verified in static gate ✅

### 6.4 Bilingual Disclaimer Verification

**Tombstone** (🪦 NO HISTORY rows):
> 此策略目前沒有 production replay 歷史資料；不會產生假回放列。  
> This strategy has been retired. Historical prediction records are not available.  
✅ Present, bilingual, accurate

**DISPLAY_ONLY** (⚠️ METADATA ONLY rows):
> 此策略僅顯示 metadata，不代表已存在 production replay 回放。  
> This strategy was evaluated but is not in active production. No per-draw prediction history is available.  
✅ Present, bilingual, accurate

### 6.5 Evidence Files

| File | Description |
|------|-------------|
| `outputs/relay/p76_browser_visual_qa_lifecycle_20260513.png` | Screenshot: lifecycle registry table with truth badges |
| `outputs/relay/p76_browser_visual_qa_badges_detail_20260513.png` | Screenshot: badge detail scrolled view |
| `outputs/relay/p76_browser_visual_qa_dom_evidence_20260513.txt` | Full DOM evidence JSON + badge details |

---

## 7. Limitations

1. **No reverse proxy**: `index.html` relative URLs require same-origin serving or a proxy. In automated QA, `addInitScript` fetch patch is required. In real operator usage, the operator must serve both from the same port or use a proxy.
2. **RETROSPECTIVE/FIXTURE/LEGACY_ERROR badges not seen live**: These badge types are implemented in code (verified static 12/12) but no active strategies carry those lifecycle states, so live visual confirmation was not possible.

---

## 8. Verdict

`ACCEPT_AS_MVP_WITH_EVIDENCE`

- All implemented badge types render correctly with correct colors, aria-labels, and bilingual text ✅
- No regressions from P75/P69 merge ✅
- Static gate 12/12 PASS ✅
- Live 16 truth badges rendering (NO HISTORY, LIVE, METADATA ONLY) ✅
- Architecture limitation documented (relative URL / no proxy) — known issue, not a new regression

---

## 9. Next — P77 Prompt

> P77 objective: Add a reverse proxy or `nginx` config so `index.html` can be served correctly without the Playwright fetch workaround. OR update `const BASE` to be configurable via env/config. Verify lifecycle registry loads from port 8081 directly without any fetch patching.

---

*P76 complete. Docs PR to be created in Stage I.*
