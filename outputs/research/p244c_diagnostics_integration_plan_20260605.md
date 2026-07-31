# P244C Diagnostics Integration Plan

**Date:** 2026-06-05
**Classification:** `P244C_DIAGNOSTICS_INTEGRATION_PLAN_COMPLETE`
**Task Type:** Type B (read-only design doc / artifact) under P240D governance simplification rules
**Status:** Design plan only — no code changes, no DB write, no registry mutation
**Authorization:** `Authorize P244C diagnostics integration plan (read-only design doc, no code changes)`
**Source:** P243B recommendation; P2.4 diagnostics layer (P241B + P242 + P243A) complete

---

## 1. Scope and Non-Goals

### In Scope
- Mapping P2.4 diagnostics layer to future P211/P221F research checkpoints
- Approved confidence-language templates per classification type
- Blocker vocabulary for governance gates
- Prompt snippet for future P211/P221F tasks
- Same-PR governance closeout under P240D Type B rule

### Explicitly Out of Scope

| Forbidden Item | Status |
|---|---|
| Code changes | Not authorized in this task |
| DB write | Not authorized |
| Registry mutation | Not authorized |
| Production / recommendation change | Not authorized |
| P211 restart | HELD_BY_USER — requires explicit "Start P211" |
| Statistical scan execution | Not authorized |
| Prediction or betting claim | Never authorized |
| Strategy promotion | Not authorized |

**P211 remains HELD_BY_USER. This plan does not restart P211.** Future P211 requires separate explicit authorization: `"Start P211"`.

---

## 2. P2.4 Component Map

| Component | What It Provides | What It Does Not Provide |
|---|---|---|
| **P241B** inventory (`p241b_p234_statistical_diagnostics_inventory_20260605.md`) | 16 diagnostic methods inventoried; 14 gap categories; 44-field schema proposed | No executable code; no standardized tooling |
| **P242** schema module (`lottery_api/diagnostics/statistical_diagnostics_schema.py`) | `REQUIRED_SCHEMA_FIELDS` (44 fields), 7 enum classes, 4 helpers (`default_safety_fields`, `build_diagnostic_report`, `validate_diagnostic_report`, `classify_nist_alert`), conservative safety defaults | No statistical computation; no DB reads; no scan runner; no Bonferroni K helper; no shared baseline registry |
| **P243A** fixture pack (`p243a_diagnostic_report_fixture_pack_20260605.json`) | 4 validated historical fixtures (P238B YELLOW, P231B NULL, P227C UNDERPOWERED, P230C REJECTED); proof schema works against real cases | No new evidence; no scan; no deployment path |

**Known gaps not yet addressed:**
- No executable scan runner (requires P244A authorization)
- No Bonferroni K registry (family-size is declared per-task)
- No shared baseline registry (baseline computed per-task from governance)
- No shared leakage-guard implementation (each task must implement its own ordinal-predecessor split)

These gaps are acceptable for a design-plan layer. The schema module provides the vocabulary and safety enforcement; future tasks supply the computational values.

---

## 3. Integration Workflow for Future P211/P221F Research

When a future research task (e.g., P211 restart, new P221F scan) uses the P2.4 diagnostics layer, it should follow this workflow:

### Step 1 — Phase 0 Verification (always required)
```
Run: git rev-parse HEAD; git branch --show-current; DB row count; drift guard.
Import P242 module: from lottery_api.diagnostics.statistical_diagnostics_schema import ...
Verify module imports successfully.
```

### Step 2 — Pre-Register the Diagnostic Subject
Before running any analysis, declare in the task prompt:
```
diagnostic_subject: "<description>"
lottery_type: <from LotteryType.*>
strategy_id: "<strategy_id or None>"
window_definition: "<short_150 | mid_500 | backward_oos_N | ...>"
family_size_k: <integer — number of simultaneous hypotheses>
baseline_method: "<theoretical | empirical_full | monte_carlo>"
baseline_value: <float>
is_oos: <true | false>
split_boundary: "<ordinal draw ID>"
```
**Gate:** If `family_size_k` is not declared before the scan, the result is FAMILY_SIZE_NOT_DECLARED and must not be promoted.

### Step 3 — Run Analysis (task-specific computation)
The P242 module does not run analysis. The task implements its own analysis using the declared parameters. The schema provides vocabulary only.

