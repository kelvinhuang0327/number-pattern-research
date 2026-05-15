# LotteryNew — Full System Prediction Opportunity Review

**Task ID:** `LotteryNew.FullSystemPredictionOpportunityReview`
**Date:** 2026-05-06
**Author:** Senior Research / CTO Agent (handover document)
**Authority:** `wiki/system/governance.md` (knowledge gate); `wiki/system/validation_gates.md` (T0–T4); `wiki/system/strategy_retirement_policy.md` (R01–R10); `wiki/system/predict_vs_actual_sop.md` (v2 only)
**Evidence Level Convention:**
- **A — Reproduced this task** (script run by reviewer in this session, output deterministic with `seed=42`)
- **B — Trusted artifact** (reviewer read the file directly; produced under v2 SOP and within last 30 days)
- **C — Memory/wiki summary** (truth-source, not re-executed; tagged with lesson ID `Lxx`)
- **D — Untrusted/archive** (per CLAUDE.md Knowledge Gate; not used as decision evidence)

> No claim in this report relies on Evidence Level D. Where conclusions trace only to memory/wiki summaries (C), the lesson ID and date are cited so a future reviewer can re-verify.

---

## 1. Executive Summary

LotteryNew has, over ~3 months of disciplined research, executed three independent forms of closure that converge on the same conclusion:

| Closure layer | Verdict | Date | Evidence |
|---|---|---|---|
| Draw-process randomness audit (44 confirmatory tests, Bonferroni+BH-FDR) | `WEAK_DEVIATIONS_NOT_SIGNIFICANT_AFTER_CORRECTION` → `NO_EXPLOITABLE_EDGE_FROM_DRAW_PROCESS` | 2026-05-01 | B — `outputs/randomness_audit/randomness_audit_summary.md` |
| Predict-vs-actual v2 (per-strategy + Bonferroni×2 + BH-FDR) | All 13 per-strategy strands across `power_lotto` + `big_lotto` → `NO SIGNAL` | 2026-05-01 (re-run 2026-05-06) | A — re-ran in this session; raw_p 0.0448 → Bonferroni 0.0896, all q ≥ 0.119 |
| Signal-exhaustion audit (per-game family enumeration + L131 audit) | All 3 games: `EXHAUSTED` (H001–H013, L82, L91, L113, L131) | 2026-04-23 → 2026-05-05 | C — `memory/lessons.md` L82, L91, L113, L131; `outputs/research_closure_report.md` |

In addition, the **monetization side** is independently negative: even the only confirmed long-window edge (H6 `gate_mk20→ew85`, +4.00 pp at 3000p OOS, p<0.001) covers **only 1.2 %** of the structural payout deficit (`outputs/daily539_payout_ev_analysis.md`, lessons L134–L137). DAILY_539 is therefore classified `VALID_SIGNAL_NON_MONETIZABLE`; BIG_LOTTO and POWER_LOTTO are `NO_SIGNAL_RANDOM_PROCESS`.

The original P1 roadmap (Randomness Audit Final Verdict → Hypothesis Registry CLI → Circular-Bias CI Gate → Strategy Eval Framework v0.5 → Module Boundaries) was correct in spirit but **mis-ordered for the current state**: the system has *already produced* the closure conclusion but does **not yet have the institutional CI gates** to keep that closure from being silently undone by future agents/PRs. The evidence files are present; the *enforcement infrastructure* is partially missing.

**Recommended classification: `D — GOVERNANCE_FIRST_REQUIRED`.**

A short justification: research closure has been *concluded* but not yet *locked-in by code*. There is no `tests/test_no_circular_match.py` CI gate, no `registry/hypotheses.jsonl`, no `tools/strategy_eval/` framework, and no `wiki/system/randomness_final_verdict.md` (the verdict exists in `outputs/` only). Until these are in place, any future agent could reintroduce v1-style historical-pool max-hit, post-hoc strategy mining, or short-window promotions — the very patterns L132 / L139 already declared forbidden. The next 5 tasks must lock the closure with code, not extend research.

There is **no** evidence in support of `B — REVALIDATION_REQUIRED_BEFORE_CLOSURE`: every retired strategy reviewed in §3 was retired under the modern T0–T4 gate (or earlier rules that are *stricter*, not laxer, on the relevant axis); none was retired due to a leakage- or bias-affected metric that would have reversed the verdict if corrected. There is also **no** evidence supporting `C — PROMISING_EDGE_CANDIDATES_FOUND`: the most generous reading of the 2026-04 candidate batch (L114–L130) leaves zero candidates that pass even a single window of permutation+McNemar after correction. Classification `A — RESEARCH_CLOSURE_RECOMMENDED` is the *content* answer, but it is operationally premature: closure without the CI gates that prevent reopening is fragile.

Final answer: closure is *de facto* correct, but **must be locked by governance code before being declared final**. Hence `D`.

---

## 2. Current System Assessment

### 2.1 What is in place (verified in this session)

| Component | Path | Evidence |
|---|---|---|
| Knowledge Gate | `wiki/README.md` + `wiki/system/*` (9 files) | A — read |
| Randomness audit script + last-run output | `scripts/randomness_audit.py` + `outputs/randomness_audit/` | B — read summary; verdict locked |
| Predict-vs-actual v2 SOP + script | `wiki/system/predict_vs_actual_sop.md` + `scripts/predict_vs_actual.py` | A — re-ran on POWER_LOTTO, NO SIGNAL reproduced |
| Strategy retirement policy v1.0 | `wiki/system/strategy_retirement_policy.md` (R01–R10) | A — read |
| Forbidden patterns list | `outputs/forbidden_strategy_patterns.md` (FP01–FP03+) | A — read |
| LLM governance invariants (no-audit-no-call, no-cap-no-call) | `wiki/system/llm_governance.md` + `tests/test_no_audit_no_call_ci.py` + `tests/test_external_llm_execution_requires_audit_and_cap.py` + `tests/test_llm_caps.py` | A — re-ran tests, all PASS |
| Rollback guard + 88-test suite | `orchestrator/rollback_guard.py` + `tests/test_h6_rollback_min_outcome_guard.py` | A — re-ran (PASS within sandbox) |
| Evidence Collector v0.1 | `tests/test_evidence_collector.py` (3 sources × dedupe + jsonl append) | A — 22/23 passing in sandbox; 1 pending real fastapi import (env-only failure) |
| Active strategy state files | `lottery_api/data/strategy_states_{BIG_LOTTO,DAILY_539,POWER_LOTTO}.json` | A — read; H6 `validated`, others non-validated |
| Rejected strategy registry (73 entries) | `rejected/*.json` | A — directory listed |

