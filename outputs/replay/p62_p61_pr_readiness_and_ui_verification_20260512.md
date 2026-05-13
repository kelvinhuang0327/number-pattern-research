# P62: P61 PR Readiness + UI Verification + Row Count Integration Audit

**Date:** 2026-05-13  
**Agent Role:** Replay Truth UI PR Readiness & Verification Agent  
**Reports To:** CTO → CEO  
**Branch:** `frontend/p61-replay-truth-level-badge-mvp-20260512`  
**Base:** `main` @ `20ae29e`

---

## 1. 本輪目標

確認 P61 truth-level badge MVP 是否可開 PR，並補足：
- Browser / Manual UI verification（DOM smoke test）
- Row-count accuracy 風險評估
- PR readiness 決定

不做 DB migration、backfill、strategy adapter 或 registry 修改。

---

## 2. Branch / Commit 狀態

| 項目 | 值 |
|---|---|
| Branch | `frontend/p61-replay-truth-level-badge-mvp-20260512` |
| HEAD SHA | `e1dc7be` |
| Commit Message | `frontend(replay/p61): add truth-level badge MVP` |
| Base (main) SHA | `20ae29e` |
| Commits ahead of main | 1 |
| Merge conflicts | 無 |

**P62 결론：** branch 狀態正常，HEAD 符合預期。

---

## 3. Diff Scope 檢查

```
git diff --name-only main..HEAD
index.html
outputs/replay/p61_replay_truth_level_badge_mvp_report_20260512.md
```

| 項目 | 結果 |
|---|---|
| 允許文件 `index.html` | ✓ |
| 允許文件 `outputs/replay/p61_*.md` | ✓ |
| DB 文件出現在 diff | 無 |
| Registry 文件出現在 diff | 無 |
| Adapter 文件出現在 diff | 無 |
| Fixture artifact 出現在 diff | 無 |
| 未允許文件 | 無 |

**Diff stats:** 2 files changed, 545 insertions(+), 8 deletions(-)  
**Diff scope: PASS** — 只包含允許文件，無污染。

---

## 4. Static Verification 結果

全部透過 `grep -n` 對 `index.html` 執行：

| 檢查項目 | 行號 | 結果 |
|---|---|---|
| `function deriveTruthLevelForStrategy` | 2875 | ✓ PASS |
| `function renderTruthLevelBadge` | 2900 | ✓ PASS |
| lifecycle table header `Truth Level` | 2133 | ✓ PASS |
| `LEGACY ERROR` badge text | 2906 | ✓ PASS |
| `NO HISTORY` badge text (MISSING_HISTORY) | 2904 | ✓ PASS |
| `METADATA ONLY` badge text (DISPLAY_ONLY) | 2903 | ✓ PASS |
| `REGENERATED_RETROSPECTIVE` placeholder only | 2897, 2907 | ✓ PASS |
| `REGENERATED_RETROSPECTIVE` NOT returned by derive fn | — | ✓ PASS |
| `DISPLAY_ONLY` disclaimer row (tombstone) | 2962 | ✓ PASS |
| `MISSING_HISTORY` tombstone row | 2969 | ✓ PASS |
| `FIXTURE_ONLY` badge (FIXTURE) | 2905 | ✓ PASS |
| `PRODUCTION_REPLAY` badge (LIVE) | 2902 | ✓ PASS |

**Static Verification: PASS**

### 關鍵 Notes（Static）

1. **REGENERATED_RETROSPECTIVE 僅為 placeholder**：`renderTruthLevelBadge` 的 badges map 中有定義，但 `deriveTruthLevelForStrategy` 從不 return 此值。確認不接 DB。

2. **LEGACY_ERROR 派生邏輯**：從 `r.replay_status === 'REPLAY_ERROR'` 派生，不依賴 DB schema 額外欄位。

3. **FIXTURE_ONLY 派生邏輯**：從 `r.fixture_mode || r.fixture_only || r.synthetic_only` 派生。目前後端 API 不返回這些欄位（fields 不在 response schema），因此 FIXTURE_ONLY badge 在 live 環境不會觸發（安全，無誤判風險）。

---

