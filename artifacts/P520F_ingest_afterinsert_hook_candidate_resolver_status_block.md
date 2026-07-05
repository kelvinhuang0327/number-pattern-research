# P520F ingest after-insert hook candidate resolver status

- Final status: `WARN`
- P520E final status: `WARN`
- Unresolved hook count: `3`
- Candidate count: `145`
- Reference count: `148`
- Source files scanned: `1694`
- Parse error count: `3`
- Confidence counts: `{'HIGH': 0, 'MEDIUM': 6, 'LOW': 139}`
- Candidate count by hook: `{'learning_integrator': 19, 'refresh_hedge_fund_outputs': 59, 'weight_adjuster': 67}`
- Target confirmed by hook: `{'learning_integrator': False, 'refresh_hedge_fund_outputs': False, 'weight_adjuster': False}`
- PASS/WARN/FAIL counts: `0/3/0`

## Scope notices
- source/AST-only candidate resolver
- reads P520E unresolved artifacts
- repo-wide Python source scan only
- does not import lottery_api.routes.ingest
- does not import live hook target modules
- does not execute after-insert hooks
- does not execute draw inserts
- no canonical DB open/write
- no migration/backfill
- no deploy
- does not implement or modify hooks
- no betting/future prediction claims

## Warnings
- learning_integrator: static candidates only; target remains unconfirmed without direct HIGH evidence
- refresh_hedge_fund_outputs: static candidates only; target remains unconfirmed without direct HIGH evidence
- weight_adjuster: static candidates only; target remains unconfirmed without direct HIGH evidence
