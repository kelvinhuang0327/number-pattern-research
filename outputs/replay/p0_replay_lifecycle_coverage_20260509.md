# P0-B Replay Lifecycle Coverage Audit
**Date:** 2026-05-09  
**Auditor:** P0-Replay-UI Executor  
**Scope:** All strategies registered in `replay_strategy_registry.py` × all lifecycle states

---

## 1. Coverage Summary

| strategy_id | lottery_type | lifecycle_status | total_rows | predicted | replay_errors | has_coverage | is_coverage_gap |
|-------------|--------------|-----------------|-----------|-----------|---------------|-------------|-----------------|
| biglotto_deviation_2bet  | BIG_LOTTO   | ONLINE | 70  | 70 | 0  | ✅ | No |
| biglotto_triple_strike   | BIG_LOTTO   | ONLINE | 70  | 70 | 0  | ✅ | No |
| daily539_f4cold          | DAILY_539   | ONLINE | 90  | 70 | 20 | ✅ | No |
| daily539_markov_cold     | DAILY_539   | ONLINE | 90  | 70 | 20 | ✅ | No |
| power_orthogonal_5bet    | POWER_LOTTO | ONLINE | 70  | 70 | 0  | ✅ | No |
| power_precision_3bet     | POWER_LOTTO | ONLINE | 70  | 70 | 0  | ✅ | No |

**Coverage Gaps:** 0

---

## 2. Lifecycle State Distribution

| lifecycle_status | strategy count |
|-----------------|---------------|
| ONLINE      | 6 |
| OFFLINE     | 0 |
| REJECTED    | 0 |
| OBSERVATION | 0 |
| RETIRED     | 0 |

All 6 currently registered strategies are in **ONLINE** state. There are no OFFLINE, REJECTED, OBSERVATION, or RETIRED strategies in the registry at this time. The lifecycle infrastructure is in place for future state transitions.

---

## 3. Replay Error Notes

The 20 `REPLAY_ERROR` rows for `daily539_f4cold` and `daily539_markov_cold` originate from `strategy_replay_runs` run #3 (status: `FAILED_LEGACY`), which is preserved for audit traceability. Current runs #4 and #7 (status: `DONE`) produced clean PREDICTED rows for both strategies. These legacy error rows do NOT represent a coverage gap.

---

## 4. What Was Not Done

- No replay generation was triggered
- No strategy states were modified
- No DB rows were deleted or updated

---

## 5. Recommendations (Follow-up)

- When OFFLINE/REJECTED/OBSERVATION strategies are created, re-run this audit
- Consider a nightly CI check (`test_replay_lifecycle_coverage.py`) to detect new coverage gaps automatically
- `outputs/replay/` files are artifacts only; API/UI reads exclusively from DB (per `replay_data_hygiene.md §1`)
