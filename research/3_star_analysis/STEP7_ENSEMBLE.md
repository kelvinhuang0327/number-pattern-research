# 3星彩預測之策略集成 (Ensemble) 與權重優化
**身分：量化策略工程師**

單一模型往往難以應對複雜的隨機波動。透過「集成學習」(Ensemble Learning)，我們可以降低預測方差，提高穩定度。

## 1. 模型融合架構
我們採用 **Voter-based Ensemble** 或 **Stacking** 結構：

- **基礎模型層 (Base Learners)**:
  - 模型 A: 頻率回歸模型 (捕捉冷熱)
  - 模型 B: 馬可夫鏈模型 (捕捉序列依賴)
  - 模型 C: 貝氏機率融合 (多特徵綜合機率)
- **權重配置層 (Weighting Layer)**:
  - 根據各模型在過去 100 期的 **滾動命中率 (Rolling Accuracy)** 動態調整權重。
  - $W_i(t) = \frac{Acc_i(t-n, t)}{\sum Acc_j(t-n, t)}$

## 2. 動態權重優化算法
我們引入 **Multi-Armed Bandit (MAB)** 算法來決定每期應「信任」哪個模型：
- **探索 (Exploration)**: 測試新模型或長期表現不佳但近期有反彈跡象的模型。
- **利用 (Exploitation)**: 集中資源於當前狀態下最準確的模型（例如系統目前正處於「序列相關性高」的階段）。

## 3. 實例代碼思路 (Pseudo-code)
```python
def ensemble_predict(history):
    m1_pred = markov_model.predict(history)
    m2_pred = frequency_model.predict(history)
    m3_pred = bayesian_model.predict(history)
    
    # 權重由回測系統動態產出
    weights = [0.4, 0.3, 0.3] 
    
    combined_scores = (m1_pred * weights[0] + 
                       m2_pred * weights[1] + 
                       m3_pred * weights[2])
    
    return np.argmax(combined_scores)
```

## 4. 目標指標
- **資訊熵降低 (Entropy Reduction)**：預測分布的集中程度。
- **預測穩定度 (Stability Index)**：跨期預測結果的波動率。
