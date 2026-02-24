---
name: backtest-framework
description: 回測框架使用指南。確保無數據洩漏、正確的滾動式驗證、Edge vs Random 方法論。當進行回測、驗證策略、或評估方法效果時使用。
---

# 回測框架技能 (2026-02-11 更新)

## 當使用此技能

- 驗證新預測方法的效果
- 對比不同策略的 Edge
- 確保無數據洩漏
- 評估多注組合策略

## 核心方法論：Edge vs Random

**所有策略評估必須使用 Edge（邊際優勢），不使用絕對命中率。**

```python
# Edge = 策略 M3+ 率 - 隨機基準
# 隨機基準公式：P(N注) = 1 - (1 - P(1注))^N

BASELINES = {
    'BIG_LOTTO': {   # 49選6, M3+ 單注 = 1.86%
        1: 1.86, 2: 3.69, 3: 5.49, 4: 7.25,
    },
    'POWER_LOTTO': { # 38選6, M3+ 單注 = 3.87%
        1: 3.87, 2: 7.59, 3: 11.17, 4: 14.61,
    },
}

# 範例：策略 M3+ = 9.50%, 基準 = 7.59% → Edge = +1.91%
```

### 採納門檻

| 條件 | 門檻 | 說明 |
|------|------|------|
| 最低回測期數 | **1000期** | 500期可能是幸運窗口 |
| Edge | > 0% | 必須優於隨機 |
| 多種子穩定性 | 10種子 ±0.3% | 確定性策略優先 (±0.00%) |
| 三階驗證 | 150/500/1500期 | 暴露 SHORT_MOMENTUM 和 LATE_BLOOMER |

## 數據洩漏防護（最重要！）

**黃金規則**：預測第N期時，只能使用第N-1期及之前的數據

```python
# ✅ 正確：滾動式回測
for i in range(test_periods):
    target_idx = len(all_draws) - test_periods + i
    target_draw = all_draws[target_idx]
    hist = all_draws[:target_idx]  # 只用之前的數據

    result = predict_func(hist)
    # 驗證...

# ❌ 錯誤：使用包含目標期的數據
train_data = all_history[orig_idx:]  # 洩漏！
```

## 標準回測模板

### 模式1：單注/多注通用回測

```python
import sys, random
from collections import Counter
sys.path.insert(0, '/path/to/LotteryNew')
from lottery_api.database import DatabaseManager

def backtest(predict_func, lottery_type, test_periods=1000, n_bets=2, seed=42):
    """標準回測框架"""
    random.seed(seed)
    db = DatabaseManager()
    all_draws = db.get_all_draws(lottery_type)
    # 資料庫返回 DESC，轉為 ASC（舊→新）
    all_draws = sorted(all_draws, key=lambda x: (x['date'], x['draw']))

    m3_plus = 0
    total = 0

    for i in range(test_periods):
        target_idx = len(all_draws) - test_periods + i
        if target_idx < 50:  # 最少 50 期訓練數據
            continue

        target = all_draws[target_idx]
        hist = all_draws[:target_idx]
        actual = set(target['numbers'])

        try:
            bets = predict_func(hist)  # 返回 list of sorted lists
            assert len(bets) == n_bets

            hit = any(len(set(bet) & actual) >= 3 for bet in bets)
            if hit:
                m3_plus += 1
            total += 1
        except Exception as e:
            print(f"⚠️ idx={target_idx}: {e}")
            continue

    rate = m3_plus / total * 100
    baseline = BASELINES[lottery_type][n_bets]
    edge = rate - baseline

    print(f"回測 {total} 期, M3+: {m3_plus} ({rate:.2f}%)")
    print(f"基準: {baseline:.2f}%, Edge: {edge:+.2f}%")
    return {'m3_plus': m3_plus, 'total': total, 'rate': rate, 'edge': edge}
```

### 模式2：三階驗證（推薦）

