# P334A — Handoff Report

**Task ID:** `P334A_POWER_LOTTO_PREDICTED_SECOND_ZONE_COVERAGE_FEASIBILITY_AUDIT_READ_ONLY`
**Date/time:** 2026-07-01 21:07:05 CST (+0800)
**Mode:** read-only feasibility/design audit — no repo change, no DB write,
no backfill, no prediction.

## 1. Evidence root

`/Users/kelvin/Kelvin-WorkSpace/p334a_power_lotto_second_zone_coverage_feasibility_20260701_210705`

## 2. Canonical origin/main HEAD

`ce2c042e7f4967841e6b31e17552d55bf4717f91` — confirmed **exact match** for
`origin/main` and for the commit named in P333A/this task's brief. The
local worktree (`task/p273a-prize-aware-inferential-validation`, dirty,
stale) was never trusted for content; all code was read via `git show
origin/main:<path>` / `git grep <pattern> origin/main`.

## 3. P333A evidence read

Full predecessor evidence root read: `handoff_report.md`,
`power_lotto_second_zone_readiness.md`, `source_field_inventory.md`,
`blockers.md` (from
`/Users/kelvin/Kelvin-WorkSpace/p333a_prize_aware_success_reconciliation_audit_20260701_205132`).
Summary in `p333a_dependency_summary.md`. The 9,000/36,104 = 24.928%
figure was independently re-derived from the same canonical DB in this
task and matches exactly — no drift.

## 4. Current POWER_LOTTO prediction pipeline summary

Two generations of code produce POWER_LOTTO `strategy_prediction_replays`
rows:

- **Generation A** (wave 3–6 adapters, 2026-05-20 to 05-25): shared
  `_special_predict()` frequency mean-reversion model wired into every
  strategy via a common `get_one_bet()` wrapper → always emits
  `predicted_special`. Source of all 9,000 populated rows.
- **Generation B** (multi-bet extensions + Tier-B, 2026-05-26 to 05-29):
  `get_all_bets_*`-style adapters that return main numbers only; every
  apply script hardcodes `"predicted_special": None`. Source of all 27,104
  NULL rows.
- **No POWER_LOTTO replay row of any kind has been generated since
  2026-05-29** — over a month before this audit — even though the live CLI
  tool `tools/quick_predict.py` computes a real second-zone value
  (`power_special_v3()` → `PowerLottoSpecialPredictor`, a Markov-fused
  model, more sophisticated than Generation A's) on every invocation; it
  simply never persists that value anywhere (stdout only, zero DB writes).

Full detail: `power_lotto_pipeline_inventory.md`, `predicted_special_gap_analysis.md`.

## 5. Exact reason predicted_special coverage is only 24.928%

Fully determinable, traced to specific commits and source lines (not
inferred from statistics alone):
- 4 strategies (`fourier_rhythm_3bet`, `power_fourier_rhythm_2bet`,
  `power_orthogonal_5bet`, `power_precision_3bet`) never had a second-zone
  model wired in, at any point in their history — 17,603 rows.
- 2 strategies (`midfreq_fourier_mk_3bet`, `pp3_freqort_4bet`) had a real
  second-zone value for bet-1 (Generation A, P48) but lost it for their
  bet-2/3/4 multi-bet extensions (Generation B, P132/P133) — 7,500 rows.
- Small extension/legacy gaps (1 row `fourier30_markov30_2bet` draw-ext,
  1,500 Tier-B rows not fully traced to a specific adapter, 100
  pre-instrumentation legacy rows) — 2,001 rows.
- 27,104 total, exactly matching P333A's figure.

## 6. Missing-coverage classification

**Pipeline (generation-code) omission**, not schema, not canonical view,
not artifact export. The `predicted_special` column has always existed and
is bound in every INSERT statement across both generations — Generation B
simply binds it to the Python literal `None` unconditionally. See
`predicted_special_gap_analysis.md` §4 for the full taxonomy mapping.

## 7. Forward-only design recommendation

Extract the currently-live `PowerLottoSpecialPredictor`/`power_special_v3()`
logic (or, more conservatively, the already-duplicated `_special_predict()`)
into a single canonical function, call it from every future POWER_LOTTO
row-generation path, and add a guard test forbidding any new POWER_LOTTO
row with NULL `predicted_special` (mirroring the existing
`test_p48_powerlotto_special_null_policy.py` precedent for `actual_special`).
This is gated on first resuming *some* live POWER_LOTTO persistence
pipeline, since none currently exists (see BLOCKER-2). Full design:
`forward_only_second_zone_design.md`; options compared in
`implementation_options.md`; risks in `risk_assessment.md`.

## 8. Explicit no-backfill boundary

The 27,104 existing NULL rows must never be filled by running any
identified model (or any other model) against their historical
`history_cutoff_draw` after the fact — that would be retroactive inference
misrepresented as a prediction-time record, not a real historical recovery.
No dated, prediction-time artifact evidencing a specific historical value
was found for any of these rows. Full rationale: `no_backfill_policy.md`.

## 9. PASS / FAIL / NOT RUN validation

See `validation.md` — all applicable checks **PASS**; repo tests **NOT
RUN** (no repo code changed, as required).

## 10. Confirm no repo changes

`git status --short` = 18 entries, identical set before and after this
task. `git diff --cached` empty throughout. No commit, no push, no branch
change.

## 11. Confirm no DB writes

Canonical DB (`lottery_api/data/lottery_v2.db`, SHA `9956c3bc…`, size
99,368,960, mtime `Jun 30 13:38:50 2026`) unchanged before/after. All
access via `mode=ro`. The benign side-effect copy `data/lottery_v2.db`
(SHA `2095c687…`) also unchanged — never opened by this task.

## 12. Recommended next single implementation task

**P335A — Extract a canonical `second_zone_predict()` function and wire it
into every future POWER_LOTTO replay-row generation path, plus a null-guard
test.** Must be scoped and separately authorized before any code change;
must explicitly state whether it also resumes the currently-dormant
POWER_LOTTO persistence pipeline (BLOCKER-2) or treats that as a
prerequisite third-party task. Must not touch any of the 27,104 existing
NULL rows.

## 13. Final classification

**`P334A_POWER_LOTTO_SECOND_ZONE_COVERAGE_FEASIBILITY_COMPLETE_WITH_BLOCKERS`**

Feasibility fully determined: predicted-second-zone coverage CAN
legitimately reach 100% for all future POWER_LOTTO rows by wiring an
already-existing, already-proven model into the generation code paths that
currently skip it — but this remains blocked on (a) a separate
authorization to implement the wiring, and (b) resuming a currently-dormant
POWER_LOTTO persistence pipeline that has produced zero new rows since
2026-05-29. No repo change, no DB write, no backfill, no prediction was
made in this audit.
