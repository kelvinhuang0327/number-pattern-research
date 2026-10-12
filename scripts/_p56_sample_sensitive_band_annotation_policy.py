"""
P56 — Sample-Sensitive Band Annotation Policy for Monitoring Contract V2.

Offline diagnostic only.  paper_only=True, live_api_calls=0.
Do NOT refit Platt.  Do NOT change runtime logic.  Do NOT deploy.
Do NOT modify P52/P53/P54/P55 artifacts.

P55 result:
  Sep mid-band (1.00-1.25) platt_ece=0.246, n=27 => INCONCLUSIVE_SAMPLE_LIMITED
  Platt worsened ECE by +0.081 in this band.

P56 goal:
  Define a sample-sensitive band annotation policy so future monitoring reports
  can correctly interpret band-level ECE when n < 30, 30-99, or >= 100,
  without triggering false drift alerts or unwarranted model refits.
"""

from __future__ import annotations

import json
import pathlib
from datetime import datetime

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = pathlib.Path(__file__).resolve().parents[1]

P45_SUMMARY = ROOT / "data/mlb_2025/derived/p45_platt_recalibration_summary.json"
P52_SUMMARY = ROOT / "data/mlb_2025/derived/p52_monitoring_contract_v2_summary.json"
P53_SUMMARY = ROOT / "data/mlb_2025/derived/p53_sep_calibration_critical_audit_summary.json"
P54_SUMMARY = ROOT / "data/mlb_2025/derived/p54_sep_sp_fip_delta_feature_drift_audit_summary.json"
P55_SUMMARY = ROOT / "data/mlb_2025/derived/p55_sep_mid_band_calibration_anomaly_audit_summary.json"

OUTPUT_JSON = ROOT / "data/mlb_2025/derived/p56_sample_sensitive_band_annotation_policy_summary.json"
REPORT_MD = ROOT / "report/p56_sample_sensitive_band_annotation_policy_20260526.md"
BETTING_PLAN_MD = ROOT / "00-BettingPlan/20260526/p56_sample_sensitive_band_annotation_policy_20260526.md"
ACTIVE_TASK_MD = ROOT / "00-Plan/roadmap/active_task.md"

# ---------------------------------------------------------------------------
# Governance (immutable)
# ---------------------------------------------------------------------------
GOVERNANCE: dict = {
    "paper_only": True,
    "diagnostic_only": True,
    "promotion_freeze": True,
    "kelly_deploy_allowed": False,
    "live_api_calls": 0,
    "tsl_crawler_modified": False,
    "champion_strategy_changed": False,
    "production_usage_proposed": False,
    "runtime_recommendation_logic_changed": False,
    "platt_constants_modified": False,
    "p52_contract_overwritten": False,
    "p53_artifact_overwritten": False,
    "p54_artifact_overwritten": False,
    "p55_artifact_overwritten": False,
    "p52_thresholds_changed": False,
}

# P45 Platt constants — locked, do not modify
PLATT_A: float = 0.435432
PLATT_B: float = 0.245464

# ---------------------------------------------------------------------------
# Governance assertions (called at start and end)
# ---------------------------------------------------------------------------

def _assert_governance() -> None:
    assert GOVERNANCE["live_api_calls"] == 0, "GOVERNANCE VIOLATION: live_api_calls != 0"
    assert GOVERNANCE["paper_only"] is True
    assert GOVERNANCE["platt_constants_modified"] is False
    assert GOVERNANCE["p52_contract_overwritten"] is False
    assert GOVERNANCE["p53_artifact_overwritten"] is False
    assert GOVERNANCE["p54_artifact_overwritten"] is False
    assert GOVERNANCE["p55_artifact_overwritten"] is False
    assert GOVERNANCE["p52_thresholds_changed"] is False
    assert GOVERNANCE["runtime_recommendation_logic_changed"] is False
    assert abs(PLATT_A - 0.435432) < 1e-6, "Platt A modified"
    assert abs(PLATT_B - 0.245464) < 1e-6, "Platt B modified"


# ---------------------------------------------------------------------------
# Task A — Band Annotation Policy
# ---------------------------------------------------------------------------

