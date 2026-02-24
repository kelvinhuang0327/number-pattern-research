---
description: 預測下期彩票號碼。支援大樂透、威力彩、今彩539。自動選擇最佳驗證策略。
allowed-tools: Read, Bash(python3:*)
---

# 彩票預測指令

預測下期彩票號碼。

## ⚠️ 強制規則（絕對不可違反）

**無論用戶用什麼方式請求預測，一律只執行以下腳本：**

```bash
python3 tools/quick_predict.py [彩票] [注數]
```

**禁止**：
- 禁止寫 inline Python 程式碼進行預測
- 禁止自行 import 任何策略函數組合預測邏輯
- 禁止用任何其他腳本替代 quick_predict.py

**原因**：quick_predict.py 是唯一經過驗證的預測入口，inline 程式碼容易引入 bug（如特別號 range 錯誤）且繞過已驗證邏輯。

## 使用方式

```
/predict              # 預測所有彩票
/predict 大樂透        # 大樂透 5注 (TS3+Markov+FreqOrt)
/predict 大樂透 2      # 大樂透 2注 (P0 回聲)
/predict 大樂透 3      # 大樂透 3注 (Triple Strike)
/predict 威力彩        # 威力彩 2注 (Fourier Rhythm)
/predict 威力彩 3      # 威力彩 3注 (Power Precision)
/predict 今彩539 3     # 今彩539 3注
```

## 執行指令

```bash
python3 tools/quick_predict.py $ARGUMENTS
```

## 策略對照 (2026-02-23 更新)

| 用戶輸入 | lottery_type | 默認注數 | 策略 | Edge |
|---------|--------------|---------|------|------|
| 大樂透 / biglotto | BIG_LOTTO | **5** | TS3+Markov+FreqOrt | **+1.77%** |
| 大樂透 2注 | BIG_LOTTO | 2 | 偏差互補+回聲 P0 | +1.21% |
| 大樂透 3注 | BIG_LOTTO | 3 | Triple Strike | +0.98% |
| 大樂透 4注 | BIG_LOTTO | 4 | TS3+Markov(w=30) | +1.23% |
| 威力彩 / power | POWER_LOTTO | 2 | Fourier Rhythm + V3特別號 | +1.91% |
| 威力彩 3注 | POWER_LOTTO | 3 | Power Precision + V3特別號 | +2.30% |
| 今彩539 / 539 | DAILY_539 | 3 | SumRange+Bayesian+ZoneBalance | N/A |

## 預期成功率

| 彩票 | 注數 | 策略 | M3+ 率 | 隨機基準 | Edge |
|------|-----|------|--------|---------|------|
| 大樂透 | **5注** | **TS3+Markov+FreqOrt** | **10.73%** | **8.96%** | **+1.77%** |
| 大樂透 | 4注 | TS3+Markov(w=30) | 8.47% | 7.25% | +1.23% |
| 大樂透 | 3注 | Triple Strike | 6.36% | 5.49% | +0.98% |
| 大樂透 | 2注 | P0 回聲 | 4.90% | 3.69% | +1.21% |
| 威力彩 | 3注 | Power Precision | 13.47% | 11.17% | +2.30% |
| 威力彩 | 2注 | Fourier Rhythm | 9.50% | 7.59% | +1.91% |
| 威力彩 | 特別號 | V3 MAB | 14.70% | 12.50% | +2.20% |
