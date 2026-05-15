我要做一個新功能頁面類似預測追蹤頁面，然後將大樂透/威力彩/539的所有期數都列出來可以查詢頁面需要有實際開獎號碼和策略預測獎號如同預測追蹤頁面一樣，差別的是我可以點選一個功能選項選擇系統上所有已有的策略，然後就顯示該策略的所有期數預測號碼以及實際號碼如同預測追蹤頁面顯示一樣ˋ
，這表示系統需要先將所有策略進行歷史回測並記錄下來，以上需求你有什麼問題嗎
A，但是需要有資料噎，資料在哪個地方產生？我想目前所有策略先做一注的預測（含reject，可以註明reject）
有，我先確認你的需求理解，這次你要做的不是 governance，而是 **LotteryNew 的新功能頁面 + 歷史策略預測結果資料化**。

## 我理解的目標

你要新增一個頁面，功能類似目前的「預測追蹤頁面」，但差別是：

目前預測追蹤頁面可能偏向「目前策略 / 當期 / 最新預測追蹤」。

你想新增的是：

> 查詢任一彩種、任一策略，在所有歷史期數上的「策略預測號碼 vs 實際開獎號碼」。

也就是一個 **策略歷史預測追蹤查詢頁**。

---

## 頁面應該支援

### 彩種

至少包含：

```text
大樂透
威力彩
今彩539
```

### 查詢條件

頁面上要可以選：

```text
彩種
策略
期數 / 日期區間
可能還有：只看中獎數、只看命中幾碼以上
```

### 顯示內容

每一期至少要顯示：

```text
期別
開獎日期
實際開獎號碼
特別號 / 第二區號碼，如果有
策略預測號碼
命中號碼
命中數
策略名稱
策略版本
回測產生時間
```

大樂透可能要顯示：

```text
實際：6 個號碼 + 特別號
預測：5 注或 N 注號碼
命中：每注命中幾碼
```

威力彩要顯示：

```text
第一區實際號碼
第二區實際號碼
第一區預測號碼
第二區預測號碼
命中狀態
```

539 要顯示：

```text
實際 5 碼
預測 5 碼或多組號碼
命中數
```

---

## 後端需要先做的事情

你說得對，這個頁面不能只靠前端做。

系統需要先把：

```text
所有既有策略 × 所有歷史期數 × 所有彩種
```

跑過一次歷史回測，並把每一期的策略預測結果記錄下來。

也就是要新增一個資料層，類似：

```text
strategy_prediction_history
```

或：

```text
historical_strategy_predictions
```

每筆記錄代表：

> 某一個策略，在某一個彩種、某一期，使用該期之前的資料，產生的預測號碼，以及該期實際開獎結果與命中結果。

---

## 這裡有一個很重要的原則

這個功能不能變成 leakage。

所以每一期的策略預測必須遵守：

```text
預測第 N 期時，只能使用第 N-1 期以前的資料
```

不能用到目標期本身，也不能用到目標期之後的資料。

因此這個功能本質上是：

```text
Walk-forward historical prediction replay
```

不是單純把策略拿去套所有資料。

---

## 我目前有幾個關鍵問題

### 1. 你要這個頁面叫什麼？

我建議名稱可以是：

```text
策略歷史追蹤
```

或：

```text
策略回測追蹤
```

或：

```text
歷史預測查詢
```

我個人建議用：

```text
策略歷史追蹤
```

因為它比較像你說的「預測追蹤頁面」的延伸。

---

### 2. 顯示的是「所有策略」還是「已啟用策略」？

你說「系統上所有已有的策略」，這裡要確認是：

```text
A. 所有 strategy registry 裡的策略
B. 只有 active / enabled 策略
C. 包含 retired / archived 策略
D. 只包含已通過 governance 的策略
```

我建議第一版先做：

```text
所有已註冊策略，但標示狀態：ACTIVE / EXPERIMENTAL / RETIRED
```

不要只顯示 active，否則歷史分析會不完整。

---

### 3. 每個策略的預測注數是否固定？

例如大樂透：

```text
TS3+M+FO 可能是 5 注
其他策略可能是 1 注、3 注、10 注
```

頁面要支援：

```text
一個期數底下多組預測號碼
```

所以資料表不能假設只有一組號碼。

---

### 4. 要不要顯示統計摘要？

除了每一期列表，我建議頁面上方加策略摘要：

