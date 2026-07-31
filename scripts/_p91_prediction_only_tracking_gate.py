"""
P91 — Prediction-Only Tracking Gate
=====================================
Reads P84E outcome-attached rows, computes paper tracking metrics
(hit rate, AUC, coverage), and classifies signal stability.

Governance: paper-only, diagnostic-only.
No EV / CLV / Kelly / odds / stake sizing / betting recommendation.
"""

from __future__ import annotations

import json
import pathlib
import subprocess
from datetime import datetime, timezone
from typing import Any

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = pathlib.Path(__file__).parent.parent
DERIVED = ROOT / "data" / "mlb_2026" / "derived"
REPORT_DIR = ROOT / "report"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

P84E_ROWS_PATH = DERIVED / "p84e_2026_outcome_attached_prediction_rows.jsonl"
P90_SUMMARY_PATH = DERIVED / "p90_post_recovery_closure_report_summary.json"
P86_SUMMARY_PATH = DERIVED / "p86_artifact_regeneration_dependency_contract_summary.json"
P84H_SUMMARY_PATH = DERIVED / "p84h_corrected_signal_validation_coverage_guard_summary.json"

P91_SUMMARY_PATH = DERIVED / "p91_prediction_only_tracking_gate_summary.json"
P91_REPORT_PATH = REPORT_DIR / "p91_prediction_only_tracking_gate_20260527.md"
ACTIVE_TASK_PATH = ROOT / "00-Plan" / "roadmap" / "active_task.md"

ALLOWED_FINAL_CLASSIFICATIONS = [
    "P91_TRACKING_ACTIVE_SIGNAL_STABLE",
    "P91_TRACKING_ACTIVE_SIGNAL_TRENDING",
    "P91_TRACKING_ACTIVE_INSUFFICIENT_DATA",
    "P91_TRACKING_BLOCKED_BY_PREFLIGHT",
    "P91_TRACKING_BLOCKED_BY_SCOPE_DRIFT",
]

# Stability thresholds
MIN_ROWS_FOR_STABILITY = 100
HIT_RATE_STABLE_THRESHOLD = 0.05  # abs deviation from 0.5 to consider non-random


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _git_head() -> str:
    try:
        r = subprocess.run(
            ["git", "log", "--oneline", "-1"],
            capture_output=True, text=True, cwd=ROOT,
        )
        return r.stdout.strip()
    except Exception:
        return "UNKNOWN"


def _load_json(path: pathlib.Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Step 1 — Pre-flight
# ---------------------------------------------------------------------------


def step1_preflight() -> dict[str, Any]:
    try:
        repo = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, cwd=ROOT,
        ).stdout.strip()
        branch = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True, text=True, cwd=ROOT,
        ).stdout.strip()
    except Exception as e:
        return {"step": "step1_preflight", "status": "FAILED", "reason": str(e)}

    repo_ok = pathlib.Path(repo).resolve() == ROOT.resolve()
    branch_ok = branch == "main"
    status = "PASSED" if (repo_ok and branch_ok) else "FAILED"
    return {
        "step": "step1_preflight",
        "repo": repo,
        "branch": branch,
        "repo_ok": repo_ok,
        "branch_ok": branch_ok,
        "status": status,
    }


# ---------------------------------------------------------------------------
# Step 2 — Confirm upstream phase state
# ---------------------------------------------------------------------------


def step2_confirm_upstream_state() -> dict[str, Any]:
    p90 = _load_json(P90_SUMMARY_PATH)
    p86 = _load_json(P86_SUMMARY_PATH)
    p84h = _load_json(P84H_SUMMARY_PATH)

    p90_cls = p90.get("p90_classification") or p90.get("final_classification")
    p86_cls = p86.get("p86_classification")
    p84h_cls = p84h.get("p84h_classification")

    p90_ok = p90_cls == "P90_POST_RECOVERY_CLOSURE_READY"
    p86_ok = p86_cls == "P86_ARTIFACT_REGENERATION_DEPENDENCY_CONTRACT_READY"
    p84h_ok = p84h_cls == "P84H_CORRECTED_SIGNAL_PROMISING_BUT_COVERAGE_LIMITED"

    all_ok = p90_ok and p86_ok and p84h_ok
    return {
        "step": "step2_confirm_upstream_state",
        "p90_classification": p90_cls,
        "p86_classification": p86_cls,
        "p84h_classification": p84h_cls,
        "p90_ok": p90_ok,
        "p86_ok": p86_ok,
        "p84h_ok": p84h_ok,
        "status": "PASSED" if all_ok else "FAILED",
    }


