# P42: Wave 3 BIG_LOTTO Dry-Run + Temp Rehearsal

**Date**: 2026-05-24
**Branch**: p42-wave3-biglotto-dryrun-rehearsal
**Classification**: P42_WAVE3_BIGLOTTO_DRYRUN_REHEARSAL_READY

---

## Scope and Goal

P42 is a readiness/rehearsal task. This is NOT a production apply.

- Build BIG_LOTTO Wave 3 adapter scaffold following the p36 DAILY_539 pattern
- Generate 1500 dry-run rows per strategy (9000 total)
- Complete temp DB rehearsal R1/R2/R3
- Production rows must remain 28960
- STOP before production apply (P43 requires separate authorization)

---

## BIG_LOTTO Adapter Scaffold Design

**File**: `lottery_api/models/p42_wave3_biglotto_adapters.py`
**Reference pattern**: `lottery_api/models/p36_wave2_daily539_adapters.py`

### Pool and Pick Specification

| Parameter | Value |
|-----------|-------|
| Pool | 1-49 (BIG_LOTTO) |
| Pick | 6 main numbers per prediction |
| Special number | NOT predicted in Wave 3 |
| predicted_special | None (always) |
| special_hit | 0 (always) |

### Architecture

- `_P42AdapterMeta`: Lightweight metadata (strategy_id, strategy_name, lifecycle_status=DRY_RUN)
- `_P42BaseAdapter`: Base class with `get_one_bet()` and output validation (6 unique ints in [1,49])
- 6 concrete adapter classes, one per Wave 3 strategy
- `WAVE3_ADAPTERS`: ordered list, `WAVE3_ADAPTER_MAP`: dict keyed by strategy_id
- `generate_dryrun_rows()`: flat list generator with causal history slices

---

## Special Number Policy: NOT_PREDICTED_WAVE3

Wave 3 BIG_LOTTO strategies do NOT predict the special number.

- `predicted_special = None` for every row
- `special_hit = 0` for every row
- The actual special number is stored in `actual_special` for reference only
- This policy aligns with DAILY_539 Wave 2 (no special number in 539)

---

## Cutoff Semantics

For each target draw at index `i`:
- `history = all_draws[:i]` — strictly before the target (causal slice)
- `prediction_cutoff_date = history[-1]["date"]` — last available draw date
- `draw_date = target["date"]` — the target draw date

Invariant: `prediction_cutoff_date < draw_date` (verified for all 9000 rows)

---

## Per-Strategy Dry-Run Row Counts

| Rank | Strategy ID | Algorithm | Rows |
|------|------------|-----------|------|
| 1 | markov_single_biglotto | 1st-order Markov transition window=100, top-6 | 1500 |
| 2 | markov_2bet_biglotto | Markov 2注, bet-1 only (same as rank-1) | 1500 |
| 3 | bet2_fourier_expansion_biglotto | FFT Fourier window=500, top-6 bet-1 | 1500 |
| 4 | fourier30_markov30_biglotto | Fourier30 linear-ramp weighted, bet-1 | 1500 |
| 5 | cold_complement_biglotto | Coldest-12 from window=100, bet-1 (top 6) | 1500 |
| 6 | coldpool15_biglotto | Cold pool-15 pick-6 from window=100 | 1500 |
| | **Total** | | **9000** |

---

## Temp Rehearsal R1/R2/R3 Results

| Phase | Description | Result |
|-------|-------------|--------|
| R1 | Insert 9000 rows into temp DB | PASS (9000 inserted) |
| R2 | Re-run inserts, expect 0 new | PASS (0 duplicates) |
| R3 | Rollback all rows, expect 0 remaining | PASS (0 after delete) |

Temp DB path: `/tmp/p42_temp_rehearsal.db`

---

## Schema Validation Summary

| Check | Result |
|-------|--------|
| lottery_type == "BIG_LOTTO" | PASS (all 9000 rows) |
| predicted_numbers length == 6 | PASS |
| All numbers in [1, 49] | PASS |
| No duplicate predicted numbers | PASS |
| predicted_special == None | PASS |
| special_hit == 0 | PASS |
| lifecycle == "DRY_RUN" | PASS |
| hit_count == len(hit_numbers) | PASS |
| prediction_cutoff_date < draw_date | PASS (0 violations) |
| Schema validation errors | 0 |

---

## Production DB Safety

| Metric | Value |
|--------|-------|
| Production rows before | 28960 |
| Production rows after | 28960 |
| P42 rows in production DB | 0 |
| Production DB modified | NO |

---

## P43 Production Apply Readiness

P42 is complete. The Wave 3 BIG_LOTTO adapter scaffold is ready for production apply.

**Conditions for P43**:
- P42 must be merged to main (this PR)
- Separate P43 authorization phrase required
- P43 will apply 9000 rows to production DB (28960 → 37960)
- P43 must re-run all guards post-apply

**Authorization phrase for P43**:
`YES apply P43 production wave3 biglotto`

---

## Files Changed

| File | Type |
|------|------|
| `lottery_api/models/p42_wave3_biglotto_adapters.py` | NEW — adapter scaffold |
| `scripts/p42_wave3_biglotto_dryrun_rehearsal.py` | NEW — rehearsal script |
| `tests/test_p42_wave3_biglotto_dryrun_rehearsal.py` | NEW — contract tests |
| `outputs/replay/p42_wave3_biglotto_dryrun_rehearsal_20260524.json` | NEW — main output |
| `outputs/replay/p42_temp_rehearsal_20260524.json` | NEW — rehearsal details |
| `docs/replay/p42_wave3_biglotto_dryrun_rehearsal_20260524.md` | NEW — this document |
| `tests/test_p35_wave2_candidate_planning.py` | UPDATE — stale 19960→28960 assertion |

---

## Final Classification

`P42_WAVE3_BIGLOTTO_DRYRUN_REHEARSAL_READY`
