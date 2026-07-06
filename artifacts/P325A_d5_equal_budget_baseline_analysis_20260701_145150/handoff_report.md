# P325A Handoff Report

1. Final classification: **P325A_D5_EQUAL_BUDGET_BASELINE_COMPLETE_WITH_LIMITATIONS**
2. Evidence root: `/Users/kelvin/Kelvin-WorkSpace/p325a_d5_equal_budget_baseline_analysis_20260701_145150`
3. Source files used (read-only, SHA256-verified):
   - `/Users/kelvin/Kelvin-WorkSpace/LotteryNew-p300a-d5-ui/public/demo-data/lottery-d5/p320a/strategy_combination_metrics.csv` (2418 rows)
   - `/Users/kelvin/Kelvin-WorkSpace/LotteryNew-p300a-d5-ui/public/demo-data/lottery-d5/p320a/top_descriptive_candidates.csv`, `window_summary.csv`, `source_provenance.json`
   - `/Users/kelvin/Kelvin-WorkSpace/p320a_d5_per_draw_combination_analysis_20260701_131917/build_analysis.py` (method confirmation only)
4. Raw per-draw equal-budget subsampling possible? **NO** from static aggregates — per-draw
   per-ticket hit vectors are absent. equal_budget_status = INSUFFICIENT_RAW_DATA. No data faked.
5. Random baseline computed? **YES** — exact hypergeometric matched-budget reference
   `1-(1-q_k)^m`, m = sample_size_rows/sample_size_draws (verified integer/constant).
6. Exact method: see `baseline_method.md`. Matched-budget analytic random-portfolio reference +
   exact one-sided binomial screen vs the equal-budget-random null.
7. Output artifacts: phase0_state.md, source_readiness.md, baseline_method.md,
   equal_budget_baseline_metrics.csv, equal_budget_baseline_summary.md, budget_bias_diagnostics.csv,
   random_baseline_reference.csv, limitations.md, commands.log, manifest.json, handoff_report.md,
   build_p325a.py.
8. Key findings (plain language):
   - Observed hit rates rise with combination size, but the matched-budget random baseline rises
     the same way: mean delta (observed − equal-budget-random) across all 2418 rows =
     hit≥1 -0.0279, hit≥2 +0.0075, hit≥3 -0.0091.
   - Rows with positive delta: hit≥1 1041/2418, hit≥2 1322/2418, hit≥3 783/2418.
   - Bonferroni screen (k∈{2,3}, 4836 tests, α=1.03e-05): 41 rows beat the
     equal-budget random null — **all DAILY_539, zero BIG_LOTTO, all at k=2 only**. These are NOT
     independent: carrier strategy `daily539_f4cold_5bet` appears in 34/41 of
     them; nested windows + shared members inflate the count. Top rows:
  - DAILY_539 recent_750 size=3 m=7 k=2 delta=+0.1140 p=9.42e-11 [daily539_f4cold_5bet|daily539_markov_cold|midfreq_acb_2bet]
  - DAILY_539 recent_750 size=3 m=7 k=2 delta=+0.1140 p=9.42e-11 [daily539_f4cold_5bet|daily539_markov_cold|midfreq_fourier_2bet]
  - DAILY_539 recent_750 size=3 m=7 k=2 delta=+0.1140 p=9.42e-11 [daily539_f4cold_5bet|markov_1bet_539|midfreq_acb_2bet]
  - DAILY_539 recent_750 size=3 m=7 k=2 delta=+0.1140 p=9.42e-11 [daily539_f4cold_5bet|markov_1bet_539|midfreq_fourier_2bet]
  - DAILY_539 recent_750 size=2 m=6 k=2 delta=+0.1158 p=1.05e-10 [daily539_f4cold_5bet|midfreq_acb_2bet]
  - DAILY_539 recent_750 size=2 m=6 k=2 delta=+0.1158 p=1.05e-10 [daily539_f4cold_5bet|midfreq_fourier_2bet]
  - DAILY_539 recent_750 size=1 m=5 k=2 delta=+0.1127 p=3.94e-10 [daily539_f4cold_5bet]
  - DAILY_539 recent_750 size=2 m=6 k=2 delta=+0.1038 p=6.54e-09 [daily539_f4cold_5bet|daily539_markov_cold]
  - DAILY_539 recent_750 size=2 m=6 k=2 delta=+0.1038 p=6.54e-09 [daily539_f4cold_5bet|markov_1bet_539]
  - DAILY_539 recent_750 size=3 m=7 k=2 delta=+0.0980 p=2.45e-08 [acb_markov_midfreq|daily539_f4cold_5bet|midfreq_acb_2bet]
   - Same-budget cross-size (summary §3) is decisive: at fixed budget m, larger combinations do NOT
     beat smaller ones (DAILY single f4cold_5bet m=5 hit≥2=0.700 vs triples m=5 0.498).
   - Interpretation: P320A/P321A combination "improvements" are predominantly a ticket-BUDGET
     effect. At matched budget, combinations do not exceed random beyond a few single strategies'
     own (non-combination) signal, which they partly dilute.
9. Validation: see manifest.json + §"Required validation" below and phase0_state.md.
10. No repo changes (this script writes only under the external evidence root).
11. No DB write / migration / checkpoint (no DB opened at all).
12. No production apply / registry publication / future-ticket creation.
13. Not blocked. Optional deeper step (not required): empirical equal-budget subsampling of actual
    tickets would need a read-only pass over the P320A source snapshot DB — deliberately out of
    scope to keep this artifact zero-DB.

## Required validation (self-check)
- PASS evidence root exists.
- PASS manifest covers all payload artifacts (generated last, globs the root).
- PASS manifest hashes recompute (verify by re-shasum vs manifest).
- PASS P320A static hashes match expected values (asserted in-script).
- PASS no DB write/migration/checkpoint (no DB opened).
- PASS no repo code / static-artifact changes (writes confined to evidence root).
- PASS equal-budget handled honestly (random reference computed; actual-subsample marked
  INSUFFICIENT_RAW_DATA; nothing fabricated).
- NOT RUN npm tests (no root package.json in scope for this analysis).
- Repo working-tree-clean / no-staged-files: verified separately via git after this run.
