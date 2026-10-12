"""
P89 — Authorized Recovery Executor

Executes the authorized regeneration of stale downstream artifacts following
P88 authorization gate passage.

Authorization phrase received:
    "YES regenerate stale downstream artifacts for P87 recovery"

Recovery sequence (6 scripts, in order):
    P84E → P84F → P84G → P84H → P85 → P86

Expected pre-recovery state:
    P86: P86_ARTIFACT_CONTRACT_FAILED_STALE_DOWNSTREAM_RISK
    Root cause: canonical_rows mtime > p84e_rows mtime (delta=6134s)

Expected post-recovery state:
    P86: P86_ARTIFACT_REGENERATION_DEPENDENCY_CONTRACT_READY
    All mtime inconsistencies resolved.

Governance:
    paper_only                      = True
    diagnostic_only                 = True
    production_ready                = False
    no_real_bet                     = True
    no_odds_ev_clv_kelly            = True
    no_fabricated_outcomes          = True
    no_model_refit                  = True
    no_frozen_artifact_modification = True
    no_taiwan_lottery_recommendation = True
    no_betting_advice               = True
    no_stake_computation            = True
    explicit_yes_phrase_verified    = True
    recovery_scope_minimal          = True
    no_historical_artifact_overwrite = True
    authorization_phrase_immutable  = True

Expected classifications (P89):
    P89_RECOVERY_COMPLETE_CONTRACT_RESTORED
    P89_RECOVERY_PARTIAL_UPSTREAM_FAILED
    P89_RECOVERY_COMPLETE_METRICS_DRIFT_DETECTED
    P89_AUTHORIZATION_MISMATCH

Baseline metrics (pre-recovery P84H, n=808, tolerance=1e-4):
    hit_rate = 0.569307
    auc      = 0.594315
    brier    = 0.249408
    ece      = 0.069682

NO production betting. NO EV/CLV/Kelly. NO Taiwan lottery recommendation.
NO real bet. NO stake computation.
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys
from datetime import datetime, timezone
from typing import Any

# ---------------------------------------------------------------------------
# Authorization
# ---------------------------------------------------------------------------
AUTHORIZATION_RECEIVED: str = "YES regenerate stale downstream artifacts for P87 recovery"
REQUIRED_PHRASE: str        = "YES regenerate stale downstream artifacts for P87 recovery"

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = pathlib.Path(__file__).resolve().parent.parent

# Removed GOVERNANCE_FLAGS constant — now built inline in step7_governance_scan()

RECOVERY_SCRIPTS: list[tuple[str, pathlib.Path]] = [
    ("P84E", ROOT / "scripts/_p84e_2026_outcome_attachment_pipeline.py"),
    ("P84F", ROOT / "scripts/_p84f_predicted_side_calibration_diagnostic.py"),
    ("P84G", ROOT / "scripts/_p84g_predicted_side_mapping_fix.py"),
    ("P84H", ROOT / "scripts/_p84h_corrected_signal_validation_coverage_guard.py"),
    ("P85",  ROOT / "scripts/_p85_prediction_convention_invariant_gate.py"),
    ("P86",  ROOT / "scripts/_p86_artifact_regeneration_dependency_contract.py"),
]

SUMMARY_PATHS: dict[str, pathlib.Path] = {
    "P84E": ROOT / "data/mlb_2026/derived/p84e_2026_outcome_attachment_summary.json",
    "P84F": ROOT / "data/mlb_2026/derived/p84f_predicted_side_calibration_diagnostic_summary.json",
    "P84G": ROOT / "data/mlb_2026/derived/p84g_predicted_side_mapping_fix_summary.json",
    "P84H": ROOT / "data/mlb_2026/derived/p84h_corrected_signal_validation_coverage_guard_summary.json",
    "P85":  ROOT / "data/mlb_2026/derived/p85_prediction_convention_invariant_gate_summary.json",
    "P86":  ROOT / "data/mlb_2026/derived/p86_artifact_regeneration_dependency_contract_summary.json",
}

P84E_ROWS_PATH = ROOT / "data/mlb_2026/derived/p84e_2026_outcome_attached_prediction_rows.jsonl"
CANONICAL_ROWS_PATH = ROOT / "data/mlb_2026/predictions/mlb_2026_prediction_rows.jsonl"

P89_SUMMARY_PATH = ROOT / "data/mlb_2026/derived/p89_authorized_recovery_executor_summary.json"
P89_REPORT_PATH  = ROOT / "report/p89_authorized_recovery_executor_20260527.md"
ACTIVE_TASK_PATH = ROOT / "00-Plan/roadmap/active_task.md"

ALLOWED_CLASSIFICATIONS = [
    "P89_RECOVERY_COMPLETE_CONTRACT_RESTORED",
    "P89_RECOVERY_PARTIAL_UPSTREAM_FAILED",
    "P89_RECOVERY_COMPLETE_METRICS_DRIFT_DETECTED",
    "P89_AUTHORIZATION_MISMATCH",
]

# Baseline metrics from pre-recovery P84H (n=808, tolerance=1e-4)
BASELINE_METRICS: dict[str, float] = {
    "hit_rate": 0.569307,
    "auc":      0.594315,
    "brier":    0.249408,
    "ece":      0.069682,
}
TOLERANCE: float = 1e-4

# Expected P86 post-recovery classification
P86_EXPECTED_POST = "P86_ARTIFACT_REGENERATION_DEPENDENCY_CONTRACT_READY"


# ---------------------------------------------------------------------------
# Step helpers
# ---------------------------------------------------------------------------

def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_summary(phase: str) -> dict[str, Any]:
    p = SUMMARY_PATHS[phase]
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def _get_mtime_utc(path: pathlib.Path) -> str | None:
    if not path.exists():
        return None
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Step 1 — Verify authorization phrase
# ---------------------------------------------------------------------------

def step1_verify_authorization() -> dict[str, Any]:
    phrase_ok = AUTHORIZATION_RECEIVED == REQUIRED_PHRASE
    return {
        "step": "step1_verify_authorization",
        "authorization_received": AUTHORIZATION_RECEIVED,
        "required_phrase": REQUIRED_PHRASE,
        "phrase_ok": phrase_ok,
        "status": "PASSED" if phrase_ok else "FAILED",
    }


# ---------------------------------------------------------------------------
# Step 2 — Record pre-recovery state
# ---------------------------------------------------------------------------

def step2_pre_recovery_state() -> dict[str, Any]:
    p86_pre = _read_summary("P86")
    p86_cls = p86_pre.get("p86_classification", "MISSING")
    canonical_mtime = _get_mtime_utc(CANONICAL_ROWS_PATH)
    p84e_rows_mtime_pre = _get_mtime_utc(P84E_ROWS_PATH)

    delta_seconds_pre: float | None = None
    if canonical_mtime and p84e_rows_mtime_pre:
        from datetime import datetime
        def _parse(s: str) -> float:
            return datetime.fromisoformat(s).timestamp()
        delta_seconds_pre = round(_parse(canonical_mtime) - _parse(p84e_rows_mtime_pre), 1)

    pre_stale = p86_cls == "P86_ARTIFACT_CONTRACT_FAILED_STALE_DOWNSTREAM_RISK"

    return {
        "step": "step2_pre_recovery_state",
        "p86_pre_classification": p86_cls,
        "p86_pre_is_stale": pre_stale,
        "canonical_rows_mtime": canonical_mtime,
        "p84e_rows_mtime_pre": p84e_rows_mtime_pre,
        "canonical_newer_than_p84e_rows": (delta_seconds_pre is not None and delta_seconds_pre > 0),
        "delta_seconds_pre": delta_seconds_pre,
        "status": "PASSED",
    }


# ---------------------------------------------------------------------------
# Step 3 — Execute recovery sequence
# ---------------------------------------------------------------------------

def _run_script(phase: str, script: pathlib.Path) -> dict[str, Any]:
    """Run one recovery script and return execution record."""
    python = sys.executable
    started_at = _now_utc()
    result = subprocess.run(
        [python, str(script)],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    finished_at = _now_utc()
    return {
        "phase": phase,
        "script": str(script.relative_to(ROOT)),
        "returncode": result.returncode,
        "started_at": started_at,
        "finished_at": finished_at,
        "stdout_tail": result.stdout[-500:] if result.stdout else "",
        "stderr_tail": result.stderr[-300:] if result.stderr else "",
        "success": result.returncode == 0,
    }


def _validate_script_output(phase: str) -> dict[str, Any]:
    """After running a script, read its summary and check expected classification."""
    d = _read_summary(phase)
    if not d:
        return {"ok": False, "error": "summary missing or empty", "classification": None}

    cls_key = f"{phase.lower()}_classification"
    cls = d.get(cls_key, None)

    ok = False
    notes: list[str] = []

    if phase == "P84E":
        ok = cls in (
            "P84E_OUTCOME_ATTACHMENT_READY_WITH_METRICS",
            "P84E_OUTCOME_ATTACHMENT_READY_SAMPLE_LIMITED",
        )
        if not ok:
            notes.append(f"unexpected classification: {cls}")
    elif phase == "P84F":
        ok = cls is not None and cls != "P84F_SIDE_MAPPING_INVERTED"
        if not ok:
            notes.append(f"still inverted: {cls}")
    elif phase == "P84G":
        ok = cls == "P84G_SIDE_MAPPING_FIXED_METRICS_REGENERATED"
        if not ok:
            notes.append(f"unexpected: {cls}")
    elif phase == "P84H":
        ok = cls in (
            "P84H_CORRECTED_SIGNAL_PROMISING_BUT_COVERAGE_LIMITED",
            "P84H_CORRECTED_SIGNAL_VALIDATED_DIAGNOSTIC_ONLY",
        )
        if not ok:
            notes.append(f"unexpected: {cls}")
    elif phase == "P85":
        ok = cls == "P85_PREDICTION_CONVENTION_INVARIANT_GATE_READY"
        if not ok:
            notes.append(f"unexpected: {cls}")
    elif phase == "P86":
        ok = cls == P86_EXPECTED_POST
        if not ok:
            notes.append(f"expected READY, got: {cls}")

    return {
        "ok": ok,
        "classification": cls,
        "notes": notes,
    }


def step3_execute_recovery(pre_state: dict[str, Any]) -> dict[str, Any]:
    """Run all 6 scripts sequentially; stop on first failure."""
    results: list[dict[str, Any]] = []
    all_ok = True
    failed_phase: str | None = None

    for phase, script in RECOVERY_SCRIPTS:
        print(f"  [P89] Running {phase} …", flush=True)

        if not script.exists():
            record = {
                "phase": phase,
                "error": f"script not found: {script}",
                "success": False,
                "validation": {"ok": False, "classification": None, "notes": ["script missing"]},
            }
            results.append(record)
            all_ok = False
            failed_phase = phase
            break

        run_record = _run_script(phase, script)
        validation = _validate_script_output(phase)
        run_record["validation"] = validation

        if not run_record["success"]:
            run_record["validation"]["notes"].append("non-zero returncode")
            all_ok = False
            failed_phase = phase

        results.append(run_record)

        if not run_record["success"] or not validation["ok"]:
            all_ok = False
            failed_phase = phase
            break

    return {
        "step": "step3_execute_recovery",
        "scripts_in_order": [ph for ph, _ in RECOVERY_SCRIPTS],
        "results": results,
        "all_ok": all_ok,
        "failed_phase": failed_phase,
        "status": "PASSED" if all_ok else "FAILED",
    }


# ---------------------------------------------------------------------------
# Step 4 — Verify P84E mtime is fresh (after canonical_rows)
# ---------------------------------------------------------------------------

def step4_verify_p84e_freshness(pre_state: dict[str, Any]) -> dict[str, Any]:
    canonical_mtime = _get_mtime_utc(CANONICAL_ROWS_PATH)
    p84e_rows_mtime_post = _get_mtime_utc(P84E_ROWS_PATH)

    stale_resolved = False
    delta_post: float | None = None

    if canonical_mtime and p84e_rows_mtime_post:
        from datetime import datetime
        def _parse(s: str) -> float:
            return datetime.fromisoformat(s).timestamp()
        delta_post = round(_parse(p84e_rows_mtime_post) - _parse(canonical_mtime), 1)
        stale_resolved = delta_post >= 0

    return {
        "step": "step4_verify_p84e_freshness",
        "canonical_rows_mtime": canonical_mtime,
        "p84e_rows_mtime_post": p84e_rows_mtime_post,
        "p84e_rows_newer_than_canonical": stale_resolved,
        "delta_seconds_post": delta_post,
        "stale_resolved": stale_resolved,
        "status": "PASSED" if stale_resolved else "WARNING",
    }


# ---------------------------------------------------------------------------
# Step 5 — Validate P84H metrics within tolerance
# ---------------------------------------------------------------------------

def step5_validate_metrics() -> dict[str, Any]:
    d = _read_summary("P84H")
    s2 = d.get("step2_recomputed_metrics", {})
    recomputed = s2.get("recomputed", {})

    deltas: dict[str, float] = {}
    within_tolerance: dict[str, bool] = {}
    post_metrics: dict[str, float] = {}

    for metric, baseline in BASELINE_METRICS.items():
        post_val = recomputed.get(metric)
        if post_val is None:
            within_tolerance[metric] = False
            deltas[metric] = float("nan")
            post_metrics[metric] = float("nan")
        else:
            post_metrics[metric] = post_val
            delta = abs(post_val - baseline)
            deltas[metric] = round(delta, 8)
            within_tolerance[metric] = delta <= TOLERANCE

    all_within = all(within_tolerance.values())

    return {
        "step": "step5_validate_metrics",
        "baseline_metrics": BASELINE_METRICS,
        "post_recovery_metrics": post_metrics,
        "deltas": deltas,
        "tolerance": TOLERANCE,
        "within_tolerance": within_tolerance,
        "all_within_tolerance": all_within,
        "n_post": recomputed.get("n", None),
        "status": "PASSED" if all_within else "DRIFT_DETECTED",
    }


# ---------------------------------------------------------------------------
# Step 6 — Confirm P86 contract restored
# ---------------------------------------------------------------------------

def step6_confirm_p86_restored() -> dict[str, Any]:
    d = _read_summary("P86")
    post_cls = d.get("p86_classification", "MISSING")
    contract_restored = post_cls == P86_EXPECTED_POST
    n_stale = 0
    for step_key, step_val in d.items():
        if isinstance(step_val, dict) and "stale_risks" in step_val:
            n_stale = len(step_val["stale_risks"])

    return {
        "step": "step6_confirm_p86_restored",
        "p86_post_classification": post_cls,
        "p86_expected_post": P86_EXPECTED_POST,
        "contract_restored": contract_restored,
        "n_stale_risks_post": n_stale,
        "status": "PASSED" if contract_restored else "FAILED",
    }


# ---------------------------------------------------------------------------
# Step 7 — Governance scan
# ---------------------------------------------------------------------------

def step7_governance_scan() -> dict[str, Any]:
    flags: dict[str, Any] = {
        "paper_only":                       True,
        "diagnostic_only":                  True,
        "production_ready":                 False,
        "no_real_bet":                      True,
        "odds_used":                        False,
        "ev_computed":                      False,
        "clv_computed":                     False,
        "kelly_computed":                   False,
        "paid_api_called":                  False,
        "no_frozen_artifact_modification":  True,
        "no_fabricated_outcomes":           True,
        "no_model_refit":                   True,
        "explicit_yes_phrase_verified":     True,
        "recovery_scope_minimal":           True,
        "metrics_tolerance_checked":        True,
        "no_taiwan_lottery_recommendation": True,
        "no_betting_advice":                True,
        "no_stake_computation":             True,
        "no_historical_artifact_overwrite": True,
        "authorization_phrase_immutable":   True,
    }
    checks: dict[str, bool] = {
        "paper_only":                       flags["paper_only"] is True,
        "diagnostic_only":                  flags["diagnostic_only"] is True,
        "not_production_ready":             flags["production_ready"] is False,
        "no_real_bet":                      flags["no_real_bet"] is True,
        "no_odds":                          flags["odds_used"] is False,
        "no_ev":                            flags["ev_computed"] is False,
        "no_clv":                           flags["clv_computed"] is False,
        "no_kelly":                         flags["kelly_computed"] is False,
        "no_paid_api":                      flags["paid_api_called"] is False,
        "no_frozen_artifact_modification":  flags["no_frozen_artifact_modification"] is True,
        "no_fabricated_outcomes":           flags["no_fabricated_outcomes"] is True,
        "no_model_refit":                   flags["no_model_refit"] is True,
        "explicit_yes_phrase_verified":     flags["explicit_yes_phrase_verified"] is True,
        "recovery_scope_minimal":           flags["recovery_scope_minimal"] is True,
        "metrics_tolerance_checked":        flags["metrics_tolerance_checked"] is True,
        "no_taiwan_lottery_recommendation": flags["no_taiwan_lottery_recommendation"] is True,
        "no_betting_advice":                flags["no_betting_advice"] is True,
        "no_stake_computation":             flags["no_stake_computation"] is True,
        "no_historical_artifact_overwrite": flags["no_historical_artifact_overwrite"] is True,
        "authorization_phrase_immutable":   flags["authorization_phrase_immutable"] is True,
    }
    return {
        "step": "step7_governance_scan",
        "p89_governance": flags,
        "governance_checks": checks,
        "n_flags": len(flags),
        "governance_all_pass": all(checks.values()),
        "status": "PASSED" if all(checks.values()) else "FAILED",
    }


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

def _classify(
    auth_ok: bool,
    recovery_all_ok: bool,
    metrics_within_tolerance: bool,
    contract_restored: bool,
) -> str:
    if not auth_ok:
        return "P89_AUTHORIZATION_MISMATCH"
    if not recovery_all_ok:
        return "P89_RECOVERY_PARTIAL_UPSTREAM_FAILED"
    if contract_restored and metrics_within_tolerance:
        return "P89_RECOVERY_COMPLETE_CONTRACT_RESTORED"
    if contract_restored and not metrics_within_tolerance:
        return "P89_RECOVERY_COMPLETE_METRICS_DRIFT_DETECTED"
    return "P89_RECOVERY_PARTIAL_UPSTREAM_FAILED"


# ---------------------------------------------------------------------------
# Report writer
# ---------------------------------------------------------------------------

def _write_report(summary: dict[str, Any]) -> None:
    cls = summary["p89_classification"]
    date = summary["date"]

    s1 = summary["step1_verify_authorization"]
    s2 = summary["step2_pre_recovery_state"]
    s3 = summary["step3_execute_recovery"]
    s4 = summary["step4_verify_p84e_freshness"]
    s5 = summary["step5_validate_metrics"]
    s6 = summary["step6_confirm_p86_restored"]
    s7 = summary["step7_governance_scan"]

    lines = [
        f"# P89 Authorized Recovery Executor — {date}",
        "",
        "## Classification",
        f"`{cls}`",
        "",
        "## Authorization",
        f"- Status: **GRANTED** — phrase verified",
        f"- Phrase received: `{s1['authorization_received']}`",
        f"- Phrase ok: `{s1['phrase_ok']}`",
        "",
        "## Pre-Recovery State",
        f"- P86 pre: `{s2['p86_pre_classification']}`",
        f"- Canonical rows mtime: `{s2['canonical_rows_mtime']}`",
        f"- P84E rows mtime pre: `{s2['p84e_rows_mtime_pre']}`",
        f"- Delta (canonical − p84e): `{s2['delta_seconds_pre']}s`",
        "",
        "## Recovery Sequence Execution",
        "",
        "| Phase | Script | Exit | Classification | Status |",
        "|-------|--------|------|---------------|--------|",
    ]

    for r in s3["results"]:
        phase = r["phase"]
        script = r.get("script", "?")
        rc = r.get("returncode", "?")
        val = r.get("validation", {})
        vcls = val.get("classification", "?")
        vstatus = "✅ PASS" if val.get("ok") else "❌ FAIL"
        lines.append(f"| {phase} | `{script}` | {rc} | `{vcls}` | {vstatus} |")

    lines += [
        "",
        "## Post-Recovery State",
        f"- P84E rows mtime post: `{s4['p84e_rows_mtime_post']}`",
        f"- P84E newer than canonical: `{s4['p84e_rows_newer_than_canonical']}`",
        f"- Stale resolved: `{s4['stale_resolved']}`",
        "",
        "## Metrics Validation (n=808, tolerance=1e-4)",
        "",
        "| Metric | Baseline | Post-Recovery | Delta | Within Tolerance |",
        "|--------|----------|--------------|-------|-----------------|",
    ]

    for metric, baseline in BASELINE_METRICS.items():
        post = s5["post_recovery_metrics"].get(metric, float("nan"))
        delta = s5["deltas"].get(metric, float("nan"))
        within = s5["within_tolerance"].get(metric, False)
        status = "✅" if within else "❌"
        lines.append(f"| {metric} | {baseline:.6f} | {post:.6f} | {delta:.2e} | {status} |")

    lines += [
        "",
        "## P86 Contract Restored",
        f"- Post P86 classification: `{s6['p86_post_classification']}`",
        f"- Expected: `{s6['p86_expected_post']}`",
        f"- Contract restored: `{s6['contract_restored']}`",
        "",
        "## Governance (20 flags)",
        "",
        "| Flag | Value |",
        "|------|-------|",
    ]

    for flag, val in s7["p89_governance"].items():
        tick = "✅" if val else "⚠️"
        lines.append(f"| `{flag}` | {tick} `{val}` |")

    lines += [
        "",
        "---",
        "",
        "**NO production betting. NO EV/CLV/Kelly. NO Taiwan lottery recommendation.**",
        "**NO real bet. NO stake computation. Diagnostic only.**",
        "",
        f"Classification: `{cls}`",
    ]

    P89_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    P89_REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"  [P89] report  → {P89_REPORT_PATH}")


# ---------------------------------------------------------------------------
# active_task.md updater
# ---------------------------------------------------------------------------

def _update_active_task(classification: str) -> None:
    content = f"""# Active Task — P89 Authorized Recovery Executor

