# Strategy Spec: H6_gate_mk20→ew85 (DAILY_539)

## Overview
H6_gate_mk20→ew85 is a 3-bet DAILY_539 candidate using a gate_size=20 markov filter and EWMA weighting (decay=0.85).

## Parameters
- gate_size: 20
- ewma_decay: 0.85
- num_bets: 3

## Validation Evidence (production validation 2026-04-29)
- edge_150p: 7.1267%
- edge_500p: 5.0600%
- edge_1000p: 2.4600%
- edge_1500p: 2.4600%
- MC p-value: 0.0578 (mc_n=5000)
- Cohen's d: 1.6004
- McNemar p (exact): 4.3790577010150533e-47

Reference: runtime/winner_followup/H6_gate_mk20_ew85_prod_validation_2026-04-29.json and .md

## Comparison vs baseline
- vs incumbent (acb_markov_midfreq_3bet): net edge delta (1500p) = +2.372% (observed)
- McNemar indicates strategy beats incumbent (p ≪ 0.05)

## Bear Regime Risk ⚠️
- Bear regime edge: **-1.93%** (validated in prod_validation task 326)
- Neutral regime edge: +4.28% | Bull regime edge: -0.15%
- **Risk**: strategy underperforms significantly during bear regime periods
- Mitigation: rollback trigger (-2% on 30-period live edge) will auto-revert before sustained bear losses
- Note: bear regime flag (`has_bear_regime=False`) is NOT automatically detected by coordinator — manual monitoring via RSM required

## Deployment
- Classification: WINNER
- Validated status: validated
- Promotion: set active_strategy for DAILY_539 to H6_gate_mk20→ew85

## Fallback / Rollback Plan
- Rollback trigger: 30-period live edge < -2% (monitor_period=30)
- Rollback action: revert active_strategy_state.active_strategy to previous active strategy (saved as shadow_strategy); set planner_focus="RESEARCH"; notify CTO and create an automatic re-evaluation ticket in agent_orchestrator/cto_backlog_items.
- Rollback steps:
  1. Stop auto-monitor alerts
  2. Update orchestrator DB row active_strategy_state: set active_strategy=<shadow_strategy>, active_edge=<shadow_edge>, planner_focus="MONITOR", updated_at=<ISO>
  3. Add entry to runtime/winner_followup/rollback_log.md with timestamp and reason

## Monitoring / RSM Configuration
- monitoring_interval: 1 draw (real-time per-draw check)
- monitoring_window: 30
- monitoring_threshold: -0.02  # rollback if live_edge < -2%
- alert_levels: WARN at -1%, CRITICAL at -2%

## Operational Notes
- No live bets to be placed by this agent during deployment.
- Ensure tools/verify_no_data_leakage.py passes before finalizing deployment.

## Audit & Trace
- Prod validation artifacts:
  - runtime/winner_followup/H6_gate_mk20_ew85_prod_validation_2026-04-29.json
  - runtime/winner_followup/H6_gate_mk20_ew85_prod_validation_2026-04-29.md


