# P336A — No-Backfill Confirmation

**Confirmed: no historical backfill was performed, and none is possible via the
P336A code path.**

## Structural guarantees
1. **No DB access at all.** `build_power_lotto_forward_replay_row(...)` returns a
   dict; it never opens, reads, or writes any database (see `db_invariance.md`).
   It therefore cannot read the 27,104 existing historical NULL rows, let alone
   rewrite them.
2. **Forward-only by shape.** The builder produces a **prediction-time** row for a
   *target draw* using strictly-causal `history`, with `actual_*`/`hit_*` left
   `None` and `replay_status="PREDICTED"`. There is no loop over historical
   targets, no `UPDATE`, and no re-derivation of a past draw's second zone from
   its historical `history_cutoff_draw`.
3. **No mutation of existing rows.** Zero existing files changed; no INSERT/UPDATE
   anywhere in the diff. The 27,104 historical NULL rows are untouched.
4. **Inherited P335A boundary.** The consumed helper is documented forward-only
   and, per P334A `no_backfill_policy`, must not be used to "fill in" historical
   NULL rows. P336A honours this: it only ever constructs NEW rows.

## What P336A explicitly did NOT do
- Did not run any historical replay (full or partial).
- Did not run an all-strategy replay.
- Did not persist any generated row to any database.
- Did not touch the dormant persistence pipeline.