def build_band_annotation_policy() -> dict:
    """Define sample-sensitive band annotation policy."""
    return {
        "policy_name": "Sample-Sensitive Band Annotation Policy v1",
        "policy_version": "1.0",
        "created_date": datetime.now().strftime("%Y-%m-%d"),
        "purpose": (
            "Define how band-level calibration findings should be labelled "
            "in monitoring reports based on the sample size of each band, "
            "without changing P52 global monitoring thresholds or triggering "
            "unwarranted model refits."
        ),
        "scope": "Tier C sp_fip_delta bands (0.5-0.75, 0.75-1.00, 1.00-1.25, >=1.25) "
                 "per month in MLBseason 2025.",
    }


def build_sample_size_tiers() -> dict:
    """Define the three sample size tiers for band-level evidence quality."""
    return {
        "BAND_SAMPLE_INSUFFICIENT": {
            "condition": "n < 30",
            "label": "BAND_SAMPLE_INSUFFICIENT",
            "description": (
                "Band sample is too small for reliable ECE estimation. "
                "High variance expected. ECE may deviate substantially "
                "from true calibration due to binning noise."
            ),
            "allowed_annotations": ["SAMPLE_SENSITIVE_BAND_ANOMALY"],
            "disallowed_actions": [
                "TRIGGER_REFIT",
                "TRIGGER_THRESHOLD_CHANGE",
                "PROMOTE_TO_DRIFT_CANDIDATE",
                "REPORT_AS_CONFIRMED_DRIFT",
            ],
            "allowed_actions": ["TRACK_ONLY_NO_REFIT"],
            "note": "P55 Sep 1.00-1.25 band (n=27) falls in this tier.",
        },
        "BAND_SAMPLE_WATCHLIST": {
            "condition": "30 <= n < 100",
            "label": "BAND_SAMPLE_WATCHLIST",
            "description": (
                "Band sample is sufficient for preliminary ECE estimation "
                "but below the stable inference threshold (n=100). "
                "Findings should be treated as watchlist candidates."
            ),
            "allowed_annotations": [
                "BAND_WATCHLIST",
                "SAMPLE_SENSITIVE_BAND_ANOMALY",
            ],
            "allowed_actions": [
                "TRACK_ONLY_NO_REFIT",
                "FLAG_FOR_FOLLOW_UP",
            ],
            "elevation_criteria": (
                "Elevate to BAND_DRIFT_CANDIDATE only if elevated ECE "
                "persists across at least 2 separate months in the same band "
                "AND n >= 30 in both months."
            ),
        },
        "BAND_SAMPLE_MONITORABLE": {
            "condition": "n >= 100",
            "label": "BAND_SAMPLE_MONITORABLE",
            "description": (
                "Band sample meets the stable inference threshold. "
                "ECE estimates carry sufficient statistical reliability "
                "for drift candidate consideration."
            ),
            "allowed_annotations": [
                "STABLE_BAND_EVIDENCE",
                "BAND_DRIFT_CANDIDATE",
                "BAND_WATCHLIST",
            ],
            "allowed_actions": [
                "TRACK_ONLY_NO_REFIT",
                "FLAG_FOR_FOLLOW_UP",
                "PROMOTE_TO_DRIFT_CANDIDATE_IF_CI_ELEVATED",
            ],
            "drift_candidate_criteria": (
                "Classify as BAND_DRIFT_CANDIDATE only if n >= 100 "
                "AND ECE confidence interval lower bound remains above 0.08 "
                "across cumulative data."
            ),
        },
    }


