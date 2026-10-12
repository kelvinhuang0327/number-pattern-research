"""
scripts/_p71_the_odds_api_live_pull_execution.py
================================================
P71 — The Odds API Live Pull Execution or Awaiting-Key Closure

GOVERNANCE (immutable):
  - PAPER_ONLY = True
  - DIAGNOSTIC_ONLY = True
  - PROMOTION_FREEZE = True
  - KELLY_DEPLOY_ALLOWED = False
  - REAL_BET_ALLOWED = False
  - PRODUCTION_READY = False
  - RUNTIME_RECOMMENDATION_LOGIC_CHANGED = False
  - TSL_CRAWLER_CALLED = False
  - ANTI_BOT_BYPASS_ATTEMPTED = False

P71 SCOPE:
  - If THE_ODDS_API_KEY absent → P71_PATH_A_STILL_AWAITING_API_KEY
  - If THE_ODDS_API_KEY present → invoke P70 pull script, validate CSV
    → P71_PATH_A_PULL_COMPLETE | P71_PATH_A_PULL_DATA_QUALITY_FAIL | P71_PATH_A_PULL_API_ERROR

P45 PLATT CONSTANTS (locked): A=0.435432, B=0.245464
P52 THRESHOLDS (locked):
  - ECE warning > 0.10, critical > 0.12
  - Brier warning > 0.25, critical > 0.27
  - Edge warning < 0.07, critical ≤ 0
"""

from __future__ import annotations

import csv
import importlib.util
import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Governance constants (NEVER modify)
# ---------------------------------------------------------------------------
PAPER_ONLY: bool = True
DIAGNOSTIC_ONLY: bool = True
PROMOTION_FREEZE: bool = True
KELLY_DEPLOY_ALLOWED: bool = False
REAL_BET_ALLOWED: bool = False
PRODUCTION_READY: bool = False
RUNTIME_RECOMMENDATION_LOGIC_CHANGED: bool = False
TSL_CRAWLER_CALLED: bool = False
BULK_SCRAPING_PERFORMED: bool = False
ANTI_BOT_BYPASS_ATTEMPTED: bool = False

# Platt calibration constants — locked at P45
PLATT_A: float = 0.435432
PLATT_B: float = 0.245464

# P52 thresholds (locked — do NOT modify)
P52_ECE_WARN: float = 0.10
P52_ECE_CRIT: float = 0.12
P52_BRIER_WARN: float = 0.25
P52_BRIER_CRIT: float = 0.27
P52_EDGE_WARN: float = 0.07   # mean_edge < 0.07 → warning
P52_EDGE_CRIT: float = 0.0    # edge_ci_low ≤ 0 → critical

# P71 version
P71_VERSION: str = "p71_v1"
EXECUTION_DATE: str = "2026-05-26"

# CEO authorization (inherited from P70)
CEO_AUTHORIZATION_PHRASE: str = (
    "YES authorize P61 PATH_A The Odds API historical 2024 MLB moneyline pull "
    "for paper-only validation"
)
CEO_AUTHORIZATION_CONFIRMED: bool = True

# ---------------------------------------------------------------------------
# Valid P71 classifications
# ---------------------------------------------------------------------------
VALID_P71_CLASSIFICATIONS: frozenset[str] = frozenset({
    "P71_PATH_A_PULL_COMPLETE",
    "P71_PATH_A_STILL_AWAITING_API_KEY",
    "P71_PATH_A_PULL_DATA_QUALITY_FAIL",
    "P71_PATH_A_PULL_API_ERROR",
    "P71_PATH_A_BLOCKED_BY_GOVERNANCE_RISK",
    "P71_PATH_A_BLOCKED_BY_MISSING_AUTHORIZATION",
})

# Required CSV schema fields (from P61 spec)
REQUIRED_CSV_FIELDS: list[str] = [
    "game_date",
    "home_team",
    "away_team",
    "home_ml",
    "away_ml",
    "bookmaker",
    "odds_timestamp",
    "closing_indicator",
    "source_trace",
]

