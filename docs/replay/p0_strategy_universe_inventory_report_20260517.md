# P0 Strategy Universe Inventory Report - 20260517

Generated at: `2026-05-18T01:22:20.156728+00:00`

## Final Classification
P0_STRATEGY_UNIVERSE_INVENTORY_COMPLETED

## Totals
- Total strategies: **512**
- Lifecycle breakdown:
  - PRODUCTION: 69
  - WATCHING: 8
  - PROVISIONAL: 7
  - REJECTED: 82
  - OFFLINE: 0
  - EXPERIMENTAL: 305
  - UNKNOWN: 41
- Lottery breakdown:
  - DAILY_539: 67
  - BIG_LOTTO: 163
  - POWER_LOTTO: 80
  - CROSS_GAME: 15
  - UNSPECIFIED: 187

## Coverage Gap Summary
- Strategies with replay rows: 6
- Strategies without replay rows: 506
- Strategies with historical records but no replay: 76
- Strategies with no records anywhere: 430

## Top 10 Ambiguous Classifications
- `predict_539_5bet_f4cold` | predict_539_5bet_f4cold | DAILY_539 | notes: lesson_reference:memory/todo.md:L23
- `tools_predict_539_5bet_f4cold_py` | tools/predict_539_5bet_f4cold.py | DAILY_539 | notes: lesson_reference:memory/todo.md:L23
- `bet_deviation_complement` | bet_deviation_complement | BIG_LOTTO | notes: lesson_reference:memory/todo.md:L76
- `bet_fourier_rhythm` | bet_fourier_rhythm | BIG_LOTTO | notes: lesson_reference:memory/todo.md:L76; lesson_reference:memory/todo.md:L77; source_count:2
- `bl_ts3_m4_fo` | BL TS3+M4+FO | BIG_LOTTO | notes: lesson_reference:memory/todo.md:L100
- `core_satellite` | Core-Satellite | BIG_LOTTO | notes: lesson_reference:memory/lessons.md:L107
- `data_rolling_monitor_power_lotto_json` | data/rolling_monitor_POWER_LOTTO.json | POWER_LOTTO | notes: lesson_reference:memory/todo.md:L31
- `fcf_vs_ts3` | FCF vs TS3 | POWER_LOTTO | notes: lesson_reference:MEMORY.md:L100; lesson_reference:MEMORY.md:L44; source_count:2
- `power_lotto` | Power Lotto | POWER_LOTTO | notes: lesson_reference:MEMORY.md:L102; lesson_reference:memory/todo.md:L77; source_count:2
- `rolling_monitor_power_lotto` | rolling_monitor_POWER_LOTTO | POWER_LOTTO | notes: lesson_reference:memory/todo.md:L31

## Safety Confirmation
- No DB writes were performed.
- No draw execution/import was performed.
- No prediction_runs / prediction_items / replay rows were modified.
- Inventory generation is read-only and classification-only.

## Notes
- This inventory uses conservative deduplication. Unclear aliases remain separate and are marked in `notes`.
- `UNKNOWN` is reserved for entries without enough lifecycle evidence.
- Production evidence prioritizes RSM / MEMORY / replay registry / current monitor files.
