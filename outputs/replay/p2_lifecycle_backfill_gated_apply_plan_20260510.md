# P2 Lifecycle Backfill Gated Apply Plan

## 1. Objective

Design a gated apply path for P2 lifecycle catalog backfill without executing apply.

The goal is to make the 15 promotable candidates eligible for future review under a separate approval gate, while keeping all current runtime data and registry state unchanged.

## 2. Current Baseline

- Dry-run manifest counts: `15 / 26 / 1`
- `runtime_write_allowed=false` for every row
- Database unchanged by the dry-run generator
- Registry unchanged
- No apply mode exists today

## 3. Apply Preconditions

Gated apply must not start unless all of the following are true:

- Human approval is explicitly recorded
- `main` is clean and up to date
- Dry-run manifest is current and deterministic
- No row content drift is present
- A database snapshot exists before any write path is enabled
- Rollback path is confirmed and rehearsed
- Blocked rows are quarantined
- Parse-error rows are quarantined
- Lifecycle source-of-truth is confirmed
- Runtime source must remain DB-backed
- Evidence under `outputs/replay/` cannot be treated as runtime source

## 4. Proposed Apply Architecture

This section defines a future shape only; it does not implement writes.

- Proposed script name: `scripts/apply_p2_lifecycle_backfill.py`
- Input: approved manifest derived from the dry-run contract
- Transaction boundary: one strategy row per transaction, with a higher-level batch guard
- Row-level validation: enforce schema, lifecycle enum, source-of-truth, and approval checks before any write
- Write target: the lifecycle runtime database only, never evidence artifacts
- Audit output: immutable apply report with before/after hashes and validation results
- Rollback output: revert report that records the exact rows and hashes restored
- Post-apply verification: replay API smoke and DB state comparison against the approved manifest

## 5. No-Write Defaults

- Default mode must remain dry-run
- Apply requires an explicit flag
- Apply requires an explicit approval artifact
- `runtime_write_allowed` must remain `false` until an approved manifest exists
- Blocked and parse-error rows can never be auto-applied

## 6. Row Contract

Every future apply row must carry the following fields:

- `strategy_id`
- `lifecycle_status`
- `target_draw` or `target_date`
- `source_evidence`
- `runtime_source`
- `validation_status`
- `validation_reasons`
- `approval_status`
- `rollback_key`
- `before_state_hash`
- `after_state_hash`
- `apply_allowed`

## 7. Validation Gates

Future apply execution must pass these gates in order:

- Manifest schema validation
- Lifecycle enum validation
- Source-of-truth validation
- Blocked-row exclusion
- Parse-error exclusion
- Database snapshot existence
- Transaction dry-run
- Rollback simulation
- Post-apply replay API smoke
- Forbidden-language sweep
- No production DB access unless explicitly approved

## 8. Rollback Plan

Rollback must support all of the following:

- DB snapshot restore
- Audit log replay
- Row-level revert
- Failure marker emission
- No partial unverified state left behind

## 9. Approval Form

Human approval should be captured with one of these scopes:

- Approve planning only
- Approve apply skeleton only
- Approve dry-run apply simulation only
- Approve real DB apply

Default state is planning or skeleton only. Real apply remains blocked until a separate explicit approval exists.

## 10. Risks

- Schema mismatch
- Evidence mistaken as runtime
- Partial apply
- Stale manifest
- Blocked row leakage
- Parse-error leakage
- Lifecycle SSOT mismatch
- Accidental DB write

## 11. Decision

The gated apply path is ready for apply skeleton no-write implementation planning, not for apply execution.

No execution step is authorized by this document.

## 12. Next Executable Prompt

The next allowed step is a gated apply planning review or an apply skeleton no-write implementation.

Do not execute apply.