```text
總回測期數
平均命中數
最高命中數
命中 3 碼以上次數
命中 4 碼以上次數
命中 5 碼以上次數
是否有通過 governance eval
classification
```

但要注意不能寫成「提高中獎率」，只能寫成歷史 replay 統計。

---

### 5. 這個功能要不要支援重新產生歷史預測？

我建議分兩階段。

第一階段：

```text
只做 batch job / CLI 產生歷史預測資料
頁面只讀取已產生結果
```

第二階段再做：

```text
後台按鈕重新產生某策略 / 某彩種的歷史 replay
```

因為如果一開始就讓 UI 觸發全部策略回測，可能會太重，也容易造成資料污染。

---

## 我建議的功能拆分

### P0 — 先做資料產生與查詢頁

這一輪最小可行版本應該做：

```text
1. 建立 historical strategy prediction replay job
2. 建立 prediction history 儲存格式
3. 針對大樂透 / 威力彩 / 539 支援查詢
4. 新增策略歷史追蹤頁面
5. 頁面可選彩種 + 策略
6. 顯示所有期數：實際號碼 vs 預測號碼 vs 命中結果
```

---

### P1 — 再做統計摘要與篩選

下一輪再補：

```text
命中數篩選
日期區間
策略版本比較
匯出 CSV
依命中數排序
只看命中 3 碼以上
```

---

### P2 — 再做 governance / eval metadata 串接

之後再補：

```text
hypothesis_id
strategy_eval classification
leakage check status
permutation status
OOS status
report link
```

---

## 我建議下一輪 prompt 的方向

下一輪不要寫成「找 edge」，也不要寫成「治理強化」。

應該寫成：

```text
P0-FEATURE — Strategy Historical Prediction Tracker
```

核心任務：

> 建立一個可以查詢所有彩種、所有策略、所有歷史期數的預測結果追蹤頁，並先用 walk-forward replay job 產生歷史策略預測資料。

---

## 我會特別要求 Agent 注意這幾點

1. 不得用未來資料產生歷史預測。
2. 預測第 N 期只能使用 N-1 期以前資料。
3. 頁面顯示的是 replay result，不是正式 edge claim。
4. 不得宣稱提高中獎率。
5. 不得改 active strategy state。
6. 不得寫 production outcome。
7. 若策略無法 replay，要標示 `REPLAY_UNAVAILABLE`，不要硬補。
8. 若資料不足，要標示 `INSUFFICIENT_HISTORY`。
9. 統計結果只能叫 historical replay stats，不可叫 signal。
10. 頁面要能支援多注預測。

---

## 我目前需要你確認的只有一件事

這個頁面你想先做成：

```text
A. 純查詢頁：先由 CLI / batch job 產生歷史預測資料，頁面只讀資料
```

還是：

```text
B. 查詢頁 + 頁面上可以按「重新產生歷史回測」
```

我建議先選 **A**，比較安全，也比較容易一次做對。
A，但是需要有資料噎，資料在哪個地方產生？我想目前所有策略先做一注的預測（含reject，可以註明reject）

對，選 A 的話，資料必須先由 後端 CLI / batch job 產生並落地，前端頁面只讀取這些 replay 結果。

你這次補充的需求很關鍵：

目前所有策略先做「一注」的歷史預測，包含 reject，也要記錄並顯示 reject reason。

這樣第一版會比較穩，而且不會被多注策略複雜度卡住。

建議資料產生位置

我建議不要放在 outputs/ 當主資料來源，因為前面治理已定義：

outputs/ 不得作為 governance source-of-truth

所以資料產生應分兩層：

1. 真正可查詢資料：放 DB 或 canonical data file

如果 LotteryNew 目前已有 DB，建議新增資料表：

strategy_prediction_replays

如果目前沒有穩定 DB，第一版可以先用 canonical JSONL 檔案：

data/replay/strategy_prediction_replays.jsonl

但要明確標示：

data/replay/ = application data source
outputs/ = report artifacts only

不要把 outputs/ 當頁面資料來源。

2. 產生報告：可以放 outputs

CLI 跑完後可以產生摘要報告：

outputs/replay/strategy_prediction_replay_summary_YYYYMMDD.md
outputs/replay/strategy_prediction_replay_summary_YYYYMMDD.json

但這只是 audit/report，不是前端查詢主來源。

我建議第一版資料流
已註冊策略
   ↓
