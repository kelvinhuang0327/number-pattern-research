# P5 Replay Source of Truth Audit - 20260517

## Final Classification
P5_REPLAY_SOURCE_OF_TRUTH_AUDIT_COMPLETED

## P0/P1/P3 Input Summary
- Total strategies: 506
- Lifecycle states: PRODUCTION, WATCHING, PROVISIONAL, REJECTED, OFFLINE, EXPERIMENTAL, UNKNOWN
- Pipeline split: HISTORICAL_RECONSTRUCTION 97, FUTURE_WAITING 2, DISPLAY_ONLY 407, UNSUPPORTED 0
- Replay coverage gap: 13 replay rows, 86 historical-record-no-replay, 407 no-records-anywhere

## Source Map Summary
- DB sources: 5
- JSON / artifact sources: 10
- Runtime read paths: 11

## Source-of-Truth Assessment
- Canonical runtime source: DB
- Deployment safe: False
- Local-only risk: True
- Migration / seed policy required: True
- Artifact promotion policy required: True

## Key Risks Found
- Tracked vs ignored DB risk: the runtime SQLite path under lottery_api/data is ignored by git, while tracked DB copies also exist under data/ and tools/data/.
- Local-only replay rows risk: the replay API reads the ignored local DB path directly, so a clean repo checkout does not guarantee deployable replay state.
- Fixture/runtime mismatch risk: fixture_mode reads a JSON fixture, which is useful for tests but not the normal runtime source.
- Deployment visibility risk: there is no Docker/migration/seed policy in the repo that currently proves production can derive the same replay rows deterministically.

## Recommended Policy
- Canonical runtime source should remain DB, but only a deployment DB that is produced by an explicit migration/seed/promotion policy.
- P0/P1/P3 artifacts should remain governance and dry-run inputs, not runtime truth.
- Replay page acceptance should verify the deployable source, not the local ignored DB file.
- P6 watcher logic should continue to treat DB source-of-truth decisions as a blocker until the deployable path is explicit.

## Safety Confirmation
- No DB write
- No draw import
- No replay row generation
- No prediction update
- No strategy execution

## Current Conclusion
Runtime replay data is DB-backed, but the current repo state is not yet deployment-safe because the working replay DB is local/ignored and the promotion path is not formalized.