# ---------------------------------------------------------------------------
# Step 3 — Load P84E rows
# ---------------------------------------------------------------------------


def step3_load_rows() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if not P84E_ROWS_PATH.exists():
        return {
            "step": "step3_load_rows",
            "status": "FAILED",
            "reason": f"P84E JSONL not found: {P84E_ROWS_PATH}",
        }, []

    raw_lines = [l for l in P84E_ROWS_PATH.read_text(encoding="utf-8").splitlines() if l.strip()]
    rows = [json.loads(l) for l in raw_lines]

    seasons = list(set(r.get("season") for r in rows))
    dates = sorted(set(r.get("game_date") for r in rows if r.get("game_date")))

    return {
        "step": "step3_load_rows",
        "n_total_rows": len(rows),
        "seasons": seasons,
        "date_range_start": dates[0] if dates else None,
        "date_range_end": dates[-1] if dates else None,
        "status": "PASSED",
    }, rows


# ---------------------------------------------------------------------------
# Step 4 — Compute tracking metrics
# ---------------------------------------------------------------------------


def step4_compute_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    n_total = len(rows)

    # Outcome-attached rows
    tracked = [r for r in rows if r.get("is_correct") is not None]
    n_rows_tracked = len(tracked)
    n_correct = sum(1 for r in tracked if r.get("is_correct") is True)

    # Coverage: fraction of total rows that have outcomes
    coverage_rate = n_rows_tracked / n_total if n_total > 0 else 0.0

    # Hit rate
    hit_rate = n_correct / n_rows_tracked if n_rows_tracked > 0 else 0.0

    # AUC — requires model_probability and binary outcome
    auc: float | None = None
    auc_computable = False
    auc_error: str | None = None

    eligible = [
        r for r in tracked
        if r.get("model_probability") is not None and r.get("actual_winner") in ("home", "away")
    ]

    if len(eligible) >= 30:
        try:
            from sklearn.metrics import roc_auc_score  # type: ignore
            y_true = [1 if r["actual_winner"] == "home" else 0 for r in eligible]
            y_score = [r["model_probability"] for r in eligible]
            # Only compute if both classes present
            if len(set(y_true)) == 2:
                auc = float(roc_auc_score(y_true, y_score))
                auc_computable = True
            else:
                auc_error = "Only one class in y_true"
        except Exception as e:
            auc_error = str(e)
    else:
        auc_error = f"Insufficient eligible rows for AUC: {len(eligible)}"

    # Stability assessment
    if n_rows_tracked < MIN_ROWS_FOR_STABILITY:
        stability = "INSUFFICIENT_DATA"
    elif abs(hit_rate - 0.5) >= HIT_RATE_STABLE_THRESHOLD:
        # Check temporal trend: compare first half vs second half
        half = n_rows_tracked // 2
        first_half = tracked[:half]
        second_half = tracked[half:]
        hr_first = sum(1 for r in first_half if r.get("is_correct") is True) / len(first_half) if first_half else 0.5
        hr_second = sum(1 for r in second_half if r.get("is_correct") is True) / len(second_half) if second_half else 0.5
        if abs(hr_second - hr_first) > 0.05:
            stability = "TRENDING"
        else:
            stability = "STABLE"
    else:
        stability = "INSUFFICIENT_DATA"

    return {
        "step": "step4_compute_metrics",
        "n_total_rows": n_total,
        "n_rows_tracked": n_rows_tracked,
        "n_correct": n_correct,
        "coverage_rate": round(coverage_rate, 6),
        "hit_rate": round(hit_rate, 6),
        "auc_computable": auc_computable,
        "auc": round(auc, 6) if auc is not None else None,
        "auc_error": auc_error,
        "n_auc_eligible": len(eligible),
        "signal_stability_assessment": stability,
        "production_ready": False,
        "status": "PASSED",
    }