historical replay CLI
   ↓
逐彩種、逐期數 walk-forward 產生一注預測
   ↓
若策略 reject，也記錄 reject
   ↓
寫入 canonical replay store
   ↓
API 查詢 replay store
   ↓
前端策略歷史追蹤頁顯示
每一期資料應該長這樣

第一版每個策略每一期只記錄一注：

{
  "lottery_type": "lotto649",
  "draw_id": "202600001",
  "draw_date": "2026-01-01",
  "strategy_id": "ts3_m_fo",
  "strategy_name": "TS3+M+FO",
  "strategy_version": "v1",
  "replay_status": "PREDICTED",
  "reject_reason": null,
  "predicted_numbers": [1, 8, 12, 23, 31, 42],
  "predicted_special": null,
  "actual_numbers": [3, 8, 12, 19, 28, 42],
  "actual_special": 15,
  "hit_numbers": [8, 12, 42],
  "hit_count": 3,
  "generated_at": "2026-05-07T..."
}

如果 reject：

{
  "lottery_type": "lotto649",
  "draw_id": "202600002",
  "strategy_id": "ts3_m_fo",
  "replay_status": "REJECTED",
  "reject_reason": "INSUFFICIENT_HISTORY",
  "predicted_numbers": [],
  "actual_numbers": [2, 7, 11, 18, 25, 39],
  "hit_numbers": [],
  "hit_count": 0
}
replay_status 建議

第一版至少支援：

PREDICTED
REJECTED
STRATEGY_UNAVAILABLE
INSUFFICIENT_HISTORY
REPLAY_ERROR

其中：

PREDICTED：有產生一注預測
REJECTED：策略自己拒絕下注 / 拒絕預測
STRATEGY_UNAVAILABLE：該策略不支援該彩種
INSUFFICIENT_HISTORY：歷史資料不足，無法產生預測
REPLAY_ERROR：執行錯誤，但不可中斷整批 replay
這個功能的正確定位

這不是 strategy eval，也不是宣稱 edge。

它應該叫：

Historical Prediction Replay

中文可以叫：

策略歷史預測回放

重點是：

回放每個策略在每一期如果只用過去資料，當時會產生什麼一注預測，並對照實際開獎結果。

建議下一輪 prompt

下面這版是你現在真正要的需求，不再偏 governance，也不會壞掉。

# ROLE
你是 LotteryNew 的 Senior Full-Stack Feature Agent，直接向 CTO 上級主管回報。

# TASK
任務名稱：

P0-FEATURE — Strategy Historical Prediction Replay Page

# CONTEXT
LotteryNew 目前已完成 governance hardening，包括：

- Hypothesis Registry
- Strategy Eval Framework
- Circular Bias Gate
- Leakage Detector
- RollingBacktester leakage integration
- Strategy Eval Enforcement Layer
- Classification Guard
- Module Boundaries
- Forbidden Strategy Patterns trusted wiki

本輪任務不是新增策略，不是重新尋找 edge，也不是 strategy mining。

本輪目標是建立一個新功能頁面，類似現有「預測追蹤頁面」，但可以查詢：

- 大樂透
- 威力彩
- 今彩539

所有歷史期數中，指定策略的「一注預測號碼」與「實際開獎號碼」對照。

# CORE OBJECTIVE
建立 Strategy Historical Prediction Replay 功能。

使用者可以在頁面上：

1. 選擇彩種
2. 選擇系統已有策略
3. 查詢該策略在所有歷史期數的一注預測結果
4. 看到每一期的：
   - 期別
   - 開獎日期
   - 實際開獎號碼
   - 策略預測號碼
   - 命中號碼
   - 命中數
   - replay 狀態
   - reject reason，如果策略 reject

# IMPORTANT PRODUCT REQUIREMENT
目前所有策略先只做「一注」預測。

即使某策略原本支援多注，本輪也只取第一注或最小 canonical one-bet output。

若策略在某一期 reject，不能略過該期，必須記錄並顯示：

- replay_status = REJECTED
- reject_reason

# DATA GENERATION REQUIREMENT
此頁面採用 A 方案：

頁面只讀取已產生的 replay 資料。

必須新增 CLI / batch job 先產生歷史 replay 資料。

不得由前端頁面即時觸發所有策略回測。

# DATA SOURCE RULE
不得把 outputs/ 作為前端查詢的 source-of-truth。

