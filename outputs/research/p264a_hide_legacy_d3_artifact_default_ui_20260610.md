# P264A — Hide Legacy D3 Artifact From Default UI

_Read-only index.html display change. No API/DB/registry/adapter change._

## Problem

After P263B, the sidebar nav had two D3 buttons at equal visual prominence:
- **D3 合約稽核** (P258O, `p258-d3-audit`) — artifact-backed, 14 rows, 8 mapped + 6 phantom, 2026-06-09 snapshot
- **D3 策略狀態 (SSOT)** (P263B, `p263b-d3-ssot`) — live SSOT, 41 cells, 40 strategies, 0 phantom

A user scanning the nav might click D3 合約稽核 first and see "14 rows" as the strategy count, which is misleading.

## Solution — nav_reorder_plus_details_collapse

### 1. Nav reorder + visual demotion

| | Before | After |
|---|---|---|
| Nav position 1 | D3 合約稽核 (P258O legacy) | **D3 策略狀態 (SSOT)** ← primary |
| Nav position 2 | D3 策略狀態 (SSOT) | D3 合約稽核 (Legacy) ← dimmed (opacity 0.55, font-size 0.88em) |

The P258O button label changed to **D3 合約稽核 (Legacy)** and carries a tooltip: _"Historical Artifact — Legacy D3 Contract Audit (artifact-backed, 14 rows, 2026-06-09)"_.

### 2. P258O section heading — Legacy badge

The h2 now includes a grey "Legacy" chip next to the title.

### 3. Prominent legacy warning banner (always visible when section is active)

A new `#p258-legacy-warning-p264a` div appears above the `<details>`:

> ⚠️ 此區為歷史 D3 Artifact 稽核資料（Legacy / Historical Artifact）
> 此頁顯示的是 P258N artifact-backed 靜態資料（2026-06-09 快照，14 rows = 8 mapped + 6 phantom），**不代表目前策略總數或最新狀態**。
> 目前正式策略狀態請以左側「**D3 策略狀態 (SSOT)**」為準（40 strategies / 41 cells，即時從 registry ∪ replay store 建構）。

### 4. section-content wrapped in `<details>` (collapsed by default)

The entire table/filters/summary content is inside a `<details>` element with no `open` attribute, so it renders collapsed. The `<summary>` reads:

> 展開歷史稽核資料 / Expand Legacy D3 Artifact Audit Data (artifact-backed snapshot · 14 rows · 2026-06-09)

## Locked contract preservation

All P258N/O/P test constraints are preserved verbatim:
- `data-section="p258-d3-audit"` nav button ✓
- `id="p258-d3-audit-section"` section ID ✓
- `p258-disclaimer-banner` disclaimer ID ✓
- `NOT_YET_REJECTED` text ✓
- `預測模型` text ✓
- JS: `p258Init()` call ✓
- JS: `/api/replay/d3-strategy-status-audit` fetch URL ✓

(The `test_no_ui_files_modified_in_branch` branch-isolation test will fail on-branch as expected — not CI-gated, same accepted pattern as all tasks since P259A.)

## No changes to

- `lottery_api/routes/replay.py` — untouched
- DB, registry, adapter, migration — none
- P263B SSOT section — untouched
- Any other file outside the whitelist

## Test results

| Suite | Result |
|---|---|
| `test_p264a_hide_legacy_d3_artifact_default_ui.py` | **31/31 PASS** |
| `test_p263b_d3_strategy_status_ssot_rebuild.py` | **29/29 PASS** |
| `test_replay_api_contract.py` | **44/44 PASS** |
| `git diff --check` | **CLEAN** |
