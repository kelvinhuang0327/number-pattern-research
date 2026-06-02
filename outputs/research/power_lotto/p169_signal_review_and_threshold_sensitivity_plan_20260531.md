# P169 — POWER_LOTTO Signal Review and Threshold Sensitivity Plan

**Task**: P169_POWER_LOTTO_SIGNAL_REVIEW_AND_THRESHOLD_SENSITIVITY_PLAN_ONLY  
**Date**: 2026-06-01  
**Final Classification**: `P169_POWER_LOTTO_SIGNAL_REVIEW_AND_THRESHOLD_SENSITIVITY_PLAN_READY`  
**Status**: PLAN ONLY — no analysis executed  
**Authorization**: YES produce P169 signal review and threshold sensitivity plan only, no rerun, no verdict change

---

## Phase 0 Verification — ALL PASS

| Check | Result |
|---|---|
| Authorization phrase | PRESENT ✓ |
| Worktree | `/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802` ✓ |
| Branch | `claude/zen-gates-ff6802` ✓ |
| DB rows before | 94,924 ✓ |
| DB rows after | 94,924 (unchanged) ✓ |
| Drift guard | PASS ✓ |
| P161–P168 tests | PASS (352/352) ✓ |
| P167 script | PASS ✓ |
| P167 artifact | `P167_POWER_LOTTO_NO_DEFENSIBLE_EDGE_FOUND` ✓ |
| P168 artifact | `P168_POWER_LOTTO_RESEARCH_DECISION_REVIEW_READY` ✓ |

---

## P167 NULL Conclusion — PRESERVED (NOT CHANGED)

**P167 classification: `P167_POWER_LOTTO_NO_DEFENSIBLE_EDGE_FOUND`**

This classification is NOT changed by P169. The following are facts that P169 does NOT alter:
- OOS Window 2 had 499 draws — the pre-declared minimum was 500 — Window 2 did NOT pass
- Module F final gate required ≥ 2 computed OOS windows — only 1 was computed — gate FAILED
- No retroactive reclassification of 499 draws as meeting the 500-draw threshold is permitted

P169 acknowledges the positive signals from P167:
- Module A in-sample: mean=1.001, p_bh=0.038 (BH-significant, but in-sample)
- Module E main-number: p_bh=0.024 (BH-significant, but in-sample)
- Module F OOS Window 1: mean=1.040, p_bh=0.049 (one computed window — insufficient for stability)

These signals are **encouraging but unconfirmed**. P169 designs a plan to evaluate their robustness without changing the P167 verdict.

---

## P168 Decision Summary

P168 recommended **Option B + C**: threshold sensitivity plan (descriptive) combined with prospective signal tracking pre-registration.

---

## Part 1 — Threshold Sensitivity Plan

### Objective

Evaluate whether the pre-declared 500-draw OOS window minimum is materially sensitive. Does the ensemble consensus voting result change direction or lose significance at nearby thresholds (450, 475, 499, or 525 draws)?

**Type**: Retrospective descriptive sensitivity — NOT retroactive gate passage.

### Pre-Declared Scenarios for P170

| Scenario | Threshold | OOS Window 2 draws available | Label |
|---|---|---|---|
| S1 | 450 draws minimum | 499 → PASSES | RETROSPECTIVE_SENSITIVITY_ONLY |
| S2 | 475 draws minimum | 499 → PASSES | RETROSPECTIVE_SENSITIVITY_ONLY |
| S3 | 499 draws minimum | 499 → PASSES | RETROSPECTIVE_SENSITIVITY_ONLY |
| S4 | 500 draws minimum | 499 → FAILS | ORIGINAL_PROTOCOL (P167 reference) |
| S5 | 525 draws minimum | 500 → FAILS; 499 → FAILS | RETROSPECTIVE_SENSITIVITY_ONLY |

**All scenarios other than S4 are sensitivity explorations only.** Results at S1–S3 do NOT mean the P167 Module F gate was satisfied. Results at S5 are informational.

### Metrics Per Scenario

For each scenario, P170 must report:
1. Number of OOS windows meeting the threshold
2. Mean hit count per OOS window that qualifies
3. Direction vs random baseline (0.9474) and best single (0.9749)
4. z-statistic and raw p-value per qualifying window
5. BH-corrected p across all qualifying windows in scenario
6. Stability: do all qualifying windows agree on direction?

### Forbidden Interpretations

- ✗ "P167 would have passed at 450-draw threshold" → This is NOT equivalent to "the P167 Module F gate was satisfied"
- ✗ Using S1/S2/S3 results as deployment evidence
- ✗ Reclassifying P167 final classification based on sensitivity findings
- ✗ Authorizing controlled_apply or champion based on sensitivity results

### Interpretation Requirement

If the effect holds consistently at 400+ draws AND all scenarios show positive direction: this demonstrates threshold-robustness of the signal, NOT that the P167 Module F gate was satisfied. The only path to formal Module F gate passage is future data collection completing Window 2 at the 500-draw minimum.

