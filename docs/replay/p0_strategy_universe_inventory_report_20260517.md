# P0 Strategy Universe Inventory Report - 20260517

Generated at: `2026-05-17T07:59:01.701200+00:00`

## Final Classification
P0_STRATEGY_UNIVERSE_INVENTORY_COMPLETED

## Totals
- Total strategies: **506**
- Lifecycle breakdown:
  - PRODUCTION: 68
  - WATCHING: 7
  - PROVISIONAL: 6
  - REJECTED: 90
  - OFFLINE: 0
  - EXPERIMENTAL: 307
  - UNKNOWN: 28
- Lottery breakdown:
  - DAILY_539: 64
  - BIG_LOTTO: 174
  - POWER_LOTTO: 77
  - CROSS_GAME: 15
  - UNSPECIFIED: 176

## Coverage Gap Summary
- Strategies with replay rows: 13
- Strategies without replay rows: 493
- Strategies with historical records but no replay: 86
- Strategies with no records anywhere: 407

## Top 10 Ambiguous Classifications
- `predict_539_5bet_f4cold` | predict_539_5bet_f4cold | DAILY_539 | notes: lesson_reference:memory/todo.md:L23
- `bet_deviation_complement` | bet_deviation_complement | BIG_LOTTO | notes: lesson_reference:memory/todo.md:L76
- `bet_fourier_rhythm` | bet_fourier_rhythm | BIG_LOTTO | notes: lesson_reference:memory/todo.md:L76; lesson_reference:memory/todo.md:L77; source_count:2
- `bl_ts3_m4_fo` | BL TS3+M4+FO | BIG_LOTTO | notes: lesson_reference:memory/todo.md:L100
- `core_satellite` | Core-Satellite | BIG_LOTTO | notes: lesson_reference:memory/lessons.md:L107
- `cold_complement` | Cold Complement | UNSPECIFIED | notes: lesson_reference:memory/todo.md:L97
- `echo_weight_grid_search` | Echo weight grid search | UNSPECIFIED | notes: lesson_reference:memory/lessons.md:L66
- `fourier30_markov30` | Fourier30+Markov30 | UNSPECIFIED | notes: lesson_reference:memory/todo.md:L97
- `fourier_rhythm_3bet_accelerating` | fourier_rhythm_3bet ACCELERATING | UNSPECIFIED | notes: lesson_reference:memory/todo.md:L32
- `freq_x_markov` | freq_x_markov | UNSPECIFIED | notes: lesson_reference:MEMORY.md:L26

## Safety Confirmation
- No DB writes were performed.
- No draw execution/import was performed.
- No prediction_runs / prediction_items / replay rows were modified.
- Inventory generation is read-only and classification-only.

## Notes
- This inventory uses conservative deduplication. Unclear aliases remain separate and are marked in `notes`.
- `UNKNOWN` is reserved for entries without enough lifecycle evidence.
- Production evidence prioritizes RSM / MEMORY / replay registry / current monitor files.
