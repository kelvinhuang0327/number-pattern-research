#!/usr/bin/env python3
"""
P37 Manual Odds Provisioning Gate — CLI

Usage:
  ./.venv/bin/python scripts/run_p37_manual_odds_provisioning_gate.py \\
    --output-dir data/mlb_2024/processed/p37_manual_odds_provisioning \\
    --paper-only true

Optional:
  --approval-record data/mlb_2024/manual_import/odds_approval_record.json
  --manual-odds-file data/mlb_2024/manual_import/odds_2024_approved.csv
  --skip-determinism-check

Exit codes:
  0  P37_MANUAL_ODDS_PROVISIONING_GATE_READY
  1  P37_BLOCKED_*
  2  P37_FAIL_*

PAPER_ONLY=True  PRODUCTION_READY=False  SEASON=2024
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import List, Optional

# ---------------------------------------------------------------------------
# Module-level contract guard
# ---------------------------------------------------------------------------
from wbc_backend.recommendation.p37_manual_odds_provisioning_contract import (
    PAPER_ONLY,
    PRODUCTION_READY,
    SEASON,
    P37_OUTPUT_FILES,
)
from wbc_backend.recommendation.p37_approval_record_template_writer import (
    write_approval_record_template,
    write_approval_record_instructions,
)
from wbc_backend.recommendation.p37_manual_odds_template_writer import (
    write_manual_odds_template,
    write_manual_odds_column_guide,
)
from wbc_backend.recommendation.p37_manual_odds_provisioning_gate import (
    check_manual_approval_record,
    check_manual_odds_file,
    detect_raw_commit_risk,
    build_provisioning_gate_result,
    write_p37_outputs,
)

# Repo root is two levels above this script
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_SCRIPT_DIR)


def _parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="P37 Manual Odds Provisioning Gate CLI"
    )
    parser.add_argument(
        "--output-dir",
        default="data/mlb_2024/processed/p37_manual_odds_provisioning",
        help="Directory to write P37 outputs.",
    )
    parser.add_argument(
        "--paper-only",
        default="true",
        help="Must be 'true'. Any other value causes exit 2.",
    )
    parser.add_argument(
        "--approval-record",
        default=None,
        help="Path to a filled odds_approval_record.json.",
    )
    parser.add_argument(
        "--manual-odds-file",
        default=None,
        help="Path to a licensed odds CSV.",
    )
    parser.add_argument(
        "--skip-determinism-check",
        action="store_true",
        help="Skip the post-run determinism check.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = _parse_args(argv)

    # -----------------------------------------------------------------------
    # Step 1: paper-only guard
    # -----------------------------------------------------------------------
    if args.paper_only.lower() != "true":
        print("FAIL: --paper-only must be 'true'. This pipeline is PAPER_ONLY.")
        print("EXIT_CODE=2")
        return 2

    # -----------------------------------------------------------------------
    # Step 2: Module-level contract guard
    # -----------------------------------------------------------------------
    if PRODUCTION_READY:
        print("FAIL: PRODUCTION_READY=True at module level. Contract violation.")
        print("EXIT_CODE=2")
        return 2
    if not PAPER_ONLY:
        print("FAIL: PAPER_ONLY=False at module level. Contract violation.")
        print("EXIT_CODE=2")
        return 2

    output_dir = args.output_dir
    os.makedirs(output_dir, exist_ok=True)

    # -----------------------------------------------------------------------
    # Step 3: Write templates and instructions (always written regardless of gate)
    # -----------------------------------------------------------------------
    try:
        write_approval_record_template(output_dir)
        write_approval_record_instructions(output_dir)
        write_manual_odds_template(output_dir)
        write_manual_odds_column_guide(output_dir)
        templates_written = True
    except Exception as exc:
        print(f"FAIL: Could not write templates: {exc}")
        print("EXIT_CODE=2")
        return 2

    # -----------------------------------------------------------------------
    # Step 4: Detect raw commit risk
    # -----------------------------------------------------------------------
    raw_commit_risk = detect_raw_commit_risk(_REPO_ROOT)

    # -----------------------------------------------------------------------
    # Step 5: Check approval record
    # -----------------------------------------------------------------------
    approval_check = check_manual_approval_record(args.approval_record)

    # -----------------------------------------------------------------------
    # Step 6: Check manual odds file
    # -----------------------------------------------------------------------
    odds_check = check_manual_odds_file(args.manual_odds_file)

    # -----------------------------------------------------------------------
    # Step 7: Build gate result
    # -----------------------------------------------------------------------
    gate_result = build_provisioning_gate_result(
        approval_check=approval_check,
        odds_check=odds_check,
        raw_commit_risk=raw_commit_risk,
        templates_written=templates_written,
        repo_root=_REPO_ROOT,
    )

    # -----------------------------------------------------------------------
    # Step 8: Write gate outputs (manual_odds_provisioning_gate.json + .md + p37_gate_result.json)
    # -----------------------------------------------------------------------
    write_p37_outputs(output_dir, gate_result, approval_check, odds_check)

    # -----------------------------------------------------------------------
    # Step 9: Determinism check
    # -----------------------------------------------------------------------
    determinism_ok = True
    if not args.skip_determinism_check:
        import tempfile
        import shutil
        try:
            with tempfile.TemporaryDirectory() as tmp2:
                write_approval_record_template(tmp2)
                write_approval_record_instructions(tmp2)
                write_manual_odds_template(tmp2)
                write_manual_odds_column_guide(tmp2)
                gate_result2 = build_provisioning_gate_result(
                    approval_check=check_manual_approval_record(args.approval_record),
                    odds_check=check_manual_odds_file(args.manual_odds_file),
                    raw_commit_risk=detect_raw_commit_risk(_REPO_ROOT),
                    templates_written=True,
                    repo_root=_REPO_ROOT,
                )
                _EXCLUDE_KEYS = frozenset({"generated_at", "output_dir", "artifacts"})
                for fname in ("manual_odds_provisioning_gate.json", "p37_gate_result.json"):
                    p1 = os.path.join(output_dir, fname)
                    p2 = os.path.join(tmp2, fname)
                    if not os.path.exists(p1):
                        continue
                    write_p37_outputs(tmp2, gate_result2, approval_check, odds_check)
                    with open(p1) as f1, open(p2) as f2:
                        d1 = {k: v for k, v in json.load(f1).items() if k not in _EXCLUDE_KEYS}
                        d2 = {k: v for k, v in json.load(f2).items() if k not in _EXCLUDE_KEYS}
                    if d1 != d2:
                        determinism_ok = False
                        print(f"FAIL: Non-deterministic output in {fname}")
                        break
        except Exception as exc:
            print(f"WARN: Determinism check error: {exc}")

    # -----------------------------------------------------------------------
    # Step 10: Print summary
    # -----------------------------------------------------------------------
    print(f"p37_gate={gate_result.gate}")
    print(f"approval_record_status={gate_result.approval_record_status}")
    print(f"manual_odds_file_status={gate_result.manual_odds_file_status}")
    print(f"raw_commit_risk={gate_result.raw_commit_risk}")
    print(f"templates_written={gate_result.templates_written}")
    print(f"recommended_next_action={gate_result.recommended_next_action}")
    print(f"production_ready={gate_result.production_ready}")
    print(f"paper_only={gate_result.paper_only}")
    if determinism_ok:
        print("DETERMINISM_CHECK=PASSED")
    else:
        print("DETERMINISM_CHECK=FAILED")

    # -----------------------------------------------------------------------
    # Step 11: Exit code
    # -----------------------------------------------------------------------
    if not determinism_ok:
        print("EXIT_CODE=2")
        return 2

    gate = gate_result.gate
    if gate == "P37_MANUAL_ODDS_PROVISIONING_GATE_READY":
        print("EXIT_CODE=0")
        return 0
    if gate.startswith("P37_BLOCKED_"):
        print("EXIT_CODE=1")
        return 1
    print("EXIT_CODE=2")
    return 2


if __name__ == "__main__":
    sys.exit(main())
