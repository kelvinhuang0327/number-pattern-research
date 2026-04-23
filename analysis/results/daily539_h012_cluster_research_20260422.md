# DAILY_539 H012 Cross-Draw Cluster / Transition Research (2026-04-22)

**Verdict:** REJECT

## Reproducibility

- Command: `python3 tools/research_daily539_h012_cluster.py`
- Params: seed=42, n_perm=200, min_history=300, perm_warmup=900, windows=[150, 500, 1500]
- Data range: 96000001 (2007/01/01) → 115000095 (2026/04/17), total draws=5839

## Summary

- Formal leakage checker: PASS (`tools/verify_no_data_leakage.py` -> `analysis/results/daily539_h012_cluster_no_leakage_20260422.txt`)
- Cross-draw overlap diagnostics: random baseline mean overlap=0.641, lag1=0.646, lag2=0.658, lag3=0.642.
- Random baseline P(overlap>=2)=0.1140; observed lag1/2/3=0.1143/0.1129/0.1146.
- Decision rule applied: any window edge <= 0, permutation p >= 0.05, Cohen's d <= 1.0, or marginal efficiency < 80% blocks promotion; McNemar runs only after the first three gates clear.

## Candidate Results

### Temporal-cluster residual 1-bet — REJECT

- Incumbent comparator: `acb_1bet`
- Gate summary: 三窗口 Edge 未全正；permutation p 未全窗口 < 0.05；Cohen's d 未全窗口 > 1.0；未進入 McNemar 替換閘
- Failed gates by window: 150: edge<=0, perm>=0.05, d<=1.0 | 500: edge<=0, perm>=0.05, d<=1.0 | 1500: perm>=0.05, d<=1.0

| Window | Edge | Sharpe | Perm p | Cohen's d | Hit rate | ROI | M2+/M3+/M4+/M5 |
|---:|---:|---:|---:|---:|---:|---:|---|
| 150 | -2.73% | -0.097 | 0.8706 | -1.026 | 8.67% | -81.33% | 13/3/0/0 |
| 500 | -1.80% | -0.061 | 0.9204 | -1.336 | 9.60% | -84.40% | 48/6/0/0 |
| 1500 | +0.53% | 0.016 | 0.2687 | 0.600 | 11.93% | -80.40% | 179/23/0/0 |

- McNemar: not triggered (前三閘門未過，不執行替換檢定)

### ACB + temporal-cluster overlay 2-bet — REJECT

- Incumbent comparator: `midfreq_acb_2bet`
- Gate summary: 三窗口 Edge 未全正；permutation p 未全窗口 < 0.05；Cohen's d 未全窗口 > 1.0；多注邊際效率未全窗口 > 80%；未進入 McNemar 替換閘
- Failed gates by window: 150: edge<=0, perm>=0.05, d<=1.0, eff<80 | 500: perm>=0.05, d<=1.0 | 1500: none

| Window | Edge | Sharpe | Perm p | Cohen's d | Hit rate | ROI | M2+/M3+/M4+/M5 |
|---:|---:|---:|---:|---:|---:|---:|---|
| 150 | -1.54% | -0.038 | 0.8060 | -0.777 | 20.00% | -86.67% | 30/2/0/0 |
| 500 | +1.46% | 0.035 | 0.3284 | 0.410 | 23.00% | -85.70% | 115/5/0/0 |
| 1500 | +3.99% | 0.092 | 0.0050 | 3.105 | 25.53% | -81.60% | 383/32/0/0 |

| Window | Bet | Cum hit rate | Incremental efficiency |
|---:|---:|---:|---:|
| 150 | 1 | 12.67% | 100.00% |
| 150 | 2 | 20.00% | 72.32% |
| 500 | 1 | 14.40% | 100.00% |
| 500 | 2 | 23.00% | 84.81% |
| 1500 | 1 | 14.20% | 100.00% |
| 1500 | 2 | 25.53% | 111.77% |

- McNemar: not triggered (前三閘門未過，不執行替換檢定)

### ACB + Markov + temporal-cluster 3-bet — REJECT

- Incumbent comparator: `acb_markov_midfreq_3bet`
- Gate summary: permutation p 未全窗口 < 0.05；Cohen's d 未全窗口 > 1.0；未進入 McNemar 替換閘
- Failed gates by window: 150: perm>=0.05, d<=1.0 | 500: perm>=0.05, d<=1.0 | 1500: none

| Window | Edge | Sharpe | Perm p | Cohen's d | Hit rate | ROI | M2+/M3+/M4+/M5 |
|---:|---:|---:|---:|---:|---:|---:|---|
| 150 | +0.83% | 0.018 | 0.6766 | -0.380 | 31.33% | -85.78% | 47/3/0/0 |
| 500 | +3.90% | 0.082 | 0.1891 | 0.944 | 34.40% | -84.60% | 172/10/0/0 |
| 1500 | +6.17% | 0.128 | 0.0050 | 3.342 | 36.67% | -56.02% | 550/44/3/0 |

| Window | Bet | Cum hit rate | Incremental efficiency |
|---:|---:|---:|---:|
| 150 | 1 | 12.67% | 100.00% |
| 150 | 2 | 22.00% | 92.04% |
| 150 | 3 | 31.33% | 104.17% |
| 500 | 1 | 14.40% | 100.00% |
| 500 | 2 | 24.60% | 100.59% |
| 500 | 3 | 34.40% | 109.37% |
| 1500 | 1 | 14.20% | 100.00% |
| 1500 | 2 | 25.87% | 115.06% |
| 1500 | 3 | 36.67% | 120.54% |

- McNemar: not triggered (前三閘門未過，不執行替換檢定)

## Conclusion

- Signal exhaustion read: closer_to_exhaustion.
REJECT H012 cluster/transition overlays for DAILY_539 under current data. The family can generate some medium/long-window raw edge, but not a stable three-window, permutation-confirmed, incumbent-beating signal. DAILY_539 should be treated as even closer to signal exhaustion; only exogenous data or materially different pool-size / market-behavior signals are still worth testing.

## Handoff Notes

- Wiki update: applied.
