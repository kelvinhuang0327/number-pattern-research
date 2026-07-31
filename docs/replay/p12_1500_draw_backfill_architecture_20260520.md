# P12 1500-Draw Backfill Engine Architecture
**Date:** 2026-05-20  
**Classification:** P12_1500_DRAW_BACKFILL_PLAN_READY  
**Status:** Architecture Plan — dry-run design only. No implementation yet.

---

## 1. Backfill Engine 目標

為所有 ONLINE strategies，系統性地針對最近 1500 期歷史開獎記錄，重新執行預測函式，並將預測結果與實際開獎比對後寫入 `strategy_prediction_replays` 表。

最終目標：UI 歷史回放頁面可顯示 8 ONLINE strategies × 1500 期 = 12,000 rows 的比對記錄。

**黃金規則：**
- 不得 fabricate 任何 predicted_numbers / actual_numbers / hit_count
- 不得使用未來資料（嚴格 causal slice）
- 不得在 CEO 授權前寫入 production DB

---

## 2. Input: Strategy Registry

來源：`lottery_api/models/replay_strategy_registry.py`

只使用 `lifecycle_status == "ONLINE"` 的策略：

```python
from lottery_api.models.replay_strategy_registry import list_strategies
online = [s for s in list_strategies() if s["strategy_lifecycle_status"] == "ONLINE"]
# 8 strategies
```

每個 strategy 提供：
- `strategy_id`
- `strategy_name`
- `strategy_version`
- `supported_lottery_types`
- `min_history`（預設 100，需至少 100 期歷史才執行）
- `get_one_bet(history, lottery_type) → (numbers, special)` adapter

---

## 3. Input: Historical Draws

來源：`draws` 表（DB read-only）

```sql
SELECT draw, date, lottery_type, numbers, special
FROM draws
WHERE lottery_type = ?
ORDER BY draw ASC
```

**重要：** draw 排序必須嚴格升序（數字排序，非字串），確保 causal slice 正確。

每一期 target draw `T`，history slice 為：
```
history = [所有 draw < T 的記錄（strict less-than）]
```

min_history 檢查：
```
len(history) < strategy.min_history → SKIP (記錄 replay_status="INSUFFICIENT_HISTORY")
```

---

## 4. Input: Strategy Prediction Function

來源：registry adapter 的 `get_one_bet()` 方法

```python
adapter = get_adapter(strategy_id)
predicted_numbers, predicted_special = adapter.get_one_bet(history_slice, lottery_type)
```

**規則：**
- history 必須是 strictly-before-T 的完整有序記錄
- adapter 不得讀取 DB / 外部檔案 / env（在執行期間）
- DAILY_539 special = None
- POWER_LOTTO: 6 main numbers
- BIG_LOTTO: 6 main numbers
- DAILY_539: 5 main numbers

例外處理：
- `RejectPrediction` → `replay_status="REJECTED"`, `reject_reason=str(exc)`
- `InsufficientHistory` → `replay_status="INSUFFICIENT_HISTORY"`
- `UnsupportedLotteryType` → `replay_status="UNSUPPORTED_LOTTERY_TYPE"`
- 其他 Exception → `replay_status="REPLAY_ERROR"`, `reject_reason=str(exc)[:256]`

---

## 5. Output: strategy_prediction_replays rows

每個成功執行的 (strategy, draw) pair 產生一個 row：

```python
{
    "lottery_type":        lottery_type,
    "target_draw":         draw_id,
    "target_date":         draw_date,
    "strategy_id":         strategy_id,
    "strategy_name":       strategy_name,
    "strategy_version":    strategy_version,
    "history_cutoff_draw": last_draw_before_target,
    "replay_status":       "PREDICTED",  # or error status
    "reject_reason":       None,
    "predicted_numbers":   json.dumps(sorted(predicted_numbers)),
    "predicted_special":   predicted_special,
    "actual_numbers":      json.dumps(sorted(actual_numbers)),
    "actual_special":      actual_special,
    "hit_numbers":         json.dumps(sorted(hit_set)),
    "hit_count":           len(hit_set),
    "special_hit":         1 if predicted_special == actual_special else 0,
    "truth_level":         "CAUSAL_REPLAY_GENERATED",
    "source":              "P12_BACKFILL_ENGINE",
    "provenance_hash":     sha256(strategy_id + draw + predicted_numbers_json),
    "provenance_source":   "backfill_engine_v1",
    "dry_run":             1,  # 0 only after CEO apply authorization
    "controlled_apply_id": None,  # set during apply gate
}
```

