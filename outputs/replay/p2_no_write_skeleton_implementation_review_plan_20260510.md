# P2 No-Write Skeleton Implementation Review Plan

## 1. Review Purpose

Review the next no-write skeleton implementation path for P2 without executing backfill, without adding apply behavior, and without changing runtime state.

The goal is to confirm the future skeleton stays inside a dry-run / eligibility-only boundary before any implementation work is attempted.

## 2. Source Prompt Artifact

This review plan is derived from [outputs/replay/p2_next_no_write_skeleton_implementation_prompt_20260510.md](outputs/replay/p2_next_no_write_skeleton_implementation_prompt_20260510.md).

That prompt requires a no-write skeleton only and explicitly forbids any real apply execution.

## 3. Expected Future Files

The next implementation step, if ever approved, is expected to introduce only these files:

- `scripts/p2_lifecycle_backfill_apply_skeleton.py`
- `tests/test_p2_lifecycle_backfill_apply_skeleton.py`

No other runtime files should be introduced by the skeleton review outcome.

## 4. Forbidden Changes

The review must reject any plan that includes:

- real apply execution
- backfill execution
- a true apply mode
- DB writes
- production DB writes
- registry writes
- active strategy state writes
- generated fake rows
- strategy mining or edge discovery
- SQL write statements such as `INSERT`, `UPDATE`, `DELETE`, `CREATE`, `DROP`, or `ALTER`

## 5. Required Skeleton Behaviors

The skeleton, if later implemented, must:

- default to dry-run only
- not add an execute flag
- reject any DB write path
- reject any production DB path
- reject any registry write path
- reject any active strategy state write path
- require an approval artifact
- reject malformed approval artifacts
- reject any row where `runtime_write_allowed=true`
- exclude blocked rows
- exclude parse-error rows
- keep the DB hash unchanged before and after
- emit output JSON and report files as no-write artifacts only
- stop immediately on any forbidden condition

## 6. Required Tests

The future test file should verify at minimum:

- dry-run is the default behavior
- no execute mode exists
- forbidden DB / registry / active-state paths are rejected
- approval artifact presence is required
- malformed approval artifacts fail fast
- rows with `runtime_write_allowed=true` are rejected
- blocked rows are excluded
- parse-error rows are excluded
- DB hash is unchanged across the skeleton path
- output JSON and report are generated without writes
- SQL write keywords are absent from the implementation path

## 7. Required Commands

The review should expect these commands to remain read-only:

- `python3 scripts/generate_p2_lifecycle_backfill_dry_run.py`
- `/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.venv/bin/python3 -m pytest tests/test_p2_lifecycle_backfill_dry_run.py -x`
- `git diff --check`

If a future skeleton branch is created, its validation should still avoid any command that mutates DB, registry, or active strategy state.

## 8. Manifest No-Write Requirements

The manifest contract must remain:

- `promotable_candidates = 15`
- `blocked_rows = 26`
- `parse_error_rows = 1`
- every row has `runtime_write_allowed=false`
- DB hash stays unchanged
- no runtime artifact becomes a source of truth for writes

## 9. DB / Registry / Active State Safety Requirements

The review must ensure the future skeleton never:

- mutates the runtime DB
- mutates registry state
- mutates active strategy state
- uses a production DB path
- treats evidence reports as runtime source data

Any plan that crosses these boundaries is rejected.

## 10. Approval Artifact Requirements

The future skeleton must require an approval artifact before any eligibility path continues.

The artifact must be:

- present
- well-formed
- explicitly approved for the targeted no-write review path

Malformed, missing, or ambiguous approval artifacts must fail fast.

## 11. Production DB Rejection Requirements

The skeleton must reject any production DB path immediately.

It must also reject any path that would implicitly target production through environment inference, fallback behavior, or ambiguous configuration.

## 12. Failure Markers

If review finds any of the following, the plan is blocked:

- `P2_NO_WRITE_SKELETON_REVIEW_BLOCKED_forbidden_write_path`
- `P2_NO_WRITE_SKELETON_REVIEW_BLOCKED_missing_approval_artifact`
- `P2_NO_WRITE_SKELETON_REVIEW_BLOCKED_malformed_approval_artifact`
- `P2_NO_WRITE_SKELETON_REVIEW_BLOCKED_runtime_write_allowed_true`
- `P2_NO_WRITE_SKELETON_REVIEW_BLOCKED_manifest_content_drift`
- `P2_NO_WRITE_SKELETON_REVIEW_BLOCKED_unexpected_dirty_scope`
- `P2_NO_WRITE_SKELETON_REVIEW_BLOCKED_apply_mode_introduced`

## 13. Success Marker

`P2_NO_WRITE_SKELETON_IMPLEMENTATION_REVIEW_READY`

## 14. Next Executable Prompt

When this review plan is accepted, the next allowed step is a no-write skeleton implementation review only.

Do not execute apply.
Do not execute backfill.
Do not add a real apply mode.