### Step 4 — Populate the Diagnostic Report
```python
from lottery_api.diagnostics.statistical_diagnostics_schema import build_diagnostic_report
report = build_diagnostic_report(
    task_id=<P_number>,
    report_date=<ISO date>,
    lottery_type=<LotteryType.*>,
    strategy_id=<id or None>,
    diagnostic_subject=<declared in Step 2>,
    sample_size=<N>,
    window_definition=<declared in Step 2>,
    is_oos=<declared in Step 2>,
    split_boundary=<declared in Step 2>,
    family_size_k=<declared in Step 2>,
    baseline_method=<declared in Step 2>,
    baseline_value=<declared in Step 2>,
    observed_metric=<float>,
    p_value_raw=<float>,
    correction_method=<CorrectionMethod.*>,
    corrected_threshold=<float>,
    is_corrected_significant=<bool>,
    robustness_check_description=<str>,
    robustness_sign_stable=<bool>,
    drift_guard_result=<DriftGuardResult.*>,
    feature_bottleneck=<str>,
    classification=<str>,
    blocker_classification=<str>,
    allowed_next_action=<list>,
    forbidden_next_action=<list>,
    confidence_language=<from template §5 below>,
    human_review_required=<bool>,
    nist_alert_level=<NistAlertLevel.*>,
    # Safety fields default to False — do not override
)
```

### Step 5 — Validate
```python
from lottery_api.diagnostics.statistical_diagnostics_schema import validate_diagnostic_report
ok, errors = validate_diagnostic_report(report)
if not ok:
    raise ValueError(f"Diagnostic report invalid: {errors}")
```
A task must not publish or promote a report that fails `validate_diagnostic_report`.

### Step 6 — Assign Classification and Blockers
Use the blocker vocabulary from §7. If any blocker applies, the `allowed_next_action` must not include promotion or production change.

### Step 7 — Apply Confidence Language
Use the templates from §5. Do not use custom phrasing that implies prediction edge, betting advice, or deployment authorization.

### Step 8 — Required Completion Check
Every research task must close with the standard Required Completion Check including:
- DB rows before/after
- drift guard result
- targeted test result (PASS / FAIL / NOT RUN)
- list of modified files
- explicit `betting_advice: false` statement
- explicit `production_authorized: false` statement

---

## 4. Field Mapping: P242 Schema → P211/P221F Checkpoints

### Fields Required Before Any Claim Can Be Made

These fields must be populated with non-null values before a research result is reported:

| Field | Research Checkpoint | Blocker If Missing |
|---|---|---|
| `diagnostic_subject` | Pre-registration | SUBJECT_NOT_DECLARED |
| `lottery_type` | Pre-registration | SUBJECT_NOT_DECLARED |
| `sample_size` | Phase 0 / DB verification | SAMPLE_SIZE_NOT_DECLARED |
| `window_definition` | Pre-registration | P221F_GATE_NOT_PASSED |
| `is_oos` | Pre-registration | OOS_SPLIT_MISSING |
| `split_boundary` | Pre-registration | OOS_SPLIT_MISSING |
| `family_size_k` | Pre-registration | FAMILY_SIZE_NOT_DECLARED |
| `baseline_method` | Pre-registration | BASELINE_NOT_DECLARED |
| `baseline_value` | Phase 0 / baseline computation | BASELINE_NOT_DECLARED |
| `p_value_raw` | Analysis | SIGNIFICANCE_NOT_COMPUTED |
| `correction_method` | Analysis | MULTIPLE_TESTING_NOT_CORRECTED |
| `corrected_threshold` | Analysis | MULTIPLE_TESTING_NOT_CORRECTED |
| `is_corrected_significant` | Analysis | MULTIPLE_TESTING_NOT_CORRECTED |
| `robustness_check_description` | Post-analysis robustness | ROBUSTNESS_CHECK_MISSING |
| `robustness_sign_stable` | Post-analysis robustness | ROBUSTNESS_FAILED |
| `drift_guard_result` | Phase 0 / Phase-end verification | DRIFT_GUARD_NOT_RUN |
| `feature_bottleneck` | Classification | FEATURE_BOTTLENECK_NOT_ASSIGNED |
| `classification` | Classification | CLASSIFICATION_MISSING |
| `confidence_language` | Required Completion Check | CONFIDENCE_LANGUAGE_MISSING |

