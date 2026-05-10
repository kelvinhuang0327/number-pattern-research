# P2 Lifecycle Catalog Backfill Plan

## P2 Objective

Backfill the replay lifecycle catalog so Replay can read canonical lifecycle coverage for non-ONLINE strategies from trusted runtime sources, without fabricating rows or using report files as runtime data.

The intended end state is:
- Replay runtime remains DB-first for replay rows.
- Lifecycle classification is backed by trusted catalog/source-of-truth data.
- OFFLINE / REJECTED / OBSERVATION / RETIRED are represented truthfully, not inferred from empty-state copy.

## Current Lifecycle DB Snapshot

### Raw runtime schema

The local replay DB at `lottery_api/data/lottery_v2.db` currently exposes these replay tables:
- `strategy_prediction_replays`
- `strategy_replay_runs`

The runtime replay tables do **not** expose a persisted `lifecycle_status` column. Current relevant columns are:
- `strategy_prediction_replays`: `replay_status`, `history_cutoff_draw`, `predicted_numbers`, `actual_numbers`, `hit_numbers`, `replay_run_id`, ...
- `strategy_replay_runs`: `status`, `notes`, `started_at`, `finished_at`, ...

Current raw counts in the local DB:
- `strategy_prediction_replays.replay_status = PREDICTED`: 420
- `strategy_prediction_replays.replay_status = REPLAY_ERROR`: 40
- `strategy_replay_runs.status = DONE`: 6
- `strategy_replay_runs.status = FAILED_LEGACY`: 1

### Registry-derived lifecycle view from P0 evidence

The P0 replay data-health report rolls lifecycle up from the canonical registry/source-of-truth and reports:
- ONLINE: 460
- OFFLINE: 0
- REJECTED: 0
- OBSERVATION: 0
- RETIRED: 0

That means the current runtime DB is stable, but the non-ONLINE lifecycle catalog still has no canonical rows in the validated replay path.

## Candidate Source-of-Truth Inventory

Use only trusted sources with an explicit role distinction.

### Runtime source candidates

| Source | Role | Can be runtime source? |
|---|---|---|
| `lottery_api/models/replay_strategy_registry.py` | canonical lifecycle SSOT for adapters and canonical lifecycle values | yes |
| `lottery_api/data/lottery_v2.db` (`strategy_prediction_replays`, `strategy_replay_runs`) | runtime replay store | yes |
| `scripts/backfill_replay_history_cutoff.py` | safe backfill pattern and no-write/audit rules | yes, as implementation pattern only |
| `scripts/validate_replay_test_fixture.py` | fixture integrity contract | yes, as validation pattern only |

### Evidence-only candidates

These files help explain the target state, but they are **not** runtime data sources:
- [outputs/replay/p0_replay_data_health_20260510.md](outputs/replay/p0_replay_data_health_20260510.md)
- [outputs/replay/p0_replay_product_golive_pr_readiness_20260510.md](outputs/replay/p0_replay_product_golive_pr_readiness_20260510.md)
- [outputs/replay/p0_replay_product_post_merge_closure_20260510.md](outputs/replay/p0_replay_product_post_merge_closure_20260510.md)
- [outputs/replay/p0_replay_lifecycle_catalog_truth_inventory_20260509.md](outputs/replay/p0_replay_lifecycle_catalog_truth_inventory_20260509.md)
- [outputs/replay/p0_replay_lifecycle_catalog_population_plan_20260509.md](outputs/replay/p0_replay_lifecycle_catalog_population_plan_20260509.md)
- [outputs/replay/p0_replay_lifecycle_catalog_population_pr_readiness_20260509.md](outputs/replay/p0_replay_lifecycle_catalog_population_pr_readiness_20260509.md)

## Runtime Data Rule

Replay backfill must use DB tables and canonical lifecycle source-of-truth only.

It must **not** use any of the following as runtime truth:
- output reports in `outputs/replay/`
- screenshot or markdown evidence artifacts
- empty-state UI copy
- ad hoc JSON summaries generated for PR review

The rule is simple:
1. If the evidence can be traced to a trusted runtime table or registry source, it may enter the backfill manifest.
2. If it only exists in a report, it stays evidence-only.
3. If it cannot be traced, it must be blocked, not inferred.

## Backfill Design Options

### Option A — Direct insert into runtime replay tables

