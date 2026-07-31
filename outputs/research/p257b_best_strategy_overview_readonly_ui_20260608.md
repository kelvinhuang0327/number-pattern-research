# P257B — Best Strategy Overview: Read-Only API + UI Implementation

**Task:** P257B | **Date:** 2026-06-08 | **Type:** C (small additive implementation)
**Classification:** `P257B_BEST_STRATEGY_OVERVIEW_READONLY_UI_IMPLEMENTED`
**Final Decision:** `BEST_STRATEGY_OVERVIEW_READONLY_UI_IMPLEMENTED`

> ⚠️ **歷史回測聲明** — 本頁為歷史回測統計，不代表未來中獎機率。目前沒有任何策略被證明具有可部署預測優勢。本頁不提供投注建議。

---

## Executive Summary

P257B implements the read-only Best Strategy Overview page using the P257A artifact as the sole data source.

- **API endpoint added:** `GET /api/replay/best-strategy-overview` in `lottery_api/routes/replay.py`
- **Frontend section added:** `#p257-overview-section` in `index.html` (vanilla JS SPA)
- **Nav button added:** `data-section="p257-overview"` → 最佳策略總覽
- **Data source:** P257A artifact only — no DB query, no registry mutation
- **3_STAR / 4_STAR:** rendered as empty-state (no replay rows)
- **Warning copy:** rendered prominently above all content

---

## Source Artifact

| Field | Value |
|---|---|
| Artifact | `p257a_best_nbet_strategy_overview_historical_replay_20260608.json` |
| Classification | `P257A_BEST_NBET_STRATEGY_OVERVIEW_HISTORICAL_REPLAY_DATA_READY` |
| Best entries | 14 (BIG_LOTTO N=1–4, DAILY_539 N=1–5, POWER_LOTTO N=1–5) |
| Replay rows | 94,924 |

---

## API Endpoint Summary

**Endpoint:** `GET /api/replay/best-strategy-overview`

**Implementation:** `lottery_api/routes/replay.py`
- Follows evidence-dashboard pattern (`_load_best_strategy_overview_payload`)
- Reads P257A artifact file; no DB access
- Adds metadata flags: `historical_replay_only=true`, `no_future_guarantee=true`, `no_betting_advice=true`, `no_strategy_promotion=true`

**Response includes:**
- All fields from P257A artifact
- `historical_replay_only: true`
- `no_future_guarantee: true`
- `no_betting_advice: true`
- `no_strategy_promotion: true`
- `source_artifact: "p257a_...json"`

---

## Frontend Route Summary

**Frontend type:** Vanilla JS SPA (`index.html`, 4000+ lines)

**Changes made to `index.html`:**
1. New nav button: `<button class="nav-btn" data-section="p257-overview">最佳策略總覽</button>`
2. New section: `<section id="p257-overview-section">`
3. New JS block: `P257B BEST STRATEGY OVERVIEW` IIFE at end of script

---

## UI Layout

```
┌─ Warning Banner (歷史回測聲明) ──────────────────────────────┐
│ 本頁為歷史回測統計，不代表未來中獎機率。本頁不提供投注建議。  │
└──────────────────────────────────────────────────────────────┘

[大樂透] [今彩539] [威力彩] [3星彩] [4星彩]   ← Lottery tabs

┌─ Summary Cards ──────────────────────────────────────────────┐
│ 歷史最佳策略 │ 最高組合成功率 │ 平均最佳命中 │ 回測期數 ...  │
└──────────────────────────────────────────────────────────────┘

┌─ 最佳 N 注組合 (BIG_LOTTO) ──────────────────────────────────┐
│ 組合      │ 最佳策略          │ 回測期數 │ 組合成功率 │ ...   │
│ 最佳 1 注 │ biglotto_devia... │ 1550     │ 57.9%      │ ...   │
│ 最佳 2 注 │ biglotto_echo...  │ 1500     │ 83.8%      │ ...   │
│ 最佳 3 注 │ biglotto_echo...  │ 1500     │ 94.9%      │ ...   │
│ 最佳 4 注 │ biglotto_ts3...   │ 1500     │ 98.8%      │ ...   │
│ 最佳 5 注 │ 此注數組合目前資料不足。                          │
└──────────────────────────────────────────────────────────────┘

┌─ 歷史最高命中紀錄 ───────────────────────────────────────────┐
│ historical_high_hit_event — 未必等同獎級或獎金               │
│ 期別       │ 組合     │ 注序 │ 策略 │ 單注命中 │ 備註        │
└──────────────────────────────────────────────────────────────┘
```

### 3_STAR / 4_STAR empty state:
```
此彩種目前沒有可用回測資料。
```

---

## Warning Copy

### 繁體中文
- 本頁為歷史回測統計，不代表未來中獎機率。
- 最佳策略依歷史資料排序，可能存在過度擬合。
- 目前沒有任何策略被證明具有可部署預測優勢。
- 本頁不提供投注建議。
- 歷史最高命中僅代表回測資料中的命中數紀錄，未必等同實際獎級或獎金。

### English
- This page shows historical replay statistics only; it does not represent future win probability.
- Best strategies are ranked by historical data and may reflect overfitting.
- No strategy has been proven to have a deployable predictive edge.
- This page does not provide betting advice.
- Historical high-hit events refer only to hit counts in replay data and do not imply any prize tier or payout.

---

## Empty States

| Condition | Display |
|---|---|
| 3_STAR or 4_STAR selected | 此彩種目前沒有可用回測資料。 |
| N-bet row missing | 此注數組合目前資料不足。 |
| No prize-tier data | 未提供獎級資料，因此僅顯示命中數，不標示獎級或獎金。 |

---

## Explicit Non-Actions

- **No DB write** — endpoint reads artifact file only via `mode=ro`-equivalent file open
- **No replay generation** — only existing P257A artifact consumed
- **No registry mutation** — `replay_strategy_registry.py` not touched
- **No strategy promotion** — historical ranking ≠ deployment authorization
- **No recommendation-logic change** — no recommendation endpoints modified
- **No betting advice** — warning copy is prominent and binding
- **No broad frontend rewrite** — additive changes only (one nav button, one section, one JS block)
- **No package/tsconfig/CI config changes** — vanilla JS, no build tooling
- **Frontend tests:** NOT RUN — vanilla JS SPA; no jest/tsconfig; running frontend tests would require package config changes which are out of scope

---

## Required Completion Check

| Item | Result |
|---|---|
| Completed | YES |
| Test Result | PASS (see pytest output) |
| Single Blocking Issue | NONE |
| DB write | NO |
| Registry mutation | NO |
| Strategy promotion | NO |
| Betting advice | NO |
| Frontend tests | NOT RUN (vanilla JS, no test runner in scope) |
| Final Classification | `P257B_BEST_STRATEGY_OVERVIEW_READONLY_UI_IMPLEMENTED` |
| Strong Model Needed | NO |
