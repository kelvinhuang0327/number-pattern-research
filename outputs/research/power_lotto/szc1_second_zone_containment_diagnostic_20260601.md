# SZC1 — Second-Zone Special Ball Containment Diagnostic

- Final classification: **SECOND_ZONE_NO_SIGNAL_CONFIRMED**
- Data scope: POWER_LOTTO rows=36104, distinct draws=1551, predicted_special rows=9000
- Baseline: random 1/8 = **0.125**

## Executive Summary
This is a read-only containment audit. The question is whether second-zone has stable out-of-sample signal above 0.125. The evidence shows concentrated predictions (often fixed or near-fixed values), and no corrected-significant stable edge.

## Root Cause
Most strategies over-concentrate on a small set of specials (notably 3/7), reducing adaptability when realized specials rotate to 4/5/8-dominant periods.

## Baseline Comparison (walk-forward)
- n_eval draws: 1912
- rolling_weighted_expected_hits_w50: hit_rate=0.126160
- uniform_random_expected_hits: hit_rate=0.125000
- global_freq_top1: hit_rate=0.132322
- rolling_recent_freq_top1_w50: hit_rate=0.125523
- last_k_recency_top1_k1: hit_rate=0.135460

## Recent Misses: Abnormal or Expected?
- Last 3: hit_rate=0.000000, actual(4/5/8) share=1.000, predicted(3/7) share=1.000
- Last 20: hit_rate=0.100000, actual(4/5/8) share=0.550, predicted(3/7) share=0.642
- Last 50: hit_rate=0.110000, actual(4/5/8) share=0.460, predicted(3/7) share=0.433
Conclusion: recent misses are expected under concentration mismatch, not a rare anomaly.

## Governance Recommendation
- Exclude second-zone from recommendation score.
- Keep second-zone as display-only with explicit random baseline (12.5%).
- Evaluate second-zone separately from first-zone metrics.
- Do not label second-zone as improved unless corrected walk-forward evidence beats 0.125.

## Score Semantics Check
Code search indicates score aggregation loops use main-number `numberScores`; second-zone appears display-oriented and not clearly weighted into recommendation score.