### Fields That Block Promotion If Set Incorrectly

| Field | Promotion-Blocking Condition |
|---|---|
| `is_corrected_significant` | Must be True before any "statistically significant" claim |
| `robustness_sign_stable` | Must be True before any "robust" claim |
| `db_write_authorized` | Must remain False unless explicitly authorized |
| `registry_write_authorized` | Must remain False unless explicitly authorized |
| `production_authorized` | Must remain False unless explicitly authorized |
| `betting_advice` | Must always remain False |
| `human_review_required` | If True, no automated promotion is allowed |
| `nist_alert_level` | YELLOW/RED/ORANGE → no strategy, production, or recommendation change |

---

## 5. Confidence-Language Templates

Future research tasks must use one of these approved templates. **Do not use custom phrasing that implies prediction edge, betting advice, or deployment.**

### OBSERVATION_ONLY
```
"[Subject] result is observation-only. No prediction edge claim. No win-rate claim.
Historical research evidence only. Not a wagering recommendation."
```

### NULL / NO_EDGE
```
"[Subject]: [metric] vs baseline [baseline]; p=[p_value] (not significant at α=[threshold]).
CI crosses baseline; both robustness checks fail. Non-deployable. Observation-only.
Historical evidence; not a wagering recommendation."
```

### UNDERPOWERED_NO_SIGNAL
```
"[Subject]: [N] draws available (need ≥[threshold]). [K_bonf] Bonferroni passes (threshold [α/K]).
UNDERPOWERED_NO_SIGNAL. Not deployable. Requires more data before re-scanning.
Not a wagering recommendation."
```

### WAIT_FOR_OOS / GATE_NOT_OPEN
```
"[Subject]: Gate not open. Requires ≥[N] new live draws. Current draws: [count].
Do not promote until gate conditions are met.
Not a wagering recommendation."
```

### REJECTED_BY_BACKWARD_OOS
```
"[Subject]: Backward-OOS ([N] draws): observed [metric] [< or >] baseline [baseline]; p=[p_value].
All era and robustness checks fail. In-window edge is a historical artifact.
REJECTED_BY_BACKWARD_OOS. Not deployable. Not a wagering recommendation."
```

### HUMAN_REVIEW_ONLY (for NIST RED or similar)
```
"[Subject] result requires human diagnostic review only. Does not authorize prediction,
strategy, production, recommendation, monitoring, DB write, or betting advice.
ORANGE/RED require independent future confirmation."
```

### SCHEMA_VALIDATED_ONLY
```
"[Subject]: Diagnostic report validated through P242 validate_diagnostic_report().
All safety booleans false. Schema compliance confirmed.
No prediction edge claim. Not a wagering recommendation."
```

---

## 6. Forbidden-Language Templates

The following phrases or claim types must **not** appear in any research result, confidence_language field, or PR description unless separately authorized and evidence explicitly supports them:

| Forbidden Phrase / Claim Type | Why Forbidden |
|---|---|
| "prediction edge" | Implies deployable advantage; no current evidence supports this in any lottery |
| "improved win rate" | Implies higher probability of winning; never claimed in this project |
| "betting advice" | Explicitly forbidden in all research artifacts |
| "wagering recommendation" | Same as above |
| "production-ready" | No strategy is authorized for production without explicit controlled_apply authorization |
| "recommended numbers" | Implies betting advice |
| "strategy authorized" | Never true unless `strategy_authorized: true` is explicitly set with separate authorization |
| "registry write authorized" | Never true unless `registry_write_authorized: true` is explicitly set |
| "DB write authorized" | Never true unless `db_write_authorized: true` is explicitly set |
| "deployable edge" | Implies strategy promotion; not authorized |
| "statistically significant" | Only when `is_corrected_significant: true` after Bonferroni/BH correction |
| "robust result" | Only when `robustness_sign_stable: true` for all robustness checks |

---

## 7. Blocker Vocabulary

The following labels may be assigned to `blocker_classification` in a diagnostic report to explain why a result cannot be promoted:

