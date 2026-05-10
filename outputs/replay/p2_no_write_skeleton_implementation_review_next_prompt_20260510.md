# P2 No-Write Skeleton Implementation Review Next Prompt

Use this prompt only for a no-write skeleton implementation review.

This task may create skeleton script/test only if the user explicitly asks to implement in a later turn.

In this task, implementation is allowed only as a no-write skeleton.

## Required Review Scope

- Default mode must be dry-run only
- No execute flag may be added
- No DB writes may occur
- No production DB writes may occur
- No registry writes may occur
- No active strategy state writes may occur
- No real apply mode may be added
- No backfill execution may occur
- No apply execution may occur
- No merge may happen without explicit YES

## Required Input Constraints

- An approval artifact is required and must be `dry_run_only`
- A malformed approval artifact must be rejected
- A missing approval artifact must be rejected
- Any row with `runtime_write_allowed=true` must be rejected
- Blocked rows must be excluded
- Parse-error rows must be excluded
- The DB hash before and after must remain unchanged

## Required Output Constraints

- Output JSON must explicitly prove no-write behavior
- Markdown report must explicitly prove no-write behavior
- Output artifacts must not be treated as runtime source data

## Required Forbidden Tokens and Paths

- No `INSERT`
- No `UPDATE`
- No `DELETE`
- No `CREATE`
- No `DROP`
- No `ALTER`
- No production DB path acceptance
- No fallback to production inference

## Required Review Checklist

Use the combined guidance from the PR #24 prompt and PR #27 review plan to verify that the next implementation review only accepts a dry-run-only skeleton.

The checklist must confirm:

- no-write skeleton only
- no apply execution
- no DB writes
- no production DB writes
- no registry writes
- no active strategy writes
- no real apply mode
- no execute flag
- approval artifact required
- malformed approval rejected
- production DB rejected
- `runtime_write_allowed=true` rejected
- blocked rows excluded
- parse-error rows excluded
- DB hash unchanged before and after
- output JSON and MD report are explicitly no-write

## Required Review Outcome

The next allowed step is a no-write skeleton implementation review only.

Do not execute apply.
Do not execute backfill.
Do not add a real apply mode.
Do not add skeleton implementation code unless the user explicitly requests an implementation turn.

## Final Marker

P2_NO_WRITE_SKELETON_IMPLEMENTATION_REVIEW_NEXT_PROMPT_READY