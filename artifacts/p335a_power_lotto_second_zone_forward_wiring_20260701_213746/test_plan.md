# P335A — Test Plan

## Runner

Repo venv `/Users/kelvin/Kelvin-WorkSpace/LotteryNew/venv/bin/python`
(pytest 9.0.3, numpy 2.4.4, Python 3.14.4). `pytest.ini` sets `pythonpath = .`.
All P335A tests are pure (synthetic in-memory history) — **no DB, no network**.

## New guard suite — `tests/test_p335a_power_lotto_second_zone_forward_wiring.py`

`TestSecondZonePredict`
- `test_returns_non_null_int_in_range_for_sufficient_history` — non-null int in [1,8].
- `test_deterministic_same_history_same_value` — reproducibility (fixed output).
- `test_exactly_min_history_is_sufficient` — boundary at `MIN_HISTORY`.
- `test_raises_on_insufficient_history[0,1,29]` — raises below threshold (not silent default).
- `test_raises_on_non_list` — raises on `None`/non-list input.
- `test_falls_back_when_fused_model_raises` — monkeypatch `PowerLottoSpecialPredictor`
  to raise → frequency fallback still returns valid non-null value.
- `test_frequency_fallback_direct_in_range` — fallback output in [1,8].
- `test_frequency_fallback_empty_uses_fixed_prior` — no usable specials → fixed prior (2), never 0/None.

`TestNullGuard`
- `test_passes_for_valid_production_row` — valid row passes.
- `test_raises_on_null_predicted_special` — POWER_LOTTO non-dry-run + NULL → raises.
- `test_raises_on_out_of_range[0,9,-1,100]` — out-of-[1,8] → raises.
- `test_ignores_non_power_lotto_null` — DAILY_539/BIG_LOTTO NULL is allowed (no-op).
- `test_ignores_dry_run_rows` — dry-run NULL is allowed (no-op).

`TestForwardWiringPreventsNull`
- `test_rowbuilder_using_helper_is_never_null` — a representative future row-builder
  wired through `second_zone_predict()` yields non-null in-range `predicted_special`
  and passes the guard.
- `test_old_generation_b_none_literal_now_fails_guard` — the exact Generation-B
  `"predicted_special": None` literal now fails the guard (regression is caught).

## Relevant existing tests (regression / no-break check)

- `tests/test_p93_tier_b_replay_adapter_bootstrap_dryrun.py` — the Tier-B file
  intentionally NOT modified; non-DB content/structure assertions must still pass.
- `tests/test_p48_powerlotto_special_null_policy.py` — the `actual_special`
  null-policy precedent this work mirrors; non-DB unit assertions must still pass.

DB-backed assertions in those two files require the canonical 99MB DB, which is
**untracked and therefore absent in a fresh `origin/main` worktree** → recorded
as NOT RUN (skip/DB-absent), with a non-causation proof (see `test_results.md`).
