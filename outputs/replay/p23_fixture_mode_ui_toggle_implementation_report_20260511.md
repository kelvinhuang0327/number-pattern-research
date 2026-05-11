# P23 Fixture Mode UI Toggle Button — Implementation Report

**Version:** P23-IMPL-v1  
**Date:** 2026-05-11  
**Branch:** `feature/p23-fixture-mode-ui-toggle-20260511`  
**Status:** IMPLEMENTED — TESTS PASS — PR OPEN (NOT MERGED)  
**Prepared By:** PR #62 Merge Gatekeeper + P23 Implementation Agent  
**Report To:** CTO → CEO  
**Spec Reference:** `outputs/replay/p23_fixture_mode_ui_toggle_button_spec_20260511.md`

---

## 1. 本輪目標

| 目標 | 狀態 |
|---|---|
| PR #62 (P23 spec) squash merge 到 main | ✅ DONE |
| 在 replay dashboard 加入 Fixture Mode UI Toggle Button | ✅ DONE |
| 新增 P23 static tests (16 tests) | ✅ DONE — 94/94 PASS |
| data/lottery_v2.db 全程不寫入 | ✅ CLEAN |
| implementation PR 只開不 merge | ✅ DONE |

---

## 2. PR #62 Merge 結果

| 項目 | 值 |
|---|---|
| PR #62 狀態 | MERGED |
| merge commit | `e86c860` |
| mergedAt | 2026-05-11T15:07:34Z |
| Branch deleted | ✅ |
| main HEAD after merge | `e86c860 docs(replay): specify fixture mode ui toggle (#62)` |

---

## 3. Implementation 摘要

### 3.1 新增 HTML（`index.html`）

在 replay dashboard filter bar 的查詢按鈕群組後新增 Fixture Mode toggle button：

```html
<div style="display:flex;flex-direction:column;align-items:flex-start;gap:2px">
  <label style="font-size:11px;color:#888;margin-bottom:2px" for="rp-fixture-toggle">
    Fixture Mode
  </label>
  <button
    id="rp-fixture-toggle"
    data-testid="rp-fixture-toggle"
    title="啟用合成資料模式 (synthetic only / advisory only / no production DB write / not production replay outcome)"
    aria-label="Fixture Mode toggle"
    aria-pressed="false"
    style="padding:5px 14px;border-radius:4px;border:1px solid #c0392b;background:#fff;color:#c0392b;font-size:12px;font-weight:700;cursor:pointer;transition:background .15s,color .15s"
  >⬜ Fixture Mode OFF</button>
</div>
```

### 3.2 新增 JS 函數（`index.html`）

**`rpSyncFixtureModeToggle()`**
- Toggle ON → 按鈕文字 `✅ Fixture Mode ON`，紅底白字
- Toggle OFF → 按鈕文字 `⬜ Fixture Mode OFF`，白底紅字
- 同步 `aria-pressed` 屬性

**`rpToggleFixtureMode()`**
- 翻轉 `rpFixtureMode` 狀態
- 呼叫 `rpSyncFixtureModeToggle()` 更新按鈕視覺
- 呼叫 `rpSetFixtureModeBanner(rpFixtureMode)` 顯示/隱藏 banner
- 同步 URL state（`rp_fixture_mode=true` / 移除）

### 3.3 DOMContentLoaded 事件綁定

```js
const fixtureToggleBtn = document.getElementById('rp-fixture-toggle');
if (fixtureToggleBtn) {
  fixtureToggleBtn.addEventListener('click', rpToggleFixtureMode);
}
// ...
rpRestoreFromURL();
// P23: sync toggle visual state after URL restore
rpSyncFixtureModeToggle();
```

---

## 4. 修改檔案

| 檔案 | 修改類型 | 說明 |
|---|---|---|
| `index.html` | UI + JS | 新增 toggle button HTML；新增 `rpSyncFixtureModeToggle`、`rpToggleFixtureMode` 函數；事件綁定；init 呼叫 |
| `tests/test_replay_browser_smoke.py` | Tests | 新增 `TestP23FixtureModeToggle` class，16 個 static tests |

**未修改：**
- `lottery_api/routes/replay.py` — 不改
- `outputs/replay/non_online_replay_fixture_20260511.json` — 不改
- `docs/replay/strategy_lifecycle_endpoint_contract.md` — 不改
- `data/lottery_v2.db` — 不改
- Registry — 不改

---

## 5. Toggle ON/OFF 行為

| 狀態 | 按鈕文字 | 按鈕樣式 | banner | API query |
|---|---|---|---|---|
| **OFF（預設）** | `⬜ Fixture Mode OFF` | 白底紅字 | 不顯示 | 不帶 `fixture_mode=true` |
| **ON** | `✅ Fixture Mode ON` | 紅底白字 | 顯示 `⚠ FIXTURE MODE — 合成資料、僅供驗收，不代表真實預測` | 帶 `fixture_mode=true` |

---

## 6. URL State 行為

| 操作 | URL state |
|---|---|
| 預設（OFF） | `rp_fixture_mode` 不存在 |
| 點擊 toggle ON | `?...&rp_fixture_mode=true` 加入 URL |
| 再次點擊（OFF） | `rp_fixture_mode` 從 URL 移除 |
| 頁面載入時 URL 帶 `rp_fixture_mode=true` | toggle 自動顯示 ON（`rpRestoreFromURL` + `rpSyncFixtureModeToggle`）|

