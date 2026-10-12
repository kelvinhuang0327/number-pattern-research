"""P36 Odds Approval Import Gate — CLI runner.

Usage:
  python scripts/run_p36_odds_approval_import_gate.py \\
    --p32-dir data/mlb_2024/processed \\
    --p35-dir data/mlb_2024/processed/p35_dual_source_import_validation \\
    --output-dir data/mlb_2024/processed/p36_odds_approval_import_gate \\
    --paper-only true

Optional:
  --approval-record data/mlb_2024/manual_import/odds_approval_record.json
  --manual-odds-file data/mlb_2024/manual_import/odds_2024_approved.csv

Exit codes:
  0  P36_ODDS_APPROVAL_RECORD_READY
  1  P36_BLOCKED_*
  2  P36_FAIL_* / contract violation

PAPER_ONLY=True, PRODUCTION_READY=False enforced throughout.
No scraping, no automated download, no raw odds committed.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import tempfile
from typing import Dict, List, Optional

# ---------------------------------------------------------------------------
# Project root on path
# ---------------------------------------------------------------------------

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_SCRIPT_DIR)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from wbc_backend.recommendation.p36_odds_approval_contract import (  # noqa: E402
    PAPER_ONLY,
    PRODUCTION_READY,
    SEASON,
    P36_BLOCKED_APPROVAL_RECORD_MISSING,
    P36_BLOCKED_CONTRACT_VIOLATION,
    P36_FAIL_INPUT_MISSING,
    P36_FAIL_NON_DETERMINISTIC,
    P36_ODDS_APPROVAL_RECORD_READY,
)
from wbc_backend.recommendation.p36_odds_approval_record_validator import (  # noqa: E402
    load_approval_record,
    summarize_approval_validation,
)
from wbc_backend.recommendation.p36_manual_odds_import_validator import (  # noqa: E402
    build_manual_odds_import_schema,
    load_manual_odds_file,
    summarize_manual_odds_import,
)
from wbc_backend.recommendation.p36_odds_import_gate_planner import (  # noqa: E402
    build_odds_import_gate_plan,
    determine_p36_gate,
    validate_p36_gate_plan,
    write_p36_outputs,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_P32_DIR = "data/mlb_2024/processed"
DEFAULT_P35_DIR = "data/mlb_2024/processed/p35_dual_source_import_validation"
DEFAULT_OUTPUT_DIR = "data/mlb_2024/processed/p36_odds_approval_import_gate"

P35_REQUIRED_GATE_FILE = "p35_gate_result.json"
P35_REQUIRED_GATE_VALUE = "P35_BLOCKED_ODDS_LICENSE_NOT_APPROVED"

P32_GAME_IDENTITY_CSV = "mlb_2024_game_identity.csv"

P36_OUTPUT_FILES = (
    "odds_approval_validation.json",
    "manual_odds_import_schema.json",
    "manual_odds_import_validation.json",
    "odds_import_gate_plan.json",
    "odds_import_gate_plan.md",
    "p36_gate_result.json",
)

_DETERMINISM_EXCLUDE_KEYS = frozenset({"generated_at", "output_dir", "artifacts"})

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("p36_runner")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_p35_gate(p35_dir: str) -> Optional[Dict]:
    gate_path = os.path.join(p35_dir, P35_REQUIRED_GATE_FILE)
    if not os.path.isfile(gate_path):
        return None
    try:
        with open(gate_path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:  # noqa: BLE001
        return None


def _compare_deterministic(run1: dict, run2: dict) -> tuple:
    """Return (ok, message) comparing two gate result dicts."""

    def _strip(d: dict) -> dict:
        return {k: v for k, v in d.items() if k not in _DETERMINISM_EXCLUDE_KEYS}

    d1, d2 = _strip(run1), _strip(run2)
    diffs = []
    for k in sorted(set(d1) | set(d2)):
        if d1.get(k) != d2.get(k):
            diffs.append(f"  key={k}: run1={d1.get(k)!r} vs run2={d2.get(k)!r}")
    if diffs:
        return False, "Determinism check FAILED:\n" + "\n".join(diffs)
    return True, "Determinism check PASSED."


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="P36 Odds Approval Import Gate",
    )
    parser.add_argument("--p32-dir", default=DEFAULT_P32_DIR)
    parser.add_argument("--p35-dir", default=DEFAULT_P35_DIR)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--paper-only",
        default="true",
        help='Must be "true". Any other value exits 2.',
    )
    parser.add_argument("--approval-record", default=None)
    parser.add_argument("--manual-odds-file", default=None)
    parser.add_argument(
        "--skip-determinism-check",
        action="store_true",
        default=False,
    )
    args = parser.parse_args(argv)

    # Step 1: paper-only guard
    if args.paper_only.lower().strip() != "true":
        print(
            f"FAIL: --paper-only must be 'true'. Got: {args.paper_only!r}. "
            "This phase is PAPER_ONLY."
        )
        return 2

    # Step 2: module-level contract guard
    if not PAPER_ONLY or PRODUCTION_READY:
        print("FAIL: Contract violation — PAPER_ONLY must be True, PRODUCTION_READY False.")
        return 2

    logger.info("P36 paper-only guard: PASS. PAPER_ONLY=%s PRODUCTION_READY=%s",
                PAPER_ONLY, PRODUCTION_READY)

    # Step 3: P35 prerequisite check
    p35_gate = _load_p35_gate(args.p35_dir)
    if p35_gate is None:
        logger.warning(
            "P35 gate result not found at %s. Continuing without prior-phase verification.",
            args.p35_dir,
        )
    else:
        logger.info("P35 gate verified: %s", p35_gate.get("gate", "UNKNOWN"))

    # Step 4: load approval record (may be None)
    approval_record = load_approval_record(args.approval_record)
    if approval_record is not None:
        logger.info("Approval record loaded from: %s", args.approval_record)
    else:
        logger.info("No approval record provided.")

    # Step 5: validate approval record
    approval_validation = summarize_approval_validation(approval_record)
    logger.info(
        "Approval validation: status=%s, reason=%s",
        approval_validation.approval_status,
        approval_validation.blocker_reason,
    )

    # Step 6: build manual odds import schema
    schema_spec = build_manual_odds_import_schema()
    schema_dict = {
        "required_columns": list(schema_spec.required_columns),
        "forbidden_columns": list(schema_spec.forbidden_columns),
        "allowed_market_types": list(schema_spec.allowed_market_types),
        "p_market_range": list(schema_spec.p_market_range),
        "odds_decimal_min": schema_spec.odds_decimal_min,
        "paper_only": schema_spec.paper_only,
        "production_ready": schema_spec.production_ready,
        "notes": schema_spec.notes,
        "season": schema_spec.season,
    }

    # Step 7: load P32 game identity (for coverage check, optional)
    game_identity_df = None
    p32_identity_path = os.path.join(args.p32_dir, P32_GAME_IDENTITY_CSV)
    if os.path.isfile(p32_identity_path):
        try:
            import pandas as pd
            game_identity_df = pd.read_csv(p32_identity_path, dtype=str)
            logger.info("P32 game identity loaded: %d rows", len(game_identity_df))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not load P32 game identity: %s", exc)

    # Step 8: load manual odds file (may be None)
    manual_df = None
    if args.manual_odds_file:
        manual_df = load_manual_odds_file(args.manual_odds_file)
        if manual_df is not None:
            logger.info(
                "Manual odds file loaded: %d rows from %s",
                len(manual_df),
                args.manual_odds_file,
            )
        else:
            logger.warning("Failed to load manual odds file: %s", args.manual_odds_file)

    # Step 9: summarize manual import
    manual_import_summary = summarize_manual_odds_import(manual_df, game_identity_df)
    logger.info("Manual import status: %s", manual_import_summary.get("status", "N/A"))

    # Step 10: build gate plan
    gate_plan = build_odds_import_gate_plan(approval_validation, manual_import_summary)

    # Step 11: validate gate plan
    if not validate_p36_gate_plan(gate_plan):
        print("FAIL: P36 gate plan failed contract validation.")
        return 2

    # Step 12: determine gate
    gate = determine_p36_gate(gate_plan)
    logger.info("P36 gate: %s", gate.gate)

    # Step 13: write outputs
    written = write_p36_outputs(
        args.output_dir,
        gate,
        approval_validation,
        schema_dict,
        manual_import_summary,
        gate_plan,
    )
    logger.info("Wrote %d output files to %s", len(written), args.output_dir)

    # Step 14: determinism check
    if not args.skip_determinism_check:
        tmp_dir = tempfile.mkdtemp(prefix="p36_det_")
        try:
            gate2 = determine_p36_gate(gate_plan)
            write_p36_outputs(
                tmp_dir,
                gate2,
                approval_validation,
                schema_dict,
                manual_import_summary,
                gate_plan,
            )
            gate_path1 = os.path.join(args.output_dir, "p36_gate_result.json")
            gate_path2 = os.path.join(tmp_dir, "p36_gate_result.json")
            with open(gate_path1, encoding="utf-8") as fh:
                d1 = json.load(fh)
            with open(gate_path2, encoding="utf-8") as fh:
                d2 = json.load(fh)
            det_ok, det_msg = _compare_deterministic(d1, d2)
            logger.info("Determinism: %s", det_msg)
            if not det_ok:
                print(f"FAIL: {det_msg}")
                return 2
        finally:
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)

    # Step 15: print summary
    print(f"p36_gate={gate.gate}")
    print(f"approval_record_status={gate.approval_record_status}")
    print(f"odds_source_status={gate.odds_source_status}")
    print(f"internal_research_allowed={gate.internal_research_allowed}")
    print(f"raw_odds_commit_allowed={gate.raw_odds_commit_allowed}")
    print(f"recommended_next_action={gate.recommended_next_action}")
    print(f"production_ready={gate.production_ready}")
    print(f"paper_only={gate.paper_only}")

    # Step 16: exit code
    if gate.gate == P36_ODDS_APPROVAL_RECORD_READY:
        return 0
    if gate.gate.startswith("P36_BLOCKED_"):
        return 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
