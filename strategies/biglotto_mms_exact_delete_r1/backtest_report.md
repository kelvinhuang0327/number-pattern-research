# Causal Backtest Report: BIGLOTTO_MMS_EXACT_DELETE_MULTI_TICKET_CANDIDATE_BATCH_R1

**Evaluation Date**: 2026-09-02 09:55:46  
**Historical Universe**: 2,074 historical draws (2007-01-02 to 2026-01-30)  
**Strategy Protocol**: Strict Causal Prefix (No look-ahead leak)  
**Mechanism**: Multiscale Markov Transition Space + Exact Deletion Filter  

---

## 1. Summary of Validation Windows (20-Ticket Portfolio)

| Validation Window | Tested Draws | M3+ Hits | Empirical Rate | Baseline Rate | Edge (%) | Z-Score | p-value | ROI | Sharpe | Max Drawdown |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **Window 1 (150 draws)** | 150 | 42 | 0.2800 | 0.3354 | -16.51% | -1.436 | 0.9245 | -80.67% | -23.788 | 80.67% |
| **Window 2 (500 draws)** | 500 | 141 | 0.2820 | 0.3354 | -15.91% | -2.527 | 0.9943 | -80.88% | -45.000 | 80.88% |
| **Window 3 (1500 draws)** | 1500 | 401 | 0.2673 | 0.3354 | -20.29% | -5.581 | 1.0000 | -77.33% | -21.754 | 77.33% |

---

## 2. Multi-Ticket Portfolio Scaling (Full 1500-Draw Window)

| Ticket Count (k) | Empirical M3+ Rate | Baseline M3+ Rate | Absolute Edge | Z-Score | p-value | Empirical M2+ Rate | Empirical M4+ Rate |
|---|---:|---:|---:|---:|---:|---:|---:|
| **1 Ticket** | 0.0233 | 0.0186 | +0.0047 | +1.34 | 0.0894 | 0.1407 | 0.0013 |
| **5 Tickets** | 0.0813 | 0.0929 | -0.0116 | -1.54 | 0.9386 | 0.5120 | 0.0060 |
| **10 Tickets** | 0.1467 | 0.1817 | -0.0350 | -3.52 | 0.9998 | 0.7220 | 0.0107 |
| **15 Tickets** | 0.2060 | 0.2607 | -0.0547 | -4.82 | 1.0000 | 0.8133 | 0.0160 |
| **20 Tickets** | 0.2673 | 0.3354 | -0.0680 | -5.58 | 1.0000 | 0.8580 | 0.0213 |

---

## 3. Stability Diagnostics
- **Edge Across Windows**: 150-window (-0.0554) vs 500-window (-0.0534) vs 1500-window (-0.0680).
