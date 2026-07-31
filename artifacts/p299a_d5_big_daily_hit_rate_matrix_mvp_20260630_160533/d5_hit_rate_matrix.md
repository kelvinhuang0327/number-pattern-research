# D5 Hit-Rate Matrix MVP

All values are retrospective replay observations only. Baselines are intentionally not computed in this MVP, so `delta` and `delta_pp` remain `NULL` and no edge is inferred.

## BIG_LOTTO
- Matrix rows: 55
- Strategies in coverage summary: 13
- Retrospective matrix-ready strategies: 11
- Not-ready strategies: 2
- Replay rows represented in coverage summary: 24140
- Maximum distinct target draws by strategy: 1550

## DAILY_539
- Matrix rows: 75
- Strategies in coverage summary: 16
- Retrospective matrix-ready strategies: 15
- Not-ready strategies: 1
- Replay rows represented in coverage summary: 34680
- Maximum distinct target draws by strategy: 1550

## Metric Semantics
- `m1_hits`, `m2_hits`, and `m3_hits` count replay rows whose `hit_count` is at least 1, 2, or 3 respectively.
- `m3plus_draw_successes` counts target draws where any replay row for that strategy/window/top_k reached `hit_count >= 3`.
- `m1_rate`, `m2_rate`, and `m3_rate` use replay rows as denominator. `m3plus_hit_rate` uses distinct target draws as denominator.
- `top_k` is the maximum `bet_index` observed for the strategy in the immutable replay table.

## Readiness
- `RETROSPECTIVE_MATRIX_READY` means rows are available for a D5 display contract. It does not mean production readiness or future predictive value.
- Rows with `baseline_mode=not_computed` must not be consumed as edge by an optimizer.