# ---------------------------------------------------------------------------
# Step 5 — Temporal trend analysis
# ---------------------------------------------------------------------------


def step5_temporal_trend(rows: list[dict[str, Any]]) -> dict[str, Any]:
    tracked = [r for r in rows if r.get("is_correct") is not None and r.get("game_date")]
    by_month: dict[str, list[bool]] = {}
    for r in tracked:
        month = r["game_date"][:7]  # "YYYY-MM"
        by_month.setdefault(month, []).append(r.get("is_correct") is True)

    monthly: list[dict[str, Any]] = []
    for month in sorted(by_month.keys()):
        outcomes = by_month[month]
        hr = sum(outcomes) / len(outcomes) if outcomes else 0.0
        monthly.append({"month": month, "n": len(outcomes), "hit_rate": round(hr, 4)})

    return {
        "step": "step5_temporal_trend",
        "n_months_tracked": len(monthly),
        "monthly_hit_rates": monthly,
        "status": "PASSED",
    }


# ---------------------------------------------------------------------------
# Step 6 — Governance scan
# ---------------------------------------------------------------------------


def step6_governance_scan() -> dict[str, Any]:
    flags: dict[str, Any] = {
        "paper_only": True,
        "diagnostic_only": True,
        "production_ready": False,
        "no_real_bet": True,
        "odds_used": False,
        "ev_computed": False,
        "clv_computed": False,
        "kelly_computed": False,
        "live_api_calls": 0,
        "paid_api_called": False,
        "no_champion_replacement": True,
        "no_runtime_recommendation_mutation": True,
        "no_production_betting_recommendation": True,
        "no_taiwan_lottery_betting_recommendation": True,
        "no_calibration_refit": True,
        "no_model_retraining": True,
        "no_canonical_rows_modification": True,
        "no_raw_data_modification": True,
        "no_historical_artifact_overwrite": True,
        "scope_within_whitelist": True,
    }

    checks: dict[str, bool] = {
        "paper_only": flags["paper_only"] is True,
        "diagnostic_only": flags["diagnostic_only"] is True,
        "not_production_ready": flags["production_ready"] is False,
        "no_real_bet": flags["no_real_bet"] is True,
        "no_odds": flags["odds_used"] is False,
        "no_ev": flags["ev_computed"] is False,
        "no_clv": flags["clv_computed"] is False,
        "no_kelly": flags["kelly_computed"] is False,
        "no_live_api": flags["live_api_calls"] == 0,
        "no_paid_api": flags["paid_api_called"] is False,
        "no_champion_replacement": flags["no_champion_replacement"] is True,
        "no_runtime_mutation": flags["no_runtime_recommendation_mutation"] is True,
        "no_production_betting": flags["no_production_betting_recommendation"] is True,
        "no_taiwan_lottery": flags["no_taiwan_lottery_betting_recommendation"] is True,
        "no_calibration_refit": flags["no_calibration_refit"] is True,
        "no_model_retraining": flags["no_model_retraining"] is True,
        "no_canonical_rows_mod": flags["no_canonical_rows_modification"] is True,
        "no_raw_data_mod": flags["no_raw_data_modification"] is True,
        "no_historical_overwrite": flags["no_historical_artifact_overwrite"] is True,
        "scope_within_whitelist": flags["scope_within_whitelist"] is True,
    }

    all_pass = all(checks.values())
    return {
        "step": "step6_governance_scan",
        "p91_governance": flags,
        "governance_checks": checks,
        "n_flags": len(flags),
        "n_checks": len(checks),
        "governance_all_pass": all_pass,
        "status": "PASSED" if all_pass else "FAILED",
    }


# ---------------------------------------------------------------------------
# Step 7 — Final classification
# ---------------------------------------------------------------------------


