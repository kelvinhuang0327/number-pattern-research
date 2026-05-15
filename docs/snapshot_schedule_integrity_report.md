# Snapshot & Schedule Integrity Report
Generated: 2026-03-26

---

## 一、快照唯一性機制

### 問題：同一期可否建立多個快照？

**現狀**：prediction_runs 表無 UNIQUE 約束於 (lottery_type, latest_known_draw)。
使用者多次點擊「產生預測快照」，同一期可建立多個 run。

**驗證**：DB 中 run#9 和 run#11 都是 DAILY_539 / 115000075 / VALID → 重複了。

**影響**：
- 歷史列表出現重複期數
- 績效統計若解析後會重複計算

**建議修正**：在 create_snapshot 前檢查同 (lottery_type, latest_known_draw, snapshot_source='VALID') 是否已存在，若已有 VALID 快照則拒絕再建。

### 目前排程狀態

| 彩種 | latest_draw | next_expected | status |
|------|-------------|---------------|--------|
| 今彩539 | 115000075 | 115000076 | SNAPSHOT_CREATED |
| 大樂透 | 115000038 | 115000039 | SNAPSHOT_CREATED |
| 威力彩 | 115000024 | 115000025 | SNAPSHOT_CREATED |

✅ 三個彩種下期快照均已建立。

---

## 二、排程狀態機定義

| 狀態 | 意義 | 觸發 |
|------|------|------|
| SCHEDULED | 已排程，快照尚未建立 | startup 邏輯自動建立 |
| SNAPSHOT_CREATED | 快照已建立（含 VALID 或 RECONSTRUCTED） | create_snapshot 呼叫 |
| MISSED_WINDOW | 開獎期已過但未建立快照 | startup 邏輯偵測 |
| RECONSTRUCTED | 重建快照（非正式預測，事後補算） | schedule/generate 端點 |

---

## 三、RECONSTRUCTED 是否影響統計

✅ 績效統計 `valid_only=True`（預設）明確排除 RECONSTRUCTED：

```python
# engine/prediction_tracker.py L540
if valid_only:
    conditions.append("(pr.snapshot_source = 'VALID' OR pr.snapshot_source IS NULL)")
```

✅ `valid_only` 前端 toggle（`pt-valid-toggle`）預設勾選，使用者可手動切換查看包含 RECONSTRUCTED 的統計。

---

## 四、未來多期快照建立限制

**需求**："未來多期只能建立 schedule，不可預先算號碼"

**現狀**：POST /api/tracking/snapshot 的邏輯：
- 計算 `target_draw = latest_known_draw + 1`
- 若 target_draw 已在 DB → RECONSTRUCTED（事後補算）
- 若 target_draw 未在 DB → VALID（正式預測，期數尚未開出）

系統無機制阻止「建立 target_draw+2 或更遠的快照」，但因為邏輯是固定 target_draw = latest+1，所以自然只能預測下一期。

✅ 符合需求，不存在超前預測問題。

---

## 五、快照重複建立問題（需修正）

**問題嚴重度**：中等（影響歷史列表美觀和績效統計準確性）

**建議修正**：在 `create_snapshot` 端點加入重複檢查：

```python
# 建議加入 prediction_tracking.py snapshot endpoint
existing = db.fetchone(
    "SELECT id FROM prediction_runs WHERE lottery_type=? AND latest_known_draw=? AND snapshot_source='VALID'",
    (lottery_type, target_draw)
)
if existing:
    raise HTTPException(400, f"VALID 快照已存在 (run#{existing['id']})，不可重複建立")
```

**此項修正不在本次 P1 範圍，但記錄為 BLOCKER-3。**

---

## 六、資料完整性工具驗收

| 功能 | 實作位置 | 狀態 |
|------|---------|------|
| 查看哪些期數缺漏 | `/api/tracking/schedule/status` | ✅ 正確 |
| 抓最新獎號 | DrawEntryManager UI / `/api/ingest` | ✅ 正確 |
| 回補缺漏資料 | `/api/tracking/schedule/generate/{id}?source=RECONSTRUCTED` | ✅ 正確 |
| 查看快照排程狀態 | `/api/tracking/schedule/status` + schedule history | ✅ 正確 |
| 標記 SCHEDULED | startup 邏輯 | ✅ 正確 |
| 標記 SNAPSHOT_CREATED | create_snapshot 後更新 | ✅ 正確 |
| 標記 MISSED_WINDOW | startup 偵測 | ✅ 正確 |
| 標記 RECONSTRUCTED | generate 端點傳入 source=RECONSTRUCTED | ✅ 正確 |
| 不干擾績效統計 | valid_only 篩選 | ✅ 正確 |
