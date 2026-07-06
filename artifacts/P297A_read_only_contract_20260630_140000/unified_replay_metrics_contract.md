# Unified Replay Metrics Contract

Generated: 2026-06-30T07:38:29.278339+00:00
Task: P297A_BIG649_UNIFIED_REPLAY_METRICS_CONTRACT_AND_STRATEGY_INVENTORY
Mode: read-only, artifact-only. This contract defines fields for retrospective replay metrics. It does not authorize DB writes, registry publication, production application, or betting claims.

## Row Grain
One record represents one metric value for one `(lottery, strategy_id, metric_family, window_segment, top_k, draw_range)` cell. The same strategy may have multiple rows for M1/M2/M3, prize tiers, special/zone metrics, and inferential summaries.

## Required Identity Fields
- `contract_version`: `p297a_unified_replay_metrics_contract_v1`.
- `lottery`: exact enum `BIG_LOTTO`, `DAILY_539`, `POWER_LOTTO`.
- `strategy_id`: stable replay/catalog identifier.
- `strategy_name`: display name from registry/inventory when available.
- `metric_family`: one of `HIT_RATE`, `M3PLUS`, `PRIZE_AWARE`, `SPECIAL_OR_ZONE`, `BASELINE`, `INFERENTIAL`, `FEASIBILITY`, `OPTIMIZER_INPUT`.
- `window_segment`: canonical label such as `recent_100`, `recent_150`, `recent_500`, `recent_1500`, `block_500_1`, `block_500_2`, `block_500_3`, or `full_available`.
- `top_k`: integer 1..6. For multi-bet strategies this is the maximum bet index included in the draw-level aggregation. For one-bet stored rows, use `1` even when the strategy name historically contains a larger bet count.
- `draw_start`, `draw_end`: inclusive draw identifiers for the metric window, stored as text plus optional numeric cast fields.
- `sample_size_draws`: number of distinct target draws in denominator.
- `sample_size_rows`: number of replay rows used after eligibility/exclusion filters.
- `source_artifact`: file path or DB table source used to derive the metric.
- `source_artifact_sha256`: SHA256 of artifact when file-backed; NULL if not computed.

## Required Metric Fields
- `m1_hits`, `m2_hits`, `m3_hits`: counts by exact main-number hit depth where applicable.
- `m3plus_draw_successes`: draw-level count where any included bet has `hit_count >= 3`.
- `m1_rate`, `m2_rate`, `m3_rate`, `m3plus_hit_rate`: count divided by `sample_size_draws`; NULL when not applicable.
- `special_hit_count`: BIG_LOTTO actual special hit count or POWER_LOTTO second-zone hit count when structurally available.
- `special_or_zone_metric_id`: e.g. `BIG_SPECIAL_IN_PREDICTED_MAIN`, `POWER_SECOND_ZONE_HIT`, `DAILY_539_NOT_APPLICABLE`.
- `special_or_zone_rate`: special/zone count divided by eligible denominator.
- `prize_tier_id`: scorer tier identifier when using prize-aware scoring; NULL for M3+ only rows.
- `prize_tier_success_count`: count for that tier.
- `any_prize_aware_win_count`: governed draw-level prize-aware success count.
- `any_prize_aware_win_rate`: governed count divided by eligible draw denominator.
- `baseline_mode`: `exact_hypergeometric_1bet`, `per_draw_conditional_MC`, `official_prize_formula`, `empirical_null`, `not_computed`, or `not_applicable`.
- `baseline_value`: baseline rate/expected value for the same denominator.
- `delta`: observed rate minus baseline value in proportion units.
- `delta_pp`: observed rate minus baseline in percentage points.
- `confidence_method`: `exact_poisson_binomial`, `monte_carlo`, `wilson`, `bootstrap`, `not_computed`, or `not_applicable`.
- `confidence_low`, `confidence_high`: interval bounds; NULL when not computed.
- `p_value`: inferential p-value; NULL for descriptive-only artifacts.
- `multiple_testing_family_size`: integer family size when applicable.
- `correction_method`: `bonferroni`, `bh_fdr`, `none`, `not_computed`.
- `inferential_status`: `GO`, `NO_GO`, `NULL`, or `NOT_READY`. `GO` is reserved for passed inferential evidence and still does not mean production-ready.
- `readiness_status`: `GO`, `NO_GO`, `NULL`, `NOT_READY`. Use `NOT_READY` for missing prospective threshold/horizon or missing canonical source.

## Eligibility and Exclusion Fields
- `replay_status_filter`: e.g. `PREDICTED`.
- `dry_run_filter`: normally `0` for durable replay metrics.
- `causality_status`: `VERIFIED`, `VIOLATION`, `NOT_CHECKED`.
- `eligibility_status`: `ELIGIBLE`, `PARTIAL`, `EXCLUDED`, `NOT_READY`.
- `exclusion_reason`: explicit reason such as `MISSING_PREDICTED_SECOND_ZONE`, `NO_REPLAY_ROWS`, `NO_CANONICAL_VIEW`, or NULL.
- `canonical_source_status`: `PRESENT`, `ABSENT`, `PARTIAL`, `UNKNOWN`. POWER_LOTTO canonical view is currently absent in this read-only inspection.

## Consumer Coverage
- D2 per-strategy hit-rate matrix consumes `HIT_RATE`, `M3PLUS`, `BASELINE`, and `INFERENTIAL` fields.
- D3 prize-tier scoring consumes `PRIZE_AWARE`, `SPECIAL_OR_ZONE`, eligibility, and scorer provenance fields.
- D4 cross-lottery feasibility consumes identity, canonical source, sample-size, eligibility, and blocked reason fields.
- D5 combination optimizer consumes top-k, draw-range, hit-rate, baseline, delta, confidence, and readiness fields, but must not optimize cells marked `NOT_READY` or `NULL` as if they were future edge.

## Non-Claims
This contract is a reporting schema. It must not be interpreted as a strategy promotion, wagering recommendation, production readiness signal, or evidence of future predictive ability.
