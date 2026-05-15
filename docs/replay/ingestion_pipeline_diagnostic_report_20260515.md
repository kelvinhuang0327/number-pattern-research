# Ingestion Pipeline Diagnostic — 2026-05-15

**Branch:** `chore/ingestion-pipeline-diagnostic-20260515`
**Generated:** 2026-05-15T07:30:00Z
**Final Classification:** `INGESTION_PIPELINE_DIAGNOSTIC_READY`

---

## 1. 目標 (Objective)

本診斷旨在找出 BIG_LOTTO draw `115000051` 為何遲遲未進入 `lottery_v2.db`，並分析整體 ingestion pipeline 架構，確認是否存在自動化資料更新機制。

觸發原因：P2C watcher 執行 8 次（2026-05-15），每次均顯示 `big_lotto_draw_exists: false`，且各彩種最新 draw 日期均偏舊，判斷為系統性 ingestion lag。

---

## 2. 停止 Watcher 重複的原因

| 指標 | 數值 |
|------|------|
| Watcher 執行次數 | 8 次（同一天） |
| 每次結果 | `BLOCKED` — `115000051` 不存在 |
| BIG_LOTTO 最新 draw | `115000050` (2026/05/05) |
| 偏舊天數 | 10 天 |

Run 8 新增 ingestion diagnostic 後確認：問題非偶發，而是 systemic — 所有彩種均停止更新。繼續 watcher 重複無意義，改行 ingestion 根因分析。

---

## 3. Phase 3 Performance Recovery

在 Phase 3 執行前，上一版診斷腳本因 heredoc 語法錯誤（非 DB 效能問題）被取消。依照 recovery 流程：

| 項目 | 結果 |
|------|------|
| 卡住的命令 | 無（腳本被 user 取消，無 stuck process） |
| 根本原因 | Shell heredoc 巢狀語法錯誤（`<<'EOF'` inside another heredoc） |
| 改用最小 check | ✅ 是 |
| 最小 check 耗時 | **0.05 秒** |
| DB 狀態 | ✅ 健康 |
| 後續 search 範圍 | `scripts`, `tools`, `lottery_api`, `docs`, `.github/workflows` |
| 排除目錄 | `.git`, `.venv`, `node_modules`, `outputs`, `__pycache__` |

---

## 4. DB 狀態快照

查詢時間：2026-05-15，對應 `lottery_api/data/lottery_v2.db`（production DB，唯讀模式）。

| 指標 | 數值 |
|------|------|
| Tables | 18 |
| draws 總筆數 | 14,002 |
| strategy_prediction_replays 總筆數 | 966 |
| P2B rows (apply_id=P2B_20260515) | 6 ✅ |
| P2C rows (apply_id=P2C_20260515) | 0 |

---

## 5. 各彩種最新 Draw 狀態

| lottery_type | 最新 draw | 最新日期 | 偏舊天數 | 嚴重性 |
|---|---|---|---|---|
| 3_STAR | 99000261 | 2026/01/28 | **107 天** | 🔴 CRITICAL |
| BIG_LOTTO | 115000050 | 2026/05/05 | **10 天** | 🟠 HIGH |
| DAILY_539 | 99000261 | 2026/04/29 | **16 天** | 🟠 HIGH |
| POWER_LOTTO | 99000104 | 2026/04/27 | **18 天** | 🟠 HIGH |

> **注意：** 3_STAR 偏舊 107 天屬異常，可能為獨立問題（資料源或格式變更）。

---

## 6. Draw 115000051 存在狀況

| lottery_type | 存在 | draw | date |
|---|---|---|---|
| BIG_LOTTO | ❌ 不存在 | — | — |
| DAILY_539 | ✅ 存在 | 115000051 | 2026/02/26 |

> 重要：draw 號碼在各彩種間共用，但屬完全獨立的開獎事件。DAILY_539 有 `115000051` 不代表 BIG_LOTTO 也有。

---

## 7. 預期開獎日程 vs DB 狀態

BIG_LOTTO 每週一、週四開獎（每週約 2 期）：

| Draw | 預期開獎日 | DB 狀態 |
|---|---|---|
| 115000051 | 約 2026-05-08（週四） | ❌ OVERDUE |
| 115000052 | 約 2026-05-12（週一） | ❌ OVERDUE |
| 115000053 | 約 2026-05-15（週四，今日） | ❌ OVERDUE |

---

## 8. 候選 Ingestion 腳本

在 `tools/`, `lottery_api/` 找到以下可能寫入 draws 的腳本：

### 8a. 主要爬蟲腳本

| 腳本 | 資料來源 | 彩種 |
|---|---|---|
| `tools/scrape_lottery_data.py` | `https://api.taiwanlottery.com/TLCAPIWeB/Lotto649/history` | BIG_LOTTO |
| `tools/upload_lottery_data.py` | CSV 檔案（手動下載） | 多彩種 |
| `tools/upload_big_lotto_csv.py` | CSV 檔案（手動下載） | BIG_LOTTO |
| `tools/upload_daily539_txt.py` | TXT 檔案（手動下載） | DAILY_539 |
| `tools/universal_downloader.py` | 任意 URL（通用下載器） | 非 draw-specific |

