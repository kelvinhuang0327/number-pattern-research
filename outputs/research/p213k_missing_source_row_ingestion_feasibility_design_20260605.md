# P213K Missing Source-Row Ingestion Feasibility Design

Date: 2026-06-05

Classification: `P213K_MISSING_SOURCE_ROW_INGESTION_FEASIBILITY_DESIGN_COMPLETE`

Task type: Type B read-only design artifact.

Authorization: `Authorize P213K missing source-row ingestion feasibility/design only (read-only, no DB write, no ingestion)`

## 1. Scope And Non-Goals

This artifact evaluates whether and how the 4,599 P213I source-only 3_STAR / 4_STAR rows could be handled in a future governed ingestion task.

In scope:

- Read P213I and P213H artifacts.
- Inspect production DB schema and row counts with SELECT / PRAGMA only.
- Identify missing-row inventory, key assumptions, validation gates, backup and rollback requirements.
- Recommend whether future Type D ingestion is feasible.

Non-goals:

- No DB write.
- No ingestion.
- No migration.
- No controlled_apply.
- No registry, production recommendation, monitoring, strategy, straight-play scan, box-play re-scan, or betting advice.
- No cleanup of unrelated dirty files.
- No fix for the minor P211 wording inconsistency across governance docs.

## 2. P213H Current State Recap

P213H completed a Type D controlled positional backfill for existing DB rows only.

| Metric | Value |
|---|---:|
| Source rows parsed | 11,700 |
| Existing DB matched rows | 7,101 |
| Rows updated with `numbers_positional` | 7,101 |
| Missing source-only rows left uninserted | 4,599 |
| Mismatches | 0 |
| 3_STAR positional rows | 4,179 |
| 4_STAR positional rows | 2,922 |
| Non-star rows touched | 0 |
| Replay rows before/after | 94,924 / 94,924 |
| Draw rows before/after | 59,762 / 59,762 |
| Drift guard | `REPLAY_LIFECYCLE_DRIFT_GUARD_PASS` |

Backup evidence:

- `backups/p213h_lottery_v2_backup_20260605_20260605_142219.db`
- sha256 `214f05870e741164495cd0dbf46158ba1e92835d7a7c072df47a20a0795896c1`

## 3. Missing-Row Inventory

The 4,599 rows are P213I source rows whose status is `MISSING_IN_DB`. They are not mismatches. They have no exact `(lottery_type, draw)` row in production `draws`.

| Lottery | Missing source-only rows |
|---|---:|
| 3_STAR | 1,671 |
| 4_STAR | 2,928 |
| Total | 4,599 |

Year distribution:

| Year | Missing rows |
|---|---:|
| 2007 | 223 |
| 2008 | 210 |
| 2009 | 199 |
| 2010 | 204 |
| 2011 | 245 |
| 2012 | 251 |
| 2013 | 256 |
| 2014 | 247 |
| 2015 | 245 |
| 2016 | 258 |
| 2017 | 248 |
| 2018 | 233 |
| 2019 | 236 |
| 2020 | 236 |
| 2021 | 238 |
| 2022 | 244 |
| 2023 | 249 |
| 2024 | 258 |
| 2025 | 247 |
| 2026 | 72 |

Range:

| Lottery | Earliest date | Latest date | Min draw number | Max draw number |
|---|---|---|---:|---:|
| 3_STAR | 2007/01/01 | 2026/04/16 | 96000001 | 115000094 |
| 4_STAR | 2007/01/01 | 2026/04/30 | 96000001 | 115000106 |

Source-file distribution is broad across 40 real CSV files under `00-Plan/roadmap/number`. The largest missing contributors are 4_STAR files, including 2015 (165), 2016 (164), 2023 (162), 2024 (161), 2014 (159), 2012 (158), and 2017 (158). The gap is not isolated to one file or one year.

Additional read-only checks:

