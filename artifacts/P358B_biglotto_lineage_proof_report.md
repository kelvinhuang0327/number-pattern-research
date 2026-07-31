# P358B Big Lotto Lineage Proof Report

## Executive summary

P358B performed a focused source-identity and lineage-separation pass for:

- `biglotto_ts3_markov_freq_5bet`
- `biglotto_ts3_acb_4bet`
- `ts3_acb_4bet_biglotto`
- `bet2_fourier_expansion_biglotto`

Final classification: `P358B_COMPLETE_LINEAGE_PROOF_WITH_BLOCKED_ADAPTERS`.

No replay, backfill, temp-DB rehearsal, production apply, or adapter expansion was run. No DB was opened or written. No strategy status, production registry, deploy config, or service runtime was changed.

The result is conservative:

- `biglotto_ts3_markov_freq_5bet`: partial evidence only; registered-source identity is still not proven.
- `biglotto_ts3_acb_4bet`: blocked; current evidence is a non-executable registry stub plus rejected/result artifacts.
- `ts3_acb_4bet_biglotto`: blocked; rejected JSON lineage only, with no callable source found.
- `bet2_fourier_expansion_biglotto`: distinct lineages are proven; adaptation remains blocked by confirmed ID reuse.

## Worktree and safety state

Verified before artifact creation:

- Worktree: `/Users/kelvin/Kelvin-WorkSpace/LotteryNew.worktrees/P358-biglotto-historical-strategy-recovery`
- Branch: `feature/P358-biglotto-historical-strategy-recovery`
- HEAD: `0e8584a209457fa8fb962168a0251623e593135f`
- Ahead of `origin/main`: `0 1`
- Initial status: clean
- Required P358A artifacts, adapters, and tests existed.

Final P358B artifacts are only in this worktree. No P358B artifact files remain in the canonical checkout `/Users/kelvin/Kelvin-WorkSpace/LotteryNew`.

## Search scope

Evidence used repo files and Git history only. The pass inspected current grep hits for all priority ids plus broad case-insensitive scans for `acb`, `freq`, `fourier_expansion`, `P42`, and `P280`. It also inspected `git log --all --name-only` and deleted-path logs for `*biglotto*` and `*lotto*`, plus the `73062646^` historical tree.

Important commits:

- `0e8584a209457fa8fb962168a0251623e593135f`: P358A local recovery commit.
- `f8ef27f73887c622148184f6cd527f9c73ce53d6`: P356 inventory and replay-eligible lineage artifacts.
- `a57f4df2662ac8a838c1fd87673fdf5993d7423a`: registry non-executable lifecycle stubs.
- `73062646f11d8881ab6c49565977fb553739bdf3`: cleanup commit; `73062646^` contains legacy strategy/result artifacts.
- `37999e12f0cc77eca7a8dc8a2b928d6c7b70d813` and `418c3def1863b14997e86857b2b81392051773e7`: P42 Wave 3 Big Lotto dry-run adapter scaffold lineage.
- `56c71a145d36081b7cbeecc33fa6e0c6c69541cd` and `50c17464d2770a8ff2e5db2bca2f3080240c1858`: P280 no-DB/freeze reconciliation lineage.
- `8da5d4c3d5761e48c128cc4644d4d3f3f4f324b8`, `44b192a2964aef6917ccd52225b5389eb19f6172`, and `4d00d7a47d6ff23e3c16e4ef0bb68e07aa5ca8df`: rejected archive lineage for historical JSON artifacts.

## biglotto_ts3_markov_freq_5bet

Conclusion: partial only; blocked for registered-id replay or adapter work.

Current evidence paths:

- `lottery_api/models/replay_strategy_registry.py`
- `tools/backtest_biglotto_5bet_ts3markov.py`
- `artifacts/P358A_biglotto_historical_recovery_manifest.csv`
- `artifacts/P358A_biglotto_historical_recovery_report.md`
- `outputs/replay/p1_replay_truth_executable_evidence_report_20260513.md`
- `artifacts/P356A_strategy_inventory_all.csv`
- `artifacts/P356B_replay_eligible_manifest.csv`
- `artifacts/P357B_historical_strategy_recovery_manifest.csv`

