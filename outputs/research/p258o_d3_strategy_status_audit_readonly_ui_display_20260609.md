# P258O — D3 Strategy Status Audit: Read-only UI Display

**Task ID:** P258O  
**Date:** 2026-06-09  
**Status:** `P258O_D3_STRATEGY_STATUS_AUDIT_READONLY_UI_DISPLAY_READY`

---

## UI Implemented

**Location:** `index.html`  
**Nav button:** `data-section="p258-d3-audit"` — label "D3 合約稽核"  
**Section:** `id="p258-d3-audit-section"`  
**API route:** `GET /api/replay/d3-strategy-status-audit`

---

## UI Features

### Safety disclaimer banner
All 5 required safety disclaimers are displayed in a purple-bordered banner at the top of the section:

1. D3 不是預測模型。(D3 is not a prediction model.)
2. 合約驗證不是策略評估。(Contract validation is not strategy evaluation.)
3. NOT_YET_REJECTED 不是核准。(NOT_YET_REJECTED is not approval.)
4. 通過合約驗證不代表提升預測準確性。(Passing contract validation does not imply improved prediction accuracy.)
5. 本頁為歷史唯讀資料，不作為下注建議。(This page is historical/read-only evidence, not betting advice.)

### Filters (client-side)

| Filter | Type |
|---|---|
| `lottery_type` | DAILY_539 / BIG_LOTTO / POWER_LOTTO / ALL |
| `lifecycle_status` | ADOPTED / PROVISIONAL / EXPERIMENTAL / HISTORICAL_ARTIFACT / REJECTED / ALL |
| `d3_contract_status` | 5 allowed values + ALL |

### Visual separation of lifecycle/evidence vs D3 contract

The table uses **two column groups** with different header colors:

| Group | Color | Columns |
|---|---|---|
| 策略生命週期 / 證據狀態 | Blue (`#58a6ff`) | lottery_type, strategy_id, lifecycle_status, evidence_status, replay_row_count, draw_coverage |
| D3 合約狀態（非核准）| Purple (`#8b5cf6`) | d3_contract_status, d3_contract_reason |

A visual border separates the two groups. The D3 column header explicitly states "(非核准)" (not approval).

### Summary bar

Shows total strategy count and per-D3-status counts.

### Strategy rows table

14 rows loaded from the API payload, filterable client-side.

---

## Allowed D3 Contract Statuses in UI

| Status | Display label |
|---|---|
| `NOT_EVALUATED_BY_D3` | 未評估 |
| `CONTRACT_READY` | 合約就緒 |
| `CONTRACT_BLOCKED` | 合約阻擋 |
| `NOT_APPLICABLE_HISTORICAL_ARTIFACT` | 不適用(歷史) |
| `NOT_APPLICABLE_NO_REPLAY` | 不適用(無回放) |

**Forbidden statuses confirmed absent:** `APPROVED`, `PROMOTED`, `PRODUCTION_READY`, `RECOMMENDED`, `PREDICTIVE_EDGE_CONFIRMED`

---

## Scope Confirmation

- No DB query
- No D3 execution
- No strategy evaluation, scoring, or recommendation
- No forbidden D3 statuses
- No API route behavior modified
- No recommendation/production/registry/controlled_apply/deployment paths touched

---

## Next Step

P258P (read-only E2E / UX / safety closeout) may proceed if explicitly authorized.