- Source duplicate `(lottery_type, draw)` keys: 0.
- Missing duplicate `(lottery_type, draw)` keys: 0.
- Exact missing keys found in DB: 0.
- Same-lottery same-date substitute rows in DB for missing candidates: 0.
- P213I mismatches: 0.

## 4. Root-Cause Hypotheses

Most likely cause: historical coverage gap in the production `draws` table for 3_STAR / 4_STAR.

Evidence:

- P213I classified all 4,599 non-matches as `MISSING_IN_DB` with reason `No matching DB row`.
- There were 0 canonical-number mismatches and 0 date mismatches.
- The source rows contain valid draw ids, dates, positional numbers, and canonical sorted numbers.
- No source duplicate keys were found.
- A direct read-only DB check found 0 exact `(lottery_type, draw)` matches for the missing set.
- A same-lottery same-date DB check found 0 substitute rows for the missing set.

Less likely causes:

- Duplicate key mismatch: not supported by evidence because duplicate source keys are 0.
- Date/draw-id mismatch: not supported by evidence because there are no same-lottery same-date substitute rows and no P213I date mismatch status.
- Source/version issue: possible in theory, but not indicated by P213I; the source is real CSV data with positional order encoded in `numbered prize` columns and broad year/file coverage.

## 5. Existing DB Schema And Constraints

`draws` schema summary:

| Column | Constraint |
|---|---|
| `id` | INTEGER PRIMARY KEY AUTOINCREMENT |
| `draw` | TEXT NOT NULL |
| `date` | TEXT NOT NULL |
| `lottery_type` | TEXT NOT NULL |
| `numbers` | TEXT NOT NULL |
| `special` | INTEGER DEFAULT 0 |
| `created_at` | TEXT DEFAULT CURRENT_TIMESTAMP |
| `jackpot_amount` | REAL DEFAULT NULL |
| `sell_amount` | REAL DEFAULT NULL |
| `total_amount` | REAL DEFAULT NULL |
| `numbers_positional` | TEXT DEFAULT NULL |

Constraints and indexes:

- `UNIQUE(draw, lottery_type)`
- `idx_lottery_type ON draws(lottery_type)`
- `idx_date ON draws(date DESC)`
- `idx_draw ON draws(draw)`

The safe insertion key for future ingestion is therefore `(draw, lottery_type)`.

## 6. Proposed Safe Insertion Key And Validation Rules

Future insertion candidates must be built only from P213I source rows with:

- `status == MISSING_IN_DB`
- `lottery_type IN ('3_STAR', '4_STAR')`
- unique `(lottery_type, draw)`
- no existing production DB row for `(lottery_type, draw)`
- no same-lottery same-date substitute row unless explicitly explained in a new dry-run artifact
- positional digit count exactly 3 for 3_STAR and 4 for 4_STAR
- every digit integer 0-9
- `canonical_numbers == sorted(positional_numbers)`
- `numbers` value would be JSON of canonical sorted numbers
- `numbers_positional` value would be JSON of source positional order
- `special` would remain 0 / no-special semantics for these lottery types
- jackpot / sell / total amounts would remain NULL unless a future source-specific artifact proves trusted values

## 7. Required Pre-Ingestion Gates

Any future insertion is Type D and requires:

1. Fresh Phase 0 on canonical repo `main`, HEAD equal to `origin/main`, staged files 0.
2. DB integrity `ok`.
3. `strategy_prediction_replays` rows remain 94,924.
4. `bet_index` nulls remain 0.
5. Duplicate replay keys remain 0.
6. Drift guard PASS.
7. Fresh immutable backup plus sha256.
8. Backup integrity check returns `ok`.
9. Re-parse source files and confirm 11,700 source rows, 7,101 existing matches, 4,599 missing source-only rows, and 0 mismatches, unless a new source artifact explains drift.
10. Dry-run exact insert set and require would-insert count equals 4,599, duplicate count 0, mismatch count 0.
11. Confirm production `draws` row count would increase by exactly 4,599 and replay rows would remain 94,924.
12. Confirm non-star rows are untouched.
13. Confirm no strategy scan, recommendation, registry mutation, monitoring, controlled_apply, or betting advice is included.