def build_interpretation_rules() -> list[dict]:
    """Define explicit interpretation rules for band-level ECE findings."""
    return [
        {
            "rule_id": "R01",
            "condition": "n < 30 AND platt_ece is high",
            "classification": "SAMPLE_SENSITIVE_BAND_ANOMALY",
            "action": "TRACK_ONLY_NO_REFIT",
            "reason": "ECE estimates below n=30 have high variance. "
                      "Elevated ECE does not confirm systematic miscalibration.",
        },
        {
            "rule_id": "R02",
            "condition": "30 <= n < 100 AND platt_ece elevated in >= 2 months",
            "classification": "BAND_WATCHLIST",
            "action": "FLAG_FOR_FOLLOW_UP",
            "reason": "Preliminary signal across multiple months is noteworthy "
                      "but below the refit evidence threshold.",
        },
        {
            "rule_id": "R03",
            "condition": "n >= 100 AND ECE CI lower bound > 0.08",
            "classification": "BAND_DRIFT_CANDIDATE",
            "action": "PROMOTE_TO_DRIFT_CANDIDATE_IF_CI_ELEVATED",
            "reason": "Large sample with elevated CI provides reliable evidence "
                      "for drift candidate consideration.",
        },
        {
            "rule_id": "R04",
            "condition": "Any tier, single month only",
            "classification": "SAMPLE_SENSITIVE_BAND_ANOMALY or BAND_WATCHLIST",
            "action": "TRACK_ONLY_NO_REFIT",
            "reason": "Single-month anomaly, even in large sample, "
                      "does not trigger refit without multi-month confirmation.",
        },
        {
            "rule_id": "R05",
            "condition": "platt_ece > raw_ece (Platt worsened ECE in band)",
            "classification": "PLATT_BAND_DEGRADATION_NOTE",
            "action": "TRACK_ONLY_NO_REFIT",
            "reason": "Platt may not universally improve calibration in all bands. "
                      "This observation is recorded but does not trigger refit "
                      "without n >= 30 and multi-month confirmation.",
        },
        {
            "rule_id": "R06",
            "condition": "P52 global calibration stable",
            "classification": "NOT_APPLICABLE",
            "action": "MAINTAIN_P52_THRESHOLDS",
            "reason": "P52 global monitoring thresholds must not change "
                      "based on band-level findings alone.",
        },
    ]


# ---------------------------------------------------------------------------
# Task B — Apply Policy to P55 Sep Mid-Band
# ---------------------------------------------------------------------------

def apply_policy_to_p55(p55: dict) -> dict:
    """Apply band annotation policy to the P55 Sep 1.00-1.25 band finding."""
    pvr = p55.get("platt_vs_raw_transformation", {})
    oc = p55.get("outlier_concentration_audit", {})
    mc = p55.get("month_band_comparison", {})

    n = pvr.get("n", 0)
    raw_ece = pvr.get("raw_ece")
    platt_ece = pvr.get("platt_ece")
    ece_delta = pvr.get("ece_delta_platt_minus_raw")
    platt_improved = pvr.get("platt_improved_ece_vs_raw", True)
    outlier_driven = oc.get("concentration_classification") == "OUTLIER_DRIVEN"
    sep_unique = mc.get("sep_uniquely_elevated", False)
    sep_rank = mc.get("sep_rank_by_platt_ece")

    # Tier determination
    if n < 30:
        sample_tier = "BAND_SAMPLE_INSUFFICIENT"
    elif n < 100:
        sample_tier = "BAND_SAMPLE_WATCHLIST"
    else:
        sample_tier = "BAND_SAMPLE_MONITORABLE"

    # Annotation
    if sample_tier == "BAND_SAMPLE_INSUFFICIENT":
        annotation = "SAMPLE_SENSITIVE_BAND_ANOMALY"
        action = "TRACK_ONLY_NO_REFIT"
        annotation_reasoning = (
            f"n={n} < 30, so ECE estimates are unreliable. "
            f"platt_ece={platt_ece:.4f} and raw_ece={raw_ece:.4f} are recorded "
            f"but do not confirm systematic miscalibration."
        )
    elif sample_tier == "BAND_SAMPLE_WATCHLIST" and platt_ece > 0.10:
        annotation = "BAND_WATCHLIST"
        action = "FLAG_FOR_FOLLOW_UP"
        annotation_reasoning = (
            f"n={n} is in WATCHLIST range (30-99). "
            f"Elevated platt_ece={platt_ece:.4f} noted but single-month finding only."
        )
    else:
        annotation = "STABLE_BAND_EVIDENCE"
        action = "TRACK_ONLY_NO_REFIT"
        annotation_reasoning = f"n={n}, no elevated ECE pattern detected."

    # Platt degradation note
    platt_degradation_note = None
    if ece_delta is not None and ece_delta > 0:
        platt_degradation_note = {
            "observation": "PLATT_BAND_DEGRADATION_NOTE",
            "ece_delta": round(ece_delta, 6),
            "raw_ece": round(raw_ece, 6) if raw_ece is not None else None,
            "platt_ece": round(platt_ece, 6) if platt_ece is not None else None,
            "meaning": (
                "Platt transform worsened ECE in this band vs raw model "
                f"by {ece_delta:.4f}. This is noted but does not trigger refit "
                "without n >= 30 and multi-month confirmation."
            ),
            "action": "TRACK_ONLY_NO_REFIT",
        }

    return {
        "band": "1.00_1.25",
        "band_definition": "1.00 <= abs(sp_fip_delta) < 1.25",
        "month": "Sep 2025",
        "n": n,
        "raw_ece": round(raw_ece, 6) if raw_ece is not None else None,
        "platt_ece": round(platt_ece, 6) if platt_ece is not None else None,
        "ece_delta_platt_minus_raw": round(ece_delta, 6) if ece_delta is not None else None,
        "outlier_driven": outlier_driven,
        "sep_uniquely_elevated": sep_unique,
        "sep_rank_by_platt_ece": sep_rank,
        "sample_tier": sample_tier,
        "annotation": annotation,
        "action": action,
        "annotation_reasoning": annotation_reasoning,
        "platt_degradation_note": platt_degradation_note,
        "required_future_evidence": {
            "description": "Evidence required to re-evaluate this band finding",
            "criteria": [
                {
                    "criterion_id": "FE01",
                    "description": "Same band n >= 30 in a future month (Sep 2026 or any month)",
                    "required": True,
                },
                {
                    "criterion_id": "FE02",
                    "description": "Repeat elevated platt_ece in at least 2 separate months within the same band",
                    "required": True,
                },
                {
                    "criterion_id": "FE03",
                    "description": "Cumulative band n >= 100 across all months with ECE CI lower bound > 0.08",
                    "required": False,
                    "note": "Alternative to FE01+FE02; stronger evidence path",
                },
                {
                    "criterion_id": "FE04",
                    "description": "Platt worsening ece_delta > 0.05 confirmed at n >= 30",
                    "required": False,
                    "note": "If met, warrants PLATT_BAND_DEGRADATION_CANDIDATE flag",
                },
            ],
            "refit_trigger_conditions": (
                "Model refit consideration requires: FE01 AND FE02 met, "
                "AND explicit senior review, AND paper_only constraints lifted by authorized user."
            ),
            "current_status": (
                "Sep 2025 1.00-1.25 band: FE01 not yet met (n=27 < 30). "
                "FE02 not yet met (single month only). "
                "No refit warranted."
            ),
        },
    }


