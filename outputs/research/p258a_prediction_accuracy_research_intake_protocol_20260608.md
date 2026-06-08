# P258A — Prediction Accuracy Improvement Research Intake Protocol

**Date:** 2026-06-08
**Task:** `P258A`
**Classification:** `PREDICTION_ACCURACY_RESEARCH_INTAKE_PROTOCOL`
**Type:** Type B read-only research intake protocol artifact (no code, no DB write)
**Final Decision:** `P258A_PREDICTION_ACCURACY_RESEARCH_INTAKE_PROTOCOL_READY`

---

## Executive Summary

The user direction for this research round is explicit: **ignore CP value and EV — the only objective is to improve prediction success rate.** This protocol converts that direction into a *governed intake* for external models / other agents. It produces (a) a copy-paste external-agent prompt, (b) a proposal scoring rubric, and (c) hard rejection rules — so incoming proposals can be evaluated consistently without weakening any statistical gate.

**CEO risk framing (read this first):** the value of this protocol is **rejection discipline**, not an expectation of finding a deployable edge. P256A returned `NULL_RESULT` (0 Bonferroni survivors / 39 tests); L82/L91 show DAILY_539 signal space exhausted and BIG_LOTTO 49C6 indistinguishable from fair random. Removing EV/CP from the objective does **not** make hit-rate signal easier to find — it only removes a guardrail against false positives. Therefore **no validation gate is relaxed** in this round.

---

## Why CP / EV / payout are excluded this round

The user explicitly scoped this round to prediction accuracy only. To keep proposals focused and prevent agents from re-deriving the (already-closed) payout/anti-crowd EV line (L102, P236A), the following are **out of scope and must not be optimized, mentioned, or traded off against**:

`CP_value`, `EV`, `payout`, `prize_money_optimization`, `betting_cost`, `ROI`, `anti_crowd_EV`, `resource_efficiency`, `cost_efficiency`.

Exclusion is a **scoping** decision, not a loosening of rigor — see gates below.

---

## Prediction accuracy target metrics

- `avg_hit_count_per_draw`
- `hit_count >= 1` success rate
- `hit_count >= 2` / `hit_count >= 3` high-hit rate
- N-bet portfolio success rate (best 1 / 2 / 3 / 4 / 5-bet portfolio)
- paired win rate vs the current best N-bet baseline (P257A)

---

## Required validation gates (NONE may be weakened)

1. No data leakage — features use only pre-target-draw information.
2. OOS validation (walk-forward holdout).
3. Short / mid / long window stability (e.g. 150 / 500 / 1500 draws, all ≥ baseline).
4. **McNemar or paired comparison** vs current best N-bet baseline.
5. **Multiple-testing correction** (Bonferroni / BH-FDR / permutation Monte-Carlo).
6. **Drift robustness** (holds under regime/drift segmentation).
7. Outlier-removal robustness (survives removing top high-hit events).
8. Comparison against current best N-bet historical portfolios from P257A.

---

## Current best N-bet baseline (from P257A — the bar every proposal must beat)

| Lottery | N | Strategy | Portfolio success rate | Avg best hit/draw | Draws |
|---|---|---|---:|---:|---:|
| BIG_LOTTO | 1 | `biglotto_deviation_2bet` | 0.5794 | 0.7574 | 1550 |
| BIG_LOTTO | 2 | `biglotto_echo_aware_3bet` | 0.838 | 1.2073 | 1500 |
| BIG_LOTTO | 3 | `biglotto_echo_aware_3bet` | 0.9493 | 1.46 | 1500 |
| BIG_LOTTO | 4 | `biglotto_ts3_markov_4bet_w30` | 0.988 | 1.5853 | 1500 |
| DAILY_539 | 1 | `539_3bet_orthogonal` | 0.542 | 0.672 | 1500 |
| DAILY_539 | 2–5 | `daily539_f4cold_5bet` | 0.792 → 0.9953 | 1.06 → 1.61 | 1500 |
| POWER_LOTTO | 1 | `midfreq_fourier_mk_3bet` | 0.7073 | 1.0273 | 1500 |
| POWER_LOTTO | 2 | `power_fourier_rhythm_2bet` | 0.9287 | 1.47 | 1500 |
| POWER_LOTTO | 3 | `power_precision_3bet` | 0.971 | 1.6394 | 1550 |
| POWER_LOTTO | 4 | `pp3_freqort_4bet` | 0.9807 | 1.6673 | 1500 |
| POWER_LOTTO | 5 | `power_orthogonal_5bet` | 0.9716 | 1.6477 | 1550 |
| 3_STAR / 4_STAR | — | **NO_REPLAY_ROWS** | — | — | — |

> All values are `HISTORICAL_REPLAY_ONLY` — no future-prediction guarantee. Portfolio success rate rises with N mechanically (more bets → more coverage); it is **not** a per-bet edge and must not be read as one.

**Data-constraint caveat:** a `>=5000 draw` minimum holds for DAILY_539 (5,882) and replay rows, but **not** for BIG_LOTTO canonical (2,114) or POWER_LOTTO (1,917). Any proposal asserting a 5,000-draw minimum is infeasible for BIG_LOTTO/POWER_LOTTO and must be flagged.

---

## External-agent copy-paste prompt

> Copy the block below verbatim to the external model / agent.