## 8. Backup And Rollback Requirements

Backup plan for future Type D:

- Create `backups/p213l_lottery_v2_backup_YYYYMMDD_HHMMSS.db`.
- Create matching `.sha256`.
- Run `PRAGMA integrity_check` on the backup and require `ok`.
- Record backup path and sha256 in the future artifact and governance closeout.

Rollback plan:

- Restore backup over `lottery_api/data/lottery_v2.db` only with separate explicit rollback authorization.
- After rollback, verify DB integrity, replay rows 94,924, draw rows restored to pre-ingestion count, and drift guard PASS.

## 9. Handling Duplicates, Conflicts, And Mismatches

Future ingestion must use a strict candidate classifier:

- `INSERT`: source row is missing in DB, key unique, valid digits, valid canonical numbers.
- `SKIP_ALREADY_EXISTS`: key appears in DB at future apply time.
- `SKIP_SOURCE_DUPLICATE`: duplicate source `(lottery_type, draw)` key appears.
- `SKIP_DATE_CONFLICT`: same-lottery same-date substitute row appears.
- `SKIP_MISMATCH`: canonical or positional validation fails.

Any non-zero conflict or mismatch count should stop the Type D write unless the future authorization explicitly allows a narrower partial insertion set.

## 10. Required Post-Ingestion Verification If Future DB Write Is Authorized

Expected future post-ingestion checks:

- DB integrity `ok`.
- `strategy_prediction_replays` remains 94,924.
- `draws` increases from 59,762 to 64,361 if all 4,599 rows are inserted.
- 3_STAR draw rows increase from 4,179 to 5,850.
- 4_STAR draw rows increase from 2,922 to 5,850.
- Star `numbers_positional` populated rows increase from 7,101 to 11,700.
- `numbers` column canonical sorted values match source canonical values.
- `numbers_positional` values match source positional order.
- Non-star `numbers_positional` count remains 0.
- Drift guard PASS.
- Idempotent rerun would insert 0 additional rows.

## 11. Interaction With Straight-Play Future Work

Missing-row ingestion should occur before any full historical straight-play scan. Otherwise, straight-play evidence would be based on partial coverage and could bias window counts, year coverage, and apparent stability.

Straight-play dry-run on existing rows only is technically safe only as a labeled partial-coverage smoke test or design review. It should not be treated as complete historical evidence, a strategy signal, a recommendation, or a betting edge.

No straight-play scan is authorized by P213K.

## 12. Recommendation

Recommendation: future Type D controlled missing-row ingestion gate is feasible, but should not be executed without separate explicit authorization.

Preferred order:

1. HOLD unless the user wants to complete historical draw coverage.
2. If moving forward, run future Type D ingestion gate for source-only rows.
3. Only after complete draw coverage, consider a separate straight-play dry-run design or scan authorization.

## 13. Exact Authorization Phrase For Next Task

`Authorize P213L controlled missing source-row ingestion gate for 3_STAR/4_STAR (Type D DB write, backup required, insert source-only rows only, no strategy scan, no recommendation change)`

## 14. No-Claim Attestation

- No betting advice.
- No recommended numbers.
- No strategy promotion.
- No prediction improvement claim.
- No production recommendation change.
- No registry mutation.
- No monitoring change.
- No DB write.
- No ingestion performed.
- P238B remains `RANDOMNESS_AUDIT_YELLOW_OBSERVATION_ONLY`.

## 15. Governance Note

P213J identified a minor P211 wording inconsistency: `active_task.md` / `CURRENT_STATE.md` still mention `HELD_BY_USER`, while later `CEO-Decision.md` says P211R ran and P211 is no longer held. P213K notes this but does not fix it because the task did not authorize that scope.
