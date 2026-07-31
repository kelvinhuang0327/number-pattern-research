# P23 Fixture Mode UI Toggle Button — Planning Spec

**Version:** P23-SPEC-v1  
**Date:** 2026-05-11  
**Status:** SPEC ONLY — NOT IMPLEMENTED  
**Prepared By:** PR #61 Merge Gatekeeper + P23 Planning Agent  
**Report To:** CTO → CEO  
**Governance Reference:** endpoint contract P11 (`docs/replay/strategy_lifecycle_endpoint_contract.md`)

---

## 1. 本輪目標

| 目標 | 說明 |
|---|---|
| 本輪只做 spec | **不做 implementation**；不寫 code |
| 規劃 UI toggle button | 讓使用者不必手動改 URL query 啟用 fixture mode |
| 限制為 pure UI change | 只控制 URL state 與既有 API call |
| 不變動任何後端邏輯 | 不新增 API behavior、不改 lifecycle state |

---

## 2. 現況

| 項目 | 目前狀態 |
|---|---|
| Fixture mode 啟用方式 | URL query: `rp_fixture_mode=true` |
| API 參數 | `GET /api/replay/strategy-lifecycle?fixture_mode=true` |
| UI | FIXTURE MODE banner（已存在，fixture mode 啟用時顯示） |
| Fixture mode 支援 lifecycle | REJECTED / RETIRED / OBSERVATION **only** |
| ONLINE | 不出現在 fixture mode |
| OFFLINE | **永不出現**（非正式 lifecycle state） |
| Toggle button | **尚未存在** |
| Default | `rp_fixture_mode=false`，production DB read path |

### 2.1 相關代碼位置（供 implementation 參考，本輪不動）

| 檔案 | 說明 |
|---|---|
| `index.html` | Replay dashboard UI；需加入 toggle button |
| `lottery_api/routes/replay.py` | Fixture mode API bridge（不改） |
| `outputs/replay/non_online_replay_fixture_20260511.json` | Fixture artifact（不改） |
| `docs/replay/strategy_lifecycle_endpoint_contract.md` | P11 contract（不改） |

---

## 3. UI Toggle 設計規格

### 3.1 Toggle 位置

- 在 replay dashboard lifecycle filter 區域附近（header 或 filter bar）
- 明確標示：**"Fixture Mode"**
- 預設：**OFF**

### 3.2 Toggle OFF（預設）

| 項目 | 行為 |
|---|---|
| URL state | `rp_fixture_mode` 不存在 或 `rp_fixture_mode=false` |
| API query | `fixture_mode=false`（或不帶此參數） |
| FIXTURE MODE banner | **不顯示** |
| Data source | Production DB read path（不變） |
| lifecycle counts | ONLINE / OBSERVATION / REJECTED / RETIRED（真實數據） |

### 3.3 Toggle ON

| 項目 | 行為 |
|---|---|
| URL state | `rp_fixture_mode=true` 加入 URL |
| API query | `fixture_mode=true` 帶入 API request |
| FIXTURE MODE banner | **必須顯示** |
| Data source | Synthetic fixture JSON |
| lifecycle counts | REJECTED=4 / RETIRED=5 / OBSERVATION=1 / ONLINE=0 |

### 3.4 Toggle 實作方式（建議）

```
// 切換時更新 URL state
const url = new URL(window.location.href);
if (isFixtureMode) {
  url.searchParams.set('rp_fixture_mode', 'true');
} else {
  url.searchParams.delete('rp_fixture_mode');
}
window.history.replaceState({}, '', url);

// API call 帶入參數
const fixtureParam = isFixtureMode ? '&fixture_mode=true' : '';
fetch(`/api/replay/strategy-lifecycle?...${fixtureParam}`)
```

> ⚠ 以上僅為 spec 建議，implementation PR 需通過 explicit YES gate。

---

## 4. Safety UX 規格

### 4.1 必要警告（Toggle ON 時）

Toggle 啟用時，**必須**同時顯示：

```
⚠ FIXTURE MODE — 合成資料、僅供驗收，不代表真實預測
```

英文版（同時顯示）：

```
⚠ FIXTURE MODE — Synthetic data. Advisory only. Not a production replay outcome.
```

### 4.2 Toggle Label / Tooltip 規格

