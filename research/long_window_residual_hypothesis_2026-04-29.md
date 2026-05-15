# EXPLORE-C Long Window Residual Research
# Forced Exploration Lane: long_window_residual

**Research ID**: EXPLORE-C (`long_window_residual`)
**Run date**: 2026-04-29
**Status**: HYPOTHESIS / VALIDATION PLAN ONLY — no strategy change, no active_strategy_state modification
**Prior lane**: EXPLORE-B (`constraint_postprocess`) — REJECT_FILTER_VALIDATION, WATCH_ARCHIVED

---

## 1. Executive Summary

**Final Decision: WORTH_VALIDATION**

Three games were reviewed. DAILY_539 has a confirmed long-window edge attenuation slope
(-1.53pp/1000 draws, from 2026-04-28 H_NEW_03) that has not yet been measured at 4000p or
full history (~5844p). This gap directly affects the Watchdog trigger condition
(`3000p edge ≤ +2.0pp → DEGRADED`). If attenuation continues at current rate, the
4000p edge is estimated at ~+2.97pp — inside the warning buffer.

BIG_LOTTO and POWER_LOTTO are both in maintenance / exhausted signal states. For those games,
only monitoring-level checks are proposed (no new research direction).

At least one hypothesis (H-LW-01) warrants a dedicated validation task: extend the existing
long-window script to 4000p and full history for DAILY_539.

---

## 2. Current Strategy State

| Game | Active Strategy | Shadow Strategy | Current Status | Known Issues |
|---|---|---|---|---|
| DAILY_539 | `acb_markov_midfreq_3bet` (3bet, edge_30p +9.50pp) | `midfreq_acb_2bet` (2bet) | WATCH_MAINTENANCE | Monotonic edge attenuation (-1.53pp/1000); 4000p not validated; watchdog trigger at 3000p ≤ +2.0pp |
| BIG_LOTTO | `p1_dev_sum5bet` (5bet, edge_30p +4.373%) | — (no active shadow) | MAINTENANCE — signal space EXHAUSTED (L90, L91) | 49C6 dilutes all frequency signals; 2129 total draws; full-history residual never formally measured |
| POWER_LOTTO | `pp3_freqort_4bet` (4bet, +3.28%) | `orthogonal_5bet` (5bet, +2.94%) | MONITOR_MODE — signal exhausted 2026-04-23 | 1905 total draws; shadow validated only to 1500p; long-window consistency across full 1905p MISSING |

---

## 3. Existing Long Window Evidence

| Game | 150p | 500p | 1500p | 2500p | 3000p | 4000p | Full History | Evidence Source |
|---|---|---|---|---|---|---|---|---|
| DAILY_539 | +9.50pp ✓ | +7.30pp ✓ | +6.70pp ✓ | +5.10pp ✓ | +4.50pp ✓ | ❌ MISSING | ❌ MISSING (5844p) | `research/daily539_long_window_validation_report_20260428.md` |
| BIG_LOTTO | ✓ (stage0 + 1500p) | ✓ | ✓ (L90/L91 exhaustion) | ❌ INFEASIBLE (2129 total < 2500) | ❌ INFEASIBLE | ❌ INFEASIBLE | ❌ MISSING (2129p) | `analysis/results/signal_exhaustion_audit_20260423.md` |
| POWER_LOTTO | ✓ (150p OOS all candidates) | ✓ | ✓ (1500p standard) | ❌ INFEASIBLE (1905 total < 2500) | ❌ INFEASIBLE | ❌ INFEASIBLE | ❌ MISSING (1905p) | `analysis/results/power_watch_downgrade_decision_20260423.json` |

**Key observations:**

- DAILY_539: 4000p and full-history (5844p) are the only actionable missing windows.
  These are feasible and directly relevant to the Watchdog condition.
- BIG_LOTTO: 2500p / 3000p / 4000p are infeasible (total history = 2129 draws).
  Only full-history (2129p) is a meaningful new window.
- POWER_LOTTO: 2500p+ infeasible (total = 1905 draws).
  Full-history (1905p) is marginally useful but only 27% wider than 1500p.

---