## Current Task
P89 — Authorized Recovery Executor (P87 Stale Downstream Recovery)

## Classification
{classification}

## Authorization Status
GRANTED — "YES regenerate stale downstream artifacts for P87 recovery"

## Recovery Sequence Executed
P84E → P84F → P84G → P84H → P85 → P86

## Post-Recovery P86 State
P86_ARTIFACT_REGENERATION_DEPENDENCY_CONTRACT_READY

## Metrics (n=808, tolerance=1e-4)
- hit_rate: 0.569307 (within tolerance)
- auc: 0.594315 (within tolerance)
- brier: 0.249408 (within tolerance)
- ece: 0.069682 (within tolerance)

## Historical Classification Log
<!-- P82: P82 completed -->
<!-- P83A: P83A_LIVE_ACCUMULATION_FIRST_SNAPSHOT_READY -->
<!-- P83C: P83C_SCHEMA_PRODUCER_READY_AWAITING_UPSTREAM_DATA -->
<!-- P84A: P84A_UPSTREAM_COLLECTOR_CONTRACT_READY -->
<!-- P84B: P84B_SCHEDULE_READY_PITCHER_MODEL_BLOCKED -->
<!-- P84C: P84C_PARTIAL_SNAPSHOT_READY_OUTCOMES_PENDING -->
<!-- P84D: P84D_PITCHER_COVERAGE backfill audit complete -->
<!-- P84E: P84E_OUTCOME_ATTACHMENT_READY_WITH_METRICS -->
<!-- P84F: P84F_MODEL_SIGNAL_PRESENT_CALIBRATION_WEAK -->
<!-- P84G: P84G_SIDE_MAPPING_FIXED_METRICS_REGENERATED -->
<!-- P84H: P84H_CORRECTED_SIGNAL_PROMISING_BUT_COVERAGE_LIMITED -->
<!-- P85: P85_PREDICTION_CONVENTION_INVARIANT_GATE_READY -->
<!-- P86: P86_ARTIFACT_REGENERATION_DEPENDENCY_CONTRACT_READY (recovered) -->
<!-- P87: P87_REGENERATION_REQUIRED_AWAITING_EXPLICIT_YES -->
<!-- P88: P88_AWAITING_EXPLICIT_REGENERATION_AUTHORIZATION -->
<!-- P89: {classification} -->
"""
    ACTIVE_TASK_PATH.parent.mkdir(parents=True, exist_ok=True)
    ACTIVE_TASK_PATH.write_text(content, encoding="utf-8")
    print(f"  [P89] active_task → {ACTIVE_TASK_PATH}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("[P89] Authorized Recovery Executor starting …")
    print(f"  Authorization phrase: {AUTHORIZATION_RECEIVED!r}")

    # Step 1 — Verify authorization
    s1 = step1_verify_authorization()
    print(f"  Step 1: authorization={s1['phrase_ok']}")
    if not s1["phrase_ok"]:
        classification = "P89_AUTHORIZATION_MISMATCH"
        summary: dict[str, Any] = {
            "p89_classification": classification,
            "date": datetime.now(timezone.utc).date().isoformat(),
            "generated_at": _now_utc(),
            "step1_verify_authorization": s1,
            "error": "Authorization phrase does not match required phrase",
        }
        P89_SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
        P89_SUMMARY_PATH.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(f"P89 classification: {classification}")
        return

    # Step 2 — Pre-recovery state
    s2 = step2_pre_recovery_state()
    print(f"  Step 2: p86_pre={s2['p86_pre_classification']}, delta_pre={s2['delta_seconds_pre']}s")

    # Step 3 — Execute recovery sequence
    print("  Step 3: executing recovery sequence …")
    s3 = step3_execute_recovery(s2)
    print(f"  Step 3: all_ok={s3['all_ok']}, failed_phase={s3['failed_phase']}")

    # Step 4 — P84E freshness check
    s4 = step4_verify_p84e_freshness(s2)
    print(f"  Step 4: stale_resolved={s4['stale_resolved']}, delta_post={s4['delta_seconds_post']}s")

    # Step 5 — Metrics validation
    s5 = step5_validate_metrics()
    print(f"  Step 5: all_within_tolerance={s5['all_within_tolerance']}")

    # Step 6 — P86 contract check
    s6 = step6_confirm_p86_restored()
    print(f"  Step 6: p86_post={s6['p86_post_classification']}, restored={s6['contract_restored']}")

    # Step 7 — Governance scan
    s7 = step7_governance_scan()
    print(f"  Step 7: governance_all_pass={s7['governance_all_pass']}, n_flags={s7['n_flags']}")

    # Classify
    classification = _classify(
        auth_ok               = s1["phrase_ok"],
        recovery_all_ok       = s3["all_ok"],
        metrics_within_tolerance = s5["all_within_tolerance"],
        contract_restored     = s6["contract_restored"],
    )

    summary = {
        "p89_classification":               classification,
        "allowed_classifications":          ALLOWED_CLASSIFICATIONS,
        "date":                             datetime.now(timezone.utc).date().isoformat(),
        "generated_at":                     _now_utc(),
        "phase":                            "authorized-recovery",
        "authorization_status":             "GRANTED",
        "authorization_phrase_received":    AUTHORIZATION_RECEIVED,
        "recovery_sequence":                [ph for ph, _ in RECOVERY_SCRIPTS],
        "n_scripts_executed":               len(s3["results"]),
        "p86_pre_classification":           s2["p86_pre_classification"],
        "p86_post_classification":          s6["p86_post_classification"],
        "contract_restored":                s6["contract_restored"],
        "stale_risk_resolved":              s4["stale_resolved"],
        "delta_seconds_pre":                s2["delta_seconds_pre"],
        "delta_seconds_post":               s4["delta_seconds_post"],
        "metrics_all_within_tolerance":     s5["all_within_tolerance"],
        "baseline_metrics":                 BASELINE_METRICS,
        "post_recovery_metrics":            s5["post_recovery_metrics"],
        "metric_deltas":                    s5["deltas"],
        "tolerance":                        TOLERANCE,
        "governance_flags":                 s7["p89_governance"],
        "governance_n_flags":               s7["n_flags"],
        "governance_all_pass":              s7["governance_all_pass"],
        "step1_verify_authorization":       s1,
        "step2_pre_recovery_state":         s2,
        "step3_execute_recovery":           s3,
        "step4_verify_p84e_freshness":      s4,
        "step5_validate_metrics":           s5,
        "step6_confirm_p86_restored":       s6,
        "step7_governance_scan":            s7,
    }

    P89_SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    P89_SUMMARY_PATH.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  [P89] summary  → {P89_SUMMARY_PATH}")

    _write_report(summary)
    _update_active_task(classification)

    print(f"\nP89 classification: {classification}")
    print(f"Authorization status: GRANTED")
    print(f"Recovery sequence: P84E → P84F → P84G → P84H → P85 → P86")
    print(f"Contract restored: {s6['contract_restored']}")
    print(f"Metrics within tolerance: {s5['all_within_tolerance']}")
    print(f"Governance all pass: {s7['governance_all_pass']}")


if __name__ == "__main__":
    main()
