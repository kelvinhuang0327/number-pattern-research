# P356A Strategy Inventory Summary

- Total strategy lineages: `1705`
- Big Lotto lineages: `57`
- Executable count: `15`
- Non-executable count: `1690`
- DB-only count: `5`
- Doc-only count: `155`
- Historical-deleted count: `0`
- ID reuse cases: `1`
- Replay: `NOT_RUN`

## Status Distribution
```json
{
  "OBSERVATION": 1,
  "ONLINE": 8,
  "REJECTED": 17,
  "RETIRED": 13,
  "UNKNOWN": 1666
}
```

## Skipped By Reason
```json
{
  "DB_ONLY": 5,
  "DOC_ONLY": 155,
  "EXECUTABLE": 15,
  "ID_REUSED": 2,
  "MISSING_CODE": 75,
  "UNKNOWN": 1453
}
```

## Big Lotto Seed Coverage
| seed_strategy_id | covered | lineage_count | executable_statuses |
| --- | --- | --- | --- |
| biglotto_ts3_markov_freq_5bet | True | 1 | MISSING_CODE |
| biglotto_ts3_markov_4bet_w30 | True | 1 | EXECUTABLE |
| coldpool15_biglotto | True | 1 | EXECUTABLE |
| biglotto_echo_aware_3bet | True | 1 | EXECUTABLE |
| biglotto_triple_strike | True | 1 | EXECUTABLE |
| biglotto_deviation_2bet | True | 1 | EXECUTABLE |
| ts3_regime_3bet | True | 1 | EXECUTABLE |
| cold_complement_biglotto | True | 1 | EXECUTABLE |
| markov_single_biglotto | True | 1 | EXECUTABLE |
| markov_2bet_biglotto | True | 1 | EXECUTABLE |
| fourier30_markov30_biglotto | True | 1 | EXECUTABLE |
| biglotto_ts3_acb_4bet | True | 1 | MISSING_CODE |
| bet2_fourier_expansion_biglotto | True | 2 | ID_REUSED |

## Old Replay Overview Gaps
- [Confirmed] P262B notes prior overview coverage mode was required to expose all 40 known strategies / 41 cells.
- [Confirmed] P263A/P263B notes D3 status audit previously covered only a subset and required SSOT rebuild.
- [Inferred] P356A extends beyond ONLINE/current overview by including registry stubs, DB-only rows, rejected artifacts, docs/evidence, and git history.

## Evidence Labels
- `[Confirmed]`: direct registry, DB, source, artifact, or git evidence.
- `[Inferred]`: classification inferred from naming/source grouping when direct metadata is absent.
- `[Unknown]`: no reliable current or historical evidence beyond seed/inference.
- `NOT_RUN`: no replay was executed by P356A.
