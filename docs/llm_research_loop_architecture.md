# LLM Research Loop Architecture
# Phase 6 — Automated Research Cycle Design
# 2026-03-15

---

## 核心設計原則

**LLM 是研究加速器，不是決策者。**
所有決策（採納/拒絕策略）由統計引擎執行，LLM 只負責提高研究吞吐量。

---

## 研究循環架構

```
┌─────────────────────────────────────────────────────────────────┐
│                    AUTOMATED RESEARCH LOOP                      │
│                                                                 │
│  ┌──────────────┐    ┌─────────────────┐    ┌───────────────┐  │
│  │  TRIGGER     │───▶│  LLM PHASE      │───▶│  STAT PHASE   │  │
│  │  ENGINE      │    │  (提案/分析)    │    │  (驗證/決策)  │  │
│  └──────────────┘    └─────────────────┘    └───────┬───────┘  │
│         ▲                                           │           │
│         │            ┌─────────────────┐           │           │
│         └────────────│  MEMORY UPDATE  │◀──────────┘           │
│                      │  (記錄結果)     │                        │
│                      └─────────────────┘                        │
└─────────────────────────────────────────────────────────────────┘
```

---

## Trigger Engine（觸發條件）

```python
class ResearchTrigger:
    """決定何時啟動新一輪 LLM 研究"""

    TRIGGERS = {
        'periodic': {
            'condition': 'new_draws >= 50',
            'action': 're_prioritize_hypothesis_queue',
            'llm_task': 'low'
        },
        'strategy_decay': {
            'condition': 'rsm_30p_consecutive_negative >= 30',
            'action': 'generate_3_new_hypotheses',
            'llm_task': 'medium'
        },
        'consecutive_reject': {
            'condition': 'last_N_hypotheses_rejected >= 5',
            'action': 'methodology_review',
            'llm_task': 'high'
        },
        'drift_detected': {
            'condition': 'drift_detector_psi > 0.2',
            'action': 'urgent_hypothesis_generation',
            'llm_task': 'high'
        }
    }
```

---

## LLM Phase 工作清單

### 任務 L1：假設生成（每 50 期觸發）
```
輸入：
  - 現有驗證信號列表（ACB, MidFreq, Markov）
  - 已拒絕假設列表（帶拒絕原因）
  - 近 50 期失敗案例統計（失敗類型分布）
  - feature_interaction_candidates.json 的 pending 假設

輸出：
  - 3-5 個新假設（JSON 格式，含可執行的偽代碼）
  - 現有 pending 假設的優先度更新
  - 建議跳過的假設（帶理由）

限制：
  - 不得提出 Zone/Sum/Streak 相關假設
  - 每個假設必須含 rejection_condition
  - 複雜度不超過現有最佳策略 ×1.5
```

### 任務 L2：失敗分析（每 20 個失敗期觸發）
```
輸入：
  - 失敗期次列表（含特徵值快照）
  - 各失敗類型分布（Type A/B/C/D/E）

輸出：
  - 主要失敗類型識別
  - 針對最常見失敗類型的 1-2 個具體改進假設
  - 以 S001-S006 格式加入 strategy_evolution_candidates.json

限制：
  - 不做單期事後合理化（"這期因為#05是熱號所以..."）
  - 必須跨 ≥10 個失敗期才能聲稱「系統性模式」
```

### 任務 L3：方法論審查（5個連續 REJECT 後觸發）
```
輸入：
  - 最近 5 個被拒絕假設的詳細結果
  - 現有研究方向清單

輸出：
  - 是否信號空間已被窮盡？
  - 建議的新研究方向（如：換用不同的數學框架）
  - 是否建議暫停假設生成（若信號空間確已窮盡）

注意：LLM 對「信號是否存在」的判斷需謹慎，最終由統計結果決定。
```

---

## Stat Phase 工作清單

### 任務 S1：快速 Gate（< 1天）
針對每個新假設先做快速拒絕測試，節省計算資源：
- Ljung-Box 自相關檢定（適用於時序特徵）
- 樣本均值 z-test（信號是否非零）
- 若快速測試失敗，直接 REJECT，不進入完整回測

### 任務 S2：完整回測（3-5天）
通過快速 Gate 的假設進行：
- Walk-forward OOS 三窗口（150/500/1500期）
- Permutation Test（≥200次）
- McNemar Test（與對應 baseline）
- Sharpe Ratio 計算

### 任務 S3：決策記錄
- 通過：更新 strategy_states；加入 RSM 監控
- 拒絕：生成 rejected/{strategy_name}.json；更新 lessons.md

---

## Memory Update（結果記錄）

每次循環結束後強制更新：
```
memory/lessons.md       ← 新 L 號教訓（無論通過或失敗）
memory/MEMORY.md        ← RSM 狀態更新
docs/feature_interaction_candidates.json  ← 假設狀態更新
rejected/{name}.json    ← 失敗假設歸檔
```

---

## 實際效率估算

| 階段 | 工時（無 LLM） | 工時（有 LLM） | 加速比 |
|------|------------|------------|--------|
| 假設生成 | 2-4小時/假設 | 10分鐘/假設 | **12x** |
| 失敗分析 | 1-2小時/批次 | 15分鐘/批次 | **6x** |
| 代碼生成 | 2-3小時/腳本 | 30分鐘/腳本 | **5x** |
| 優先排序 | 30分鐘/次 | 5分鐘/次 | **6x** |
| 統計驗證 | 不變 | 不變 | **1x**（無法加速） |

**關鍵洞察**：LLM 不加速統計驗證，但能讓研究人員在相同時間內測試 5-10x 更多假設。
假設品質可能略低（LLM 假設未必比人工更好），但數量優勢可以補償。

---

## 預期改進上限（誠實估算）

**為何上限有限：**
- 539 Zone/Sum/Streak = 白噪音（L73/L74）
- 真正有效的信號空間窄：只有頻率偏差（ACB）和頻率模式（MidFreq）
- LLM 無法從無信號的空間中創造信號

**樂觀情境（H001-H002 通過）：**
- ACB × MidFreq 乘積改進：+0.5~1.0pp Edge
- 條件 ACB 改進：+0.3~0.8pp Edge
- 合計：**+0.8~1.8pp** → 3bet Edge 從 5.83% 提升至 ~6.5~7.6%

**保守情境（僅快速 Gate 假設）：**
- Gap entropy / Cluster 分析：可能全部白噪音 → +0pp
- 合計：**+0pp**（研究成本但無效益）

**研究加速的真正價值：**
在相同時間內窮盡更多研究方向，**更快確認信號空間上限**，
而不是「一定能找到新信號」。研究的負結果同樣有價值。

---

## 立即可執行的下一步

1. **H001 回測**（1天）：ACB × MidFreq 乘積 vs 現有 combined_score
2. **H002 回測**（2天）：條件 ACB（Markov 條件化）
3. **H003 快速 Gate**（半天）：ΔACB 信號是否有 ACF（若白噪音直接 REJECT）
4. **H004/H006 快速 Gate**（1天）：Gap entropy + Cluster 序列 Ljung-Box
5. **啟用真實 LLM**（需 API Key）：解鎖後執行 L1 任務，生成下一批假設
