# UX / Decision Quality Research — 2026-04-29

Objective: improve orchestration UI decision quality: active/shadow dashboard, drift alert, strategy confidence explanation, CTO daily summary.

---

## 1. New Hypothesis

Hypothesis: "Operational Telemetry Fusion" — combining orchestrator telemetry (tick events / agent_task_runs outcomes, worker_metrics, planner_dedupe_state) with live strategy signals (strategy_live_state.drift_score, ewma_live_roi, consecutive_losses, task_outcomes.confidence_score) and explicit provider/queue signals (COPILOT_DAEMON_*, WORKER_HIGH_CPU_LOAD, PROVIDER_FALLBACK counts) enables earlier, higher-precision automated drift alerts and an explainable per-strategy confidence decomposition exposed in the UI.

Why this is genuinely new: this is not a strategy-family hypothesis (no frequency/Fourier/Markov or anti_correlation/freq_rev/shadow_gap/cold_lowfreq mechanics). It focuses on orchestration-level telemetry fusion (system-run events + live-outcome stats + planner confidence snapshots) to improve decisioning — i.e., meta-signals about execution health and live-vs-backtest divergence rather than new predictive features for draws. This differs from saturated families because it does not modify prediction algorithms or numerical feature families; it treats operational signals and live-outcome drift as first-class inputs to UI alerts and explanations.

---

## 2. Why This Could Improve Success Rate

Causal/statistical mechanism:
- Live strategy performance (ewma_live_roi, consecutive_losses, drift_score) captures real-time divergence from backtest baselines.
- Operational events (provider rate-limit, runtime fallback, high CPU, heartbeat gaps) correlate with transient artificial edge changes (e.g., partial outputs, timeouts) that can cause apparent but non-robust edge swings.
- Fusing these signals reduces false positives: require concurrent evidence (statistical drift + increased provider_fallback or worker runtime anomalies) before raising an actionable alert.
- Explainability: decompose confidence change into orthogonal contributors (data sufficiency, drift magnitude, provider stability, execution latency) so CTO sees which factor drove the score change.

Statistically: use time-series drift detection (CUSUM / EWMA slope) on per-strategy ROI + permutation test on recent windows to confirm non-random deviation before surfacing high-severity UI alerts.

---

## 3. Required Data

Existing DB tables/columns (orchestrator DB):
- agent_task_runs: runner, tick_at, outcome, request_id, task_id, message, duration_ms, epoch_id
- agent_tasks: id, slot_key, title, status, created_at, completed_at, confidence_snapshot, value_score, dedupe_key, regime_state
- strategy_live_state: strategy_id, backtest_edge, ewma_live_roi, ewma_accuracy, drift_score, consecutive_losses, sample_count, updated_at
- live_strategy_outcomes: strategy_id, draw_id, recorded_at, roi, match_count, pnl
- task_outcomes: task_id, task_type, edge_score, confidence_score, recorded_at
- worker_metrics: sampled_at, worker_type, cpu_pct, queued_count, avg_latency_s, slot_decision_reason
- planner_dedupe_state: dedupe_key, last_confidence, last_emitted_at
- classifier_calibration_log: classified_at, state, confidence_score, features_json
- cto_review_runs / cto_intent_signals: for mapping CTO actions to alerts

External data / artifacts required (if unavailable, note):
- Frontend mapping of event types → currently visualized badges/views (UI instrumentation file) — missing mapping often absent
- CT O daily summary template and required fields (cto review expectations)

Generated features (to be computed for validation):
- event_type frequency per runner (24h/48h), provider_fallback_count per strategy (24h)
- heartbeat_gap_ms distribution per worker
- drift_trend_slope: slope of ewma_live_roi over last N draws
- confidence_delta = current_confidence_snapshot - last_confidence
- composite_alert_score = weighted sum (normalized drift magnitude, provider_fallback_rate, heartbeat_gap_zscore)

Data known to be missing / not yet instrumented:
- explicit mapping of low-level outcomes (e.g., WORKER_SKIP_IDLE_NO_TASK) to UI elements — partial
- user click / acknowledgement logs for alerts (to measure human reaction)
- per-strategy provider_fallback counts currently not aggregated in a single view

---

## 4. Minimal Validation Plan

| Field | Value |
|---|---|
| sample_size | 150 draws (or 150 live evaluation windows where strategy had bets) |
| test_window | last 500p (short/medium/long windows: 150/500/1500 used for robustness checks) |
| baseline | current best operational baseline: no fused telemetry (existing alerting = simple drift_score threshold) |
| statistical_test | permutation test on ROI window (p), plus CUSUM / EWMA slope significance for drift; McNemar test when comparing binary alert decisions vs baseline (alert/no-alert) on matched periods |
| expected_output | composite_alert precision ↑ (e.g., precision improvement vs baseline by measurable margin) and early-warning lead time > 1 draw on average; programmatic target: edge_150 > 0.03 for validated strategy signals when not affected by provider/worker anomalies (secondary) |

Notes: sample_size uses draws where strategy produced live predictions; random seed = 42 for sampling reproducibility. Maintain temporal ordering for permutation tests (shuffle windows, not labels across time).

