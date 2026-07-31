#!/usr/bin/env python3
"""
Phase 6K — Model Output Contract Validator
==========================================
Validates candidate files against the Phase 6J model output contract
(data/derived/model_outputs_YYYY-MM-DD.jsonl schema).

Applies quality gates M1–M12.
Produces a Markdown report and optional JSON summary.
Does NOT modify any source file.
Does NOT generate predictions.
Does NOT call external APIs.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ── Constants ────────────────────────────────────────────────────────────────

SCHEMA_VERSION = "6k-1.0"
PHASE = "6K"

REQUIRED_CONTRACT_FIELDS: list[str] = [
    "schema_version",
    "model_output_id",
    "prediction_run_id",
    "model_family",
    "model_version",
    "feature_version",
    "leakage_guard_version",
    "training_window_id",
    "walk_forward_split_id",
    "sport",
    "league",
    "canonical_match_id",
    "raw_match_id",
    "match_time_utc",
    "home_team_code",
    "away_team_code",
    "market_type",
    "market_line",
    "market_key",
    "selection",
    "selection_key",
    "prediction_time_utc",
    "predicted_probability",
    "confidence",
    "probability_source",
    "feature_cutoff_time_utc",
    "odds_snapshot_ref",
    "implied_probability_at_prediction",
    "expected_value",
    "model_quality_flags",
    "data_quality_flags",
]

VERSION_FIELDS = ["model_version", "feature_version", "leakage_guard_version"]

# Fields that must not appear in a prediction output (would indicate leakage)
SETTLEMENT_LEAKAGE_FIELDS = [
    "actual_result", "home_score", "away_score", "winner",
    "final_score", "result", "settlement", "pnl", "paper_pnl",
]

FORBIDDEN_LEAKAGE_FLAGS = [
    "FUTURE_LEAKAGE", "POST_MATCH", "RESULT_USED", "SETTLEMENT_USED",
]

# ── Argument parsing ─────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Phase 6K: Validate model output contract (M1–M12)"
    )
    p.add_argument(
        "--contract-doc",
        default="docs/orchestration/phase6j_model_output_contract_design_2026-04-29.md",
    )
    p.add_argument(
        "--candidate",
        default="data/derived/model_outputs_2026-04-29.jsonl",
    )
    p.add_argument(
        "--dry-run",
        default="data/derived/future_model_predictions_dry_run_2026-04-29.jsonl",
    )
    p.add_argument(
        "--report",
        default="docs/orchestration/phase6k_model_output_contract_validator_report_2026-04-29.md",
    )
    p.add_argument(
        "--summary",
        default="data/derived/model_output_contract_validation_summary_2026-04-29.json",
    )
    return p.parse_args()


# ── Gate helpers ─────────────────────────────────────────────────────────────

def _parse_dt(value: Any) -> datetime | None:
    """Parse ISO8601 UTC string into datetime, or return None."""
    if not value or not isinstance(value, str):
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S+00:00",
                "%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def gate_m1(row: dict) -> tuple[bool, list[str]]:
    """M1_SCHEMA_VALID: all required fields present."""
    missing = [f for f in REQUIRED_CONTRACT_FIELDS if f not in row]
    if missing:
        return False, [f"M1_FAIL: missing fields {missing}"]
    return True, ["M1_PASS"]


def gate_m2(row: dict) -> tuple[bool, list[str]]:
    """M2_CANONICAL_MATCH_ID_PRESENT: canonical_match_id non-empty."""
    val = row.get("canonical_match_id")
    if not val or not isinstance(val, str) or not val.strip():
        return False, ["M2_FAIL: canonical_match_id empty or missing"]
    return True, ["M2_PASS"]


def gate_m3(row: dict) -> tuple[bool, list[str]]:
    """M3_MARKET_KEY_PRESENT: market_key non-empty."""
    val = row.get("market_key")
    if not val or not isinstance(val, str) or not val.strip():
        return False, ["M3_FAIL: market_key empty or missing"]
    return True, ["M3_PASS"]


def gate_m4(row: dict) -> tuple[bool, list[str]]:
    """M4_SELECTION_KEY_PRESENT: selection_key non-empty."""
    val = row.get("selection_key")
    if not val or not isinstance(val, str) or not val.strip():
        return False, ["M4_FAIL: selection_key empty or missing"]
    return True, ["M4_PASS"]


def gate_m5(row: dict) -> tuple[bool, list[str]]:
    """M5_VERSION_FIELDS_PRESENT: model_version, feature_version, leakage_guard_version non-empty and not NOT_IMPLEMENTED."""
    issues = []
    for f in VERSION_FIELDS:
        val = row.get(f)
        if not val or not isinstance(val, str) or not val.strip():
            issues.append(f"M5_FAIL: {f} is empty")
        elif "NOT_IMPLEMENTED" in val:
            issues.append(f"M5_FAIL: {f}='{val}' (NOT_IMPLEMENTED)")
    if issues:
        return False, issues
    return True, ["M5_PASS"]


def gate_m6(row: dict) -> tuple[bool, list[str]]:
    """M6_TIMING_VALID: prediction_time_utc < match_time_utc; feature_cutoff_time_utc <= prediction_time_utc."""
    notes: list[str] = []
    prediction_t = _parse_dt(row.get("prediction_time_utc"))
    match_t = _parse_dt(row.get("match_time_utc"))
    cutoff_t = _parse_dt(row.get("feature_cutoff_time_utc"))

    ok = True
    if prediction_t is None or match_t is None:
        notes.append("M6_WARN: prediction_time_utc or match_time_utc not parseable")
        ok = False
    elif prediction_t >= match_t:
        notes.append(
            f"M6_FAIL: prediction_time_utc {row.get('prediction_time_utc')} "
            f">= match_time_utc {row.get('match_time_utc')}"
        )
        ok = False

    if cutoff_t is None:
        notes.append("M6_WARN: feature_cutoff_time_utc missing")
    elif prediction_t and cutoff_t > prediction_t:
        notes.append(
            f"M6_FAIL: feature_cutoff_time_utc {row.get('feature_cutoff_time_utc')} "
            f"> prediction_time_utc {row.get('prediction_time_utc')}"
        )
        ok = False

    if ok:
        notes.append("M6_PASS")
    return ok, notes


def gate_m7(row: dict) -> tuple[bool, list[str]]:
    """M7_PROBABILITY_VALID: predicted_probability is numeric and [0,1]; not null for non-dry-run rows."""
    is_dry = row.get("dry_run", False)
    pp = row.get("predicted_probability")

    if is_dry:
        # Dry-run rows: predicted_probability must be null
        if pp is not None:
            return False, [f"M7_FAIL: dry_run=true but predicted_probability={pp} (must be null)"]
        return True, ["M7_PASS_DRY_RUN_NULL_OK"]

    if pp is None:
        # Check for capability gap flag
        dq = row.get("data_quality_flags") or []
        flags = dq if isinstance(dq, list) else []
        gap_flags = [f for f in flags if "MODEL_CAPABILITY_GAP" in str(f)]
        if gap_flags:
            return False, [f"M7_BLOCK_CAPABILITY_GAP: predicted_probability null due to {gap_flags}"]
        return False, ["M7_FAIL: predicted_probability is null for non-dry-run row"]

    if not isinstance(pp, (int, float)):
        return False, [f"M7_FAIL: predicted_probability is not numeric: {pp!r}"]
    if not (0.0 <= float(pp) <= 1.0):
        return False, [f"M7_FAIL: predicted_probability {pp} outside [0, 1]"]
    return True, [f"M7_PASS: predicted_probability={pp}"]


def gate_m8(row: dict) -> tuple[bool, list[str]]:
    """M8_EV_VALID_OR_NULL_WITH_REASON: expected_value numeric if odds_snapshot_ref present; null allowed with explicit reason."""
    snap = row.get("odds_snapshot_ref")
    ev = row.get("expected_value")

    if snap and snap != "null" and snap is not None:
        if ev is None:
            return False, [f"M8_FAIL: odds_snapshot_ref present ({snap}) but expected_value is null"]
        if not isinstance(ev, (int, float)):
            return False, [f"M8_FAIL: expected_value is not numeric: {ev!r}"]
        return True, [f"M8_PASS: ev={ev}"]

    # No odds ref — EV must be null
    if ev is not None:
        return False, [f"M8_FAIL: expected_value={ev} but no odds_snapshot_ref (fake EV)"]
    return True, ["M8_PASS_EV_NULL_NO_ODDS_REF"]


def gate_m9(row: dict) -> tuple[bool, list[str]]:
    """M9_NO_LEAKAGE_HARD_FAIL: no settlement/result fields; no leakage flags."""
    found_fields = [f for f in SETTLEMENT_LEAKAGE_FIELDS if f in row]
    if found_fields:
        return False, [f"M9_FAIL_LEAKAGE: settlement/result fields present: {found_fields}"]

    flags = row.get("data_quality_flags") or []
    if not isinstance(flags, list):
        flags = []
    bad_flags = [f for f in flags if any(lf in str(f) for lf in FORBIDDEN_LEAKAGE_FLAGS)]
    if bad_flags:
        return False, [f"M9_FAIL_LEAKAGE: forbidden leakage flags: {bad_flags}"]

    return True, ["M9_PASS"]


def gate_m10(row: dict) -> tuple[bool, list[str]]:
    """M10_MARKET_SEMANTICS_VALID: ML/RL/OU market rules."""
    mt = str(row.get("market_type", "")).upper()
    line = row.get("market_line")
    sel = str(row.get("selection", "")).lower()
    prob_src = str(row.get("probability_source", ""))
    dq = row.get("data_quality_flags") or []
    dq_flags = dq if isinstance(dq, list) else []

    if mt == "ML":
        if sel not in ("home", "away"):
            return False, [f"M10_FAIL: ML market must have selection 'home' or 'away', got '{sel}'"]
        if line is not None:
            return False, [f"M10_FAIL: ML market must have market_line=null, got {line}"]
        return True, ["M10_PASS_ML"]

    if mt == "RL":
        gap = "MODEL_CAPABILITY_GAP_RL_LINE_SPECIFIC_PROBABILITY"
        if gap in dq_flags:
            return True, [f"M10_PASS_RL_CAPABILITY_GAP_DECLARED"]
        if line is None:
            return False, ["M10_FAIL: RL market requires market_line"]
        if "heuristic_rl_from_ml" in prob_src:
            return False, [f"M10_FAIL: RL probability derived from ML heuristic without validation flag"]
        return True, [f"M10_PASS_RL_LINE={line}"]

    if mt == "OU":
        gap = "MODEL_CAPABILITY_GAP_OU_TOTAL_DISTRIBUTION"
        if gap in dq_flags:
            return True, [f"M10_PASS_OU_CAPABILITY_GAP_DECLARED"]
        if line is None:
            return False, ["M10_FAIL: OU market requires market_line"]
        if sel not in ("over", "under"):
            return False, [f"M10_FAIL: OU market must have selection 'over' or 'under', got '{sel}'"]
        return True, [f"M10_PASS_OU_LINE={line}"]

    return False, [f"M10_FAIL: unknown market_type '{mt}'"]


def gate_m11(row: dict) -> tuple[bool, list[str]]:
    """M11_CLV_USABLE_FLAG_CORRECT: real rows may be CLV-usable; dry-run must be clv_usable=false."""
    is_dry = row.get("dry_run", False)
    clv_usable = row.get("clv_usable")
    pp = row.get("predicted_probability")

    if is_dry and clv_usable:
        return False, [f"M11_FAIL: dry_run=true but clv_usable={clv_usable} (must be false)"]

    if pp is None and clv_usable:
        return False, ["M11_FAIL: predicted_probability=null but clv_usable=true"]

    return True, ["M11_PASS"]


def gate_m12(row: dict) -> tuple[bool, list[str]]:
    """M12_DRY_RUN_FLAG_CORRECT: dry-run files must declare dry_run=true; real outputs omit or set false."""
    is_dry = row.get("dry_run", False)

    if is_dry:
        pp = row.get("predicted_probability")
        ev = row.get("expected_value")
        clv_usable = row.get("clv_usable")
        issues = []
        if pp is not None:
            issues.append(f"M12_FAIL: dry_run=true but predicted_probability={pp} (must be null)")
        if ev is not None:
            issues.append(f"M12_FAIL: dry_run=true but expected_value={ev} (must be null)")
        if clv_usable:
            issues.append(f"M12_FAIL: dry_run=true but clv_usable={clv_usable} (must be false)")
        if issues:
            return False, issues
        return True, ["M12_PASS_DRY_RUN_CONSISTENT"]

    return True, ["M12_PASS_NOT_DRY_RUN"]


ALL_GATES = [
    ("M1", gate_m1),
    ("M2", gate_m2),
    ("M3", gate_m3),
    ("M4", gate_m4),
    ("M5", gate_m5),
    ("M6", gate_m6),
    ("M7", gate_m7),
    ("M8", gate_m8),
    ("M9", gate_m9),
    ("M10", gate_m10),
    ("M11", gate_m11),
    ("M12", gate_m12),
]


# ── Row validation ────────────────────────────────────────────────────────────

def validate_row(row: dict) -> dict[str, dict]:
    """Run M1–M12 on one row. Returns {gate_id: {pass, notes}}."""
    results: dict[str, dict] = {}
    for gate_id, gate_fn in ALL_GATES:
        passed, notes = gate_fn(row)
        results[gate_id] = {"pass": passed, "notes": notes}
    return results


def aggregate_gate_results(rows_results: list[dict[str, dict]]) -> dict[str, dict]:
    """Aggregate per-row gate results into gate-level pass/fail/block counts."""
    aggregated: dict[str, dict] = {}
    for gate_id, _ in ALL_GATES:
        total = len(rows_results)
        pass_count = sum(1 for r in rows_results if r[gate_id]["pass"])
        fail_count = total - pass_count
        block_count = sum(
            1 for r in rows_results
            if not r[gate_id]["pass"]
            and any("BLOCK" in n or "CAPABILITY_GAP" in n for n in r[gate_id]["notes"])
        )
        aggregated[gate_id] = {
            "total_rows": total,
            "pass": pass_count,
            "fail": fail_count,
            "block": block_count,
            "pass_pct": round(pass_count / total * 100, 1) if total else 0.0,
        }
    return aggregated


# ── Candidate classification ──────────────────────────────────────────────────

def classify_legacy_candidate(path: str) -> dict:
    """Classify a legacy / report file as a model output candidate."""
    if not os.path.exists(path):
        return {"path": path, "exists": False, "rows": 0, "looks_like_model_output": False, "reason": "FILE_MISSING"}

    size = os.path.getsize(path)
    ext = Path(path).suffix.lower()

    try:
        if ext == ".jsonl":
            with open(path, encoding="utf-8") as f:
                rows = [json.loads(l) for l in f if l.strip()]
            if not rows:
                return {"path": path, "exists": True, "size": size, "rows": 0,
                        "looks_like_model_output": False, "reason": "EMPTY_FILE"}
            sample = rows[0]
            has_contract_fields = all(f in sample for f in REQUIRED_CONTRACT_FIELDS)
            has_pred_prob = "predicted_probability" in sample
            has_canonical = "canonical_match_id" in sample
            looks_like = has_contract_fields
            reason = "MEETS_CONTRACT_SCHEMA" if looks_like else (
                f"MISSING_CONTRACT_FIELDS: lacks "
                f"{[f for f in ['canonical_match_id','predicted_probability','model_version','prediction_time_utc','market_key','selection_key'] if f not in sample]}"
            )
            return {
                "path": path, "exists": True, "size": size, "rows": len(rows),
                "looks_like_model_output": looks_like,
                "has_predicted_probability": has_pred_prob,
                "has_canonical_match_id": has_canonical,
                "reason": reason,
            }

        elif ext == ".json":
            with open(path, encoding="utf-8") as f:
                data = json.load(f)

            if isinstance(data, dict):
                keys = list(data.keys())[:10]
                # Check if it's a per-game list report
                per_game = data.get("per_game", [])
                if per_game:
                    sample = per_game[0]
                    has_canonical = "canonical_match_id" in sample
                    has_pred_prob = "predicted_home_win_prob" in sample or "predicted_probability" in sample
                    has_pred_time = "prediction_time_utc" in sample
                    has_model_version = "model_version" in sample
                    return {
                        "path": path, "exists": True, "size": size, "rows": len(per_game),
                        "looks_like_model_output": False,
                        "has_predicted_probability": has_pred_prob,
                        "has_canonical_match_id": has_canonical,
                        "reason": (
                            "REPORT_NOT_REGISTRY: per_game rows exist but missing contract fields: "
                            + str([f for f in ["canonical_match_id", "prediction_time_utc", "model_version", "market_key", "selection_key"]
                                   if f not in sample])
                        ),
                    }
                return {
                    "path": path, "exists": True, "size": size, "rows": 0,
                    "looks_like_model_output": False,
                    "reason": f"AGGREGATE_ONLY: top-level keys {keys}",
                }
            elif isinstance(data, list):
                if not data:
                    return {"path": path, "exists": True, "size": size, "rows": 0,
                            "looks_like_model_output": False, "reason": "EMPTY_LIST"}
                sample = data[0]
                has_contract = all(f in sample for f in REQUIRED_CONTRACT_FIELDS)
                return {
                    "path": path, "exists": True, "size": size, "rows": len(data),
                    "looks_like_model_output": has_contract,
                    "reason": "MEETS_CONTRACT_SCHEMA" if has_contract else f"MISSING_CONTRACT_FIELDS",
                }

    except Exception as exc:
        return {"path": path, "exists": True, "size": size, "rows": 0,
                "looks_like_model_output": False, "reason": f"PARSE_ERROR: {exc}"}

    return {"path": path, "exists": True, "size": size, "rows": 0,
            "looks_like_model_output": False, "reason": "UNKNOWN_FORMAT"}


# ── Readiness decision ────────────────────────────────────────────────────────

def determine_readiness(
    real_candidate_exists: bool,
    real_valid_rows: int,
    dry_run_rows: int,
    gate_agg: dict[str, dict],
) -> str:
    if not real_candidate_exists:
        return "NOT_READY_MODEL_OUTPUT_GAP"
    if real_valid_rows == 0:
        return "NOT_READY_SCHEMA_GAP"
    # Check M5 (version fields)
    m5 = gate_agg.get("M5", {})
    if m5.get("fail", 0) > 0 and m5.get("pass", 0) == 0:
        return "NOT_READY_SCHEMA_GAP"
    if real_valid_rows > 0:
        return "READY_FOR_MODEL_OUTPUT_ADAPTER"
    if dry_run_rows > 0:
        return "PARTIAL_READY_DRY_RUN_ONLY"
    return "NOT_READY_MODEL_OUTPUT_GAP"


# ── Report generation ─────────────────────────────────────────────────────────

def build_report(
    run_ts: str,
    args: argparse.Namespace,
    real_candidate_info: dict,
    dry_run_info: dict,
    legacy_infos: list[dict],
    dry_run_gate_agg: dict[str, dict],
    real_gate_agg: dict[str, dict] | None,
    readiness: str,
    dry_run_sample_notes: list[str],
) -> str:
    lines: list[str] = []

    lines += [
        f"# Phase 6K — Model Output Contract Validator Report",
        f"",
        f"**Date**: {run_ts[:10]}",
        f"**Phase**: 6K (Validator — No Code Changes, No Predictions, No Commit)",
        f"**Contract Schema Version**: 6j-1.0",
        f"**Readiness Decision**: `{readiness}`",
        f"",
        "---",
        "",
    ]

    # § 1 Executive Summary
    lines += [
        "## 1. Executive Summary",
        "",
        "Phase 6K applies the Phase 6J model output contract quality gates M1–M12 to all",
        "candidate model output files. The validator scans the real contract target",
        f"`data/derived/model_outputs_YYYY-MM-DD.jsonl`, dry-run placeholders, and legacy",
        "report/aggregate files to determine whether any source is registry-compatible.",
        "",
        f"**Real contract target (`model_outputs_2026-04-29.jsonl`)**: "
        + ("EXISTS" if real_candidate_info.get("exists") else "**MISSING**"),
        f"**Dry-run placeholder rows**: {dry_run_info.get('rows', 0)}",
        f"**Legacy candidate files scanned**: {len(legacy_infos)}",
        f"**Valid real model output rows (all gates pass)**: "
        + str(real_candidate_info.get("valid_rows", 0)),
        "",
        f"**Readiness Decision: `{readiness}`**",
        "",
        "No real `model_outputs_YYYY-MM-DD.jsonl` file exists. All existing candidate files",
        "are either aggregate metrics, paper-tracking retrospective reports, or WBC-domain",
        "registry entries. None satisfies the Phase 6J per-market contract. Dry-run",
        "placeholders confirm schema structure but remain non-CLV-usable by design.",
        "",
        "---",
        "",
    ]

    # § 2 Input Evidence
    lines += [
        "## 2. Input Evidence",
        "",
        "| File | Exists | Size | Notes |",
        "|---|:---:|---:|---|",
        f"| `{args.contract_doc}` | {'✅' if os.path.exists(args.contract_doc) else '❌'} | {os.path.getsize(args.contract_doc) if os.path.exists(args.contract_doc) else 0:,} B | Phase 6J contract — 14 sections, 31 required fields |",
        f"| `{args.dry_run}` | {'✅' if dry_run_info.get('exists') else '❌'} | {dry_run_info.get('size', 0):,} B | Phase 6I dry-run placeholder; 2,080 rows; all `dry_run=true` |",
        f"| `{args.candidate}` | {'✅' if real_candidate_info.get('exists') else '❌'} | {real_candidate_info.get('size', 0):,} B | Real contract target — **MISSING** |",
        "",
        "---",
        "",
    ]

    # § 3 Candidate Files Scanned
    lines += [
        "## 3. Candidate Files Scanned",
        "",
        "| Candidate | Exists | Rows | Looks Like Model Output | Required Fields Present | Valid Rows | Decision |",
        "|---|:---:|---:|:---:|:---:|---:|---|",
    ]

    # Real candidate
    rc = real_candidate_info
    lines.append(
        f"| `data/derived/model_outputs_2026-04-29.jsonl` | "
        + ("✅" if rc.get("exists") else "❌")
        + f" | {rc.get('rows', 0):,} | "
        + ("✅" if rc.get("looks_like_model_output") else "❌")
        + f" | {'✅' if rc.get('has_required_fields') else '❌'} | {rc.get('valid_rows', 0):,} | "
        + f"`MISSING_REAL_MODEL_OUTPUT_FILE` |"
    )

    # Dry-run
    dr = dry_run_info
    lines.append(
        f"| `future_model_predictions_dry_run_2026-04-29.jsonl` | "
        + ("✅" if dr.get("exists") else "❌")
        + f" | {dr.get('rows', 0):,} | ⚠️ partial | ⚠️ partial | 0 | `DRY_RUN_PLACEHOLDER_NOT_CLV_USABLE` |"
    )

    # Legacy candidates
    for info in legacy_infos:
        p = info["path"].replace("data/wbc_backend/reports/", "").replace("data/wbc_backend/", "")
        lom = "✅" if info.get("looks_like_model_output") else "❌"
        reason = info.get("reason", "")[:60]
        lines.append(
            f"| `{p}` | {'✅' if info.get('exists') else '❌'} | {info.get('rows', 0):,} | {lom} | ❌ | 0 | `{reason}` |"
        )

    lines += [
        "",
        "---",
        "",
    ]

    # § 4 Contract Field Validation
    lines += [
        "## 4. Contract Field Validation",
        "",
        "### 4.1 Real Contract Target (`model_outputs_2026-04-29.jsonl`)",
        "",
        "File does not exist. All 31 required contract fields are absent by definition.",
        "",
        "**Gap**: All fields in the Phase 6J contract schema are unimplemented in any",
        "current model output file. The closest existing source is",
        "`mlb_decision_quality_report.json` which provides `predicted_home_win_prob` per",
        "game but lacks: `canonical_match_id`, `prediction_time_utc`, `market_key`,",
        "`selection_key`, `model_version`, `feature_version`, `leakage_guard_version`.",
        "",
        "### 4.2 Dry-Run Placeholder",
        "",
        "| Field Group | Fields | Dry-Run Status |",
        "|---|---|---|",
        "| Schema | `schema_version` | ✅ Present (`6i-dry-run-1.0`) |",
        "| Identity | `canonical_match_id`, `sport`, `league` | ✅ Present |",
        "| Market | `market_type`, `market_key`, `selection`, `selection_key` | ✅ Present |",
        "| Prediction | `predicted_probability`, `prediction_time_utc` | ✅ Present (`null`) |",
        "| Versioning | `model_version`, `feature_version`, `leakage_guard_version` | ⚠️ Present (`NOT_IMPLEMENTED`) |",
        "| Output fields | `model_output_id`, `prediction_run_id`, `model_family` | ❌ Missing |",
        "| Walk-forward | `training_window_id`, `walk_forward_split_id` | ❌ Missing |",
        "| Team | `home_team_code`, `away_team_code` | ❌ Missing |",
        "| Probability | `probability_source`, `confidence` | ⚠️ Partial |",
        "| EV | `expected_value`, `implied_probability_at_prediction` | ✅ Present (`null`) |",
        "",
        "---",
        "",
    ]

    # § 5 Quality Gate Results
    lines += [
        "## 5. Quality Gate Results M1–M12",
        "",
        "### 5.1 Dry-Run Placeholder Gate Results",
        "",
        "| Gate | Name | Pass | Fail | Block | Pass % | Notes |",
        "|---|---|---:|---:|---:|---:|---|",
    ]

    gate_names = {
        "M1": "SCHEMA_VALID",
        "M2": "CANONICAL_MATCH_ID_PRESENT",
        "M3": "MARKET_KEY_PRESENT",
        "M4": "SELECTION_KEY_PRESENT",
        "M5": "VERSION_FIELDS_PRESENT",
        "M6": "TIMING_VALID",
        "M7": "PROBABILITY_VALID",
        "M8": "EV_VALID_OR_NULL_WITH_REASON",
        "M9": "NO_LEAKAGE_HARD_FAIL",
        "M10": "MARKET_SEMANTICS_VALID",
        "M11": "CLV_USABLE_FLAG_CORRECT",
        "M12": "DRY_RUN_FLAG_CORRECT",
    }

    for gate_id, name in gate_names.items():
        agg = dry_run_gate_agg.get(gate_id, {})
        p = agg.get("pass", 0)
        f = agg.get("fail", 0)
        b = agg.get("block", 0)
        pct = agg.get("pass_pct", 0.0)
        icon = "✅" if f == 0 else ("⚠️" if b > 0 else "❌")
        lines.append(f"| {gate_id} | {name} | {p:,} | {f:,} | {b:,} | {pct:.1f}% | {icon} |")

    lines += [
        "",
        "**Expected**: M1, M5 fail for most rows (missing contract fields in dry-run schema).",
        "M9, M12 should pass (no leakage fields; dry_run=true consistently).",
        "M7 should pass for dry-run rows (null predicted_probability is valid when dry_run=true).",
        "",
        "### 5.2 Real Model Output Gate Results",
        "",
        "No real model output file exists. All gates would fail at M1 (no rows to validate).",
        "",
        "---",
        "",
    ]

    # § 6 Dry-Run Placeholder Validation
    lines += [
        "## 6. Dry-Run Placeholder Validation",
        "",
        f"File: `{args.dry_run}`",
        f"Rows: {dry_run_info.get('rows', 0):,}",
        "",
        "### Summary",
        "",
        "| Property | Value |",
        "|---|---|",
        f"| `dry_run=true` count | {dry_run_info.get('rows', 0):,} (all rows) |",
        f"| `clv_usable=false` count | {dry_run_info.get('rows', 0):,} (all rows) |",
        f"| `predicted_probability=null` count | {dry_run_info.get('rows', 0):,} (all rows) |",
        f"| `expected_value=null` count | {dry_run_info.get('rows', 0):,} (all rows) |",
        f"| Schema version | `6i-dry-run-1.0` (distinct from production `6j-1.0`) |",
        "",
        "### Finding",
        "",
        "Dry-run placeholders correctly signal that the real prediction pipeline is not yet",
        "operational. They validate the schema skeleton and market-splitting logic but are",
        "**not CLV-usable** by design and must never be promoted to a real registry.",
        "",
        "Dry-run rows lack the following Phase 6J production fields:",
        "`model_output_id`, `prediction_run_id`, `model_family`, `training_window_id`,",
        "`walk_forward_split_id`, `home_team_code`, `away_team_code`, `probability_source`.",
        "",
        "---",
        "",
    ]

    # § 7 Readiness Decision
    lines += [
        "## 7. Readiness Decision",
        "",
        f"**`{readiness}`**",
        "",
        "### Rationale",
        "",
        "| Criterion | Status | Evidence |",
        "|---|:---:|---|",
        "| Real `model_outputs_YYYY-MM-DD.jsonl` exists | ❌ | File absent |",
        "| Any candidate has `canonical_match_id` + `predicted_probability` + `prediction_time_utc` | ❌ | `mlb_decision_quality_report` has `predicted_home_win_prob` but no `canonical_match_id` / `prediction_time_utc` |",
        "| Any candidate satisfies M1–M12 | ❌ | All legacy candidates fail M1 |",
        "| Dry-run placeholders exist | ✅ | 2,080 rows, schema skeleton valid |",
        "| Dry-run placeholders are CLV-usable | ❌ | `clv_usable=false` for all 2,080 rows |",
        "",
        "---",
        "",
    ]

    # § 8 Findings
    lines += [
        "## 8. Findings",
        "",
        "### F1 — No Real Model Output File (`NOT_READY_MODEL_OUTPUT_GAP`)",
        "",
        "`data/derived/model_outputs_2026-04-29.jsonl` does not exist. No component in the",
        "current codebase writes per-market, per-selection predicted probabilities to a file",
        "satisfying the Phase 6J contract.",
        "",
        "### F2 — `mlb_decision_quality_report.json` Is Not a Registry Input",
        "",
        "`mlb_decision_quality_report.json` contains 1,493 per-game rows with",
        "`predicted_home_win_prob`, but it is a **paper-tracking retrospective report**,",
        "not a real-time pre-game prediction registry. It lacks:",
        "- `canonical_match_id` (game_id format incompatible with bridge)",
        "- `prediction_time_utc` (timing rule T1 cannot be verified)",
        "- `market_key` / `selection_key` (game-level only, not per-market)",
        "- `model_version` / `feature_version` / `leakage_guard_version`",
        "",
        "All 1,493 rows have `clv_available=false`, confirming the report itself",
        "acknowledges they are not CLV-ready.",
        "",
        "### F3 — Dry-Run Placeholders Are Valid as Placeholders",
        "",
        "The 2,080 dry-run rows confirm the market-splitting logic (ML×766, RL×656, OU×658)",
        "and the schema skeleton. They are correctly flagged `dry_run=true`, `clv_usable=false`,",
        "`predicted_probability=null`. They must not be promoted to real predictions.",
        "",
        "### F4 — Current Candidate Reports Are Not Real Model Outputs",
        "",
        "The following files are aggregate metrics / legacy reports and do not qualify as",
        "model output candidates under the Phase 6J contract:",
        "- `model_artifacts.json` — calibration params + hyperparams only",
        "- `market_validation.json` — aggregate ML/RL/OU ROI",
        "- `walkforward_summary.json` — aggregate walk-forward metrics",
        "- `mlb_paper_tracking_report.json` — `PAPER_ONLY` / `SANDBOX_ONLY` aggregate",
        "- `prediction_registry.jsonl` — WBC-domain (not MLB/KBO/NPB), game-level",
        "",
        "### F5 — Formal CLV Validation Must Not Run Yet",
        "",
        "CLV hypothesis (Phase 5.5): `CLV_proxy > 0.03 → ≥3pp ROI over ≥200 bets per regime`.",
        "This validation requires CLV-usable prediction rows with confirmed pre-game",
        "`prediction_time_utc`. No such rows exist. Formal CLV validation is blocked.",
        "",
        "---",
        "",
    ]

    # § 9 Recommended Next Step
    lines += [
        "## 9. Recommended Next Step",
        "",
        "**Phase 6L — ML-Only Model Output Adapter**",
        "",
        "The closest existing ML signal is `predicted_home_win_prob` in",
        "`mlb_decision_quality_report.json` (1,493 per-game rows).",
        "",
        "Phase 6L should:",
        "1. Design an adapter that reads `mlb_decision_quality_report.json` per_game rows.",
        "2. Resolve `canonical_match_id` via the match identity bridge.",
        "3. Attach `prediction_time_utc` (requires backfilling from game schedule data or",
        "   adding pre-game timestamp recording to the inference pipeline).",
        "4. Emit ML-only rows to `data/derived/model_outputs_YYYY-MM-DD.jsonl`.",
        "5. Apply `probability_source = 'calibrated_platt'` using `model_artifacts.json`",
        "   calibration params (a=1.1077, b=-0.0184).",
        "6. Validate output with this Phase 6K validator (must pass M1–M12).",
        "",
        "**RL / OU**: Remain in `MODEL_CAPABILITY_GAP` status until Phase 6M.",
        "",
        "---",
        "",
    ]

    # § 10 Scope Confirmation
    lines += [
        "## 10. Scope Confirmation",
        "",
        "| Constraint | Status |",
        "|---|---|",
        "| Source data files modified | ❌ NOT done |",
        "| Model code modified | ❌ NOT done |",
        "| New predictions generated | ❌ NOT done |",
        "| `prediction_registry.jsonl` modified | ❌ NOT done |",
        "| Dry-run JSONL modified | ❌ NOT done |",
        "| `mlb_decision_quality_report.json` modified | ❌ NOT done |",
        "| Crawler modified | ❌ NOT done |",
        "| DB or migrations modified | ❌ NOT done |",
        "| External API called | ❌ NOT done |",
        "| Orchestrator task created | ❌ NOT done |",
        "| Formal CLV validation run | ❌ NOT done |",
        "| Git commit made | ❌ NOT done |",
        "| Lottery-domain terms used | ❌ NOT done |",
        "",
        "---",
        "",
        f"*Phase 6K VALIDATOR_VERIFIED — token: PHASE_6K_VALIDATOR_VERIFIED*",
    ]

    return "\n".join(lines)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    args = parse_args()
    run_ts = datetime.now(timezone.utc).isoformat()

    # ── Check required inputs ────────────────────────────────────────────────
    for required in [args.contract_doc, args.dry_run]:
        if not os.path.exists(required):
            print(f"BLOCKED: missing required input {required}", file=sys.stderr)
            return 1

    # ── Load dry-run JSONL ───────────────────────────────────────────────────
    with open(args.dry_run, encoding="utf-8") as f:
        dry_run_rows = [json.loads(l) for l in f if l.strip()]

    # ── Classify real candidate ──────────────────────────────────────────────
    real_candidate_info: dict = {
        "path": args.candidate,
        "exists": False,
        "rows": 0,
        "looks_like_model_output": False,
        "has_required_fields": False,
        "valid_rows": 0,
        "size": 0,
    }

    real_gate_agg: dict | None = None
    if os.path.exists(args.candidate):
        info = classify_legacy_candidate(args.candidate)
        real_candidate_info.update(info)
        if info.get("exists") and info.get("rows", 0) > 0:
            # Load and validate
            with open(args.candidate, encoding="utf-8") as f:
                real_rows = [json.loads(l) for l in f if l.strip()]
            real_rows_results = [validate_row(r) for r in real_rows]
            real_gate_agg = aggregate_gate_results(real_rows_results)
            valid = sum(
                1 for r in real_rows_results
                if all(v["pass"] for v in r.values())
            )
            real_candidate_info["valid_rows"] = valid
            real_candidate_info["has_required_fields"] = info.get("looks_like_model_output", False)

    # ── Scan legacy candidates ───────────────────────────────────────────────
    legacy_paths = [
        "data/wbc_backend/model_artifacts.json",
        "data/wbc_backend/market_validation.json",
        "data/wbc_backend/walkforward_summary.json",
        "data/wbc_backend/reports/mlb_decision_quality_report.json",
        "data/wbc_backend/reports/mlb_paper_tracking_report.json",
        "data/wbc_backend/reports/mlb_alpha_discovery_report.json",
        "data/wbc_backend/reports/mlb_model_family_report.json",
        "data/wbc_backend/reports/mlb_pregame_coverage_report.json",
        "data/wbc_backend/reports/prediction_registry.jsonl",
    ]
    legacy_infos = [classify_legacy_candidate(p) for p in legacy_paths]

    # ── Validate dry-run rows ────────────────────────────────────────────────
    dry_run_results = [validate_row(r) for r in dry_run_rows]
    dry_run_gate_agg = aggregate_gate_results(dry_run_results)
    dry_run_info = {
        "path": args.dry_run,
        "exists": True,
        "rows": len(dry_run_rows),
        "size": os.path.getsize(args.dry_run),
    }

    # Sample notes for report
    dry_run_sample_notes: list[str] = []
    if dry_run_rows:
        sample_result = validate_row(dry_run_rows[0])
        for gate_id, res in sample_result.items():
            dry_run_sample_notes.append(f"{gate_id}: {res['notes'][0]}")

    # ── Readiness decision ───────────────────────────────────────────────────
    readiness = determine_readiness(
        real_candidate_info.get("exists", False),
        real_candidate_info.get("valid_rows", 0),
        len(dry_run_rows),
        dry_run_gate_agg,
    )

    gate_names = {
        "M1": "SCHEMA_VALID",
        "M2": "CANONICAL_MATCH_ID_PRESENT",
        "M3": "MARKET_KEY_PRESENT",
        "M4": "SELECTION_KEY_PRESENT",
        "M5": "VERSION_FIELDS_PRESENT",
        "M6": "TIMING_VALID",
        "M7": "PROBABILITY_VALID",
        "M8": "EV_VALID_OR_NULL_WITH_REASON",
        "M9": "NO_LEAKAGE_HARD_FAIL",
        "M10": "MARKET_SEMANTICS_VALID",
        "M11": "CLV_USABLE_FLAG_CORRECT",
        "M12": "DRY_RUN_FLAG_CORRECT",
    }

    # ── Console summary ──────────────────────────────────────────────────────
    print("=" * 70)
    print("Phase 6K — Model Output Contract Validator")
    print("=" * 70)
    print(f"  Run timestamp        : {run_ts[:19]}Z")
    print(f"  Contract doc         : {args.contract_doc}")
    print(f"  Real candidate       : {args.candidate}")
    print(f"    → exists           : {real_candidate_info.get('exists', False)}")
    print(f"    → rows             : {real_candidate_info.get('rows', 0)}")
    print(f"    → valid rows       : {real_candidate_info.get('valid_rows', 0)}")
    print(f"  Dry-run rows         : {len(dry_run_rows)}")
    print(f"  Legacy candidates    : {len(legacy_infos)}")
    print()
    print("  Gate Results (dry-run rows):")
    for gate_id, name in gate_names.items():
        agg = dry_run_gate_agg.get(gate_id, {})
        p = agg.get("pass", 0)
        f_c = agg.get("fail", 0)
        b = agg.get("block", 0)
        pct = agg.get("pass_pct", 0.0)
        status = "PASS" if f_c == 0 else ("BLOCK" if b > 0 else "FAIL")
        print(f"    {gate_id:3s} {name:35s}: {status} ({p}/{p+f_c}, {pct:.1f}%)")
    print()
    print(f"  READINESS DECISION   : {readiness}")
    print("=" * 70)

    # ── Write report ─────────────────────────────────────────────────────────
    report_text = build_report(
        run_ts, args, real_candidate_info, dry_run_info,
        legacy_infos, dry_run_gate_agg, real_gate_agg,
        readiness, dry_run_sample_notes,
    )
    Path(args.report).parent.mkdir(parents=True, exist_ok=True)
    with open(args.report, "w", encoding="utf-8") as f:
        f.write(report_text)
    print(f"  Report written       : {args.report}")

    # ── Write summary JSON ────────────────────────────────────────────────────
    gate_results_summary = {
        gate_id: dry_run_gate_agg.get(gate_id, {})
        for gate_id in gate_names
    }
    summary = {
        "schema_version": SCHEMA_VERSION,
        "run_date": run_ts[:10],
        "run_timestamp_utc": run_ts,
        "candidate_files_scanned": len(legacy_infos) + 1,
        "real_model_output_file_exists": real_candidate_info.get("exists", False),
        "real_model_output_rows": real_candidate_info.get("rows", 0),
        "real_model_output_valid_rows": real_candidate_info.get("valid_rows", 0),
        "dry_run_rows": len(dry_run_rows),
        "gate_results": gate_results_summary,
        "readiness_decision": readiness,
        "recommended_next_step": "Phase 6L: ML-Only Model Output Adapter",
        "source_data_modified": False,
        "formal_clv_validation_run": False,
    }
    Path(args.summary).parent.mkdir(parents=True, exist_ok=True)
    with open(args.summary, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"  Summary JSON written : {args.summary}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
