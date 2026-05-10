# Next No-Write Skeleton Implementation Prompt

Create a no-write apply skeleton implementation only.

Required work:

- Create `scripts/p2_lifecycle_backfill_apply_skeleton.py`
- Create `tests/test_p2_lifecycle_backfill_apply_skeleton.py`
- Default to dry-run only
- Do not add an execute flag
- Reject any DB write path
- Reject any production DB path
- Reject any registry write path
- Reject any active strategy state write path
- Require an approval artifact
- Reject malformed approval artifacts
- Reject any row where `runtime_write_allowed=true`
- Exclude blocked rows
- Exclude parse-error rows
- Keep DB hash unchanged before and after
- Emit output JSON and report as no-write artifacts
- Do not use `INSERT`, `UPDATE`, `DELETE`, `CREATE`, `DROP`, or `ALTER`
- Do not add any real apply mode
- Do not execute backfill
- Do not merge any PR without explicit YES

Implementation boundaries:

- The skeleton must only validate inputs and report dry-run eligibility
- The skeleton must never mutate the runtime DB
- The skeleton must never mutate registry state
- The skeleton must never mutate active strategy state
- The skeleton must stop immediately on any forbidden condition

Review expectation:

- The next step is a no-write skeleton implementation review
- The next step is not apply execution

Do not execute apply.# Next No-Write Skeleton Implementation Prompt

Create a no-write apply skeleton implementation only.

Required work:

- Create `scripts/p2_lifecycle_backfill_apply_skeleton.py`
- Create `tests/test_p2_lifecycle_backfill_apply_skeleton.py`
- Default to dry-run only
- Do not add an execute flag
- Reject any DB write path
- Reject any production DB path
- Reject any registry write path
- Reject any active strategy state write path
- Require an approval artifact
- Reject malformed approval artifacts
- Reject any row where `runtime_write_allowed=true`
- Exclude blocked rows
- Exclude parse-error rows
- Keep DB hash unchanged before and after
- Emit output JSON and report as no-write artifacts
- Do not use `INSERT`, `UPDATE`, `DELETE`, `CREATE`, `DROP`, or `ALTER`
- Do not add any real apply mode
- Do not execute backfill
- Do not merge any PR without explicit YES

Implementation boundaries:

- The skeleton must only validate inputs and report dry-run eligibility
- The skeleton must never mutate the runtime DB
- The skeleton must never mutate registry state
- The skeleton must never mutate active strategy state
- The skeleton must stop immediately on any forbidden condition

Review expectation:

- The next step is a no-write skeleton implementation review
- The next step is not apply execution

Do not execute apply.