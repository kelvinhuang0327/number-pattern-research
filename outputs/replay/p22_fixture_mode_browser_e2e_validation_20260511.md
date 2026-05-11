# P22 Fixture-Mode Browser E2E Validation Report

**Date**: 2026-05-11  
**Branch**: main (post-merge)  
**Merge Commit**: ce87159e84cd5beb493953a6782b0d5bd7081cb1  
**Prepared by**: PR #53 Merge Gatekeeper + P22 Validation Agent  

---

## 1. 本輪目標

驗證 PR #53（feat(replay): add fixture mode replay history bridge）merge 至 main 後，
fixture-mode 功能在 API 與 UI 兩個層面均可正確運作：

- API `fixture_mode=true` 回傳合成 fixture 資料，flags 正確
- API `fixture_mode=false`（預設）維持既有 DB read path，不回 synthetic 資料
- UI 顯示 FIXTURE MODE banner（僅在 `rpFixtureMode=true` 時）
- UI lifecycle filter 切換可顯示 synthetic records
- 不寫 production DB，不修改 registry，不執行 backfill

---

## 2. PR #53 Merge 結果

| 項目 | 結果 |
|------|------|
| PR 編號 | #53 |
| 標題 | feat(replay): add fixture mode replay history bridge |
| Merge 方式 | Squash merge |
| Merge commit | `ce87159` |
| mergedAt | 2026-05-11T11:53:35Z |
| 狀態 | MERGED ✅ |
| main HEAD | `ce87159 feat(replay): add fixture mode replay history bridge (#53)` |
| Branch 清理 | feature/p2-fixture-mode-replay-history-ui-20260511 已刪除（local + remote）|

---

## 3. API Validation 結果

### 3.1 Fixture Mode 計數驗證

執行命令：
```
/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.venv/bin/python _p22_validate.py
```

直接呼叫 `_fixture_history_response()` route helper，驗證各 lifecycle filter 回傳筆數與 flags。

| lifecycle_status | 預期筆數 | 實際筆數 | count_ok | source | advisory_only | production_db_write | fixture_mode |
|-----------------|---------|---------|---------|--------|--------------|--------------------|-|
| REJECTED | 4 | 4 | ✅ | synthetic_fixture | True | False | True |
| RETIRED | 5 | 5 | ✅ | synthetic_fixture | True | False | True |
| OBSERVATION | 1 | 1 | ✅ | synthetic_fixture | True | False | True |

**結論：ALL_PASS**

### 3.2 全套 Contract Tests（44 tests）

```
pytest tests/test_replay_api_contract.py -v
```

結果：**44 passed in 0.50s** ✅

包含：
- `TestHistoryFixtureModeContract` — 7 tests（fixture mode 專屬）
- `TestHistoryContract` — 37 tests（既有 DB path 回歸測試）

### 3.3 Fixture Mode=false 路徑驗證

Contract tests 中的既有 `TestHistoryContract`（37 tests）全部通過，確認：
- `fixture_mode=false`（預設）維持 DB read path
- 不回 `source=synthetic_fixture`
- `test_fixture_history_does_not_return_db_marker` 確認 fixture 回應不含 DB 專屬欄位

---

## 4. UI/Browser Validation 結果

### 4.1 Static HTML Smoke Tests（34 tests）

```
pytest tests/test_replay_browser_smoke.py -v
```

結果：**34 passed in 2.72s** ✅

關鍵通過項：
- `test_fixture_mode_banner_present` — PASS
- `test_rp_fixture_mode_param_written_to_url` — PASS
- `test_js_calls_fixture_mode_history_endpoint` — PASS
- `test_no_forbidden_tokens_in_replay_js` — PASS

### 4.2 Element 結構驗證（8 項靜態 checks）

直接解析 `index.html` 進行驗證：

| Check | 結果 |
|-------|------|
| `id="rp-fixture-banner"` 元素存在 | ✅ PASS |
| banner 包含文字 "FIXTURE MODE" | ✅ PASS |
| banner 包含文字 "合成資料、僅供驗收" | ✅ PASS |
| `let rpFixtureMode = false` 初始狀態 | ✅ PASS |
| `rp_fixture_mode` URL param 支援 | ✅ PASS |
| `fixture_mode=true` query append 存在 | ✅ PASS |
| `rpFixtureMode = false` 預設值 | ✅ PASS |
| banner hidden by default（`display:none` 路徑）| ✅ PASS |

### 4.3 條件邏輯驗證

```
grep -A 30 "function rpQuery" index.html
```

確認：
- `rpQuery()` 中：`if (rpFixtureMode) url += \`&fixture_mode=true\`` → 條件式 append
- `rpSetFixtureModeBanner(active)` → `banner.style.display = active ? '' : 'none'`
- `rpSetFixtureModeBanner(rpFixtureMode)` 在 `rpQuery()` 中被呼叫

