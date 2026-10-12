#!/usr/bin/env python3
"""
P34 Dual Source Acquisition Plan — CLI Entry Point
====================================================
Runs the full P34 pipeline: loads P32 game logs, P33 candidates,
builds prediction + odds acquisition options, writes schema templates,
assembles the plan, determines gate, writes all output artifacts.

Exit codes:
  0 = P34_DUAL_SOURCE_ACQUISITION_PLAN_READY
  1 = BLOCKED_*
  2 = FAIL_*

PAPER_ONLY=True  PRODUCTION_READY=False
No fabricated predictions or odds. No live API calls. No scraping.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import List, Optional

# Ensure repo root is on path when called as a script
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT_DEFAULT = os.path.dirname(_SCRIPT_DIR)
if _REPO_ROOT_DEFAULT not in sys.path:
    sys.path.insert(0, _REPO_ROOT_DEFAULT)

from wbc_backend.recommendation.p34_dual_source_acquisition_contract import (
    P34_BLOCKED_CONTRACT_VIOLATION,
    P34_DUAL_SOURCE_ACQUISITION_PLAN_READY,
    P34_FAIL_INPUT_MISSING,
    P34_FAIL_NON_DETERMINISTIC,
    PAPER_ONLY,
    PRODUCTION_READY,
    P34GateResult,
)
from wbc_backend.recommendation.p34_dual_source_plan_builder import (
    build_dual_source_acquisition_plan,
    determine_p34_gate,
    validate_dual_source_plan,
    write_p34_outputs,
)
from wbc_backend.recommendation.p34_joined_input_schema_package import (
    write_schema_templates,
    validate_schema_templates,
)
from wbc_backend.recommendation.p34_odds_source_planner import (
    build_odds_acquisition_options,
    load_p33_odds_candidates,
    rank_odds_options,
    summarize_odds_plan,
)
from wbc_backend.recommendation.p34_prediction_source_planner import (
    build_prediction_acquisition_options,
    evaluate_oof_rebuild_feasibility,
    load_p32_game_logs,
    load_p33_prediction_candidates,
    rank_prediction_options,
    summarize_prediction_plan,
)

# ---------------------------------------------------------------------------
# Default paths
# ---------------------------------------------------------------------------

DEFAULT_P32_DIR = "data/mlb_2024/processed"
DEFAULT_P33_DIR = "data/mlb_2024/processed/p33_joined_input_gap"
DEFAULT_OUTPUT_DIR = "data/mlb_2024/processed/p34_dual_source_acquisition"

# Expected output file names (all 8 required artifacts)
P34_OUTPUT_FILES = (
    "prediction_acquisition_options.json",
    "odds_acquisition_options.json",
    "dual_source_acquisition_plan.json",
    "dual_source_acquisition_plan.md",
    "prediction_import_template.csv",
    "odds_import_template.csv",
    "joined_input_validation_rules.json",
    "p34_gate_result.json",
)

# P32 prerequisite
P32_GAME_LOG_CSV = "mlb_2024_game_identity_outcomes_joined.csv"
P32_GATE_JSON = "p32_gate_result.json"
P32_READY_GATE = "P32_RAW_GAME_LOG_ARTIFACT_READY"

# P33 prerequisite
P33_GATE_JSON = "p33_gate_result.json"
P33_PREDICTION_CSV = "prediction_source_candidates.csv"
P33_ODDS_CSV = "odds_source_candidates.csv"


# ---------------------------------------------------------------------------
# Guards
# ---------------------------------------------------------------------------


def _check_paper_only_guard() -> None:
    """Abort if PAPER_ONLY guard is violated."""
    if not PAPER_ONLY:
        print("[P34][FATAL] PAPER_ONLY=False. CLI must not run in production mode.", file=sys.stderr)
        sys.exit(2)
    if PRODUCTION_READY:
        print("[P34][FATAL] PRODUCTION_READY=True. CLI must not run in production mode.", file=sys.stderr)
        sys.exit(2)


def _check_p32_prerequisite(p32_dir: str) -> None:
    """Verify P32 gate is ready. Abort (exit 2) if missing or incorrect."""
    gate_path = os.path.join(p32_dir, P32_GATE_JSON)
    if not os.path.isfile(gate_path):
        print(f"[P34][FAIL] P32 gate file not found: {gate_path}", file=sys.stderr)
        sys.exit(2)
    try:
        with open(gate_path, encoding="utf-8") as fh:
            data = json.load(fh)
        gate_val = data.get("gate", "")
    except Exception as exc:
        print(f"[P34][FAIL] Cannot read P32 gate file: {exc}", file=sys.stderr)
        sys.exit(2)
    if gate_val != P32_READY_GATE:
        print(
            f"[P34][FAIL] P32 gate is '{gate_val}', expected '{P32_READY_GATE}'.",
            file=sys.stderr,
        )
        sys.exit(2)
    print(f"[P34] P32 gate: OK ({gate_val})")


def _check_p33_prerequisite(p33_dir: str) -> None:
    """Verify P33 artifacts exist. Abort (exit 2) if missing."""
    gate_path = os.path.join(p33_dir, P33_GATE_JSON)
    if not os.path.isfile(gate_path):
        print(f"[P34][FAIL] P33 gate file not found: {gate_path}", file=sys.stderr)
        sys.exit(2)
    print(f"[P34] P33 gate: found")


# ---------------------------------------------------------------------------
# Determinism check
# ---------------------------------------------------------------------------


def _compare_determinism(dir1: str, dir2: str) -> bool:
    """
    Compare key output files between two runs to verify determinism.
    Excludes 'generated_at' and 'output_dir' fields from JSON comparisons.
    Returns True if deterministic, False if mismatch.
    """
    json_files = [
        "prediction_acquisition_options.json",
        "odds_acquisition_options.json",
        "dual_source_acquisition_plan.json",
        "joined_input_validation_rules.json",
        "p34_gate_result.json",
    ]
    csv_files = [
        "prediction_import_template.csv",
        "odds_import_template.csv",
    ]

    def _normalize_json(path: str) -> dict:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        # Remove time-varying keys
        for key in ("generated_at", "output_dir", "artifacts"):
            data.pop(key, None)
        # Remove generated_at from nested options
        for opt_list_key in ("options",):
            if opt_list_key in data and isinstance(data[opt_list_key], list):
                for item in data[opt_list_key]:
                    if isinstance(item, dict):
                        item.pop("generated_at", None)
        return data

    for fname in json_files:
        p1 = os.path.join(dir1, fname)
        p2 = os.path.join(dir2, fname)
        if not os.path.isfile(p1) or not os.path.isfile(p2):
            print(f"[P34][WARN] Determinism: missing file {fname}", file=sys.stderr)
            return False
        try:
            d1 = _normalize_json(p1)
            d2 = _normalize_json(p2)
        except Exception as exc:
            print(f"[P34][WARN] Determinism JSON parse error for {fname}: {exc}", file=sys.stderr)
            return False
        if d1 != d2:
            print(f"[P34][WARN] Determinism mismatch: {fname}", file=sys.stderr)
            return False

    for fname in csv_files:
        p1 = os.path.join(dir1, fname)
        p2 = os.path.join(dir2, fname)
        if not os.path.isfile(p1) or not os.path.isfile(p2):
            print(f"[P34][WARN] Determinism: missing CSV {fname}", file=sys.stderr)
            return False
        c1 = open(p1, encoding="utf-8").read()
        c2 = open(p2, encoding="utf-8").read()
        if c1 != c2:
            print(f"[P34][WARN] Determinism mismatch: {fname}", file=sys.stderr)
            return False

    return True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv: Optional[List[str]] = None) -> int:
    """
    CLI entry point for P34.
    Returns exit code (0=READY, 1=BLOCKED, 2=FAIL).
    """
    parser = argparse.ArgumentParser(
        description="P34 Dual Source Acquisition Plan Builder"
    )
    parser.add_argument(
        "--p32-dir",
        default=DEFAULT_P32_DIR,
        help="Directory containing P32 processed artifacts.",
    )
    parser.add_argument(
        "--p33-dir",
        default=DEFAULT_P33_DIR,
        help="Directory containing P33 gap analysis artifacts.",
    )
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help="Output directory for P34 artifacts.",
    )
    parser.add_argument(
        "--paper-only",
        default="true",
        help="Must be 'true'. Safety guard.",
    )
    parser.add_argument(
        "--skip-determinism-check",
        action="store_true",
        default=False,
        help="Skip second-run determinism check.",
    )
    args = parser.parse_args(argv)

    # -----------------------------------------------------------------------
    # Guards
    # -----------------------------------------------------------------------
    print("[P34] Starting Dual Source Acquisition Plan Builder ...")
    print(f"[P34] PAPER_ONLY={PAPER_ONLY}, PRODUCTION_READY={PRODUCTION_READY}")
    _check_paper_only_guard()

    if args.paper_only.lower() != "true":
        print("[P34][FATAL] --paper-only must be 'true'.", file=sys.stderr)
        sys.exit(2)

    # -----------------------------------------------------------------------
    # Prerequisite checks
    # -----------------------------------------------------------------------
    _check_p32_prerequisite(args.p32_dir)
    _check_p33_prerequisite(args.p33_dir)

    # -----------------------------------------------------------------------
    # Load P32 game logs
    # -----------------------------------------------------------------------
    p32_csv = os.path.join(args.p32_dir, P32_GAME_LOG_CSV)
    print(f"[P34] Loading P32 game logs from: {p32_csv}")
    game_logs_df = load_p32_game_logs(p32_csv)
    if game_logs_df.empty:
        print(f"[P34][WARN] P32 game logs empty or missing: {p32_csv}")
    else:
        print(f"[P34] P32 game logs: {len(game_logs_df)} rows")

    # -----------------------------------------------------------------------
    # Load P33 candidates
    # -----------------------------------------------------------------------
    p33_pred_csv = os.path.join(args.p33_dir, P33_PREDICTION_CSV)
    p33_odds_csv = os.path.join(args.p33_dir, P33_ODDS_CSV)
    pred_candidates_df = load_p33_prediction_candidates(p33_pred_csv)
    odds_candidates_df = load_p33_odds_candidates(p33_odds_csv)
    print(
        f"[P34] P33 prediction candidates: {len(pred_candidates_df)}, "
        f"odds candidates: {len(odds_candidates_df)}"
    )

    # -----------------------------------------------------------------------
    # Build prediction + odds acquisition options
    # -----------------------------------------------------------------------
    print("[P34] Building prediction acquisition options ...")
    prediction_options = build_prediction_acquisition_options(game_logs_df, pred_candidates_df)
    ranked_pred = rank_prediction_options(prediction_options)
    best_pred = ranked_pred[0] if ranked_pred else None
    print(
        f"[P34] Prediction options: {len(prediction_options)} "
        f"(best={best_pred.option_id if best_pred else 'none'}, "
        f"status={best_pred.status if best_pred else 'n/a'})"
    )

    print("[P34] Building odds acquisition options ...")
    odds_options = build_odds_acquisition_options(odds_candidates_df)
    ranked_odds = rank_odds_options(odds_options)
    best_odds = ranked_odds[0] if ranked_odds else None
    print(
        f"[P34] Odds options: {len(odds_options)} "
        f"(best={best_odds.option_id if best_odds else 'none'}, "
        f"status={best_odds.status if best_odds else 'n/a'})"
    )

    # -----------------------------------------------------------------------
    # Write schema templates
    # -----------------------------------------------------------------------
    print("[P34] Writing schema templates ...")
    schema_files = write_schema_templates(args.output_dir)
    schema_valid = validate_schema_templates(args.output_dir)
    print(f"[P34] Schema templates: {len(schema_files)} written, valid={schema_valid}")

    # -----------------------------------------------------------------------
    # Build plan and determine gate
    # -----------------------------------------------------------------------
    plan = build_dual_source_acquisition_plan(
        prediction_options=prediction_options,
        odds_options=odds_options,
        schema_written=schema_valid,
    )

    if not validate_dual_source_plan(plan):
        print("[P34][FAIL] Plan failed safety validation.", file=sys.stderr)
        sys.exit(2)

    gate = determine_p34_gate(plan)
    print(f"[P34] Gate: {gate.gate}")
    if gate.license_risk:
        print(f"[P34] License risk: {gate.license_risk}")
    if gate.blocker_reason:
        print(f"[P34] Blocker: {gate.blocker_reason}")

    # -----------------------------------------------------------------------
    # Write outputs
    # -----------------------------------------------------------------------
    print("[P34] Writing output artifacts ...")
    artifacts = write_p34_outputs(
        output_dir=args.output_dir,
        plan=plan,
        gate=gate,
        schema_written_files=schema_files,
    )
    print(f"[P34] Artifacts written: {len(artifacts)}")
    for art in artifacts:
        print(f"  {art}")

    # -----------------------------------------------------------------------
    # Determinism check
    # -----------------------------------------------------------------------
    if not args.skip_determinism_check:
        print("[P34] Running determinism check ...")
        import tempfile
        det_dir = tempfile.mkdtemp(prefix="p34_det_")
        det_schema = write_schema_templates(det_dir)
        det_pred = build_prediction_acquisition_options(game_logs_df, pred_candidates_df)
        det_odds = build_odds_acquisition_options(odds_candidates_df)
        det_plan = build_dual_source_acquisition_plan(det_pred, det_odds, schema_written=True)
        det_gate = determine_p34_gate(det_plan)
        write_p34_outputs(
            output_dir=det_dir,
            plan=det_plan,
            gate=det_gate,
            schema_written_files=det_schema,
        )
        det_ok = _compare_determinism(args.output_dir, det_dir)
        if det_ok:
            print("[P34] Determinism check: PASS")
        else:
            print("[P34][WARN] Determinism check: FAIL — gate or options differ between runs.")

    # -----------------------------------------------------------------------
    # Final result
    # -----------------------------------------------------------------------
    print("")
    print(f"[P34] === RESULT ===")
    print(f"[P34] gate:                     {gate.gate}")
    print(f"[P34] best_prediction_option:   {plan.best_prediction_option_id}")
    print(f"[P34] best_odds_option:         {plan.best_odds_option_id}")
    print(f"[P34] prediction_path_status:   {plan.prediction_path_status}")
    print(f"[P34] odds_path_status:         {plan.odds_path_status}")
    print(f"[P34] schema_templates_written: {schema_valid}")
    print(f"[P34] production_ready:         {PRODUCTION_READY}")
    print(f"[P34] paper_only:               {PAPER_ONLY}")
    if gate.license_risk:
        print(f"[P34] license_risk:             {gate.license_risk}")
    print(
        f"[P34] recommended_next_action: "
        f"Complete license review for {plan.best_odds_option_id}, "
        f"then begin OOF feature engineering for {plan.best_prediction_option_id}."
    )

    if gate.gate == P34_DUAL_SOURCE_ACQUISITION_PLAN_READY:
        print(f"\n[P34] RESULT: READY — {gate.gate}")
        return 0
    elif gate.gate.startswith("P34_BLOCKED"):
        print(f"\n[P34] RESULT: BLOCKED — {gate.gate}")
        return 1
    else:
        print(f"\n[P34] RESULT: FAIL — {gate.gate}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