# ---------------------------------------------------------------------------
# Repository paths
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).parent.parent
P70_SCRIPT = REPO_ROOT / "scripts" / "_p70_path_a_the_odds_api_historical_pull.py"
P70_SUMMARY_PATH = (
    REPO_ROOT
    / "data" / "mlb_2025" / "derived"
    / "p70_path_a_the_odds_api_historical_pull_summary.json"
)
P71_SUMMARY_PATH = (
    REPO_ROOT
    / "data" / "mlb_2025" / "derived"
    / "p71_the_odds_api_live_pull_execution_summary.json"
)
OUTPUT_CSV_PATH = REPO_ROOT / "data" / "mlb_2025" / "mlb_odds_2024_real.csv"
ENV_PATH = REPO_ROOT / ".env"

# Minimum row count for data quality acceptance
MIN_ROWS_ACCEPTABLE: int = 500

# ---------------------------------------------------------------------------
# API Key detection
# ---------------------------------------------------------------------------

def detect_api_key_status() -> str:
    """
    Check whether THE_ODDS_API_KEY is configured.
    Returns 'API_KEY_PRESENT' or 'API_KEY_MISSING'.
    NEVER returns or logs the key value.
    """
    # Environment variable first
    val = os.environ.get("THE_ODDS_API_KEY", "").strip()
    if val:
        return "API_KEY_PRESENT"

    # .env file
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("THE_ODDS_API_KEY=") and not line.startswith("#"):
                v = line.split("=", 1)[1].strip().strip('"').strip("'")
                if v:
                    return "API_KEY_PRESENT"
    return "API_KEY_MISSING"


# ---------------------------------------------------------------------------
# P70 context loader
# ---------------------------------------------------------------------------

