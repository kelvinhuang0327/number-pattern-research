# LLM Hypothesis Engine Design
# Phase 2 — Structured Hypothesis Generation
# 2026-03-15

---

## 設計原則

**假設生成是 LLM 的核心貢獻**：LLM 不做統計，只做假設。每個假設必須是「可回測的命題」，
且與已驗證/已拒絕信號有明確的差異化論據。

---

## Hypothesis 資料結構

```python
@dataclass
class Hypothesis:
    id: str                    # H001, H002...
    name: str                  # 簡短名稱
    description: str           # 假設內容
    signal_type: str           # 'frequency' / 'structural' / 'interaction' / 'temporal'
    inspired_by: str           # 來源（已驗證信號、文獻、失敗分析）
    orthogonal_to: List[str]   # 與哪些現有信號正交
    candidate_feature_code: str  # 建議的特徵計算偽代碼
    priority: int              # 1(最高) ~ 5(最低)
    estimated_lift: str        # 'high/medium/low'（LLM 的定性評估）
    rejection_conditions: str  # 何種情況下應拒絕（提前定義）
    status: str                # 'pending' / 'in_backtest' / 'pass' / 'rejected'
```

---

## Prompt 設計（生成假設用）

```
系統背景：
- 彩票：今彩539（1-39 選5）
- 已驗證信號：ACB（頻率偏差 × 間隔分數）, MidFreq（中頻率號碼）
- 已拒絕信號：Zone分布、Streak連續出現、Sum均值回歸、ZPI區域壓力
- 數據期數：5810期（2007-2026）
- 已確認：Zone/Sum/Streak 序列為統計白噪音（Ljung-Box 全不顯著）

任務：
提出 5 個新的統計信號假設，每個假設必須：
1. 與已驗證信號（ACB/MidFreq）正交（不是同一機制的重複）
2. 與已拒絕信號有明確區別（說明為何此次不同）
3. 可量化為單一數值特徵
4. 有統計文獻或理論支持（說明來源）
5. 預先定義拒絕條件

格式：JSON 陣列，每個假設包含上述所有欄位。
不得包含：Zone分布、Sum值、連號對、Streak（已確認無效）
```

---

## 預設假設池（人工種子，供 LLM 擴展）

### 類型 1：頻率互動（Frequency Interaction）

| ID | 假設 | 信號機制 | 優先度 |
|----|------|---------|--------|
| H001 | ACB × MidFreq 乘積分數 | 同時滿足兩個條件的號碼 | P1 |
| H002 | 號碼間距的 entropy（均勻度） | 開獎號碼間距分布熵值 | P2 |
| H003 | 配對共現異常（Pairwise Co-occurrence） | P(i,j) vs P(i)×P(j) Lift >1.3 | P2 |
| H004 | 號碼族群 Cluster（K-means on frequency） | 同族群號碼的輪替模式 | P3 |

### 類型 2：時序結構（Temporal Structure）

| ID | 假設 | 信號機制 | 優先度 |
|----|------|---------|--------|
| H005 | 條件 ACB（前期特定號碼出現後的 ACB） | Markov × ACB 條件化 | P1 |
| H006 | 長週期 Fourier（w=1000 vs w=500） | 更長週期的頻率模式 | P2 |
| H007 | 近期頻率變化率（ΔACB = ACB_30 - ACB_300） | 頻率動量（非水準） | P2 |
| H008 | 號碼「退休」偵測（gap > 2×平均間隔） | 超長缺席後的回歸概率 | P3 |

### 類型 3：非線性組合（Non-linear Combination）

| ID | 假設 | 信號機制 | 優先度 |
|----|------|---------|--------|
| H009 | ACB × (1 / rank_in_MidFreq) | ACB高 + MidFreq排名低的號碼 | P1 |
| H010 | 頻率分布的 KL 散度（vs 均勻分布） | 整體頻率異常偵測 | P3 |
| H011 | 號碼間距的 Autocorrelation（間距本身是否有規律） | Gap 序列的 ACF | P2 |
| H012 | 號碼奇偶交替模式（Parity Run Length） | 連續奇/偶號碼長度分布 | P4 |

---

## 假設優先排序邏輯

LLM 排序時應考慮：

1. **與現有最強信號的互補性**：是否覆蓋 ACB+MidFreq 的盲區？
2. **計算複雜度**：特徵工程成本（簡單 > 複雜）
3. **理論合理性**：是否有統計/信息理論支持？
4. **歷史拒絕距離**：是否太接近已拒絕的假設？

**LLM 不得以「直覺感覺有效」作為排序理由。**

---

## 防幻覺機制

```python
class HypothesisValidator:
    """在 LLM 輸出進入回測前的程序性過濾"""

    def is_duplicate(self, h: Hypothesis, registry: HypothesisRegistry) -> bool:
        """與已測試假設的相似度 < 70%"""
        ...

    def is_too_complex(self, h: Hypothesis, best_strategy_complexity: int) -> bool:
        """特徵數 × 參數數 <= 現有最佳策略 × 1.5"""
        ...

    def has_rejection_condition(self, h: Hypothesis) -> bool:
        """必須預先定義拒絕條件"""
        return bool(h.rejection_conditions)

    def is_not_banned(self, h: Hypothesis) -> bool:
        """不使用已確認無效的信號類型"""
        BANNED = ['zone_distribution', 'sum_value', 'streak', 'zpi']
        return not any(b in h.description.lower() for b in BANNED)
```

---

## 執行頻率建議

| 觸發條件 | LLM 動作 |
|---------|---------|
| 每新增 50 期數據 | 重新排序現有假設優先度 |
| 策略 RSM 30p 連續負 30 期 | 生成 3 個針對當前弱點的新假設 |
| 新假設全部失敗（連續 5 個 REJECT） | 生成「方法論反思」報告，重新審視信號空間假設 |
| 每 200 期 | 完整假設庫審查 + 更新拒絕原因 |
