# Reject Rule Hypothesis — 2026-04-29

This report proposes a reject-rule hypothesis to identify "fake edge" candidates that pass short-window gates but decay in live outcomes. It follows wiki routing and memory lessons; does not touch active strategy state nor lottery_v2.db.

## 1. New Hypothesis
Hypothesis: Candidates exhibiting large short-window uplift (edge_150) but extreme negative/near-zero long-window edge (edge_1500) combined with (A) very low historical support count (few distinct historical seeds contributing wins), (B) high model/feature complexity (many tunable params relative to training sample), and (C) non-persistent rolling-window wins (spike then drop) are false positives—i.e., fake-edge patterns likely due to overfitting or narrow-sample artifacts and should be rejected or blacklisted.

How this differs from saturated families:
- Not a frequency/Fourier/Markov family hypothesis (explicitly avoided).
- Differs from anti_correlation, freq_rev, shadow_gap, cold_lowfreq by focusing on structural instability and tuning-ratio metrics (edge volatility, support sparsity, parameter-to-sample ratio, rolling persistence) rather than specific signal forms (anti-corr patterns, frequency reversals, gap-shadow behavior, or cold low-frequency counts).
- This hypothesis targets candidates that appear statistically strong in short windows due to high variance or tuning, not due to identifiable game-level structural signals covered by saturated families.

## 2. Why This Could Improve Success Rate
Causal/statistical mechanism:
- Overfit produces high apparent short-window edge because many parameters / conditional branches exploit idiosyncratic noise. Those features have low generalization and fail as more draws arrive.
- Sparse-support signals (few historical seeds) are brittle; a few future outcomes remove apparent edge quickly.
- Measuring the short-vs-long edge gap (Δ = edge_150 − edge_1500) quantifies instability; large Δ indicates likely non-stationary or overfit-driven gains.
- Combining Δ with support_count and complexity normalizes for sample size and prevents penalizing legitimately rare but stable signals.

No ROI claims are made; mechanism explains why rejecting such candidates avoids deployable false positives and reduces validation burden.

## 3. Required Data
Existing / accessible sources (read-only for this research):
- draw history: `data/draw_history.json` or DB table `draws` (cols: draw_id, date, numbers[]). If DB only: `lottery_api/data/lottery_v2.db` (DO NOT MODIFY).
- strategy/candidate backtest artifacts: `strategies/{name}/backtest_report.md` and `strategies/{name}/sim_result.json` (contain per-window edges: edge_150, edge_500, edge_1500; perm_p values; sharpe_*).
- runtime strategy summaries / state export: API field names referenced in wiki: `edge_300p`, `sharpe_300p`, `trend`, `alert` (used only for baseline comparisons).
- rejected records: `rejected/{strategy_name}.json` (contains failure reasons for past FAILED / FAILED_WEAK_EDGE tasks).
- validated set: `validated/` (to compute baseline edges for same lottery_type).

Generated features needed:
- edge_short (edge_150), edge_mid (edge_500), edge_long (edge_1500)
- delta_short_long = edge_short - edge_long
- support_count = number of distinct historical seed/contexts contributing winning occurrences (e.g., distinct start indices where candidate would have matched)
- complexity_score = features_count × tunable_params_count (from strategy metadata)
- persistence_index = fraction of rolling slices (e.g., rolling 150-period slices in last 1500p) where edge > 0
- perm_p_short, perm_p_long (permutation p-values)

Data known missing or to verify:
- A canonical `support_count` extractor may not exist — need to compute from backtester logs / sim_result.json.
- Tunable parameter counts may not be explicitly recorded; may need to infer from strategy YAML or feature definitions.

Constraints reminder: do not modify `lottery_api/data/lottery_v2.db` or strategy_states files.

## 4. Minimal Validation Plan
| Field | Value |
|---|---|
| sample_size | 150 most recent draws (for paired short-window diagnostic) |
| test_window | last 1500p (compute short/mid/long aggregates: 150 / 500 / 1500) |
| baseline | median edge_long of validated strategies for same lottery_type in last 1500p (or current validated baseline edge_long) |
| statistical_test | permutation test for temporal structure (short & long), paired McNemar vs incumbent for binary hit success (where applicable), bootstrap CI for delta_short_long; report perm p-values and Cohen's d |
| expected_output | candidate passes diagnostic if: edge_150 > baseline + 0.02 AND perm_p_short < 0.05 AND persistence_index >= 0.6. Primary reject rule: delta_short_long > 0.04 OR support_count < 5 OR complexity_score / sample_size > 0.1 (heuristic thresholds — tune during validation). |

