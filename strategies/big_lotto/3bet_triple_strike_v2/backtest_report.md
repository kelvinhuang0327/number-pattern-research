# Backtest Report — BIG_LOTTO 3注 Triple Strike v2

| 窗口 | Baseline (3注) | Edge | 狀態 |
|------|----------------|------|------|
| 150期 | 5.48% | **+1.86%** | ✅ |
| 500期 | 5.48% | **+2.12%** | ✅ |
| 1500期 | 5.48% | **+1.46%** | ✅ ROBUST |

- **模式**: ROBUST（三窗口全正）
- **z-score**: 2.48，p=0.007（高度顯著）
- **vs 舊版**: +0.40% 提升（注2 加入 Sum-Constraint）
- **seed**: 42
- **腳本**: `tools/predict_biglotto_triple_strike.py`
- **日期**: 2026-02-23
