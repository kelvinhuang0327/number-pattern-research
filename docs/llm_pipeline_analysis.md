# LLM Pipeline Analysis
# Phase 1 — Prediction Pipeline Mapping & LLM Integration Points
# 今彩539 / 大樂透 / 威力彩 彩票預測系統
# 2026-03-15

---

## 現有系統 Pipeline 全圖

```
┌─────────────────────────────────────────────────────────────────┐
│  Stage 0: Data Ingestion                                        │
│  lottery_v2.db (SQLite)                                         │
│  └─ 539: 5810期 / BL: 2115期 / PL: 1892期                      │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│  Stage 1: Feature Engineering                                   │
│  ├─ ACB Score: freq_deficit×0.4 + gap_score×0.6 + boundary     │
│  ├─ MidFreq Score: 0.5~1.5x expected frequency window          │
│  ├─ Markov Transition: P(n_t | n_{t-1}) 轉移概率               │
│  ├─ Fourier Rhythm: FFT 週期分析 (window=500)                   │
│  └─ Zone Counts: Z1/Z2/Z3 各區球數 [已確認白噪音]              │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│  Stage 2: Signal Detection                                      │
│  ├─ 滾動策略監控 (RSM): 30/100/300期三窗口 Edge 計算           │
│  ├─ Permutation Test: 200次隨機排列 p-value                    │
│  ├─ DriftDetector: PSI 分布偏移偵測                            │
│  └─ HypothesisRegistry: 假設狀態追蹤                           │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│  Stage 3: Strategy Generation                                   │
│  ├─ StrategyCoordinator (7 agents)                             │
│  │   midfreq / acb / consensus / markov / fourier /            │
│  │   markov2 / weibull_gap                                     │
│  ├─ quick_predict.py: 各彩種路由函數                           │
│  └─ Per-agent tracking: 100期命中率監控                        │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│  Stage 4: Backtesting & Validation                              │
│  ├─ Walk-forward OOS: 150 / 500 / 1500期三窗口                 │
│  ├─ McNemar Test: 策略對比顯著性                               │
│  ├─ backtest_async.py: 異步回測框架                            │
│  └─ 三窗口全正 + perm p<0.05 + Sharpe>0 → 採納門檻            │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│  Stage 5: Prediction Output                                     │
│  ├─ quick_predict.py: 產出預測注組                             │
│  ├─ prediction_logger.py: JSONL 記錄 + 開獎後 update_result()  │
│  └─ LLM Analyzer (mock): 事後分析摘要 [目前無效]              │
└─────────────────────────────────────────────────────────────────┘
```

---

## LLM 整合點分析

### 整合原則
**LLM 只能在「統計驗證之前」或「統計驗證之後」介入，不得替代統計驗證本身。**

```
資料 → [特徵工程] → [LLM: 假設生成] → [統計驗證] → [LLM: 失敗分析] → 決策
          ↑                                                ↓
          └──────────── [LLM: 特徵改進建議] ←─────────────┘
```

---

### 各 Stage 整合評估

| Stage | LLM 介入 | 價值 | 風險 | 建議 |
|-------|---------|------|------|------|
| 0 Data Ingestion | ❌ | 無 | 高（直接操作數據） | 不介入 |
| 1 Feature Engineering | ✅ 建議新特徵 | 高 | 中（需驗證） | **主要介入點** |
| 2 Signal Detection | ⚠️ 解讀 RSM 趨勢 | 中 | 高（誤讀白噪音） | 僅輔助解讀 |
| 3 Strategy Generation | ⚠️ 組合建議 | 中 | 中 | 策略候選生成 |
| 4 Backtesting | ❌ | 無 | 極高（繞過驗證） | **嚴禁介入** |
| 5 Prediction Output | ✅ 失敗分析 | 高 | 低 | **主要介入點** |

---

### 最高價值介入點（3個）

#### 介入點 A：Feature Engineering 上游（Stage 1 前）
**輸入**：已驗證信號列表 + 已拒絕信號列表 + 拒絕原因
**LLM 任務**：提出「與現有信號正交」的新特徵假設
**輸出**：結構化假設 → 進入回測流程

為何有效：LLM 可檢索統計學/信號處理文獻中的方法，系統性提出人工難以枚舉的候選特徵

#### 介入點 B：Failure Pattern Analysis（Stage 5 後）
**輸入**：失敗期次的特徵值、信號一致性、開獎號碼特徵
**LLM 任務**：識別失敗的結構性原因，生成改進假設
**輸出**：具體的特徵改進方向 → 回到 Stage 1

為何有效：LLM 擅長整合多維描述性信息，人工分析逐期失敗效率低

#### 介入點 C：Research Loop 協調（新增層）
**輸入**：全量回測結果 + RSM 趨勢 + 已結案研究列表
**LLM 任務**：優先排序下一步研究方向，避免重複研究
**輸出**：帶優先級的研究隊列

---

## 不介入清單（防止幻覺污染）

以下操作 LLM 嚴禁執行：
- 直接修改 ACB/MidFreq 權重
- 對單期開獎結果做因果解釋（如「因為#05連三期所以...」）
- 在缺乏回測的情況下聲稱「某特徵有效」
- 解讀白噪音序列（Zone/Sum/Streak）為有效信號

---

## 技術架構建議

```python
# 建議的 LLM 整合層
class LLMResearchAssistant:
    def propose_hypotheses(self, validated_signals, rejected_signals) -> List[Hypothesis]
    def analyze_failure_batch(self, failed_periods) -> FailureReport
    def prioritize_research_queue(self, backtest_results) -> List[ResearchItem]
    def generate_feature_code(self, hypothesis: Hypothesis) -> str  # 生成回測腳本

    # 嚴禁
    # def predict_numbers(...)  # 永遠不實作
    # def modify_backtest_results(...)  # 永遠不實作
```