## 4. New Long Window Residual Hypotheses

### H-LW-01 — DAILY_539 4000p + Full-History Edge Validation

| Field | Value |
|---|---|
| **ID** | H-LW-01 |
| **Game** | DAILY_539 |
| **Hypothesis** | The active strategy (`acb_markov_midfreq_3bet`) retains positive edge at 4000p and full-history (5844p), confirming the attenuation slope is stable and the Watchdog threshold (+2.0pp) is not yet breached. |
| **Why it might affect success rate** | If edge at 4000p drops below +2.0pp, the Watchdog triggers a mandatory CTO review and potential strategy re-evaluation. The current slope (-1.53pp/1000) extrapolates to ~+2.97pp at 4000p — within 1pp of the alarm threshold. Not measuring this creates an unmonitored risk window. |
| **Data needed** | DAILY_539 draws (all 5844, read-only from DB). No new data required. |
| **Minimal validation method** | Extend `research/daily539_long_window_validation_20260428.py` with window steps [4000, 5000, 5844]. Report hit rate, edge (pp), bootstrap CI, Z-score. Compare slope at 4000p vs extrapolated slope. No permutation needed — this is monitoring, not a new strategy claim. |
| **Risk** | Low. Read-only. No cherry-picking: both 4000p and full-history are pre-specified. Risk of over-indexing on single slope estimate is mitigated by reporting CI. |
| **Decision** | **WORTH_VALIDATION** |

---

### H-LW-02 — DAILY_539 Rolling 500p Edge Trend (Step = 200 draws)

| Field | Value |
|---|---|
| **ID** | H-LW-02 |
| **Game** | DAILY_539 |
| **Hypothesis** | The edge attenuation in DAILY_539 is a smooth monotonic decay rather than a regime shift or sampling artifact. Rolling 500p windows stepped every 200 draws will reveal whether the decline is consistent across time or shows a discrete structural break. |
| **Why it might affect success rate** | If the decay is a regime shift (one or more discrete drops), the strategy was better calibrated to pre-shift data. If it is smooth, the current strategy remains valid and the attenuation is natural signal dilution from an expanding draw pool. These two interpretations lead to different follow-up actions. |
| **Data needed** | All DAILY_539 draws; same DB, read-only. |
| **Minimal validation method** | Compute draw-level hits for `acb_markov_midfreq_3bet` over rolling 500p windows, stepping by 200 draws. Plot edge over calendar time. Apply PELT or CUSUM (same method as H_NEW_01 changepoint) to the rolling edge series. Output: "smooth_decay" or "regime_shift" + window count. |
| **Risk** | Medium. Multiple windows = multiple comparisons. Risk: discovering a spurious "break" in a noisy rolling series. Mitigation: require CUSUM p < 0.01 (not 0.05) and at least 2 consecutive windows below break threshold before calling a regime shift. |
| **Decision** | **WORTH_VALIDATION** — can be bundled with H-LW-01 in a single validation task. |

---

### H-LW-03 — DAILY_539 Full-History Dilution Baseline (5844p)

| Field | Value |
|---|---|
| **ID** | H-LW-03 |
| **Game** | DAILY_539 |
| **Hypothesis** | When averaged across the full 5844-draw history (2007–2026), the active strategy edge approaches but remains above 0pp, confirming that the strategy was calibrated on a non-stationary draw process and that early draws dilute recent signal. |
| **Why it might affect success rate** | If full-history edge < +1.0pp, it confirms that training on full history is sub-optimal and that a recency-weighted or changepoint-trimmed training window may improve calibration. |
| **Data needed** | All DAILY_539 draws (included in H-LW-01 extension). |
| **Minimal validation method** | Already part of H-LW-01 (window = 5844p). No additional script required. |
| **Risk** | Low. Academic / informational result. Does not alone trigger strategy change — requires at least a McNemar and permutation validation if used to justify recency-trimming. |
| **Decision** | **WATCH_ONLY** — subsumes into H-LW-01; no separate validation task needed. |

---

### H-LW-04 — DAILY_539 Active vs Shadow Drift at 4000p

