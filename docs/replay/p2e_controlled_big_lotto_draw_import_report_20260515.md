# P2E Controlled Official Draw Import Report

**Date:** 2026-05-15
**Classification:** WAITING_FOR_USER_DRAW_IMPORT_APPROVAL_P2E_20260515
**Controlled Import ID:** P2E_20260515
**Branch:** chore/p2e-controlled-official-draw-import-20260515

---

## 1. 本輪目標

從 P2D dry-run 驗證結果，受控匯入大樂透期號 115000051 及 115000052 至 `lottery_v2.db`。

- 本輪僅完成 preflight、schema 驗證、dry-run 預覽、腳本建立
- **尚未執行任何 DB 寫入**（需明確操作人授權）
- 匯入完成後，P2C replay 可解除封鎖

---

## 2. Authorization Gate — WAITING FOR OPERATOR APPROVAL

**目前狀態：** WAITING_FOR_USER_DRAW_IMPORT_APPROVAL_P2E_20260515

**DB 尚未被寫入。** 操作人必須提供以下完整授權文字後，方可執行 `--apply`：

```
YES import BIG_LOTTO draws 115000051 and 115000052
```

提供授權後，使用「第 7 節：授權後執行指令」執行實際匯入。

---

## 3. Required Authorization Text

操作人必須明確說出：

> YES import BIG_LOTTO draws 115000051 and 115000052

---

## 4. P2D Dry-Run Source Verification

| 項目 | 值 |
|------|-----|
| P2D run_id | `p2d_official_draw_ingestion_dryrun_20260515` |
| P2D classification | `P2D_OFFICIAL_DRAW_INGESTION_DRYRUN_PARTIAL_READY` |
| P2D JSON 路徑 | `outputs/replay/p2d_big_lotto_official_draw_ingestion_dryrun_20260515.json` |
| P2D db_written | `false` |
| P2D draw_rows_inserted | `false` |
| 官方 API endpoint | `api.taiwanlottery.com/TLCAPIWeB/Lottery/Lotto649Result` |
| special ball 範圍 | 1–49（已確認） |
| P2C unblock status | `READY_PENDING_IMPORT` |

**P2D 確認期號：**

| 期號 | 開獎日期 | 號碼 | 特別號 | 狀態 |
|------|---------|------|--------|------|
| 115000051 | 2026/05/08 | [10, 18, 25, 28, 39, 43] | 48 | FETCHED |
| 115000052 | 2026/05/12 | [6, 12, 18, 19, 32, 36] | 34 | FETCHED |
| 115000053 | N/A | N/A | N/A | NOT_PUBLISHED（明確拒絕） |

---

## 5. DB Preflight Results (Read-Only)

**執行時間：** 2026-05-15

| 期號 | DB 狀態 |
|------|---------|
| 115000050 | EXISTS（最新期，2026/05/05，[4,17,23,28,33,37] SP=15） |
| 115000051 | MISSING（待匯入） |
| 115000052 | MISSING（待匯入） |
| 115000053 | MISSING（NOT_PUBLISHED，不匯入） |

**Replay 行數（現況）：**

| Label | Rows |
|-------|------|
| P2B_20260515 | 6 |
| P2C_20260515 | 0（待解鎖） |
| P2E_20260515 | 0（本輪不寫入） |
| Total | 966 |

---

## 6. Dry-Run Preview Table

以下為 `--apply` 執行時將寫入的內容（**目前 db_written=false**）：

```
DRAW           DATE         NUMBERS                        SPECIAL  STATUS              
------------------------------------------------------------------------------------------
115000051      2026/05/08   [10, 18, 25, 28, 39, 43]       48       WOULD_IMPORT (DRY-RUN)
115000052      2026/05/12   [6, 12, 18, 19, 32, 36]        34       WOULD_IMPORT (DRY-RUN)
```

驗證通過項目：
- 每期恰好 6 個主球，範圍 1–49
- 特別號在 1–49 範圍
- 日期格式符合 YYYY/MM/DD
- P2D fetch_status = FETCHED
- DB 無衝突記錄

---

## 7. Import Script 執行方式

**腳本路徑：** `scripts/p2e_controlled_official_draw_import.py`

### Dry-Run（目前已完成）

```bash
python3 scripts/p2e_controlled_official_draw_import.py \
  --db lottery_api/data/lottery_v2.db \
  --dryrun-json outputs/replay/p2d_big_lotto_official_draw_ingestion_dryrun_20260515.json \
  --draws 115000051,115000052 \
  --controlled-import-id P2E_20260515 \
  --json-out outputs/replay/p2e_controlled_big_lotto_draw_import_receipt_20260515.json
```

### 授權後執行（--apply，需操作人授權）

```bash
cd /Users/kelvin/Kelvin-WorkSpace/LotteryNew-clean && \
/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.venv/bin/python3 scripts/p2e_controlled_official_draw_import.py \
  --db lottery_api/data/lottery_v2.db \
  --dryrun-json outputs/replay/p2d_big_lotto_official_draw_ingestion_dryrun_20260515.json \
  --draws 115000051,115000052 \
  --controlled-import-id P2E_20260515 \
  --json-out outputs/replay/p2e_controlled_big_lotto_draw_import_receipt_20260515.json \
  --apply
```

腳本設計特性：
- `INSERT OR IGNORE`（幂等，重複執行安全）
- 若期號已存在且值相符 → `ALREADY_PRESENT`，繼續
- 若期號已存在且值不符 → `HARD FAIL`，立即終止
- 115000053 明確拒絕（NOT_PUBLISHED）

---

## 8. Post-Import Steps (P2C Re-Run)

匯入完成後，建議執行以下步驟解除 P2C 封鎖：

1. 確認 DB 已含 115000051 / 115000052
2. 執行 P2C replay 回填腳本（見 P2C 分支）
3. 驗證 `strategy_prediction_replays` 中 P2C_20260515 行數 > 0
4. 更新 RSM（`tools/rsm_bootstrap.py`）
5. 執行 post-draw pipeline 確認下期快照

---

## 9. Safety Confirmation (This Round)

| 項目 | 狀態 |
|------|------|
| db_written | FALSE |
| replay_rows_generated | FALSE |
| prediction_items_promoted | FALSE |
| strategy_logic_changed | FALSE |
| api_ui_backend_changed | FALSE |
| .db 檔案納入 git | FALSE |
| 不在授權清單的期號 | 無 |
| 115000053 強制拒絕 | 是 |

---

## 10. Next Step Recommendation

1. 操作人提供授權文字：`YES import BIG_LOTTO draws 115000051 and 115000052`
2. 使用第 7 節「授權後執行」指令執行 `--apply`
3. 確認 receipt JSON 中 `db_written=true`
4. 確認 DB 中 115000051 / 115000052 存在且值正確
5. 解除 P2C 封鎖，執行 replay 回填
6. 提交 apply 後的 receipt 至 git，更新 PR 狀態
