# P2 Apply Skeleton No-Write Implementation Spec

## 1. Objective

Prepare a future no-write apply skeleton implementation.

No apply execution is authorized by this spec.
No DB writes are authorized by this spec.

## 2. Scope

- Future skeleton script only
- Dry-run default
- Approval artifact required
- Production DB forbidden
- Registry write forbidden
- Active strategy state write forbidden

## 3. Proposed Files

- `scripts/p2_lifecycle_backfill_apply_skeleton.py`
- `tests/test_p2_lifecycle_backfill_apply_skeleton.py`
- `outputs/replay/p2_lifecycle_backfill_apply_skeleton_dry_run_20260510.json`
- `outputs/replay/p2_lifecycle_backfill_apply_skeleton_report_20260510.md`

## 4. CLI Contract

Proposed flags:

- `--manifest`
- `--dry-run`
- `--approval-artifact`
- `--db-path`
- `--output-json`
- `--output-report`

Required default behavior:

- `--dry-run` is true by default
- No `--execute` flag in the first skeleton
- No writes even if approval exists
- Production DB path is rejected

## 5. Approval Artifact Contract

The approval artifact must contain:

- `approval_scope`
- `approved_by`
- `approved_at`
- `target_manifest_sha256`
- `allowed_mode = dry_run_only`
- `explicit_no_db_write = true`

## 6. Validation Contract

The skeleton must validate:

- Manifest schema
- Manifest sha256
- All `runtime_write_allowed=false`
- Blocked rows excluded
- Parse-error rows excluded
- Lifecycle enum
- DB path is non-production
- DB hash before / after unchanged
- Registry unchanged
- Active strategy state unchanged

## 7. Output Contract

JSON output must include:

- `mode = dry_run_only`
- `apply_attempted = false`
- `db_write_attempted = false`
- `db_sha256_before`
- `db_sha256_after`
- `db_sha256_unchanged`
- `promotable_candidates_seen`
- `blocked_rows_seen`
- `parse_error_rows_seen`
- `validation_status`
- `validation_reasons`

## 8. Test Contract

Required tests:

- Missing approval artifact fails safely
- Malformed approval artifact fails safely
- Production DB path rejected
- Any `runtime_write_allowed=true` fails
- Blocked rows excluded
- Parse-error rows excluded
- DB hash unchanged
- No `INSERT` / `UPDATE` / `DELETE` / `CREATE` / `DROP` / `ALTER` in the skeleton
- Output report explicit no-write

## 9. Non-Goals

- No actual apply
- No DB writes
- No registry writes
- No active strategy writes
- No branch protection changes
- No H6 cleanup

## 10. Readiness Decision

The next step can be a no-write skeleton implementation only.

It must not become real apply execution.

## 11. Next Executable Prompt

Produce the next prompt for implementation skeleton only.

Do not execute apply.