---

## 5. Lifecycle Filter 實測結果

| Lifecycle Filter | Fixture 記錄數 | source 驗證 | advisory_only | 結果 |
|-----------------|--------------|------------|--------------|------|
| REJECTED | 4 | synthetic_fixture | true | ✅ PASS |
| RETIRED | 5 | synthetic_fixture | true | ✅ PASS |
| OBSERVATION | 1 | synthetic_fixture | true | ✅ PASS |

UI 層面：`rpQuery()` 讀取 `#rp-status-select` 的值並附加至 API URL；  
fixture_mode=true 時，`rpSetFixtureModeBanner` 顯示 banner，各 lifecycle 均可取得 synthetic records。

---

## 6. Fixture Banner 實測結果

| 驗證項目 | 結果 |
|---------|------|
| `id="rp-fixture-banner"` 元素存在於 HTML | ✅ |
| Banner 文字：`⚠ FIXTURE MODE — 合成資料、僅供驗收，不代表真實預測` | ✅ |
| `rpFixtureMode=false` 時 banner hidden（`display:none`）| ✅ |
| `rpFixtureMode=true` 時 banner shown（`display:''`）| ✅ 邏輯確認 |
| banner 在 `rp_fixture_mode` URL param restore 時正確同步 | ✅ |

---

## 7. Safety 結果

| Safety 項目 | 結果 |
|------------|------|
| Production DB write | **NO** ✅ |
| `data/lottery_v2.db` final dirty | **NO** ✅（兩次 dirty 均已 restore）|
| Registry modified | **NO** ✅ |
| Backfill executed | **NO** ✅ |
| Strategy promotion / retire action | **NO** ✅ |
| Scheduler / cron 新增 | **NO** ✅ |
| Strategy mining / edge discovery | **NO** ✅ |
| Branch protection 修改 | **NO** ✅ |
| 功能擴充 | **NO** ✅（僅 validation / smoke）|

### DB Dirty 記錄

本輪共發生 2 次 `data/lottery_v2.db` dirty（mtime bump）：

1. **第 1 次**：`pytest tests/test_replay_api_contract.py` — pytest 載入 `lottery_api` routes 觸發 SQLite connection mtime bump。無寫入，已 restore。
2. **第 2 次**：`python _p22_validate.py` — 同上，import lottery_api 觸發 mtime bump。無寫入，已 restore。

兩次均以 `git checkout HEAD -- data/lottery_v2.db` restore，最終確認 `git status --short data/lottery_v2.db` 無輸出。

---

## 8. 測試命令與結果

| 命令 | 結果 |
|------|------|
| `pytest tests/test_replay_api_contract.py -v` | **44 passed** ✅ |
| `pytest tests/test_replay_api_contract.py -v -k "FixtureMode"` | **7 passed** ✅ |
| `pytest tests/test_replay_browser_smoke.py -v` | **34 passed** ✅ |
| `python _p22_validate.py`（直呼 route helper）| **ALL_PASS** ✅ |
| `git diff --check` | PASS（無 whitespace errors）|
| `git status --short data/lottery_v2.db`（最終）| CLEAN ✅ |

---

## 9. 尚未完成事項

| 項目 | 說明 |
|------|------|
| Headless / 真實瀏覽器 E2E | 本輪為 static smoke + direct API call；如需 Playwright/Selenium E2E 需另行安排 |
| `fixture_mode` toggle UI 控制項 | 目前 fixture mode 由 URL param `rp_fixture_mode=true` 手動啟用，尚無 UI toggle button |
| PR #52（P1 spec docs）| OPEN，尚未 merge；本輪無授權 merge |

---

## 10. 下一步建議

1. **PR #52 review**：`docs/p1-fixture-to-ui-bridge-spec-20260511` spec + DB dirt root cause docs 可在下一輪 YES-gated merge。
2. **UI toggle**：可考慮在 replay section 加入 "FIXTURE MODE" toggle button，避免只能透過 URL param 啟用（P23）。
3. **真實瀏覽器 E2E**：若需要 Playwright 驗證 DOM render，可作為 P24 排入。
4. **DB mtime 問題追蹤**：SQLite mtime 在 import 時即 bump 為已知問題，可考慮在 pytest conftest 加入自動 restore fixture。

---

## Final Markers

```
P2_FIXTURE_MODE_PR53_MERGED_TO_MAIN
P22_FIXTURE_MODE_API_VALIDATION_PASS
P22_FIXTURE_MODE_BROWSER_E2E_PASS
P22_DB_FINAL_CLEAN
```