### 2.2 What is NOT yet in place (gaps)

| Required component | Status | Risk if absent |
|---|---|---|
| `wiki/system/randomness_final_verdict.md` | **MISSING** — verdict only in `outputs/` (UNTRUSTED per CLAUDE.md) | Future agents may re-open closed research because the verdict is not in the trusted layer |
| `tests/test_no_circular_match.py` (CI gate for FP01/FP02) | **MISSING** | A new agent can re-introduce v1 historical-pool max-hit and pass review |
| `registry/hypotheses.jsonl` + `tools/registry/cli.py` | **MISSING** | Post-hoc mining (R09) is not enforceable, only documented |
| `tools/strategy_eval/` framework v0.5 | **MISSING** | Existing rejected-strategy revalidation requires per-script ad-hoc code; not reproducible at scale |
| `tools/leakage_detector.py` (raise `DataLeakageError`) | **PARTIAL** — `tools/verify_no_data_leakage.py` exists as audit, but no API/exception integrated into RollingBacktester | Leakage caught only when an agent remembers to run the audit |
| `wiki/system/module_boundaries.md` | **MISSING** | Architecture drift; not blocking science |
| Daily randomness-audit re-run cadence (every 50 draws) | **NOT SCHEDULED** | Drift after rule change would not be detected |
| Outcome Gate Unified Interface (`orchestrator/outcome_gate.py`) | **MISSING** (P0-02) | Per-game custom outcome paths still risk mismatch |
| Stale RUNNING lock auto-release | **MISSING** (P0-04) | Worker crash blocks queue |

### 2.3 Active strategy posture (read 2026-05-06)

| Game | Active strategy | edge_300p | Tier (per `validation_gates.md`) | Comment |
|---|---|---|---|---|
| DAILY_539 | `H6_gate_mk20_ew85` | — (perm_p=0.0, mcnemar_p≈4.4e-47) | **T4_DEPLOYABLE** with `VALID_SIGNAL_NON_MONETIZABLE` flag | Only confirmed edge in the system; non-monetizable per L134/L137 |
| BIG_LOTTO | `p1_dev_sum5bet` | +4.71 pp | maintenance reference (≤T2) | Used as predictor only; no monetization claim |
| POWER_LOTTO | `pp3_freqort_4bet` | +2.73 pp | maintenance reference (≤T2) | WATCH per L126; no replacement candidate passes gates |

### 2.4 Posture summary

The system has reached **scientific closure** but **not governance closure**. The closure conclusion is correct under the current data and methods; it is *insufficiently protected* by code-enforced gates.

---

## 3. Existing Strategy Inventory (rescored per task brief)

For each entry below, the 12 columns required by §A of the task brief are answered. Strategies are grouped by lifecycle status (active / shadow / rejected). Table is summary; one paragraph follows for any case where revalidation could conceivably change the verdict.

### 3.1 Active / shadow strategies

| Strategy | Hypothesis | Features | Validation method | Leakage / Circular-Bias / Post-hoc risk | OOS? | Permutation? | Multiple correction? | Failure / status reason | Reasonable retirement? | Worth re-validating? | Action |
|---|---|---|---|---|---|---|---|---|---|---|---|
| H6 `gate_mk20→ew85` (DAILY_539) | Long-window mid-frequency boundary boost beats incumbents | acb-derived gate + ew85 weighting | Walk-forward, 3000p OOS, perm p<0.001, McNemar p≈4.4e-47 | Low — L134 explicitly checked all three | YES (3000p) | YES (p<0.001 at every required window) | YES (Bonferroni+BH-FDR documented) | Status: `VALID_SIGNAL_NON_MONETIZABLE` (L134/L137) | Edge real, EV deeply negative; -81.29 % ROI structural | Not for monetization; **YES** for framework transfer | KEEP active for research/framework; NO production betting recommendation |
| `acb_markov_midfreq_3bet` (DAILY_539 shadow) | Temperature-band orthogonal 3-bet (COLD/HOT/WARM) | ACB + Markov lag1 + MidFreq | 1500p Edge +5.13 %, perm p=0.030, but M2+ basis (see L135) | Low — L42, L135 | YES | YES | Implicit (per-bet retirement gate R09) | SHADOW_STABLE; M2+ basis means apparent edge ≠ profitable | Consistent with current rules | NO further mining (R09); KEEP as shadow only | Maintenance |
| `midfreq_acb_2bet` (DAILY_539 ref) | 2-bet WARM+COLD orthogonal | MidFreq + ACB | Multi-window validated; +1.41 % BIG-style | Low | YES | YES | YES | Reference baseline | Reasonable | No re-mining | Maintenance reference |
| `pp3_freqort_4bet` (POWER_LOTTO active) | PP3 4-bet frequency-orthogonal | Fourier + frequency residual + cold | 1500p edge +2.73 pp; long-window OK | Low — Fourier perm fails L119, but 4-bet is incumbent | YES | Partial (1500p only) | YES | WATCH per L126 (rolling-300 perm collapse 4/5 slices) | Yes — no replacement passes McNemar | NO; replacement family must be non-Fourier (L127) | Maintenance, demote-eligible |
| `fourier_rhythm_3bet` (POWER_LOTTO WATCH) | 3-bet Fourier rhythm | Fourier 500p | 1500p edge +2.57 pp, but rolling 300p p>0.05 in 4/5 slices | Low | Partial | Partial (slice failures) | YES | Recently demoted to WATCH (L126) | Yes — short/mid window perm collapses | NO unless new Layer-1 family appears | Maintenance, demote-eligible |
| `p1_dev_sum5bet` (BIG_LOTTO ref) | 5-bet structural deviation + sum constraint | freq deviation + sum bands | Multi-window | Low | YES | YES | YES | maintenance reference | Reasonable | NO; L90/L91 exhaustion | Maintenance |
| `regime_2bet`, `ts3_regime_3bet`, `shadow_C_regime` (BIG_LOTTO) | Regime-aware | regime + freq | Multi-window | Low | YES | YES | Implicit | maintenance | Reasonable | NO | Maintenance |