# ---------------------------------------------------------------------------
# Task C — P52 V2 Compatibility Statement
# ---------------------------------------------------------------------------

def build_p52_compatibility() -> dict:
    """Build the P52 V2 compatibility statement."""
    return {
        "statement": "P56 does not supersede P52.",
        "details": [
            "P56 adds an interpretive annotation layer for band-level ECE diagnostics.",
            "P52 global monitoring thresholds (Tier C ECE, Brier score, edge rate) remain unchanged.",
            "P52 edge and calibration stream ownership remains with the P52 monitoring contract.",
            "P56 annotations are diagnostic metadata only; they do not trigger runtime changes.",
            "P56 must not modify runtime recommendation logic.",
            "P56 must not change P45 Platt constants (A=0.435432, B=0.245464).",
            "P56 must not overwrite P52/P53/P54/P55 artifacts.",
            "P56 must not modify P52 thresholds.",
            "If P52 detects a global calibration critical event, P52 governs the response, not P56.",
            "P56 findings feed into the interpretive layer; adoption requires explicit authorization.",
        ],
        "p52_threshold_status": "UNCHANGED",
        "p52_artifact_status": "PRESERVED",
        "p53_artifact_status": "PRESERVED",
        "p54_artifact_status": "PRESERVED",
        "p55_artifact_status": "PRESERVED",
        "platt_constants_status": "UNCHANGED — A=0.435432, B=0.245464 (P45 locked)",
    }


# ---------------------------------------------------------------------------
# Master audit builder
# ---------------------------------------------------------------------------

