## P520E Ingest After-Insert Hook Target Audit

- Final status: `WARN`
- Source path: `lottery_api/routes/ingest.py`
- `_refresh_after_insert` present: `True`
- `_refresh_after_insert` line: `160`
- Expected live hooks: `['scheduler.load_data']`
- Removed missing-target hooks: `['refresh_hedge_fund_outputs', 'weight_adjuster', 'learning_integrator']`
- Missing-target residue status: `PASS`
- Target audit rows: `1`
- Resolved source count: `1`
- Unresolved source count: `0`
- Target symbol found count: `1`
- DB indicator count: `0`
- File-output indicator count: `9`
- Runtime-side-effect indicator count: `8`
- PASS/WARN/FAIL counts: `0/1/0`
- Warning count: `1`
- Failure count: `0`
- Suggested next command: `python -m tools.ingest_afterinsert_hook_target_audit --status-block`

Warnings:
- scheduler.load_data: target source resolved with side-effect indicators; review matrix/risk CSV

Safety / scope:
- source/AST-only target audit
- does not import lottery_api.routes.ingest
- does not import live hook target modules
- does not execute after-insert hooks
- does not execute draw inserts
- historical missing-target hooks are removed from active and disabled surface
- no canonical DB open/write
- no migration/backfill
- no deploy
- does not implement or modify hooks
- no betting/future prediction claims
