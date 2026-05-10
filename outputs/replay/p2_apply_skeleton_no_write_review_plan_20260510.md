# P2 Apply Skeleton No-Write Review Plan

## 1. Review Goal

Review a future no-write apply skeleton implementation only.

No apply execution is part of this review.

## 2. Expected Files

- `scripts/p2_lifecycle_backfill_apply_skeleton.py`
- `tests/test_p2_lifecycle_backfill_apply_skeleton.py`
- `outputs/replay/p2_lifecycle_backfill_apply_skeleton_dry_run_20260510.json`
- `outputs/replay/p2_lifecycle_backfill_apply_skeleton_report_20260510.md`

## 3. Forbidden Changes

- No DB writes
- No registry writes
- No active strategy state writes
- No apply mode introduction
- No H6 cleanup
- No branch protection changes

## 4. Required Tests

- Missing approval fails
- Malformed approval artifact fails
- Production DB path rejected
- Any `runtime_write_allowed=true` fails
- Blocked rows excluded
- Parse-error rows excluded
- DB hash unchanged
- No SQL write keywords in the skeleton
- Output report explicitly says no write occurred

## 5. Required Commands

- Validate manifest schema
- Validate manifest sha256
- Validate the approval artifact
- Run the no-write skeleton test suite
- Verify DB hash before/after is unchanged
- Check diff scope for docs-only review

## 6. Manifest Safety Checks

- Confirm `promotable_candidates = 15`
- Confirm `blocked_rows = 26`
- Confirm `parse_error_rows = 1`
- Confirm all rows have `runtime_write_allowed=false`

## 7. DB Safety Checks

- Confirm DB path is non-production
- Confirm DB hash unchanged
- Confirm no write statements were issued

## 8. Registry / Active State Safety Checks

- Confirm no registry writes
- Confirm no active strategy state writes
- Confirm no downstream side effects

## 9. Approval Artifact Checks

- Confirm `approval_scope`
- Confirm `approved_by`
- Confirm `approved_at`
- Confirm `target_manifest_sha256`
- Confirm `allowed_mode = dry_run_only`
- Confirm `explicit_no_db_write = true`

## 10. Failure Markers

- Missing approval artifact
- Malformed approval artifact
- Production DB path
- Any runtime-write-allowed row
- Blocked-row leakage
- Parse-error leakage
- Hash drift

## 11. Success Marker

No-write skeleton review ready, with execution still blocked.

## 12. Next Prompt

Proceed to a no-write skeleton implementation review, not apply execution.

Do not execute apply.