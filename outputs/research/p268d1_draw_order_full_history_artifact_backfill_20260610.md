# P268D-1: drawNumberAppear Full-History Artifact Backfill (Bounded-Rate Prototype)

Generated: 2026-06-10T14:05:09.507812+00:00

## Scope & Constraints
- NO production DB write (`data/lottery_v2.db` never opened by this script).
- NO Hypothesis Registry write (registry-freeze artifact is a design snapshot under `outputs/research/`).
- NO H1/H2/H3 statistical test, permutation test, or p-value (reserved for P268D-3).
- NO hit-rate / success-rate-improvement claim.

## This Run
- **max_calls_per_run**: 60
- **calls_made_this_run**: 60
- **months_attempted_this_run**: ['2008-01', '2008-02', '2008-03', '2008-04', '2008-05', '2008-06', '2008-07', '2008-08', '2008-09', '2008-10', '2008-11', '2008-12']
- **games_attempted_this_run**: ['3_STAR', '4_STAR', 'BIG_LOTTO', 'DAILY_539', 'POWER_LOTTO']
- **new_records_written_this_run**: 989
- **ledger_was_newly_created**: False

## Coverage
- **start_month**: 2007-01
- **end_month**: 2026-05
- **games**: ['BIG_LOTTO', 'POWER_LOTTO', 'DAILY_539', '3_STAR', '4_STAR']
- **total_ledger_cells**: 1165
- **done_cells**: 108
- **empty_cells**: 12
- **error_cells**: 0
- **pending_cells**: 1045

## Parse Results (this run)
- **records_written**: 989
- **correct_length_count**: 989
- **incorrect_length_or_missing_field_count**: 0
- **schema_drift_count_this_run**: 0

## Missing Months By Game (PENDING or ERROR)
- **BIG_LOTTO**: 209 remaining (first 5: ['2009-01', '2009-02', '2009-03', '2009-04', '2009-05'])
- **POWER_LOTTO**: 209 remaining (first 5: ['2009-01', '2009-02', '2009-03', '2009-04', '2009-05'])
- **DAILY_539**: 209 remaining (first 5: ['2009-01', '2009-02', '2009-03', '2009-04', '2009-05'])
- **3_STAR**: 209 remaining (first 5: ['2009-01', '2009-02', '2009-03', '2009-04', '2009-05'])
- **4_STAR**: 209 remaining (first 5: ['2009-01', '2009-02', '2009-03', '2009-04', '2009-05'])

## Limitations
- Bounded-rate prototype: a single run fetches at most 60 (month, lottery_type) cells; full-history coverage requires multiple resumed runs.
- No production DB write performed; artifacts are append-only files under outputs/research/.
- No Hypothesis Registry write performed; the companion registry-freeze artifact is a design-snapshot under outputs/research/, not a write to lottery_api/data/hypothesis_registry.jsonl.
- No H1/H2/H3 statistical test, no permutation test, and no significance value of any kind computed in this task. Reserved for a separate, future, explicitly-authorized confirmatory task (P268D-3).
- No success-rate / hit-rate-improvement claim is made by this artifact.
- On endpoint instability a (month, lottery_type) cell is marked ERROR (not aggressively retried); a future run may retry by resetting that cell's status to PENDING.

## Next-Step Recommendation
Re-run this script in additional bounded sessions (resumable via the ledger) until pending_cells == 0 and error_cells == 0, then proceed to P268D step 4 (structure_validation aggregate report) and step 6 (read-only canonical DB alignment), per p268c ... p268d_implementation_order.

## Final Classification
P268D1_DRAW_ORDER_REGISTRY_FREEZE_AND_FULL_HISTORY_ARTIFACT_BACKFILL_PARTIAL_API_LIMIT
