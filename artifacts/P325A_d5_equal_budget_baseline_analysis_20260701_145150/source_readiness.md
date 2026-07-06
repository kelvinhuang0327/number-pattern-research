# P325A Source Readiness

## Inputs (read-only)
- `/Users/kelvin/Kelvin-WorkSpace/LotteryNew-p300a-d5-ui/public/demo-data/lottery-d5/p320a/strategy_combination_metrics.csv` — 2418 combination rows; SHA256 `0141b53f135a456fb3c2d02fe15f17aa5728a7ff8f47c88d26777c025e855ec5` (verified).
- `/Users/kelvin/Kelvin-WorkSpace/LotteryNew-p300a-d5-ui/public/demo-data/lottery-d5/p320a/top_descriptive_candidates.csv` — SHA256 verified (not required for computation).
- `/Users/kelvin/Kelvin-WorkSpace/LotteryNew-p300a-d5-ui/public/demo-data/lottery-d5/p320a/window_summary.csv` — SHA256 verified.
- `/Users/kelvin/Kelvin-WorkSpace/LotteryNew-p300a-d5-ui/public/demo-data/lottery-d5/p320a/source_provenance.json` — links to P320A source evidence root.
- Original P320A evidence root `/Users/kelvin/Kelvin-WorkSpace/p320a_d5_per_draw_combination_analysis_20260701_131917` (contains `build_analysis.py`; read for method confirmation only).

## Field availability for equal-budget analysis
Available per row: lottery_type, strategy_ids, combination_size, window, sample_size_draws,
sample_size_rows, predicted_number_count, top_k_by_strategy, hit_at_least_1..4_rate,
max_hit_count_0..6_draws (exact draw histogram), cross_strategy_ticket_pair_count,
any_number_overlap_pair_rate, mean_number_overlap_fraction, exact_duplicate_ticket_pair_rate,
special_hit_any_rate, delta_vs_max_constituent_hit1..4_rate, baseline_mode(not_computed),
inferential_status(DESCRIPTIVE_ONLY).

## What is / is not computable
- Ticket budget per draw m = sample_size_rows / sample_size_draws: COMPUTABLE (verified integer,
  constant per row; no variable per-draw top_k). This is the money-equivalent budget (raw tickets,
  duplicates counted — confirmed from P320A `build_analysis.py` line 156-157).
- Matched-budget random baseline `1-(1-q_k)^m` from lottery rules (6/49, 5/39): COMPUTABLE
  (exact hypergeometric). random_baseline_status = COMPUTED.
- TRUE empirical equal-budget subsampling of the strategies' OWN tickets to a common budget cap:
  requires per-draw per-ticket hit vectors, which are NOT present in the static aggregate artifacts
  (only aggregate rates + max-hit histogram). equal_budget_status = INSUFFICIENT_RAW_DATA
  (raw tickets exist only in the P320A source snapshot DB, out of this zero-DB artifact's scope).
  No equal-budget metric was fabricated; the matched-budget random reference is used instead.

## Determinism / reproducibility
- No DB opened. No randomness. Fixed lottery rules. Re-running `build_p325a.py` over the same
  SHA256-verified inputs reproduces byte-identical payload artifacts.