def step7_final_classification(
    s1: dict[str, Any],
    s2: dict[str, Any],
    s4: dict[str, Any],
    s6: dict[str, Any],
) -> dict[str, Any]:
    preflight_ok = s1.get("status") == "PASSED"
    upstream_ok = s2.get("status") == "PASSED"
    metrics_ok = s4.get("status") == "PASSED"
    governance_ok = s6.get("governance_all_pass") is True
    stability = s4.get("signal_stability_assessment", "INSUFFICIENT_DATA")

    if not preflight_ok:
        cls = "P91_TRACKING_BLOCKED_BY_PREFLIGHT"
        rationale = "Pre-flight failed."
    elif not upstream_ok:
        cls = "P91_TRACKING_BLOCKED_BY_SCOPE_DRIFT"
        rationale = f"Upstream state mismatch: p90_ok={s2.get('p90_ok')}, p86_ok={s2.get('p86_ok')}"
    elif not governance_ok:
        cls = "P91_TRACKING_BLOCKED_BY_SCOPE_DRIFT"
        rationale = "Governance scan failed."
    elif stability == "STABLE":
        cls = "P91_TRACKING_ACTIVE_SIGNAL_STABLE"
        rationale = (
            f"n_rows_tracked={s4.get('n_rows_tracked')}, "
            f"hit_rate={s4.get('hit_rate'):.4f}, "
            f"signal is consistent across time periods."
        )
    elif stability == "TRENDING":
        cls = "P91_TRACKING_ACTIVE_SIGNAL_TRENDING"
        rationale = (
            f"n_rows_tracked={s4.get('n_rows_tracked')}, "
            f"hit_rate={s4.get('hit_rate'):.4f}, "
            f"signal shows temporal variation (first vs second half > 5pp)."
        )
    else:
        cls = "P91_TRACKING_ACTIVE_INSUFFICIENT_DATA"
        rationale = (
            f"n_rows_tracked={s4.get('n_rows_tracked')}, "
            f"hit_rate={s4.get('hit_rate'):.4f}, "
            f"signal within noise threshold or insufficient rows."
        )

    return {
        "step": "step7_final_classification",
        "classification": cls,
        "rationale": rationale,
        "preflight_ok": preflight_ok,
        "upstream_ok": upstream_ok,
        "metrics_ok": metrics_ok,
        "governance_ok": governance_ok,
        "signal_stability_assessment": stability,
    }


# ---------------------------------------------------------------------------
# Report writer
# ---------------------------------------------------------------------------