## 5. Browser / Manual UI Smoke 結果

**方式：** DOM-level 靜態分析（Node.js + Python string check）+ 後端 API 呼叫驗證  
**原因不使用 Playwright：** playwright 未安裝於此環境  
**Local server：** `python3 -m http.server 9876` 啟動，index.html 成功返回（HTTP 200 + title: "Lotto Insight Platform"）

### DOM Checks（Python script，15 checks）

| Check | 結果 |
|---|---|
| Truth Level header | PASS |
| rp-truth-badge CSS class | PASS |
| LIVE badge (PRODUCTION_REPLAY) | PASS |
| METADATA ONLY badge (DISPLAY_ONLY) | PASS |
| NO HISTORY badge (MISSING_HISTORY) | PASS |
| FIXTURE badge | PASS |
| LEGACY ERROR badge | PASS |
| RETROSPECTIVE placeholder | PASS |
| REGENERATED_RETRO NOT wired to DB | PASS |
| DISPLAY_ONLY disclaimer row | PASS |
| MISSING_HISTORY tombstone row | PASS |
| LEGACY_ERROR row class | PASS |
| FIXTURE row class | PASS |
| deriveTruthLevelForStrategy fn exists | PASS |
| renderTruthLevelBadge fn exists | PASS |

**OVERALL: ALL PASS (15/15)**

### API 驗證（實際後端回應）

後端運行於 port 8002（來自 `LotteryNew/lottery_api`，branch `feature/phase4-required-check-20260509`）。

| 端點 | 狀態 | 備注 |
|---|---|---|
| `GET /api/replay/history?lottery_type=BIG_LOTTO&limit=5` | 200 ✓ | 返回 140 筆 PREDICTED 記錄 |
| `GET /api/replay/summary?lottery_type=BIG_LOTTO` | 200 ✓ | 返回每策略 `total_rows: 70` |
| `GET /api/replay/strategy-lifecycle` | 404 ✗ | 運行中後端版本較舊，缺此 route |
| REPLAY_ERROR 記錄 | 0 筆 | 目前 BIG_LOTTO 無 REPLAY_ERROR 記錄 |

**Browser Smoke: PASS（DOM checks）/ PARTIAL（API — strategy-lifecycle 404）**

> ⚠️ `/api/replay/strategy-lifecycle` 404 的原因：正在運行的後端是 `LotteryNew` workspace（branch `feature/phase4-required-check-20260509`，replay.py 636 lines），而此 endpoint 在 `main` 和 P61 branch（replay.py 903 lines）才存在。這是 **環境問題，不是 P61 bug**。P61 merge 後，main 版本的 replay.py 已包含此 route。

---

## 6. Row Count Integration Audit

### Q1：lifecycle registry rows 是否已包含 production replay row count？

**否。** `/api/replay/strategy-lifecycle` response 僅包含 in-memory registry metadata（lifecycle_status, is_executable 等），不包含 DB row counts。  
Frontend 目前在 lifecycle registry table 渲染時 hardcode `total_rows: 0`：

```javascript
// P61: Derive truth-level (assuming 0 rows for now; real row counts would come from summary API)
const rowCounts = { total_rows: 0 };  // TODO: integrate with /api/replay/summary if needed
```

### Q2：replay summary 是否可提供 per-strategy row count？

**是。** `/api/replay/summary?lottery_type=BIG_LOTTO` 返回：
```json
{ "strategy_id": "biglotto_triple_strike", "total_rows": 70, ... }
```
Backend 已具備能力，無需 DB schema 變更。

### Q3：P61 是否有 hardcoded 0 或 incomplete row count？

**是。** 在 lifecycle registry table 渲染中，`total_rows` 固定為 0。  
**影響分析：**

| 情境 | 當前行為（hardcoded 0） | 正確行為（接 API） |
|---|---|---|
| ONLINE 策略（有 rows） | 返回 `UNKNOWN` → badge 灰色 | 返回 `PRODUCTION_REPLAY` → LIVE badge |
| ONLINE 策略（無 rows） | 返回 `UNKNOWN` | 返回 `UNKNOWN`（相同） |
| REJECTED/OBSERVATION | 返回 `DISPLAY_ONLY`（正確） | 返回 `DISPLAY_ONLY`（正確） |
| RETIRED, !exec | 返回 `MISSING_HISTORY`（正確） | 返回 `MISSING_HISTORY`（正確） |
| RETIRED, has rows | 返回 `UNKNOWN` | 返回 `PRODUCTION_REPLAY` |

