# Operations Manual

Last updated: 2026-04-20

## Weekly Path
1. Confirm the LaunchAgent is installed at `~/Library/LaunchAgents/com.kelvin.lottery.weekly.plist`.
2. Load or reload the agent with `launchctl load -w ~/Library/LaunchAgents/com.kelvin.lottery.weekly.plist`.
3. Run `./tools/check_draw_status.sh` for a quick status snapshot.
4. Run `python3 tools/weekly_health_report.py` to regenerate the weekly report.
5. Inspect `logs/weekly_health.log` if the report does not look current.

## Deployment Rules
- Keep `tools/rsm_bootstrap.py` and `lottery_api/routes/prediction.py` synchronized when changing deployed bet counts.
- Treat `data/live_performance_audit.json` as the final guardrail for bet reductions.
- Keep `data/bet_sizing_decision_brief.json` and `data/system_maturity_2026_04_20.json` up to date when the runtime posture changes.

## Frontend Decision Surface
- Use `GET /api/decision/{lottery_type}` as the primary source for V3.1 UI fields such as EV gate, Kelly fraction, monetary EV, and Stage2 status.
- Keep `GET /api/decision/best-strategy-summary` as a legacy strategy/backtest surface; it does not expose the full V3.1 decision payload.
- The next-draw summary panel and draw-entry preview now render direct decision payloads, so any backend field rename must be reflected there first.
- `src/ui/PredictionTracker.js` resolves bet counts defensively across `num_bets`, `avg_bets`, `bet_count`, and `n_bets` to preserve compatibility.

## Archive Policy
- Move one-off session scripts to `tools/archive/`.
- Do not delete files that may be useful for later traceability.
- Record any rejected or retired strategy in `rejected/` with a short rationale and re-test condition.

## Recovery Checklist
- If weekly monitoring goes stale, verify the LaunchAgent plist with `plutil -lint`.
- Re-run `python3 tools/weekly_health_report.py` after any import or path change.
- Re-check the deployed keys in `tools/rsm_bootstrap.py` and the next-draw list in `lottery_api/routes/prediction.py` after every strategy cutover.

## Current Final State
- DAILY_539 is deployed as `acb_1bet`.
- POWER_LOTTO is deployed as `midfreq_fourier_2bet`.
- BIG_LOTTO remains unchanged.