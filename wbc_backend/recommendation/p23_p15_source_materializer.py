"""
wbc_backend/recommendation/p23_p15_source_materializer.py

P23 P15 Source Materializer — reads the P22.5 readiness plan and materializes
P15 inputs for each replayable date from the full source file.

Design principles:
- Uses the FULL joined_oof_with_odds.csv (not the 20-row preview)
- Updates run_date column to the target date
- Does NOT fabricate rows; only real source rows are used
- Copies simulation_ledger.csv without modification (only for P16.6 validation)
- Writes to outputs/predictions/PAPER/<date>/p23_historical_replay/p15_materialized/

PAPER_ONLY — no production systems, no real bets.
"""
from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd

from wbc_backend.recommendation.p23_historical_replay_contract import (
    P23_DATE_BLOCKED_P15_BUILD_FAILED,
    P23_DATE_BLOCKED_SOURCE_NOT_READY,
    P23_SOURCE_TYPE_BLOCKED,
    P23_SOURCE_TYPE_MATERIALIZED,
    P23ReplayDateTask,
)

# Required columns that must be present in the materialized P15 inputs
REQUIRED_MATERIALIZED_COLUMNS = [
    "y_true",
    "p_oof",
    "game_id",
    "game_date",
    "odds_decimal_home",
    "odds_decimal_away",
    "p_market",
    "edge",
    "run_date",
]

MATERIALIZATION_STATUS = "P23_MATERIALIZED"


# ---------------------------------------------------------------------------
# P22.5 plan loading
# ---------------------------------------------------------------------------


def load_p22_5_readiness_plan(plan_path: str | Path) -> dict:
    """Load the P22.5 readiness plan JSON.

    Args:
        plan_path: Path to p15_readiness_plan.json

    Returns:
        dict with the plan contents

    Raises:
        FileNotFoundError: if plan file does not exist
    """
    p = Path(plan_path)
    if not p.exists():
        raise FileNotFoundError(f"P22.5 readiness plan not found: {plan_path}")
    with open(p, "r", encoding="utf-8") as fh:
        return json.load(fh)


def list_replayable_dates(plan: dict) -> list[str]:
    """Return dates that are P15-ready from the P22.5 plan.

    Args:
        plan: P22.5 readiness plan dict

    Returns:
        Sorted list of ISO date strings (YYYY-MM-DD)
    """
    dates = plan.get("dates_ready_to_build_p15_inputs", [])
    return sorted(dates)


# ---------------------------------------------------------------------------
# Source candidate resolution
# ---------------------------------------------------------------------------


def _find_usable_source_path(p22_5_output_dir: Path) -> Optional[Path]:
    """Find the USABLE full source file from the P22.5 candidate inventory.

    Looks for SOURCE_CANDIDATE_USABLE + HISTORICAL_P15_JOINED_INPUT entries
    in the inventory. Returns the file path if found.
    """
    inventory_path = p22_5_output_dir / "source_candidate_inventory.json"
    if not inventory_path.exists():
        return None

    with open(inventory_path, "r", encoding="utf-8") as fh:
        inventory = json.load(fh)

    # Inventory may be a flat list (P22.5 v1 format) or a dict with "candidates" key
    if isinstance(inventory, list):
        candidates = inventory
    else:
        candidates = inventory.get("candidates", [])

    for c in candidates:
        if (
            c.get("candidate_status") == "SOURCE_CANDIDATE_USABLE"
            and c.get("source_type") == "HISTORICAL_P15_JOINED_INPUT"
        ):
            # Path may be stored under "file_path" or "source_path"
            raw_path = c.get("file_path") or c.get("source_path", "")
            src_path = Path(raw_path)
            if src_path.exists():
                return src_path

    return None


def _find_preview_path(p22_5_output_dir: Path, run_date: str) -> Optional[Path]:
    """Find the P22.5 dry-run preview CSV for a specific date."""
    preview = p22_5_output_dir / "previews" / run_date / "p15_input_preview.csv"
    return preview if preview.exists() else None


