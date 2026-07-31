# P336A — Implementation Plan (as executed)

## Objective
Define exactly ONE live/resumable, forward-only POWER_LOTTO replay-row
generation path that obtains its `predicted_special` from the P335A helper and
is guarded before the output boundary — additive only, no DB write, no backfill,
no pipeline resume.

## Deliverables (2 new files, 0 modifications)

1. **`lottery_api/models/power_lotto_forward_replay_row.py`** (new)
   - `build_power_lotto_forward_replay_row(*, strategy_id, target_draw_id,
     history, predicted_numbers, strategy_name=None, strategy_version=None,
     target_draw_date=None, dry_run=False) -> dict`.
   - Step 1: `_validate_first_zone(predicted_numbers)` — 6 distinct ints in
     `[1,38]` (mirrors `_P47BaseAdapter.get_one_bet` asserts; raises `ValueError`).
   - Step 2: `predicted_special = second_zone_predict(history)` — **the wiring**;
     raises `InsufficientHistoryError` for `< 30` draws (fail-fast, no default).
   - Step 3: assemble a canonical `strategy_prediction_replays`-shaped **forward**
     row (schema mirrors `p47 generate_dryrun_rows`): `predicted_numbers`,
     `predicted_special` (non-NULL), `actual_*`/`hit_*` = `None`,
     `replay_status="PREDICTED"`, `dry_run` = `0/1`.
   - Step 4: `assert_power_lotto_predicted_special(row)` — **the guard**, at the
     output/persistence boundary.
   - Re-exports `InsufficientHistoryError`, `SPECIAL_MIN`, `SPECIAL_MAX`; defines
     `FIRST_ZONE_POOL=38`, `FIRST_ZONE_PICK=6`.
   - Explicit forward-only / no-DB / no-prediction-claim docstrings.

2. **`tests/test_p336a_power_lotto_forward_row_generation_path.py`** (new)
   - Pure/isolated unit tests (deterministic synthetic history, no DB).

## Design decisions
- **First-zone as input, not computed here** — the entire P333–P335 arc concerns
  the *second* zone NULL coverage; keeping the builder first-zone-agnostic makes
  it minimal, invents no algorithm, and avoids coupling to any one strategy's
  ordering convention. The complete-path test feeds a *real* p47 first-zone bet.
- **Forward semantics** — a prediction-time row leaves `actual_*`/`hit_*`
  unknown (`None`) and `replay_status="PREDICTED"`; scoring happens later at draw
  resolution. This makes "forward-only, no backfill" structural.
- **Guard enforces by default** — `dry_run` defaults to `False`, so the P335A
  guard raises on any NULL/out-of-range second zone. The builder never fabricates
  a NULL, so in practice it returns a valid row or raises.

## Explicit non-goals (forbidden / out of scope)
No DB write/migration/checkpoint/restore; no backfill of the 27,104 historical
NULL rows; no full historical replay; no all-strategy replay; no persistence
pipeline activation; no generated/recommended numbers; no betting advice; no
future-prediction claim; no roadmap/governance edits; no edit to p47/p48/p56/p93;
no push.

## Reuse / dependency note
No new algorithm and no new third-party dependency. Reuses in-repo P335A helper
(`second_zone_predict`, `assert_power_lotto_predicted_special`, which reuse
`PowerLottoSpecialPredictor`) and, in the complete-path test, the existing
`p47_wave4_powerlotto_adapters.predict_midfreq_fourier_mk_3bet_bet1`. Test runtime
uses the repo venv (pytest 9.0.3, Python 3.14.4).
