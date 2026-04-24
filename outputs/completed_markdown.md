Deep Research — Summary

Focus 1 (Structure Filtering): computed odd/even, span, consecutive distributions (last 1000). Chi-square tests per-game saved to outputs/structure_filter_rules.json. Proposed structure filters (allow-lists) for each game.

Focus 2 (Monte Carlo Robustness): bootstrap MC (n=2000, seed=42) on structure-filter candidates; summary in outputs/mc_robustness_report.json. Selected candidates show mean delta and stability (p5/p95).

Focus 3 (Signal Quality Reconstruction): constructed signal_quality_matrix.json from strategy_states (z_score + edge_stability heuristic). Recommendations inside that JSON.

Artifacts: outputs/structure_filter_rules.json, outputs/mc_robustness_report.json, outputs/signal_quality_matrix.json, outputs/deep_research_summary.json