---

## 7. API Query 行為

| 情況 | API request |
|---|---|
| Toggle OFF | `GET /api/replay/history?...` （不帶 `fixture_mode`） |
| Toggle ON | `GET /api/replay/history?...&fixture_mode=true` |
| fixture mode response | `advisory_only=true`，`source=synthetic_fixture`，`fixture_mode=true` |
| counts（fixture ON） | `REJECTED=4 / RETIRED=5 / OBSERVATION=1 / ONLINE=0` |

---

## 8. Safety UX 行為

| 安全機制 | 實作狀態 |
|---|---|
| Toggle ON 時 banner 強制顯示 | ✅ |
| Banner 文字：`⚠ FIXTURE MODE — 合成資料、僅供驗收，不代表真實預測` | ✅ 既有 banner，不改 |
| Tooltip：`synthetic only / advisory only / no production DB write / not production replay outcome` | ✅ title attribute |
| aria-pressed 無障礙屬性 | ✅ |
| Toggle 不觸發 production DB write | ✅ 純 URL state + API query |

---

## 9. 測試結果

### 9.1 全套測試

| Test Suite | Tests | Result |
|---|---|---|
| `test_replay_browser_smoke.py` | 50 tests (34 原有 + 16 P23 新增) | **PASS** ✅ |
| `test_replay_api_contract.py` | 44 tests | **PASS** ✅ |
| **合計** | **94 tests** | **94/94 PASS** ✅ |

### 9.2 P23 新增測試明細（16 tests）

| Test ID | Description | Result |
|---|---|---|
| T-P23-S01 | toggle button element exists | ✅ PASS |
| T-P23-S02 | data-testid exists | ✅ PASS |
| T-P23-S03 | label contains "Fixture Mode" | ✅ PASS |
| T-P23-S04 | rp-fixture-banner element exists (regression) | ✅ PASS |
| T-P23-S05 | banner text advisory warning | ✅ PASS |
| T-P23-S06 | tooltip contains advisory | ✅ PASS |
| T-P23-S07 | aria-pressed exists | ✅ PASS |
| T-P23-S08 | rpToggleFixtureMode function exists | ✅ PASS |
| T-P23-S09 | rpSyncFixtureModeToggle function exists | ✅ PASS |
| T-P23-S10 | toggle wired in DOMContentLoaded | ✅ PASS |
| T-P23-S11 | sync called after rpRestoreFromURL | ✅ PASS |
| T-P23-S12 | rp_fixture_mode=true written to URL | ✅ PASS |
| T-P23-S13 | rp_fixture_mode deleted from URL on OFF | ✅ PASS |
| T-P23-S14 | fixture_mode=true passed to API (regression) | ✅ PASS |
| T-P23-S15 | no OFFLINE filter in toggle body | ✅ PASS |
| T-P23-S16 | no new fetch() in rpToggleFixtureMode | ✅ PASS |

### 9.3 API Contract Fixture Counts（regression）

| lifecycle | Count | Result |
|---|---|---|
| REJECTED | 4 | ✅ PASS |
| RETIRED | 5 | ✅ PASS |
| OBSERVATION | 1 | ✅ PASS |

---

## 10. Safety Invariants

| Invariant | Status |
|---|---|
| Production DB write | **NO** ✅ |
| Registry modified | **NO** ✅ |
| Lifecycle taxonomy changed | **NO** ✅ — 4 states locked: ONLINE / OBSERVATION / REJECTED / RETIRED |
| OFFLINE filter added | **NO** ✅ |
| OFFLINE fixture records added | **NO** ✅ |
| Fixture artifact modified | **NO** ✅ |
| New backend API behavior | **NO** ✅ |
| data/lottery_v2.db final clean | **YES** ✅ |
| Branch protection changed | **NO** ✅ |
| Scheduler / cron added | **NO** ✅ |
| Strategy mining | **NO** ✅ |

---

## 11. 尚未完成事項

| Item | 說明 |
|---|---|
| Implementation PR merge | PR #63 OPEN — 等待 explicit YES gate |
| Production Replay Backfill Decision Memo | 仍 defer；需獨立 CTO YES gate |
| Future OFFLINE prerequisites | 7 prerequisites 均未達成 |

---

## 12. 下一步建議

| Priority | 選項 | 說明 |
|---|---|---|
| **P1** | Merge PR #63 (P23 implementation) | 等待 explicit YES gate |
| **P2** | Post-merge E2E browser validation | 確認 toggle 在真實 browser 中運作 |
| **P3** | Production Replay Backfill Decision Memo | 需獨立 CTO YES gate |
| **Defer** | OFFLINE introduction | 7 prerequisites 均未達成 |

---

## Governance Markers

```
P23_FIXTURE_MODE_UI_TOGGLE_SPEC_PR62_MERGED_TO_MAIN
P23_FIXTURE_MODE_UI_TOGGLE_IMPLEMENTED
P23_FIXTURE_MODE_UI_TOGGLE_TESTS_PASS
P23_FIXTURE_MODE_UI_TOGGLE_DB_CLEAN
LIFECYCLE_TAXONOMY_UNCHANGED   — 4 formal states: ONLINE / OBSERVATION / REJECTED / RETIRED
OFFLINE_NOT_INTRODUCED         — OFFLINE never added to fixture mode
PRODUCTION_DB_UNTOUCHED        — no write, no backfill, no registry change
```