---

## 5. Risk / Overfit Check

- sample_size_risk: MEDIUM — live per-draw outcomes are sparse and noisy; 150 draws may be borderline for small-effect detection. Mitigation: use EWMA and multi-window checks, aggregate across similar strategies where safe.

- multiple_testing_risk: HIGH — many telemetry features (event types, windows, weights) create multiple hypotheses. Mitigation: pre-register primary composite rule, limit exploratory sub-tests, apply Bonferroni / permutation-based family-wise corrections.

- data_leakage_risk: LOW → MEDIUM — risk if features include future-derived fields or if validation windows leak future live outcomes. Mitigation: enforce temporal slicing (use only data up to t-1 when evaluating draw t), reuse tools/verify_no_data_leakage.py.

- overfit_risk: MEDIUM — tuning composite weights on historical episodes can overfit to past provider failure modes. Mitigation: hold-out out-of-time window, require walk-forward OOS pass, and avoid over-tuning weights; keep rule simple (2-3 signals) initially.

---

## 6. Decision

WORTH_VALIDATION

Rationale: signals are operational and orthogonal to saturated strategy families; there is plausible causal linkage (provider/worker anomalies → spurious edge swings). The cost of a focused validation (diagnostic + limited evaluation) is small and the potential to reduce false promotions / false alarms and to make CTO decisioning explainable is high. Constraints (no changes to production endpoints, no strategy replacements) respected.

---

## 7. Next Task If Worth Validation — Validation Task Prompt (complete)

Title: "UX Drift Alert & Confidence-Explanation Diagnostic + Validation"

Description / goal: produce reproducible diagnostics and a validation run that measures whether fused operational+live signals (composite_alert_score) reduce false-positive drift alerts and provide a decomposed confidence explanation for CTO.

Deliverables:
1. scripts/ux_drift_audit.py — diagnostic script (read-only on orchestrator DB) that:
   - enumerates unique agent_task_runs.outcome values in last 24h/7d and maps them to UI elements (present a CSV mapping)
   - computes per-strategy time series for: ewma_live_roi (window 150), drift_score, consecutive_losses, provider_fallback_count (24h), heartbeat_gap_ms stats, worker_cpu_pct EWMA
   - computes composite_alert_score = normalized(drift_magnitude) * 0.6 + normalized(provider_fallback_rate)*0.25 + normalized(heartbeat_gap_zscore)*0.15 (seed=42)
   - emits a labeled CSV of candidate alerts (timestamp, strategy_id, composite_alert_score, contributors)
2. notebook or report JSON summarizing test-run: compare baseline alerts (drift_score-only threshold) vs composite rule across sample_size=150 draws (last 500p window) and produce:
   - precision/recall of alerts vs confirmed live failure episodes (manual tag or objective ROI<0 across 3 draws)
   - McNemar test comparing binary alert decisions (alpha=0.05)
   - permutation p-value on ROI window deviation (preserve time ordering in permutations)
3. UX content: wireframe text for UI explanation panel:
   - one-line summary: e.g., "Confidence fell from 0.82 → 0.61 (−0.21)";
   - contributors: list top 3 contributors with short reasons and supporting metric/value (e.g., "drift_score ↑ 0.34; provider_fallback_count = 3 in 24h; last_output_gap = 420s").
4. CTO daily summary template (JSON) including fields: date, strategies_flagged, top causes (counts), suggested action (watch / immediate review), and links to task ids.

Validation plan (close-loop):
- sample_size: 150 draws where strategy had predictions (last 500p test window)
- baseline: drift_score-only threshold currently used
- statistical_test: McNemar for alerts (paired), permutation test for ROI deviation; report p-values and effect sizes
- success criteria: statistically significant reduction in false-alert rate (Bonferroni-corrected p<0.05) or improved precision with no material loss in recall; clear decomposition fields available in UI payload.

Operational constraints (must be enforced in task):
- Do NOT modify any production endpoints; this is read-only diagnostic and report generation.
- seed=42 for sampling and deterministic composite weights
- Do NOT touch lottery_api/data/lottery_v2.db or strategy_states config files
- Do NOT retrain or re-run any saturated strategy family

Execution instructions (for implementer):
- Use orchestrator DB path (orchestrator/runtime/agent_orchestrator/orchestrator.db)
- Implement temporal isolation: when scoring alerts for draw t, use only data timestamped ≤ draw t-1
- Produce outputs under outputs/ux_drift_audit/ with CSVs and report JSON
- Include a small README with commands to reproduce (python3 scripts/ux_drift_audit.py --since 2026-01-01 --limit 500)

Handoff notes after validation:
- If results pass success criteria, propose a Planner tick to schedule a controlled shadow alerting experiment (notify CTO, two-week watch, require CTO review before any promotion of automation).
- If WATCH_ONLY, add summary entry to wiki/exploration_watchlist.md (if present) with tags.
- If REJECT, write rejection reason to rejected/ux_decision_quality_research_2026-04-29.json for future avoidance.


---

Author: automated UX research tick (seed=42). Report generated per Task Contract; do not modify production endpoints. 


