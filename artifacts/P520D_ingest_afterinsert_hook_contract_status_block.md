## P520D Ingest After-Insert Hook Contract

- Final status: `WARN`
- Source path: `lottery_api/routes/ingest.py`
- `_refresh_after_insert` present: `True`
- `_refresh_after_insert` line: `160`
- `_refresh_after_insert` call sites: `[307, 410]`
- Expected live hooks: `['scheduler.load_data', 'refresh_hedge_fund_outputs', 'weight_adjuster', 'learning_integrator']`
- Detected live hook references: `4`
- Call-like live hooks: `4`
- Static target resolution PASS count: `1`
- Static target resolution WARN count: `3`
- Dead hook absence status: `PASS`
- Warning count: `3`
- Failure count: `0`
- Suggested next command: `python -m tools.ingest_afterinsert_hook_contract --status-block`

Warnings:
- refresh_hedge_fund_outputs: import target module path not found by source-only resolution; runtime import not attempted
- weight_adjuster: import target module path not found by source-only resolution; runtime import not attempted
- learning_integrator: import target module path not found by source-only resolution; runtime import not attempted

Safety / scope:
- source/AST-only contract evaluation
- does not import lottery_api.routes.ingest
- does not execute after-insert hooks
- does not execute draw inserts
- no canonical DB open/write
- no migration/backfill
- no deploy
- does not implement replacement scheduler/tracker
- no betting/future prediction claims
