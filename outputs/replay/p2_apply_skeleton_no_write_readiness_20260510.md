# P2 Apply Skeleton No-Write Readiness

## 1. Purpose

Prepare for a future no-write apply skeleton only.

No apply execution is authorized by this document.

## 2. Preconditions

- PR #17 is open, mergeable, and still waiting approval
- PR #18 is open, mergeable, and still waiting approval
- Dry-run manifest counts remain `15 / 26 / 1`
- All rows have `runtime_write_allowed=false`
- DB remains unchanged by the dry-run path
- Registry remains unchanged

## 3. Proposed Skeleton Boundaries

- Proposed script name: `scripts/apply_p2_lifecycle_backfill_skeleton.py`
- Proposed CLI shape: explicit `--dry-run` default plus a separate approval artifact path
- Default mode must stay dry-run
- Explicit approval artifact required before any future write-capable path is considered
- Production DB access must be forbidden by default
- Blocked rows and parse-error rows must remain excluded

## 4. Non-Goals

- No DB writes
- No registry writes
- No runtime apply
- No strategy mining
- No H6 cleanup

## 5. Required Future Tests

- Missing approval fails
- Apply flag without approval fails
- Production DB path fails
- Blocked rows excluded
- Parse-error rows excluded
- `runtime_write_allowed=false` blocks writes
- DB hash unchanged in no-write mode

## 6. Readiness Decision

The next task can be a no-write skeleton implementation review.

It must not become a real apply implementation.

## 7. Next Executable Prompt

Start a no-write apply skeleton implementation review.

Do not execute apply.