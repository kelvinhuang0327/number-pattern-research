#!/usr/bin/env python3
import os

filepath = "/Users/kelvin/Kelvin-WorkSpace/LotteryNew/MEMORY.md"

text = """
## P0 假設回測結論: 熱號休停回歸偵測 (2026-03-03)

針對 031 期出現的矛盾信號 #25 (Hot+HighGap, freq100=18, gap=15)，我們對 `freq100>=15 AND gap>=10` 進行了 1500 期獨立回測。

**結果**:
- 總候選號碼數: 2633 (平均每期 1.76 個)
- 命中率: 11.70%
- 基準命中率: 12.24% (6/49)
- Edge: -0.55%, z-score: -0.86
- **判定**: 無顯著差異 (NO SIGNAL)

**結論**:
1. 031 期的 #25 命中純屬**倖存者偏差**，這種「熱號休停」模式在長期統計中並未表現出高於隨機的期望值。
2. 此特徵已被否決，**不建議**納入 bet5 殘差池的候選排名因子。
3. 相關驗證紀錄已存入 `rejected/hot_gap_return_biglotto.json`。
"""

with open(filepath, 'a') as f:
    f.write(text)
