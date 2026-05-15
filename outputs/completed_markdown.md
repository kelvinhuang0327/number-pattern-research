# Deep Research — Adaptive Bet Sizing + Hybrid Strategy + Shadow Tracking

Summary (concise):
- Focus G (Adaptive Bet Sizing): Proposed conservative policy (cold ×0.5, hot ×1.5). Existing quick tests show regime-aware multiplier reduced variance but did not reliably increase edge across tested candidates; recommend pilot with run_500w before any production changes. See outputs/bet_sizing_policy.json.
- Focus D (Hybrid Strategy): Designed a hybrid_vote ensemble. Quick 150-window backtests show strong positive edge for hybrid_vote across games (BIG_LOTTO edge_150=+10.667%, DAILY_539=+12.667%, POWER_LOTTO=+6.667%). Monte Carlo (seed=42, n=1000) completed — all three show robust positive mean edge. Recommendation: run 500w and 1500w + McNemar vs incumbents before promotion.
- Focus K (Shadow Tracking): Identified initial shadow_C candidates (f4cold_3bet, p1_neighbor_cold_2bet, shadow_C_regime). Created shadow tracking outputs with rolling 20-window summaries. Promotion rule: perm_p < 0.1 && edge_30p > 0.05; downgrade: 5 consecutive negative periods.

Key outputs (paths):
- outputs/quick_benchmark.json (150-window baseline results)
- outputs/hybrid_mc_summary.json (MC seed=42 n=1000 for hybrid_vote)
- outputs/temporal_pattern_analysis.json
- outputs/hybrid_strategy_candidates.json
- outputs/cold_phase_strategy_set.json
- outputs/shadow_tracking.json
- outputs/bet_sizing_policy.json

Actionable next steps:
- run_500w for hybrid_vote candidates (BIG_LOTTO, DAILY_539, POWER_LOTTO) -> then McNemar vs incumbents
- run full three-window backtests for shadow candidates (150/500/1500) and permutation tests
- pilot adaptive bet sizing in a simulated wallet (no production deployment) for 500 draws, monitor drawdown and recovery

Strategy Output Table

| strategy_name | family | edge_150 | edge_500 | edge_1000 | mc_status | vs_incumbent | incumbent_name | validation_tier | promotion_blocker | next_action |
|---|---|---:|---:|---:|---|---:|---|---:|---:|---|
| hybrid_vote_biglotto | BIG_LOTTO | +10.667 | — | — | PASS | +10.604 | p1_neighbor_cold_2bet | T1_MC_PASS | MC_ONLY_NO_THREE_WINDOW | run_500w |
| hybrid_vote_daily_539 | DAILY_539 | +12.667 | — | — | PASS | +12.572 | midfreq_acb_2bet | T1_MC_PASS | MC_ONLY_NO_THREE_WINDOW | run_500w |
| hybrid_vote_power_lotto | POWER_LOTTO | +6.667 | — | — | PASS | +6.658 | fourier_rhythm_3bet | T1_MC_PASS | MC_ONLY_NO_THREE_WINDOW | run_500w |

Baseline info: Existing best strategies: p1_neighbor_cold_2bet | game=BIG_LOTTO | edge=+0.063; midfreq_acb_2bet | game=DAILY_539 | edge=+0.095; fourier_rhythm_3bet | game=POWER_LOTTO | edge=+0.009
MC parameters: seed=42, n=1000

Notes:
- All numerical outputs are reproducible via the scripts in tools/ (deep_research_quick.py, run_mc_hybrid.py, deep_research_runner.py).
- Forbidden actions respected: no modifications to lottery_api/data/lottery_v2.db or strategy_states_*.json.
