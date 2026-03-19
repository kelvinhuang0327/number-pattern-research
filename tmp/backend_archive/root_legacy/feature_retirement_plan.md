# Feature Retirement Plan (Phase 2)

Date: 2026-03-13
Default policy: unknown behavior => `HIDE`

## Decision Matrix

| Feature / Area | Decision | Reason | Rollback |
|---|---|---|---|
| Central API URL resolution | KEEP + MERGE | Required for consistency and environment portability | Revert helper import/calls |
| `getDataFromIndexedDB` sync path | FIX (MERGE to existing data API) | Runtime break due missing method implementation | Restore previous call |
| Dual-bet core logic | HIDE (entry-level) | Function still referenced; product intent unclear | Re-enable nav/button display |
| Smart dual-bet UI blocks | KEEP | UI and handlers still connected | N/A |
| `App.js.backup` in source | HIDE | Avoid accidental confusion while preserving history | Move back if needed |
| Direct `fetch` calls bypassing ApiClient | MERGE progressively | Inconsistent retries/timeouts | Keep old call in commit history |

## Retirement Gates (before REMOVE)
- Product owner confirms feature is obsolete.
- 150/500/1500 regression checks show no behavior loss.
- No backend endpoint dependency remains.
- UI path has no visible/hidden activation path.

## Immediate Safe Actions
1. Remove hardcoded host usage by shared API origin utility.
2. Replace broken sync history retrieval call.
3. Keep dual-bet functionality intact; do not delete handlers.