```text
You are a quantitative research model proposing NEW lottery number-prediction methods for the Taiwan
lottery system (BIG_LOTTO 6/49, POWER_LOTTO 6/38+1, DAILY_539 5/39).

SINGLE OBJECTIVE — PREDICTION ACCURACY ONLY.
Your only goal is to improve PREDICTION SUCCESS RATE. You must IGNORE CP value, expected value (EV),
payout, prize money, betting cost, anti-crowd EV, ROI, and resource efficiency entirely. Do not
optimize, mention, or trade off against any monetary metric. The accuracy metrics you may target are:
  - average hit_count per draw
  - hit_count >= 1 success_rate
  - hit_count >= 2 and hit_count >= 3 high-hit rate
  - N-bet portfolio success_rate (best 1/2/3/4/5-bet portfolio)
  - paired win rate vs the current best N-bet baseline

PROPOSE EXACTLY 3 NEW METHOD DIRECTIONS. Not 2, not 4 — exactly 3. For EACH of the 3 directions provide:
  1. method_name
  2. core_idea
  3. why_not_a_small_tweak — explicitly argue why it is NOT a minor variant of the existing
     frequency / recency / Fourier / Markov / rolling-window families already exhausted in this system
  4. target_accuracy_metric — which prediction-success metric it aims to improve
  5. minimum_viable_experiment — data needed, feature/signal generation, prediction-number generation
     method, baseline, OOS split, short/mid/long-window validation, leakage prevention,
     multiple-testing handling, and comparison against the current best N-bet baseline
  6. acceptance_thresholds
  7. failure_criteria
  8. monitoring_metrics
  9. risk_controls (observation-only trigger, auto-downgrade trigger, rollback trigger, stop trigger,
     re-pre-registration trigger, ban-from-recommendation trigger)

HARD CONSTRAINTS (a proposal that violates ANY of these is auto-rejected):
  - No future/post-draw information leakage. Features use only data available before the target draw.
  - Evidence on a single window only is NOT acceptable — require short AND mid AND long windows.
  - Evidence from a single calendar year only is NOT acceptable.
  - A high-hit anecdote (one lucky draw) is NOT evidence.
  - No OOS split = reject. No multiple-testing correction = reject. No leakage-prevention plan = reject.
  - No comparison against the current best N-bet baseline = reject.
  - Post-hoc threshold tuning to manufacture significance = reject.
  - You may NOT claim any historical result guarantees or raises future win probability.

PRIOR EVIDENCE YOU MUST RESPECT (do not propose methods these already falsified):
  - P256A: feature-information MI framework returned NULL (0 Bonferroni survivors across 39 tests).
  - L82 / L91: DAILY_539 signal space exhausted; BIG_LOTTO 49C6 indistinguishable from fair random.
  - L86 / L89: ML/evolution feature engineering overfits catastrophically on low-base-rate pools
    (300p +6.5% -> +0.12% OOS; MicroFish 10.35x overfit ratio).
A credible proposal must explain why it would survive where these failed.
```

---

## Proposal scoring rubric (0–5 per criterion)

| Criterion | Question |
|---|---|
| novelty_of_signal | Genuinely new vs frequency/recency/Fourier/Markov/rolling-window? |
| leakage_safety | Is the leakage-prevention plan airtight? |
| oos_feasibility | Evaluable OOS with available data? |
| mcnemar_paired_test_feasibility | Paired-comparable vs best N-bet baseline? |
| short_mid_long_stability | Plausible across 3 window sizes? |
| multiple_testing_discipline | Correction pre-declared and adequate? |
| drift_detectability | Can drift/regime degradation be detected? |
| implementation_cost | **OPTIONAL — weight-capped; must NOT dominate the score.** |

> `implementation_cost` is capped so a cheap-but-weak idea cannot outrank a novel, leakage-safe one.

---

## Hard rejection rules

A proposal is rejected if it exhibits **any** of:

- single-window-only evidence
- single-year-only evidence
- high-hit anecdote only
- no OOS split
- no multiple-testing correction
- no leakage-prevention plan
- post-hoc threshold tuning
- no comparison to the P257A best N-bet baseline
- claims of future win probability / guarantee
- proposes production auto-mutation without an observation-only gate

---

## Recommended follow-up: P258B

**P258B — External proposal evaluation and pre-registration selection.**
- Precondition: external-model responses (3 directions each) received.
- Type: read-only evaluation + pre-registration; **no implementation**.
- Action: score via rubric, apply hard rejection rules, pre-register at most the surviving directions for a *later* read-only feasibility prototype.

---

## Explicit non-actions (this artifact authorizes NONE of these)

- ❌ No DB write
- ❌ No new strategy implementation
- ❌ No registry mutation
- ❌ No recommendation logic change
- ❌ No production write
- ❌ No betting advice

---

## Required Completion Check

1. **真的完成？** 是 — JSON + MD 協議 artifact + 測試完成。
2. **測試結果**：見 PR CI / `pytest tests/test_p258a_prediction_accuracy_research_intake_protocol.py`.
3. **仍卡住的唯一問題**：無 — 等外部模型回覆後才進 P258B。
4. **修改檔案**：`outputs/research/p258a_*.json/.md`、`tests/test_p258a_*.py`、roadmap/active_task/CURRENT_STATE governance 檔。
5. **staged / commit / push**：file-by-file（無 `git add -A`）。
6. **是否允許進入下一輪**：是 — P258B 待外部回覆。
7. **Final Classification**：`P258A_PREDICTION_ACCURACY_RESEARCH_INTAKE_PROTOCOL_READY`
