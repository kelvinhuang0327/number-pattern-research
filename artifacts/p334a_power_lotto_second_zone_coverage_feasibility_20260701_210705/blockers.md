# P334A — Blockers

## BLOCKER-1 (unchanged from P333A, root cause now fully traced) — POWER_LOTTO predicted second-zone missing for 27,104/36,104 rows (75.072%)

- **Root cause (new in this audit):** two generations of prediction-
  generation code. Generation A (`p47_wave4_powerlotto_adapters.py`,
  `p56_wave5_powerlotto_adapters.py`, wave6) wraps every strategy with a
  shared `_special_predict()` call → always populates `predicted_special`.
  Generation B (multi-bet extension scripts P94/P126B/P132/P133/P134/P140/
  P141, using `get_all_bets_*`-style adapters) never calls any second-zone
  model and hardcodes `"predicted_special": None` in every row-builder.
  Full trace: `predicted_special_gap_analysis.md`.
- **Not a schema, view, or export gap** — the column always exists and is
  always bound in every INSERT; see `power_lotto_pipeline_inventory.md` §4.
- **Impact:** unchanged from P333A — full POWER_LOTTO prize-aware scoring
  stays `BLOCKED_BY_MISSING_FIELD` / `NOT_RUN` at the full-population
  level. Only the 9,000-row / 1,500-draw eligible subset remains scorable
  (already done, all NULL, per P271F/P281A).
- **Forbidden remediation (unchanged, restated with sharper teeth given
  this audit's findings):** no fabrication, defaulting, randomizing,
  most-frequent-filling, actual→predicted copying, or retroactively running
  any second-zone model (including the ones identified in this audit)
  against historical `history_cutoff_draw` values. See
  `no_backfill_policy.md`.
- **Only legitimate unblock path:** a future, separately-authorized
  implementation task that wires an existing second-zone model into every
  future POWER_LOTTO row-generation path, going forward only. Design in
  `forward_only_second_zone_design.md`; options compared in
  `implementation_options.md`.

## BLOCKER-2 (new finding in this audit) — No live/scheduled POWER_LOTTO prediction persistence pipeline currently exists

- **State:** the newest `strategy_prediction_replays` row for
  `lottery_type='POWER_LOTTO'` was generated `2026-05-29 06:30:32` — over a
  month before this audit (`2026-07-01`). 11 further POWER_LOTTO draws have
  occurred since (raw `draws` table max = `115000052` vs. replay-table max
  target_draw `115000041`) with zero corresponding replay rows of any kind
  (main or second-zone).
- **Impact:** a second-zone fix alone (BLOCKER-1) has no effect until this
  is separately resolved — there is currently no live path that creates
  *any* new POWER_LOTTO replay row for the fix to apply to.
- `tools/quick_predict.py`'s `predict_power()` computes both main numbers
  and a real second-zone value on every invocation, but only prints them —
  it performs zero DB writes (`git grep` for INSERT/commit verbs in that
  file returned nothing). It is not, today, a persistence pipeline.
- `tools/post_draw_pipeline.py`, referenced in project memory as the
  7-step post-draw pipeline, does not exist at `origin/main` HEAD.
- **Not fixed or worked around in this audit** — read-only, design-only
  scope. Flagged as a precondition for BLOCKER-1's fix, and as its own
  candidate future task if POWER_LOTTO prediction generation is meant to
  resume at all (independent of second-zone scoring).

## BLOCKER-3 (carried over from P333A, out of scope for P334A) — POWER_LOTTO canonical source view absent

- Unchanged from P333A/P298A/P296A/P296B: no `draws_power_lotto_canonical_main`-
  style view exists. Not the subject of this audit (this audit is scoped to
  the *predicted*-second-zone gap in the replay table, a separate,
  downstream concern from the raw-source-view gap). Re-confirmed present as
  a standing blocker, not re-investigated in depth here.

## BLOCKER-4 (carried over from P333A, out of scope) — official prize-table not machine-verified

- Unchanged from P333A: `source_verification_status =
  MANUAL_VERIFICATION_REQUIRED` across the prize-aware stack. Not
  re-investigated in this audit.

## NON-BLOCKERS

- DAILY_539 and BIG_LOTTO: unaffected by any finding in this audit; remain
  fully computable per P333A.