Notes: sample_size 150 ensures recent live sensitivity; test_window 1500p preserves long-term context required to compute edge_long.

## 5. Risk / Overfit Check
- sample_size_risk: MEDIUM — 150 draws give sensitivity to recent decay but may be too small for rare-event stabilization; mitigated by also using 1500p long-window for context.
- multiple_testing_risk: HIGH — many candidates are scanned; correct for multiplicity (e.g., Benjamini-Hochberg FDR on perm p-values) and report adjusted p-values.
- data_leakage_risk: LOW-MEDIUM — risk if support_count or feature extraction inadvertently uses future labels; enforce strict temporal slicing (see validation_gates: Temporal Isolation) and use RollingBacktester utilities.
- overfit_risk: HIGH — the hypothesis explicitly targets overfit; rely on persistence_index, support_count, and complexity_score to detect overfitting. Prefer conservative reject thresholds and WORTH_VALIDATION before auto-reject.

## 6. Decision
WORTH_VALIDATION

Rationale: patterns of extreme short-vs-long edge gaps + low support and high complexity are plausible and actionable reject signals, but require controlled validation (permutation + McNemar + bootstrap) and multiplicity correction. The candidate rule can materially reduce false positives if validated.

## 7. Next Task If Worth Validation
Complete validation task prompt (seed=42). Run as a focused diagnostic (read-only) that outputs per-candidate diagnostics and an aggregate reject-rule performance summary.

Task prompt:
```
Title: Validate Reject-Rule Diagnostics (delta_short_long / support / complexity)
Seed: 42
Scope:
  - Candidate pool: all strategies/candidates that historically reached T1 or T2 but later recorded FAILED or FAILED_WEAK_EDGE in `rejected/` or whose live performance dropped > 2σ in monitoring logs.
  - Lotteries: apply per-lottery_type (BIG_LOTTO / DAILY_539 / POWER_LOTTO) separately.
Inputs (read-only):
  - strategies/*/sim_result.json and backtest_report.md (extract edge_150, edge_500, edge_1500, perm p-values)
  - rejected/*.json (past failure labels)
  - validated/ (to compute baseline edges)
  - data/draw_history.json or DB read of draws table (no writes to lottery_v2.db)
Generated features to compute:
  - edge_short = edge_150; edge_long = edge_1500; delta_short_long
  - support_count (number of unique historical seed indices producing matches)
  - complexity_score (features_count × tunable_params_count)
  - persistence_index (fraction of rolling 150 slices in last 1500p with edge > 0)
Diagnostics per candidate:
  - table with edge_150/500/1500, perm_p_short/long, delta_short_long, support_count, complexity_score, persistence_index
  - bootstrap 95% CI for edge_150 and delta_short_long (n_boot=1000)
  - permutation test p (n_perm=2000) for short and long windows
  - paired McNemar test result vs incumbent where applicable (n>=30 paired opportunities)
Evaluation:
  - Compute ROC-like curve for reject-rule vs known FAILED label (from rejected/*.json) using rules of form: (delta_short_long > t1) OR (support_count < s1) OR (complexity_score / sample_size > c1). Sweep thresholds to produce TPR/FPR and choose conservative threshold maximizing precision at recall >= 0.6.
  - Report multiplicity-corrected p-values (BH FDR) across candidate tests.
Outputs (artifact paths):
  - JSON: outputs/reject_rule_diagnostics_2026-04-29.json (per-candidate diagnostics)
  - CSV: outputs/reject_rule_threshold_sweep_2026-04-29.csv
  - Markdown summary: outputs/reject_rule_validation_summary_2026-04-29.md (include recommended default thresholds and justification)
  - Plots: outputs/plots/{candidate_id}_diagnostic.png (delta over rolling windows)
Acceptance criteria:
  - Reject-rule achieves precision >= 0.75 on historical FAILED label at conservative thresholds and reduces candidate validation workload by >= 20% (heuristic; measured as fewer candidates passing initial automated gates).
  - All tests logged with temporal-slicing provenance and no writes to lottery_v2.db or strategy_states.
Notes / Constraints:
  - Enforce strict temporal isolation in all analysis code (use RollingBacktester utilities).
  - Do NOT modify any active strategy or strategy_live_state files.
  - Report any missing metadata (e.g., tunable_params_count) as blockers in the summary.
  - Use seed=42 for bootstrap/permutation reproducibility.
```

---

Produced by: research tick — uses wiki + memory routing; no DB writes. File: `research/reject_rule_hypothesis_2026-04-29.md`

References: wiki/system/validation_gates.md, wiki/system/stability_audit.md, wiki/system/feedback_loop.md, memory/lessons.md
