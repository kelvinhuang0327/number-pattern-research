CLEC validation summary — 2026-04-30

Decision: WATCH_ONLY

Primary CLEC parameters (pre-registered):
- cross_entropy_ratio threshold Q = 0.85
- entropy gradient Δ = 0.05
- window (primary) = 150
- seed = 42
- lookback = 500
- test_window = last 500 draws; permutation K=10000 (seed=42)

Procedure:
- Computed per-lottery sliding-window entropy (normalized) for windows {30,150,500} using prior draws only (no data leakage).
- Cross-lottery metrics (cross_entropy_ratio, cross_sync_index) computed on unified timeline; collapse flagged when ratio < Q AND entropy_gradient < -Δ.
- Selected representative strategies (1–3 per lottery) based on available predictor scripts; ran deterministic predictions for each target draw using historic data prior to target and recorded hits (m>=3).
- Paired outcomes (unfiltered vs CLEC-filtered where flagged draws were skipped) tested with McNemar and permutation tests (K=10000).

Results (high-level):
- Strategies evaluated: DAILY_539/5bet_fourier4_cold (others skipped due to incompatible predictor signatures).
- Sample size per strategy: 500 draws
- McNemar p-values: 1.0 (no discordant pairs)
- Permutation p-values: 1.0
- Effect sizes (Cohen's d): 0.0

Verdict and rationale:
- No evidence CLEC improves hit outcomes for tested strategies (McNemar p >= 0.05 and d <= 0.2). With available predictors and this implementation, CLEC is labeled WATCH_ONLY.

Actionable follow-ups / gaps:
1. Several candidate strategies could not be auto-evaluated because their predictor modules do not expose a standard `predict(hist)` function. Recommend adding a small adapter layer for each predictor script (predictors should export `predict(hist)`) to enable batch evaluation.
2. Consider expanding tested strategies to include more short-window rank & frequency-based predictors once adapters exist.
3. Record exact reproducibility manifest: python version, seeds, and file hashes (produced in task_result_json).

Files produced:
- research/clec_diag.csv
- research/clec_validation_results_2026-04-30.json
- research/clec_plots_2026-04-30.zip
- research/clec_validation_summary_2026-04-30.md

Next Planner tick:
- If team wants a full validation, create adapters for predictors and re-run evaluation across 1–3 representative strategies per lottery (aim for n>=3 per lottery).