| Field | Value |
|---|---|
| **ID** | H-LW-04 |
| **Game** | DAILY_539 |
| **Hypothesis** | The lead of `acb_markov_midfreq_3bet` over `midfreq_acb_2bet` (shadow) narrows or reverses at 4000p. At 500p, shadow briefly outperformed (+8.66pp vs +7.30pp). At 3000p, active led (+4.50pp vs +3.23pp). If the active/shadow delta inverts at 4000p, it is an early signal that the 3-bet composition may be losing its multi-bet advantage. |
| **Why it might affect success rate** | If shadow consistently outperforms at longer windows, the 3-bet strategy may be allocating too many bets to a weaker signal component (Markov) that decays faster than the base ACB/MidFreq components. |
| **Data needed** | Same as H-LW-01. |
| **Minimal validation method** | Already covered by H-LW-01 script extension (compute all three strategies at 4000p and 5844p). |
| **Risk** | Low. Informational. Does not trigger strategy change unless active is formally shown INFERIOR via McNemar+permutation in a separate validation task. |
| **Decision** | **WATCH_ONLY** — bundle with H-LW-01 output, report as supplementary finding. |

---

### H-LW-05 — BIG_LOTTO Full-History Residual Audit (2129p)

| Field | Value |
|---|---|
| **ID** | H-LW-05 |
| **Game** | BIG_LOTTO |
| **Hypothesis** | Active strategies (`p1_dev_sum5bet`, `regime_2bet`) show positive edge at 1500p but approach or cross zero at full history (2129p). This would confirm L91 quantitatively: "49C6 statistically indistinguishable from random over all available draws." |
| **Why it might affect success rate** | If 2129p edge is ≤ 0pp, the strategy's positive edge at 1500p is purely a recency artifact — the strategy is fitted to a favorable recent regime and would be expected to regress. Justifies keeping BIG_LOTTO in pure maintenance. |
| **Data needed** | BIG_LOTTO draws (all 2129). Existing strategy evaluation scripts. |
| **Minimal validation method** | Compute `p1_dev_sum5bet` and `regime_2bet` hit rates at 1500p and 2129p (all draws). Report edge, bootstrap CI. No new strategy logic. |
| **Risk** | Low. Read-only. Risk of over-interpreting a slight positive at 2129p — mitigation: only report CI, do not claim any edge unless CI lower bound > 0. |
| **Decision** | **WATCH_ONLY** — confirms existing classification. No new research direction for BIG_LOTTO. |

---

### H-LW-06 — BIG_LOTTO Active Strategy Degradation Trajectory

| Field | Value |
|---|---|
| **ID** | H-LW-06 |
| **Game** | BIG_LOTTO |
| **Hypothesis** | The BIG_LOTTO active strategies show a consistent edge attenuation pattern similar to DAILY_539: positive at 150p, compressed at 500p, further compressed at 1500p. At full history (2129p), edge may fall near zero or negative. This pattern confirms monotonic decay and justifies the existing MAINTENANCE classification. |
| **Why it might affect success rate** | If BIG_LOTTO shows a similar attenuation slope to DAILY_539, it suggests the attenuation is a fundamental property of this lottery category, not a DAILY_539-specific issue. This informs how aggressively to monitor DAILY_539 attenuation. |
| **Data needed** | BIG_LOTTO draws; stage0 baseline results (already exist). |
| **Minimal validation method** | Assemble existing 150p / 500p / 1500p edge data from stage0 + exhaustion audit. Extend to 2129p. Report slope. No new script if data already reported — just assemble from existing results. |
| **Risk** | Very low. Monitoring only. |
| **Decision** | **WATCH_ONLY** — informational; confirms maintenance mode. |

---

### H-LW-07 — POWER_LOTTO Shadow Full-History Consistency (1905p)