---

## 6. predicted_numbers 來源規則

- **唯一合法來源**：`adapter.get_one_bet(history_slice, lottery_type)` 的返回值
- **嚴格禁止**：從任何已有 row、log、artifact 複製；隨機生成；hardcode
- **驗證**：adapter 返回後立即驗證號碼格式（長度、範圍）

```python
def _validate_numbers(numbers, lottery_type):
    rules = {"POWER_LOTTO": (6, 1, 38), "BIG_LOTTO": (6, 1, 49), "DAILY_539": (5, 1, 39)}
    count, lo, hi = rules[lottery_type]
    assert len(numbers) == count
    assert all(lo <= n <= hi for n in numbers)
    assert len(set(numbers)) == len(numbers)  # no duplicates
```

---

## 7. actual_numbers 來源規則

- **唯一合法來源**：`draws` 表的 `numbers` 欄位（JSON array）
- **嚴格禁止**：猜測、推算、從 predicted_numbers 複製
- 如果 draws 表無此期記錄 → `replay_status="ACTUAL_MISSING"`，跳過

---

## 8. hit_numbers 計算方式

```python
predicted_set = set(json.loads(predicted_numbers_json))
actual_set    = set(json.loads(actual_numbers_json))
hit_numbers   = sorted(predicted_set & actual_set)
```

- hit_numbers 是 predicted 和 actual 的交集
- 不得人工設定或調整

---

## 9. hit_count 計算方式

```python
hit_count = len(hit_numbers)  # 0 到 max balls
```

- 純計算自 hit_numbers，不得 fabricate

---

## 10. special_hit 計算方式

```python
if lottery_type == "DAILY_539":
    special_hit = 0  # no special in 539
elif predicted_special is None or actual_special is None:
    special_hit = 0
else:
    special_hit = 1 if int(predicted_special) == int(actual_special) else 0
```

---

## 11. truth_level 設計

| truth_level 值 | 意義 |
|---------------|------|
| `CAUSAL_REPLAY_GENERATED` | 由 backfill engine 使用 causal history slice 執行產生 |
| `REGENERATED` | 從已有 artifact / DB 重建（P7/P8 路徑） |
| `ARTIFACT` | 僅有 artifact 記錄，未重新執行 |

**Backfill engine 產生的所有 rows 使用 `CAUSAL_REPLAY_GENERATED`。**

---

## 12. source_trace / provenance_hash 設計

```python
import hashlib, json

def _provenance_hash(strategy_id, draw, predicted_json, history_cutoff):
    payload = f"{strategy_id}|{draw}|{predicted_json}|{history_cutoff}"
    return hashlib.sha256(payload.encode()).hexdigest()
```

- `source`: `"P12_BACKFILL_ENGINE"` + phase tag
- `provenance_hash`: SHA256 of (strategy_id + draw + predicted_numbers + history_cutoff)
- `provenance_source`: `"backfill_engine_v1"`

每個 row 可獨立驗證，確保可重現性。

---

## 13. controlled_apply_id 設計

- Dry-run rows: `controlled_apply_id = None`, `dry_run = 1`
- Apply 授權後: `controlled_apply_id = "P12_PHASE1_APPLY_<timestamp>"`, `dry_run = 0`
- Apply 必須使用獨立 apply gate script（類似 P7 apply script）
- Apply gate 要求：明確 CEO 授權 phrase

---

## 14. Dry-run / Apply Gate

