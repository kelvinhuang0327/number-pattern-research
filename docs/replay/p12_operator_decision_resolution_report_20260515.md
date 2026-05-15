# P1.2 Operator Decision Resolution Report

**Document type**: Operator Decision Report — Read-Only Evidence Scan  
**Date**: 2026-05-15  
**Branch**: `docs/p12-operator-decision-resolution-20260515`  
**Input PR**: #104 (P1.1 Strategy Denominator Cleanup)  
**Output JSON**: `outputs/replay/p12_operator_decision_resolution_20260515.json`

---

## 1. 本輪目標

解決 P1.1 遺留的 2 個 `NEEDS_OPERATOR_DECISION` strategies：

- `fourier_rhythm_3bet`
- `ts3_regime_3bet`

依 evidence scan 結果，決定每個 strategy 的最終分類：
- A. `DUPLICATE_OR_SUPERSEDED`
- B. `PRODUCT_DENOMINATOR + RETIRED tombstone candidate`
- C. `RESEARCH_ARCHIVE / false positive`

並鎖定 clean denominator 為 69 或 71，為 P1.3 registry proposal 做準備。

---

## 2. 輸入來源

| 來源 | 用途 |
|------|------|
| `outputs/replay/p11_strategy_denominator_cleanup_20260515.json` (PR #104) | P1.1 分類結果，NOD 2 個策略 |
| `outputs/replay/p2_lifecycle_backfill_dry_run_manifest_20260510.json` | p2 dry run promotable/blocked rows |
| `lottery_api/data/lottery_v2.db` (read-only) | prediction_runs, prediction_items 當前狀態 |
| `lottery_api/engine/rolling_strategy_monitor.py` | 生產 RSM 策略配置 |
| `tools/rsm_bootstrap.py` | RSM bootstrap 策略配置 |
| `lottery_api/models/replay_strategy_registry.py` | 16 canonical registry strategies |
| `outputs/replay/strategy_catalog_inventory_20260512.md` | 策略 catalog 清查 |
| `memory/lessons.md` | 歷史研究決策記錄 |

---

## 3. 兩個待決策略的 Evidence Scan

### 3.1 P1.1 NOD 分類依據回顧

P1.1 將這兩個策略標記為 `NEEDS_OPERATOR_DECISION` 的原因：
- 在 `p2_lifecycle_backfill_dry_run_manifest_20260510.json` 中 `lifecycle_status=ONLINE`
- 搜尋 `strategy_id` column → 0 rows in ALL DB tables
- Not in canonical registry
- No tombstone

> **P1.2 根本原因發現**: P1.1 DB scan 搜尋 `strategy_id` column，但 `prediction_items` 和 `prediction_runs` tables 使用的是 `strategy_name` column (不是 `strategy_id`)。因此「0 rows in ALL tables」的結論是 column-name 不匹配，不是資料真的不存在。

### 3.2 DB 當前狀態（P1.2 新掃描）

```sql
-- prediction_items schema (no strategy_id column):
-- id, run_id, bet_index, numbers, special, status, created_at, strategy_name, num_bets, zone_coverage

-- prediction_runs schema (uses strategy_name, not strategy_id):
-- id, lottery_type, latest_known_draw, latest_known_date, strategy_name, ...

-- strategy_prediction_replays (uses strategy_id column — 0 rows for both)
```

| Table | fourier_rhythm_3bet | ts3_regime_3bet |
|-------|--------------------|--------------------|
| `strategy_prediction_replays` | 0 rows | 0 rows |
| `prediction_runs` (via strategy_name) | 1 run (run_id=168) | 3 runs (167, 174, 175) |
| `prediction_items` (via run_id) | 3 rows (PENDING) | 9 rows (PENDING) |

### 3.3 fourier_rhythm_3bet — 完整證據

**prediction_run 168 (POWER_LOTTO):**
```
id=168, lottery_type=POWER_LOTTO, latest_known_draw=115000034
target_date=2026-04-27, strategy_name=fourier_rhythm_3bet
snapshot_source=VALID, created_at=2026-04-29 09:42:51
```

**prediction_items (3 rows, status=PENDING):**
```
id=1072, run_id=168, bet_index=0, numbers=[12,22,24,26,29,37], status=PENDING
id=1073, run_id=168, bet_index=1, numbers=[4,23,25,27,33,36],  status=PENDING
id=1074, run_id=168, bet_index=2, numbers=[2,11,13,15,20,32],  status=PENDING
```

**RSM engine registration:**
```python
# lottery_api/engine/rolling_strategy_monitor.py, get_power_lotto_strategies(), line 749:
{'name': 'fourier_rhythm_3bet', 'predict_func': fourier_3bet, 'num_bets': 3}

# tools/rsm_bootstrap.py, get_power_lotto_strategies_inline(), line 60:
{'name': 'fourier_rhythm_3bet', 'predict_func': fourier_3bet, 'num_bets': 3}
```

**memory/lessons.md 關鍵引用:**
- `L76`: "決策：進化3注作為 ALTERNATIVE 備選，不替換 fourier_rhythm_3bet（L76 原則再次確認）"
- `L94`: "fourier_rhythm_3bet 30p 過熱警告（比 6.6x）— 處置：維持上線，下 30 期後重確認"
- Multiple strategies benchmarked against it: "McNemar vs fourier_rhythm_3bet: net=+16, p=0.458"
- "現有 fourier_rhythm_3bet 300p edge=+3.16%（更穩定，不依賴進化搜尋）"

### 3.4 ts3_regime_3bet — 完整證據

**prediction_runs (3 runs, BIG_LOTTO):**
```
id=167, lottery_type=BIG_LOTTO, draw=115000048, date=2026-04-28, VALID
id=174, lottery_type=BIG_LOTTO, draw=115000050, date=2026-05-05, VALID
id=175, lottery_type=BIG_LOTTO, draw=115000049, date=2026-05-01, RECONSTRUCTED
```

**prediction_items (9 rows, all PENDING):**
```
Run 167: items 1069 (bet0), 1070 (bet1), 1071 (bet2) — BIG_LOTTO 115000048
Run 174: items 1090 (bet0), 1091 (bet1), 1092 (bet2) — BIG_LOTTO 115000050
Run 175: items 1093 (bet0), 1094 (bet1), 1095 (bet2) — BIG_LOTTO 115000049
```

**strategy_catalog_inventory_20260512.md, section 6.2:**
> "ts3_regime_3bet | wiki/games/big_lotto.md | UNKNOWN（監控參考策略）| 需 governance 決定是否加入 registry"

**memory/lessons.md 關鍵引用:**
- "繼續使用 regime_2bet/ts3_regime_3bet/p1_dev_sum5bet 生產策略" (L_biglotto_maintenance_mode)
- "McNemar vs ts3_regime_3bet: net=-6, p=0.606 — 新策略未改善生產" (新策略未能超越它)
- 大樂透 49C6 正式進入維護模式，明確列出 ts3_regime_3bet 為保留的生產策略

**與 canonical ts3 variants 的關係:**
- `biglotto_ts3_acb_4bet` (canonical, REJECTED) — ts3 + ACB + 4bet variant
- `biglotto_ts3_markov_freq_5bet` (canonical, REJECTED) — ts3 + MarkovFreq + 5bet variant
- `ts3_regime_3bet` — ts3 + **regime-switching** + 3bet variant (DISTINCT, not a duplicate)

---

## 4. fourier_rhythm_3bet 決策

### 分類結果

**決策: `PRODUCT_DENOMINATOR_ONLINE_CANDIDATE`**

> ⚠️ **注意**: P1.2 調整 P1.1 分類框架 — 此策略不是 RETIRED tombstone candidate，而是 ACTIVE ONLINE candidate。需要的是**加入 registry 作為 ONLINE**，不是建 tombstone。

**理由:**
1. ✅ **曾明確作為 live/prediction strategy** — 有 VALID prediction_run, PENDING items
2. ✅ **不是 alias/duplicate** — 與 canonical 16 中任何 POWER_LOTTO strategy 均不同
3. ✅ **應被 replay 產品記錄** — PENDING predictions eligible for P2 backfill
4. ✅ **不是 false positive** — 在 RSM engine 中有 stable code registration
5. ✅ **目前仍在 ONLINE 狀態** — prediction_run VALID, items PENDING (not expired)

**Recommended lifecycle:** `ONLINE`  
**Recommended replay display semantics:** `NO_DATA` (ONLINE 但無 strategy_prediction_replays rows)

### 風險旗標
- `no_registry_entry` — 未在 canonical registry 中
- `currently_active_pending_predictions` — 目前有 3 個 PENDING predictions
- `critical_governance_gap` — live strategy without registry governance
- `live_production_no_formal_lifecycle` — 運作中但無正式 lifecycle 定義
- `p11_db_scan_column_mismatch` — P1.1 因 column-name 不一致導致誤判「0 rows」

### Operator 行動要求
**優先級: HIGH**  
加入 `replay_strategy_registry.py`：
```python
strategy_id="fourier_rhythm_3bet",
strategy_name="fourier_rhythm_3bet",
lottery_type="POWER_LOTTO",
lifecycle_status="ONLINE",
supported_lottery_types=["POWER_LOTTO"],
# min_history: 根據 fourier_3bet predict_func 要求設定
```

---

## 5. ts3_regime_3bet 決策

### 分類結果

**決策: `PRODUCT_DENOMINATOR_ONLINE_CANDIDATE`**

> ⚠️ **注意**: 同 fourier_rhythm_3bet — 此策略不是 RETIRED tombstone candidate，而是 ACTIVE ONLINE candidate。

**理由:**
1. ✅ **曾明確作為 live/prediction strategy** — 3 個 BIG_LOTTO prediction_runs, 9 PENDING items
2. ✅ **不是 alias/duplicate** — regime-switching ts3 variant，與 biglotto_ts3_acb_4bet 和 biglotto_ts3_markov_freq_5bet 均不同
3. ✅ **應被 replay 產品記錄** — memory/lessons 明確列為大樂透維護模式保留生產策略
4. ✅ **不是 false positive** — strategy_catalog 和 memory/lessons 雙重確認為生產策略
5. ✅ **目前仍在 ONLINE 狀態** — 有 VALID + RECONSTRUCTED prediction_runs

**Recommended lifecycle:** `ONLINE`  
**Recommended replay display semantics:** `NO_DATA` (ONLINE 但無 strategy_prediction_replays rows)

### 風險旗標
- `no_registry_entry` — 未在 canonical registry 中
- `currently_active_pending_predictions` — 目前有 9 個 PENDING predictions (3 draws)
- `critical_governance_gap` — live strategy without registry governance
- `live_production_no_formal_lifecycle` — 運作中但無正式 lifecycle 定義
- `multiple_active_runs_across_draws` — 跨 3 個 draws 都有 PENDING items
- `p11_db_scan_column_mismatch` — P1.1 因 column-name 不一致導致誤判「0 rows」

### Operator 行動要求
**優先級: HIGH**  
加入 `replay_strategy_registry.py`：
```python
strategy_id="ts3_regime_3bet",
strategy_name="ts3_regime_3bet",
lottery_type="BIG_LOTTO",
lifecycle_status="ONLINE",
supported_lottery_types=["BIG_LOTTO"],
# min_history: 根據 ts3 regime-switching predict_func 要求設定
```

---

## 6. Clean Denominator 最終建議

### 最終鎖定: **71 strategies**

```
Clean denominator = canonical_16 + P1.1_product_denominator_53 + P1.2_online_candidates_2
                  = 16            + 53                           + 2
                  = 71 strategies
```

**詳細分解:**

| 類別 | Count | 說明 |
|------|-------|------|
| Canonical registry (ONLINE + DB rows) | 6 | 已有 strategy_prediction_replays rows |
| Canonical registry (REJECTED + DB rows) | 4 | PARTIAL (有 rows 但非 ONLINE) |
| Canonical registry (RETIRED, V3 tombstone) | 5 | RETIRED (0 replay rows) |
| Canonical registry (OBSERVATION, 0 replay rows) | 1 | OBSERVATION |
| P1.1 PRODUCT_DENOMINATOR (REJECTED artifact-only) | 53 | 0 replay rows |
| P1.2 ONLINE candidates (fourier_rhythm_3bet, ts3_regime_3bet) | 2 | 0 replay rows (PENDING items) |
| **Total clean denominator** | **71** | |

**已排除項目 (不進分母):**
- 15 RESEARCH_ARCHIVE (PR #104)
- 3 DUPLICATE_OR_SUPERSEDED (PR #104)
- 0 NON_STRATEGY_ARTIFACT

---

## 7. Coverage Rate 更新

| Metric | P1.1 結果 | P1.2 更新後 |
|--------|----------|------------|
| Clean denominator | 69 | **71** |
| COVERED (ONLINE + strategy_prediction_replays rows) | 6 | **6** |
| PARTIAL (REJECTED/OBS + strategy_prediction_replays rows) | 4 | **4** |
| COVERED rate | 6/69 = 8.7% | **6/71 = 8.5%** |
| COVERED+PARTIAL rate | 10/69 = 14.5% | **10/71 = 14.1%** |
| Expected post-backfill (if P2 backfills NOD rows) | — | **8/71 = 11.3%** |

> **Post-backfill note**: fourier_rhythm_3bet (1 run × 3 bets) and ts3_regime_3bet (3 runs × 3 bets) have PROMOTABLE entries in the p2 dry run manifest. If P1.3 adds them to registry as ONLINE and the P2 backfill runs, COVERED count may increase from 6 to up to 8.

---

## 8. Operator 手動確認需求

### 需要確認的項目

**兩個策略均需要 `operator_followup_required=true`**, 原因：

| 確認項目 | fourier_rhythm_3bet | ts3_regime_3bet |
|----------|--------------------|--------------------|
| 確認仍應保持 ONLINE (未被棄用) | ✅ 需要確認 | ✅ 需要確認 |
| 確認 min_history 要求 (供 registry 使用) | ✅ 需要確認 | ✅ 需要確認 |
| 確認 predict_func 對應 (registry adapter) | ✅ 需要確認 | ✅ 需要確認 |
| 確認 P2 backfill 是否應補齊 PENDING items | ✅ 需要確認 | ✅ 需要確認 |

### 這不是阻擋 P1.3 的項目

P1.3 registry ONLINE proposal 可以基於 P1.2 evidence 建立草稿，但最終 registry 程式碼需要 operator 確認 predict_func 綁定方式。

---

## 9. 下一步建議

### 立即 (P1.3): Registry ONLINE Proposal

建立 `replay_strategy_registry.py` 的 PR，新增 2 個 ONLINE strategies：
- `fourier_rhythm_3bet` (POWER_LOTTO, ONLINE)
- `ts3_regime_3bet` (BIG_LOTTO, ONLINE)

此步骤需要 operator 確認 `predict_func` 與 `min_history` 綁定。

### 接下來 (P2): Replay Backfill

P1.3 完成後，執行 P2 replay backfill dry run：
- 重跑 p2 manifest 但允許 `runtime_write_allowed=true`
- 會補齊 `strategy_prediction_replays` rows for:
  - `fourier_rhythm_3bet`: run_id=168 (3 bets, POWER_LOTTO)
  - `ts3_regime_3bet`: run_ids=167,174,175 (9 bets, BIG_LOTTO)
- Expected COVERED count 提升: 6 → 8

### 平行推進 (P2 Replay Page): 不需等待 P1.3

Replay page UI 可用 canonical 16 作為初始分母先開始開發。
P1.3 + P2 backfill 完成後，replay page 分母可擴充至 71。

---

## 10. Safety Confirmation

| 非目標 | 確認 |
|--------|------|
| 未新增策略 | ✅ |
| 未補 replay row | ✅ |
| 未寫 DB | ✅ |
| 未修改 API / UI / backend | ✅ |
| 未跑 backtest | ✅ |
| 未修改 registry | ✅ |
| 未 merge PR | ✅ |
| 未把不足證據策略強制進 PRODUCT_DENOMINATOR | ✅ (兩個均有充分證據) |
| JSON valid | ✅ |
| No forbidden staged artifacts | ✅ |

---

## Appendix: P1.1 NOD 根本原因分析

**問題**: P1.1 DB scan 結論「0 rows in ALL tables」

**根本原因**: P1.1 scan 遍歷所有 tables，對每個 table 用 `WHERE strategy_id=?` 查詢。但：
- `prediction_items` table → 無 `strategy_id` column（有 `run_id`, `strategy_name`）
- `prediction_runs` table → 無 `strategy_id` column（有 `strategy_name`）

因此這兩個 table 被 PRAGMA table_info 過濾掉（因為 `strategy_id not in cols`），導致實際上有資料的 tables 被跳過。

**只有 `strategy_prediction_replays` table 有 `strategy_id` column**，而這個 table 確實有 0 rows for both strategies（正確結論）。

**影響**: P1.1 分類為 NEEDS_OPERATOR_DECISION 是**正確的**（有充分理由不確定），但風險描述偏輕（「was_live_no_tombstone」）。P1.2 更新後的風險描述是「critically_active_no_registry」。

**P1.1 行動的正確性**: 使用 NEEDS_OPERATOR_DECISION 分類是正確的決策 — P1.1 的謹慎分類機制有效地捕獲了這個治理缺口。
