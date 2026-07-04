# P357C Daily 539 Recovery Adapter Report

Final classification: `P357C_COMPLETE_DAILY539_ADAPTERS`

## Scope And Safety

- Worktree: `/Users/kelvin/Kelvin-WorkSpace/LotteryNew.worktrees/P357-historical-strategy-recovery`
- Branch: `feature/P357-historical-strategy-recovery`
- Starting HEAD: `e3265ad4baeb35d0e8e60d6df5915bdd4ddfa855`
- P357B artifacts preserved:
  - `artifacts/P357B_historical_strategy_recovery_manifest.csv`
  - `artifacts/P357B_historical_strategy_recovery_report.md`
- P357B artifacts status at start: present and untracked.
- No canonical checkout writes were made.
- No DB writes were made.
- No services were started.
- No production registry registration was added.
- No strategy statuses were changed.
- No full replay was run.

## Historical Evidence

All three target files are directly restorable from git history.

| Candidate | Historical Source | Deletion Commit | Restorable Commit | Historical Callable | Imports / Dependencies | Compatibility Risks |
| --- | --- | --- | --- | --- | --- | --- |
| `539_3bet_orthogonal` | `tools/backtest_539_3bet_orthogonal.py` | `73062646` | `73062646^` (`28940a2572c051c6ba8b2ab6a077f706e800477d`) | `predict_3bet_ortho(hist)` | `json`, `random`, `math`, `numpy`, `scipy.stats`, `DatabaseManager` in `load_data`, `UnifiedPredictionEngine`, `GapPressureScorer`, `ZoneShiftDetector` | Historical prediction legs depended on legacy model APIs and DB-backed `load_data`; P357C adapter preserves no-DB 3-bet shape with in-memory substitutes for SumRange, GapPressure, and ZoneShift. |
| `p0b_539_3bet_f_cold_fmid` | `tools/backtest_539_3bet_f_cold_fmid.py` | `73062646` | `73062646^` (`28940a2572c051c6ba8b2ab6a077f706e800477d`) | `predict_3bet_f_cold_fmid(hist)` | `json`, `random`, `math`, `numpy`, `scipy.stats`, `scipy.fft`, `Counter`, `DatabaseManager` in `load_data` | Historical backtest entrypoint opened DB only in `load_data`; P357C adapter removes that path and keeps in-memory Fourier/cold/fmid selection. |
| `p0c_539_3bet_f_cold_x2` | `tools/backtest_539_3bet_f_cold_x2.py` | `73062646` | `73062646^` (`28940a2572c051c6ba8b2ab6a077f706e800477d`) | `predict_3bet_f_cold_x2(hist)` | `json`, `random`, `math`, `numpy`, `scipy.stats`, `scipy.fft`, `Counter`, `DatabaseManager` in `load_data` | Historical backtest entrypoint opened DB only in `load_data`; P357C adapter removes that path and keeps in-memory Fourier/cold/cold-second-batch selection. |

## Quarantined Adapter

Adapter path: `recovered_strategies/daily539/historical_adapters.py`

Public callables:

- `generate_no_db_adapter_output(strategy_id, history)`
- `predict_3bet_ortho(history)`
- `predict_3bet_f_cold_fmid(history)`
- `predict_3bet_f_cold_x2(history)`

Required output shape is implemented:

- `strategy_id`
- `game`
- `bet_count`
- `predictions`
- `candidate_sets`
- `notes`
- `warnings`

The package is intentionally isolated under `recovered_strategies/` and is not imported by production routes, replay registries, services, migrations, or status files.

## Fixture Smoke Status

Focused fixture smoke test:

`tests/test_p357c_daily539_recovered_adapters.py`

Smoke assertions:

- exact three-strategy slice only
- each adapter returns `game=DAILY_539`
- each adapter returns `bet_count=3`
- each adapter returns three 5-number candidate sets
- all numbers are in `1..39`
- each 3-bet set is orthogonal with 15 unique numbers
- `sqlite3.connect` is monkeypatched to fail, confirming adapter calls do not open SQLite

Current replay readiness for all three candidates: `READY_FOR_NO_DB_REPLAY_SMOKE`.

## Caveats

- This is not a full replay and does not assert historical edge metrics.
- `539_3bet_orthogonal` had the highest compatibility risk because the deleted source delegated to legacy model classes; the quarantined adapter avoids production imports and preserves the no-DB multi-bet contract with local in-memory substitutes.
- The P0-B/P0-C adapters preserve the historical Fourier and cold selection logic while replacing `scipy.fft` with `numpy.fft` to reduce dependencies in the quarantined smoke path.