```
┌─────────────────────────────────────────┐
│         Backfill Engine (dry-run)        │
│  - reads DB (read-only)                  │
│  - executes adapter.get_one_bet()        │
│  - generates row payloads in memory      │
│  - writes to OUTPUT JSON file only       │
│  - dry_run=1, controlled_apply_id=None   │
└──────────────────┬──────────────────────┘
                   │ dry-run JSON output
                   ▼
┌─────────────────────────────────────────┐
│         Human / CEO Review               │
│  - verify no fake rows                   │
│  - verify hit counts make sense          │
│  - confirm strategy IDs match registry   │
│  - issue apply authorization phrase      │
└──────────────────┬──────────────────────┘
                   │ "YES apply P12 Phase 1 backfill rows"
                   ▼
┌─────────────────────────────────────────┐
│         Apply Gate Script                │
│  - reads dry-run JSON                    │
│  - checks authorization phrase           │
│  - inserts rows with dry_run=0           │
│  - maintains rollback capability         │
└─────────────────────────────────────────┘
```

---

## 15. Rollback Strategy

Rollback 基於 `controlled_apply_id`：

```sql
-- Rollback all P12 Phase 1 rows
DELETE FROM strategy_prediction_replays
WHERE controlled_apply_id = 'P12_PHASE1_APPLY_<timestamp>';
```

在 apply 前必須記錄：
- apply_id
- apply_timestamp
- row_count_before
- row_count_after（預期）

---

## 16. Duplicate Prevention

```python
# 插入前必須檢查 UNIQUE constraint
# schema: UNIQUE(lottery_type, target_draw, strategy_id, replay_run_id)
# 使用 INSERT OR IGNORE 或先 SELECT COUNT(*) 確認

existing = conn.execute(
    "SELECT COUNT(*) FROM strategy_prediction_replays "
    "WHERE strategy_id=? AND lottery_type=? AND target_draw=?",
    (strategy_id, lottery_type, draw)
).fetchone()[0]
if existing > 0:
    skip_reason = "DUPLICATE_ALREADY_EXISTS"
    continue
```

---

## 17. DB Index / Pagination Requirement

**目前已有 index（足夠 Phase 1）：**
```sql
CREATE INDEX idx_spr_lottery   ON strategy_prediction_replays(lottery_type);
CREATE INDEX idx_spr_strategy  ON strategy_prediction_replays(strategy_id);
CREATE INDEX idx_spr_draw      ON strategy_prediction_replays(target_draw);
CREATE INDEX idx_spr_status    ON strategy_prediction_replays(replay_status);
CREATE INDEX idx_spr_run       ON strategy_prediction_replays(replay_run_id);
CREATE INDEX idx_spr_hit       ON strategy_prediction_replays(hit_count);
```

**12,000 rows 後需評估的 index（P17）：**
- `(strategy_id, lottery_type, target_draw)` composite index for pagination
- `(lottery_type, target_draw DESC)` for timeline queries

**API Pagination 設計（P17）：**
```
GET /api/replay/history?strategy_id=X&lottery_type=Y&page=1&per_page=50
```
- 12,000 rows 時，使用 cursor-based pagination（避免 OFFSET 效能問題）
- 建議 default page_size=50，max=200

---

## 18. API Impact

**現有 API endpoints（預計不變）：**
- `GET /api/replay/strategies` — 返回 strategy list
- `GET /api/replay/history` — 返回 replay rows（需加 pagination）

**P12 後需注意：**
- 12,000 rows 時，`GET /api/replay/history` 必須有 pagination
- 否則 response 可能超過 browser 可處理範圍

---

## 19. UI Impact

**目前 UI：** 歷史預測清單（draw-level）  
**P12 後不做 UI 大改版**

**P18 需做：**
- 分頁控制（pagination controls）
- Strategy filter dropdown
- Draw range selector
- 排序方式（by draw number / hit count）

---

## 20. Performance Risk

| 風險 | 說明 | 緩解方案 |
|------|------|---------|
| 1500 × 8 strategies × adapter execution | 每次 adapter call 需要 100 期 history slice | batch processing，先 BIG_LOTTO（2135 draws），逐步擴展 |
| DB write volume | 一次寫入 12,000 rows | batch insert（1000 rows / batch），每 batch 後 commit |
| DAILY_539 5865 draws × 2 strategies | 最大子集，單次可達 ~11,730 rows | 分批 + progress checkpoint |
| Adapter regression | fourier_rhythm_3bet / ts3_regime_3bet 無現有 rows | Phase 1 先跑 proven strategies，再測 0-row strategies |
| Index scan degradation | 12K→全量 | Phase 1 結束後加 composite index |

---

*Architecture plan only. No implementation. No DB writes.*