Historical evidence paths:

- `rejected/ts3_markov_freq_5bet_biglotto.json`
- `strategies/big_lotto/5bet_ts3_markov_freq/strategy.yaml` at `73062646^`
- `strategies/big_lotto/5bet_ts3_markov_freq/backtest_report.md` at `73062646^`
- `tools/backtest_biglotto_5bet_ts3markov.py`

Evidence details:

- The registry row is a non-executable lifecycle stub in `lottery_api/models/replay_strategy_registry.py`, introduced in the lifecycle-stub lineage at `a57f4df2662ac8a838c1fd87673fdf5993d7423a`.
- The historical `strategies/big_lotto/5bet_ts3_markov_freq/strategy.yaml` at `73062646^` describes a 5-bet TS3 + Markov + Frequency Leftover strategy and points to `tools/backtest_biglotto_5bet_ts3markov.py`.
- `tools/backtest_biglotto_5bet_ts3markov.py` is runnable-style historical helper code, but it imports `lottery_api.database` and SciPy FFT and is not proven to be the registered stub's direct source identity.
- Prior P356/P358A evidence explicitly distinguishes the current helper/shape evidence from the registered id and says no adapter should be created under `biglotto_ts3_markov_freq_5bet` without a proven mapping.

Classification:

- `source_identity_status`: `PARTIAL_EVIDENCE`
- `adapter_recommendation`: `NEEDS_RECONSTRUCTION`
- `replay_recommendation`: `NOT_READY_LINEAGE_GAP`
- Confidence: `MEDIUM`

## biglotto_ts3_acb_4bet

Conclusion: blocked; missing runnable source.

Current evidence paths:

- `lottery_api/models/replay_strategy_registry.py`
- `rejected/ts3_acb_4bet_biglotto.json`
- `artifacts/P356A_strategy_inventory_all.csv`
- `artifacts/P356B_replay_eligible_manifest.csv`
- `artifacts/P357B_historical_strategy_recovery_manifest.csv`
- `artifacts/P358A_biglotto_historical_recovery_manifest.csv`
- `outputs/replay/p1_replay_truth_executable_evidence_report_20260513.md`

Historical evidence paths:

- `tmp/backend_archive/root_legacy/backtest_ts3_acb_4bet_results.json` at `73062646^`

Evidence details:

- The registry entry is a non-executable lifecycle stub in `lottery_api/models/replay_strategy_registry.py`.
- `rejected/ts3_acb_4bet_biglotto.json` gives rejection statistics and retest conditions, but it is not callable predictor source.
- `73062646^:tmp/backend_archive/root_legacy/backtest_ts3_acb_4bet_results.json` contains result metrics for TS3+ACB 4-bet, not Python source.
- P356A/P357B/P358A classify this path as missing code or reconstruction-needed, and P356A specifically notes special handling not to fake execution.

Classification:

- `source_identity_status`: `MISSING_RUNNABLE_SOURCE`
- `adapter_recommendation`: `DO_NOT_ADAPT_MISSING_SOURCE`
- `replay_recommendation`: `NOT_READY_MISSING_SOURCE`
- Confidence: `HIGH`

## ts3_acb_4bet_biglotto

Conclusion: blocked; rejected artifact only, no callable entrypoint.

Current evidence paths:

- `rejected/ts3_acb_4bet_biglotto.json`
- `rejected/README.md`
- `artifacts/P356A_strategy_inventory_all.csv`
- `artifacts/P356B_replay_eligible_manifest.csv`
- `artifacts/P357B_historical_strategy_recovery_manifest.csv`
- `artifacts/P358A_biglotto_historical_recovery_manifest.csv`
- `scripts/v2_artifact_only_parser_dryrun.py`

