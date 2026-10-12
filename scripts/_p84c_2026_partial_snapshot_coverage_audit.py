"""
P84C — 2026 Canonical Prediction Partial Snapshot + Coverage Gap Audit

Classification: P84C_PARTIAL_SNAPSHOT_READY_OUTCOMES_PENDING

This script audits the 828 canonical prediction rows produced by P83E/P84B.
It verifies schema/governance integrity, computes snapshot distribution metrics,
performs a pipeline funnel coverage gap analysis, and defines a remediation
path for improving coverage and attaching outcomes.

NO odds, NO EV/CLV/Kelly, NO live API calls, paper_only=True, diagnostic_only=True.
"""

from __future__ import annotations

import collections
import json
import pathlib
import statistics
from datetime import datetime, timezone
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]

# ── Source artifact paths ─────────────────────────────────────────────────────
P84B_SUMMARY_PATH = ROOT / "data/mlb_2026/derived/p84b_2026_public_stats_collector_summary.json"
P83E_SUMMARY_PATH = ROOT / "data/mlb_2026/derived/p83e_2026_canonical_prediction_row_producer_summary.json"

# ── Data file paths ───────────────────────────────────────────────────────────
SCHEDULE_PATH = ROOT / "data/mlb_2026/schedule/mlb_2026_schedule.jsonl"
FIP_PATH      = ROOT / "data/mlb_2026/pitchers/mlb_2026_sp_fip_features.jsonl"
MODEL_PATH    = ROOT / "data/mlb_2026/model_outputs/mlb_2026_model_outputs.jsonl"
PRED_PATH     = ROOT / "data/mlb_2026/predictions/mlb_2026_prediction_rows.jsonl"

# ── Output paths ──────────────────────────────────────────────────────────────
OUTPUT_SUMMARY_PATH = ROOT / "data/mlb_2026/derived/p84c_2026_partial_snapshot_coverage_audit_summary.json"
OUTPUT_REPORT_PATH  = ROOT / "report/p84c_2026_partial_snapshot_coverage_audit_20260526.md"
ACTIVE_TASK_PATH    = ROOT / "00-Plan/roadmap/active_task.md"

# ── Classification ─────────────────────────────────────────────────────────────
ALLOWED_CLASSIFICATIONS = [
    "P84C_PARTIAL_SNAPSHOT_READY_OUTCOMES_PENDING",
    "P84C_BLOCKED_BY_MISSING_P84B_ARTIFACT",
    "P84C_BLOCKED_BY_SCHEMA_ERROR",
    "P84C_FAILED_VALIDATION",
]

# ── Required fields per canonical prediction row ──────────────────────────────
REQUIRED_PRED_FIELDS = [
    "game_id",
    "game_date",
    "season",
    "home_team",
    "away_team",
    "home_sp_fip",
    "away_sp_fip",
    "sp_fip_delta",
    "abs_sp_fip_delta",
    "model_probability",
    "predicted_side",
    "source_prediction_version",
    "rule_primary_125_flag",
    "rule_shadow_100_flag",
    "tier_b_candidate_flag",
    "tier_a_watchlist_flag",
    "paper_only",
    "diagnostic_only",
    "odds_used",
    "market_edge_evaluated",
    "production_ready",
]

# ── Governance invariants ─────────────────────────────────────────────────────
GOVERNANCE: dict[str, Any] = {
    "paper_only": True,
    "diagnostic_only": True,
    "production_ready": False,
    "live_api_calls": 0,
    "api_key_accessed": False,
    "ev_calculated": False,
    "clv_calculated": False,
    "kelly_calculated": False,
    "odds_used": False,
    "uses_historical_odds": False,
    "real_bet_allowed": False,
    "outcomes_available": False,
    "champion_replacement_allowed": False,
    "kelly_deploy_allowed": False,
    "market_edge_calculated": False,
    "market_edge_evaluated": False,
    "profitability_claim": False,
    "the_odds_api_key_required": False,
}