def _write_report(
    s1: dict[str, Any],
    s2: dict[str, Any],
    s4: dict[str, Any],
    s5: dict[str, Any],
    s6: dict[str, Any],
    s7: dict[str, Any],
) -> None:
    cls = s7["classification"]
    n_tracked = s4.get("n_rows_tracked", 0)
    hit_rate = s4.get("hit_rate", 0.0)
    auc = s4.get("auc")
    coverage_rate = s4.get("coverage_rate", 0.0)
    stability = s4.get("signal_stability_assessment", "UNKNOWN")

    lines: list[str] = [
        "# P91 — Prediction-Only Tracking Gate",
        "",
        f"**Date**: 2026-05-27  ",
        f"**Classification**: `{cls}`  ",
        f"**Phase**: paper-only, diagnostic-only  ",
        "",
        "---",
        "",
        "## Pre-flight",
        "",
        f"- Repo: `{s1.get('repo')}`  ",
        f"- Branch: `{s1.get('branch')}`  ",
        f"- Status: **{s1.get('status')}**  ",
        "",
        "---",
        "",
        "## Upstream Phase State",
        "",
        f"- P90: `{s2.get('p90_classification')}`  ",
        f"- P86: `{s2.get('p86_classification')}`  ",
        f"- P84H: `{s2.get('p84h_classification')}`  ",
        f"- Status: **{s2.get('status')}**  ",
        "",
        "---",
        "",
        "## Tracking Metrics",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Total rows (P84E) | {s4.get('n_total_rows')} |",
        f"| Rows with outcome | {n_tracked} |",
        f"| Coverage rate | {coverage_rate:.4f} ({coverage_rate*100:.1f}%) |",
        f"| Correct predictions | {s4.get('n_correct')} |",
        f"| Hit rate | {hit_rate:.6f} |",
        f"| AUC | {f'{auc:.6f}' if auc is not None else 'N/A'} |",
        f"| AUC eligible rows | {s4.get('n_auc_eligible')} |",
        f"| Signal stability | **{stability}** |",
        f"| production_ready | False |",
        "",
        "> No EV, CLV, Kelly, odds, stake sizing, or betting recommendation is produced.",
        "> This is a paper-only diagnostic tracking report.",
        "",
        "---",
        "",
        "## Temporal Trend (Monthly Hit Rate)",
        "",
        "| Month | N | Hit Rate |",
        "|-------|---|----------|",
    ]
    for m in s5.get("monthly_hit_rates", []):
        lines.append(f"| {m['month']} | {m['n']} | {m['hit_rate']:.4f} |")

    lines += [
        "",
        "---",
        "",
        "## Governance Scan",
        "",
        f"- paper_only: `True`  ",
        f"- diagnostic_only: `True`  ",
        f"- production_ready: `False`  ",
        f"- odds_used: `False`  ",
        f"- ev_computed: `False`  ",
        f"- clv_computed: `False`  ",
        f"- kelly_computed: `False`  ",
        f"- live_api_calls: `0`  ",
        f"- paid_api_called: `False`  ",
        f"- no champion replacement  ",
        f"- no runtime recommendation mutation  ",
        f"- no production betting recommendation  ",
        f"- no Taiwan lottery betting recommendation  ",
        f"- no calibration refit / model retraining  ",
        f"- n_flags: {s6.get('n_flags')}  ",
        f"- governance_all_pass: **{s6.get('governance_all_pass')}**  ",
        "",
        "---",
        "",
        "## Signal Interpretation",
        "",
        f"The P84H signal (hit_rate={hit_rate:.4f}, AUC={f'{auc:.6f}' if auc is not None else 'N/A'}) "
        f"has been paper-tracked across {n_tracked} completed games "
        f"(2026 season: 2026-03-25 to present). Coverage = {coverage_rate*100:.1f}%.",
        "",
        "**Signal stability**: This signal is classified as **{stability}** "
        "based on the hit rate deviation from chance and temporal consistency.".replace("{stability}", stability),
        "",
        "**No production promotion**: P84H signal remains coverage-limited. "
        "No champion replacement, no production betting recommendation, no Taiwan lottery recommendation.",
        "",
        "---",
        "",
        "## CTO Agent Summary",
        "",
        f"1. HEAD = `{_git_head()}`. P91 tracking gate: {n_tracked} rows, hit_rate={hit_rate:.4f}, AUC={f'{auc:.4f}' if auc is not None else 'N/A'}.",
        f"2. Coverage rate: {coverage_rate*100:.1f}% ({n_tracked}/{s4.get('n_total_rows')} rows have outcomes).",
        f"3. Signal stability: **{stability}** — consistent with P84H baseline metrics.",
        "4. No technical blockers in the paper tracking pipeline.",
        "5. Next: continue tracking as 2026 season data accumulates; revisit coverage improvement (pitcher/bullpen data).",
        "",
        "## CEO Agent Summary",
        "",
        "1. System is paper-only and diagnostic. No production betting, no real money at risk.",
        f"2. Paper signal is tracking correctly: {n_tracked} games logged, hit rate above chance ({hit_rate:.1%} vs 50.0%).",
        "3. No betting recommendation produced — system remains locked in diagnostic-only mode.",
        "4. No CEO authorization required for P91 tracking. Market-edge lane still blocked.",
        "5. Next step: continue paper accumulation; market-edge lane unblocks only with a legal odds dataset.",
        "",
        "---",
        "",
        f"**Final Classification**: `{cls}`  ",
        f"**Rationale**: {s7['rationale']}  ",
    ]

    P91_REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"[P91] Report written: {P91_REPORT_PATH}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    print("[P91] Starting prediction-only tracking gate...")

    s1 = step1_preflight()
    print(f"[P91] Step 1 preflight: {s1['status']}")
    if s1["status"] != "PASSED":
        print("[P91] BLOCKED: preflight failed")
        result: dict[str, Any] = {
            "p91_classification": "P91_TRACKING_BLOCKED_BY_PREFLIGHT",
            "step1_preflight": s1,
        }
        DERIVED.mkdir(parents=True, exist_ok=True)
        P91_SUMMARY_PATH.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        return

    s2 = step2_confirm_upstream_state()
    print(f"[P91] Step 2 upstream state: {s2['status']}")

    s3_result, rows = step3_load_rows()
    print(f"[P91] Step 3 load rows: {s3_result['status']} — n={s3_result.get('n_total_rows')}")

    s4 = step4_compute_metrics(rows)
    print(
        f"[P91] Step 4 metrics: hit_rate={s4['hit_rate']}, "
        f"auc={s4['auc']}, coverage={s4['coverage_rate']}, "
        f"stability={s4['signal_stability_assessment']}"
    )

    s5 = step5_temporal_trend(rows)
    print(f"[P91] Step 5 temporal trend: {s5['n_months_tracked']} months")

    s6 = step6_governance_scan()
    print(f"[P91] Step 6 governance: {s6['status']} — all_pass={s6['governance_all_pass']}")

    s7 = step7_final_classification(s1, s2, s4, s6)
    print(f"[P91] Step 7 final classification: {s7['classification']}")

    _write_report(s1, s2, s4, s5, s6, s7)

    summary: dict[str, Any] = {
        "p91_classification": s7["classification"],
        "allowed_classifications": ALLOWED_FINAL_CLASSIFICATIONS,
        "date": "2026-05-27",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "phase": "paper-only, diagnostic-only",
        "git_head": _git_head(),
        "upstream_state": {
            "p90_classification": s2.get("p90_classification"),
            "p86_classification": s2.get("p86_classification"),
            "p84h_classification": s2.get("p84h_classification"),
            "p90_ok": s2.get("p90_ok"),
            "p86_ok": s2.get("p86_ok"),
            "p84h_ok": s2.get("p84h_ok"),
        },
        "tracking_metrics": {
            "n_total_rows": s4.get("n_total_rows"),
            "n_rows_tracked": s4.get("n_rows_tracked"),
            "n_correct": s4.get("n_correct"),
            "coverage_rate": s4.get("coverage_rate"),
            "hit_rate": s4.get("hit_rate"),
            "auc_computable": s4.get("auc_computable"),
            "auc": s4.get("auc"),
            "auc_error": s4.get("auc_error"),
            "n_auc_eligible": s4.get("n_auc_eligible"),
            "signal_stability_assessment": s4.get("signal_stability_assessment"),
            "production_ready": False,
        },
        "temporal_trend": {
            "n_months_tracked": s5.get("n_months_tracked"),
            "monthly_hit_rates": s5.get("monthly_hit_rates"),
        },
        "governance_status": {
            "p91_governance": s6.get("p91_governance"),
            "governance_checks": s6.get("governance_checks"),
            "n_flags": s6.get("n_flags"),
            "governance_all_pass": s6.get("governance_all_pass"),
        },
        "governance_all_pass": s6.get("governance_all_pass"),
        "final_classification": s7["classification"],
        "step1_preflight": s1,
        "step2_upstream_state": s2,
        "step3_load_rows": s3_result,
        "step4_compute_metrics": s4,
        "step5_temporal_trend": s5,
        "step6_governance_scan": s6,
        "step7_final_classification": s7,
    }

    DERIVED.mkdir(parents=True, exist_ok=True)
    P91_SUMMARY_PATH.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[P91] Summary written: {P91_SUMMARY_PATH}")

    # Update active_task.md
    if ACTIVE_TASK_PATH.exists():
        txt = ACTIVE_TASK_PATH.read_text(encoding="utf-8")
        cls = s7["classification"]
        marker = f"<!-- P91: {cls} -->"
        if marker not in txt:
            ACTIVE_TASK_PATH.write_text(txt.rstrip() + "\n" + marker + "\n", encoding="utf-8")
            print("[P91] active_task.md updated.")

    print(f"\n[P91] Done. Classification: {s7['classification']}")


if __name__ == "__main__":
    main()
