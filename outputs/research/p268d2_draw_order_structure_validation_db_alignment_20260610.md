# P268D-2 Draw-Order Structure Validation + Read-Only DB Alignment

Generated: 2026-06-10T14:32:31.022640+00:00

## P268D-1 Boundary

P268D-1 (PR #409, merged) produced a registry-freeze artifact (hypotheses H1/H1_holdout/H2/H3 status=FROZEN_NOT_TESTED, final_classification=P268D1_DRAW_ORDER_REGISTRY_FREEZE_ARTIFACT_COMPLETE) and a full-history drawNumberAppear backfill artifact (final_classification=P268D1_DRAW_ORDER_REGISTRY_FREEZE_AND_FULL_HISTORY_ARTIFACT_BACKFILL_COMPLETE, coverage=2007-01..2026-05, records=21682, pending_cells=0, error_cells=0, empty_cells=12). No H1/H2/H3 test, no DB write, no Hypothesis Registry write, no hit-rate claim were made by P268D-1.

## Structure Validation Summary

- Records checked: 21682 (expected 21682, matches=True)
- Games seen: 3_STAR, 4_STAR, BIG_LOTTO, DAILY_539, POWER_LOTTO
- drawNumberAppear present: 21682/21682
- Parse success: 21682/21682 (100.0000%)
- Correct length: 21682/21682 (100.0000%)
- sorted(drawNumberAppear) matches drawNumberSize flag: 9930/21682
- Duplicate (lottery_type, period) keys: 0
- Schema drift entries: 0
- Ledger cells: total=1165, DONE=1153, EMPTY=12, ERROR=0, PENDING=0
- JSONL vs ledger record-count mismatches: 0

## Read-Only DB Alignment Summary

- DB path: `data/lottery_v2.db`
- Opened read-only (mode=ro): True
- Tables inspected: draws, prediction_items, prediction_results, prediction_review_status, prediction_runs, review_actions, review_findings, review_hypotheses, review_sessions, shadow_experiments, snapshot_schedule, sqlite_sequence, strategy_prediction_replays, strategy_replay_runs
- Views inspected: (none)
- Canonical BIG_LOTTO view present: False
- `draws` table present: True, row count: 0
- Rows available per lottery: {}
- Matched records per lottery: {}
- Unmatched artifact records: ALL (no DB rows to compare against)
- Unmatched DB records: 0
- Date range overlap: NOT_COMPUTABLE_NO_DB_ROWS
- Verdict: **PARTIAL_ENV_LIMITATION** -- data/lottery_v2.db 'draws' table has 0 rows in this environment (consistent with P268B finding DB alignment = NO_LOCAL_ROWS). No row-level alignment is possible; structural schema (table/columns) was inspected read-only and is consistent with the P268D-1 artifact's key fields (lottery_type, draw identifier/period, date, numbers).

## Data-Quality Gate Verdict

- Overall verdict: **STRUCTURE_PASS_DB_ALIGNMENT_PARTIAL_ENV_LIMITATION**
- Can P268D-3 proceed: **True**
- Allowed next scope for P268D-3: P268D-3 may proceed with: (1) within-draw permutation null model construction for H1/H1_holdout (per-ball exit-rank heterogeneity), using DAILY_539 as primary game and BIG_LOTTO/POWER_LOTTO as secondary, per the registry-freeze windows/baseline/correction definitions; (2) computing the H1 statistic and its permutation p-value as a confirmatory test (single pre-registered hypothesis, P221F guardrails). P268D-3 must NOT write to the production Hypothesis Registry until results are reviewed; results should be written to a new outputs/research/ artifact first. DB write remains forbidden -- this is a read-only-source confirmatory analysis using the P268D-1 JSONL artifact (DB alignment for this environment is PARTIAL_ENV_LIMITATION / NO_LOCAL_ROWS, so the JSONL artifact, not the local DB, is the data source for P268D-3).

## Explicit Non-Claims

- No H1/H2/H3 statistical test, no permutation test, and no significance value of any kind was computed in this task. Reserved for a separate, future, explicitly-authorized confirmatory task (P268D-3).
- No production database write was performed (data/lottery_v2.db opened read-only via sqlite3 URI mode=ro, no INSERT/UPDATE/DELETE/DDL).
- No write to lottery_api/data/hypothesis_registry.jsonl was performed.
- No new strategy was generated and no betting recommendation is made.
- No hit-rate / success-rate-improvement claim is made by this artifact.

Final Classification: `P268D2_DRAW_ORDER_STRUCTURE_VALIDATION_DB_ALIGNMENT_COMPLETE_DB_ALIGNMENT_PARTIAL`
