# P334A — P333A Dependency Summary

Source: `/Users/kelvin/Kelvin-WorkSpace/p333a_prize_aware_success_reconciliation_audit_20260701_205132/`
(`handoff_report.md`, `power_lotto_second_zone_readiness.md`,
`source_field_inventory.md`, `blockers.md` read in full).

## What P333A established (accepted as given, re-verified where cheap to do so)

1. **DAILY_539** and **BIG_LOTTO** prize-aware success metrics are fully
   **COMPUTABLE** — no blockers, all required fields at 100%.
2. **POWER_LOTTO** full prize-aware scoring is **BLOCKED_BY_MISSING_FIELD**:
   `strategy_prediction_replays.predicted_special` is NULL for
   27,104 / 36,104 rows (75.072%); only 9,000 rows (24.928%) are populated.
3. `actual_special` for POWER_LOTTO is 100% present and valid (range 1–8) —
   the gap is exclusively on the **predicted** side.
4. The populated 9,000-row subset spans 1,500 distinct target draws
   (range `101000002..115000040`), already scored descriptively in P271F/P281A
   (all NULL after Bonferroni — not a prediction, not reused here).
5. A separate, independent blocker exists: no POWER_LOTTO canonical DB
   source view (analogous to `draws_big_lotto_canonical_main`) — confirmed
   absent by P298A/P296A/P296B. This is **not** the subject of P334A (P334A
   is scoped strictly to the *predicted*-second-zone coverage gap in
   `strategy_prediction_replays`, which is a downstream replay-table
   concern, not the raw-source-view concern).
6. P333A explicitly named **P334A** as the recommended next task: determine
   whether/how the prediction pipeline could legitimately emit and persist
   a real, prediction-time `predicted_special` for the 27,104 NULL rows
   *going forward*, without any historical backfill.
7. Re-verification in this task (read-only DB query against the same
   canonical DB, SHA `9956c3bc…`, unchanged) reproduced the exact 9,000 /
   36,104 = 24.928% figure independently, confirming no drift since P333A
   (same day, same DB state).

## What P334A adds on top of P333A

P333A characterized the gap at the *aggregate* level (24.928% populated,
75.072% NULL) and at the *strategy* level (6 strategies with some
second-zone support vs. 4 with none — `NO_SECOND_ZONE_SUPPORT`). P334A goes
one level deeper: it traces the gap to specific **code paths and commits**,
and shows the split is not purely a strategy-capability split — it is a
**pipeline-generation-path** split (see `predicted_special_gap_analysis.md`).
This distinction matters because it changes the forward-fix scope from
"build new per-strategy second-zone models" to "wire an already-existing,
already-working second-zone model into the code paths that currently skip
it."