---

## Part 2 — Prospective Signal Tracking Plan

### Objective

Pre-register a tracking protocol for the two strongest signals from P167, evaluated on future POWER_LOTTO draws NOT yet in the P167 dataset.

### Target Signals (pre-declared configurations — do NOT modify before P170 evaluation)

**Signal A: Consensus Voting Ensemble**
- Source: P167 Module A
- Configuration: Equal-weight voting, bet_index=1, top-6 by vote count across all 10 strategies
- In-sample reference: mean=1.001, p_bh=0.038
- OOS Window 1 reference: mean=1.040, p_bh=0.049
- Target metric: per-draw mean > 0.9749 (best P161 single strategy)

**Signal E: Main-Number Hit Rate**
- Source: P167 Module E
- Configuration: Per-draw mean hit count across all 10 strategies, bet_index=1, main numbers only
- In-sample reference: p_bh=0.024
- Target metric: per-draw mean > 0.9749

### Tracking Protocol (pre-registered in P169 — must not be changed in P170)

| Rule | Requirement |
|---|---|
| Prospective draws only | Draws strictly AFTER draw 115000041 (last P167 dataset draw) |
| Minimum N for evaluation | ≥ 100 prospective draws |
| Statistical unit | Per distinct target_draw (NOT per bet row) |
| Multiple-testing correction | Bonferroni + BH on 2 signals simultaneously |
| Baseline comparison | Both random (0.9474) AND best single strategy (0.9749) |
| Stability check | ≥ 2 non-overlapping prospective windows × ≥ 50 draws each |
| Success criterion (each signal) | Prospective mean > 0.9749 AND p_bh < 0.05 AND stable across ≥ 2 windows |

### If Fewer Than 100 Prospective Draws Are Available at P170 Time

P170 must report `AWAITING_PROSPECTIVE_DATA`. It must NOT:
- Evaluate any signal on fewer than 100 prospective draws and claim significance
- Use retrospective draws as proxies for prospective draws
- Lower the 100-draw minimum without re-authorization

### Forbidden Tracking Practices

- ✗ Retroactively labeling old draws as "prospective"
- ✗ Selecting which draws to include after seeing results
- ✗ Lowering the 100-draw minimum without re-authorization
- ✗ Changing signal configurations after seeing early tracking results

---

## P170 Implementation Boundary

### Allowed in P170 (after explicit authorization)

- Read-only DB queries (PRAGMA query_only=ON)
- Execute threshold sensitivity analysis on existing 1,499 draws for pre-declared scenarios S1–S5
- Report sensitivity results labeled RETROSPECTIVE_SENSITIVITY_ONLY
- Check how many prospective draws (> 115000041) are now in DB
- If ≥ 100 prospective draws: evaluate Signal A and Signal E on them
- If < 100 prospective draws: report AWAITING_PROSPECTIVE_DATA
- Produce P170 artifact with clear separation of sensitivity vs prospective sections

### Forbidden in P170 (absolute)

- Any DB write or new row insertion
- Modifying P167 analysis script
- Changing P167 final classification
- Retroactively reclassifying OOS Window 2 (499 draws) as meeting 500-draw threshold
- Champion promotion or controlled_apply
- Registry or lifecycle mutations
- Stage, commit, or push
- Merge, rebase, or checkout

### What P170 Cannot Claim

P170 may NOT claim a defensible edge was found unless ALL of:
1. Prospective Signal A or E survives BH correction with ≥ 100 prospective draws
2. Module F walk-forward OOS from P166 protocol is formally re-run with ≥ 2 windows × ≥ 500 draws each
3. Both conditions are documented in the P170 artifact with full statistical evidence

Sensitivity results (S1–S3) are descriptive only — not grounds for any deployment.

---

## No-Action Confirmations

- **Zero DB writes** — DB unchanged at 94,924 rows
- **Zero P167 reruns** — P167 script not modified
- **Zero verdict changes** — P167 NULL stands
- **Zero retroactive 499-draw reclassifications**
- **Zero registry mutations, champion promotions, controlled_apply**
- **Zero commits or pushes**
- **No win guarantees, no real-money guidance**

---

## Next Task — WAITING_FOR_USER_AUTHORIZATION

**P170_POWER_LOTTO_THRESHOLD_SENSITIVITY_AND_SIGNAL_TRACKING_READ_ONLY**

P170 is BLOCKED until the user provides explicit authorization.

---

## Governance Invariants

| Invariant | Value |
|---|---|
| DB rows | 94,924 (unchanged) |
| Drift guard | PASS |
| main/zen-gates split | UNRESOLVED |
| P167 NULL result | **STANDS — not changed by P169** |
| Defensible edge found | **NO** |
| Plan status | PLAN ONLY — no analysis executed |