### 8b. API Endpoints（HTTP 寫入路徑）

| Method | Route | Handler | 說明 |
|---|---|---|---|
| POST | `/api/history` | `lottery_api/routes/data.py` | 批次 insert draws（INSERT OR IGNORE） |
| POST | `/api/draws` | `lottery_api/routes/data.py` | 單筆 draw 新增 |
| PUT | `/api/draws/{draw_id}` | `lottery_api/routes/data.py` | 更新既有 draw |

---

## 9. Scheduler 分析

### lottery_api/utils/scheduler.py

```python
# APScheduler AsyncIOScheduler
# 每天 02:00 執行：AdvancedAutoLearningEngine optimization
# → 策略參數調整，NOT draw 資料抓取
```

**結論：** scheduler 不抓 draw，僅做 ML 優化。

### lottery_api/utils/smart_scheduler.py

```python
# 策略評估 02:00 + 學習 03:00
# → SmartLearningScheduler，NOT draw ingestion
```

**結論：** 同上，不抓 draw。

### GitHub Actions

| Workflow | Cron | 功能 |
|---|---|---|
| `replay-governance-ci.yml` | push/PR trigger | Governance test |
| `replay-lifecycle-drift-guard.yml` | `0 2 * * *` (daily 02:00 UTC) | Replay drift 偵測 |

**結論：** 無任何 workflow 抓取 draws。

### LaunchD (com.kelvin.lottery.dev.plist)

- `start_all.sh --foreground` → 啟動 backend (port 8002) + frontend (port 8081)
- 不含 draw fetch job

---

## 10. 根因假設 (Root Cause)

> **NO_AUTOMATED_INGESTION_PIPELINE**

整個 codebase 沒有任何自動化機制（cron job、scheduler task、GitHub Action、background service）定期從台灣彩券 API 抓取新 draw 並寫入 `lottery_v2.db`。

所有 draw 寫入路徑均為**手動操作**：
1. 開發者手動執行 `tools/scrape_lottery_data.py`
2. 或手動下載 CSV/TXT 後執行 upload 腳本
3. 或透過 HTTP POST 到 `/api/history`

**最後一次手動 ingestion：** 2026-05-05（BIG_LOTTO draw 115000050），距今 10 天。

---

## 11. 修復方案

### 短期修復（立即執行）

```bash
# Step 1: 確認 backend 在運行（PID 10477, port 8002）
curl -s http://localhost:8002/health

# Step 2: 執行 scraper 抓取最新 BIG_LOTTO draws
cd /Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery_api
python tools/scrape_lottery_data.py

# Step 3: 驗證 115000051 已寫入
python3 -c "import sqlite3; c=sqlite3.connect('data/lottery_v2.db'); \
  print(c.execute(\"SELECT draw, date FROM draws WHERE lottery_type='BIG_LOTTO' \
  ORDER BY CAST(draw AS INTEGER) DESC LIMIT 5\").fetchall())"
```

### 中期修復（架構改善）

```bash
# 建議新增 GitHub Actions workflow 或 launchd job：
# - 每天 22:00 或 23:00（開獎後）自動執行 scrape_lottery_data.py
# - 只允許 INSERT OR IGNORE（冪等操作，安全）
# - 完成後觸發 replay drift guard CI
```

### P2C 解鎖條件

當 BIG_LOTTO draw `115000051` 成功寫入後：
- 執行 promotion engine，將 items 1090-1092（run_id=174）從 `PENDING` 推進至 `TRUTH_CONFIRMED`
- 確認 P2C rows = 3（DAILY_539 類型），或依實際 item lottery_type 決定

---

## 12. 安全確認

- ✅ No DB writes performed in this diagnostic
- ✅ No draw inserts
- ✅ No replay rows inserted
- ✅ No prediction_items promotion
- ✅ No strategy code changes
- ✅ No API/UI/backend behavior changes
- ✅ PR #110 (P2C readiness snapshot) remains OPEN DRAFT — not merged
- ✅ PR #111 (watcher canonical) remains OPEN DRAFT — not merged
- ✅ This PR: DRAFT only

---

## Appendix — Watcher History Summary

| Run | 日期 | BIG_LOTTO 最新 | 115000051 存在 | 分類 |
|---|---|---|---|---|
| 1 | 2026-05-15 | 115000050 | ❌ | BLOCKED |
| 2 | 2026-05-15 | 115000050 | ❌ | BLOCKED |
| 3 | 2026-05-15 | 115000050 | ❌ | BLOCKED |
| 4 | 2026-05-15 | 115000050 | ❌ | BLOCKED |
| 5 | 2026-05-15 | 115000050 | ❌ | BLOCKED |
| 6 | 2026-05-15 | 115000050 | ❌ | BLOCKED |
| 7 | 2026-05-15 | 115000050 | ❌ | BLOCKED |
| 8 | 2026-05-15 | 115000050 | ❌ | BLOCKED + SYSTEMIC_INGESTION_LAG |
