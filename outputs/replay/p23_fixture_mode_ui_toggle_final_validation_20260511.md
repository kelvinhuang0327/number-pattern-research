# P23 Fixture Mode UI Toggle Button — Final Validation Report

**Version:** P23-FINAL-v1  
**Date:** 2026-05-11 (validation) / 2026-05-12 (report)  
**main HEAD:** `7d80a03 feat(replay): add fixture mode ui toggle (#63)`  
**Status:** FINAL VALIDATION PASS  
**Prepared By:** PR #63 Merge Gatekeeper + P23 Final Validation Agent  
**Report To:** CTO → CEO  
**Spec Reference:** `outputs/replay/p23_fixture_mode_ui_toggle_button_spec_20260511.md`  
**Implementation Reference:** `outputs/replay/p23_fixture_mode_ui_toggle_implementation_report_20260511.md`

---

## 1. 本輪目標

| 目標 | 狀態 |
|---|---|
| PR #63 收到 explicit YES gate | ✅ YES received |
| PR #63 squash merge 到 main | ✅ DONE — commit `7d80a03` |
| 從最新 main 執行 P23 final validation | ✅ ALL PASS |
| UI toggle contracts 全部成立 | ✅ 15/15 PASS |
| Forbidden diff checks | ✅ 2/2 PASS |
| 94/94 tests PASS | ✅ DONE |
| data/lottery_v2.db final clean | ✅ CLEAN (restored) |
| final validation docs PR 只開不 merge | ✅ OPEN |

---

## 2. PR #63 Merge 結果

| 項目 | 值 |
|---|---|
| PR #63 狀態 | MERGED |
| merge commit | `7d80a03c4b219b16e9ac170f25adcde6f0cb4a31` |
| mergedAt | 2026-05-11T23:48:31Z |
| Branch deleted | ✅ `feature/p23-fixture-mode-ui-toggle-20260511` |
| main HEAD after merge | `7d80a03 feat(replay): add fixture mode ui toggle (#63)` |
| 3 files merged | `index.html`, `tests/test_replay_browser_smoke.py`, `outputs/replay/p23_fixture_mode_ui_toggle_implementation_report_20260511.md` |

---

## 3. P23 UI Toggle 行為摘要

Fixture Mode toggle button 已嵌入 replay dashboard filter bar，緊接查詢按鈕群組之後：

- **ID**: `rp-fixture-toggle`
- **data-testid**: `rp-fixture-toggle`
- **aria-label**: `Fixture Mode toggle`
- **aria-pressed**: `false`（OFF 時）/ `true`（ON 時）
- **label text**: `Fixture Mode`

---

## 4. Toggle OFF 行為（預設）

| 屬性 | 值 |
|---|---|
| 按鈕文字 | `⬜ Fixture Mode OFF` |
| 按鈕樣式 | 白底紅字（`background:#fff; color:#c0392b`） |
| aria-pressed | `false` |
| FIXTURE MODE banner | 不顯示 |
| API query | 不帶 `fixture_mode=true` |
| URL | `rp_fixture_mode` 不存在 |

---

## 5. Toggle ON 行為

| 屬性 | 值 |
|---|---|
| 按鈕文字 | `✅ Fixture Mode ON` |
| 按鈕樣式 | 紅底白字（`background:#c0392b; color:#fff`） |
| aria-pressed | `true` |
| FIXTURE MODE banner | 顯示（`⚠ FIXTURE MODE — 合成資料、僅供驗收，不代表真實預測`） |
| API query | 帶 `fixture_mode=true` |
| URL | `?...&rp_fixture_mode=true` |

---

## 6. URL State 行為

| 操作 | URL state |
|---|---|
| 預設（OFF） | `rp_fixture_mode` 不存在 |
| 點擊 toggle ON | `?...&rp_fixture_mode=true` 加入 |
| 再次點擊（OFF） | `rp_fixture_mode` 從 URL 移除（`params.delete`） |
| 頁面載入帶 `rp_fixture_mode=true` | toggle 自動顯示 ON（`rpRestoreFromURL` + `rpSyncFixtureModeToggle`） |

---

## 7. API Query 行為

| 情況 | API request |
|---|---|
| Toggle OFF | `GET /api/replay/history?...`（不帶 `fixture_mode`） |
| Toggle ON | `GET /api/replay/history?...&fixture_mode=true` |
| fixture mode response | `advisory_only=true`, `source=synthetic_fixture`, `fixture_mode=true` |
| counts（fixture ON） | `REJECTED=4 / RETIRED=5 / OBSERVATION=1 / ONLINE=0` |

---

## 8. FIXTURE MODE Banner 行為

| 狀態 | Banner |
|---|---|
| Toggle OFF | `display:none`（不顯示） |
| Toggle ON | 顯示，文字：`⚠ FIXTURE MODE — 合成資料、僅供驗收，不代表真實預測` |

