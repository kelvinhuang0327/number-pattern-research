# P334A — No-Backfill Policy (explicit boundary)

Restates and extends P333A's/P298A's/P271-series' standing prohibition, in
light of this audit's specific findings.

## 1. The rule

The 27,104 existing NULL `predicted_special` rows in
`strategy_prediction_replays` (`lottery_type = 'POWER_LOTTO'`) **must never
be filled in retroactively** by:

- Running `_special_predict()`, `PowerLottoSpecialPredictor`, or any other
  model against each row's stored `history_cutoff_draw` after the fact.
- Defaulting, randomizing, or most-frequent-filling.
- Copying `actual_special` into `predicted_special` (this would make
  `special_hit` trivially 1 for every row — a fabricated result, explicitly
  forbidden by every prior POWER_LOTTO audit in this repo's history).
- Any statistical inference, imputation, or "best guess" derived from
  neighboring rows, other strategies, or aggregate frequency tables.

## 2. Why this audit's findings make the temptation to backfill *worse*, not better

This audit found that a working second-zone model (`_special_predict()`,
even more so the fused `PowerLottoSpecialPredictor`) already exists and
*could* be run against any historical `history_cutoff_draw` right now,
mechanically producing a plausible-looking `predicted_special` for all
27,104 rows in minutes. **This must not be done.** Running a model today
against a historical cutoff and writing the result into a row whose
`prediction_generated_at` timestamp already claims an earlier,
already-completed prediction event would misrepresent *when* the
prediction was made — it is retroactive inference dressed as history, not
a real prediction-time record. This is exactly the failure mode P271G's
"prospective-only" preregistration and P298A's/P333A's explicit forbidden-
remediation lists were written to prevent.

## 3. What would make a historical value legitimate (and why none currently qualify)

A `predicted_special` value for an existing row could be legitimately
added, without being a backfill, **only if** independent, dated evidence
already exists that a specific value was actually computed and would have
been output *at or before* that row's `prediction_cutoff_date` /
`prediction_generated_at` — e.g. a committed artifact, log, or manifest
from that exact date recording the second-zone value the pipeline would
have emitted at that time (even if it was never written to the DB then).
This audit did not find any such artifact for the 27,104 NULL rows: the
Generation-B apply scripts (P94/P126B/P132/P133/P134/P140/P141) contain no
evidence a second-zone value was ever computed and then dropped — they
never computed one in the first place (see `predicted_special_gap_analysis.md`
Pattern 1/2). There is nothing to "recover"; any value produced now would
be newly computed, not historically evidenced, and therefore forbidden.

## 4. Scope of "forward-only"

"Forward-only" means: starting from the first `strategy_prediction_replays`
row inserted **after** a future, separately-authorized implementation task
ships the fix in `forward_only_second_zone_design.md`, every new POWER_LOTTO
row must carry a real `predicted_special`. Every row that already exists in
the DB as of this audit (2026-07-01) remains permanently excluded from full
prize-aware scoring under `EXCLUSION_MISSING_PREDICTED_SECOND_ZONE`, exactly
as `lottery_api/prize_aware_replay_adapter.py` already handles it. Full
POWER_LOTTO population-level scoring will only ever be
`BLOCKED_BY_MISSING_FIELD` for the pre-fix rows; it becomes fully
`COMPUTABLE` only for rows generated after the fix, and remains
irreversibly `PARTIAL` at the full-history level unless a future,
separately-scoped decision is made to permanently exclude the pre-fix rows
from the "full scoring" definition (a scope/governance decision, not a
data-remediation one — out of scope for this audit to decide).
