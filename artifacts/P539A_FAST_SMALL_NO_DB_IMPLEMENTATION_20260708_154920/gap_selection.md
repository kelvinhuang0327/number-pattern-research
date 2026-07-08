# P539A Fast Small No-DB Gap Selection

## Context

- Worktree: `/Users/kelvin/Kelvin-WorkSpace/LotteryNew.worktrees/P539A-FAST-SMALL-NO-DB`
- Branch: `p539a-fast-small-no-db-implementation`
- Base: `origin/main` at `fa8387635c81ab0a64980c4da1f246a3fa4351be`
- PR #609 merge commit ancestry: verified ancestor of `origin/main`
- Open PR inventory: only PR #444 was open; PR #444 is hard-excluded by task rule.

## Task-Relevant Constraints

- Risk domains: data-ingestion, canonical-db, scheduled-jobs, timezone-date, stats-methodology, compliance-disclaimer, worktree-debt.
- Do not touch: canonical DB paths, `data/*.db`, pid/runtime/outputs, existing artifacts outside this task evidence, docs/memory/00-Plan/wiki, p273a branch/worktree, PR #444.
- Hard gates: no DB write/open/migration/import/backfill, no service or scheduler startup, no deploy/release, no `.ai` edits.
- Allowed writes used: one frontend source file, one focused static pytest file, and this task evidence directory in the task worktree.

## Selected Gap

`src/ui/AutoFetchManager.js` centralized all ingest UI status messages through `_setStatus`, but the helper only changed visual styling and text. Existing status containers did not consistently expose `role` / `aria-live` semantics, so asynchronous success, warning, loading, and error messages could be missed by assistive technology unless each caller or HTML node handled it separately.

## Why This Gap Is Safe

- Small no-DB frontend accessibility fix.
- No API contract, data semantics, denominator, prediction, betting, scheduler, or runtime behavior changes.
- No new dependency required; native DOM attributes are sufficient.
- Testable with static pytest against the touched JS source.

## Implementation Plan

- Add `role="status"` / `aria-live="polite"` for non-error status messages.
- Add `role="alert"` / `aria-live="assertive"` for error messages.
- Preserve existing status class, display, whitespace, and text assignment behavior.
- Add focused static tests for the helper.