| 元素 | 必要內容 |
|---|---|
| Toggle label | "Fixture Mode" |
| Tooltip（hover） | "Enable synthetic fixture data (advisory only, no production DB write)" |
| Banner（ON 時） | "⚠ FIXTURE MODE — Synthetic data. Advisory only. Not a production replay outcome." |
| Banner 顏色 | 警示色（amber / orange），不得用綠色或成功色 |

### 4.3 防止誤讀規則

- **不得**讓 toggle 看起來像「切換 production filter」
- **不得**移除或弱化 FIXTURE MODE banner
- **不得**在 toggle ON 時顯示帶有「預測通過」或「推薦」字樣的 UI

---

## 5. Allowed Scope（本輪實作時適用）

| 允許 | 說明 |
|---|---|
| ✅ 新增 toggle button HTML/CSS/JS | 在 index.html replay section |
| ✅ 修改 URL query state | `rp_fixture_mode=true/false` |
| ✅ 調用既有 API | `fixture_mode=true/false` |
| ✅ 顯示 / 隱藏 FIXTURE MODE banner | 依 toggle state |
| ✅ lifecycle filter 顯示 REJECTED / RETIRED / OBSERVATION | fixture mode ON 時 |
| ✅ 新增 toggle 相關 browser smoke tests | 驗收用 |

---

## 6. Not In Scope（嚴格禁止）

| 禁止 | 說明 |
|---|---|
| ❌ Production DB 寫入 | 不寫 data/lottery_v2.db |
| ❌ Registry 修改 | 不改 strategy registry |
| ❌ Lifecycle taxonomy 修改 | 4 formal states 已鎖定 |
| ❌ 新增 OFFLINE filter | OFFLINE 非正式 lifecycle state |
| ❌ 新增 OFFLINE fixture records | fixture 永不包含 OFFLINE |
| ❌ Production DB backfill | 未評估風險，需獨立 YES gate |
| ❌ Strategy promotion / retire action | 不觸碰 strategy state |
| ❌ Scheduler / cron 新增 | 不新增 background job |
| ❌ Strategy mining / edge discovery | 不啟動 |
| ❌ Branch protection 修改 | 不動 GitHub repo 設定 |
| ❌ 新增 API behavior | 只使用既有 fixture_mode=true endpoint |
| ❌ 修改 lifecycle endpoint contract | P11 已鎖定 |

---

## 7. Acceptance Criteria

| # | 驗收條件 | 期望結果 |
|---|---|---|
| AC-1 | 預設狀態 Toggle OFF | 既有行為不變；rp_fixture_mode 不在 URL |
| AC-2 | Toggle ON 後 URL 狀態 | `rp_fixture_mode=true` 出現在 URL |
| AC-3 | Toggle ON 後 API request | API request 帶 `fixture_mode=true` |
| AC-4 | Toggle ON 後 Banner | FIXTURE MODE banner **可見** |
| AC-5 | Toggle ON 後 Records | REJECTED / RETIRED / OBSERVATION 可見 |
| AC-6 | Toggle ON — ONLINE records | **不出現**（fixture 不含 ONLINE） |
| AC-7 | Toggle ON — OFFLINE records | **永不出現** |
| AC-8 | Toggle OFF 後 Banner | FIXTURE MODE banner **消失** |
| AC-9 | Toggle OFF 後 Records | 不回傳 synthetic_fixture；production path 恢復 |
| AC-10 | URL state 與 button state 一致 | 手動帶 `?rp_fixture_mode=true` 時 button 也要 ON |
| AC-11 | data/lottery_v2.db | **final clean** — no dirty state |
| AC-12 | Registry | **no change** |
| AC-13 | 警告文字 | Toggle ON 時警告文字可見 |
| AC-14 | Tooltip | Hover toggle 時顯示 advisory-only 說明 |

---

## 8. Test Plan

### 8.1 Browser Smoke Tests（新增）