Historical evidence paths:

- `tmp/backend_archive/root_legacy/backtest_ts3_acb_4bet_results.json` at `73062646^`

Evidence details:

- `rejected/ts3_acb_4bet_biglotto.json` describes the rejected TS3+ACB 4-bet research outcome.
- `rejected/README.md` indexes `ts3_acb_4bet_biglotto` as rejected/marginal.
- The only `73062646^` path found for this lineage is a result JSON file, not predictor source.
- The artifact-only parser evidence proves parseable retrospective rows, not a runnable strategy implementation.

Classification:

- `source_identity_status`: `MISSING_RUNNABLE_SOURCE`
- `adapter_recommendation`: `DO_NOT_ADAPT_MISSING_SOURCE`
- `replay_recommendation`: `NOT_READY_MISSING_SOURCE`
- Confidence: `HIGH`

## bet2_fourier_expansion_biglotto

Conclusion: distinct lineages are proven; blocked from adaptation by ID reuse.

Current P42/P280 frozen-code lineage evidence:

- `lottery_api/models/p42_wave3_biglotto_adapters.py`
- `tools/big649_no_db_strategy_output_adapter.py`
- `analysis/p280d_big649_future_only_protocol.py`
- `docs/replay/p41_wave3_biglotto_adapter_bootstrap_planning_20260524.md`
- `docs/replay/p42_wave3_biglotto_dryrun_rehearsal_20260524.md`
- `artifacts/P356A_strategy_id_reuse_cases.md`
- `artifacts/P358A_biglotto_historical_recovery_manifest.csv`

Historical rejected JSON lineage evidence:

- `rejected/bet2_fourier_expansion_biglotto.json`
- `rejected/README.md`
- `strategies/big_lotto/2bet_fourier_rhythm/strategy.yaml` at `73062646^`

Evidence details:

- P42 code (`37999e12f0cc77eca7a8dc8a2b928d6c7b70d813`, merged lineage `418c3def1863b14997e86857b2b81392051773e7`) provides `predict_fourier_expansion_bet1` under `lottery_api/models/p42_wave3_biglotto_adapters.py`.
- P280 code (`56c71a145d36081b7cbeecc33fa6e0c6c69541cd`, later reconciliation `50c17464d2770a8ff2e5db2bca2f3080240c1858`) freezes that source through `tools/big649_no_db_strategy_output_adapter.py`.
- The rejected JSON lineage, introduced through the rejected archive commits (`8da5d4c3d5761e48c128cc4644d4d3f3f4f324b8`, `44b192a2964aef6917ccd52225b5389eb19f6172`, `4d00d7a47d6ff23e3c16e4ef0bb68e07aa5ca8df`), describes a Fourier expansion replacement/zone-filter rationale.
- P356A and P358A already classify this as ID reuse: current P42/P280 frozen code differs from the historical rejected JSON rationale lineage while sharing `strategy_id`.

Classification:

- `source_identity_status`: `PROVEN_DISTINCT_LINEAGES`
- `adapter_recommendation`: `DO_NOT_ADAPT_ID_REUSE`
- `replay_recommendation`: `NOT_READY_ID_REUSE`
- Confidence: `HIGH`

## Adapter decision

No P358B adapter was created.

Reasons:

- `biglotto_ts3_markov_freq_5bet` still lacks proven registered-source identity.
- `biglotto_ts3_acb_4bet` and `ts3_acb_4bet_biglotto` still lack runnable predictor source.
- `bet2_fourier_expansion_biglotto` has confirmed ID reuse, so adapting it under the shared id would risk lineage contamination.

## Validation notes

P358B is artifact-only. Validation should confirm:

- CSV parses and contains all required columns.
- Every priority target has at least one row.
- Report exists and contains conclusions for all four targets.
- No DB files changed.
- No registry/status/deploy files changed.
- No full replay run was performed.
