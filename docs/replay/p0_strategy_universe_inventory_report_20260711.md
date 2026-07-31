# P0 Strategy Universe Inventory Report - 20260517

Generated at: `2026-07-11T03:38:24.872153+00:00`

## Final Classification
P0_STRATEGY_UNIVERSE_INVENTORY_COMPLETED

## Totals
- Total strategies: **524**
- Lifecycle breakdown:
  - PRODUCTION: 94
  - WATCHING: 13
  - PROVISIONAL: 6
  - REJECTED: 79
  - OFFLINE: 0
  - EXPERIMENTAL: 308
  - UNKNOWN: 24
- Lottery breakdown:
  - DAILY_539: 62
  - BIG_LOTTO: 173
  - POWER_LOTTO: 79
  - CROSS_GAME: 15
  - UNSPECIFIED: 195

## Coverage Gap Summary
- Strategies with replay rows: 35
- Strategies without replay rows: 489
- Strategies with historical records but no replay: 72
- Strategies with no records anywhere: 417

## Top 10 Ambiguous Classifications
- `strategy_prediction_replays` | strategy_prediction_replays | BIG_LOTTO | notes: lesson_reference:memory/lessons.md:L13
- `power_lotto_artifact_only_entries` | POWER_LOTTO artifact-only entries | POWER_LOTTO | notes: lesson_reference:memory/lessons.md:L39; lesson_reference:memory/todo.md:L52; source_count:2
- `power_lotto_replay_rows` | POWER_LOTTO replay rows | POWER_LOTTO | notes: lesson_reference:memory/lessons.md:L51
- `freq_x_markov` | freq_x_markov | UNSPECIFIED | notes: lesson_reference:MEMORY.md:L26
- `gap_x_markov` | gap_x_markov | UNSPECIFIED | notes: lesson_reference:MEMORY.md:L20; lesson_reference:MEMORY.md:L9; source_count:2
- `gmm_regime` | GMM Regime | UNSPECIFIED | notes: lesson_reference:MEMORY.md:L35
- `historical_snapshot` | historical snapshot | UNSPECIFIED | notes: lesson_reference:memory/lessons.md:L62; lesson_reference:memory/lessons.md:L80; lesson_reference:memory/todo.md:L58; source_count:3
- `historical_snapshot_lifecycle` | historical snapshot lifecycle | UNSPECIFIED | notes: lesson_reference:memory/lessons.md:L64
- `historical_snapshot_status` | historical snapshot status | UNSPECIFIED | notes: lesson_reference:memory/lessons.md:L43
- `lag2_echo` | lag2_echo | UNSPECIFIED | notes: lesson_reference:MEMORY.md:L84

## Safety Confirmation
- No DB writes were performed.
- No draw execution/import was performed.
- No prediction_runs / prediction_items / replay rows were modified.
- Inventory generation is read-only and classification-only.

## Notes
- This inventory uses conservative deduplication. Unclear aliases remain separate and are marked in `notes`.
- `UNKNOWN` is reserved for entries without enough lifecycle evidence.
- Production evidence prioritizes RSM / MEMORY / replay registry / current monitor files.