| Field | Value |
|---|---|
| **ID** | H-LW-07 |
| **Game** | POWER_LOTTO |
| **Hypothesis** | The shadow strategy (`orthogonal_5bet`, +2.94% edge, Sharpe=0.072) was validated at 1500p. At full history (1905p), edge may compress but should remain positive if the signal is not purely a recent regime artifact. |
| **Why it might affect success rate** | Shadow strategy is the fallback if active degrades. If shadow's 1905p edge is < +1.5%, the fallback is weaker than the 1500p figure suggests, and the contingency plan needs adjustment. |
| **Data needed** | POWER_LOTTO draws (all 1905). Shadow strategy evaluation script. |
| **Minimal validation method** | Compute `orthogonal_5bet` hit rate at 1905p (all draws). Compare to 1500p result (+2.94%). Report edge, bootstrap CI. No permutation needed — monitoring-level check. |
| **Risk** | Low. Only 27% more data than 1500p window. Result likely similar. Risk of over-interpreting minor change — report CI and conclude only if CI lower bound clearly changes direction. |
| **Decision** | **WATCH_ONLY** |

---

### H-LW-08 — POWER_LOTTO Fourier Long-Window Final Scan (1905p)

| Field | Value |
|---|---|
| **ID** | H-LW-08 |
| **Game** | POWER_LOTTO |
| **Hypothesis** | `fourier_rhythm_3bet` showed 1500p perm p=0.0100 (passing) but 150p/500p perm failing. At 1905p (all draws), the signal may remain present at a level consistent with WATCH_DOWNGRADED — positive edge but not reliably replicating at short windows. |
| **Why it might affect success rate** | If 1905p confirms the pattern (positive long-window, weak short-window), it closes the investigation of this strategy: "long-window signal only, not deployable." If 1905p edge turns negative, further downgrade to INACTIVE_MONITOR is justified. |
| **Data needed** | POWER_LOTTO draws (all 1905). |
| **Minimal validation method** | Compute `fourier_rhythm_3bet` hit rate at 1905p. Report edge, CI. Compare to 1500p result (+2.57%). |
| **Risk** | Low. Not proposing any Fourier variant — this is a read-only diagnostic on existing strategy. |
| **Decision** | **WATCH_ONLY** |

---

### H-LW-09 — POWER_LOTTO Active Strategy Decay Check (pp3_freqort_4bet)

| Field | Value |
|---|---|
| **ID** | H-LW-09 |
| **Game** | POWER_LOTTO |
| **Hypothesis** | `pp3_freqort_4bet` (active, +3.28% edge) has been validated at 1500p. A monotonic edge decay pattern similar to DAILY_539 may exist when measured across 150p / 500p / 1500p / 1905p. Measuring this provides an analogous Watchdog reference for POWER_LOTTO. |
| **Why it might affect success rate** | If the PP3 active strategy shows -1.0pp/1000draw attenuation similar to 539, it should have its own Watchdog trigger (e.g., if 1905p edge ≤ +1.5%, flag for review). Currently no explicit Watchdog exists for POWER_LOTTO active. |
| **Data needed** | POWER_LOTTO draws (all 1905); existing 150/500/1500p edge figures from `analysis/results/power_watch_downgrade_decision_20260423.json`. |
| **Minimal validation method** | Assemble existing 150p/500p/1500p edge from existing results. Extend to 1905p. Compute attenuation slope. Define Watchdog threshold at 50% of 1500p edge. |
| **Risk** | Low. Monitoring only. No strategy change. |
| **Decision** | **WATCH_ONLY** |

---

## 5. Validation Candidate Ranking

