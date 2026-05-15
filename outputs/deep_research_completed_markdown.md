Deep Research — Coverage Optimization + Number Distribution Bias + Signal Reconstruction

Per-focus concise summaries (quantitative):

Focus A — Coverage Optimization:
- Analysis: concentrated pool (coverage factor 0.8) tested via cov_opt_concentrated on POWER_LOTTO.
- 150p edge: -3.80% (worse than random); MC(mean) = -1.205% (n=1000, seed=42).
- Conclusion: current coverage heuristic reduced hit-rate; tune pool size and selection method.

Focus H — Number Distribution Bias:
- Analysis: freq_reversion_strategy (short/long freq ratio) on POWER_LOTTO.
- 150p edge: -1.80%; MC(mean)=+0.155% (n=1000, seed=42).
- Conclusion: weak positive MC mean but not reliable short-window edge; needs feature strengthening.

Focus F — Signal Reconstruction:
- Analysis: struct_filter_strategy (span/consec/odd-even composite) on POWER_LOTTO.
- 150p edge: -3.00%; MC(mean)=+0.237% (n=1000, seed=42).
- Conclusion: small MC mean; candidate not robust across windows.

Overall verdict: FAILED_NO_EDGE — no candidate had edge_150 > 0. Detailed results: tools/deep_research_results_powerlotto.json

Recommendations:
1) Re-tune coverage heuristics (try smaller pools, diversify combinations) and re-run 150/500 quick tests.
2) Engineer stronger composite features (zone×parity×lag delta) and test on DAILY_539 where short-window density is higher.
3) If any future candidate attains edge_150 > 0, run permutation (perm_test.py) and McNemar OOS before any promotion.
