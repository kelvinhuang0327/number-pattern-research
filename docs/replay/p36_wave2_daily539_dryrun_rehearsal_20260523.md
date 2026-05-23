# P36: Wave 2 DAILY_539 Dry-Run + Temp Rehearsal

**Date**: 2026-05-23
**Branch**: p36-wave2-daily539-dryrun-rehearsal
**Classification**: P36_WAVE2_DAILY539_DRYRUN_REHEARSAL_READY
**Production rows before/after**: 19960 / 19960 (UNCHANGED)

---

## Scope

P36 implements dry-run readiness for the 6 DAILY_539 Wave 2 strategies selected in P35. This is a
**read-only rehearsal phase** — no rows are written to the production DB. Production apply requires
separate explicit authorization (P37).

---

## Wave 2 Strategies

All 6 are DAILY_539 LOW effort / LOW risk candidates from P35 planning:

| Rank | strategy_id | Source | Bet Recorded |
|------|------------|--------|--------------|
| 1 | `markov_1bet_539` | `backtest_39lotto_comprehensive.py::MarkovStrategy(n=1)` | 1-bet |
| 2 | `acb_single_539` | `quick_predict.py::predict_539_acb` | 1-bet |
| 3 | `zone_gap_3bet_539` | `backtest_39lotto_comprehensive.py::ZoneBalanceStrategy` | bet-1 of 3 |
| 4 | `539_3bet_orthogonal` | ACB+Markov+Fourier orthogonal | bet-1 of 3 |
| 5 | `p0b_539_3bet_f_cold_fmid` | `predict_539_5bet_f4cold.py` (cold+midfreq) | bet-1 of 3 |
| 6 | `p0c_539_3bet_f_cold_x2` | `predict_539_5bet_f4cold.py` (x2 cold) | bet-1 of 3 |

---

## Per-Strategy Dry-Run Row Counts

| strategy_id | lifecycle | row_count |
|-------------|-----------|-----------|
| markov_1bet_539 | DRY_RUN | 1500 |
| acb_single_539 | DRY_RUN | 1500 |
| zone_gap_3bet_539 | DRY_RUN | 1500 |
| 539_3bet_orthogonal | DRY_RUN | 1500 |
| p0b_539_3bet_f_cold_fmid | DRY_RUN | 1500 |
| p0c_539_3bet_f_cold_x2 | DRY_RUN | 1500 |
| **TOTAL** | | **9000** |

---

## Temp Rehearsal Results

| Step | Description | Result |
|------|-------------|--------|
| R1 | Insert 9000 rows into temp SQLite DB | PASS (9000 inserted) |
| R2 | Re-run inserts with duplicate detection | PASS (0 new rows) |
| R3 | Rollback — temp DB cleaned, production untouched | PASS |

---

## Schema Validation Summary

- Total rows validated: 9000
- Validation errors: 0
- `lottery_type == "DAILY_539"`: all rows PASS
- `lifecycle != "ONLINE"`: all rows PASS (all lifecycle=DRY_RUN)
- `predicted_numbers`: exactly 5 unique ints in [1..39] for all PREDICTED rows
- `hit_count == len(hit_numbers)`: all rows PASS
- `is_retired == False`: all rows PASS

---

## Lifecycle Semantics Confirmation

All 9000 dry-run rows have `lifecycle = "DRY_RUN"`. No rows have `lifecycle = "ONLINE"`. The P36
dry-run phase does not promote any strategy to ONLINE or ACTIVE status.

Adapter module: `lottery_api/models/p36_wave2_daily539_adapters.py`
- `_P36AdapterMeta.lifecycle_status = "DRY_RUN"` for all 6 adapters
- NOT registered in `replay_strategy_registry._ALL_ADAPTERS` or `_REGISTRY`
- temp DB only: `/tmp/p36_temp.db`

---

## Governance

- Drift guard (pre): `REPLAY_LIFECYCLE_DRIFT_GUARD_PASS`
- Branch governance guard (pre): `BRANCH_GOVERNANCE_PASS` (main, 19960 rows)
- Production DB rows before: 19960
- Production DB rows after: 19960 (UNCHANGED)
- Forbidden files staged: CLEAN (no DB, no bak, no pid files)

---

## P37 Production Apply Readiness

**Status**: READY — all P36 gates passed.

P37 (production apply) requires a **separate explicit authorization phrase**:

```
YES apply P37 production wave2 daily539
```

P37 will insert the 9000 rows from temp rehearsal into `lottery_api/data/lottery_v2.db`,
bringing the total from 19960 to **28960 rows**.

### Blockers

None. P36 rehearsal passed all checks.

---

## Files Created in P36

| File | Description |
|------|-------------|
| `lottery_api/models/p36_wave2_daily539_adapters.py` | 6 adapter wrappers + `generate_dryrun_rows()` |
| `scripts/p36_wave2_daily539_dryrun_rehearsal.py` | Main dry-run + rehearsal script |
| `tests/test_p36_wave2_daily539_dryrun_rehearsal.py` | Verification tests |
| `outputs/replay/p36_wave2_daily539_dryrun_rehearsal_20260523.json` | Main output |
| `outputs/replay/p36_temp_rehearsal_20260523.json` | Detailed rehearsal results |
| `docs/replay/p36_wave2_daily539_dryrun_rehearsal_20260523.md` | This document |