| Rank | ID | Game | Decision | Expected Value | Novelty | Feasibility | Sample Sufficiency | Overfit Risk | Implementation Cost |
|---|---|---|---|---|---|---|---|---|---|
| 1 | H-LW-01 | DAILY_539 | WORTH_VALIDATION | HIGH — feeds watchdog | LOW (extends existing) | HIGH | HIGH (1844 new draws) | LOW | LOW (reuse existing script) |
| 2 | H-LW-02 | DAILY_539 | WORTH_VALIDATION | HIGH — decodes decay mode | MEDIUM | HIGH | MEDIUM | MEDIUM (rolling windows) | LOW–MEDIUM |
| 3 | H-LW-09 | POWER_LOTTO | WATCH_ONLY | MEDIUM | LOW | HIGH | LOW (1905p ≈ 1500p+27%) | LOW | LOW |
| 4 | H-LW-07 | POWER_LOTTO | WATCH_ONLY | MEDIUM | LOW | HIGH | LOW | LOW | LOW |
| 5 | H-LW-04 | DAILY_539 | WATCH_ONLY | LOW | LOW | HIGH | HIGH | LOW | LOW (bundled H-LW-01) |
| 6 | H-LW-05 | BIG_LOTTO | WATCH_ONLY | LOW | LOW | MEDIUM | LOW (2129p ≈ 1500p+42%) | LOW | LOW |
| 7 | H-LW-06 | BIG_LOTTO | WATCH_ONLY | LOW | LOW | HIGH | LOW | LOW | LOW |
| 8 | H-LW-08 | POWER_LOTTO | WATCH_ONLY | LOW | LOW | HIGH | LOW | LOW | LOW |
| 9 | H-LW-03 | DAILY_539 | WATCH_ONLY | LOW (academic) | LOW | HIGH | HIGH | LOW | LOW (bundled H-LW-01) |

**Top 2 candidates (H-LW-01 + H-LW-02) can be bundled in a single validation task.**
H-LW-04 and H-LW-03 are free riders in the same script.

---

## 6. Risk / Leakage Check

### 6.1 Chronological Split

All long-window analyses must use chronologically ordered draws. Windows are measured
from the MOST RECENT draw backward (e.g., 4000p = last 4000 draws). No shuffling.
For rolling windows (H-LW-02), each window must be non-overlapping in prediction
position — strategy scores computed on draws that were NOT in the training calibration
period for that strategy.

### 6.2 No Future Leakage

The strategy candidate lists (`acb_markov_midfreq_3bet`, `midfreq_acb_2bet`) are
fixed prior to this analysis. No parameter re-tuning based on long-window results is
permitted. The strategies are evaluated as black boxes on historical draws.

### 6.3 Multiple Testing

Nine hypotheses are proposed. Only H-LW-01 and H-LW-02 are designated WORTH_VALIDATION
with a pre-specified decision gate. All others are WATCH_ONLY with no decision gate —
they are informational. This prevents multiple-testing inflation for the primary
validation question (Does 4000p edge remain > +2.0pp?).

For H-LW-02 (CUSUM changepoint on rolling series), a stricter threshold (p < 0.01
rather than 0.05) is pre-specified to guard against false positives in a time series
with autocorrelation.

### 6.4 Sample Sufficiency

- H-LW-01 (4000p): 4000 draws → adequate (bootstrapped CI width ~±3pp; Z >3 if true edge > +2pp)
- H-LW-02 (rolling 500p): Each window = 500 draws, ~26 windows available → adequate for CUSUM
- H-LW-05 / H-LW-06 (BIG 2129p): Small sample caveat — 49C6 draw space means even 2129 draws is sparse
- H-LW-07–09 (POWER 1905p): Marginal — only 405 new draws beyond 1500p baseline

### 6.5 Overfit Risk

No new model parameters are tuned in any of these hypotheses. All analyses are
retrospective evaluation of fixed strategies. The only risk is the "long-window selection"
bias: choosing 4000p specifically because the slope extrapolates to a notable value. This
is mitigated by pre-registering the Watchdog threshold (+2.0pp) independently of the 4000p result.

### 6.6 Cherry-Picking Long Windows

The window selection {4000p, 5844p} for DAILY_539 was pre-specified before analysis.
For BIG_LOTTO and POWER_LOTTO, the only feasible long window is the full history,
which is not a cherry-picked choice.

---

## 7. Decision

**WORTH_VALIDATION**

Justification:
- H-LW-01 (DAILY_539 4000p validation) is directly actionable: it feeds the existing
  Watchdog threshold and closes a gap in the monitoring infrastructure.
- H-LW-02 (rolling trend analysis) disambiguates the nature of edge attenuation
  (smooth decay vs regime shift) — the result determines whether a more aggressive
  response is warranted.
- Both can be implemented with minimal cost by extending the existing script
  (`research/daily539_long_window_validation_20260428.py`).
- BIG_LOTTO and POWER_LOTTO checks are WATCH_ONLY and can be incorporated as
  low-cost additions to the same task.