Populate new canonical replay rows directly into `strategy_prediction_replays` and related `strategy_replay_runs` entries.

Pros:
- simplest operationally
- no new read path

Cons:
- highest risk of mixing candidate evidence with runtime truth
- easy to accidentally treat blocked / parse-error rows as canonical
- hard to audit after the fact without a manifest

### Option B — Manifest-first staged backfill with explicit validation gates

Generate a backfill manifest from trusted sources, validate it in dry-run mode, then apply only the approved rows.

Pros:
- safest path
- preserves auditability for blocked rows and parse errors
- easiest to roll back if a contract check fails

Cons:
- requires one extra manifest / validation step
- slower than direct inserts

### Option C — Introduce a dedicated lifecycle catalog table or view first

Add a dedicated catalog layer for lifecycle truth, then derive replay behavior from that layer.

Pros:
- clean separation between runtime rows and catalog truth
- best long-term maintainability

Cons:
- requires a schema / read-path change before any data backfill
- larger implementation footprint than this planning step

## Recommended Option

**Recommend Option B, with Option C as a later schema follow-up if the runtime still needs a persisted lifecycle catalog table.**

Reasoning:
- The current replay DB has no persisted `lifecycle_status` column.
- The replay system already proves it can derive lifecycle truth from the registry for P0 stability.
- A manifest-first dry-run keeps the 15 promotable rows separate from the 26 blocked rows and the 1 parse error.
- This keeps the next execution bounded and reversible.

## Required Schema / Row Contract

Any executable backfill must satisfy all of the following:

- `strategy_prediction_replays` rows must remain causal:
  - `history_cutoff_draw` must be parseable when required
  - `history_cutoff_draw < target_draw`
  - no row may use `target_draw` as its own cutoff
- `strategy_replay_runs` rows must remain audit-safe:
  - run status is preserved; do not mutate existing run semantics
  - every inserted replay row must point to a valid replay run id
- lifecycle source-of-truth must be explicit:
  - registry-derived lifecycle must match the canonical lifecycle enum
  - no fabricated lifecycle aliases in runtime rows
- no placeholder or synthetic replay rows:
  - blocked rows stay blocked
  - parse-error rows stay evidence-only

## Validation Gates

Before any executable backfill is allowed, require all of the following:

1. Dry-run manifest review passes.
2. Causal ordering checks pass for every promotable row.
3. Parseability checks pass for every target draw that will be written.
4. Lifecycle source-of-truth mapping resolves to a canonical lifecycle value.
5. The runtime write set contains only DB-backed replay rows, not report-derived rows.
6. Re-run replay smoke validation after any apply step.
7. `git diff --check` remains clean after any implementation change.

## Rollback Plan

If any apply step fails:
- stop the backfill immediately
- discard the new transaction / migration batch
- keep the manifest and blocked-row audit artifacts for review
- restore the pre-backfill DB snapshot if a write was applied
- do not reuse partially applied rows without revalidation

## Blocked Rows Handling Plan

The dry-run evidence provided by the user should be treated as follows:

- 15 promotable rows: candidate set only; may enter the executable manifest only after all validation gates pass.
- 26 blocked rows: do not write; keep in a blocked audit list with explicit reasons.
- 1 parse error: do not write; keep as parse-error evidence only.

Blocked and parse-error rows must never be converted into canonical runtime rows by inference.
If a row cannot be safely mapped, it remains excluded from the runtime write set.

## Risks

- The current runtime DB does not persist lifecycle status as a column, so the backfill design must not assume a schema that does not exist.
- Evidence files in `outputs/replay/` can go stale; they are support artifacts only.
- If the registry changes before execution, the manifest must be regenerated.
- A direct-write implementation would be faster but would increase the risk of mixing evidence-only rows into runtime data.

## Explicit Non-Execution Statement

This document is planning only.

No DB writes were performed.
No registry was modified.
No backfill was executed.
No implementation commit was created.
No H6 cleanup was performed.

## Next Executable Implementation Prompt

After explicit approval, implement the backfill as a manifest-first dry-run plus gated apply workflow:
1. generate a candidate manifest from the runtime DB and canonical lifecycle source
2. validate the manifest against the row contract
3. apply only the approved rows in a single transactional batch
4. re-run replay smoke checks
5. keep blocked rows and parse errors out of the runtime write set