| Test ID | Description |
|---|---|
| T-P23-01 | 頁面載入後 toggle button 存在 |
| T-P23-02 | 預設 toggle 狀態為 OFF |
| T-P23-03 | 點擊 toggle ON → URL 含 `rp_fixture_mode=true` |
| T-P23-04 | Toggle ON → API request 含 `fixture_mode=true` |
| T-P23-05 | Toggle ON → FIXTURE MODE banner 可見 |
| T-P23-06 | Toggle ON → REJECTED records 可見 |
| T-P23-07 | Toggle ON → RETIRED records 可見 |
| T-P23-08 | Toggle ON → OBSERVATION records 可見 |
| T-P23-09 | Toggle ON → ONLINE records 不出現 |
| T-P23-10 | Toggle OFF → banner 消失 |
| T-P23-11 | Toggle OFF → synthetic records 不出現 |
| T-P23-12 | 手動帶 `?rp_fixture_mode=true` → toggle 自動顯示 ON |
| T-P23-13 | 警告文字含 "advisory only" 或 "不代表真實預測" |
| T-P23-14 | Tooltip 含 "no production DB write" |

### 8.2 Static HTML Tests（新增）

| Test ID | Description |
|---|---|
| T-P23-S01 | Toggle button element 存在（id 或 data-testid） |
| T-P23-S02 | Toggle label 文字含 "Fixture Mode" |
| T-P23-S03 | Warning text element 存在 |
| T-P23-S04 | FIXTURE MODE banner element 存在 |

### 8.3 API Contract Reuse（既有，不改）

| Test | File |
|---|---|
| fixture_mode=true lifecycle counts | `tests/test_replay_api_contract.py` |
| fixture_mode=false unchanged | `tests/test_replay_api_contract.py` |

### 8.4 Regression Tests

| Test | 期望 |
|---|---|
| fixture_mode=false default behavior | 完全不變 |
| production DB read path | 不受 toggle 影響 |
| ONLINE records in production mode | 不受影響 |

### 8.5 Final DB Clean Check

```bash
git checkout HEAD -- data/lottery_v2.db 2>/dev/null || true
git status --short data/lottery_v2.db
# Expected: no output (CLEAN)
```

---

## 9. Risks

| Risk | 說明 | Mitigation |
|---|---|---|
| Fixture mode 誤讀 | Toggle 太容易啟用，使用者可能誤以為是 production filter | 強制顯示 warning banner；tooltip 說明 |
| URL state 與 button state 不一致 | 手動修改 URL 後 button 狀態未同步 | AC-10 驗收條件；初始化時讀取 URL state |
| Lifecycle filter 切換後遺失 fixture mode state | 切換 lifecycle filter 重新 fetch 時忘記帶 fixture_mode | API call 邏輯統一管理 fixture_mode param |
| 使用者截圖時忽略 banner | 截圖後分享，收到方看不到 banner 語境 | Banner 顏色明顯；always visible in viewport |
| 頁面 refresh 後 toggle 狀態遺失 | 若 URL state 沒有持久化 | 使用 URL query string 持久化（replaceState） |

---

## 10. CTO Recommendation

| 建議 | 說明 |
|---|---|
| ✅ **可做 P23 implementation** | 純 UI + 既有 API call；低風險 |
| ⚠ Implementation PR 仍需 **explicit YES gate** | 本輪只做 spec；code 需下一輪確認 |
| ✅ Test plan 已完整 | 14 browser smoke + 4 static + regression |
| ❌ Production backfill decision memo | 仍 defer；需獨立 CTO YES gate |
| ❌ OFFLINE filter / OFFLINE fixture records | 永不加入 |

---

## Governance Markers

```
P23_FIXTURE_MODE_UI_TOGGLE_SPEC_READY
LIFECYCLE_TAXONOMY_UNCHANGED   — 4 formal states: ONLINE / OBSERVATION / REJECTED / RETIRED
OFFLINE_DEFERRED               — OFFLINE not introduced in P23 scope
PRODUCTION_DB_UNTOUCHED        — no write, no backfill, no registry change
```

---

## Related Files

| 檔案 | 說明 |
|---|---|
| `docs/replay/strategy_lifecycle_endpoint_contract.md` | P11 endpoint contract（不改） |
| `outputs/replay/non_online_replay_fixture_20260511.json` | Fixture artifact（不改） |
| `outputs/replay/replay_lifecycle_taxonomy_update_20260511.md` | Taxonomy lock（不改） |
| `outputs/replay/offline_classification_decision_memo_20260511.md` | OFFLINE decision Route B（不改） |
| `lottery_api/routes/replay.py` | API bridge（不改） |
| `index.html` | 下一輪 implementation target |
| `tests/test_replay_browser_smoke.py` | 下一輪新增 T-P23-xx tests |