```python
def three_tier_validation(predict_func, lottery_type, n_bets, seed=42):
    """150/500/1500 期三階驗證，暴露衰減模式"""
    results = {}
    for periods in [150, 500, 1500]:
        r = backtest(predict_func, lottery_type, periods, n_bets, seed)
        results[periods] = r

    # 判斷模式
    e150, e500, e1500 = [results[p]['edge'] for p in [150, 500, 1500]]

    if e1500 < 0:
        if e150 > 0 or e500 > 0:
            print("⚠️ SHORT_MOMENTUM: 短期正 Edge 但長期失效")
        else:
            print("❌ INEFFECTIVE: 全段無效")
    elif e150 < 0 and e1500 > 0:
        print("⚠️ LATE_BLOOMER: 近期表現差但長期穩定")
    elif all(e > 0 for e in [e150, e500, e1500]):
        print("✅ STABLE: 三窗口全正")

    return results
```

### 模式3：多種子穩定性

```python
def multi_seed_validation(predict_func, lottery_type, n_bets, seeds=range(10)):
    """10 種子驗證穩定性"""
    edges = []
    for seed in seeds:
        r = backtest(predict_func, lottery_type, 1000, n_bets, seed)
        edges.append(r['edge'])

    import numpy as np
    mean_edge = np.mean(edges)
    std_edge = np.std(edges)

    print(f"Mean Edge: {mean_edge:+.2f}% ± {std_edge:.2f}%")
    if std_edge == 0:
        print("✅ 確定性策略（無隨機成分）")
    elif std_edge < 0.3:
        print("✅ 穩定")
    else:
        print("⚠️ 變異過大")
```

## 當前已驗證策略排名

| 彩票 | 注數 | 策略 | Edge | 穩定性 |
|------|-----|------|------|--------|
| 威力彩 | 2注 | Fourier Rhythm | +1.91% | STABLE |
| 威力彩 | 特別號 | V3 MAB | +2.20% | STABLE |
| 大樂透 | 3注 | Triple Strike | +0.98% | STABLE (三窗口全正) |
| 大樂透 | 2注 | P0 偏差互補+回聲 | +1.21% | STABLE |
| 大樂透 | 2注 | Fourier Rhythm | +0.51% | MODERATE_DECAY |

## 衰減模式分類

| 模式 | 定義 | 處置 |
|------|------|------|
| STABLE | 三窗口(150/500/1500)全正 | ✅ 採納 |
| MODERATE_DECAY | 1500期仍正但衰減明顯 | ✅ 可用，持續監控 |
| LATE_BLOOMER | 短期差但長期正 | ⚠️ 備用 |
| SHORT_MOMENTUM | 500期正但1500期負 | ❌ 不採納 |
| INEFFECTIVE | 全段負或接近0 | ❌ 不採納 |

## 統計顯著性檢驗

```python
# McNemar 配對檢驗（比較兩策略）
from scipy.stats import binom_test
# z-test（比較策略 vs 基準）
import numpy as np

def significance_test(m3_hits, total, baseline_rate):
    """單策略 vs 隨機基準的 z-test"""
    p_hat = m3_hits / total
    p0 = baseline_rate / 100
    se = np.sqrt(p0 * (1 - p0) / total)
    z = (p_hat - p0) / se
    print(f"z = {z:.2f}, {'顯著' if abs(z) > 1.96 else '不顯著'} (p<0.05)")
```

**多重比較校正**：測試 N 個號碼/策略時，使用 Bonferroni 校正 (p < 0.05/N)。

## 回測腳本索引

```bash
# 統一預測入口
python3 tools/quick_predict.py 威力彩      # 2注 Fourier Rhythm
python3 tools/quick_predict.py 大樂透      # 3注 Triple Strike
python3 tools/quick_predict.py 大樂透 2    # 2注 P0 回聲

# 大樂透全面回測
python3 tools/backtest_biglotto_comprehensive.py

# RSM 滾動監控
python3 tools/rsm_bootstrap.py
```

## 經驗教訓

1. **500期可能是幸運窗口** — 結構過濾 500期 +1.92% 崩壞至 1000期 -1.38%
2. **Layer 2 無法彌補 Layer 1** — 投注結構(L2)不能彌補預測信號(L1)缺失
3. **注2-3品質守護** — 改善注1的修改可能損害注2-3 (Gap Rebound、條件分支均證實)
4. **確定性策略優先** — 偏差互補無隨機成分，10種子完全一致
5. **Bonferroni 校正必要** — 38個號碼多重比較，未校正 p<0.05 全是假陽性