| Blocker Label | Trigger Condition |
|---|---|
| `P221F_GATE_NOT_PASSED` | window_definition not in frozen P221F set (short 100/125/150, mid 500/750/1000) |
| `SAMPLE_TOO_SMALL` | sample_size < minimum for adequate power |
| `FAMILY_SIZE_NOT_DECLARED` | family_size_k is null before multiple-testing correction |
| `BASELINE_NOT_DECLARED` | baseline_value is null |
| `OOS_SPLIT_MISSING` | is_oos is null or split_boundary is null |
| `MULTIPLE_TESTING_NOT_CORRECTED` | correction_method == "none" with family_size_k > 1 |
| `ROBUSTNESS_FAILED` | robustness_sign_stable == False |
| `BACKWARD_OOS_NOT_CONFIRMED` | backward-OOS mean below baseline or p >= 0.05 |
| `RANDOMNESS_OBSERVATION_ONLY` | NIST alert level is YELLOW — observation only; no strategy |
| `NIST_HUMAN_REVIEW_ONLY` | NIST alert level is RED — human review; no strategy or production |
| `DB_WRITE_NOT_AUTHORIZED` | db_write_authorized is False (default) |
| `REGISTRY_WRITE_NOT_AUTHORIZED` | registry_write_authorized is False (default) |
| `PRODUCTION_NOT_AUTHORIZED` | production_authorized is False (default) |
| `P211_HELD_BY_USER` | P211 diagnostic is on hold; restart requires explicit "Start P211" |
| `MCNEMAR_NOT_SIGNIFICANT` | McNemar test p >= 0.05; strategy replacement not authorized (L48) |
| `HISTORICAL_ARTIFACT` | Forward-OOS edge not confirmed by backward-OOS; historical artifact only |

---

## 8. Prompt Snippet for Future P211/P221F Tasks

The following block should be included verbatim (or closely adapted) in future P211/P221F task prompts to enforce P2.4 schema discipline:

```
### P2.4 Diagnostics Schema Discipline (required)

Before reporting any research result:

1. Import the P242 schema module:
   from lottery_api.diagnostics.statistical_diagnostics_schema import (
       REQUIRED_SCHEMA_FIELDS, build_diagnostic_report,
       validate_diagnostic_report, classify_nist_alert,
       LotteryType, LifecycleStatus, CorrectionMethod,
       PsiStatus, NistAlertLevel, DriftGuardResult,
       default_safety_fields,
   )

2. Populate a diagnostic report using build_diagnostic_report(**kwargs).
   All safety booleans (db_write_authorized, registry_write_authorized,
   production_authorized, betting_advice) default to False and must NOT be True.

3. Validate: ok, errors = validate_diagnostic_report(report)
   Do not publish or promote a report where ok is False.

4. Apply a confidence-language template from P244C §5.
   Do not use phrases: "prediction edge", "improved win rate",
   "betting advice", "production-ready", "recommended numbers".

5. Assign a blocker_classification from P244C §7 if any gate is unmet.

6. Final Completion Check must include:
   - report['db_write_authorized'] is False
   - report['registry_write_authorized'] is False
   - report['production_authorized'] is False
   - report['betting_advice'] is False
   - validate_diagnostic_report(report) returns (True, [])

Reference: P244C integration plan artifact:
  outputs/research/p244c_diagnostics_integration_plan_20260605.md
```

---

## 9. Next-Step Guidance

| Next Option | Authorization Phrase | Notes |
|---|---|---|
| Restart P211 short/mid-window diagnostic | `"Start P211"` | P211 remains HELD_BY_USER; use P244C §3–§8 prompt snippet for schema discipline |
| P244A module hardening (Bonferroni K helper, baseline registry, McNemar helper) | `"Authorize P244A statistical diagnostics module hardening (no DB write, no production change)"` | Optional; only useful if P211 or future research needs executable helpers |
| P244B multi-signal fixture support for BIG_LOTTO omitted case | `"Authorize P244B multi-signal fixture support (no DB write, no production change)"` | Low priority; omission was representational, not a schema gap |
| Remain HOLD | *(none needed)* | Valid if no new research is desired |

---

## 10. Type B Same-PR Closeout Rationale

This task is **Type B** under P240D §Task Type Classification because:
- It produces only Markdown and JSON artifact files (no code changes)
- Governance changes affect ≤4 files and add ≤120 governance lines
- CI passes on a single PR
- No merge conflict

**Same-PR governance closeout is allowed. No separate P244D closeout PR is required.**
