# P358A Big Lotto Historical Recovery Report

Final classification: `P358A_COMPLETE_WITH_GAPS`

## Scope And Safety

- Owner authorization: confirmed from the first line of the task message.
- Worktree: `/Users/kelvin/Kelvin-WorkSpace/LotteryNew.worktrees/P358-biglotto-historical-strategy-recovery`
- Branch: `feature/P358-biglotto-historical-strategy-recovery`
- Base: `origin/main` at `3ffa948b5b3671cc129e62f860c7c8e9abf0b668` (P357 merge).
- Canonical checkout was not used for source edits. A misplaced initial patch was removed before continuing; P358 files exist only in the isolated worktree.
- DB write/open status: no DB opened or written by P358A adapters/tests.
- Replay status: no full replay, no production replay, no all-strategy replay.
- Strategy status / registry / deployment changes: none.

## Evidence Read

- P356A inventory CSV/JSON, skipped-strategies report, and ID-reuse report.
- P356B replay-eligible manifest CSV/Markdown.
- P356C replay result review.
- P357B historical recovery manifest and report.
- Git history for `*biglotto*` and `*lotto*`, including deleted paths.
- Current grep evidence for `biglotto`, `big lotto`, `big_lotto`, and `大樂透`.
- Historical source around deletion commit `73062646^`.

## P356 Already Replayed Big Lotto Strategies

Currently discoverable P356/P357 evidence marks these as already covered by P356/P356C and not needing P358 adapters: `biglotto_deviation_2bet`, `biglotto_echo_aware_3bet`, `biglotto_triple_strike`, `biglotto_ts3_markov_4bet_w30`, `cold_complement_biglotto`, `coldpool15_biglotto`, `fourier30_markov30_biglotto`, `markov_2bet_biglotto`, `markov_single_biglotto`, and `ts3_regime_3bet`.

## Restorable / Adapted

P358A created quarantined no-DB adapters for:

- `biglotto_p0_2bet`
- `predict_biglotto_echo_2bet`
- `predict_biglotto_echo_phase2` as 2-bet and 3-bet shapes
- `predict_biglotto_echo_mixed_3bet`
- `biglotto_zonal_pruning`
- `biglotto_5bet_orthogonal`
- `predict_biglotto_regime`
- `biglotto_10bet_combined`

The adapters live under `recovered_strategies/biglotto/` and return only `list[list[int]]`.

## Not Replayable / Deferred

- `biglotto_ts3_markov_freq_5bet`: not adapted under that registered strategy id because the registry stub lacks a proven direct runnable source identity. The current TS3/Markov/FreqOrt helper was handled only under `biglotto_5bet_orthogonal`.
- `biglotto_ts3_acb_4bet` and `ts3_acb_4bet_biglotto`: no runnable source found; classified as reconstruction-needed.
- `bet2_fourier_expansion_biglotto`: split into current P42/P280 frozen-code lineage and historical rejected JSON lineage. No adapter created to avoid ID reuse contamination.
- DB-only combined scopes remain not replayable as single strategies.

## Adapter Caveats

`biglotto_p0_2bet`, echo 2bet/phase2/mixed adapters copy pure in-memory current logic and are acceptable for the no-DB harness. `biglotto_zonal_pruning`, `biglotto_5bet_orthogonal`, `predict_biglotto_regime`, and `biglotto_10bet_combined` are shape/safety-only where exact NumPy/SciPy ranking parity is not proven.

## Artifacts

- `artifacts/P358A_biglotto_historical_recovery_manifest.csv`
- `artifacts/P358A_biglotto_historical_recovery_report.md`
- `artifacts/P358A_biglotto_recovered_adapter_manifest.csv`
- `artifacts/P358A_biglotto_recovered_adapter_report.md`

## Validation Summary

- `python3 -m py_compile recovered_strategies/biglotto/__init__.py recovered_strategies/biglotto/historical_adapters.py`: PASS
- `pytest -q tests/test_p358a_biglotto_recovered_adapters.py`: PASS (`12 passed`)
- Full replay: NOT RUN by design.

## Next Recommended Task

Run a P358B lineage-mapping pass for `biglotto_ts3_markov_freq_5bet`, `biglotto_ts3_acb_4bet`, and `bet2_fourier_expansion_biglotto` before any replay/backfill attempt. The goal should be source identity proof, not adapter expansion.
