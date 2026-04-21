---
name: DAILY_539 PSI 觸發假設清單
description: 當 DAILY_539 PSI > 0.2 時立即執行的假設生成與測試清單
type: project
---

# DAILY_539 PSI 觸發假設清單

> 目前狀態：PSI = 0.1058 **WARNING**（2026-03-22）
> 觸發閾值：PSI > 0.20
> 準備目的：PSI 超閾時無需從零開始，直接執行以下清單

---

## 觸發後立即執行（Phase 0 — 確認漂移）

### P0-A：漂移特徵定位
```sql
-- 計算最近 30 / 100 / 300 期各特徵均值差異
SELECT
  AVG(CAST(json_extract(numbers, '$[0]') + ... AS REAL)) AS mean_sum,
  ...
FROM draws WHERE lottery_type='DAILY_539'
ORDER BY CAST(draw AS INTEGER) DESC LIMIT 30/100/300
```

需計算的特徵：
| 特徵 | 計算方法 | 正常範圍（300p基準） |
|------|----------|---------------------|
| 和值 mean | sum(5碼) | ~99.8 ± 15 |
| 奇數比例 | odd/5 | ~2.50/5 |
| Zone 低 (1-13) | count(n≤13)/5 | ~1.70 |
| Zone 高 (27-39) | count(n≥27)/5 | ~1.68 |
| 連號率 | pairs_diff1 / 4 | ~28% |
| 最大 Gap | max(diff) | ~8.5 |

判定：若任一特徵 30p 偏離 300p 基準 > 2σ → **確認漂移特徵**

---

## 假設生成清單（按優先級排序）

### H-PSI-1：和值 Regime 漂移
**假設**：PSI 上升由和值分布漂移引起（近期出現高/低和值聚集）
**測試方法**：
```python
# Ljung-Box test on recent 30p sum series
from statsmodels.stats.diagnostic import acorr_ljungbox
result = acorr_ljungbox(sum_series_30p, lags=[5,10,15])
# p < 0.05 → 和值存在自相關，分布已漂移
```
**行動**：若 p < 0.05 → 加入「和值 Regime 過濾器」到 ACB/MidFreq 策略
**停用條件**：p ≥ 0.1（連續 30 期後重測）

---

### H-PSI-2：區間 Zone 漂移
**假設**：低號(1-13)或高號(27-39)出現頻率顯著異於歷史基準
**測試方法**：
```python
# Chi-squared test: recent 30p Zone distribution vs 300p baseline
from scipy.stats import chi2_contingency
obs = [zone_low_30p, zone_mid_30p, zone_high_30p]
exp = [zone_low_300p, zone_mid_300p, zone_high_300p]
chi2, p, _, _ = chi2_contingency([obs, exp])
```
**行動**：若 p < 0.05 → 修正 Zone boundary 加權（提高漂移方向的選號比例）
**停用條件**：下次 RSM 300p 更新後 PSI 回落 < 0.1

---

### H-PSI-3：奇偶比例漂移
**假設**：近期奇偶比例偏離歷史 2.5/5
**測試方法**：
```python
# Binomial test: 30p 奇數碼總數 vs 期望值
from scipy.stats import binomtest
result = binomtest(total_odd_30p, n=30*5, p=0.5)
```
**行動**：若 p < 0.05 → 更新 ACB 奇偶約束（動態調整 boundary）
**停用條件**：奇偶比例回歸 2.5 ± 0.3 後停用

---

### H-PSI-4：號碼冷熱急速切換
**假設**：特定號碼段（如 1-10 或 30-39）在 30p 內出現頻率 > 2x 歷史均值
**測試方法**：
```python
# Per-number frequency 30p vs 300p
freq_30p = Counter(n for draw in last_30 for n in draw)
freq_300p = Counter(n for draw in last_300 for n in draw)
z_scores = {n: (freq_30p[n]/30 - freq_300p[n]/300) / se for n in range(1,40)}
# 若任意號碼 |z| > 2.5 → 該號碼進入「急速漂移」狀態
```
**行動**：若 z > 2.5（過熱）→ 對應號碼納入 MidFreq 冷號候選
**停用條件**：z 回落 < 1.5 後停用

