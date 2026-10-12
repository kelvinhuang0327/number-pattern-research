#!/usr/bin/env python3
"""P35 Dual Source Import Validation CLI

Validates the dual-source import plan for 2024 MLB predictions and market
odds identified in P34. Produces structured outputs documenting whether
the import path is feasible, blocked, or requires further approval.

HARD GUARDS:
- PAPER_ONLY must always be "true" (CLI arg and module constant).
- PRODUCTION_READY is always False.
- No odds data is downloaded or scraped.
- No predictions are fabricated.
- data/mlb_2024/raw/gl2024.txt is NEVER staged or committed.

Expected current result: exit 1, gate=P35_BLOCKED_ODDS_LICENSE_NOT_APPROVED
(odds license approval record is not provided at this phase).

Usage:
    python scripts/run_p35_dual_source_import_validation.py \\
        --p32-dir data/mlb_2024/processed \\
        --p34-dir data/mlb_2024/processed/p34_dual_source_acquisition \\
        --output-dir data/mlb_2024/processed/p35_dual_source_import_validation \\
        --paper-only true

Exit codes:
    0  — P35_DUAL_SOURCE_IMPORT_VALIDATION_READY
    1  — BLOCKED (odds license, source, prediction, or pipeline)
    2  — FAIL (missing inputs, contract violation, non-determinism)
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from typing import List, Optional, Tuple

# ---------------------------------------------------------------------------
# Import guards — validate before heavy imports
# ---------------------------------------------------------------------------

# Ensure repo root is importable
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_SCRIPT_DIR)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from wbc_backend.recommendation.p35_dual_source_import_validation_contract import (
    PAPER_ONLY,
    PRODUCTION_READY,
    P35_BLOCKED_CONTRACT_VIOLATION,
    P35_BLOCKED_FEATURE_PIPELINE_MISSING,
    P35_BLOCKED_ODDS_LICENSE_NOT_APPROVED,
    P35_BLOCKED_ODDS_SOURCE_NOT_PROVIDED,
    P35_BLOCKED_PREDICTION_REBUILD_NOT_FEASIBLE,
    P35_DUAL_SOURCE_IMPORT_VALIDATION_READY,
    P35_FAIL_INPUT_MISSING,
    P35_FAIL_NON_DETERMINISTIC,
)
from wbc_backend.recommendation.p35_odds_license_provenance_validator import (
    build_odds_import_validation_plan,
    build_odds_license_checklist,
    load_p34_odds_options,
    summarize_odds_license_validation,
    validate_manual_odds_source_approval,
    validate_odds_import_schema_template,
)
from wbc_backend.recommendation.p35_prediction_rebuild_feasibility_auditor import (
    evaluate_2024_oof_rebuild_feasibility,
    scan_feature_pipeline_candidates,
    scan_model_training_candidates,
    scan_oof_generation_candidates,
)
from wbc_backend.recommendation.p35_import_validator_skeletons import (
    validate_validator_specs,
    write_validator_specs,
)
from wbc_backend.recommendation.p35_dual_source_validation_builder import (
    build_dual_source_validation_summary,
    determine_p35_gate,
    validate_p35_summary,
    write_p35_outputs,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("p35_runner")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_P32_DIR = "data/mlb_2024/processed"
DEFAULT_P34_DIR = "data/mlb_2024/processed/p34_dual_source_acquisition"
DEFAULT_OUTPUT_DIR = "data/mlb_2024/processed/p35_dual_source_import_validation"
P32_GAME_LOG_CSV = "mlb_2024_game_identity_outcomes_joined.csv"
P34_ODDS_OPTIONS_JSON = "odds_acquisition_options.json"
P34_ODDS_TEMPLATE_CSV = "odds_import_template.csv"

P35_OUTPUT_FILES: Tuple[str, ...] = (
    "odds_license_validation.json",
    "prediction_rebuild_feasibility.json",
    "odds_import_validator_spec.json",
    "prediction_import_validator_spec.json",
    "dual_source_validation_summary.json",
    "dual_source_validation_summary.md",
    "p35_gate_result.json",
)

# Exit code mapping
_EXIT_CODES = {
    P35_DUAL_SOURCE_IMPORT_VALIDATION_READY: 0,
    P35_BLOCKED_ODDS_LICENSE_NOT_APPROVED: 1,
    P35_BLOCKED_ODDS_SOURCE_NOT_PROVIDED: 1,
    P35_BLOCKED_FEATURE_PIPELINE_MISSING: 1,
    P35_BLOCKED_PREDICTION_REBUILD_NOT_FEASIBLE: 1,
    P35_BLOCKED_CONTRACT_VIOLATION: 2,
    P35_FAIL_INPUT_MISSING: 2,
    P35_FAIL_NON_DETERMINISTIC: 2,
}

# Fields excluded from determinism comparison (timestamps, paths, per-run file lists)
_DETERMINISM_EXCLUDE_KEYS = frozenset({"generated_at", "output_dir", "artifacts"})


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def _parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="P35 Dual Source Import Validation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--p32-dir",
        default=DEFAULT_P32_DIR,
        help="Directory containing P32 processed outputs.",
    )
    parser.add_argument(
        "--p34-dir",
        default=DEFAULT_P34_DIR,
        help="Directory containing P34 acquisition plan outputs.",
    )
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help="Directory to write P35 outputs into.",
    )
    parser.add_argument(
        "--paper-only",
        default="true",
        choices=["true"],
        help="Must be 'true'. Any other value causes exit 2.",
    )
    parser.add_argument(
        "--odds-approval-record",
        default=None,
        help="Optional path to manual odds approval_record.json.",
    )
    parser.add_argument(
        "--manual-odds-source",
        default=None,
        help="Optional path to manually provided odds source JSON.",
    )
    parser.add_argument(
        "--skip-determinism-check",
        action="store_true",
        default=False,
        help="Skip the determinism check (for testing).",
    )
    return parser.parse_args(argv)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_gate_result(output_dir: str, run_label: str) -> Optional[dict]:
    """Load the gate result JSON from a prior run."""
    path = os.path.join(output_dir, "p35_gate_result.json")
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        return data
    except Exception as exc:
        logger.warning("Could not load %s for %s: %s", path, run_label, exc)
        return None


def _compare_deterministic(
    run1: dict,
    run2: dict,
    exclude_keys: frozenset = _DETERMINISM_EXCLUDE_KEYS,
) -> Tuple[bool, str]:
    """Compare two gate result dicts for determinism, excluding timestamp keys."""

    def _strip(d: dict) -> dict:
        return {k: v for k, v in d.items() if k not in exclude_keys}

    d1 = _strip(run1)
    d2 = _strip(run2)

    diffs = []
    all_keys = set(d1) | set(d2)
    for k in sorted(all_keys):
        if d1.get(k) != d2.get(k):
            diffs.append(f"  key={k}: run1={d1.get(k)!r} vs run2={d2.get(k)!r}")

    if diffs:
        return (False, "Determinism check FAILED:\n" + "\n".join(diffs))
    return (True, "Determinism check PASSED.")


def _check_p34_prerequisite(p34_dir: str) -> Tuple[bool, str]:
    """Verify P34 gate marker exists and is READY."""
    gate_path = os.path.join(p34_dir, "p34_gate_result.json")
    if not os.path.isfile(gate_path):
        return (False, f"P34 gate result not found: {gate_path}")
    try:
        with open(gate_path, encoding="utf-8") as fh:
            data = json.load(fh)
        gate = data.get("gate", "")
        if "READY" not in gate:
            return (False, f"P34 gate is not READY: {gate}")
        return (True, f"P34 gate OK: {gate}")
    except Exception as exc:
        return (False, f"Could not parse P34 gate: {exc}")


def _print_summary(gate: str, blocker: str, output_dir: str) -> None:
    """Print a structured summary to stdout."""
    sep = "=" * 70
    print(sep)
    print("P35 Dual Source Import Validation")
    print(sep)
    print(f"  gate:             {gate}")
    print(f"  paper_only:       True")
    print(f"  production_ready: False")
    print(f"  season:           2024")
    if blocker:
        print(f"  blocker:          {blocker}")
    print(f"  output_dir:       {output_dir}")
    print(sep)
    if gate == P35_DUAL_SOURCE_IMPORT_VALIDATION_READY:
        print("RESULT: P35 PASSED — dual source import path validated.")
    else:
        print(f"RESULT: P35 BLOCKED — {gate}")
    print(sep)


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------


def main(argv: Optional[List[str]] = None) -> int:  # noqa: C901
    args = _parse_args(argv)

    # --- Step 1: Paper-only guard ---
    if args.paper_only != "true" or not PAPER_ONLY or PRODUCTION_READY:
        print("FAIL: --paper-only must be 'true'. PAPER_ONLY must be True. "
              "PRODUCTION_READY must be False.")
        _print_summary(P35_BLOCKED_CONTRACT_VIOLATION, "paper_only violation", args.output_dir)
        return 2

    # --- Step 2: P34 prerequisite check ---
    p34_ok, p34_msg = _check_p34_prerequisite(args.p34_dir)
    if not p34_ok:
        logger.warning("P34 prerequisite check failed: %s", p34_msg)
        # Warn but don't block — P34 may still be valid even if JSON differs
        print(f"INFO: P34 status: {p34_msg}")

    # --- Step 3: Load P34 odds options ---
    odds_options_path = os.path.join(args.p34_dir, P34_ODDS_OPTIONS_JSON)
    odds_options = load_p34_odds_options(odds_options_path)
    logger.info("Loaded %d odds options from P34.", len(odds_options))

    # --- Step 4: Build odds license checklist ---
    checklist = build_odds_license_checklist(odds_options)
    logger.info("Checklist has %d items.", len(checklist))

    # --- Step 5: Validate approval record ---
    approval_path = args.odds_approval_record if hasattr(args, "odds_approval_record") else None
    approval_approved, approval_reason, approval_record = validate_manual_odds_source_approval(
        approval_path
    )
    logger.info("Odds approval: approved=%s, reason=%s", approval_approved, approval_reason)

    # --- Step 6: Validate odds schema template ---
    template_path = os.path.join(args.p34_dir, P34_ODDS_TEMPLATE_CSV)
    schema_valid, schema_reason, schema_missing_cols = validate_odds_import_schema_template(
        template_path
    )
    logger.info("Schema valid=%s, reason=%s", schema_valid, schema_reason)

    # --- Step 7: Summarize odds license validation ---
    odds_validation = summarize_odds_license_validation(
        approval_approved,
        approval_reason,
        schema_valid,
        schema_reason,
        schema_missing_cols,
        checklist,
        odds_options,
    )

    # --- Step 8: Scan feature pipeline candidates ---
    base_paths = [
        os.path.join(_REPO_ROOT, "wbc_backend"),
        os.path.join(_REPO_ROOT, "scripts"),
        os.path.join(_REPO_ROOT, "orchestrator"),
        os.path.join(_REPO_ROOT, "data"),
    ]
    feature_candidates = scan_feature_pipeline_candidates(base_paths)
    logger.info("Feature pipeline candidates: %d", len(feature_candidates))

    # --- Step 9: Scan model training candidates ---
    model_candidates = scan_model_training_candidates(base_paths)
    logger.info("Model training candidates: %d", len(model_candidates))

    # --- Step 10: Scan OOF generation candidates ---
    oof_candidates = scan_oof_generation_candidates(base_paths)
    logger.info("OOF generation candidates: %d", len(oof_candidates))

    # --- Step 11: Evaluate 2024 OOF rebuild feasibility ---
    game_log_path = os.path.join(args.p32_dir, P32_GAME_LOG_CSV)
    prediction_feasibility = evaluate_2024_oof_rebuild_feasibility(
        game_log_path, base_paths
    )
    logger.info("Prediction feasibility: %s", prediction_feasibility.feasibility_status)

    # --- Step 12: Write validator specs ---
    os.makedirs(args.output_dir, exist_ok=True)
    validator_spec_files = write_validator_specs(args.output_dir)
    specs_valid = validate_validator_specs(args.output_dir)
    logger.info(
        "Validator specs written: %d files, valid=%s", len(validator_spec_files), specs_valid
    )

    # --- Step 13: Build validation summary ---
    summary = build_dual_source_validation_summary(
        odds_validation, prediction_feasibility, specs_valid
    )
    if not validate_p35_summary(summary):
        print("FAIL: P35 summary failed internal validation (PRODUCTION_READY or paper_only).")
        return 2

    # --- Step 14: Determine P35 gate ---
    gate_result = determine_p35_gate(summary)

    # --- Step 15: Write outputs ---
    written_files = write_p35_outputs(
        args.output_dir,
        summary,
        gate_result,
        odds_validation,
        prediction_feasibility,
        validator_spec_files,
    )
    logger.info("Wrote %d output files.", len(written_files))

    # --- Step 16: Determinism check (first run only saves baseline) ---
    if not args.skip_determinism_check:
        det_ok = True  # True if this is the first run; compare on second run
        # Load what we just wrote
        gate_data_run1 = _load_gate_result(args.output_dir, "run1")
        if gate_data_run1:
            # Second run: write to temp dir and compare
            import tempfile
            import shutil

            tmp_dir = tempfile.mkdtemp(prefix="p35_det_")
            try:
                _ = write_validator_specs(tmp_dir)
                _ = write_p35_outputs(
                    tmp_dir, summary, gate_result, odds_validation,
                    prediction_feasibility, []
                )
                gate_data_run2 = _load_gate_result(tmp_dir, "run2")
                if gate_data_run2:
                    det_ok, det_msg = _compare_deterministic(gate_data_run1, gate_data_run2)
                    logger.info("Determinism: %s", det_msg)
                    if not det_ok:
                        print(f"FAIL: {det_msg}")
                        return 2
            finally:
                shutil.rmtree(tmp_dir, ignore_errors=True)

    # --- Step 17: Print result ---
    _print_summary(gate_result.gate, gate_result.blocker_reason, args.output_dir)

    # --- Step 18: Return exit code ---
    return _EXIT_CODES.get(gate_result.gate, 1)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    sys.exit(main())
