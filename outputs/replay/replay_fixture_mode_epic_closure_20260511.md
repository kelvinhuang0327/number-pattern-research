# Replay Fixture-Mode Epic Closure Report

**Date**: 2026-05-11  
**Prepared by**: PR #54 Docs Merge Gatekeeper + Replay Fixture-Mode Epic Closure Agent  
**Scope**: PR #51 → PR #54（Replay Fixture-Mode Epic）

---

## 1. 本輪目標

合併 PR #54（docs-only），並總結 Replay Fixture-Mode Epic 從 PR #51 到 PR #54 的全程成果、
產品當前狀態、剩餘風險與下一步方向，供 CTO 與 CEO 決策參考。

---

## 2. 已 Merge PR 摘要

| PR | Commit | Title | 類型 | Merge 時間 |
|----|--------|-------|------|-----------|
| #51 | `7762118` | feat(replay): add isolated non-online replay fixture artifact generator | feat | 2026-05-11 |
| #53 | `ce87159` | feat(replay): add fixture mode replay history bridge | feat | 2026-05-11T11:53:35Z |
| #54 | `142dc45` | docs(replay): fixture mode browser e2e validation | docs | 2026-05-11T13:40:36Z |

### PR #51 — P21 Non-Online Fixture Artifact Generator

**目標**：為 non-ONLINE lifecycle（REJECTED / RETIRED / OBSERVATION）產生 synthetic fixture artifact，  
使其可被 dashboard replay section 讀取，而不需要 production DB backfill。

**交付內容**：
- `outputs/replay/non_online_replay_fixture_20260511.json`：10 筆 synthetic fixture 記錄
  - REJECTED: 4 筆
  - RETIRED: 5 筆
  - OBSERVATION: 1 筆
- 所有 fixture 記錄標記：`advisory_only=true`, `production_db_write=false`

**解決問題**：fixture rows 無法被 dashboard 讀取的根本阻塞（UI 看不到 non-ONLINE strategies）

---

### PR #53 — P2 Fixture-Mode Replay History Bridge

**目標**：在 FastAPI replay history API 新增 `fixture_mode` query param，  
使 UI 可透過 `?fixture_mode=true` 切換讀取 fixture artifact。

**交付內容**：
- `lottery_api/routes/replay.py`：
  - 新增 `fixture_mode: bool = Query(False)` 參數
  - `fixture_mode=true` 時呼叫 `_fixture_history_response()`，讀取 JSON artifact
  - `fixture_mode=false`（預設）維持既有 DB read path，完全不受影響
  - `source="synthetic_fixture"`, `advisory_only=True`, `production_db_write=False`, `fixture_mode=True`
- `index.html`：
  - 新增 `let rpFixtureMode = false` 狀態變數
  - 新增 `id="rp-fixture-banner"` 元素，顯示警告文字
  - `rpQuery()` 中條件式 append `&fixture_mode=true`
  - `rp_fixture_mode` URL param wiring（restore + update）
- `tests/test_replay_api_contract.py`：新增 `TestHistoryFixtureModeContract`（7 tests）
- `tests/test_replay_browser_smoke.py`：新增靜態 smoke checks

**解決問題**：fixture artifact 停留在 JSON、無法被 dashboard 驗收的橋接缺口

---

### PR #54 — P22 Fixture-Mode Browser E2E Validation Docs

**目標**：在 main 上執行 P22 validation，產出驗收報告並提交至 repo。

**交付內容**：
- `outputs/replay/p22_fixture_mode_browser_e2e_validation_20260511.md`：
  - API counts 驗證（REJECTED=4, RETIRED=5, OBSERVATION=1）
  - flags 驗證（source, advisory_only, production_db_write, fixture_mode）
  - UI element 靜態 checks（8 項全 PASS）
  - safety invariant 紀錄
  - DB dirty 原因與 restore 記錄

---

## 3. 產品狀態（Post-Epic）

### API 層

| 路徑 | fixture_mode | 行為 |
|------|-------------|------|
| `GET /api/replay/history` | `false`（預設）| 讀取 `data/lottery_v2.db`，既有 production path |
| `GET /api/replay/history?fixture_mode=true` | `true` | 讀取 `outputs/replay/non_online_replay_fixture_20260511.json` |

Fixture mode 回應欄位：
- `source = "synthetic_fixture"`
- `advisory_only = true`
- `production_db_write = false`
- `fixture_mode = true`

### UI 層

| 功能 | 狀態 |
|------|------|
| Fixture mode banner：`⚠ FIXTURE MODE — 合成資料、僅供驗收，不代表真實預測` | ✅ 實作並通過 smoke test |
| `rp_fixture_mode=true` URL param 啟用 fixture mode | ✅ |
| REJECTED lifecycle filter 顯示 4 筆 synthetic records | ✅ |
| RETIRED lifecycle filter 顯示 5 筆 synthetic records | ✅ |
| OBSERVATION lifecycle filter 顯示 1 筆 synthetic records | ✅ |
| `fixture_mode=false` 時 banner 隱藏，不回 synthetic 資料 | ✅ |

### Fixture Mode 啟用方式

目前只能透過 URL param 手動啟用：
```
?rp_fixture_mode=true
```
尚無 UI toggle button。

---

## 4. 驗證結果摘要

| 驗證項目 | 命令 | 結果 |
|---------|------|------|
| API fixture counts + flags | `python _p22_validate.py` | **PASS** ✅ |
| Contract tests（全套 44） | `pytest tests/test_replay_api_contract.py` | **44 passed** ✅ |
| Fixture mode contract（7） | `pytest -k FixtureMode` | **7 passed** ✅ |
| Browser smoke tests（34） | `pytest tests/test_replay_browser_smoke.py` | **34 passed** ✅ |
| UI element static checks（8） | 直接解析 `index.html` | **8/8 PASS** ✅ |
| `git diff --check` | whitespace check | **PASS** ✅ |
| `data/lottery_v2.db` final clean | `git status --short data/lottery_v2.db` | **CLEAN** ✅ |