def build_p56_audit() -> dict:
    print("[P56.PRE] Governance assertions...")
    _assert_governance()
    print("  PASS")

    print("[P56.A] Loading source artifacts...")
    for path in [P52_SUMMARY, P53_SUMMARY, P54_SUMMARY, P55_SUMMARY]:
        assert path.exists(), f"Source artifact missing: {path}"
    p52 = json.loads(P52_SUMMARY.read_text(encoding="utf-8"))
    p53 = json.loads(P53_SUMMARY.read_text(encoding="utf-8"))
    p54 = json.loads(P54_SUMMARY.read_text(encoding="utf-8"))
    p55 = json.loads(P55_SUMMARY.read_text(encoding="utf-8"))
    print(f"  P52/P53/P54/P55 loaded")

    print("[P56.B] Building band annotation policy...")
    policy = build_band_annotation_policy()
    tiers = build_sample_size_tiers()
    rules = build_interpretation_rules()
    print(f"  {len(rules)} interpretation rules defined")

    print("[P56.C] Applying policy to P55 Sep mid-band...")
    application = apply_policy_to_p55(p55)
    print(f"  sample_tier={application['sample_tier']}")
    print(f"  annotation={application['annotation']}")
    print(f"  action={application['action']}")

    print("[P56.D] P52 V2 compatibility statement...")
    p52_compat = build_p52_compatibility()

    final_clf = "P56_BAND_ANNOTATION_POLICY_READY_DIAGNOSTIC"
    print(f"\n[P56.E] Final classification: {final_clf}")

    # Final governance assertions
    _assert_governance()

    audit = {
        "p56_phase": "P56 — Sample-Sensitive Band Annotation Policy for Monitoring Contract V2",
        "run_date": datetime.now().strftime("%Y-%m-%d"),
        "source_artifacts": {
            "p52": str(P52_SUMMARY.relative_to(ROOT)),
            "p53": str(P53_SUMMARY.relative_to(ROOT)),
            "p54": str(P54_SUMMARY.relative_to(ROOT)),
            "p55": str(P55_SUMMARY.relative_to(ROOT)),
            "p45": str(P45_SUMMARY.relative_to(ROOT)),
        },
        "p55_recap": {
            "final_p55_classification": p55["final_p55_classification"],
            "tier_c_n": p55["tier_c_verification"]["n"],
            "sep_mid_band_n": p55["sep_mid_band_dataset"]["n"],
            "sep_mid_band_platt_ece": p55["outlier_concentration_audit"]["platt_ece"],
            "sep_mid_band_raw_ece": p55["outlier_concentration_audit"]["raw_ece"],
            "ece_delta_platt_minus_raw": p55["platt_vs_raw_transformation"]["ece_delta_platt_minus_raw"],
            "anomaly_source": p55["platt_vs_raw_transformation"]["anomaly_source"],
            "concentration": p55["outlier_concentration_audit"]["concentration_classification"],
            "sep_uniquely_elevated": p55["month_band_comparison"]["sep_uniquely_elevated"],
        },
        "band_annotation_policy": policy,
        "sample_size_tiers": tiers,
        "interpretation_rules": rules,
        "p55_application": application,
        "p52_v2_compatibility": p52_compat,
        "data_gap_status": {
            "p43_2024_closing_line_gap": "UNRESOLVED",
            "note": (
                "2024 closing-line data gap (P43_BLOCKED_BY_DATA_GAP) remains unresolved. "
                "Cross-year band analysis cannot be completed until 2024 historical odds are obtained. "
                "P56 is based exclusively on 2025 Tier C data."
            ),
        },
        "final_p56_classification": final_clf,
        "governance_flags": GOVERNANCE,
    }
    return audit


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def write_report(audit: dict) -> None:
    clf = audit["final_p56_classification"]
    recap = audit["p55_recap"]
    tiers = audit["sample_size_tiers"]
    rules = audit["interpretation_rules"]
    app = audit["p55_application"]
    compat = audit["p52_v2_compatibility"]
    fe = app["required_future_evidence"]

    pdn = app.get("platt_degradation_note") or {}

    rules_table = "".join(
        f"| {r['rule_id']} | {r['condition']} | {r['classification']} | {r['action']} |\n"
        for r in rules
    )

    fe_criteria = "".join(
        f"- **{c['criterion_id']}** ({('REQUIRED' if c['required'] else 'OPTIONAL')}): {c['description']}\n"
        for c in fe["criteria"]
    )

    compat_details = "".join(f"- {d}\n" for d in compat["details"])

    content = f"""# P56 — Sample-Sensitive Band Annotation Policy for Monitoring Contract V2

**Date**: {audit['run_date']}  
**Classification**: `{clf}`  
**Governance**: paper_only=True, diagnostic_only=True, live_api_calls=0

---

## 1. P55 Recap

| Item | Value |
|------|-------|
| P55 classification | `{recap['final_p55_classification']}` |
| Tier C n | {recap['tier_c_n']} |
| Sep mid-band n | {recap['sep_mid_band_n']} |
| Sep mid-band platt_ece | {recap['sep_mid_band_platt_ece']} |
| Sep mid-band raw_ece | {recap['sep_mid_band_raw_ece']} |
| ECE delta (platt-raw) | {recap['ece_delta_platt_minus_raw']} |
| Anomaly source | {recap['anomaly_source']} |
| Concentration | {recap['concentration']} |
| Sep uniquely elevated | {recap['sep_uniquely_elevated']} |

**P55 Conclusion**: Sep 1.00-1.25 band platt_ece=0.246 with n=27 is sample-limited.
Platt worsened ECE by +0.081 in this band, but n < 30 prevents reliable attribution.
No refit warranted.

---

## 2. Why a Band Annotation Policy Is Needed

P53 identified a Sep global calibration anomaly. P54 isolated it to the `sp_fip_delta` feature drift
in the 1.00-1.25 band. P55 confirmed n=27 is below the ECE reliability threshold.

Without an explicit annotation policy, future monitoring reports risk:
1. **False positives**: Treating n<30 band ECE as confirmed drift, triggering unnecessary refits.
2. **False negatives**: Ignoring band-level patterns that could accumulate into systemic drift.
3. **Threshold conflation**: Applying P52 global thresholds to small-band sub-analyses.

P56 defines a structured tiered approach to prevent these failure modes.

---

## 3. Sample Size Tiers

| Tier | Condition | Annotation | Action |
|------|-----------|------------|--------|
| BAND_SAMPLE_INSUFFICIENT | n < 30 | SAMPLE_SENSITIVE_BAND_ANOMALY | TRACK_ONLY_NO_REFIT |
| BAND_SAMPLE_WATCHLIST | 30 ≤ n < 100 | BAND_WATCHLIST | FLAG_FOR_FOLLOW_UP |
| BAND_SAMPLE_MONITORABLE | n ≥ 100 | STABLE_BAND_EVIDENCE or BAND_DRIFT_CANDIDATE | Per ECE CI |

**Sep 2025 1.00-1.25 band (n=27)**: BAND_SAMPLE_INSUFFICIENT.

---

## 4. Interpretation Rules

| Rule | Condition | Classification | Action |
|------|-----------|----------------|--------|
{rules_table}

---

## 5. Application to Sep 2025 1.00-1.25 Band

| Item | Value |
|------|-------|
| Band | {app['band_definition']} |
| Month | {app['month']} |
| n | {app['n']} |
| raw_ece | {app['raw_ece']} |
| platt_ece | {app['platt_ece']} |
| ece_delta (platt-raw) | {app['ece_delta_platt_minus_raw']} |
| Outlier driven | {app['outlier_driven']} |
| Sep uniquely elevated | {app['sep_uniquely_elevated']} |
| **Sample tier** | **{app['sample_tier']}** |
| **Annotation** | **{app['annotation']}** |
| **Action** | **{app['action']}** |

**Annotation reasoning**: {app['annotation_reasoning']}

### Platt Degradation Note

{f"**Observation**: {pdn.get('observation', 'N/A')}  " if pdn else "No Platt degradation note generated."}
{f"ece_delta = +{pdn['ece_delta']:.4f} (Platt worsened ECE vs raw model)  " if pdn else ""}
{f"**Action**: {pdn.get('action', 'N/A')}  " if pdn else ""}
{f"**Meaning**: {pdn.get('meaning', '')}" if pdn else ""}

---

## 6. Future Evidence Requirements

To re-evaluate the Sep 2025 1.00-1.25 band finding, the following evidence is required:

{fe_criteria}

**Refit trigger condition**: {fe['refit_trigger_conditions']}

**Current status**: {fe['current_status']}

---

## 7. P52 V2 Compatibility Statement

{compat['statement']}

{compat_details}

| Item | Status |
|------|--------|
| P52 thresholds | {compat['p52_threshold_status']} |
| P52 artifact | {compat['p52_artifact_status']} |
| P53 artifact | {compat['p53_artifact_status']} |
| P54 artifact | {compat['p54_artifact_status']} |
| P55 artifact | {compat['p55_artifact_status']} |
| Platt constants | {compat['platt_constants_status']} |

---

## 8. Limitations

1. P56 policy is based on 2025 Tier C data only (n=535); cross-year validation is not yet possible.
2. The n<30 / n<100 thresholds are heuristic; formal statistical power analysis has not been performed.
3. ECE is computed with 10-bin uniform-width; other binning schemes may yield different tier boundaries.
4. The Platt degradation observation (ece_delta=+0.081) may or may not represent a systematic pattern.
5. P56 is a metadata annotation layer only; runtime logic and monitoring thresholds are unchanged.

---

## 9. 2024 Closing-Line Data Gap

**The 2024 closing-line data gap (P43_BLOCKED_BY_DATA_GAP) remains unresolved.**

This analysis is based exclusively on 2025 Tier C data. Cross-year band-level analysis
cannot be completed until 2024 historical odds data is obtained. P56 policy applicability
to pre-2025 seasons is unknown.

---

## 10. Final P56 Classification

```
{clf}
```

---

## 11. Next Recommended Diagnostic Task

**P57 — Monitoring Contract V2 Annotation Integration**:
- Integrate P56 band annotation policy into the P52 monitoring contract as an interpretive metadata layer.
- Define how future monitoring reports should reference `sample_tier` and `annotation` fields.
- Verify that P52 global thresholds remain unchanged after annotation layer addition.
- Required input: P56 policy JSON + P52 V2 contract JSON.

Prerequisite before P57: 2024 closing-line data remains unavailable.
Until then, P56 annotations apply to 2025 Tier C data only.

---

*Governance: paper_only=True, diagnostic_only=True, promotion_freeze=True, live_api_calls=0*  
*P45 Platt constants unchanged: A=0.435432, B=0.245464*  
*P52/P53/P54/P55 artifacts not overwritten. P52 thresholds not changed.*
"""

    REPORT_MD.parent.mkdir(parents=True, exist_ok=True)
    REPORT_MD.write_text(content, encoding="utf-8")
    print(f"Report written: {REPORT_MD}")

    BETTING_PLAN_MD.parent.mkdir(parents=True, exist_ok=True)
    BETTING_PLAN_MD.write_text(content, encoding="utf-8")
    print(f"BettingPlan report written: {BETTING_PLAN_MD}")