> ⚠️ **P61 已知限制**：ONLINE 策略在 lifecycle registry table 顯示 `UNKNOWN`，而非 `LIVE`。此為 MVP scope，已在 P61 report 中標記為 TODO。

### Q4：若要準確顯示 MISSING_HISTORY，需要 frontend-only 修正還是 backend response field？

**Frontend-only 修正即可**。  
修正方式：在 `rpRenderLifecycleRegistry()` 初始化時，先 fetch `/api/replay/summary` (per supported_lottery_type) 建立 `strategyId → total_rows` 映射，再傳入 `deriveTruthLevelForStrategy`。  
不需要新增 backend endpoint 或修改 DB。

### Q5：是否可在不改 DB 的情況下補 endpoint response field？

**是。** 兩個方案：
1. **前端 join**：fetch `strategy-lifecycle` + `summary` per lottery type，client-side join。
2. **後端增強**（可選）：在 `/api/replay/strategy-lifecycle` response 中附加 `row_counts_by_lottery_type` per strategy（從 `strategy_prediction_replays` 聚合查詢）。不需 DB migration。

### Q6：P63 是否需要 backend API enhancement？

**建議性 enhancement，非必要**。  
P63 可以純 frontend 方案整合 row count：
- fetch `summary` + `strategy-lifecycle` 兩個 endpoints
- build strategy → row_count map
- 傳入 `deriveTruthLevelForStrategy`

若要更乾淨的 API，P63 可選擇在 `/api/replay/strategy-lifecycle` 中直接包含 row counts（backend 單次查詢）。但不需要 DB migration，只需 backend route enhancement。

---

## 7. 是否建議開 P61 PR？

**建議：是。可開 PR。**

**理由：**
- Diff scope 乾淨，無 DB/registry/adapter 污染
- Static verification 全 PASS
- DOM smoke test 15/15 PASS
- REGENERATED_RETROSPECTIVE 確認為 placeholder（不接 DB）
- Row count hardcoded 0 為已知 MVP 限制，在 P61 report 中已文件化
- ONLINE → UNKNOWN 的視覺問題在 lifecycle registry table 中存在，但不影響 per-row LIVE/LEGACY ERROR/FIXTURE badge（這些直接從 API response 欄位派生，不依賴 row count）
- 不 merge，只開 PR，供 review

**P61 PR 開啟條件：** 收到 `YES open P61 UI truth-level badge MVP PR`

---

## 8. 是否建議 Merge P61 PR？

**建議：暫緩 merge，等 code review 完成後再決定。**

**理由：**
- PR 需要 code review 確認 ONLINE→UNKNOWN 的 known limitation 是否可接受
- 建議在 PR description 中明確標記 `total_rows hardcoded=0` 限制
- 若 reviewer 要求先修正 ONLINE strategy 顯示，應先做 P63 row-count integration 再 merge
- 目前無 blocker 阻止 PR 開啟本身

---

## 9. Remaining Risks

| Risk | 嚴重度 | 說明 |
|---|---|---|
| ONLINE strategy 在 lifecycle registry 顯示 UNKNOWN | 中 | hardcoded `total_rows=0`，已知 MVP 限制 |
| `/api/replay/strategy-lifecycle` 在 live server 404 | 低 | 環境問題，running server 版本較舊；merge 後解決 |
| `fixture_mode/fixture_only` fields 不在 API response | 低 | FIXTURE_ONLY badge 不觸發，安全 |
| REPLAY_ERROR 無測試記錄 | 低 | 目前 DB 無 REPLAY_ERROR 數據，badge 邏輯正確但未 live 驗證 |
| REGENERATED_RETROSPECTIVE 未來可能被誤接 | 低 | 目前 derive fn 不返回此值，明確 placeholder |

---

