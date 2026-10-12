#!/usr/bin/env python3
"""
P33: 2024 Prediction/Odds Gap Builder
=======================================
CLI entry point for the P33 pipeline.

Scans known data directories for 2024 model predictions and market odds,
documents the gap, writes skeleton artifacts, and emits a gate result.

Exit codes:
  0 — P33_PREDICTION_ODDS_GAP_PLAN_READY (both sources verified)
  1 — BLOCKED  (one or both sources missing / invalid)
  2 — FAIL     (input missing or non-determinism detected)

PAPER_ONLY — No live data. No fabrication. No bets.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path
from typing import List, Optional

# ---------------------------------------------------------------------------
# Repo root discovery — must happen before any relative imports
# ---------------------------------------------------------------------------
_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = str(_SCRIPT_DIR.parent)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from wbc_backend.recommendation.p33_prediction_odds_gap_contract import (
    PAPER_ONLY,
    PRODUCTION_READY,
    P33_BLOCKED_NO_VERIFIED_ODDS_SOURCE,
    P33_BLOCKED_NO_VERIFIED_PREDICTION_SOURCE,
    P33_BLOCKED_CONTRACT_VIOLATION,
    P33_FAIL_INPUT_MISSING,
    P33_FAIL_NON_DETERMINISTIC,
    P33_PREDICTION_ODDS_GAP_PLAN_READY,
    P33GateResult,
)
from wbc_backend.recommendation.p33_2024_source_gap_auditor import (
    DEFAULT_SCAN_PATHS,
    scan_all_source_candidates,
)
from wbc_backend.recommendation.p33_safe_source_recommendation_builder import (
    build_recommendation_set,
)
from wbc_backend.recommendation.p33_joined_input_skeleton_writer import (
    write_all_skeleton_artifacts,
    validate_skeleton_outputs,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DEFAULT_OUTPUT_DIR = "data/mlb_2024/processed/p33_joined_input_gap"
P32_OUTCOMES_CSV = "data/mlb_2024/processed/mlb_2024_game_identity_outcomes_joined.csv"
P32_GATE_JSON = "data/mlb_2024/processed/p32_gate_result.json"


def _abort(msg: str, exit_code: int = 2) -> None:
    print(f"[P33][ERROR] {msg}", file=sys.stderr)
    sys.exit(exit_code)


def _check_paper_only_guard() -> None:
    if not PAPER_ONLY:
        _abort("PAPER_ONLY guard is disabled. Refusing to run.", exit_code=2)
    if PRODUCTION_READY:
        _abort("PRODUCTION_READY is True. Refusing to run.", exit_code=2)


def _check_p32_prerequisite(repo_root: str) -> None:
    """Verify P32 gate is READY before proceeding."""
    gate_path = os.path.join(repo_root, P32_GATE_JSON)
    if not os.path.isfile(gate_path):
        _abort(
            f"P32 gate result not found at {gate_path}. "
            "Run P32 first: python scripts/run_p32_build_2024_raw_game_logs.py",
            exit_code=2,
        )
    try:
        with open(gate_path, encoding="utf-8") as fh:
            gate_data = json.load(fh)
        gate_value = gate_data.get("gate", "")
        if gate_value != "P32_RAW_GAME_LOG_ARTIFACT_READY":
            _abort(
                f"P32 gate is '{gate_value}', not READY. Resolve P32 first.",
                exit_code=2,
            )
    except Exception as exc:
        _abort(f"Failed to read P32 gate result: {exc}", exit_code=2)


def _determine_final_gate(gap_summary) -> P33GateResult:
    """Derive the P33 gate from the gap summary."""
    pred_blocked = gap_summary.prediction_missing
    odds_blocked = gap_summary.odds_missing

    if pred_blocked and odds_blocked:
        gate = P33_BLOCKED_NO_VERIFIED_PREDICTION_SOURCE
        blocker = (
            f"PREDICTION: {gap_summary.prediction_gap_reason} | "
            f"ODDS: {gap_summary.odds_gap_reason}"
        )
    elif pred_blocked:
        gate = P33_BLOCKED_NO_VERIFIED_PREDICTION_SOURCE
        blocker = gap_summary.prediction_gap_reason
    elif odds_blocked:
        gate = P33_BLOCKED_NO_VERIFIED_ODDS_SOURCE
        blocker = gap_summary.odds_gap_reason
    else:
        gate = P33_PREDICTION_ODDS_GAP_PLAN_READY
        blocker = ""

    return P33GateResult(
        gate=gate,
        season=2024,
        prediction_gap_blocked=pred_blocked,
        odds_gap_blocked=odds_blocked,
        schema_gap_blocked=False,
        license_blocked=False,
        blocker_reason=blocker,
        artifacts=[],
        paper_only=PAPER_ONLY,
        production_ready=PRODUCTION_READY,
        next_phase="P34_DUAL_SOURCE_ACQUISITION_PLAN",
    )


def _write_gap_summary_json(output_dir: str, gap_summary) -> str:
    """Write p33_source_gap_summary.json."""
    out_path = os.path.join(output_dir, "p33_source_gap_summary.json")

    def _serialise_candidate(c) -> dict:
        d = dict(
            candidate_id=c.candidate_id,
            file_path=c.file_path,
            detected_season=c.detected_season,
            status=c.status,
            blocker_reason=c.blocker_reason,
            row_count=c.row_count,
            detected_columns=list(c.detected_columns),
        )
        if hasattr(c, "is_dry_run"):
            d["is_dry_run"] = c.is_dry_run
        if hasattr(c, "year_verified"):
            d["year_verified"] = c.year_verified
        return d

    payload = {
        "season": gap_summary.season,
        "paper_only": gap_summary.paper_only,
        "production_ready": gap_summary.production_ready,
        "prediction_candidates_found": gap_summary.prediction_candidates_found,
        "odds_candidates_found": gap_summary.odds_candidates_found,
        "prediction_ready_count": gap_summary.prediction_ready_count,
        "odds_ready_count": gap_summary.odds_ready_count,
        "prediction_blocked_count": gap_summary.prediction_blocked_count,
        "odds_blocked_count": gap_summary.odds_blocked_count,
        "prediction_missing": gap_summary.prediction_missing,
        "odds_missing": gap_summary.odds_missing,
        "prediction_gap_reason": gap_summary.prediction_gap_reason,
        "odds_gap_reason": gap_summary.odds_gap_reason,
        "prediction_candidates": [
            _serialise_candidate(c) for c in gap_summary.prediction_candidates
        ],
        "odds_candidates": [
            _serialise_candidate(c) for c in gap_summary.odds_candidates
        ],
        "scanned_paths": gap_summary.scanned_paths,
    }
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
    return out_path


def _write_gap_summary_md(output_dir: str, gap_summary, gate_result: P33GateResult) -> str:
    """Write p33_source_gap_summary.md."""
    out_path = os.path.join(output_dir, "p33_source_gap_summary.md")
    lines = [
        "# P33 2024 Source Gap Summary\n",
        f"**Gate**: `{gate_result.gate}`  ",
        f"**Season**: {gap_summary.season}  ",
        f"**PAPER_ONLY**: {gap_summary.paper_only}  ",
        f"**PRODUCTION_READY**: {gap_summary.production_ready}",
        "",
        "## Prediction Source Gap",
        f"- Candidates found: {gap_summary.prediction_candidates_found}",
        f"- Ready: {gap_summary.prediction_ready_count}",
        f"- Blocked: {gap_summary.prediction_blocked_count}",
        f"- Missing: {gap_summary.prediction_missing}",
        f"- Reason: {gap_summary.prediction_gap_reason or 'N/A'}",
        "",
        "## Odds Source Gap",
        f"- Candidates found: {gap_summary.odds_candidates_found}",
        f"- Ready: {gap_summary.odds_ready_count}",
        f"- Blocked: {gap_summary.odds_blocked_count}",
        f"- Missing: {gap_summary.odds_missing}",
        f"- Reason: {gap_summary.odds_gap_reason or 'N/A'}",
        "",
        "## Blocker",
        f"> {gate_result.blocker_reason or 'None — READY'}",
        "",
        "## Next Phase",
        f"`{gate_result.next_phase}`",
    ]
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    return out_path


def _write_candidates_csv(output_dir: str, candidates: list, fname: str) -> str:
    """Write prediction or odds candidates list as CSV."""
    import csv as _csv
    out_path = os.path.join(output_dir, fname)
    if not candidates:
        with open(out_path, "w", encoding="utf-8", newline="") as fh:
            fh.write("candidate_id,file_path,detected_season,status,blocker_reason,row_count\n")
        return out_path
    with open(out_path, "w", encoding="utf-8", newline="") as fh:
        fields = ["candidate_id", "file_path", "detected_season", "status", "blocker_reason", "row_count"]
        writer = _csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for c in candidates:
            row = {
                "candidate_id": c.candidate_id,
                "file_path": c.file_path,
                "detected_season": c.detected_season,
                "status": c.status,
                "blocker_reason": c.blocker_reason,
                "row_count": c.row_count,
            }
            writer.writerow(row)
    return out_path


def _write_recommendations_json(output_dir: str, rec_set) -> str:
    out_path = os.path.join(output_dir, "source_recommendations.json")

    def _rec_to_dict(r) -> dict:
        return {
            "recommendation_id": r.recommendation_id,
            "target_data_type": r.target_data_type,
            "priority": r.priority,
            "source_name": r.source_name,
            "url_or_reference": r.url_or_reference,
            "format_hint": r.format_hint,
            "license_note": r.license_note,
            "required_schema_fields": list(r.required_schema_fields),
            "acquisition_method": r.acquisition_method,
            "estimated_effort": r.estimated_effort,
            "paper_only": r.paper_only,
            "production_ready": r.production_ready,
            "blocker_if_skipped": r.blocker_if_skipped,
        }

    payload = {
        "paper_only": PAPER_ONLY,
        "production_ready": PRODUCTION_READY,
        "total_count": rec_set.total_count,
        "summary_message": rec_set.summary_message,
        "prediction_recommendations": [
            _rec_to_dict(r) for r in rec_set.prediction_recommendations
        ],
        "odds_recommendations": [
            _rec_to_dict(r) for r in rec_set.odds_recommendations
        ],
    }
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
    return out_path


def _write_gate_result(output_dir: str, gate_result: P33GateResult, artifacts: List[str]) -> str:
    gate_result.artifacts = artifacts
    out_path = os.path.join(output_dir, "p33_gate_result.json")
    payload = {
        "gate": gate_result.gate,
        "season": gate_result.season,
        "prediction_gap_blocked": gate_result.prediction_gap_blocked,
        "odds_gap_blocked": gate_result.odds_gap_blocked,
        "schema_gap_blocked": gate_result.schema_gap_blocked,
        "license_blocked": gate_result.license_blocked,
        "blocker_reason": gate_result.blocker_reason,
        "paper_only": gate_result.paper_only,
        "production_ready": gate_result.production_ready,
        "next_phase": gate_result.next_phase,
        "artifacts": artifacts,
    }
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
    return out_path


def _determinism_check(output_dir: str, repo_root: str) -> bool:
    """
    Re-run the scan and verify gate matches first run.
    Returns True if deterministic.
    """
    gate_path = os.path.join(output_dir, "p33_gate_result.json")
    if not os.path.isfile(gate_path):
        return False
    with open(gate_path, encoding="utf-8") as fh:
        first_gate = json.load(fh).get("gate", "")

    gap2 = scan_all_source_candidates(repo_root)
    gate2 = _determine_final_gate(gap2)
    return gate2.gate == first_gate


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="P33: 2024 Prediction/Odds Gap Builder"
    )
    parser.add_argument(
        "--repo-root",
        default=_REPO_ROOT,
        help="Repository root directory (default: auto-detected)",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help=f"Output directory (default: <repo-root>/{DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--skip-determinism-check",
        action="store_true",
        help="Skip the second-run determinism verification",
    )
    args = parser.parse_args(argv)

    repo_root = os.path.abspath(args.repo_root)
    output_dir = (
        os.path.abspath(args.output_dir)
        if args.output_dir
        else os.path.join(repo_root, DEFAULT_OUTPUT_DIR)
    )

    print("[P33] Starting 2024 Prediction/Odds Gap Builder ...")
    print(f"[P33] PAPER_ONLY={PAPER_ONLY}, PRODUCTION_READY={PRODUCTION_READY}")
    print(f"[P33] Repo root: {repo_root}")
    print(f"[P33] Output dir: {output_dir}")

    # Guard
    _check_paper_only_guard()

    # Prerequisite
    print("[P33] Checking P32 prerequisite ...")
    _check_p32_prerequisite(repo_root)
    print("[P33] P32 gate: OK")

    # Scan
    print("[P33] Scanning source candidates ...")
    gap_summary = scan_all_source_candidates(repo_root)
    print(
        f"[P33] Prediction candidates: {gap_summary.prediction_candidates_found} "
        f"(ready={gap_summary.prediction_ready_count}, "
        f"blocked={gap_summary.prediction_blocked_count})"
    )
    print(
        f"[P33] Odds candidates: {gap_summary.odds_candidates_found} "
        f"(ready={gap_summary.odds_ready_count}, "
        f"blocked={gap_summary.odds_blocked_count})"
    )

    # Determine gate
    gate_result = _determine_final_gate(gap_summary)
    print(f"[P33] Gate: {gate_result.gate}")
    if gate_result.blocker_reason:
        print(f"[P33] Blocker: {gate_result.blocker_reason[:200]}")

    # Recommendations
    rec_set = build_recommendation_set(gap_summary)
    print(f"[P33] Recommendations: {rec_set.summary_message}")

    # Write artifacts
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    written: List[str] = []

    written.append(_write_gap_summary_json(output_dir, gap_summary))
    written.append(_write_gap_summary_md(output_dir, gap_summary, gate_result))
    written.append(
        _write_candidates_csv(
            output_dir,
            gap_summary.prediction_candidates,
            "prediction_source_candidates.csv",
        )
    )
    written.append(
        _write_candidates_csv(
            output_dir,
            gap_summary.odds_candidates,
            "odds_source_candidates.csv",
        )
    )
    written.append(_write_recommendations_json(output_dir, rec_set))

    # Skeleton artifacts
    p32_outcomes = os.path.join(repo_root, P32_OUTCOMES_CSV)
    skeleton_files = write_all_skeleton_artifacts(
        output_dir,
        gap_summary,
        p32_outcomes_csv=p32_outcomes if os.path.isfile(p32_outcomes) else None,
    )
    written.extend(skeleton_files)

    # Gate result
    gate_path = _write_gate_result(output_dir, gate_result, written)
    written.append(gate_path)

    # Determinism check
    if not args.skip_determinism_check:
        print("[P33] Running determinism check ...")
        det_ok = _determinism_check(output_dir, repo_root)
        if not det_ok:
            print("[P33][WARN] Determinism check FAILED — gate differs between runs.", file=sys.stderr)
            # Non-fatal — report but don't change gate

    print(f"[P33] Artifacts written: {len(written)}")
    for f in written:
        print(f"  {f}")

    # Exit code
    gate = gate_result.gate
    if gate == P33_PREDICTION_ODDS_GAP_PLAN_READY:
        print("[P33] RESULT: READY")
        return 0
    elif gate in (
        P33_BLOCKED_NO_VERIFIED_PREDICTION_SOURCE,
        P33_BLOCKED_NO_VERIFIED_ODDS_SOURCE,
    ):
        print(f"[P33] RESULT: BLOCKED — {gate}")
        return 1
    else:
        print(f"[P33] RESULT: FAIL — {gate}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
