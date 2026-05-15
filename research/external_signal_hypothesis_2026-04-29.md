# External Signal Hypothesis Research — 2026-04-29

This report follows the Task Contract for EXPLORE-A. Seed=42.

## 1. New Hypothesis
Hypothesis: Exogenous market-like signals — jackpot carryover amount, ticket sell_amount (pool size), weekday/holiday, and month-end/start cycles — systematically change player purchase behavior and ticket composition, producing small but consistent conditional shifts in hit-probability for certain bet constructions. These signals are external (player/population-level) not internal to draw history; unlike saturated families (frequency, Fourier, Markov, anti_correlation, freq_rev, shadow_gap, cold_lowfreq), this hypothesis leverages exogenous covariates (economic/timing) that affect human selection bias and pool coverage rather than altering number-generation dynamics derived from past draws. This is therefore a genuinely new direction.

## 2. Why This Could Improve Success Rate
Causal/statistical mechanisms:
- Jackpot carryover increases casual participation and tends to concentrate choices on culturally-preferred or rounded numbers, altering the distribution of tickets (more clustering), which changes conditional coverage probability across number-sets.
- Higher sell_amount (larger pool) increases the chance of duplicate tickets on popular combinations but also changes relative probability mass over rare combinations — both affect expected payout per unique bet.
- Weekday/holiday and month-start/end map to demographic shifts (commuter vs leisure players, payday cycles) altering popular-number preferences and bet-size mix.
Together, these change the conditional probability P(ticket covers winning combination | external_signal) versus unconditional P. If certain conditional states increase true coverage of targeted bet-structures, weighting by these signals can produce marginal edge. Note: no ROI claim — empirical validation required.

## 3. Required Data
Existing DB (verified): lottery_api/data/lottery_v2.db contains a `draws` table with columns including:
- id, draw, date, lottery_type, numbers, special, created_at
- jackpot_amount (REAL, may be NULL)
- sell_amount (REAL, may be NULL)
- total_amount (REAL, may be NULL)

Other relevant tables: prediction_runs, prediction_items, prediction_results, snapshot_schedule, review_sessions (schemas inspected).

External data needed (likely missing or partial):
- Official holiday calendar per jurisdiction (date-level, boolean holiday, holiday_name).
- Payday calendar or municipal pay-cycle proxy (if available) — otherwise use month-end / first-3-days as surrogate.
- If jackpot_amount or sell_amount are NULL for some draws, external scrape of published draw summaries (lottery operator site) to fill missing values.

Generated features to produce:
- weekday (Mon..Sun) extracted from draws.date
- is_month_end_three (last 3 calendar days of month), is_month_start_three (first 3 days)
- days_since_payday (if payday calendar available) or is_payday_week
- jackpot_bucket (quantiles, e.g., low/med/high top-10% carryover)
- sell_amount_bucket (quantiles)
- holiday_before_after flags (t-1, t+1 around holiday)

Data known missing or to verify:
- Complete holiday annotations
- Completeness of jackpot_amount and sell_amount fields (some rows may be NULL)