## 10. No-Write Verification

| 項目 | 結果 |
|---|---|
| `lottery_api/data/lottery_v2.db` 是否被寫入 | 否 |
| `lottery_api/models/replay_strategy_registry.py` 是否被修改 | 否 |
| DB migration 是否執行 | 否 |
| Backfill 是否執行 | 否 |
| Strategy adapter 是否執行 | 否 |
| git staged 包含 DB/registry/adapter | 否 |

---

## 11. Final Markers

- `P62_BASELINE_VERIFIED` ✓
- `P62_DIFF_SCOPE_VERIFIED` ✓
- `P62_STATIC_VERIFICATION_COMPLETE` ✓
- `P62_BROWSER_SMOKE_REPORTED` ✓ (DOM 15/15 PASS, API partial)
- `P62_ROW_COUNT_AUDIT_COMPLETE` ✓
- `P62_P61_PR_READINESS_DECIDED` ✓ (建議開 PR，暫緩 merge)
- `P62_DB_UNCHANGED` ✓ (hash: `de0e27bb800bc7183773a0dc596d66b8`)
- `P62_REGISTRY_UNCHANGED` ✓ (hash: `3ea71cfc20c882714f3824ad68202f6e`)
- `P62_NO_DB_WRITE_VERIFIED` ✓
- `P62_REPORT_CREATED` ✓

---

## 12. Safety Invariant Summary

```
DB hash:       de0e27bb800bc7183773a0dc596d66b8  [UNCHANGED]
Registry hash: 3ea71cfc20c882714f3824ad68202f6e  [UNCHANGED]
Staged files:  (none)
DB in diff:    (none)
Registry in diff: (none)
Adapter in diff:  (none)
```

---

## 13. 下一輪 P63 Prompt

```
# P63: Row Count Integration + ONLINE Strategy LIVE Badge Fix

## CONTEXT
P61 truth-level badge MVP 已 merge/PR ready。
已知 MVP 限制：lifecycle registry table 中 ONLINE 策略顯示 UNKNOWN（hardcoded total_rows=0）。

P62 audit 確認：
- /api/replay/summary?lottery_type=BIG_LOTTO 返回 per-strategy total_rows（70 each）
- /api/replay/strategy-lifecycle 返回 lifecycle metadata（in-memory, no DB）
- frontend 只需 fetch summary + join，不需新 backend endpoint

## MISSION
P63: 實作 lifecycle registry truth-level row-count integration。
在 deriveTruthLevelForStrategy 調用前，先 fetch /api/replay/summary per lottery type，
建立 strategyId → total_rows 映射，讓 ONLINE 策略正確顯示 LIVE badge。

## STRICT RULES
- 不寫 production DB
- 不修改 lottery_api/data/lottery_v2.db
- 不做 DB migration
- 不執行 backfill
- 不執行 strategy adapter
- 不修改 registry
- 只修改 index.html（rpRenderLifecycleRegistry 相關邏輯）
- 使用 /Users/kelvin/Kelvin-WorkSpace/LotteryNew-clean

## SCOPE
修改目標：
1. 在 rpRenderLifecycleRegistryTable 初始化時，parallel fetch /api/replay/summary
   for each supported lottery type
2. 建立 strategyId → { total_rows } map
3. 傳入 deriveTruthLevelForStrategy(s, rowCounts) 
4. 移除 TODO comment，改為實際 row count

## VERIFICATION
- ONLINE 策略在 lifecycle registry table 顯示 LIVE（rp-truth-production）
- REJECTED/OBSERVATION 仍顯示 METADATA ONLY
- RETIRED/!exec 仍顯示 NO HISTORY
- DB hash 不變
- Registry hash 不變
- No new backend endpoint required

## PR SCOPE
此 P63 change 可 amend 到 P61 branch，或作為新 commit。
建議：新 commit "frontend(replay/p63): integrate row counts for lifecycle truth level"
```

---

## Artifact Path

```
outputs/replay/p62_p61_pr_readiness_and_ui_verification_20260512.md
```

---

*P62 完成。P61 PR Readiness: RECOMMENDED. Merge: PENDING REVIEW.*