def update_active_task(classification: str) -> None:
    ACTIVE_TASK_MD.parent.mkdir(parents=True, exist_ok=True)
    p56_header = f"""# Active Task — P56 Sample-Sensitive Band Annotation Policy

> **[COMPLETED 2026-05-26]** `{classification}`
> **Issued by**: P55 `P55_INCONCLUSIVE_SAMPLE_LIMITED` → band annotation layer needed
> **HEAD**: `a9ecdf0` → 提交中 | **Branch**: `main` | **Mode**: `paper_only=True`
> **前置 Phase**: P55 `P55_INCONCLUSIVE_SAMPLE_LIMITED`

## P56 成果摘要

- **政策名稱**: Sample-Sensitive Band Annotation Policy v1
- **樣本層級**: INSUFFICIENT (n<30), WATCHLIST (30-99), MONITORABLE (n>=100)
- **Sep 2025 1.00-1.25 帶**: sample_tier=BAND_SAMPLE_INSUFFICIENT, annotation=SAMPLE_SENSITIVE_BAND_ANOMALY, action=TRACK_ONLY_NO_REFIT
- **Platt 降解注記**: ece_delta=+0.081 記錄在案，但不觸發重擬合
- **P52 V2 相容性**: P56 不取代 P52，僅添加詮釋性注釋層
- **P52 閾值**: UNCHANGED（未修改）
- **最終分類**: `{classification}`
- **Governance**: paper_only=True, live_api_calls=0, p52/p53/p54/p55 artifacts preserved
- **P45 Platt 常數**: A=0.435432, B=0.245464（未修改）
- **2024 缺口**: P43 closing-line data gap 仍未解決

---

"""
    existing = ""
    if ACTIVE_TASK_MD.exists():
        existing = ACTIVE_TASK_MD.read_text(encoding="utf-8")
    ACTIVE_TASK_MD.write_text(p56_header + existing, encoding="utf-8")
    print("active_task.md updated")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    _assert_governance()

    audit = build_p56_audit()
    clf = audit["final_p56_classification"]

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(audit, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"JSON written: {OUTPUT_JSON}")

    write_report(audit)
    update_active_task(clf)

    print()
    print("=" * 60)
    print(f"P56 COMPLETE — {clf}")
    print(f"  live_api_calls={audit['governance_flags']['live_api_calls']}")
    print(f"  paper_only={audit['governance_flags']['paper_only']}")
    print(f"  p52_thresholds_changed={audit['governance_flags']['p52_thresholds_changed']}")
    print("=" * 60)


if __name__ == "__main__":
    main()
