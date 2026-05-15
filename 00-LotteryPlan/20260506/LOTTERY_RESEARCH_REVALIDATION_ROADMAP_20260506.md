# LotteryNew — Research Re-Validation Roadmap (post-review)

> ⚠️ SUPERSEDED 2026-05-07: P1 Ranks 1–3 已完成；剩餘 Rank 4–5 與插入任務的最新 priority 在 `00-LotteryPlan/20260507/lottery_roadmap_20260507.md`（successor）。本檔保留為歷史版本，不再作為 priority 來源。

**Version:** 1.0
**Effective:** 2026-05-06
**Status:** SUPERSEDED by `00-LotteryPlan/20260507/lottery_roadmap_20260507.md`
**Supersedes (in order):** P1 ranking section of `00-Plan/MASTER_ROADMAP_CONVERGED_20260504.md`
**Authority:** `outputs/research_review/full_system_prediction_opportunity_review_20260506.md`
**Final classification:** `D — GOVERNANCE_FIRST_REQUIRED`

> Closure has been *scientifically* established but is not yet *code-locked*. This roadmap re-orders the next P1 work to lock-in closure before any further research. **No new research is added.**

---

## 1. Re-prioritised P1 Order

| New rank | Original rank | Item | Estimated days | Blocking? | Reason |
|---|---|---|---|---|---|
| **1** | 3 | **Circular-Bias CI Gate** (`tests/test_no_circular_match.py` + fixture) | 1 | YES — blocks ranks 3–5 | Highest-impact bias (v1 produced apparent 6/6 hits = 46× baseline; circular-match bias). Must be code-locked before any new claims can be evaluated. |
| **2** | 2 | **Hypothesis Registry CLI** (`registry/hypotheses.jsonl` + `tools/registry/cli.py` + 2 sentinels) | 1 | YES — blocks rank 3 | Without it, R09 (post-hoc forbidden) is documentation only. |
| **3** | 4 | **Strategy Evaluation Framework v0.5** (`tools/strategy_eval/cli.py`) | 2 | NO — depends on ranks 1–2 | Closes 4 false-positive risks in one CLI: multi-window + perm + Bonferroni + BH-FDR + circular-bias check + leakage check. |
| **4** | 1 | **Randomness Audit Final Verdict → wiki** (`wiki/system/randomness_final_verdict.md` + cadence test) | 0.5 | NO | Move verdict from UNTRUSTED `outputs/` → TRUSTED `wiki/system/`. After ranks 1–3, the verdict is auditable, not asserted. |
| **5** | 5 | **Module Boundaries** (`wiki/system/module_boundaries.md`) | 0.5 | NO | Architecture clarity; no scientific risk. |

### 1.1 Inserted P1 tasks (new)

| Insertion point | Item | Days | Reason |
|---|---|---|---|
| In rank 3 | **Leakage Detector API** (`tools/leakage_detector.py` raising `DataLeakageError`) | 0.5 | Integrate inside Strategy Eval v0.5; not deferred to v1. |
| After rank 4 | **Forbidden Patterns → wiki** (`wiki/system/forbidden_strategy_patterns.md`) | 0.25 | Promote from UNTRUSTED `outputs/`. |
| After rank 5 | **Randomness Audit cadence test** (`tests/test_randomness_audit_cadence.py`) | 0.5 | Fail CI if last audit > 50 draws old. |

---

## 2. Sequenced Acceptance Criteria

### Day 1 (rank 1) — Circular-Bias CI Gate

```
Path        : tests/test_no_circular_match.py
Fixture     : tests/fixtures/circular_match_violation.py
Doc         : wiki/system/llm_governance.md (add section: "Circular-Bias CI Gate")
Pass        : current codebase PASS; fixture FAIL; <60s runtime
Fail-mode   : any v1-style historical-pool max-hit pattern in scripts/, tools/, lottery_api/
Reviewer    : strategy_validation_engineer
```

### Day 2 (rank 2) — Hypothesis Registry CLI

```
Path        : registry/hypotheses.jsonl (append-only)
CLI         : tools/registry/cli.py with subcommands register|list|close
Tests       : tests/test_hypothesis_registry.py
Sentinels   : 2 entries pre-registered (one big_lotto, one power_lotto)
Pass        : strategy_eval run without --hypothesis-id raises HypothesisNotRegisteredError
Reviewer    : governance_engineer
```

### Day 3–4 (rank 3) — Strategy Evaluation Framework v0.5