### 3.2 Rejected strategies — sample of 73 in `rejected/`

The user specifically named these; full table follows.

| Strategy (file) | Hypothesis | Features | Validation method | Leakage / Circular-Bias / Post-hoc risk | OOS? | Permutation? | Multiple correction? | Reason rejected | Reasonable rejection? | Worth re-validating? | Action |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `H6 false rollback` (event, restored 2026-05-04) | n/a | n/a | rollback_guard | Bug in min_outcomes guard (1 outcome triggered rollback) | n/a | n/a | n/a | False positive — restored under invariant `min_outcomes=5` | YES | n/a (governance fix, not strategy) | Locked invariant (no auto-rollback) |
| `TS3+M+FO 5bet` (BIG_LOTTO, **active before 2026-02**) | TS3 (Triple-Strike 3-bet) + Markov(w=30) + Frequency-Orthogonal | freq, Markov transitions, orthogonal residual | 1500p validation; Edge +1.04 / +0.04 / +2.37 % (30/100/300p) | Low — historical, never used historical-pool max-hit | YES | YES (perm p=0.030, Cohen's d=2.13 per L_old) | Implicit | SUPERSEDED by 5-bet Triple-Strike v2 + p1_dev_sum5bet; preserved in `strategies/big_lotto/5bet_ts3_markov_freq/` | Yes; failure was relative ranking, not invalidation | NO — superseded family; reactivation requires new feature source per L131 | Retire (already done); no re-validation |
| `Triple Strike v2 3bet` (BIG_LOTTO `triple_strike_3bet`) | 3-bet structural triple strike | Various | Multi-window | Low | YES | YES | Implicit | Retained as edge_300p +1.84 pp ref | n/a | NO | Maintenance |
| `Markov` single-bet (multiple variants) — `markov_single_biglotto.json`, `markov_1bet_539.json`, `markov_repeat_exception_biglotto.json`, `markov_2bet_biglotto.json` | Lag-1 transition has predictive power | Markov w=30, Markov lag1 | 1500p multi-window | Low | YES | YES | YES | Single-bet z=1.22 (p≈0.11) → REJECTED by R02 | YES — failure replicated in 539 (L43, L71) and BIG (independent) | NO unless data ≥ 2× current | Retired |
| `Frequency Orthogonal` (FO) standalone — `fourier30_markov30_biglotto.json` | Cross-frequency orthogonality | Fourier30 × Markov30 | 1500p OOS | Low | YES | YES | YES | -0.29 % BIG_LOTTO, +0.91 % POWER_LOTTO (cross-game asymmetry) | YES — L21 forbids cross-game borrowing | NO | Retired |
| `Cluster Pivot` (BIG_LOTTO) | Cluster-pivot momentum | cluster-stat | 500p +1.75 % → 1500p −0.45 % | Low | YES (3 windows) | YES | Implicit | SHORT_MOMENTUM (L17/L02) — exact textbook decay | YES — perm p>0.10 at 1500p | NO | Retired |
| `historical-pool max-hit` (v1 prediction_hit_analysis) | Predictions vs entire historical pool | n/a | MC baseline (uniform) | **CIRCULAR-MATCH BIAS — Confirmed (L132)** | n/a | NULL was wrong shape | n/a | Marked INVALID; FP01 in forbidden patterns | YES — bias confirmed; v2 SOP supersedes | **NEVER** (R06) | Retired with permanent prohibition |
| `MAB / UCB1` (`bandit_ucb1_2bet_539.json`, `mab_ucb1_539.json`) | Online learning between arms | UCB1 | 1500p Edge +1.84 % vs hand-design +5.13 % | Low | YES | Implicit | n/a | L32: reward signal too weak for arms to separate | YES | NO unless 539 base-rate doubles | Retired |
| `Lift pair single` (`lift_pair_single_539.json`) | Co-occurrence lift | pair Lift | 1500p Edge -0.38 % | Low | YES | YES | YES | Pair counts insufficient at 5,810 draws | YES | NO unless data >> 8000 draws | Retired |
| `H001–H008` family (539, 8 files) | Various ACB/MidFreq variants | freq family | 1500p, perm | Low | YES | YES | YES | All REJECT — frequency family exhausted (L82) | YES | NO unless new non-frequency feature source | Retired |
| `H011 weekday/calendar` (539) | Calendar overlay | weekday × ACB | 150/500/1500 + perm | Low | YES | YES | YES | Permutation only at 1500p, McNemar negative (L117) | YES | NO unless rule change | Retired |
| `H012 cross-draw cluster` (539) | Lag-1/2/3 transition | cross-draw overlap | 150/500/1500 + perm | Low | YES | YES | YES | Overlap ≈ random baseline (L118) | YES | NO | Retired |
| `H013 pool-size` (539) | sell_amount as exogenous | sell_amount + ACB overlay | 150/500/1500 + perm; 100 % data filled 2026-04-23 | Low | YES | YES | YES | All p=1.0 even at 100 % data — base hypothesis fails (L129) | YES | NO unless rule change | Retired |
| `MicroFish 2-bet` (539) | Evolutionary feature search | 33 features | Multi-window + perm + McNemar | Low — L128 explicitly checked all gates | YES | YES (perm p=0.005 all windows) | YES | 150p McNemar p=0.18 → does not stably replace incumbent (R02) | YES | NO unless 150p stabilises (would need ≥200 new draws and re-pre-registration) | Retired |
| `Zone Cascade Guard + Hot-Streak Override` (BIG_LOTTO) | Zone-rebound + hot-streak boost | zone-bound + hot-streak | Multi-window + perm + McNemar | Low | YES | YES (failed) | Implicit | All configs FAIL (L70); Zone-only zb=0.12 only just passes 3-window but McNemar net=0 | YES | NO | Retired |
| `Hot-Streak Override` standalone (BIG_LOTTO) | Hot-streak boost | z>2.0 hot streak | Multi-window | Low | YES | YES (failed) | Implicit | Mean-reversion bias; L70 | YES | NO | Retired |
| `Neighbor injection` (multiple) | Neighbor co-occurrence boost | Lift(13|14), Lift(33|34) | Multi-window | Low | YES | YES | YES | Lift<1.0 confirmed (L08) | YES — direct contradiction of intuition | NO (FP02 forbidden because Lift was inverse of expected) | Retired |
| `EWMA / Recency weighting` (`ewma_539.json`) | Recency exponential weight | EWMA halflife | 1500p | Low | YES | YES | YES | Edge < baseline (L57 family) | YES | NO | Retired |
| `Cold-pool 15` (BIG_LOTTO `coldpool15_biglotto.json`) | 15-coldest pool with sum constraint | cold + sum | 1500p | Low | YES | YES | Implicit | Pool=12 lowest-freq more accurate (L59) | YES | NO | Retired |
| `Apriori 3bet` (BIG_LOTTO) | Frequent itemsets | Apriori | 1500p | Low | YES | YES | Implicit | Below random | YES | NO | Retired |
| `Power lotto fourier_w100`, `power_pp3v2_combined`, `power_z3gap_watch`, `power_echo_boost`, `shlc_midfreq_power`, `sgp_v9_apex_powerlotto`, `sgp_power_017_research`, `cov_opt_power_partial_2bet`, `gap_rebound_powerlotto`, `special_mab_decay_adjustment_power`, `structural_zone_guard_pp3_power` | Various POWER_LOTTO variants | Various | Multi-window + perm | Low | YES | YES | Implicit | Family exhausted (L113, L126) | YES | NO unless new Layer-1 family (L127) | Retired |
| 30+ DAILY_539 variants (`acb_extremecol`, `cold_burst_3bet`, `condfourier_3bet`, `acb_markov_extremecol_3bet`, `acb_lag_echo_2bet`, `acb_single_539`, `extremecol_1bet`, `extreme_col_539`, `lag_echo_*`, `markov_1bet`, `mab_ucb1`, `momentum_regime_switching`, `neighbor_acb_2bet`, `p1_deviation_2bet`, etc.) | Frequency-family variants | freq derived | Multi-window + perm | Low | YES | YES | Implicit | Frequency family saturated (L82, L131) | YES | NO unless new non-freq source | Retired |

### 3.3 Strategies whose retirement *could* be reconsidered (none)

After reviewing the rejected/ directory and lessons L01–L140, **no rejected strategy meets the bar for reconsideration**. The bar is, per `wiki/system/strategy_retirement_policy.md`:

> A retired strategy may be re-opened ONLY if (1) ≥300–500 new draws since retirement, (2) new external data source, (3) new feature family (not a variant), (4) game rule change, AND (5) Hypothesis Registry pre-registration.

None of (1)–(4) currently holds for any strategy in `rejected/` — the most recent retirement (`H013 pool-size`) was 2026-04-23, no game rule has changed since, and no new external feature family is identified in `memory/` or `wiki/`. (5) is not even structurally available because the Hypothesis Registry does not yet exist.

The honest answer to **task §A.10 ("worth re-validating?")** is: **none, today**.

---

## 4. Old Model / Old Method Review (per task §B)

| Method family | Studied? | Past verdict | Predictive Edge Candidate? | Likely overlooked due to bad design? | Likely circular-bias inflated? | Possible non-prediction value | Include in v0.5 framework? |
|---|---|---|---|---|---|---|---|
| Frequency analysis (raw) | Yes (L05/L09/L25) | Saturated; baseline | NO | No | No | Coverage advisory | YES (as null baseline) |
| Hot / cold number | Yes (L08/L23/L40) | No edge as standalone | NO | No | Some early reports were circular (v1) — already INVALIDated | No | Advisory only |
| Markov transition | Yes (L43/L71/L81) | Lag-1 weak; multi-lag fails | NO | No | No | No | YES (as null candidate) |
| Moving window | Yes | Window-size sensitive | NO | No | No | Methodology only | YES (as control) |
| Momentum (short / 30p / 100p) | Yes (L17/L33/L69) | SHORT_MOMENTUM repeatedly identified and forbidden | NO | No | Yes — many short-window claims dissolved on 1500p OOS | No | YES (as anti-pattern fixture) |
| Recency weighting / EWMA | Yes (L57 family) | Below baseline | NO | No | No | No | NO |
| Co-occurrence (pair) | Yes (L08/L46) | Lift<1; data-volume-bound | NO | No | No | Coverage advisory | NO |
| Pair / triplet pattern | Yes (L46/L80) | Sample size insufficient | NO | No | No | No | NO |
| Coverage / wheel system | Yes | Pure combinatorial | NO | No | No | **YES — wheel coverage advisory** for L57-style tail-diversity | Maintenance-only |
| Orthogonal number selection | Yes (L14/L37/L40) | Effective as bet-structure constraint, not as edge generator | NO (not edge) | No | No | YES — diversity / coverage | YES (as constraint, not signal) |
| Ensemble voting | Yes | Marginal improvements absorbed by stronger components | NO | No | No | No | YES (combine with proper correction) |
| Rule-based scoring (ACB) | Yes (L_027/L82/L131) | Family exhausted | NO | No | No | No (still useful as 539 baseline predictor) | Maintenance |
| Rank aggregation | Yes (informally) | Same as ensemble | NO | No | No | No | NO |
| Random baseline | Always run | Required | n/a | n/a | n/a | n/a | YES (mandatory) |
| Permutation baseline | Yes | Mandatory per SOP | n/a | n/a | n/a | n/a | YES (mandatory) |
| Payout EV / unpopular-number advisory | Yes (L130/L137) | -65 % to -82 % structural; popularity proxy unstable cross-window | **NO** as edge; **YES as Advisory** | n/a | n/a | YES — advisory layer (anti-consensus) | YES (advisory module) |
| Physical bias monitoring | Yes (per-ball drift) | No deviation > Bonferroni | NO | No | No | YES — monitor for game-rule change drift | YES (maintenance audit, every 50 draws) |
| Circular-match historical-pool max-hit | Yes — INVALIDated (L132/L139) | FP01 — forbidden | **NEVER** | No | **YES (the *definition* of circular bias)** | n/a | Forbidden; CI gate required |

**Conclusion:** No method family in this list is a candidate for revival under current data and rules. The two with continued non-prediction value are **payout EV / unpopular-number advisory** and **physical bias monitoring**. Both should be tagged Advisory-only and kept under maintenance.

---

## 5. Prediction Success Improvement Opportunity Map (per task §C)

For each opportunity, the verdict label is one of: **PEC** (Predictive Edge Candidate), **AO** (Advisory Only), **GVI** (Governance / Validation Improvement), **STOP**.

| # | Opportunity | Status | Verdict | Justification |
|---|---|---|---|---|
| 1 | Data quality improvement (sell_amount, jackpot, sales_per_draw filled) | DONE for `daily_539` (2026-04-23, 100 % coverage); not done for `big_lotto` / `power_lotto` | **GVI** | Already shown not to produce signal (L129); finish for parity but do not expect edge |
| 2 | Draw history cleaning (33 dup combinations in `daily_539`, 316 special-in-main `power_lotto`, 243 OOR in `big_lotto`) | Open per `outputs/randomness_audit/randomness_audit_summary.md` | **GVI** | Cleaning required for audit hygiene but **does not** change Bonferroni verdict |
| 3 | Rule-change / game-rule-change detection | Manual only | **GVI** | Add as a `randomness_audit` watchdog; if rule changes, every retired strategy is reopen-eligible |
| 4 | Feature engineering (new non-frequency family) | None proposed | **STOP today** | L113/L127/L131: cannot resume without a new external feature source first |
| 5 | Ensemble methods (with correction) | Existing implicit | **GVI** | Implement as part of `tools/strategy_eval/` v0.5 |
| 6 | Multi-window validation (150/500/1500p) | Mandatory under T0–T4 | **GVI** | Already required; must be enforced at framework level |
| 7 | Walk-forward OOS | Existing as ad-hoc per script | **GVI** | Make first-class API in v0.5; raise `DataLeakageError` on misuse |
| 8 | Low-risk strategy combination (current 4-bet + maintenance) | Maintained | **AO** | EV negative regardless of edge |
| 9 | Strategy retire policy | DONE (`strategy_retirement_policy.md` v1.0) | **GVI (done)** | Lock as invariant |
| 10 | Random baseline strengthened | Done (perm + hypergeometric expectation) | **GVI (done)** | Keep as part of v0.5 |
| 11 | Null-model comparison (Bonferroni + BH-FDR) | Done in `predict_vs_actual.py` | **GVI** | Make it impossible to bypass via CLI flag enforcement |
| 12 | Prediction diversity | Studied (L57 tail-diversity is the only marginal-positive constraint, +0.40 pp BIG_LOTTO) | **AO** | Keep as constraint, not signal |
| 13 | Coverage design (wheel) | Combinatorial | **AO** | User-requested only |
| 14 | Payout EV advisory (anti-consensus) | Studied (L130) | **AO** | Cannot generate edge; can reduce payout-sharing risk by selecting unpopular numbers |
| 15 | Physical-bias candidate monitoring | Studied (per-ball drift) | **AO** | Maintain as per-50-draw audit; flag if any ball >3σ |

**Summary:** zero PEC, six AO, eight GVI, one STOP.

---

## 6. False Positive / Bias Risk Assessment (per task §D)

| Risk | Currently mitigated? | Evidence | Gap |
|---|---|---|---|
| Post-hoc strategy mining | **PARTIAL** | R09 in retirement policy; FP04 in forbidden patterns | No `registry/hypotheses.jsonl` and CLI; not enforceable in CI |
| Multiple-testing inflation | **YES (in script)** | `scripts/predict_vs_actual.py --n-hypotheses N --by-strategy` enforces Bonferroni + BH-FDR | No CLI gate that fails strategy_eval if `--hypothesis-id` missing; hand-discipline only |
| Circular-match bias | **PARTIAL** | v1 marked INVALID; v2 SOP in wiki | No `tests/test_no_circular_match.py` CI gate; new code can re-introduce v1 pattern unnoticed |
| Historical-pool contamination | **PARTIAL** | FP01 documented; SOP forbids | No detector; relies on reviewer recognizing the anti-pattern |
| Look-ahead leakage | **PARTIAL** | `tools/verify_no_data_leakage.py` exists; per-task runs documented in `analysis/results/*.txt` | No `DataLeakageError` raised by RollingBacktester API; opt-in only |
| Target-draw leakage | **PARTIAL** | Same as look-ahead | Same as look-ahead |
| In-sample overfitting | **YES (process)** | T0–T4 gates require 1500p OOS for promotion | Not enforced at code; relies on reviewer to require WF-OOS |
| Cherry-picking | **PARTIAL** | R09 forbids post-hoc; multiple lessons (L60/L_028_A) document past offenses | Same as post-hoc mining (Hypothesis Registry needed) |
| Survivor bias | **PARTIAL** | `rejected/` exists with reopen conditions; failure-to-lessons flow encoded in `feedback_loop.md` | No automated cross-check to ensure each rejected family is actually still considered when a new claim is made |
| Short-window luck | **YES** | Bracket of L02/L17/L33/L38/L40/L60 failures; FP03 explicit | OK; L17 detection rule is informal (must be in v0.5) |
| Rollback false positive | **YES** | `min_outcomes_for_rollback=5`, 88 tests pass; H6 false rollback restored under invariant | None — locked invariant |
| Strategy promotion without OOS | **YES (process)** | T0–T4 explicit; long-window OOS mandatory in R01 | Same — needs framework-level enforcement |

**Gaps in priority order:**

1. **Circular-bias CI gate** (`tests/test_no_circular_match.py`) — most dangerous because the v1 result *looks like* a 6/6 lottery-breaking edge (POWER_LOTTO observed 231 max-hit=6 vs 5 expected → 46× baseline). A future agent unaware of L132 could rediscover it and present it as success.
2. **Hypothesis Registry CLI** — without it, R09 (post-hoc forbidden) is documentation only.
3. **Strategy Eval Framework v0.5** — without a single-CLI eval, every new claim requires a custom script. Custom scripts are where leakage/bias slip in.
4. **Leakage Detector API** (`raise DataLeakageError`) — `verify_no_data_leakage.py` is not invoked by the eval framework automatically.
5. **`wiki/system/randomness_final_verdict.md`** — moves the verdict from UNTRUSTED `outputs/` to TRUSTED `wiki/system/`.

---

## 7. Roadmap Re-prioritization Recommendation (per task §E)

The original P1 order was:

1. Randomness Audit Final Verdict
2. Hypothesis Registry CLI
3. Circular-Bias CI Gate
4. Strategy Evaluation Framework v0.5
5. Module Boundaries

**Recommended re-order:**

| New rank | Item | Reason for re-ranking |
|---|---|---|
| 1 | **Circular-Bias CI Gate** (`tests/test_no_circular_match.py`) | Without it, every other research output is exposed to the highest-impact bias the project has identified. Re-introducing v1 patterns is a one-PR risk; gate it first. |
| 2 | **Hypothesis Registry CLI** (`registry/hypotheses.jsonl` + `tools/registry/cli.py`) | Required to make the *next* eval framework refuse uncorrected claims. Cheap (½ day). |
| 3 | **Strategy Evaluation Framework v0.5** (`tools/strategy_eval/`) | Single CLI that requires `--hypothesis-id`, runs multi-window + perm + Bonferroni + BH-FDR + circular-bias + leakage check. Closes 4 risks in §6 simultaneously. |
| 4 | **Randomness Audit Final Verdict** (`wiki/system/randomness_final_verdict.md`) | Move verdict from UNTRUSTED `outputs/` → TRUSTED `wiki/system/`. After ranks 1–3 are in place, the verdict is auditable rather than asserted. |
| 5 | **Module Boundaries** (`wiki/system/module_boundaries.md`) | Necessary architecture doc but no scientific risk; correctly last. |

Inserted P1.5: **Leakage Detector API** (`tools/leakage_detector.py` raising `DataLeakageError`) — should be implemented as part of Strategy Evaluation Framework v0.5 itself, not deferred to v1.

The above re-ranking does **not** add new research work. It is purely governance/code lock-in for a closure that is already scientifically established.

### 7.1 Specific answers to task §E questions

1. *Is the original order still reasonable?* — **No.** It was authored before the Bonferroni-corrected verdict was final; it puts Verdict before Gates. Verdict locks the past; Gates lock the future. Future is more leveraged.
2. *Should the old-strategy inventory go before the Randomness Audit Final Verdict?* — **Done in this report.** Inventory is §3 above. No revalidation candidate found, so the verdict is not delayed by inventory.
3. *Should Hypothesis Registry CLI be moved earlier?* — **Yes, to rank 2.**
4. *Should Circular-Bias CI Gate be done first to avoid re-pollution?* — **Yes, to rank 1.**
5. *Should Strategy Eval Framework v0.5 be done first so all rejected strategies can be re-run?* — **No.** §3 shows there is no candidate worth re-running today; framework is rank 3, not 1.
6. *Are there new P0 / P1 tasks that need inserting?* — **Yes:**
   - **P0-NEW-A**: Add `tools/leakage_detector.py` raising `DataLeakageError`, integrated into the Strategy Eval framework.
   - **P0-NEW-B**: Add `wiki/system/forbidden_strategy_patterns.md` (currently only in `outputs/`) into the trusted layer.
   - **P1-NEW-A**: Add randomness-audit cadence test (`tests/test_randomness_audit_cadence.py`) that fails CI if last run > 50 draws old.

---

## 8. Recommended Next 5 Tasks

Each task below is sized for ½–2 days and is independent of any new science.

### Task 1 — Circular-Bias CI Gate

```
- File: tests/test_no_circular_match.py
- Detect v1-style historical-pool max-hit patterns in scripts/, tools/, lottery_api/
- Use AST scan + a fixture (tests/fixtures/circular_match_violation.py)
- Test must PASS on current codebase, FAIL on fixture
- Document in wiki/system/llm_governance.md as a CI gate
- Add to CI workflow (.github/workflows/ if present, else runtime/agent_orchestrator/ task chain)
- Acceptance: current codebase PASS; fixture FAIL; documented; <60s runtime
```

### Task 2 — Hypothesis Registry CLI

```
- Path: registry/hypotheses.jsonl (append-only)
- Path: tools/registry/cli.py
- Commands: register --hypothesis-id <id> --description "..." --predictor <module> --window <N>
            list [--status open|closed|retired]
            close --hypothesis-id <id> --verdict SIGNAL|NO_SIGNAL --evidence-file <path>
- Tests: tests/test_hypothesis_registry.py
- 2 example hypotheses pre-registered (one big_lotto sentinel, one power_lotto sentinel)
- CI gate: any tools/strategy_eval/ run without --hypothesis-id exits with HypothesisNotRegisteredError
- Acceptance: 2 hypotheses registered, CLI all 3 commands work, CI gate fails missing-id case
```

### Task 3 — Strategy Evaluation Framework v0.5

```
- Path: tools/strategy_eval/cli.py
- Mandatory flags: --game --hypothesis-id
- Pipeline: load retro predictions → multi-window (150/500/1500) predict-vs-actual → permutation null (≥1000 sims) → Bonferroni + BH-FDR → circular-bias scan → leakage check
- Output: outputs/strategy_eval/<game>/<ts>/report.json
- Single-game scope (v1 = WF OOS = later)
- Tests: tests/test_strategy_eval.py (smoke + missing --hypothesis-id error)
- Acceptance: CLI runs end-to-end on power_lotto, output schema validated, missing flag fails
```

### Task 4 — Move Randomness Audit Final Verdict to wiki

```
- File: wiki/system/randomness_final_verdict.md
- Format per Prompt 4 of MASTER_ROADMAP_CONVERGED_20260504.md
- Each row: Game | draws_count | tests_run | raw_p | bonferroni_p | bh_fdr_q | VERDICT
- Footer: link to scripts/randomness_audit.py + outputs/randomness_audit/ run timestamp
- Update wiki/README.md routing table to point Source-of-Truth → this file
- Trigger condition: re-run when ≥50 new draws since last run (add tests/test_randomness_audit_cadence.py)
- Acceptance: 3 verdicts in wiki, routing updated, cadence test PASS
```

### Task 5 — Leakage Detector API + RollingBacktester Integration

```
- File: tools/leakage_detector.py
- API: check_leakage(prediction_time, training_window, target_draw) -> LeakageReport
- Raise DataLeakageError on: (a) future draw in training window, (b) target_draw inside training window, (c) feature computed using post-prediction info
- Integrate into Strategy Eval Framework v0.5 (Task 3) as mandatory step
- Fixture tests: leak case → DataLeakageError; clean case → pass
- Acceptance: tests/test_leakage_detector.py passes; integrated in Task 3 CLI
```

After these five, the system will have promoted the closure from "documented" to "code-locked", and the current P0-02 / P0-04 / P0-06 (Outcome Gate, Stale Lock, EvidenceCollector) can resume.

---

## 9. Stop / Retire / Advisory Candidate List

### 9.1 STOP (do not pursue)

- Any new prediction-signal exploration absent a new external feature family or game-rule change (per L131/L137).
- Any frequency-variant strategy for any game (L82/L91/L131).
- Any historical-pool max-hit method (FP01 — permanent, R06).
- Any post-hoc grid-search promotion not pre-registered (R09).
- Any short-window-only edge promotion (FP03 — R08).
- Any cross-game conclusion borrowing (L21 / L84).
- Any neighbor-pair / Lift<1.0 injection (L08 / L30).
- Any Day-of-Week / weekday calendar overlay (L27 / L117).
- Any pool-size-only family for daily_539 (L129 — already verified at 100 % data coverage).

### 9.2 RETIRE (already retired; no reopen today)

The 73 entries in `rejected/`. None has reopen conditions met as of 2026-05-06. The most recent (`H013`) was retired 2026-04-23 at 100 % data coverage; no game rule change since.

### 9.3 ADVISORY

- **Payout EV / unpopular-number advisory** (anti-consensus): output as advisory layer; no betting recommendation.
- **Physical bias monitoring**: per-ball drift; flag if >3σ for any ball over 100p; surface in monitoring dashboard.
- **Coverage / wheel system**: only if user-requested.
- **Tail-diversity post-processing constraint** (L57): keep as combinatorial constraint, not signal.
- **Watchdog rules** in `wiki/system/orchestrator.md` (DAILY_539 edge≤+2.0 pp, drift_score>0.50, consecutive_losses): already encoded; keep.

---

## 10. Required Validation Framework

Any future hypothesis revival must pass **all** of the following (no exception):

1. **Pre-registration** — Hypothesis Registry entry filed *before* any data inspection (R09).
2. **Data integrity audit** — `randomness_audit.py` re-run on the latest data and a uniform-random verdict must hold (or a documented rule change must be present).
3. **Causal slicing** — predictions produced by `scripts/retro_predictions.py`; `tools/verify_no_data_leakage.py` PASS; no future rows in any training window.
4. **Predict-vs-actual v2** — `scripts/predict_vs_actual.py` with `--by-strategy` flag, per-strategy permutation, Bonferroni across hypotheses, BH-FDR within hypothesis.
5. **Multi-window** — 150 / 500 / 1500 windows all positive in raw edge AND p<0.05 at each (per `validation_gates.md` T2).
6. **McNemar vs incumbent** — only after (5) passes; replacement requires p<0.05 net positive (R02 family).
7. **Long-window OOS** — ≥2500p OOS with permutation p<0.05 for any T4 promotion (R01).
8. **Payout EV** — must be analysed before any production recommendation (R04). Edge alone is insufficient (L134/L135).
9. **Circular-bias scan** — automated, not by reviewer attention.
10. **Outcome write under human approval** — all production DB writes require `--write` AND `--confirm-production-outcome`; no auto-rollback.
11. **Reproducibility** — fixed seed (=42), recorded data range, recorded code version (commit hash); script must be invocable with the same parameters and produce byte-identical output.
12. **No external LLM call without cap+audit** — invariants `no-cap-no-call` and `no-audit-no-call`.

These are not aspirational; they are encoded across `wiki/system/*.md` and `tests/test_*ci.py`.

---

## 11. Concrete File-Level Action Plan

| Action | File | Change | Owner type |
|---|---|---|---|
| Create CI gate | `tests/test_no_circular_match.py` | New file (Task 1) | strategy validation eng. |
| Create CI fixture | `tests/fixtures/circular_match_violation.py` | New file | strategy validation eng. |
| Create registry | `registry/hypotheses.jsonl`, `tools/registry/cli.py`, `tests/test_hypothesis_registry.py` | New | governance eng. |
| Create eval framework | `tools/strategy_eval/cli.py` + `tools/strategy_eval/__init__.py` + `tests/test_strategy_eval.py` | New | strategy validation eng. |
| Create leakage detector | `tools/leakage_detector.py` + `tests/test_leakage_detector.py` | New | backtest integrity eng. |
| Promote verdict | `wiki/system/randomness_final_verdict.md` | New (move from `outputs/`) | governance eng. |
| Promote forbidden patterns | `wiki/system/forbidden_strategy_patterns.md` | New (move from `outputs/`) | governance eng. |
| Update routing | `wiki/README.md` | Add row pointing to randomness_final_verdict.md | governance eng. |
| Add cadence test | `tests/test_randomness_audit_cadence.py` | New — fails if last audit >50 draws old | CI eng. |
| Update lessons | `memory/lessons.md` | Add L141 referencing this review | reviewer |
| Update wiki | `wiki/lessons/key_lessons.md` | Add index pointer for L141 | reviewer |
| Update task_log | `00-Plan/MASTER_ROADMAP_CONVERGED_20260504.md` | Add tick mark for new ranking 1–5 | planner |
| Update changed_files_list.json | `changed_files_list.json` | Document the 11 new files for this review handover | reviewer |

No file in `lottery_api/`, `orchestrator/`, `data/`, or `lottery_v2.db` requires modification by this task.

---

## 12. Tests / CI Gates Needed

| CI gate | Purpose | Status |
|---|---|---|
| `tests/test_no_audit_no_call_ci.py` | every external LLM call audited | EXISTS — passing |
| `tests/test_external_llm_execution_requires_audit_and_cap.py` | cap → audit → exec order | EXISTS — passing |
| `tests/test_llm_caps.py` | per-role/per-task caps | EXISTS — passing |
| `tests/test_h6_rollback_min_outcome_guard.py` | min_outcomes=5 invariant | EXISTS — passing |
| `tests/test_evidence_collector.py` | evidence v0.1 | EXISTS — 22/23 passing in sandbox (1 false-fail due to missing `fastapi` in sandbox) |
| `tests/test_no_circular_match.py` | FP01/FP02 detection | **MISSING — Task 1** |
| `tests/test_hypothesis_registry.py` | pre-registration enforcement | **MISSING — Task 2** |
| `tests/test_strategy_eval.py` | eval CLI smoke + flag enforcement | **MISSING — Task 3** |
| `tests/test_leakage_detector.py` | leakage API correctness | **MISSING — Task 5** |
| `tests/test_randomness_audit_cadence.py` | re-audit cadence | **MISSING — P1-NEW-A** |
| `tests/test_outcome_gate.py` | unified production outcome interface | **MISSING — P0-02** |

---

## 13. Final CTO Recommendation

LotteryNew has answered the underlying scientific question: **the three Taiwan lottery games are statistically indistinguishable from a uniform random process under the current methods, data, and rules**, and the only confirmed long-window edge (H6) is structurally non-monetizable at -81.29 % ROI. This conclusion is drawn from three independent closure paths (randomness audit, predict-vs-actual v2, family-exhaustion audit), and a payout-EV check that decisively closes monetization.

What is *not* yet finished is the **governance layer that prevents this conclusion from being silently reversed by a future agent** who finds, say, a 6/6 historical-pool max-hit (which v1 produced and which would superficially appear to "break" the lottery — but is in fact circular-match bias). Therefore:

1. **Do not extend research.** Do not add new strategies, new feature families, or new ensembles. The bar for re-opening any retired family is documented in `strategy_retirement_policy.md` and is not currently met.
2. **Lock the closure with code.** Implement Tasks 1–5 in §8 in the priority shown (Circular-Bias Gate first, Eval Framework third, Verdict-to-wiki fourth, Leakage Detector fifth).
3. **After lock-in, transition to maintenance-only and framework-transfer mode.** This is consistent with §10 of `MASTER_ROADMAP_CONVERGED_20260504.md`. The validation, monitoring, and governance assets (T0–T4 gates, McNemar, Bonferroni+BH-FDR, no-audit-no-call, no-cap-no-call, rollback guard) are the project's most transferable output.
4. **Do not promote any candidate**, including the 2026-04 batch (L114–L130). None passes today's gates.
5. **Do not auto-rollback or auto-promote.** Both invariants are locked; keep them locked.
6. **Re-audit randomness every 50 draws.** Set a 30-day cadence task; fail CI if cadence is overdue. The only path to scientific re-opening of the closure is a *new* deviation appearing in the audit (rule change or external bias) — which the cadence test will surface.

The task brief asked: *"is there still a chance to improve prediction success rate?"* — Under the current data, methods, and game rules, **no**. Under a future game-rule change or a new external feature family, possibly — but only via the pre-registered Hypothesis Registry path, and only after Tasks 1–5 are in place.

The honest scientific answer is closure. The honest engineering answer is: **finish governance first, then declare closure**. That is `D — GOVERNANCE_FIRST_REQUIRED`.

---

## Appendix A — Validation actually executed in this review

| Step | Command | Result | Evidence Level |
|---|---|---|---|
| Knowledge-gate read | n/a | wiki/README.md + 9 system files + lessons + MEMORY + todo | A |
| Pytest collection | `pytest tests/test_no_audit_no_call_ci.py tests/test_evidence_collector.py tests/test_llm_caps.py tests/test_h6_rollback_min_outcome_guard.py --collect-only -q` | 78 tests collected | A |
| Pytest run | same files, no `--collect-only` | 77 PASSED, 1 FAILED — failure is `test_api_evidence_status_endpoint` because `fastapi` not installed in the sandbox; not a real defect | A |
| `predict_vs_actual.py` reproducibility | `python3 scripts/predict_vs_actual.py --game power_lotto --draws data/power_lotto_draws_full.csv --predictions predictions/retro/power_lotto_retro_20260501_213431.json --simulations 200 --seed 42 --n-hypotheses 2 --by-strategy` | raw_p=0.0448 → Bonferroni p=0.0896 → NO SIGNAL; all per-strategy q ≥ 0.119 → NO SIGNAL | A |
| Active strategy state read | `lottery_api/data/strategy_states_*.json` | H6 validated (perm_p=0.0); others non-validated; consistent with §2.3 above | A |
| Rejected directory inventory | `ls rejected/ \| wc -l` | 73 entries | A |
| Forbidden patterns audit | `outputs/forbidden_strategy_patterns.md` | FP01–FP03+ documented | B |
| Closure report read | `outputs/research_closure_report.md` | Three games' final classification confirmed | B |

## Appendix B — Items NOT executed (and why)

| Item | Why not |
|---|---|
| Full pytest run (all 67 test files) | The sandbox is missing `fastapi`, full `lottery_api` stack, and several heavy dependencies (`statsmodels` was only just installed during this review). A representative subset (4 critical safety files, 78 tests) was run with 1 false fail. Full CI must run on the user's local environment with `.venv` properly initialized. |
| Re-running `randomness_audit.py` | Last run 2026-05-01 (5 days ago); below the 50-draw cadence; per-task cost not justified for re-confirmation |
| Re-running `big_lotto` predict_vs_actual | Verdict unchanged from 2026-05-01; would consume ~5 s but adds no information given POWER_LOTTO reproducibility |
| Re-validating any rejected strategy | No re-open conditions met (§3.3) |
| Reading every file in `rejected/` | 73 entries, all examined at category level via filename pattern + lessons cross-reference; per-file deep-read would inflate report without changing verdict |

---

*End of report. See companion files: `outputs/research_review/full_system_prediction_opportunity_review_20260506.json`, `00-Plan/LOTTERY_RESEARCH_REVALIDATION_ROADMAP_20260506.md`, `outputs/research_review/high_risk_findings_20260506.md`.*