## 4. Minimal Validation Plan
| Field | Value |
|---|---|
| sample_size | 150 draws (primary), supplement with 500 draws for robustness checks |
| test_window | last 500p for primary diagnostics; short window: last 150p; long window: last 1500p for stability if available |
| baseline | current best edge for each game (use existing `edge_150` / validated benchmark from strategy catalog) — if no single baseline, use random-weighted baseline / incumbent predictor |
| statistical_test | Permutation test for edge (shuffle external signal labels across draws) + McNemar for paired hypothesis vs incumbent; report p-values and effect sizes (Cohen's d) |
| expected_output | Example success criterion: conditional edge_150 (when jackpot_bucket=high) > baseline_edge_150 by ≥ 0.02 with permutation p < 0.05. Produce stability across 150/500 windows.

Minimal experiment steps:
1. Extract draws + jackpot_amount + sell_amount + date for target game (e.g., DAILY_539). Seed=42 used for any sampling.
2. Feature-engineer weekday, month-start/end, holiday flags, quantile buckets.
3. For each external-state (e.g., jackpot_high, weekday=Sun, month_end3), compute empirical edge (edge_150) for a small set of lightweight selectors: e.g., anti-crowd weighting of top-k popular numbers vs baseline selector used in incumbents (but do NOT create new frequency/Fourier/Markov variants).
4. Run permutation: shuffle external-state labels across draws 2000 times to get null distribution of edges. Run McNemar to compare binary hit outcomes paired per-draw where applicable.
5. Report whether any external-state passes both effect-size and p-value gates across 150/500 windows.

## 5. Risk / Overfit Check
- sample_size_risk: MEDIUM — game-level variance is high; 150 draws gives limited power but is standard for rapid triage. Use 500/1500 for stability checks.
- multiple_testing_risk: HIGH — many external states (weekday×holiday×jackpot_bucket) produce multiplicity. Mitigation: pre-register a small set of primary contrasts (e.g., jackpot_high vs others, month_end3 vs rest, holiday±1) and correct with Benjamini-Hochberg / Bonferroni for exploratory checks.
- data_leakage_risk: LOW — plan uses only past draws and external signals tied to draw date; ensure permutation shuffles labels across time blocks, and that feature engineering uses only information available before target draw. Use tools/verify_no_data_leakage.py if integrating predictors.
- overfit_risk: MEDIUM — risk of curve-fitting to rare jackpot spikes. Mitigation: require stability across 150/500/1500 windows and out-of-time walk-forward slices; hold an independent OOS block (e.g., final 150 draws) for McNemar.

## 6. Decision
WORTH_VALIDATION

Rationale: DB already contains jackpot_amount and sell_amount fields, and the hypothesized mechanisms (player behavior shifts driven by exogenous signals) are orthogonal to saturated internal-number families. The presence of usable columns reduces data acquisition friction and supports a focused validation plan. Multiplicity and sample-size issues exist but are manageable with pre-registration, permutation tests, and multi-window stability gates.

## 7. Next Task If Worth Validation — Validation Task Prompt
Task: Validate external-signal conditional edges for DAILY_539, POWER_LOTTO, and BIG_LOTTO using draws in lottery_v2.db.

Requirements / Constraints (must include):
- Do not modify lottery_api/data/lottery_v2.db.
- Do not add frequency/Fourier/Markov variants or re-run saturated strategy families.
- Seed=42 for any sampling or split.

Inputs:
- DB: /lottery_api/data/lottery_v2.db (read-only)
- External holiday calendar CSV (if not available, generate holiday flags only for major public holidays — record missingness)

Steps (detailed):
1. Extract from `draws` where lottery_type in ("DAILY_539","POWER_LOTTO","BIG_LOTTO"): fields draw, date, numbers, jackpot_amount, sell_amount.
2. Derive features: weekday, is_month_end3, is_month_start3, jackpot_qtile (low/med/high defined by calendar-year quantiles), sell_qtile, holiday_flag (t, t-1, t+1).
3. Define primary contrasts (pre-registered):
   - jackpot_high (top 10%) vs others
   - month_end3 vs rest
   - holiday_day vs non-holiday
   - weekend (Sat/Sun) vs weekday
4. For each contrast and each game, compute simple conditional edge: compare incumbent baseline predictor edge_150 (use incumbent selector from prediction_runs / prediction_results if available — otherwise use random baseline) to conditional edge computed by filtering draws to the given state and computing historical hit rates for the same bet-selection logic used by the incumbent. Avoid creating new complex selectors; reuse lightweight weighting functions.
5. Statistical tests: permutation (shuffle state labels 2000 times) and McNemar (paired per-draw where possible). Adjust p-values for multiple testing (Benjamini-Hochberg). Report effect sizes and 95% CI (bootstrap 1000 resamples).
6. Stability: run across windows 150 / 500 / 1500 (where available). If conditional edge passes p<0.05 and effect ≥ 0.02 across at least two windows and holds in an OOS final-150 McNemar, mark as candidate for deeper validation (T1_MC_PASS).

Deliverables:
- Script: research/external_signal_diag_2026-04-29.py (read-only outputs; do not write DB). The script must be self-contained, use seed=42, and output CSVs: research/external_signal_summary_{game}.csv and a short JSON summary research/external_signal_decision.json containing pass/fail per contrast.
- Report: research/external_signal_hypothesis_2026-04-29.md (this file) — update only after validation results.
- Acceptance: A result JSON indicates which contrasts (if any) meet pre-registered gates and includes p-values, effect sizes, and per-window stability status.

If any contrast passes the gates, schedule a Planner tick for a full validation task (three-window backtest, McNemar vs incumbent, and CTO review) and record candidate in `provisional/` per governance.

---

Notes & Follow-ups:
- If Decision=WATCH_ONLY, record entry in wiki/exploration_watchlist.md; if REJECT, produce a rejection note for `memory/lessons.md`. (This run chose WORTH_VALIDATION.)
- Avoid over-claiming ROI; this task only produces validation evidence to elevate to T1/T2 per validation_gates.


*End of report.*

## 8. Validation run results (2026-04-29)
- Script executed: research/external_signal_diag_2026-04-29.py (seed=42). Outputs produced under research/: external_signal_summary_{game}.csv and external_signal_decision.json.
- Holidays source: external CSV missing (holidays_missing = true). Fallback holiday flags used (major holidays only); missingness recorded in outputs.
- Summary verdict: No pre-registered contrast met the pre-registered gates. For all three games (DAILY_539, POWER_LOTTO, BIG_LOTTO) the primary contrasts (jackpot_high, month_end3, holiday_day, weekend) failed to achieve permutation p < 0.05 and effect >= 0.02 across required windows, and no OOS McNemar passed. Decision: no candidate elevated (no T1_MC_PASS).
- Recommended follow-ups: provide a canonical holiday calendar CSV and re-run; consider richer selectors or alternative hit metrics if domain team requests deeper exploration.

Outputs generated:
- research/external_signal_decision.json
- research/external_signal_summary_DAILY_539.csv
- research/external_signal_summary_POWER_LOTTO.csv
- research/external_signal_summary_BIG_LOTTO.csv


