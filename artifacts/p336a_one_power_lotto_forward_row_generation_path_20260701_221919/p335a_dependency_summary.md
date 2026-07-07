# P336A — P335A Dependency Summary

P335A's `handoff_report.md`, `implementation_plan.md`, `changed_files.md`,
`test_results.md`, and `p333a_p334a_dependency_summary.md` were read in full
before any P336A code was written.

## What P335A delivered (the building blocks P336A consumes)

Module `lottery_api/models/power_lotto_second_zone.py` (169 lines):

- `second_zone_predict(history) -> int`
  - Reuses the already-live fused model `PowerLottoSpecialPredictor`
    (`lottery_api/models/special_predictor.py`, the same model
    `tools/quick_predict.py::power_special_v3()` runs on every human prediction).
  - Degrades to a recent-frequency count (`_frequency_fallback`) only if the
    fused model cannot be imported/executed — **never returns NULL** for
    sufficient history.
  - **Raises `InsufficientHistoryError`** when `history` is not a list or has
    `< MIN_HISTORY (=30)` draws — no silent default.
  - Deterministic (no RNG on the prediction path); returns an int in `[1, 8]`.
  - `MIN_HISTORY = 30` was chosen to mirror the most-demanding Generation-A
    wave-4 guard (`MidFreqFourierMk3BetAdapter.min_history == _MARKOV_WINDOW == 30`
    in `p47_wave4_powerlotto_adapters.py`).

- `assert_power_lotto_predicted_special(row) -> None`
  - Fail-fast NULL guard. Raises if a POWER_LOTTO, non-`dry_run` row has NULL or
    out-of-`[1,8]` `predicted_special`. No-ops for DAILY_539/BIG_LOTTO and for
    `dry_run` rows.

## The blocker P335A left open (P336A's mandate)

**BLOCKER-2 (unchanged from P334A):** no live POWER_LOTTO persistence pipeline
exists — no replay row has been persisted since 2026-05-29. P335A shipped the
helper + guard but **could not wire an in-tree call site** because:

- Generation-A wave builders (p47/p48) already emit a `predicted_special` (via a
  *local* `_special_predict`), so there was nothing to "un-NULL".
- The Generation-B builders that hardcoded `predicted_special=None`
  (`p132…p141`) are **not on origin/main** (side-branch `claude/zen-gates-ff6802`).
- The only in-tree Generation-B POWER path (Tier-B `p93`) is frozen
  `DRY_RUN`/`production_eligible=False`, content-phrase-guarded — deliberately
  untouched.

P335A's recommended next task (P336A) is exactly this: define/resume ONE live
POWER_LOTTO row-generation path wired to `second_zone_predict()` +
`assert_power_lotto_predicted_special()`.

## Facts re-verified against origin/main (ce2c042) for P336A

- P335A's two files are present and byte-identical (SHA256 `15b60f2c…` /
  `5e34c360…`).
- `second_zone_predict()` runs **DB-free** in the fresh worktree venv (smoke:
  returned `8` for a 150-draw synthetic history, deterministic, in range;
  matches P335A's reuse-fidelity result of `8`).
- `scripts/p48_powerlotto_wave4_production_apply.py:560` imports
  `generate_dryrun_rows` from `p47_wave4_powerlotto_adapters` → the p47 module is
  **shared with the production-apply lineage** and by 6+ test modules. This drives
  the P336A path-selection decision (see `selected_path_rationale.md`).
