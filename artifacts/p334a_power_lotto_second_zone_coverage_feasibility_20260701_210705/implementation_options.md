# P334A — Implementation Options (design comparison only, nothing implemented)

Three options for the future, separately-authorized implementation task.
Ranked by recommendation; no code was written for any of them here.

## Option 1 (recommended) — Wire the existing live model into a single canonical function, call it from every future POWER_LOTTO row-builder

- Extract `power_special_v3()`'s logic (`tools/quick_predict.py`) or
  `PowerLottoSpecialPredictor.predict()` (`lottery_api/models/special_predictor.py`)
  into one importable, side-effect-free function `second_zone_predict(history)`.
- Every future POWER_LOTTO row-generation path (whatever resumes the
  currently-dormant persistence pipeline — see `power_lotto_pipeline_inventory.md`
  §3) calls this one function.
- Add the guard test described in `forward_only_second_zone_design.md` §5.
- **Pros:** single source of truth going forward; reuses the
  already-best-performing model already in production use for live human
  predictions; smallest code surface (one function + one call-site
  convention + one guard test).
- **Cons:** requires first re-establishing *some* live POWER_LOTTO
  persistence pipeline (§3b), since there is currently none — this is a
  precondition, not a drawback of the second-zone piece specifically.

## Option 2 — Reuse the legacy `_special_predict()` frequency model as-is

- Same wiring as Option 1, but call the simpler, already-duplicated
  `_special_predict()` (currently copy-pasted across
  `p47_wave4_powerlotto_adapters.py` and `p56_wave5_powerlotto_adapters.py`)
  instead of the fused Markov model.
- **Pros:** zero risk of behavior change vs. the 9,000 already-populated
  rows (bit-for-bit same model family); simplest to reason about for
  continuity with historical rows.
- **Cons:** knowingly ships a weaker model than the one already live in
  `quick_predict.py`; still has the duplication problem (two copies of
  `_special_predict()` already exist and would need consolidating first).

## Option 3 — Do nothing to persistence; only fix the multi-bet extension gap (Pattern 2)

- Narrowest possible fix: only wire the second-zone call into future
  multi-bet extensions of strategies that already have it for bet-1
  (`midfreq_fourier_mk_3bet`, `pp3_freqort_4bet`, and similar future cases),
  leaving the 4 structurally-second-zone-blind strategies (Pattern 1)
  unaddressed.
- **Pros:** smallest possible diff; addresses the most clearly
  "regression, not design" part of the gap.
- **Cons:** does not move POWER_LOTTO from `BLOCKED` to `COMPUTABLE` at the
  full-population level, since 4 strategies would remain permanently
  second-zone-blind going forward too; leaves the live-pipeline dormancy
  (§3b) completely unaddressed, so no new rows of any kind would be
  produced regardless.

## Recommendation

Option 1, gated behind first resolving §3b (some live POWER_LOTTO
persistence path must exist before a second-zone fix has anything to
attach to). This is stated as the smallest single future task in
`handoff_report.md` / `blockers.md`.
