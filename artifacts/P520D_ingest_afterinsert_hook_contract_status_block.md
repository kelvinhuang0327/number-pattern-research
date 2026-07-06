## P520D Ingest After-Insert Hook Contract

- Final status: `PASS`
- Source path: `lottery_api/routes/ingest.py`
- `_refresh_after_insert` present: `True`
- `_refresh_after_insert` line: `160`
- `_refresh_after_insert` call sites: `[280, 383]`
- Expected live hooks: `['scheduler.load_data']`
- Detected live hook references: `1`
- Call-like live hooks: `1`
- Static target resolution PASS count: `1`
- Static target resolution WARN count: `0`
- Removed missing-target hooks: `['refresh_hedge_fund_outputs', 'weight_adjuster', 'learning_integrator']`
- Missing-target residue status: `PASS`
- Dead hook absence status: `PASS`
- Warning count: `0`
- Failure count: `0`
- Suggested next command: `python -m tools.ingest_afterinsert_hook_contract --status-block`

Warnings:
- none

Safety / scope:
- source/AST-only contract evaluation
- does not import lottery_api.routes.ingest
- does not execute after-insert hooks
- does not execute draw inserts
- historical missing-target hooks are removed from active and disabled surface
- no canonical DB open/write
- no migration/backfill
- no deploy
- does not implement replacement scheduler/tracker
- no betting/future prediction claims
