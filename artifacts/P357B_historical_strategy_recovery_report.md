# P357B Historical Strategy Recovery Report

Final classification: `P357B_COMPLETE_RECOVERY_MANIFEST`

## Scope And Safety

- Owner authorization: confirmed in standalone user message before work started.
- Worktree: `/Users/kelvin/Kelvin-WorkSpace/LotteryNew.worktrees/P357-historical-strategy-recovery`
- Branch: `feature/P357-historical-strategy-recovery`
- HEAD: `e3265ad4baeb35d0e8e60d6df5915bdd4ddfa855`
- Canonical checkout was inspected only and left unmodified.
- Canonical DB write status: no DB writes; DB was not opened for this manifest.
- Replay status: full replay not run.
- Production code/status changes: none.

## Evidence Loaded

- P356A/B artifacts read from commit `f8ef27f73887c622148184f6cd527f9c73ce53d6` because the files are not present in current `origin/main`.
- P356C review read from commit `ce497e8f9241ddee9bc097d4bd3c4f6e66b41db0`.
- Deleted-file audit: `1026` deleted paths, `436` keyword-matching deleted paths, `190` keyword `.py` deleted paths.
- Key deletion commit: `73062646f11d8881ab6c49565977fb553739bdf3` (`feat(replay-ui): expose all-lifecycle strategy replay history`).

## Manifest Summary

- Manifest rows: `35`
- By recovery status: `CURRENT_EXECUTABLE`=16, `DB_ONLY`=5, `HISTORICAL_DELETED_NEEDS_RECONSTRUCTION`=3, `HISTORICAL_RESTORABLE`=9, `ID_REUSED_NEEDS_SPLIT`=2
- By replay readiness: `NEEDS_ADAPTER`=15, `NEEDS_RECONSTRUCTION`=4, `NOT_REPLAYABLE`=6, `READY`=10
- By game: `BIG_LOTTO`=25, `DAILY_539`=4, `POWER_LOTTO`=5, `UNKNOWN`=1

## High-Priority Restorable

- `539_3bet_orthogonal`: `tools/backtest_539_3bet_orthogonal.py` deleted at `73062646`; restorable from `73062646^`; readiness `NEEDS_ADAPTER`.
- `p0b_539_3bet_f_cold_fmid`: `tools/backtest_539_3bet_f_cold_fmid.py` deleted at `73062646`; restorable from `73062646^`; readiness `NEEDS_ADAPTER`.
- `p0c_539_3bet_f_cold_x2`: `tools/backtest_539_3bet_f_cold_x2.py` deleted at `73062646`; restorable from `73062646^`; readiness `NEEDS_ADAPTER`.
- `power_shlc_midfreq`: `tools/backtest_power_shlc.py` deleted at `73062646`; restorable from `73062646^`; readiness `NEEDS_ADAPTER`.
- `power_pp3v2_combined`: `tools/backtest_power_pp3v2_comprehensive.py` deleted at `73062646`; restorable from `73062646^`; readiness `NEEDS_ADAPTER`.
- `power_lotto_pp3_sum_regime`: `tools/backtest_power_sum_regime.py` deleted at `73062646`; restorable from `73062646^`; readiness `NEEDS_ADAPTER`.
- `biglotto_10bet_combined`: `tools/backtest_biglotto_10bet_combined.py` deleted at `73062646`; restorable from `73062646^`; readiness `NEEDS_ADAPTER`.
- `predict_biglotto_regime`: `tools/predict_biglotto_regime.py` deleted at `73062646`; restorable from `73062646^`; readiness `NEEDS_ADAPTER`.

## Medium-Priority Needs Adapter

- `biglotto_p0_2bet`: current source `tools/backtest_biglotto_p0_2bet.py`; callable evidence `true`; P356A `UNKNOWN`.
- `biglotto_5bet_orthogonal`: current source `tools/quick_predict.py`; callable evidence `true`; P356A `UNKNOWN`.
- `biglotto_zonal_pruning`: current source `tools/predict_biglotto_zonal.py`; callable evidence `true`; P356A `UNKNOWN`.
- `predict_biglotto_echo_2bet`: current source `tools/predict_biglotto_echo_2bet.py`; callable evidence `true`; P356A `UNKNOWN`.
- `predict_biglotto_echo_phase2`: current source `tools/predict_biglotto_echo_phase2.py`; callable evidence `true`; P356A `UNKNOWN`.
- `predict_biglotto_mixed_3bet`: current source `tools/predict_biglotto_mixed_3bet.py`; callable evidence `true`; P356A `UNKNOWN`.

## Needs Reconstruction

