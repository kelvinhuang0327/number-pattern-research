# Causal Backtest Report: BIGLOTTO_MULTISCALE_TEMPORAL_PROFILE_CLUSTER_MULTI_TICKET_CANDIDATE_BATCH_R1

**Evaluation Date**: 2026-08-23 19:08:38  
**Historical Universe**: 2,074 historical draws (2007-01-02 to 2026-01-30)  
**Strategy Protocol**: Strict Causal Prefix (No look-ahead leak)  
**Candidate Generator**: Multiscale Temporal Profile Clustering + Min-Overlap Diversification  

---

## 1. Summary of Validation Windows (20-Ticket Portfolio)

| Validation Window | Tested Draws | M3+ Hits | Empirical Rate | Baseline Rate | Edge (%) | Z-Score | p-value | ROI | Sharpe | Max Drawdown |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **Window 1 (150 draws)** | 150 | 37 | 0.2467 | 0.3354 | -26.45% | -2.301 | 0.9893 | -78.80% | -19.963 | 78.93% |
| **Window 2 (500 draws)** | 500 | 117 | 0.2340 | 0.3354 | -30.22% | -4.801 | 1.0000 | -76.56% | -27.168 | 76.60% |
| **Window 3 (1500 draws)** | 1500 | 330 | 0.2200 | 0.3354 | -34.40% | -9.464 | 1.0000 | -78.89% | -48.344 | 78.91% |

---

## 2. Multi-Ticket Portfolio Scaling (Full 1500-Draw Window)

| Ticket Count (k) | Empirical M3+ Rate | Baseline M3+ Rate | Absolute Edge | Z-Score | p-value | Empirical M2+ Rate | Empirical M4+ Rate |
|---|---:|---:|---:|---:|---:|---:|---:|
| **1 Ticket** | 0.0167 | 0.0186 | -0.0020 | -0.56 | 0.7138 | 0.1473 | 0.0000 |
| **5 Tickets** | 0.0760 | 0.0929 | -0.0169 | -2.25 | 0.9879 | 0.4573 | 0.0040 |
| **10 Tickets** | 0.1393 | 0.1817 | -0.0423 | -4.25 | 1.0000 | 0.6260 | 0.0113 |
| **15 Tickets** | 0.1853 | 0.2607 | -0.0753 | -6.65 | 1.0000 | 0.7040 | 0.0160 |
| **20 Tickets** | 0.2200 | 0.3354 | -0.1154 | -9.46 | 1.0000 | 0.7513 | 0.0227 |

---

## 3. Stability and Consistency Diagnostics
- **Edge Consistency**: Edge in 150-window (-0.0887) vs 500-window (-0.1014) vs 1500-window (-0.1154).
- **Variance Ratio**: Ratio of empirical standard deviation to theoretical standard error across windows is within expected limits.
