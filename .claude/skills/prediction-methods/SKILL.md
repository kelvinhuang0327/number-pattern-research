---
name: prediction-methods
description: 彩票預測方法完整指南。包含已驗證策略、Edge方法論、統一預測入口。當需要了解或實作預測方法、選擇最佳策略、或進行方法對比時使用。
---

# 彩票預測方法技能 (2026-02-11 更新)

## 當使用此技能

- 選擇適合的預測策略
- 了解各方法的原理和 Edge
- 實作新預測方法前了解基準
- 使用統一預測入口

## 統一預測入口

```bash
# 所有預測都通過 quick_predict.py
python3 tools/quick_predict.py 威力彩        # 2注 Fourier Rhythm + V3特別號
python3 tools/quick_predict.py 威力彩 3      # 3注 Power Precision + V3特別號
python3 tools/quick_predict.py 大樂透        # 3注 Triple Strike
python3 tools/quick_predict.py 大樂透 2      # 2注 P0 偏差互補+回聲
python3 tools/quick_predict.py 今彩539 3     # 3注
python3 tools/quick_predict.py all           # 全部彩票
```

## 已驗證策略（2026-02-11 當前有效）

### 威力彩 (38選6 + 特別號1-8)

| 注數 | 策略 | Edge | M3+ 率 | 基準 | 穩定性 |
|-----|------|------|--------|------|--------|
| 2注 | **Fourier Rhythm** | **+1.91%** | 9.50% | 7.59% | STABLE ★推薦 |
| 3注 | **Power Precision (F2+Echo/Cold)** | **+2.30%** | 13.47% | 11.17% | STABLE 三窗口全正 ★推薦 |
| 特別號 | V3 MAB | +2.20% | 14.70% | 12.50% | STABLE |

### 大樂透 (49選6)

| 注數 | 策略 | Edge | M3+ 率 | 基準 | 穩定性 |
|-----|------|------|--------|------|--------|
| 3注 | **Triple Strike** | **+0.98%** | 6.36% | 5.49% | STABLE 三窗口全正 ★推薦 |
| 2注 | P0 偏差互補+回聲 | +1.21% | 4.90% | 3.69% | STABLE |
| 2注 | Fourier Rhythm | +0.51% | 4.20% | 3.69% | MODERATE_DECAY |

### 隨機基準公式

```python
# P(N注至少一注M3+) = 1 - (1 - P單注)^N
# 大樂透 P單注 = 1.86%, 威力彩 P單注 = 3.87%
BASELINES = {
    'BIG_LOTTO': {1: 1.86, 2: 3.69, 3: 5.49, 4: 7.25},
    'POWER_LOTTO': {1: 3.87, 2: 7.59, 3: 11.17, 4: 14.61},
}
```

## 策略原理

### Fourier Rhythm (威力彩 2注首推)
FFT 分析號碼出現頻率的週期性，預測「即將到期」的號碼。
```python
from tools.power_fourier_rhythm import fourier_rhythm_predict
bets = fourier_rhythm_predict(history, n_bets=2, window=500)
# 返回: [[n1,n2,n3,n4,n5,n6], [n1,n2,...]]
```

### P0 偏差互補 + Lag-2 回聲 (大樂透 2注)
偏差分析找出偏離期望頻率的號碼，echo_boost=1.5 強化 N-2 期出現號碼。
```python
# 內嵌於 quick_predict.py 的 biglotto_p0_2bet()
# 無 numpy 依賴，純 Counter 計算
# bet1: 偏差排名Top6 + echo boost
# bet2: 互補（排名7-12）
```

### Triple Strike (大樂透 3注首推)
組合 Fourier 週期 + 冷號回歸 + 尾數平衡三個獨立信號。
```python
from tools.predict_biglotto_triple_strike import generate_triple_strike
bets = generate_triple_strike(history)
# 返回 3 注，每注 6 個號碼
```

### Power Precision (威力彩 3注首推)
Fourier Top12 分割為 bet1+bet2，Echo+Cold 互補為 bet3。
```python
from tools.predict_power_precision_3bet import generate_power_precision_3bet
bets = generate_power_precision_3bet(history)
# bet1: Fourier Top 6, bet2: Fourier 7-12, bet3: Lag-2 Echo + Cold fill
# 150p +3.50%, 500p +2.43%, 1500p +2.30% — 三窗口全正 STABLE
```

### V3 特別號 (威力彩)
MAB (Multi-Armed Bandit) 自適應預測威力彩特別號 (1-8)。
```python
from lottery_api.models.special_predictor import PowerLottoSpecialPredictor
predictor = PowerLottoSpecialPredictor()
special = predictor.predict_v3(history)
# 返回: int (1-8)
```

## 暫停研究策略（附重啟條件，見 rejected/ 目錄）

| 策略 | 暫停原因 |
|------|---------|
| ~~UnifiedPredictionEngine~~ | 全部方法 Edge < 0，已廢棄 |
| ~~BigLotto3BetOptimizer~~ | 過時，已被 Triple Strike 取代 |
| ~~Cluster Pivot 4注+~~ | SHORT_MOMENTUM: 500期+1.75% → 1500期-0.45% |
| ~~Core-Satellite~~ | 覆蓋損失 > 相關收益 |
| ~~GNN/LSTM/Transformer~~ | 數據不足（<2500期），Edge 為負 |
| ~~Gap Rebound 注入~~ | 損害注2-3品質，z=0.23 不顯著 |
| ~~條件機率分支~~ | Bonferroni 校正後 0/16 顯著 |
| ~~鄰號共現~~ | Lift < 1.0，是負相關 |

## 數據載入標準模式

```python
import sys
sys.path.insert(0, '/Users/kelvin/Kelvin-WorkSpace/LotteryNew')
from lottery_api.database import DatabaseManager

db = DatabaseManager()
history = db.get_all_draws('POWER_LOTTO')  # 返回 DESC（新→舊）

# ⚠️ 策略需要 ASC（舊→新），必須排序
history = sorted(history, key=lambda x: (x['date'], x['draw']))

# history[-1] = 最新期
# history[0] = 最舊期
```

## 新策略開發流程

1. **提出假說** — 基於統計觀察，非直覺
2. **實作預測函數** — `predict_func(history) → list of bets`
3. **1000期回測** — 使用 `backtest-framework` Skill
4. **計算 Edge** — 必須 > 0% vs 隨機基準
5. **三階驗證** — 150/500/1500 期，排除 SHORT_MOMENTUM
6. **10種子穩定性** — 隨機策略必須 ±0.3% 以內
7. **注2-3影響評估** — 修改不能損害其他注的品質

## 關鍵原則

1. **Edge > 0 才有意義** — 絕對命中率無意義，必須優於隨機
2. **簡單統計 > 深度學習** — 2000期數據不足以訓練 ML
3. **確定性 > 隨機** — 偏差互補(±0.00%)優於隨機策略(±0.5%)
4. **500期可能是幸運窗口** — 最低 1000期驗證
5. **Layer 1 信號優先** — L2 投注結構無法彌補 L1 預測缺失
