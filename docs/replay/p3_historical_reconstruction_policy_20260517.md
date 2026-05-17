# P3 Historical Reconstruction vs Future Waiting Policy

1. Historical reconstruction does not wait for future draws.
2. Future waiting must not block historical coverage.
3. The 86 strategies with historical records but no replay rows are the next backfill-planning denominator.
4. The 407 strategies with no records anywhere remain DISPLAY_ONLY or wait for future data policy changes.
5. UNKNOWN lifecycle entries are not production-safe apply candidates.
6. This phase does not write DB state; it only emits dry-run classification and policy artifacts.
7. P4 can use the classification to review replay page acceptance, and P5 can use it to decide persistence / deployment source of truth.

## Current Split

- HISTORICAL_RECONSTRUCTION: 97
- FUTURE_WAITING: 2
- DISPLAY_ONLY: 407
- UNSUPPORTED: 0

## Safety

- db_write: false
- draw_import: false
- replay_row_generation: false
- prediction_update: false
- strategy_execution: false