建議新增 canonical replay data source：

如果專案已有 DB：
- 建立 strategy_prediction_replays 資料表

如果專案目前沒有穩定 DB：
- 建立 data/replay/strategy_prediction_replays.jsonl
- 建立 data/replay/strategy_prediction_replays.index.json，如有需要

outputs/ 只能用來放 CLI 產生的摘要報告，不可作為頁面查詢主資料來源。

# REQUIRED WORK

## Part A — Inspect Existing Prediction Tracking Page
先閱讀現有「預測追蹤頁面」相關檔案，包含：

- route / page component
- API endpoint
- data model
- display table
- strategy prediction format

找出可以重用的 UI pattern 與資料格式。

不要大改現有預測追蹤頁面。

## Part B — Strategy Registry / Strategy Discovery
找出目前系統已有策略的來源。

建立一個可供 replay job 使用的 strategy discovery adapter。

需求：

1. 能列出所有已有策略
2. 每個策略至少有：
   - strategy_id
   - strategy_name
   - strategy_version
   - supported_lottery_types
   - status，如 ACTIVE / EXPERIMENTAL / RETIRED，若目前沒有就先用 UNKNOWN
3. 若策略不支援某彩種，replay job 要記錄 STRATEGY_UNAVAILABLE，不可直接略過

## Part C — Historical Replay Data Model
建立歷史 replay result 格式。

每筆資料代表：

某一個 strategy 在某一個 lottery_type 的某一期，使用該期以前資料產生的一注預測，並與實際開獎號碼對照。

每筆至少包含：

- lottery_type
- draw_id
- draw_date
- strategy_id
- strategy_name
- strategy_version
- replay_status
- reject_reason
- predicted_numbers
- predicted_special_numbers 或 predicted_power_number，如適用
- actual_numbers
- actual_special_numbers 或 actual_power_number，如適用
- hit_numbers
- hit_count
- special_hit_count 或 power_hit，如適用
- training_window_start_draw_id，如可取得
- training_window_end_draw_id，如可取得
- generated_at
- replay_engine_version

支援 replay_status：

- PREDICTED
- REJECTED
- STRATEGY_UNAVAILABLE
- INSUFFICIENT_HISTORY
- REPLAY_ERROR

## Part D — Historical Replay CLI / Batch Job
新增 CLI / batch job，例如：

tools/replay/generate_strategy_prediction_replays.py

或依專案既有架構放置等價位置。

CLI 需求：

1. 支援參數：
   - --lottery-type
   - --strategy-id
   - --all-lotteries
   - --all-strategies
   - --limit-draws
   - --output-format jsonl
   - --dry-run

2. 預設不可寫 production outcome。

3. 對每一個 target draw，必須只使用 target draw 之前的資料產生預測。

4. 每個策略每期只產生一注。

5. 若策略回傳多注，只取第一注，並在 metadata 標示 one_bet_projection = true。

6. 若策略 reject，必須寫入 REJECTED 與 reject_reason。

7. 若資料不足，必須寫入 INSUFFICIENT_HISTORY。

8. 若策略不支援該彩種，必須寫入 STRATEGY_UNAVAILABLE。

9. 若單一策略或單一期錯誤，必須寫入 REPLAY_ERROR，不可讓整批中斷。

10. 跑完後寫入 canonical replay data source。

11. 可額外產生 outputs/replay/ summary report，但 outputs 不可作為查詢主來源。

# LEAKAGE SAFETY RULE
預測第 N 期時，只能使用第 N-1 期以前資料。

不可使用：

- 第 N 期開獎號碼作為 feature
- 第 N 期之後資料
- 全歷史資料做回頭最佳化
- historical-pool max-hit
- post-hoc mining

本功能是 historical replay，不是 edge claim。

# Part E — API Endpoint
新增 API endpoint，供前端查詢 replay 資料。

建議路徑依現有架構決定，例如：

/api/strategy-replay

或：

/api/prediction-history/replay

API 至少支援 query：

- lottery_type
- strategy_id
- page
- page_size
- min_hit_count
- replay_status
- draw_start
- draw_end

API 回傳：

- summary
- rows
- pagination
- available_lottery_types
- available_strategies

summary 至少包含：

- total_draws
- predicted_count
- rejected_count
- unavailable_count
- error_count
- average_hit_count
- max_hit_count

注意：
summary 只能命名為 historical replay stats，不得命名為 signal / edge / performance proof。

