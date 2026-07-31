# P213L Controlled Missing Source-Row Ingestion

Date: 2026-06-05

Classification: `P213L_3STAR_4STAR_CONTROLLED_MISSING_SOURCE_ROW_INGESTION_COMPLETE`

Task type: Type D production DB write / controlled missing-row ingestion.

Authorization: `Authorize P213L controlled missing source-row ingestion for 3_STAR/4_STAR (DB write authorized, backup required, insert missing source rows only, no strategy scan)`

## 1. Scope And Explicit DB-Write Authorization

P213L inserted only the 3_STAR / 4_STAR source-only rows validated by P213I and designed by P213K. Existing rows were not updated, deleted, or rewritten.

## 2. Backup

- Backup path: `backups/p213l_lottery_v2_backup_20260605_20260605_151715.db`
- Backup sha256: `1b2abd793a3ea3f2d300337eb2db6d2621b52e1600453bc20141377fa6475485`
- Backup integrity: `ok`

## 3. Pre-Write DB Baseline

- Production replay rows before: `94924`
- Draw rows before: `59762`
- 3_STAR rows before: `4179`
- 4_STAR rows before: `2922`
- Star positional rows before: `7101`

## 4. Source Evidence

- Source rows parsed: `11700`
- Existing DB matched rows: `7101`
- Missing source rows from P213K: `4599`
- Expected insert count: `4599`

## 5. Insertion Method

Rows were inserted from P213I `MISSING_IN_DB` records only. The script stored sorted canonical numbers in `numbers` and source positional order in `numbers_positional`. The unique key was `(draw, lottery_type)`.

## 6. Insertion Counts

- Rows inserted: `4599`
- Rows skipped existing: `0`
- Rows skipped mismatch: `0`
- Rows skipped non-star: `0`

## 7. Post-Write DB Baseline

- Production replay rows after: `94924`
- Draw rows after: `64361`
- Replay rows changed: `False`
- Numbers column changed: `False`
- Numbers positional inserted count: `4599`
- Non-star rows touched: `0`

## 8. Drift Guard

`REPLAY_LIFECYCLE_DRIFT_GUARD_PASS`

## 9. Verification Queries

- DB integrity: `ok`
- bet_index nulls: `0`
- duplicate replay keys: `0`
- draw rows increased by inserted count only
- existing matched rows unchanged
- inserted rows have `numbers_positional` populated

## 10. Rollback Instruction

Restore backup over lottery_api/data/lottery_v2.db only with explicit rollback authorization.

## 11. Remaining Limitations

P213L completes draw-side coverage for the validated P213I source set. It does not create replay rows, strategy predictions, scans, recommendations, or betting claims.

## 12. Next Direction

Return to `WAITING_FOR_USER_AUTHORIZATION`. Any straight-play dry-run, scan, strategy work, or product change requires separate explicit authorization.

## 13. Safety / No-Claim Attestation

- No registry mutation: `True`
- No production recommendation change: `True`
- No monitoring change: `True`
- No strategy authorization: `True`
- No betting advice: `True`
- P238B interpretation: `RANDOMNESS_AUDIT_YELLOW_OBSERVATION_ONLY - observation only; no strategy, production, recommendation, monitoring, DB write, or betting implication.`
