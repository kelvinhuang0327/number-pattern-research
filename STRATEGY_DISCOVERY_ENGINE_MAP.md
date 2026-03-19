# 🌌 策略發現引擎 (Strategy Discovery Engine) - 研究地圖 V1.0

**目標**：超越傳統統計方法，透過窮盡式的「方法空間搜尋」，找出隱藏在隨機雜訊中的非顯著性訊號。

---

## 一、 方法空間掃描 (Method Space Exploration)

### 1. 特徵生成空間 (Feature Generation Space)
*   **高階統計交互作用 (Higher-Order Interactions)**:
    *   計算號碼間的 **Mutual Information (互信息)** 矩陣，找出「同步共動」的強拉力對。
    *   **Skewness/Kurtosis Trend**: 追蹤最近 N 期的偏度與峰度，判斷出號是否朝向單一極端偏移。
*   **混沌與碎形指標 (Non-linear Dynamics)**:
    *   **Hurst Exponent (H)**: 判斷時間序列是「正相關 (Trending)」、「負相關 (Mean-reverting)」還是「純隨機」。
    *   **Lempel-Ziv Complexity**: 測量開獎序列的序列複雜度，判斷當下是否處於「規律轉變期」。
    *   **Lyapunov Exponent**: 評估系統對初始條件的敏感度（預測視界）。
*   **跨維度轉換**:
    *   **Wavelet Transform (小波轉換)**: 多尺度分析，過濾極短期雜訊，提取中長期趨勢訊號。
    *   **Gile-Empirical Mode Decomposition (EMD)**: 將序列分解為不同的本徵模態函數 (Intrinsic Mode Functions)，尋找隱藏的週期。

### 2. 模型結構空間 (Model Structure Space)
*   **隱狀態模型 (Latent State Models)**:
    *   **Hidden Markov Models (HMM)**: 將開獎狀態分為「低熵平穩」、「高熵亂序」、「區間聚集」，不同狀態下套用不同注碼權重。
    *   **State-Space Models**: 使用卡爾曼濾波 (Kalman Filter) 追蹤每個號碼的「潛在強度值」。
*   **無監督模式發現 (Unsupervised Discovery)**:
    *   **Self-Organizing Maps (SOM)**: 將高維的開獎向量映射到 2D 拓撲圖，觀測開獎模式的「路徑移動」。
    *   **Isolation Forest Anomaly Detection**: 識別出哪些號碼組合屬於「極端異常」，作為下一期殺號或選號的依據。
*   **圖論表徵 (Graph Representation)**:
    *   **Graph Attention Networks (GAT)**: 將號碼視為節點，共現頻率為邊，透過注意力機制學習號碼間的深層拓撲關係。

### 3. 時間尺度與 Regime 控制
*   **Adaptive Windowing (自適應窗口)**:
    *   自動偵測 **regime switch**。當 P-value 發生漂移時，自動縮短窗口至近期動能最強的尺度。
*   **Volatility Gating**:
    *   僅在系統波動度低於閾值（穩定性高）時下注，或在波動度極高（轉折點預測）時加大注碼。

---

## 二、 優先研究路徑 (Research Backlog)

| 優先級 | 方法名稱 | 預期效果 | 計算成本 | 狀態 |
| :--- | :--- | :--- | :--- | :--- |
| **Rejected** | **Regime-Gated Formula (RGF)** | 嘗試利用 GMM 區分狀態下注。 | 失敗 (Data Leakage) | 2026/02/23 |
| **High** | **Symbolic Regression (GP)** | 自動生成「號碼得分公式」。 | 高 (需大量演化) | 準備啟動 |
| **Medium** | **Hurst Exponent Memory** | 區分號碼是處於「慣性」還是「反轉」狀態。 | 低 | 待測試 |
| **Medium** | **Graph Embedding (Node2Vec)** | 用向量空間描述號碼關係，捕捉非線性的共現模式。 | 中 | 待啟動 |
| **Low** | **Chaos Attraction Analysis** | 嘗試在相位空間中建立吸引子模型。 | 極高 | 概念階段 |

---

## 三、 嚴格評估協定 (Evaluation Protocol)

1.  **OOS Walk-forward (1500p)**: 絕對禁止使用未來資料。
2.  **Permutation Test (n=1000)**: 透過隨機洗牌證明訊號不是巧合。
3.  **Alpha Decay Test**: 測試訊號在不同歷史長度下的衰減速度。
4.  **Cost-Benefit Audit**: 評估預測模型所需的算力與預期 Edge 回報比。

---

## 下一步行動建議
我建議先執行 **「Regime-Adaptive HMM」** 與 **「Symbolic Logic Discovery」**。這兩者最能直接檢驗「方法空間」中是否有被遺漏的非線性訊號。您是否同意以此地圖作為後續「策略發現引擎」的導航？