---

## 8. Next Task If Worth Validation

### Validation Task Prompt

```
# VALIDATION TASK: DAILY_539 Long Window Extension (H-LW-01 + H-LW-02)

## Context
EXPLORE-C long_window_residual identified two WORTH_VALIDATION hypotheses for DAILY_539:
- H-LW-01: Extend edge validation to 4000p and full history (5844p)
- H-LW-02: Rolling 500p edge trend analysis (step=200 draws) to characterize decay mode

Prior work: research/daily539_long_window_validation_report_20260428.md
Prior script: research/daily539_long_window_validation_20260428.py

## Objectives

1. Extend the existing long-window validation script to add windows:
   - 4000p (most recent 4000 DAILY_539 draws)
   - 5000p (most recent 5000 draws, if N >= 5000)
   - Full history (all 5844 draws)

2. Add rolling 500p analysis:
   - Windows: step every 200 draws from oldest to newest 500p window
   - Compute draw-level hit rate for acb_markov_midfreq_3bet per window
   - Apply CUSUM changepoint detection (p < 0.01 threshold)
   - Report: smooth_decay / regime_shift + break date if detected

3. Report active vs shadow delta at all new windows (H-LW-04, free rider)

4. Report full-history edge for acb_1bet baseline (H-LW-03, free rider)

## Pre-specified Decision Gate (H-LW-01)

- If 4000p active edge > +2.0pp → WATCHDOG_STABLE (continue monitoring, update report)
- If 4000p active edge <= +2.0pp → WATCHDOG_BREACH — flag for CTO review,
  DO NOT automatically change strategy

## Constraints

- DB: lottery_api/data/lottery_v2.db — READ ONLY
- Python: .venv/bin/python3; seed=42 for any bootstrap
- No strategy change, no new strategy tuning, no active_strategy_state modification
- All windows use most-recent N draws (chronological, no shuffle)
- No new candidate generators or Fourier/Markov variants

## Output Files

1. research/daily539_long_window_extension_2026-04-29.md
   - Sections: Context / Window Results (table) / Rolling Trend / Changepoint /
     Active vs Shadow Delta / H-LW-01 Decision / H-LW-02 Decision / Overall Conclusion
2. research/daily539_long_window_extension_2026-04-29.py (script)

## Optional Additions (low-cost)

- BIG_LOTTO full-history (2129p) edge check for p1_dev_sum5bet (H-LW-05)
- POWER_LOTTO full-history (1905p) edge check for orthogonal_5bet (H-LW-07)
  and pp3_freqort_4bet (H-LW-09)
- These do NOT require permutation — monitoring only, report edge + 95% CI

## Acceptance Criteria

1. Script runs to completion without error
2. Output report exists at specified path
3. 4000p edge reported with 95% CI for all three strategies
4. Rolling trend classification (smooth_decay or regime_shift) reported
5. H-LW-01 decision gate explicitly stated (WATCHDOG_STABLE or WATCHDOG_BREACH)
6. No strategy change made
7. grep confirms: "4000p" "rolling" "WATCHDOG" "H-LW-01" "H-LW-02" in report
```

### Watch-Only Monitoring Triggers

For BIG_LOTTO (H-LW-05, H-LW-06):
- Trigger review if full-history (2129p) edge < 0pp for active strategy
- Otherwise: confirm MAINTENANCE mode, no further action

For POWER_LOTTO (H-LW-07, H-LW-08, H-LW-09):
- Trigger review if 1905p shadow edge < +1.0pp (current shadow = orthogonal_5bet)
- Trigger review if 1905p active edge drops > 30% from 1500p value
- Otherwise: confirm MONITOR_MODE, no further action

---

*Report generated: 2026-04-29*
*Knowledge sources: wiki/games/daily_539.md, wiki/games/big_lotto.md, wiki/games/power_lotto.md,*
*wiki/lessons/key_lessons.md, research/daily539_long_window_validation_report_20260428.md*
*Lane: EXPLORE-C (long_window_residual)*
*No active_strategy_state was modified. No lottery_v2.db was modified.*