# Part F — Frontend Page
新增頁面，類似現有預測追蹤頁面。

頁面名稱建議：

策略歷史追蹤

或英文：

Strategy Historical Replay

頁面需求：

1. 彩種 selector：
   - 大樂透
   - 威力彩
   - 今彩539

2. 策略 selector：
   - 顯示所有已有策略
   - 顯示 strategy status，如 ACTIVE / EXPERIMENTAL / RETIRED / UNKNOWN

3. 篩選：
   - replay_status
   - min_hit_count
   - draw date / draw id range，如容易實作

4. 表格欄位：
   - 期別
   - 開獎日期
   - 實際開獎號碼
   - 策略預測號碼
   - 命中號碼
   - 命中數
   - replay_status
   - reject_reason

5. 若 replay_status = REJECTED：
   - 預測號碼欄顯示「策略拒絕」
   - reject_reason 顯示原因

6. 若 replay_status = STRATEGY_UNAVAILABLE：
   - 顯示「策略不支援此彩種」

7. 若 replay_status = INSUFFICIENT_HISTORY：
   - 顯示「歷史資料不足」

8. 若 replay_status = REPLAY_ERROR：
   - 顯示錯誤摘要，不顯示完整 stack trace

9. 頁面上方顯示 summary cards：
   - 總期數
   - 已預測期數
   - reject 期數
   - 平均命中數
   - 最高命中數

10. 頁面需明確標示：
   「本頁為歷史預測回放，不代表提高中獎率，也不是正式 edge claim。」

# Part G — Tests
新增或更新測試。

至少包含：

1. Replay CLI tests：
   - 只使用 target draw 之前資料
   - 多注策略只取第一注
   - reject 會被記錄
   - unsupported lottery 會被記錄
   - insufficient history 會被記錄
   - single draw error 不會中斷整批

2. API tests：
   - 可以依 lottery_type + strategy_id 查詢
   - summary 正確
   - replay_status filter 正確
   - min_hit_count filter 正確

3. Frontend tests，如專案已有：
   - 頁面可顯示彩種 selector
   - 頁面可顯示策略 selector
   - 表格可顯示實際號碼與預測號碼
   - reject 狀態可顯示 reject reason

4. Governance safety tests：
   - outputs/ 不可作為 replay API source-of-truth
   - replay result 不得產出 SIGNAL / NO_SIGNAL / NO_VALIDATED_EDGE
   - replay page 不得宣稱提高中獎率

# VALIDATION
請依專案實際架構執行相關測試。

至少執行：

python -m pytest tests/test_strategy_prediction_replay.py tests/test_strategy_prediction_replay_api.py -q

如果有前端測試，請執行對應 npm test 或 playwright test。

另外執行既有 governance tests，避免破壞前面完成的 hard-lock：

python -m pytest tests/test_strategy_eval_enforcement.py tests/test_classification_guard.py tests/test_backtest_framework_leakage_integration.py tests/test_strategy_eval.py tests/test_no_circular_match.py tests/test_hypothesis_registry.py tests/test_module_boundaries.py -q

# HARD RULES
- 本輪不新增彩票策略。
- 本輪不做 strategy mining。
- 本輪不做 edge discovery claim。
- 不得宣稱提高中獎率。
- 不得修改 active strategy state。
- 不得寫 production outcome。
- 不得 auto promotion。
- 不得 auto rollback。
- 預測第 N 期只能使用第 N-1 期以前資料。
- 不得把 outputs/ 當作前端查詢 source-of-truth。
- replay 結果不得產生 SIGNAL / NO_SIGNAL / NO_VALIDATED_EDGE classification。
- reject 不可被略過，必須被記錄。
- 每個策略每期第一版只產生一注。

# FINAL REPORT FORMAT
請回報：

## Completed
## Files Created / Modified
## Replay Data Source
## Strategy Coverage
## Lottery Coverage
## Reject Handling
## API Result
## Frontend Result
## Validation
## Leakage Safety
## Remaining Gaps
## Final Marker

完成 marker：

P0_FEATURE_STRATEGY_HISTORICAL_REPLAY_PAGE_ONE_BET_VERIFIED

這版的重點是：先讓資料能產生、能查、能顯示，而且包含 reject。
等這版完成後，下一輪再把「多注顯示、策略比較、匯出、統計摘要深化」加上去。