```
Path        : tools/strategy_eval/cli.py + tools/strategy_eval/__init__.py
Pipeline    : load retro predictions → multi-window (150/500/1500) predict-vs-actual
              → permutation null (≥1000 sims) → Bonferroni + BH-FDR
              → circular-bias scan (rank 1) → leakage check (Leakage Detector)
Mandatory   : --game --hypothesis-id (else fail)
Output      : outputs/strategy_eval/<game>/<ts>/report.json
Tests       : tests/test_strategy_eval.py (smoke + missing-flag fail)
Pass        : end-to-end on power_lotto produces NO_SIGNAL verdict matching 2026-05-01 run
Reviewer    : strategy_validation_engineer
```

### Day 4 (inside rank 3) — Leakage Detector API

```
Path        : tools/leakage_detector.py
API         : check_leakage(prediction_time, training_window, target_draw) -> LeakageReport
Errors      : raise DataLeakageError on (a) future draw in training window
                                       (b) target draw inside training window
                                       (c) feature using post-prediction info
Tests       : tests/test_leakage_detector.py (leak fixture FAIL; clean fixture PASS)
Integration : invoked by tools/strategy_eval/cli.py automatically
Reviewer    : backtest_integrity_engineer
```

### Day 5 (rank 4) — Randomness Audit Verdict → wiki

```
File         : wiki/system/randomness_final_verdict.md
Format       : per Prompt 4 of MASTER_ROADMAP_CONVERGED_20260504.md
Content      : Game | draws_count | tests_run | raw_p | bonferroni_p | bh_fdr_q | VERDICT
              for power_lotto, big_lotto, daily_539
Routing      : wiki/README.md row added
Cadence      : tests/test_randomness_audit_cadence.py — fail CI if last audit > 50 draws
Reviewer     : governance_engineer
```

### Day 5 (rank 5) — Module Boundaries

```
File         : wiki/system/module_boundaries.md
Content      : per task §11 of CONVERGED roadmap (lottery_api/ vs orchestrator/ vs scripts/ vs tools/)
Reviewer     : architecture_engineer
```

---

## 3. Items Explicitly Removed from P1

| Removed | Reason |
|---|---|
| Any new strategy mining for any game | Per L131/L137; closure declared |
| Any frequency-family variant | Per L82/L91 |
| Any historical-pool max-hit method | FP01 — permanent |
| Any post-hoc grid-search promotion | R09 |
| Any short-window-only edge promotion | R08 / FP03 |
| Any cross-game borrowing | L21 / L84 |
| MicroFish 2-bet revival | L128 — does not stably replace incumbent at 150p |
| H013 pool-size revival | L129 — verified at 100 % data, p=1.0 |

---

## 4. Items Explicitly Kept in Maintenance Mode

| Kept | Frequency | Action |
|---|---|---|
| H6 daily monitoring | Daily | Check via `scripts/h6_observation_check.py` |
| Watchdog rules (DAILY_539 edge ≤ +2.0pp; drift_score > 0.50; consecutive_losses) | Each draw | Per `wiki/system/orchestrator.md` |
| Per-ball drift monitor (>3σ flag) | Every 50 draws | Advisory output |
| Randomness audit | Every 50 draws | Cadence test from rank 4 |
| Payout EV / unpopular-number advisory | On request | Anti-consensus advisory; no betting recommendation |

---

## 5. Re-open Path (Documented for Future Reviewer)

A retired strategy or a closed game may re-open research **only** if all of the following hold:

1. ≥300 new draws since the relevant retirement.
2. New external feature family (not a frequency variant).
3. A documented game-rule change OR a randomness-audit deviation that survives Bonferroni + BH-FDR.
4. Hypothesis Registry pre-registration filed before any data inspection.
5. Strategy Evaluation Framework v0.5 (rank 3 above) PASS on the new claim.

Any one missing → **NO** re-open.

---

## 6. Transition Plan (90-day horizon, post-rank-5)

After ranks 1–5 ship, the project transitions to:

| Track | Owner | Deliverable |
|---|---|---|
| Maintenance | research | every-50-draw randomness audit + per-ball drift monitor |
| Framework Transfer | engineering | `tools/backtest_framework/` v0.1 (extract circular_bias_detector + leakage_detector for Stock / Betting POC) |
| Governance | architecture | `wiki/system/module_boundaries.md` + BFF API v0.5 |

No new lottery research is scheduled.

---

## 7. Re-classification Trigger

The next quarterly review (or any earlier event satisfying §5 above) will re-evaluate the classification. Under the current data and rules, the expected next-classification is `A — RESEARCH_CLOSURE_RECOMMENDED` once ranks 1–5 ship.

---

*End of roadmap.*
*Next checkpoint: Day 5 (rank 5 complete) — re-classify A vs C.*
