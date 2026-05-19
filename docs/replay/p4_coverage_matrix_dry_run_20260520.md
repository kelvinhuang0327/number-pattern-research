# P4 Replay Coverage Matrix — Dry-Run Report

Generated: 2026-05-19T12:42:25.482598Z
Catalog source: `p2_json`  
Catalog entries (denominator): 59  
Draws evaluated: 50 (most recent 50)  
Total cells: 400  
Covered cells: 0 (0.0%)  

## Coverage Status Summary

| Status | Count |
|--------|-------|
| `MISSING_REPLAY_ROW` | 100 |
| `RECONSTRUCTIBLE_PENDING` | 300 |

## Per Lottery Type

| Lottery Type | Strategies | Draws | Cells | Covered | Coverage% |
|---|---|---|---|---|---|
| POWER_LOTTO | 5 | 0 | 0 | 0 | 0.0% |
| BIG_LOTTO | 5 | 0 | 0 | 0 | 0.0% |
| DAILY_539 | 8 | 50 | 400 | 0 | 0.0% |
| UNKNOWN | 41 | 0 | 0 | 0 | 0.0% |

## Safety Confirmation

- DB `strategy_prediction_replays` rows before: 460
- DB `strategy_prediction_replays` rows after: 460
- **Rows unchanged**: True

## Notes

- `COVERED` = replay row exists for this draw × strategy
- `MISSING_REPLAY_ROW` = REGISTERED_WITH_REPLAY_ROWS but no row yet
- `RECONSTRUCTIBLE_PENDING` = has artifact, rows not yet backfilled (P5-P7 needed)
- `NO_DATA` = no artifact, no rows, no reconstruction path
- `ARTIFACT_ONLY` = ARTIFACT_CANDIDATE, not in runtime registry
- This report is **read-only measurement only**. No rows were generated.
