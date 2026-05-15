# Data Index

Last updated: 2026-04-20

## Operating Artifacts
- [bet_sizing_decision_brief.json](bet_sizing_decision_brief.json) - Human approval brief for the final DAILY_539 and POWER_LOTTO bet reductions.
- [live_performance_audit.json](live_performance_audit.json) - Live-vs-backtest audit used to confirm the final reductions stayed within the 95% CI guardrail.
- [automation_setup.json](automation_setup.json) - LaunchAgent and weekly monitoring setup summary.
- [milestone_monitor_test.json](milestone_monitor_test.json) - Snapshot from the milestone tracker smoke test.
- [system_maturity_2026_04_20.json](system_maturity_2026_04_20.json) - High-level maintenance-mode maturity summary.
- [weekly_health_20260420.json](weekly_health_20260420.json) - Latest weekly health output with EV gate and milestone sections.

## Research And Validation
- [annual_budget_analysis.json](annual_budget_analysis.json) - Budget framing for the deployed bet sizing.
- [monte_carlo_simulation.json](monte_carlo_simulation.json) - Monte Carlo result set used in the sizing decision.
- [bet_sizing_optimization.json](bet_sizing_optimization.json) - Optimization output for the final bet-count cutover.
- [smart_betting_summary_2026_04_20.json](smart_betting_summary_2026_04_20.json) - Summary view for the current smart-betting posture.
- [betting_strategy_guide_2026_04_20.json](betting_strategy_guide_2026_04_20.json) - Strategy guide snapshot used for the final closeout.

## Strategy And Monitoring
- [combo_b_milestone.json](combo_b_milestone.json) - Long-horizon milestone for the tracked combo-B event.
- [strategy_states_DAILY_539.json](../lottery_api/data/strategy_states_DAILY_539.json) - Current DAILY_539 strategy-state catalog.
- [strategy_states_BIG_LOTTO.json](../lottery_api/data/strategy_states_BIG_LOTTO.json) - Current BIG_LOTTO strategy-state catalog.
- [strategy_states_POWER_LOTTO.json](../lottery_api/data/strategy_states_POWER_LOTTO.json) - Current POWER_LOTTO strategy-state catalog.

## Notes
- The repository now keeps the deployed runtime maps in sync with [tools/rsm_bootstrap.py](../tools/rsm_bootstrap.py) and [lottery_api/routes/prediction.py](../lottery_api/routes/prediction.py).
- Session-generated scratch scripts should be archived under [tools/archive](../tools/archive) instead of deleted.