---

### H-PSI-5：連號模式頻率漂移
**假設**：近期連號出現率（0對/1對/2對）分布已改變
**測試方法**：
```python
# Chi-squared: 30p 連號分布 vs 300p 基準
obs_consec = [count_0pair_30p, count_1pair_30p, count_2pair_30p]
exp_consec = [count_0pair_300p * 30/300, ...]
chi2, p, _, _ = chi2_contingency([obs_consec, exp_consec])
```
**行動**：若 p < 0.05 → 根據漂移方向調整連號偏好策略
**停用條件**：p ≥ 0.1 且連續 50 期穩定後停用

---

## 執行優先序

```
PSI > 0.20 觸發後：

1. 先執行 P0-A（漂移特徵定位）— 5 分鐘
2. 找出 >2σ 漂移特徵 → 對應執行 H-PSI-1~5
3. 若多個特徵同時漂移 → 優先序：和值 > Zone > 奇偶 > 冷熱 > 連號
4. 每個假設：permutation test p<0.05 才加入策略
5. 30期後重測 PSI → 若回落 <0.15 → 考慮撤回策略修正
```

---

## 快速執行腳本模板

```python
# tools/psi_triggered_analysis.py
# 當 PSI > 0.2 時執行此腳本

import sqlite3, json
from scipy.stats import chi2_contingency, binomtest
from collections import Counter

DB = 'lottery_api/data/lottery_v2.db'

def run_psi_analysis():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("""
        SELECT numbers FROM draws
        WHERE lottery_type='DAILY_539'
        ORDER BY CAST(draw AS INTEGER) DESC
        LIMIT 300
    """)
    all_draws = [json.loads(r[0]) for r in cur.fetchall()]

    draws_30  = all_draws[:30]
    draws_300 = all_draws[:300]

    # H-PSI-1: 和值
    sums_30  = [sum(d) for d in draws_30]
    sums_300 = [sum(d) for d in draws_300]
    mean_30, mean_300 = sum(sums_30)/30, sum(sums_300)/300
    std_300 = (sum((s-mean_300)**2 for s in sums_300)/300)**0.5
    z_sum = (mean_30 - mean_300) / (std_300 / 30**0.5)
    print(f"H-PSI-1 和值漂移: z={z_sum:.2f} (mean_30={mean_30:.1f} vs mean_300={mean_300:.1f})")

    # H-PSI-2: Zone
    def zone(nums): return [sum(1 for n in nums if n<=13), sum(1 for n in nums if 14<=n<=26), sum(1 for n in nums if n>=27)]
    z30  = [sum(zone(d)[i] for d in draws_30)  for i in range(3)]
    z300 = [sum(zone(d)[i] for d in draws_300) for i in range(3)]
    exp  = [z*30/300 for z in z300]
    chi2, p, _, _ = chi2_contingency([[z30[0],z30[1],z30[2]], [exp[0],exp[1],exp[2]]])
    print(f"H-PSI-2 Zone漂移: chi2={chi2:.3f} p={p:.3f}")

    # H-PSI-3: 奇偶
    odd_30 = sum(n%2==1 for d in draws_30 for n in d)
    binom = binomtest(odd_30, n=30*5, p=0.5)
    print(f"H-PSI-3 奇偶漂移: odd_rate={odd_30/(30*5):.3f} p={binom.pvalue:.3f}")

    conn.close()

if __name__ == '__main__':
    run_psi_analysis()
```

---

## Why: 此文件的存在意義

PSI=0.1058 已持續多期 WARNING，若突破 0.2 代表分布已顯著漂移。
漂移發生時需在「當日」開始假設測試，不能等到下期。
此清單確保：觸發後 < 1 小時可以完成所有假設的快速掃描。

**How to apply**: PSI 每次開獎後由 DriftDetector 自動計算。
若超過 0.2，立即執行 `tools/psi_triggered_analysis.py` 取得漂移方向，
再針對性執行對應 H-PSI-X 假設回測。
