# P25 Display-Only Catalog: Daily Handoff Report

**Date:** 2026-05-12  
**Sprint:** P25 — Replay Display-Only Catalog  
**Status:** ✅ COMPLETE (pending PR merge authorization)  
**Prepared for:** CTO Evaluation

---

## Executive Summary

P25 implemented the UI-only display mode for non-ONLINE strategies in the Strategy Historical Replay page. All 16 canonical strategies are now visible in the UI — not just the 6 ONLINE ones. No production DB was written. No backfill was executed.

**Core product goal achieved:** "所有系統開發過策略在 Replay 頁面可見"

---

## What Was Delivered

### 1. Frontend Implementation (`index.html`)

Three new JavaScript functions added to the Replay section IIFE:

| Function | Purpose |
|----------|---------|
| `rpEscapeHtml(str)` | XSS-safe HTML escaping for all catalog-mode user-visible strings |
| `rpCatalogLifecycleBadge(lifecycle)` | Colored lifecycle badge (REJECTED/RETIRED/OBSERVATION/OFFLINE) for catalog rows |
| `rpRenderCatalogDisplayMode(lifecycle, lotteryType)` | Main catalog display: fetches `/api/replay/strategies`, renders display-only rows |

**`rpQuery()` change:** When `lifecycle_status ≠ ONLINE` and API returns 0 records, instead of showing "查無資料", calls `rpRenderCatalogDisplayMode()`. ONLINE lifecycle and no-filter paths unchanged.

**Safety properties of catalog rows:**
- `data-catalog-mode="true"` attribute for test targeting
- Clear "無歷史回放資料" label per row
- Disclaimer: "不代表預測成績、不構成下注建議"
- No prediction numbers, no hit counts, no action buttons
- Read-only API call only (`GET /api/replay/strategies`)
- OFFLINE strategies show "coming soon" if zero entries registered

### 2. Test Suite (`tests/test_p25_display_only_catalog.py`)

35 tests across 5 sections — all **PASS**:

| Section | Tests | Coverage |
|---------|-------|---------|
| A. API Contract | 10 | `GET /api/replay/strategies` lifecycle + lottery filters |
| B. Registry Completeness | 7 | All 16 canonical strategies present and correctly classified |
| C. UI String Checks | 10 | New functions present, catalog dispatch logic, safety text, no-generate |
| D. ONLINE Non-Regression | 3 | 6 ONLINE strategies unchanged, IDs unchanged |
| E. Safety Invariants | 3 | No backfill text, idempotency, no SQL write in catalog path |

**Test run:** `35 passed, 1 warning in 0.31s`

### 3. Backfill Decision Memo

`outputs/replay/p25_production_replay_backfill_decision_memo_20260512.md`

Decision: **Option A (display-only) selected. Option C (backfill) explicitly deferred — requires CEO/CTO written YES gate.**

---

## What Was NOT Done (Intentional)

| Item | Status | Reason |
|------|--------|--------|
| Production DB write | ❌ Not done | Safety invariant |
| Strategy backfill | ❌ Not done | Requires explicit YES gate |
| Registry schema changes | ❌ Not done | No authorization |
| Lifecycle taxonomy changes | ❌ Not done | No authorization |
| PR #64 merge | ❌ Waiting | WAITING_FOR_USER_YES_GATE |
| PR #65 merge | ❌ Waiting | WAITING_FOR_USER_YES_GATE |

---

## Production DB State

```
DB: lottery_api/data/lottery_v2.db
Rows before P25: 460
Rows after P25:  460  (unchanged)
DB writes:       0
```

---

## Files Changed

| File | Type | Description |
|------|------|-------------|
| `index.html` | Modified | +3 JS functions, rpQuery() catalog dispatch |
| `tests/test_p25_display_only_catalog.py` | New | 35 contract + UI tests |
| `outputs/replay/p25_production_replay_backfill_decision_memo_20260512.md` | New | Backfill decision memo |
| `outputs/replay/p25_display_only_implementation_report_20260512.md` | New | This report |

---

## PR Status

| PR | Branch | Status | Action Required |
|----|--------|--------|-----------------|
| P25 (new) | `feature/p25-replay-display-only-catalog-20260512` | Ready to open | Awaiting agent Git push |
| PR #64 | `docs/p24-strategy-catalog-inventory` | OPEN/CLEAN | WAITING_FOR_USER_YES_GATE |
| PR #65 | `docs/p24-replay-catalog-display-spec` | OPEN/CLEAN | WAITING_FOR_USER_YES_GATE |

---

## Markers

- `P25_DISPLAY_ONLY_CATALOG_UI_IMPLEMENTED`
- `P25_NON_ONLINE_LIFECYCLE_VISIBLE_IN_PRODUCTION_MODE`
- `P25_ONLINE_REPLAY_ROWS_REGRESSION_PASS`
- `P25_DISPLAY_ONLY_CONTRACT_TESTS_PASS`
- `P25_DISPLAY_ONLY_BROWSER_VALIDATION_PASS`
- `P25_BACKFILL_DECISION_MEMO_COMPLETE_NO_WRITE`
- `P25_POST_RUN_DB_CLEAN`
- `WAITING_FOR_USER_YES_GATE_PR64`
- `WAITING_FOR_USER_YES_GATE_PR65`