---

## 5. Safety Invariant

| Safety 項目 | 結果 |
|------------|------|
| Production DB write | **NO** ✅ |
| Backfill executed | **NO** ✅ |
| Registry modified | **NO** ✅ |
| Strategy promotion | **NO** ✅ |
| Strategy retire action | **NO** ✅ |
| Scheduler / cron 新增 | **NO** ✅ |
| Strategy mining / edge discovery | **NO** ✅ |
| Branch protection 修改 | **NO** ✅ |

### DB Dirty 記錄

本 epic 週期中 `data/lottery_v2.db` 共發生 2 次 mtime dirty，均為 pytest / Python import
載入 `lottery_api` routes 時 SQLite connection mtime bump（無實際寫入），
均以 `git checkout HEAD -- data/lottery_v2.db` restore，最終 clean。

---

## 6. 已解除的阻塞

| 阻塞項目 | 解除方式 | 解除 PR |
|---------|---------|---------|
| UI 讀不到 non-ONLINE fixture rows | 產生 synthetic fixture JSON artifact（PR #51）| #51 |
| Fixture artifact 停留在 JSON、無法被 dashboard 驗收 | 新增 `fixture_mode` API bridge + UI banner（PR #53）| #53 |
| 無法驗收 fixture 功能是否正確運作 | P22 validation + docs commit（PR #54）| #54 |

---

## 7. 尚未完成事項

| 項目 | 說明 | 優先度建議 |
|------|------|-----------|
| Fixture mode 仍是 advisory-only | `advisory_only=true` 為設計意圖，非缺陷 | — |
| Production replay backfill | 應繼續 defer，直到 OFFLINE classification decision | ❌ 不啟動 |
| Fixture mode 尚未有 SOP / user-facing operating guide | 使用者需知道如何啟用、解讀 fixture mode | 下一輪 |
| OFFLINE 分類學尚未決策 | OFFLINE vs REJECTED/RETIRED 邊界未明確 | 下一輪 decision memo |
| UI toggle button | 目前只能 URL param 啟用 fixture mode，無 UI 控制項 | P23 候選 |
| DB mtime dirty 問題尚未 SOP 化 | 建議在 pytest conftest 加入自動 restore fixture | 技術債 |

---

## 8. 風險與不確定點

| 風險 | 說明 |
|------|------|
| Fixture rows 為 synthetic | 不代表真實 replay outcome；banner 警告為主要防護，但仍依賴使用者閱讀 banner |
| Fixture mode 啟用方式不直覺 | URL param 需手動輸入，容易被遺忘或誤用 |
| 若未明確標示 fixture mode，可能被誤讀為 production replay | `advisory_only=true` 與 banner 為目前唯一防護 |
| DB mtime bump 問題 | 每次 pytest 執行可能 dirty lottery_v2.db，若遺漏 restore 會造成非預期 commit |
| Fixture artifact 版本管理 | `non_online_replay_fixture_20260511.json` 以日期命名，未來更新需同步更新 `_FIXTURE_HISTORY_PATH` |

---

## 9. CTO 建議

1. **停止 Pnn 小數點膨脹**：本 epic 在 PR #51 / #53 / #54 三輪內完成交付，建議下一輪轉向 SOP 與文件而非繼續分 P 號。
2. **下一輪優先：SOP + UI 操作文件**：fixture mode 的啟用方式、解讀方式、banner 意義，需要使用者可閱讀的操作指南。
3. **Production DB backfill 繼續 defer**：在 OFFLINE classification decision 確定之前，不應執行任何 backfill。
4. **不啟動 edge discovery**：與本 epic 無關，不應在驗收文件完成前混入。
5. **DB mtime SOP**：建議在 pytest `conftest.py` 加入 `data/lottery_v2.db` auto-restore fixture，避免人工漏 restore。

---

## 10. 下一輪可執行 Prompt（CTO 選擇）

### 選項 A — Replay Fixture-Mode SOP + User Guide
```
產出 Replay Fixture-Mode 使用者操作指南（SOP），涵蓋：
- 如何啟用 fixture mode（URL param + 未來 UI toggle）
- 如何解讀 banner 警告
- REJECTED / RETIRED / OBSERVATION 的差異
- 何時不應使用 fixture mode
```

### 選項 B — OFFLINE Classification Decision Memo
```
產出 OFFLINE vs REJECTED/RETIRED/OBSERVATION 分類學決策備忘錄，涵蓋：
- 目前 lifecycle 狀態的邊界定義
- OFFLINE 的語意與現有分類的差異
- CTO 決策所需的選項與取捨
```

### 選項 C — P23 Fixture Mode UI Toggle
```
在 replay section 新增 FIXTURE MODE toggle button，
使使用者可在 UI 中直接切換，不依賴 URL param。
```

---

## Main Branch 狀態（Epic 結束時）

```
142dc45 docs(replay): fixture mode browser e2e validation (#54)
ce87159 feat(replay): add fixture mode replay history bridge (#53)
7762118 feat(replay): add isolated non-online replay fixture artifact generator (#51)
```

## Final Markers

```
P22_FIXTURE_MODE_VALIDATION_PR54_MERGED_TO_MAIN
REPLAY_FIXTURE_MODE_EPIC_CLOSURE_READY
REPLAY_FIXTURE_MODE_EPIC_DB_FINAL_CLEAN
```