def load_p70_context() -> dict[str, Any]:
    """Load P70 summary as context for P71."""
    if not P70_SUMMARY_PATH.exists():
        return {"error": "P70 summary not found", "p70_classification": "MISSING"}
    with open(P70_SUMMARY_PATH, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Awaiting-key closure path (Step 3A)
# ---------------------------------------------------------------------------

def run_awaiting_key_closure() -> dict[str, Any]:
    """
    Step 3A: API key not configured.
    Validate P70 dry-run is stable, document required steps.
    """
    print("[P71] Key status: API_KEY_MISSING")
    print("[P71] Executing awaiting-key closure path")

    # Confirm P70 dry-run is still stable
    p70_context = load_p70_context()
    p70_cls = p70_context.get("p70_classification", "UNKNOWN")
    print(f"[P71] P70 context loaded — classification: {p70_cls}")

    return {
        "p71_version": P71_VERSION,
        "p71_classification": "P71_PATH_A_STILL_AWAITING_API_KEY",
        "execution_date": EXECUTION_DATE,
        "mode": "AWAITING_KEY",
        "api_key_status": "API_KEY_MISSING",
        "ceo_authorization_confirmed": CEO_AUTHORIZATION_CONFIRMED,
        "ceo_authorization_phrase": CEO_AUTHORIZATION_PHRASE,
        "paid_api_called": False,
        "live_api_calls": 0,
        "p70_context": {
            "p70_classification": p70_cls,
            "pull_date": p70_context.get("pull_date"),
            "pull_config": p70_context.get("pull_config"),
        },
        "required_schema_fields": REQUIRED_CSV_FIELDS,
        "output_csv_path": str(OUTPUT_CSV_PATH),
        "min_rows_required": MIN_ROWS_ACCEPTABLE,
        "setup_required_for_live_pull": {
            "step_1": "Register at https://the-odds-api.com",
            "step_2": "Subscribe to a plan with historical data access (~$30-50)",
            "step_3": "Locate API key in account dashboard",
            "step_4": "Add to .env: THE_ODDS_API_KEY=<your_key>",
            "step_5": "Re-run P70 script: .venv/bin/python scripts/_p70_path_a_the_odds_api_historical_pull.py",
            "step_6": "Script auto-detects key → LIVE mode → writes mlb_odds_2024_real.csv",
            "step_7": "Re-run P71 script to validate CSV and advance classification",
        },
        "governance": _build_governance(paid_api_called=False),
    }


# ---------------------------------------------------------------------------
# CSV validator
# ---------------------------------------------------------------------------

def validate_csv(csv_path: Path) -> dict[str, Any]:
    """
    Validate the output CSV against required schema.
    Returns a dict with validation status and details.
    """
    if not csv_path.exists():
        return {"valid": False, "error": "CSV file does not exist", "row_count": 0}

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []
        rows = list(reader)

    missing_fields = [f for f in REQUIRED_CSV_FIELDS if f not in headers]
    row_count = len(rows)

    # Check moneyline fields are numeric
    ml_errors = 0
    null_errors = 0
    date_errors = 0
    trace_errors = 0

    for row in rows:
        # Critical join fields must not be empty
        for field in ["game_date", "home_team", "away_team", "bookmaker"]:
            if not row.get(field, "").strip():
                null_errors += 1
        # Moneyline must be numeric
        for ml_field in ["home_ml", "away_ml"]:
            val = row.get(ml_field, "")
            try:
                float(val)
            except (ValueError, TypeError):
                ml_errors += 1
        # Date must be within 2024 season
        gd = row.get("game_date", "")
        if gd and not ("2024-03-20" <= gd[:10] <= "2024-09-29"):
            date_errors += 1
        # Source trace not empty
        if not row.get("source_trace", "").strip():
            trace_errors += 1

    quality_ok = (
        not missing_fields
        and row_count >= MIN_ROWS_ACCEPTABLE
        and ml_errors == 0
        and null_errors == 0
        and trace_errors == 0
    )

    return {
        "valid": quality_ok,
        "row_count": row_count,
        "row_count_sufficient": row_count >= MIN_ROWS_ACCEPTABLE,
        "missing_fields": missing_fields,
        "ml_errors": ml_errors,
        "null_errors": null_errors,
        "date_errors": date_errors,
        "trace_errors": trace_errors,
        "headers_present": list(headers),
    }


# ---------------------------------------------------------------------------
# Live pull path (Step 3B)
# ---------------------------------------------------------------------------

def run_live_pull_path() -> dict[str, Any]:
    """
    Step 3B: API key is configured.
    Invoke P70 pull script, then validate the resulting CSV.
    """
    print("[P71] Key status: API_KEY_PRESENT")
    print("[P71] Executing live pull path")
    print(f"[P71] GOVERNANCE: paper_only=True, real_bet_allowed=False, production_ready=False")

    # Invoke P70 pull script
    result = subprocess.run(
        [sys.executable, str(P70_SCRIPT)],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )

    if result.returncode != 0:
        return {
            "p71_version": P71_VERSION,
            "p71_classification": "P71_PATH_A_PULL_API_ERROR",
            "execution_date": EXECUTION_DATE,
            "mode": "LIVE",
            "api_key_status": "API_KEY_PRESENT",
            "paid_api_called": True,
            "live_api_calls": 1,
            "error": f"P70 script exited with code {result.returncode}",
            "stderr": result.stderr[:2000] if result.stderr else "",
            "governance": _build_governance(paid_api_called=True),
        }

    # Load P70 summary (updated by the pull script)
    p70_context = load_p70_context()
    p70_cls = p70_context.get("p70_classification", "UNKNOWN")
    rows_written = p70_context.get("rows_written", 0)

    # Validate CSV
    csv_validation = validate_csv(OUTPUT_CSV_PATH)

    if p70_cls == "P71_PATH_A_PULL_COMPLETE" and csv_validation["valid"]:
        classification = "P71_PATH_A_PULL_COMPLETE"
    elif rows_written > 0 and not csv_validation["valid"]:
        classification = "P71_PATH_A_PULL_DATA_QUALITY_FAIL"
    elif p70_cls == "P70_PATH_A_PULL_COMPLETE" and csv_validation["valid"]:
        classification = "P71_PATH_A_PULL_COMPLETE"
    elif p70_cls == "P70_PATH_A_PULL_DATA_QUALITY_FAIL":
        classification = "P71_PATH_A_PULL_DATA_QUALITY_FAIL"
    else:
        classification = "P71_PATH_A_PULL_API_ERROR"

    return {
        "p71_version": P71_VERSION,
        "p71_classification": classification,
        "execution_date": EXECUTION_DATE,
        "mode": "LIVE",
        "api_key_status": "API_KEY_PRESENT",
        "ceo_authorization_confirmed": CEO_AUTHORIZATION_CONFIRMED,
        "ceo_authorization_phrase": CEO_AUTHORIZATION_PHRASE,
        "paid_api_called": True,
        "live_api_calls": 1,
        "p70_result": {
            "p70_classification": p70_cls,
            "rows_written": rows_written,
        },
        "csv_validation": csv_validation,
        "output_csv_path": str(OUTPUT_CSV_PATH),
        "required_schema_fields": REQUIRED_CSV_FIELDS,
        "governance": _build_governance(paid_api_called=True),
    }


# ---------------------------------------------------------------------------
# Governance block builder
# ---------------------------------------------------------------------------

def _build_governance(paid_api_called: bool) -> dict[str, Any]:
    return {
        "paper_only": PAPER_ONLY,
        "diagnostic_only": DIAGNOSTIC_ONLY,
        "promotion_freeze": PROMOTION_FREEZE,
        "kelly_deploy_allowed": KELLY_DEPLOY_ALLOWED,
        "real_bet_allowed": REAL_BET_ALLOWED,
        "production_ready": PRODUCTION_READY,
        "runtime_recommendation_logic_changed": RUNTIME_RECOMMENDATION_LOGIC_CHANGED,
        "tsl_crawler_called": TSL_CRAWLER_CALLED,
        "bulk_scraping_performed": BULK_SCRAPING_PERFORMED,
        "anti_bot_bypass_attempted": ANTI_BOT_BYPASS_ATTEMPTED,
        "paid_api_called": paid_api_called,
        "platt_a": PLATT_A,
        "platt_b": PLATT_B,
        "p52_ece_warn": P52_ECE_WARN,
        "p52_ece_crit": P52_ECE_CRIT,
        "p52_brier_warn": P52_BRIER_WARN,
        "p52_brier_crit": P52_BRIER_CRIT,
        "p52_edge_warn": P52_EDGE_WARN,
    }


# ---------------------------------------------------------------------------
# Summary writer
# ---------------------------------------------------------------------------

def write_summary(summary: dict[str, Any], output_path: Optional[Path] = None) -> Path:
    if output_path is None:
        output_path = P71_SUMMARY_PATH
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    return output_path


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_p71(output_path: Optional[Path] = None) -> dict[str, Any]:
    """Full P71 pipeline entry point."""
    # Governance pre-checks
    assert PAPER_ONLY is True, "PAPER_ONLY must be True"
    assert DIAGNOSTIC_ONLY is True, "DIAGNOSTIC_ONLY must be True"
    assert KELLY_DEPLOY_ALLOWED is False, "KELLY_DEPLOY_ALLOWED must be False"
    assert REAL_BET_ALLOWED is False, "REAL_BET_ALLOWED must be False"
    assert PRODUCTION_READY is False, "PRODUCTION_READY must be False"
    assert CEO_AUTHORIZATION_CONFIRMED is True, "CEO authorization must be confirmed"

    key_status = detect_api_key_status()
    print(f"[P71] Key detection result: {key_status}")

    if key_status == "API_KEY_MISSING":
        summary = run_awaiting_key_closure()
    else:
        summary = run_live_pull_path()

    written_path = write_summary(summary, output_path)
    print(f"[P71] Summary written → {written_path}")
    print(f"[P71] Classification: {summary['p71_classification']}")
    return summary


if __name__ == "__main__":
    run_p71()