Banner element `id="rp-fixture-banner"` 為既有元件，P23 不改其 DOM 結構，只透過 `rpSetFixtureModeBanner()` 控制顯示狀態。

---

## 9. 測試結果

### 9.1 全套測試（從最新 main）

| Test Suite | Tests | Result |
|---|---|---|
| `test_replay_browser_smoke.py` | 50 tests (34 原有 + 16 P23) | **94/94 PASS** ✅ |
| `test_replay_api_contract.py` | 44 tests | **PASS** ✅ |
| **合計** | **94 tests** | **94/94 PASS** ✅ |

### 9.2 UI Contract Checks（靜態驗證）

| Check | Result |
|---|---|
| toggle_control_exists | ✅ PASS |
| label_contains_fixture_mode | ✅ PASS |
| tooltip_synthetic_only | ✅ PASS |
| tooltip_advisory_only | ✅ PASS |
| tooltip_no_production_db_write | ✅ PASS |
| tooltip_not_production_replay_outcome | ✅ PASS |
| rp_fixture_mode_url_state | ✅ PASS |
| fixture_mode_true_query | ✅ PASS |
| fixture_mode_banner_text | ✅ PASS |
| default_state_off | ✅ PASS |
| toggle_on_calls_fixture_path | ✅ PASS |
| toggle_off_removes_fixture_url | ✅ PASS |
| rpToggleFixtureMode_exists | ✅ PASS |
| rpSyncFixtureModeToggle_exists | ✅ PASS |
| sync_wired_in_domcontentloaded | ✅ PASS |

### 9.3 Forbidden Diff Checks

| Check | Result |
|---|---|
| no_new_offline_filter (in toggle body) | ✅ PASS |
| no_registry_modification (in toggle body) | ✅ PASS |

### 9.4 data/lottery_v2.db

| Check | Result |
|---|---|
| DB dirty after tests | ⚠ YES (pytest opened API connections) |
| DB restored via `git checkout HEAD` | ✅ DONE |
| DB final status | ✅ CLEAN |

---

## 10. Safety Invariants

| Invariant | Status |
|---|---|
| Production DB write | **NO** ✅ |
| Registry modified | **NO** ✅ |
| Lifecycle taxonomy changed | **NO** ✅ — 4 states locked: ONLINE / OBSERVATION / REJECTED / RETIRED |
| Backend API behavior changed | **NO** ✅ — beyond already-merged fixture mode bridge |
| OFFLINE filter added | **NO** ✅ |
| OFFLINE fixture rows added | **NO** ✅ |
| Fixture artifact modified | **NO** ✅ |
| data/lottery_v2.db final clean | **YES** ✅ (restored) |
| Branch protection changed | **NO** ✅ |
| Scheduler / cron added | **NO** ✅ |
| Strategy mining / edge discovery | **NO** ✅ |
| Production DB backfill | **NO** ✅ |
| Strategy promotion / retire action | **NO** ✅ |

---

## 11. 尚未完成事項

| Item | 說明 |
|---|---|
| Production Replay Backfill Decision Memo | 仍 defer；需獨立 CTO YES gate |
| User-facing screenshot walkthrough | 未做（無 browser 自動化） |
| Future OFFLINE prerequisites | 7 prerequisites 均未達成 |
| Strategy mining / edge discovery | 明確 defer |

---

## 12. 下一步建議

| Priority | 選項 | 說明 |
|---|---|---|
| **P1** | Post-merge browser validation | 在真實 browser 中點擊 toggle，確認 ON/OFF 視覺與 API query 切換正常 |
| **P2** | Production Replay Backfill Decision Memo | 需獨立 CTO YES gate；確認 backfill scope 與安全邊界 |
| **P3** | User-facing screenshot walkthrough | CTO/CEO demo：toggle ON → banner → API 切換 fixture data |
| **Defer** | OFFLINE introduction | 7 prerequisites 均未達成 |
| **Defer** | Strategy mining / edge discovery | 本 epic 範圍外 |

---

## Governance Markers

```
P23_FIXTURE_MODE_UI_TOGGLE_SPEC_PR62_MERGED_TO_MAIN
P23_FIXTURE_MODE_UI_TOGGLE_IMPLEMENTED
P23_FIXTURE_MODE_UI_TOGGLE_TESTS_PASS
P23_FIXTURE_MODE_UI_TOGGLE_PR63_MERGED_TO_MAIN
P23_FIXTURE_MODE_UI_TOGGLE_FINAL_VALIDATION_PASS
P23_FIXTURE_MODE_UI_TOGGLE_FINAL_DB_CLEAN
LIFECYCLE_TAXONOMY_UNCHANGED   — 4 formal states: ONLINE / OBSERVATION / REJECTED / RETIRED
OFFLINE_NOT_INTRODUCED         — OFFLINE never added to fixture mode
PRODUCTION_DB_UNTOUCHED        — no write, no backfill, no registry change
```
