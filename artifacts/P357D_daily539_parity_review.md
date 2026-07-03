# P357D Daily 539 Parity Review

Final classification: `P357D_COMPLETE_WITH_GAPS`

## Scope And Safety

- Worktree: `/Users/kelvin/Kelvin-WorkSpace/LotteryNew.worktrees/P357-historical-strategy-recovery`
- Branch: `feature/P357-historical-strategy-recovery`
- Starting HEAD: `e3265ad4baeb35d0e8e60d6df5915bdd4ddfa855`
- Historical source inspected from `73062646^` (`28940a2572c051c6ba8b2ab6a077f706e800477d`).
- Deletion commit: `73062646f11d8881ab6c49565977fb553739bdf3`
- P357B artifacts were present and preserved:
  - `artifacts/P357B_historical_strategy_recovery_manifest.csv`
  - `artifacts/P357B_historical_strategy_recovery_report.md`
- P357C files were present and preserved:
  - `recovered_strategies/__init__.py`
  - `recovered_strategies/daily539/__init__.py`
  - `recovered_strategies/daily539/historical_adapters.py`
  - `tests/test_p357c_daily539_recovered_adapters.py`
  - `artifacts/P357C_daily539_recovery_adapter_manifest.csv`
  - `artifacts/P357C_daily539_recovery_adapter_report.md`
- No canonical checkout writes were made.
- No DB writes were made.
- No services were started.
- No production registry registration was added.
- No strategy statuses were changed.
- No full replay was run.

## Historical Source Extraction

| Candidate | Historical Source | Historical Callable | Dependencies | Input Expectations | Output Shape | Old Runtime Assumptions |
| --- | --- | --- | --- | --- | --- | --- |
| `539_3bet_orthogonal` | `tools/backtest_539_3bet_orthogonal.py` | `predict_3bet_ortho(hist)` | `DatabaseManager` in `load_data`; `UnifiedPredictionEngine`; `GapPressureScorer`; `ZoneShiftDetector`; NumPy/SciPy for backtest metrics | Sorted Daily 539 draw history; `numbers` list or JSON string | `list[list[int]]`, 3 bets x 5 numbers | DB-backed `load_data`, legacy model classes importable from project runtime, min train 300 in backtest |
| `p0b_539_3bet_f_cold_fmid` | `tools/backtest_539_3bet_f_cold_fmid.py` | `predict_3bet_f_cold_fmid(hist)` | `DatabaseManager` in `load_data`; `Counter`; NumPy/SciPy FFT for Fourier scoring | Daily 539 draw history; 500-draw Fourier window expected for validation | `list[list[int]]`, 3 bets x 5 numbers | DB-backed `load_data`, SciPy FFT, min train 500 in backtest |
| `p0c_539_3bet_f_cold_x2` | `tools/backtest_539_3bet_f_cold_x2.py` | `predict_3bet_f_cold_x2(hist)` | `DatabaseManager` in `load_data`; `Counter`; NumPy/SciPy FFT for Fourier scoring | Daily 539 draw history; 500-draw Fourier window expected for validation | `list[list[int]]`, 3 bets x 5 numbers | DB-backed `load_data`, SciPy FFT, min train 500 in backtest |

## Fixture Method

- Fixture type: deterministic in-memory Daily 539 synthetic history.
- Fixture size used for parity evidence: 520 draws.
- Data source: generated in test memory from SHA-256 bytes; no DB path or file-backed fixture.
- Comparisons:
  - bet count
  - number range validity
  - output shape
  - deterministic output
  - zero-overlap 15-number coverage
  - historical ranking/selection rules where source logic was self-contained

## Parity Matrix Summary

| Candidate | Classification | Evidence | Proceed To Controlled No-DB Replay Harness | Historical Reconstruction Required |
| --- | --- | --- | --- | --- |
| `539_3bet_orthogonal` | `PARITY_PARTIAL_NEEDS_NOTES` | Fixture output `[[17, 18, 19, 20, 21], [2, 6, 7, 26, 35], [30, 31, 33, 36, 39]]`; deterministic; 3 bets; all numbers `1..39`; 15 unique numbers | Yes, for no-DB harness shape/safety only | Yes, for exact historical ranking parity |
| `p0b_539_3bet_f_cold_fmid` | `PARITY_ACCEPTABLE_FOR_NO_DB_REPLAY_HARNESS` | Standard-library historical replica matched adapter exactly on 520-draw fixture: `[[3, 24, 31, 33, 37], [15, 20, 26, 30, 39], [5, 10, 13, 17, 34]]` | Yes | No |
| `p0c_539_3bet_f_cold_x2` | `PARITY_ACCEPTABLE_FOR_NO_DB_REPLAY_HARNESS` | Standard-library historical replica matched adapter exactly on 520-draw fixture: `[[3, 24, 31, 33, 37], [15, 20, 26, 30, 39], [9, 22, 25, 29, 36]]` | Yes | No |

## Adapter Differences

- `539_3bet_orthogonal`: P357C intentionally does not import `UnifiedPredictionEngine`, `GapPressureScorer`, or `ZoneShiftDetector`. It substitutes local no-DB SumRange, gap-pressure, and zone-shift heuristics. This preserves the output contract and orthogonal 3-bet shape, but exact historical ranking parity is not proven.
- `p0b_539_3bet_f_cold_fmid`: P357C removes DB loading and validates output shape. The core Fourier top-5, cold top-5, and Fourier middle-rank selection rules match the historical callable on the 520-draw fixture.
- `p0c_539_3bet_f_cold_x2`: P357C removes DB loading and validates output shape. The core Fourier top-5 plus two cold batches match the historical callable on the 520-draw fixture.

## Caveats

- No full replay was run.
- No historical edge metrics were recomputed.
- The available validation Python for pytest did not include NumPy/SciPy, so the P357D parity test uses a standard-library DFT replica of the historical SciPy FFT ranking.
- The historical SciPy `fftfreq(width, 1) > 0` implementation excludes the even-window Nyquist bin. P357C's manual Fourier scorer includes `width // 2`; this did not change outputs on the 500/520-draw parity fixtures checked here, but a short 120-draw exploratory fixture produced a P0-B third-bet difference. P357C already warns for histories below the 500-draw Fourier window, so this is a harness caveat rather than a blocker for controlled >=500-draw no-DB replay.
- `539_3bet_orthogonal` should not be treated as exact historical signal parity until the legacy model-backed legs are reconstructed or frozen behind no-DB fixtures.

## Validation Plan

The required validation commands for P357D are:

- `git diff --check`
- Python compile for changed Python files
- `pytest -q tests/test_p357c_daily539_recovered_adapters.py`
- `pytest -q tests/test_p357d_daily539_parity_review.py`
- artifact completeness check for:
  - `artifacts/P357D_daily539_parity_review.md`
  - `artifacts/P357D_daily539_parity_matrix.csv`