# ---------------------------------------------------------------------------
# Materializer
# ---------------------------------------------------------------------------


def materialize_p15_inputs_for_date(
    run_date: str,
    p22_5_output_dir: str | Path,
    output_base_dir: str | Path,
) -> dict:
    """Materialize P15 inputs for a single date from the full source file.

    Reads the full joined_oof_with_odds.csv (not the 20-row preview), updates
    the run_date column, and writes it to the per-date output directory.
    Also copies simulation_ledger.csv from the same P15 source directory.

    Args:
        run_date:           Target date string (YYYY-MM-DD)
        p22_5_output_dir:  Path to P22.5 source artifact builder output dir
        output_base_dir:   Base PAPER output dir (e.g. outputs/predictions/PAPER)

    Returns:
        dict with keys: status, p15_materialized_path, sim_ledger_path,
                        n_rows, blocker_reason, paper_only, production_ready
    """
    p22_5_dir = Path(p22_5_output_dir)
    base_dir = Path(output_base_dir)

    out_dir = base_dir / run_date / "p23_historical_replay" / "p15_materialized"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Find USABLE full source file
    src_path = _find_usable_source_path(p22_5_dir)
    if src_path is None:
        return {
            "status": P23_DATE_BLOCKED_SOURCE_NOT_READY,
            "p15_materialized_path": "",
            "sim_ledger_path": "",
            "n_rows": 0,
            "blocker_reason": "No USABLE HISTORICAL_P15_JOINED_INPUT candidate found in inventory",
            "paper_only": True,
            "production_ready": False,
        }

    # Step 2: Read full source
    try:
        df = pd.read_csv(src_path)
    except Exception as exc:
        return {
            "status": P23_DATE_BLOCKED_P15_BUILD_FAILED,
            "p15_materialized_path": "",
            "sim_ledger_path": "",
            "n_rows": 0,
            "blocker_reason": f"Failed to read source file {src_path}: {exc}",
            "paper_only": True,
            "production_ready": False,
        }

    # Step 3: Validate required columns that must exist in the source file.
    # NOTE: "run_date" is excluded here — the materializer adds it in Step 5.
    # The output file validation (validate_materialized_p15_inputs) checks all columns.
    source_required = [c for c in REQUIRED_MATERIALIZED_COLUMNS if c != "run_date"]
    missing_cols = [c for c in source_required if c not in df.columns]
    if missing_cols:
        return {
            "status": P23_DATE_BLOCKED_P15_BUILD_FAILED,
            "p15_materialized_path": "",
            "sim_ledger_path": "",
            "n_rows": 0,
            "blocker_reason": f"Source file missing required columns: {missing_cols}",
            "paper_only": True,
            "production_ready": False,
        }

    # Step 4: Validate non-empty y_true
    if df["y_true"].isna().all():
        return {
            "status": P23_DATE_BLOCKED_P15_BUILD_FAILED,
            "p15_materialized_path": "",
            "sim_ledger_path": "",
            "n_rows": 0,
            "blocker_reason": "Source file: y_true is all-null",
            "paper_only": True,
            "production_ready": False,
        }

    # Step 5: Update run_date and add metadata columns
    df = df.copy()
    df["run_date"] = run_date
    df["materialization_status"] = MATERIALIZATION_STATUS
    df["paper_only"] = True
    df["production_ready"] = False

    # Step 6: Write materialized CSV
    out_csv = out_dir / "joined_oof_with_odds.csv"
    try:
        df.to_csv(out_csv, index=False)
    except Exception as exc:
        return {
            "status": P23_DATE_BLOCKED_P15_BUILD_FAILED,
            "p15_materialized_path": "",
            "sim_ledger_path": "",
            "n_rows": 0,
            "blocker_reason": f"Failed to write materialized CSV: {exc}",
            "paper_only": True,
            "production_ready": False,
        }

    # Step 7: Copy simulation_ledger.csv from same source P15 directory
    src_ledger = src_path.parent / "simulation_ledger.csv"
    out_ledger = out_dir / "simulation_ledger.csv"
    if src_ledger.exists():
        shutil.copy2(str(src_ledger), str(out_ledger))
        sim_ledger_path = str(out_ledger)
    else:
        sim_ledger_path = ""

    # Step 8: Write summary JSON
    summary = {
        "run_date": run_date,
        "materialization_status": MATERIALIZATION_STATUS,
        "source_file": str(src_path),
        "n_rows_materialized": len(df),
        "out_csv": str(out_csv),
        "sim_ledger_path": sim_ledger_path,
        "paper_only": True,
        "production_ready": False,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    summary_path = out_dir / "p15_materialized_summary.json"
    with open(summary_path, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)

    return {
        "status": MATERIALIZATION_STATUS,
        "p15_materialized_path": str(out_csv),
        "sim_ledger_path": sim_ledger_path,
        "n_rows": len(df),
        "blocker_reason": "",
        "paper_only": True,
        "production_ready": False,
    }


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_materialized_p15_inputs(df: pd.DataFrame) -> list[str]:
    """Check a materialized P15 DataFrame for contract compliance.

    Returns:
        List of violation messages. Empty = valid.
    """
    violations: list[str] = []

    missing = [c for c in REQUIRED_MATERIALIZED_COLUMNS if c not in df.columns]
    if missing:
        violations.append(f"Missing required columns: {missing}")

    if "y_true" in df.columns and df["y_true"].isna().all():
        violations.append("y_true is all-null")

    if "paper_only" in df.columns:
        non_paper = (~df["paper_only"].astype(bool)).sum()
        if non_paper > 0:
            violations.append(f"{non_paper} rows have paper_only != True")

    if "production_ready" in df.columns:
        prod_rows = df["production_ready"].astype(bool).sum()
        if prod_rows > 0:
            violations.append(f"{prod_rows} rows have production_ready != False")

    return violations


# ---------------------------------------------------------------------------
# Task planning
# ---------------------------------------------------------------------------


def build_replay_date_tasks(
    dates: list[str],
    p22_5_output_dir: str | Path,
    paper_base_dir: str | Path,
) -> list[P23ReplayDateTask]:
    """Build replay task specs for each date.

    Args:
        dates:              List of date strings to replay
        p22_5_output_dir:  P22.5 output directory
        paper_base_dir:    Base PAPER output directory

    Returns:
        List of P23ReplayDateTask (one per date)
    """
    p22_5_dir = Path(p22_5_output_dir)
    base_dir = Path(paper_base_dir)

    # Locate the USABLE source file once
    src_path = _find_usable_source_path(p22_5_dir)
    full_source_path = str(src_path) if src_path else ""

    tasks: list[P23ReplayDateTask] = []
    for run_date in sorted(dates):
        preview_path = _find_preview_path(p22_5_dir, run_date)
        source_ready = src_path is not None

        # Check if an existing P20-ready output already exists
        existing_p20 = base_dir / run_date / "p20_daily_paper_orchestrator" / "p20_gate_result.json"
        already_ready = False
        if existing_p20.exists():
            with open(existing_p20, "r", encoding="utf-8") as fh:
                p20_data = json.load(fh)
            if p20_data.get("p20_gate") == "P20_DAILY_PAPER_ORCHESTRATOR_READY":
                already_ready = True

        if already_ready:
            source_type = "ALREADY_READY"
        elif source_ready:
            source_type = P23_SOURCE_TYPE_MATERIALIZED
        else:
            source_type = P23_SOURCE_TYPE_BLOCKED

        tasks.append(
            P23ReplayDateTask(
                run_date=run_date,
                p22_5_source_ready=source_ready,
                p22_5_preview_path=str(preview_path) if preview_path else "",
                p22_5_full_source_path=full_source_path,
                source_type=source_type,
                paper_only=True,
                production_ready=False,
            )
        )

    return tasks
