# Backtest Report — BIG_LOTTO 4注 TS3+Markov(w=30)

| 窗口 | Baseline (4注) | Edge | 狀態 |
|------|----------------|------|------|
| 150期 | 7.25% | **+1.43%** | ✅ |
| 500期 | 7.25% | **+2.37%** | ✅ |
| 1500期 | 7.25% | **+1.70%** | ✅ ROBUST |

- **模式**: ROBUST（三窗口全正）
- **z-score**: 2.54
- **邊際Edge(注4)**: +0.14%（500/1500p 一致）
- **Markov window**: w=30（必須，w=100降至+1.17%）
- **含**: Sum-Constraint v2（注2）
- **seed**: 42
- **腳本**: `tools/backtest_biglotto_markov_4bet.py`
- **日期**: 2026-02-24