- `biglotto_ts3_markov_freq_5bet`: evidence `lottery_api/models/replay_strategy_registry.py`; P356A `MISSING_CODE`; note: P356A found non-executable lifecycle stub only. No direct deleted Python implementation matched; docs say reconstructible/code-scan and later governance rejected/superseded.
- `biglotto_ts3_acb_4bet`: evidence `lottery_api/models/replay_strategy_registry.py`; P356A `MISSING_CODE`; note: P356A MISSING_CODE. Current registry has visibility stub; rejected JSON exists, but only historical result JSON deletion found, not runnable source.
- `ts3_acb_4bet_biglotto`: evidence `rejected/ts3_acb_4bet_biglotto.json`; P356A `MISSING_CODE`; note: Rejected artifact lineage. Needs code reconstruction or mapping to a current TS3/ACB implementation before replay.
- `bet2_fourier_expansion_biglotto`: evidence `rejected/bet2_fourier_expansion_biglotto.json`; P356A `ID_REUSED`; note: Historical rejected JSON describes a different Fourier expansion/zone-filter lineage sharing the same strategy_id.

## ID Reused

- `bet2_fourier_expansion_biglotto` (`P357B-IDREUSE-001`): `PYTHON_CURRENT` evidence `lottery_api/models/p42_wave3_biglotto_adapters.py`; readiness `NEEDS_ADAPTER`.
- `bet2_fourier_expansion_biglotto` (`P357B-IDREUSE-002`): `REJECTED_JSON` evidence `rejected/bet2_fourier_expansion_biglotto.json`; readiness `NEEDS_RECONSTRUCTION`.

## Low-Priority Doc/DB-Only

- `biglotto_triple_strike,biglotto_deviation_2bet`: `DB_ONLY`, readiness `NOT_REPLAYABLE`.
- `ts3_regime_3bet,biglotto_triple_strike,biglotto_deviation_2bet`: `DB_ONLY`, readiness `NOT_REPLAYABLE`.
- `daily539_f4cold,daily539_markov_cold`: `DB_ONLY`, readiness `NOT_REPLAYABLE`.
- `fourier_rhythm_3bet,power_precision_3bet,power_orthogonal_5bet`: `DB_ONLY`, readiness `NOT_REPLAYABLE`.
- `power_precision_3bet,power_orthogonal_5bet`: `DB_ONLY`, readiness `NOT_REPLAYABLE`.

## Exclude / Not Replayable

- `strategy_coordinator`: `PYTHON_DELETED_INFRA`; Restorable infrastructure/coordinator module, not a strategy lineage. Recover only as reference for algorithm extraction, not as replay candidate.
- `biglotto_triple_strike,biglotto_deviation_2bet`: `DB`; P356A found DB evidence only; no current implementation/config/doc source established. Keep low-priority until source lineage is found.
- `ts3_regime_3bet,biglotto_triple_strike,biglotto_deviation_2bet`: `DB`; P356A found DB evidence only; no current implementation/config/doc source established. Keep low-priority until source lineage is found.
- `daily539_f4cold,daily539_markov_cold`: `DB`; P356A found DB evidence only; no current implementation/config/doc source established. Keep low-priority until source lineage is found.
- `fourier_rhythm_3bet,power_precision_3bet,power_orthogonal_5bet`: `DB`; P356A found DB evidence only; no current implementation/config/doc source established. Keep low-priority until source lineage is found.
- `power_precision_3bet,power_orthogonal_5bet`: `DB`; P356A found DB evidence only; no current implementation/config/doc source established. Keep low-priority until source lineage is found.

## Validation Plan Results

- Artifact completeness check: PASS (`manifest.csv` and `report.md` exist and are non-empty).
- CSV parse check: PASS (35 rows; required columns and allowed enum values validated).
- High-priority evidence path/commit check: PASS (every `HISTORICAL_RESTORABLE` row has evidence path, evidence commit, deleted path, deleted-at commit, and restorable-from commit; infrastructure-only row is explicitly `NOT_REPLAYABLE`).
- Production code restored: no.
- Full replay run: no.
- DB write: no DB opened/written for P357B.

## Risks And Blockers

- P356A/B/C artifacts are not present in current `origin/main`; this report relies on the historical P356 commits named above.
- `biglotto_ts3_markov_freq_5bet`, `biglotto_ts3_acb_4bet`, and `ts3_acb_4bet_biglotto` still lack direct runnable source evidence.
- Directly restorable scripts import historical DB helpers and numpy/scipy; replay adapters should isolate them and use immutable DB reads only.
- Some restored scripts encode historical backtest behavior, not current replay harness contracts; do not restore them into production code paths without a separate authorization/task.

## Next Recommended Task

P357C should restore selected high-priority files into a quarantined recovery namespace or artifact archive, then build minimal no-DB replay adapters for one candidate family at a time. Start with `539_3bet_orthogonal`, `p0b_539_3bet_f_cold_fmid`, and `p0c_539_3bet_f_cold_x2` because they have direct deleted source plus current p36 adapter references.
