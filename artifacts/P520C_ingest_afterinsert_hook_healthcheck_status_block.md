## P520C Ingest After-Insert Hook Healthcheck

- Final status: `PASS`
- Source path: `lottery_api/routes/ingest.py`
- `_refresh_after_insert` present: `True`
- `_refresh_after_insert` line: `160`
- `_refresh_after_insert` call sites: `[307, 410]`
- Detected live hook count: `4`
- Missing or renamed live hooks: `[]`
- Dead hook absence status: `PASS`
- Warning count: `0`
- Failure count: `0`
- Suggested next command: `python -m tools.ingest_afterinsert_hook_healthcheck --status-block`

Safety / scope:
- source/AST-only healthcheck
- does not import lottery_api.routes.ingest
- does not execute draw inserts
- no canonical DB open/write
- no migration/backfill
- no deploy
- does not implement replacement scheduler/tracker
- no betting/future prediction claims
