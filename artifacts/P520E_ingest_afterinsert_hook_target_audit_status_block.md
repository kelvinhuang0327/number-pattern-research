## P520E Ingest After-Insert Hook Target Audit

- Final status: `WARN`
- Source path: `lottery_api/routes/ingest.py`
- `_refresh_after_insert` present: `True`
- `_refresh_after_insert` line: `160`
- Expected live hooks: `['scheduler.load_data', 'refresh_hedge_fund_outputs', 'weight_adjuster', 'learning_integrator']`
- Target audit rows: `4`
- Resolved source count: `1`
- Unresolved source count: `3`
- Target symbol found count: `1`
- DB indicator count: `0`
- File-output indicator count: `9`
- Runtime-side-effect indicator count: `8`
- PASS/WARN/FAIL counts: `0/4/0`
- Warning count: `4`
- Failure count: `0`
- Suggested next command: `python -m tools.ingest_afterinsert_hook_target_audit --status-block`

Warnings:
- scheduler.load_data: target source resolved with side-effect indicators; review matrix/risk CSV
- refresh_hedge_fund_outputs: source path unresolved by static source mapping; runtime import not attempted
- weight_adjuster: source path unresolved by static source mapping; runtime import not attempted
- learning_integrator: source path unresolved by static source mapping; runtime import not attempted

Safety / scope:
- source/AST-only target audit
- does not import lottery_api.routes.ingest
- does not import live hook target modules
- does not execute after-insert hooks
- does not execute draw inserts
- no canonical DB open/write
- no migration/backfill
- no deploy
- does not implement or modify hooks
- no betting/future prediction claims