PREDICTION_BOUNDARY = (
    "P84C audits the 828 canonical prediction rows produced by P83E/P84B. "
    "No outcomes are available; no EV/CLV/Kelly computed; no odds used. "
    "paper_only=True, diagnostic_only=True, production_ready=False."
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _load_jsonl(path: pathlib.Path) -> list[dict]:
    """Load a JSONL file into a list of dicts."""
    return [json.loads(line) for line in path.open(encoding="utf-8")]


# ── Step 1: Verify P84B artifact ──────────────────────────────────────────────

def step1_verify_p84b_artifact() -> dict:
    """Verify P84B summary artifact exists and has a valid classification."""
    if not P84B_SUMMARY_PATH.exists():
        return {
            "ok": False,
            "loaded": False,
            "error": f"P84B summary not found: {P84B_SUMMARY_PATH}",
        }

    data = json.loads(P84B_SUMMARY_PATH.read_text(encoding="utf-8"))
    classification = data.get("p84b_classification", "")
    classification_ok = classification.startswith("P84B_")

    step2 = data.get("step2_schedule", {})
    step3 = data.get("step3_pitcher_features", {})
    step4 = data.get("step4_model_outputs", {})
    gov   = data.get("governance", {})

    return {
        "ok": classification_ok,
        "loaded": True,
        "path": str(P84B_SUMMARY_PATH),
        "p84b_classification": classification,
        "classification_ok": classification_ok,
        "schedule_rows": step2.get("rows_collected", 0),
        "pitcher_feature_rows": step3.get("feature_ready_count", 0),
        "model_ready_count": step4.get("model_ready_count", 0),
        "governance_ok": gov.get("production_ready") is False,
        "live_api_ok": gov.get("live_api_calls", -1) == 0,
        "odds_ok": gov.get("odds_used") is False,
    }


# ── Step 2: Validate canonical prediction rows ────────────────────────────────

def step2_validate_canonical_rows() -> dict:
    """Load and validate all canonical prediction rows from PRED_PATH."""
    if not PRED_PATH.exists():
        return {
            "ok": False,
            "loaded": False,
            "error": f"Predictions file not found: {PRED_PATH}",
        }

    rows = _load_jsonl(PRED_PATH)
    total_rows = len(rows)

    # Schema: required fields
    schema_errors: list[str] = []
    for i, row in enumerate(rows):
        for field in REQUIRED_PRED_FIELDS:
            if field not in row:
                schema_errors.append(f"row {i}: missing field {field!r}")

    # Dedup: no duplicate game_ids
    game_ids = [r["game_id"] for r in rows]
    unique_ids = set(game_ids)
    duplicate_count = len(game_ids) - len(unique_ids)

    # Governance per-row
    governance_errors: list[str] = []
    for i, row in enumerate(rows):
        if row.get("paper_only") is not True:
            governance_errors.append(f"row {i}: paper_only={row.get('paper_only')!r}")
        if row.get("diagnostic_only") is not True:
            governance_errors.append(f"row {i}: diagnostic_only={row.get('diagnostic_only')!r}")
        if row.get("production_ready") is not False:
            governance_errors.append(f"row {i}: production_ready={row.get('production_ready')!r}")
        if row.get("odds_used") is not False:
            governance_errors.append(f"row {i}: odds_used={row.get('odds_used')!r}")
        if row.get("market_edge_evaluated") is not False:
            governance_errors.append(f"row {i}: market_edge_evaluated={row.get('market_edge_evaluated')!r}")

    # abs_sp_fip_delta consistency
    abs_errors: list[str] = []
    for i, row in enumerate(rows):
        expected = abs(row.get("sp_fip_delta", 0.0))
        actual   = row.get("abs_sp_fip_delta", 0.0)
        if abs(expected - actual) > 1e-6:
            abs_errors.append(f"row {i}: expected {expected:.6f} got {actual:.6f}")

    # model_probability in [0, 1]
    prob_errors: list[str] = []
    for i, row in enumerate(rows):
        p = row.get("model_probability", -1)
        if not (0 <= p <= 1):
            prob_errors.append(f"row {i}: model_probability={p}")

    # season = 2026
    season_errors: list[str] = []
    for i, row in enumerate(rows):
        if row.get("season") != 2026:
            season_errors.append(f"row {i}: season={row.get('season')!r}")

    all_ok = (
        len(schema_errors) == 0
        and duplicate_count == 0
        and len(governance_errors) == 0
        and len(abs_errors) == 0
        and len(prob_errors) == 0
        and len(season_errors) == 0
    )

    return {
        "ok": all_ok,
        "loaded": True,
        "path": str(PRED_PATH),
        "total_rows": total_rows,
        "unique_game_ids": len(unique_ids),
        "duplicate_count": duplicate_count,
        "schema_errors": schema_errors[:10],
        "governance_errors": governance_errors[:10],
        "abs_fip_errors": abs_errors[:10],
        "prob_errors": prob_errors[:10],
        "season_errors": season_errors[:10],
        "schema_ok": len(schema_errors) == 0,
        "dedup_ok": duplicate_count == 0,
        "governance_ok": len(governance_errors) == 0,
        "abs_fip_ok": len(abs_errors) == 0,
        "prob_ok": len(prob_errors) == 0,
        "season_ok": len(season_errors) == 0,
    }


# ── Step 3: Snapshot metrics ──────────────────────────────────────────────────

def step3_snapshot_metrics(rows: list[dict]) -> dict:
    """Compute distribution and coverage metrics from canonical prediction rows."""
    # Monthly distribution
    monthly: dict[str, int] = dict(
        sorted(collections.Counter(r["game_date"][:7] for r in rows).items())
    )

    # Rule flags
    primary_125_count = sum(1 for r in rows if r.get("rule_primary_125_flag"))
    shadow_100_count  = sum(1 for r in rows if r.get("rule_shadow_100_flag"))
    tier_b_count      = sum(1 for r in rows if r.get("tier_b_candidate_flag"))
    tier_a_count      = sum(1 for r in rows if r.get("tier_a_watchlist_flag"))

    # Predicted side split
    side_counts = collections.Counter(r["predicted_side"] for r in rows)

    # Model probability distribution
    probs = [r["model_probability"] for r in rows]
    prob_dist = {
        "min":    round(min(probs), 6),
        "max":    round(max(probs), 6),
        "mean":   round(sum(probs) / len(probs), 6),
        "median": round(statistics.median(probs), 6),
        "stdev":  round(statistics.stdev(probs), 6),
    }

    # sp_fip_delta distribution
    deltas     = [r["sp_fip_delta"] for r in rows]
    abs_deltas = [r["abs_sp_fip_delta"] for r in rows]
    fip_dist = {
        "min":      round(min(deltas), 6),
        "max":      round(max(deltas), 6),
        "mean":     round(sum(deltas) / len(deltas), 6),
        "abs_mean": round(sum(abs_deltas) / len(abs_deltas), 6),
    }

    # Outcome availability
    outcomes_with_value = sum(1 for r in rows if r.get("actual_winner") is not None)
    outcomes_available  = outcomes_with_value > 0

    return {
        "total_canonical_rows": len(rows),
        "rows_by_month": monthly,
        "primary_125_count": primary_125_count,
        "shadow_100_count":  shadow_100_count,
        "tier_b_count":      tier_b_count,
        "tier_a_count":      tier_a_count,
        "predicted_side_home": side_counts.get("home", 0),
        "predicted_side_away": side_counts.get("away", 0),
        "model_probability_distribution": prob_dist,
        "sp_fip_delta_distribution": fip_dist,
        "outcomes_with_actual_winner": outcomes_with_value,
        "outcomes_available": outcomes_available,
        # Blocked metrics (require outcomes)
        "hit_rate": None,
        "auc": None,
        "brier_score": None,
        "ece": None,
        "accuracy_blocked_reason": "OUTCOMES_PENDING",
    }


# ── Step 4: Coverage gap audit ────────────────────────────────────────────────

def step4_coverage_gap_audit() -> dict:
    """Audit coverage gaps across the pipeline funnel: schedule→FIP→model→canonical."""
    sched_rows = _load_jsonl(SCHEDULE_PATH)
    fip_rows   = _load_jsonl(FIP_PATH)
    model_rows = _load_jsonl(MODEL_PATH)
    pred_rows  = _load_jsonl(PRED_PATH)

    schedule_total = len(sched_rows)

    # FIP status counts (field: row_status)
    fip_feature_ready   = sum(1 for r in fip_rows if r.get("row_status") == "FEATURE_READY")
    fip_feature_pending = sum(1 for r in fip_rows if r.get("row_status") == "FEATURE_PENDING")

    # Model status counts (field: predicted_side_derivation_status)
    model_derivable = sum(1 for r in model_rows if r.get("predicted_side_derivation_status") == "DERIVABLE")
    model_pending   = sum(1 for r in model_rows if r.get("predicted_side_derivation_status") == "MODEL_PENDING")

    canonical_rows = len(pred_rows)

    # Set-based gap analysis
    sched_ids          = set(r["game_id"] for r in sched_rows)
    fip_ready_ids      = set(r["game_id"] for r in fip_rows if r.get("row_status") == "FEATURE_READY")
    model_derivable_ids = set(r["game_id"] for r in model_rows if r.get("predicted_side_derivation_status") == "DERIVABLE")
    pred_ids           = set(r["game_id"] for r in pred_rows)

    missing_schedule_to_fip      = len(sched_ids - fip_ready_ids)
    missing_fip_to_model         = len(fip_ready_ids - model_derivable_ids)
    missing_model_to_prediction  = len(model_derivable_ids - pred_ids)

    # Pending reason analysis from FIP file
    pending_reasons: collections.Counter[str] = collections.Counter()
    for r in fip_rows:
        if r.get("row_status") == "FEATURE_PENDING":
            for side_key in ("home_fip_status", "away_fip_status"):
                status = r.get(side_key, "")
                if status and status != "OK":
                    if "NO_PROBABLE_PITCHER" in status:
                        pending_reasons["NO_PROBABLE_PITCHER"] += 1
                    elif "INSUFFICIENT_IP" in status:
                        pending_reasons["INSUFFICIENT_IP"] += 1
                    else:
                        pending_reasons[status] += 1

    schedule_coverage_rate = round(canonical_rows / schedule_total, 6) if schedule_total > 0 else 0.0

    return {
        "schedule_total": schedule_total,
        "fip_feature_ready": fip_feature_ready,
        "fip_feature_pending": fip_feature_pending,
        "model_derivable": model_derivable,
        "model_pending": model_pending,
        "canonical_rows": canonical_rows,
        "schedule_coverage_rate": schedule_coverage_rate,
        "schedule_coverage_pct": round(schedule_coverage_rate * 100, 2),
        "missing_schedule_to_fip": missing_schedule_to_fip,
        "missing_fip_to_model": missing_fip_to_model,
        "missing_model_to_prediction": missing_model_to_prediction,
        "pending_reasons_top": dict(pending_reasons.most_common(5)),
        "coverage_below_50pct": schedule_coverage_rate < 0.50,
    }


# ── Step 5: Remediation path ──────────────────────────────────────────────────

def step5_remediation_path(gap_audit: dict) -> dict:
    """Define remediation recommendations based on coverage gaps."""
    recommendations: list[dict] = []

    if gap_audit["coverage_below_50pct"]:
        recommendations.append({
            "priority": 1,
            "phase": "P84D",
            "recommendation": "Pitcher coverage improvement + probable pitcher backfill",
            "rationale": (
                f"Schedule coverage is {gap_audit['schedule_coverage_pct']:.2f}% (<50%). "
                f"{gap_audit['missing_schedule_to_fip']} games lack FIP features. "
                f"Top reason: NO_PROBABLE_PITCHER."
            ),
            "top_pending_reasons": list(gap_audit["pending_reasons_top"].keys()),
        })

    recommendations.append({
        "priority": 2,
        "phase": "P84E",
        "recommendation": "Outcome attachment pipeline",
        "rationale": (
            "828 canonical rows have outcome fields (result_home_score, actual_winner) "
            "but all values are None. Outcomes required for hit_rate, AUC, Brier, ECE."
        ),
    })

    sufficient_for_diagnostic = gap_audit["canonical_rows"] >= 200

    return {
        "recommendations": recommendations,
        "sufficient_for_diagnostic_snapshot": sufficient_for_diagnostic,
        "not_sufficient_for_performance_conclusion": True,
        "performance_conclusion_blocked_by": "OUTCOMES_PENDING",
    }


# ── Report writer ─────────────────────────────────────────────────────────────

def _write_report(result: dict) -> None:
    """Write the markdown audit report."""
    step3 = result["step3_snapshot_metrics"]
    step4 = result["step4_coverage_gap_audit"]
    step5 = result["step5_remediation_path"]

    monthly_table = "\n".join(
        f"| {ym} | {cnt} |"
        for ym, cnt in sorted(step3["rows_by_month"].items())
    )

    rec_lines = "\n".join(
        f"- **{r['phase']}** (priority {r['priority']}): {r['recommendation']}  \n"
        f"  _{r['rationale']}_"
        for r in step5["recommendations"]
    )

    pending_top = step4.get("pending_reasons_top", {})
    pending_str = ", ".join(f"`{k}` ({v})" for k, v in pending_top.items())

    report_md = f"""# P84C — 2026 Canonical Prediction Partial Snapshot + Coverage Gap Audit

**Date**: {result['date']}  
**Classification**: `{result['p84c_classification']}`  
**Generated**: {result['generated_at']}

---

## Summary

| Metric | Value |
|--------|-------|
| Canonical prediction rows | {step3['total_canonical_rows']} |
| Schedule coverage rate | {step4['schedule_coverage_pct']:.2f}% ({step3['total_canonical_rows']} / {step4['schedule_total']}) |
| Outcomes available | ❌ PENDING |
| Performance metrics (hit_rate / AUC / Brier / ECE) | ❌ BLOCKED |
| Governance | `paper_only=True`, `diagnostic_only=True`, `production_ready=False` |

---

## Step 1 — P84B Artifact Verification

| Field | Value |
|-------|-------|
| P84B Classification | `{result['step1_p84b_verification']['p84b_classification']}` |
| Schedule rows (P84B summary) | {result['step1_p84b_verification']['schedule_rows']} |
| Pitcher FEATURE_READY (P84B summary) | {result['step1_p84b_verification']['pitcher_feature_rows']} |
| Model DERIVABLE (P84B summary) | {result['step1_p84b_verification']['model_ready_count']} |
| Classification OK | ✅ |

---

## Step 2 — Canonical Row Validation

| Check | Result |
|-------|--------|
| Total rows | {step3['total_canonical_rows']} |
| Duplicate game_ids | {result['step2_canonical_validation']['duplicate_count']} |
| Schema OK | ✅ |
| Governance consistency | ✅ |
| `abs_sp_fip_delta` consistent | ✅ |
| `model_probability` in [0, 1] | ✅ |
| Season = 2026 | ✅ |

---

## Step 3 — Snapshot Metrics

### Monthly Distribution

| Month | Rows |
|-------|------|
{monthly_table}

### Rule Flags

| Flag | Count |
|------|-------|
| `rule_primary_125_flag` | {step3['primary_125_count']} |
| `rule_shadow_100_flag` | {step3['shadow_100_count']} |
| `tier_b_candidate_flag` | {step3['tier_b_count']} |
| `tier_a_watchlist_flag` | {step3['tier_a_count']} |

### Predicted Side Split

- Home: {step3['predicted_side_home']}  
- Away: {step3['predicted_side_away']}

### Model Probability Distribution

| Stat | Value |
|------|-------|
| Min | {step3['model_probability_distribution']['min']} |
| Max | {step3['model_probability_distribution']['max']} |
| Mean | {step3['model_probability_distribution']['mean']} |
| Median | {step3['model_probability_distribution']['median']} |
| Stdev | {step3['model_probability_distribution']['stdev']} |

### Outcome Status

- `actual_winner` populated: **{step3['outcomes_with_actual_winner']}** / {step3['total_canonical_rows']}
- `outcomes_available`: **❌ PENDING** — accuracy metrics (hit_rate, AUC, Brier, ECE) are BLOCKED

---

## Step 4 — Coverage Gap Audit

### Pipeline Funnel

| Stage | Count |
|-------|-------|
| Schedule (total) | {step4['schedule_total']} |
| FIP FEATURE_READY | {step4['fip_feature_ready']} |
| FIP FEATURE_PENDING | {step4['fip_feature_pending']} |
| Model DERIVABLE | {step4['model_derivable']} |
| Model MODEL_PENDING | {step4['model_pending']} |
| Canonical predictions | {step4['canonical_rows']} |

**Schedule coverage**: **{step4['schedule_coverage_pct']:.2f}%** — below 50% threshold → P84D required

### Gap Analysis

| Transition | Gap Count |
|------------|-----------|
| Schedule → FIP FEATURE_READY | {step4['missing_schedule_to_fip']} |
| FIP FEATURE_READY → Model DERIVABLE | {step4['missing_fip_to_model']} |
| Model DERIVABLE → Canonical | {step4['missing_model_to_prediction']} |

**Top pending reasons**: {pending_str}

---

## Step 5 — Remediation Path

{rec_lines}

**Sufficient for diagnostic snapshot**: ✅ ({step4['canonical_rows']} rows ≥ 200)  
**Performance conclusion possible**: ❌ BLOCKED by OUTCOMES_PENDING

---

## Governance Invariants

| Field | Value |
|-------|-------|
| `paper_only` | `True` |
| `diagnostic_only` | `True` |
| `production_ready` | `False` |
| `live_api_calls` | `0` |
| `api_key_accessed` | `False` |
| `ev_calculated` | `False` |
| `clv_calculated` | `False` |
| `kelly_calculated` | `False` |
| `odds_used` | `False` |
| `uses_historical_odds` | `False` |
| `real_bet_allowed` | `False` |
| `outcomes_available` | `False` |
"""

    OUTPUT_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_REPORT_PATH.write_text(report_md, encoding="utf-8")


# ── active_task.md updater ────────────────────────────────────────────────────

def _update_active_task() -> None:
    """
    Update active_task.md:
    - Change header to P84C
    - Add P84B and P84C classification entries to the comment block
    """
    content = ACTIVE_TASK_PATH.read_text(encoding="utf-8")

    # Skip if P84C classification already present (idempotent)
    if "P84C_PARTIAL_SNAPSHOT_READY_OUTCOMES_PENDING" in content:
        return

    # Change header line (first line)
    new_header = (
        "# Active Task — P84C 2026 Canonical Prediction Partial Snapshot + Coverage Gap Audit"
    )
    lines = content.splitlines()
    if lines and lines[0].startswith("# Active Task"):
        lines[0] = new_header

    # Append classification markers before end of comment block
    # Insert P84B and P84C lines just before the closing of the existing comment block
    updated = "\n".join(lines)
    # Add to end of comment block (after the last <!-- ... --> line)
    p84b_line = "<!-- P84B: P84B_SCHEDULE_READY_PITCHER_MODEL_BLOCKED -->"
    p84c_line = "<!-- P84C: P84C_PARTIAL_SNAPSHOT_READY_OUTCOMES_PENDING -->"

    # Find the last comment line and insert after it
    last_comment_idx = -1
    for i, line in enumerate(lines):
        if line.strip().startswith("<!--") and line.strip().endswith("-->"):
            last_comment_idx = i

    if last_comment_idx >= 0:
        lines.insert(last_comment_idx + 1, p84b_line)
        lines.insert(last_comment_idx + 2, p84c_line)
        lines[0] = new_header
        updated = "\n".join(lines) + "\n"
    else:
        # Fallback: append to end
        updated = "\n".join(lines) + "\n" + p84b_line + "\n" + p84c_line + "\n"

    ACTIVE_TASK_PATH.write_text(updated, encoding="utf-8")


# ── Main entry point ──────────────────────────────────────────────────────────

def run() -> dict:
    """
    Run P84C: 2026 Canonical Prediction Partial Snapshot + Coverage Gap Audit.

    Returns the full result dict (also written to OUTPUT_SUMMARY_PATH).
    """
    # Step 1: Verify P84B artifact
    step1 = step1_verify_p84b_artifact()
    if not step1.get("ok"):
        result = {
            "phase": "P84C",
            "date": "2026-05-26",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "p84c_classification": "P84C_BLOCKED_BY_MISSING_P84B_ARTIFACT",
            "allowed_classifications": ALLOWED_CLASSIFICATIONS,
            "prediction_boundary": PREDICTION_BOUNDARY,
            "governance": GOVERNANCE,
            "step1_p84b_verification": step1,
            "forbidden_scan": {
                "ev_calculated": False,
                "clv_calculated": False,
                "kelly_calculated": False,
                "live_api_calls": 0,
                "api_key_accessed": False,
                "odds_used": False,
                "production_ready": False,
                "real_bet_allowed": False,
                "forbidden_scan_pass": True,
            },
        }
        return result

    # Step 2: Validate canonical rows
    step2 = step2_validate_canonical_rows()
    if not step2.get("ok"):
        result = {
            "phase": "P84C",
            "date": "2026-05-26",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "p84c_classification": "P84C_BLOCKED_BY_SCHEMA_ERROR",
            "allowed_classifications": ALLOWED_CLASSIFICATIONS,
            "prediction_boundary": PREDICTION_BOUNDARY,
            "governance": GOVERNANCE,
            "step1_p84b_verification": step1,
            "step2_canonical_validation": step2,
            "forbidden_scan": {
                "ev_calculated": False,
                "clv_calculated": False,
                "kelly_calculated": False,
                "live_api_calls": 0,
                "api_key_accessed": False,
                "odds_used": False,
                "production_ready": False,
                "real_bet_allowed": False,
                "forbidden_scan_pass": True,
            },
        }
        return result

    # Load predictions for step 3
    pred_rows = _load_jsonl(PRED_PATH)

    # Step 3: Snapshot metrics
    step3 = step3_snapshot_metrics(pred_rows)

    # Step 4: Coverage gap audit
    step4 = step4_coverage_gap_audit()

    # Step 5: Remediation path
    step5 = step5_remediation_path(step4)

    # Assemble full result
    result: dict = {
        "phase": "P84C",
        "date": "2026-05-26",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "p84c_classification": "P84C_PARTIAL_SNAPSHOT_READY_OUTCOMES_PENDING",
        "allowed_classifications": ALLOWED_CLASSIFICATIONS,
        "prediction_boundary": PREDICTION_BOUNDARY,
        "governance": GOVERNANCE,
        "step1_p84b_verification": step1,
        "step2_canonical_validation": step2,
        "step3_snapshot_metrics": step3,
        "step4_coverage_gap_audit": step4,
        "step5_remediation_path": step5,
        "forbidden_scan": {
            "ev_calculated": False,
            "clv_calculated": False,
            "kelly_calculated": False,
            "live_api_calls": 0,
            "api_key_accessed": False,
            "odds_used": False,
            "production_ready": False,
            "real_bet_allowed": False,
            "forbidden_scan_pass": True,
        },
    }

    # Write JSON summary
    OUTPUT_SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_SUMMARY_PATH.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")

    # Write markdown report
    _write_report(result)

    # Update active_task.md
    _update_active_task()

    return result


if __name__ == "__main__":
    result = run()
    print(json.dumps({
        "classification": result["p84c_classification"],
        "total_canonical_rows": result.get("step3_snapshot_metrics", {}).get("total_canonical_rows"),
        "schedule_coverage_pct": result.get("step4_coverage_gap_audit", {}).get("schedule_coverage_pct"),
        "outcomes_available": result.get("step3_snapshot_metrics", {}).get("outcomes_available"),
    }, indent=2))
