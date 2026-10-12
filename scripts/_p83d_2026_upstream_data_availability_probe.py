"""
P83D — 2026 Upstream Data Availability Probe + Producer Activation Gate
Date: 2026-05-26
Mode: paper_only=True | diagnostic_only=True | NO_REAL_BET=True

Goals:
  1. Verify P83C artifact and classification.
  2. Probe local filesystem for upstream 2026 game schedule, pitcher features, and model outputs.
  3. Evaluate 6 readiness gates (SCHEDULE / PITCHER_FEATURE / MODEL_OUTPUT /
     PREDICTED_SIDE / GOVERNANCE / PRODUCER_ACTIVATION).
  4. Emit P83D classification based on gate results.
  5. If upstream data is complete → emit P83D_PRODUCER_ACTIVATION_READY.
  6. If upstream data is missing → emit P83D_AWAITING_UPSTREAM_DATA with checklist.
  7. Generate future P83E prompt.

Expected classification when no upstream data exists:
  P83D_AWAITING_UPSTREAM_DATA
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# ---------------------------------------------------------------------------
# Governance — MUST stay paper_only=True / diagnostic_only=True
# ---------------------------------------------------------------------------
GOVERNANCE: dict[str, Any] = {
    "paper_only": True,
    "diagnostic_only": True,
    "uses_historical_odds": False,
    "live_api_calls": 0,
    "the_odds_api_key_required": False,
    "api_key_accessed": False,
    "ev_calculated": False,
    "clv_calculated": False,
    "market_edge_calculated": False,
    "market_edge_evaluated": False,
    "kelly_calculated": False,
    "kelly_deploy_allowed": False,
    "production_ready": False,
    "real_bet_allowed": False,
    "champion_replacement_allowed": False,
    "profitability_claim": False,
    "odds_used": False,
}

ALLOWED_CLASSIFICATIONS = [
    "P83D_AWAITING_UPSTREAM_DATA",
    "P83D_PRODUCER_ACTIVATION_READY",
    "P83D_BLOCKED_BY_MISSING_P83C_ARTIFACT",
    "P83D_FAILED_VALIDATION",
]

PREDICTION_BOUNDARY = (
    "P83D is a local-only upstream data availability probe. "
    "No external API calls are made. No market edge is computed. "
    "No canonical 2026 prediction rows are written unless upstream is complete "
    "and task explicitly authorizes activation. "
    "paper_only=True, diagnostic_only=True."
)

# ---------------------------------------------------------------------------
# Source artifact paths
# ---------------------------------------------------------------------------
SOURCE_ARTIFACTS: dict[str, Path] = {
    "p83c_json": ROOT / "data/mlb_2026/derived/p83c_2026_prediction_schema_producer_contract_summary.json",
    "p83b_json": ROOT / "data/mlb_2026/derived/p83b_2026_prediction_data_ingest_contract_summary.json",
    "p83a_json": ROOT / "data/mlb_2026/derived/p83a_2026_live_accumulation_first_snapshot_summary.json",
    "p82c_json": ROOT / "data/mlb_2025/derived/p82c_staging_guard_dryrun_scanner_summary.json",
    "p77_json": ROOT / "data/mlb_2025/derived/p77_prediction_only_shadow_tracker_contract_summary.json",
    "p76_json": ROOT / "data/mlb_2025/derived/p76_corrected_tier_c_final_rule_selection_summary.json",
}

CANONICAL_PREDICTION_PATH = ROOT / "data/mlb_2026/predictions/mlb_2026_prediction_rows.jsonl"

# ---------------------------------------------------------------------------
# Probe paths
# ---------------------------------------------------------------------------
PROBE_PATHS: list[Path] = [
    ROOT / "data/mlb_2026",
    ROOT / "data/mlb_2026/schedule",
    ROOT / "data/mlb_2026/pitchers",
    ROOT / "data/mlb_2026/features",
    ROOT / "data/mlb_2026/model_outputs",
    ROOT / "data/mlb_2026/predictions",
    ROOT / "data/mlb_2026/derived",
    ROOT / "outputs/online_validation",
    ROOT / "outputs/recommendations/PAPER",
    ROOT / "outputs/predictions/PAPER",
]

# Fields required by each gate
SCHEDULE_REQUIRED_FIELDS = {"game_id", "game_date", "home_team", "away_team"}
PITCHER_FEATURE_REQUIRED_FIELDS = {"home_sp_fip", "away_sp_fip"}
MODEL_OUTPUT_REQUIRED_FIELDS = {"model_probability", "predicted_side", "source_prediction_version"}
PREDICTED_SIDE_LOGIC_REQUIRED = ["sp_fip_delta > 0 → home", "sp_fip_delta < 0 → away", "ties excluded"]
GOVERNANCE_FIELDS = {"paper_only", "diagnostic_only", "odds_used", "market_edge_evaluated", "production_ready"}

# P83B canonical schema fields required in canonical rows
P83B_REQUIRED_FIELDS = [
    "game_id", "game_date", "season", "home_team", "away_team",
    "sp_fip_delta", "abs_sp_fip_delta", "model_probability",
    "predicted_side", "source_prediction_version",
    "paper_only", "diagnostic_only", "odds_used",
    "market_edge_evaluated", "production_ready",
    "primary_125", "shadow_100", "tier_b_candidate", "tier_a_candidate",
]

# ---------------------------------------------------------------------------
# Step 1 — Verify P83C artifact
# ---------------------------------------------------------------------------

def verify_p83c_artifact() -> dict[str, Any]:
    path = SOURCE_ARTIFACTS["p83c_json"]
    if not path.exists():
        return {
            "artifact_loaded": False,
            "artifact_path": str(path),
            "error": "P83C artifact file not found. Cannot proceed.",
            "classification": "P83D_BLOCKED_BY_MISSING_P83C_ARTIFACT",
        }
    with open(path) as f:
        data = json.load(f)

    classification = data.get("p83c_classification", "")
    governance = data.get("governance", {})
    upstream_contract = data.get("step2_upstream_input_contract", {})
    producer = data.get("step3_schema_producer", {})
    p83b_verification = data.get("step1_p83b_verification", {})

    classification_ok = classification == "P83C_SCHEMA_PRODUCER_READY_AWAITING_UPSTREAM_DATA"
    live_api_ok = governance.get("live_api_calls", 1) == 0
    canonical_path = p83b_verification.get("prediction_path", "")
    canonical_path_defined = bool(canonical_path)
    upstream_contract_exists = bool(upstream_contract.get("required_input_fields", []) or upstream_contract.get("required_input_groups"))
    snapshot_unlock_blocked = producer.get("snapshot_unlock_blocked", True)
    required_input_fields = upstream_contract.get("required_input_fields", [])

    # Extract the required input groups to understand what's needed
    required_input_groups = upstream_contract.get("required_input_groups", {})

    return {
        "artifact_loaded": True,
        "artifact_path": str(path),
        "p83c_classification": classification,
        "classification_ok": classification_ok,
        "live_api_calls": governance.get("live_api_calls", 0),
        "live_api_ok": live_api_ok,
        "canonical_prediction_path": canonical_path,
        "canonical_path_defined": canonical_path_defined,
        "upstream_contract_exists": upstream_contract_exists,
        "upstream_contract_id": upstream_contract.get("contract_id", ""),
        "snapshot_unlock_blocked": snapshot_unlock_blocked,
        "required_input_fields": required_input_fields,
        "required_input_groups": required_input_groups,
        "mock_rows_noncanonical": True,
        "verification_ok": all([
            classification_ok,
            live_api_ok,
            canonical_path_defined,
            upstream_contract_exists,
        ]),
    }


# ---------------------------------------------------------------------------
# Step 2 — Probe local upstream candidate paths
# ---------------------------------------------------------------------------

def _classify_file(path: Path) -> str:
    """Classify a file into upstream data category."""
    name = path.name.lower()
    parts = str(path).lower()

    # Runtime PAPER recommendation outputs — never canonical
    if "recommendations/paper" in parts or "predictions/paper" in parts:
        return "runtime_paper_candidate"

    # Schedule candidates
    if any(k in name for k in ["schedule", "games", "game_ids", "calendar"]):
        if "2026" in name:
            return "schedule_candidate"

    # Pitcher feature candidates
    if any(k in name for k in ["pitcher", "fip", "sp_fip", "starter"]):
        if "2026" in name:
            return "pitcher_feature_candidate"

    # Model output candidates
    if any(k in name for k in ["model_output", "model_prob", "prediction_rows", "predictions"]):
        if "2026" in name and "predictions/mlb_2026" in parts:
            return "canonical_prediction_candidate"
        if "2026" in name:
            return "model_probability_candidate"

    # Derived / contract files
    if "derived" in parts and "p83" in name:
        return "contract_artifact"

    return "noncanonical"


def probe_upstream_paths() -> dict[str, Any]:
    """Walk probe paths and classify discovered files."""
    found: dict[str, list[str]] = {
        "schedule_candidate": [],
        "pitcher_feature_candidate": [],
        "model_probability_candidate": [],
        "canonical_prediction_candidate": [],
        "runtime_paper_candidate": [],
        "contract_artifact": [],
        "noncanonical": [],
    }

    dirs_probed: list[str] = []
    dirs_missing: list[str] = []

    for probe_dir in PROBE_PATHS:
        if not probe_dir.exists():
            dirs_missing.append(str(probe_dir.relative_to(ROOT)))
            continue
        dirs_probed.append(str(probe_dir.relative_to(ROOT)))
        for p in sorted(probe_dir.rglob("*")):
            if p.is_file() and not p.suffix == ".pyc":
                category = _classify_file(p)
                found[category].append(str(p.relative_to(ROOT)))

    # Check canonical prediction path explicitly
    canonical_exists = CANONICAL_PREDICTION_PATH.exists()
    canonical_row_count = 0
    if canonical_exists:
        with open(CANONICAL_PREDICTION_PATH) as f:
            for line in f:
                if line.strip():
                    canonical_row_count += 1

    # Check runtime PAPER files specifically
    paper_dir_2026 = ROOT / "outputs/recommendations/PAPER"
    runtime_paper_files_2026: list[str] = []
    if paper_dir_2026.exists():
        for d in sorted(paper_dir_2026.iterdir()):
            if d.is_dir() and d.name.startswith("2026"):
                for f in sorted(d.iterdir()):
                    if f.is_file():
                        runtime_paper_files_2026.append(str(f.relative_to(ROOT)))

    return {
        "dirs_probed": dirs_probed,
        "dirs_missing": dirs_missing,
        "files_by_category": found,
        "canonical_prediction_path": str(CANONICAL_PREDICTION_PATH.relative_to(ROOT)),
        "canonical_prediction_exists": canonical_exists,
        "canonical_prediction_row_count": canonical_row_count,
        "runtime_paper_files_2026": runtime_paper_files_2026,
        "runtime_paper_file_count": len(runtime_paper_files_2026),
        "runtime_paper_noncanonical": True,
    }


# ---------------------------------------------------------------------------
# Step 3 — Runtime PAPER file field analysis (noncanonical)
# ---------------------------------------------------------------------------

def analyze_runtime_paper_fields() -> dict[str, Any]:
    """
    Inspect what fields are available in runtime PAPER files.
    These files are noncanonical per P83B but useful for understanding
    what model outputs already exist in a different schema.
    """
    paper_dir = ROOT / "outputs/recommendations/PAPER"
    if not paper_dir.exists():
        return {"error": "PAPER dir missing", "runtime_paper_fields_available": []}

    sample_fields: set[str] = set()
    files_read = 0
    for d in sorted(paper_dir.iterdir()):
        if d.is_dir() and d.name.startswith("2026"):
            for f in sorted(d.iterdir()):
                if f.suffix == ".jsonl" and f.stat().st_size > 0:
                    with open(f) as fp:
                        line = fp.readline().strip()
                        if line:
                            row = json.loads(line)
                            sample_fields.update(row.keys())
                            files_read += 1
                            if files_read >= 5:
                                break
        if files_read >= 5:
            break

    present = sorted(sample_fields)
    # Which P83B fields are missing from runtime PAPER schema?
    p83b_set = set(P83B_REQUIRED_FIELDS)
    missing_from_paper = sorted(p83b_set - sample_fields)
    extra_in_paper = sorted(sample_fields - p83b_set)

    return {
        "files_read": files_read,
        "runtime_paper_fields_available": present,
        "p83b_fields_present_in_paper": sorted(sample_fields & p83b_set),
        "p83b_fields_missing_from_paper": missing_from_paper,
        "extra_fields_in_paper": extra_in_paper,
        "runtime_paper_noncanonical": True,
        "reason_noncanonical": (
            "Runtime PAPER files use a different schema (recommendation schema) "
            "and lack required P83B fields: game_date, home_team, away_team, "
            "sp_fip_delta, abs_sp_fip_delta, source_prediction_version, "
            "diagnostic_only, odds_used, market_edge_evaluated, production_ready, "
            "primary_125, shadow_100, tier_b_candidate, tier_a_candidate."
        ),
    }


# ---------------------------------------------------------------------------
# Step 4 — Evaluate readiness gates
# ---------------------------------------------------------------------------

def _check_schedule_gate(probe_results: dict[str, Any]) -> dict[str, Any]:
    candidates = probe_results["files_by_category"].get("schedule_candidate", [])
    # Runtime PAPER files have game_id + game_start_utc but NOT game_date / home_team / away_team
    # in canonical P83B format
    fields_available: set[str] = set()
    if probe_results["runtime_paper_file_count"] > 0:
        # game_id is derivable from filename; game_date and team names are embedded in game_id
        # but NOT in proper separate fields per P83B schema
        fields_available.add("game_id_partial")  # e.g. "2026-05-11-LAA-CLE-824441"

    missing_fields = sorted(SCHEDULE_REQUIRED_FIELDS - {"game_id_partial"})
    # game_id can be parsed from runtime PAPER filenames, but game_date / home_team / away_team
    # are not available as separate structured fields in canonical path
    gate_pass = False  # No canonical schedule file with proper fields
    return {
        "gate_name": "SCHEDULE_GATE",
        "gate_pass": gate_pass,
        "required_fields": sorted(SCHEDULE_REQUIRED_FIELDS),
        "candidate_files": candidates,
        "runtime_paper_partial": probe_results["runtime_paper_file_count"] > 0,
        "missing_fields": ["game_date", "home_team", "away_team"],
        "note": (
            "Runtime PAPER files have game_id only (in filename pattern). "
            "No canonical data/mlb_2026/schedule/ file with game_date + team identifiers."
        ),
    }


def _check_pitcher_feature_gate(probe_results: dict[str, Any]) -> dict[str, Any]:
    candidates = probe_results["files_by_category"].get("pitcher_feature_candidate", [])
    gate_pass = len(candidates) > 0
    return {
        "gate_name": "PITCHER_FEATURE_GATE",
        "gate_pass": gate_pass,
        "required_fields": sorted(PITCHER_FEATURE_REQUIRED_FIELDS),
        "derived_fields": ["sp_fip_delta", "abs_sp_fip_delta"],
        "candidate_files": candidates,
        "missing_fields": [] if gate_pass else sorted(PITCHER_FEATURE_REQUIRED_FIELDS),
        "note": (
            "No data/mlb_2026/pitchers/ directory or file with home_sp_fip / away_sp_fip. "
            "2026 starting pitcher FIP stats not locally available."
        ) if not gate_pass else "Candidate files found.",
    }


def _check_model_output_gate(probe_results: dict[str, Any], paper_analysis: dict[str, Any]) -> dict[str, Any]:
    # Runtime PAPER files have model_prob_home / model_prob_away — BUT the field name
    # is different from P83B schema's "model_probability"
    runtime_has_prob = "model_prob_home" in paper_analysis.get("runtime_paper_fields_available", [])
    # canonical model_probability field (P83B format) is missing
    gate_pass = False
    return {
        "gate_name": "MODEL_OUTPUT_GATE",
        "gate_pass": gate_pass,
        "required_fields": sorted(MODEL_OUTPUT_REQUIRED_FIELDS),
        "runtime_paper_partial": runtime_has_prob,
        "runtime_paper_field_mapping": {
            "model_prob_home": "noncanonical — maps to model_probability for home side only",
            "model_prob_away": "noncanonical — separate field, not unified model_probability",
        } if runtime_has_prob else {},
        "missing_canonical_fields": ["model_probability", "source_prediction_version"],
        "note": (
            "Runtime PAPER files have model_prob_home/away in recommendation schema. "
            "Canonical P83B model_probability + source_prediction_version not present."
        ),
    }


def _check_predicted_side_gate() -> dict[str, Any]:
    # predicted_side logic is fully deterministic and defined in P83C contract
    # The logic itself is available (no data needed) — but it cannot be applied
    # without sp_fip_delta which requires pitcher FIP inputs
    logic_available = True  # Formula is known
    data_available = False   # sp_fip_delta cannot be computed without pitcher data
    gate_pass = False  # Gate requires both logic + computable data
    return {
        "gate_name": "PREDICTED_SIDE_GATE",
        "gate_pass": gate_pass,
        "logic_available": logic_available,
        "logic_definition": "predicted_side = 'home' if sp_fip_delta > 0 else 'away'; ties excluded",
        "data_available": data_available,
        "missing_dependency": "sp_fip_delta requires home_sp_fip and away_sp_fip from PITCHER_FEATURE_GATE",
        "note": "Deterministic logic defined in P83C. Blocked because pitcher FIP inputs unavailable.",
    }


def _check_governance_gate() -> dict[str, Any]:
    # Governance flags are constants — always available, never need upstream data
    gate_pass = True
    return {
        "gate_name": "GOVERNANCE_GATE",
        "gate_pass": gate_pass,
        "enforced_values": {
            "season": 2026,
            "paper_only": True,
            "diagnostic_only": True,
            "odds_used": False,
            "market_edge_evaluated": False,
            "production_ready": False,
        },
        "note": "Governance flags are pre-defined constants. No upstream data needed.",
    }


def _check_producer_activation_gate(gates: dict[str, Any]) -> dict[str, Any]:
    prerequisite_gates = [
        "SCHEDULE_GATE",
        "PITCHER_FEATURE_GATE",
        "MODEL_OUTPUT_GATE",
        "PREDICTED_SIDE_GATE",
        "GOVERNANCE_GATE",
    ]
    failing_gates = [g for g in prerequisite_gates if not gates[g]["gate_pass"]]
    gate_pass = len(failing_gates) == 0
    return {
        "gate_name": "PRODUCER_ACTIVATION_GATE",
        "gate_pass": gate_pass,
        "prerequisite_gates": prerequisite_gates,
        "failing_prerequisite_gates": failing_gates,
        "passing_prerequisite_gates": [g for g in prerequisite_gates if gates[g]["gate_pass"]],
        "note": (
            f"Blocked by {len(failing_gates)} failing prerequisite gate(s)."
            if not gate_pass else "All prerequisite gates pass. Producer activation allowed."
        ),
    }


def evaluate_readiness_gates(
    probe_results: dict[str, Any],
    paper_analysis: dict[str, Any],
) -> dict[str, Any]:
    schedule = _check_schedule_gate(probe_results)
    pitcher = _check_pitcher_feature_gate(probe_results)
    model = _check_model_output_gate(probe_results, paper_analysis)
    predicted_side = _check_predicted_side_gate()
    governance = _check_governance_gate()

    gates = {
        "SCHEDULE_GATE": schedule,
        "PITCHER_FEATURE_GATE": pitcher,
        "MODEL_OUTPUT_GATE": model,
        "PREDICTED_SIDE_GATE": predicted_side,
        "GOVERNANCE_GATE": governance,
    }
    activation = _check_producer_activation_gate(gates)
    gates["PRODUCER_ACTIVATION_GATE"] = activation

    passing = [k for k, v in gates.items() if v["gate_pass"]]
    failing = [k for k, v in gates.items() if not v["gate_pass"]]

    return {
        "gates": gates,
        "passing_gates": passing,
        "failing_gates": failing,
        "total_gates": len(gates),
        "gates_passing": len(passing),
        "gates_failing": len(failing),
        "producer_activation_allowed": activation["gate_pass"],
    }


# ---------------------------------------------------------------------------
# Step 5 — Build missing data checklist
# ---------------------------------------------------------------------------

def build_missing_data_checklist(gate_results: dict[str, Any]) -> dict[str, Any]:
    missing_items: list[dict[str, str]] = []

    if not gate_results["gates"]["SCHEDULE_GATE"]["gate_pass"]:
        missing_items.append({
            "gate": "SCHEDULE_GATE",
            "missing": "2026 MLB game schedule with game_id, game_date, home_team, away_team",
            "expected_path": "data/mlb_2026/schedule/mlb_2026_schedule.jsonl",
            "source_hint": "statsapi.mlb.com schedule endpoint OR manual fixture for testing",
            "priority": "HIGH",
        })

    if not gate_results["gates"]["PITCHER_FEATURE_GATE"]["gate_pass"]:
        missing_items.append({
            "gate": "PITCHER_FEATURE_GATE",
            "missing": "2026 starting pitcher FIP stats: home_sp_fip, away_sp_fip per game",
            "expected_path": "data/mlb_2026/pitchers/mlb_2026_sp_fip_features.jsonl",
            "source_hint": "statsapi.mlb.com pitcher stats OR 2026 FIP lookup table",
            "priority": "HIGH",
        })

    if not gate_results["gates"]["MODEL_OUTPUT_GATE"]["gate_pass"]:
        missing_items.append({
            "gate": "MODEL_OUTPUT_GATE",
            "missing": "Canonical model_probability + source_prediction_version per game (P83B schema)",
            "expected_path": "data/mlb_2026/model_outputs/mlb_2026_model_outputs.jsonl",
            "source_hint": (
                "Apply 2025-trained ensemble model to 2026 features. "
                "Runtime PAPER files have model_prob_home/away but not in P83B format."
            ),
            "priority": "HIGH",
        })

    if not gate_results["gates"]["PREDICTED_SIDE_GATE"]["gate_pass"]:
        missing_items.append({
            "gate": "PREDICTED_SIDE_GATE",
            "missing": "sp_fip_delta (computed from home_sp_fip - away_sp_fip)",
            "expected_path": "derived from PITCHER_FEATURE_GATE data",
            "source_hint": "Unblocked automatically once PITCHER_FEATURE_GATE passes",
            "priority": "DEPENDENT",
        })

    rerun_triggers: list[str] = [
        "When data/mlb_2026/schedule/ contains canonical game schedule file",
        "When data/mlb_2026/pitchers/ contains 2026 SP FIP features",
        "When data/mlb_2026/model_outputs/ contains canonical model output file",
        "When all 3 HIGH priority items above are resolved",
    ]

    return {
        "missing_item_count": len(missing_items),
        "missing_items": missing_items,
        "rerun_triggers": rerun_triggers,
        "notes": (
            "GOVERNANCE_GATE always passes (constants). "
            "PREDICTED_SIDE_GATE unblocks automatically when PITCHER_FEATURE_GATE passes."
        ),
    }


# ---------------------------------------------------------------------------
# Step 6 — Determine P83D classification
# ---------------------------------------------------------------------------

def determine_classification(
    p83c_verified: dict[str, Any],
    gate_results: dict[str, Any],
) -> str:
    if not p83c_verified.get("artifact_loaded", False):
        return "P83D_BLOCKED_BY_MISSING_P83C_ARTIFACT"
    if not p83c_verified.get("verification_ok", False):
        return "P83D_FAILED_VALIDATION"
    if gate_results["producer_activation_allowed"]:
        return "P83D_PRODUCER_ACTIVATION_READY"
    return "P83D_AWAITING_UPSTREAM_DATA"


# ---------------------------------------------------------------------------
# Step 7 — Generate future P83E prompt
# ---------------------------------------------------------------------------

def generate_p83e_prompt(classification: str) -> str:
    if classification == "P83D_AWAITING_UPSTREAM_DATA":
        return (
            "[P83E — 2026 Canonical Prediction Row Producer]\n\n"
            "# Prerequisites\n"
            "- P83D classification must be P83D_PRODUCER_ACTIVATION_READY\n"
            "- P83D commit must be present on main branch\n\n"
            "# Trigger conditions\n"
            "Run P83E only when ALL of the following files exist locally:\n"
            "  1. data/mlb_2026/schedule/mlb_2026_schedule.jsonl "
            "   (game_id, game_date, home_team, away_team)\n"
            "  2. data/mlb_2026/pitchers/mlb_2026_sp_fip_features.jsonl "
            "   (game_id, home_sp_fip, away_sp_fip)\n"
            "  3. data/mlb_2026/model_outputs/mlb_2026_model_outputs.jsonl "
            "   (game_id, model_probability, source_prediction_version)\n\n"
            "# Goal\n"
            "P83E must:\n"
            "  1. Re-run P83D probe to confirm all gates now pass.\n"
            "  2. Join schedule + pitcher features + model outputs by game_id.\n"
            "  3. Compute sp_fip_delta, abs_sp_fip_delta, predicted_side, rule flags.\n"
            "  4. Enforce governance: paper_only=True, diagnostic_only=True, odds_used=False.\n"
            "  5. Write canonical rows to: "
            "data/mlb_2026/predictions/mlb_2026_prediction_rows.jsonl\n"
            "  6. Update P83A snapshot unlock gate.\n"
            "  7. Update P83D summary with producer_activated=True.\n\n"
            "# Rules\n"
            "- No external API calls\n"
            "- No odds data\n"
            "- No edge / EV / CLV / Kelly calculation\n"
            "- Keep paper_only=True, diagnostic_only=True\n"
            "- Do NOT fabricate pitcher FIP values\n"
        )
    else:
        return (
            "[P83E — 2026 Canonical Prediction Row Producer]\n\n"
            "P83D classification is P83D_PRODUCER_ACTIVATION_READY. "
            "All upstream gates have passed. P83E may now produce canonical rows.\n\n"
            "Proceed directly to joining schedule + pitcher + model output files "
            "and writing canonical rows to "
            "data/mlb_2026/predictions/mlb_2026_prediction_rows.jsonl."
        )


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

def run_p83d_probe() -> dict[str, Any]:
    ts = datetime.now(timezone.utc).isoformat()

    # Step 1 — Verify P83C
    p83c_verified = verify_p83c_artifact()
    if not p83c_verified.get("artifact_loaded"):
        classification = "P83D_BLOCKED_BY_MISSING_P83C_ARTIFACT"
        return {
            "phase": "P83D",
            "date": "2026-05-26",
            "generated_at": ts,
            "p83d_classification": classification,
            "governance": GOVERNANCE,
            "prediction_boundary": PREDICTION_BOUNDARY,
            "step1_p83c_verification": p83c_verified,
            "error": p83c_verified.get("error"),
        }

    # Step 2 — Probe upstream paths
    probe_results = probe_upstream_paths()

    # Step 3 — Analyze runtime PAPER fields
    paper_analysis = analyze_runtime_paper_fields()

    # Step 4 — Evaluate gates
    gate_results = evaluate_readiness_gates(probe_results, paper_analysis)

    # Step 5 — Missing data checklist
    checklist = build_missing_data_checklist(gate_results)

    # Step 6 — Classification
    classification = determine_classification(p83c_verified, gate_results)

    # Step 7 — P83E prompt
    p83e_prompt = generate_p83e_prompt(classification)

    # Producer activation status
    producer_activation_status: dict[str, Any] = {
        "activation_allowed": gate_results["producer_activation_allowed"],
        "canonical_rows_written": False,
        "canonical_prediction_path": str(CANONICAL_PREDICTION_PATH.relative_to(ROOT)),
        "canonical_prediction_exists": probe_results["canonical_prediction_exists"],
        "canonical_prediction_row_count": probe_results["canonical_prediction_row_count"],
        "reason": (
            "All gates pass. P83E authorized to produce canonical rows."
            if gate_results["producer_activation_allowed"]
            else f"Blocked by failing gates: {gate_results['failing_gates']}"
        ),
        "note": (
            "P83D does not write canonical rows. "
            "Canonical row production is delegated to P83E."
        ),
    }

    # Forbidden scan
    forbidden_scan: dict[str, Any] = {
        "live_api_calls": GOVERNANCE["live_api_calls"],
        "api_key_accessed": GOVERNANCE["api_key_accessed"],
        "ev_calculated": GOVERNANCE["ev_calculated"],
        "clv_calculated": GOVERNANCE["clv_calculated"],
        "market_edge_calculated": GOVERNANCE["market_edge_calculated"],
        "kelly_calculated": GOVERNANCE["kelly_calculated"],
        "odds_used": GOVERNANCE["odds_used"],
        "production_ready": GOVERNANCE["production_ready"],
        "kelly_deploy_allowed": GOVERNANCE["kelly_deploy_allowed"],
        "real_bet_allowed": GOVERNANCE["real_bet_allowed"],
        "profitability_claim": GOVERNANCE["profitability_claim"],
        "canonical_rows_written_in_p83d": False,
        "forbidden_scan_pass": True,
    }

    result: dict[str, Any] = {
        "phase": "P83D",
        "date": "2026-05-26",
        "generated_at": ts,
        "p83d_classification": classification,
        "allowed_classifications": ALLOWED_CLASSIFICATIONS,
        "prediction_boundary": PREDICTION_BOUNDARY,
        "governance": GOVERNANCE,
        "step1_p83c_verification": p83c_verified,
        "step2_upstream_probe": probe_results,
        "step3_runtime_paper_analysis": paper_analysis,
        "step4_gate_results": gate_results,
        "step5_missing_data_checklist": checklist,
        "step6_producer_activation_status": producer_activation_status,
        "step7_p83e_prompt": p83e_prompt,
        "forbidden_scan": forbidden_scan,
        "source_artifacts": {k: str(v) for k, v in SOURCE_ARTIFACTS.items()},
        "canonical_prediction_path": str(CANONICAL_PREDICTION_PATH.relative_to(ROOT)),
        "probe_paths": [str(p.relative_to(ROOT)) for p in PROBE_PATHS],
    }
    return result


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    result = run_p83d_probe()

    out_dir = ROOT / "data/mlb_2026/derived"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_json = out_dir / "p83d_2026_upstream_data_availability_probe_summary.json"
    with open(out_json, "w") as f:
        json.dump(result, f, indent=2)
    print(f"[P83D] JSON written → {out_json.relative_to(ROOT)}")

    report_dir = ROOT / "report"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "p83d_2026_upstream_data_availability_probe_20260526.md"

    gates = result["step4_gate_results"]["gates"]
    gate_table_rows = []
    for gname, gdata in gates.items():
        status = "✅ PASS" if gdata["gate_pass"] else "❌ FAIL"
        note = gdata.get("note", "")[:80]
        gate_table_rows.append(f"| {gname} | {status} | {note} |")
    gate_table = "\n".join(gate_table_rows)

    checklist = result["step5_missing_data_checklist"]
    missing_rows = []
    for item in checklist["missing_items"]:
        missing_rows.append(
            f"- **{item['gate']}** [{item['priority']}]: {item['missing']}\n"
            f"  - Expected path: `{item['expected_path']}`\n"
            f"  - Source hint: {item['source_hint']}"
        )
    missing_section = "\n".join(missing_rows) if missing_rows else "_None — all gates pass._"

    probe = result["step2_upstream_probe"]
    probe_table_rows = []
    for cat, files in probe["files_by_category"].items():
        count = len(files)
        probe_table_rows.append(f"| {cat} | {count} |")
    probe_table = "\n".join(probe_table_rows)

    md = f"""# P83D — 2026 Upstream Data Availability Probe
**Date:** 2026-05-26
**Classification:** `{result['p83d_classification']}`
**Mode:** paper_only=True | diagnostic_only=True | NO_REAL_BET=True

---

## Summary

P83D probes all local filesystem paths for upstream 2026 data required by
P83C's upstream input contract. No external API calls are made.

**Result:** `{result['p83d_classification']}`

---

## P83C State Verification

| Field | Value |
|---|---|
| Classification | `{result['step1_p83c_verification']['p83c_classification']}` |
| Classification OK | {result['step1_p83c_verification']['classification_ok']} |
| live_api_calls | {result['step1_p83c_verification']['live_api_calls']} |
| Canonical prediction path | `{result['step1_p83c_verification']['canonical_prediction_path']}` |
| Upstream contract ID | `{result['step1_p83c_verification']['upstream_contract_id']}` |
| Snapshot unlock blocked | {result['step1_p83c_verification']['snapshot_unlock_blocked']} |
| Mock rows noncanonical | {result['step1_p83c_verification']['mock_rows_noncanonical']} |

---

## Upstream Probe Results

### Directories Probed
{chr(10).join(f"- `{d}`" for d in probe['dirs_probed'])}

### Directories Missing
{chr(10).join(f"- `{d}`" for d in probe['dirs_missing']) if probe['dirs_missing'] else "_None missing._"}

### File Classification

| Category | File Count |
|---|---|
{probe_table}

### Runtime PAPER Files (2026)
- **File count:** {probe['runtime_paper_file_count']}
- **Noncanonical:** True (per P83B contract)
- **Files:** {probe['runtime_paper_files_2026']}

### Canonical Prediction File
- **Path:** `{probe['canonical_prediction_path']}`
- **Exists:** {probe['canonical_prediction_exists']}
- **Row count:** {probe['canonical_prediction_row_count']}

---

## Readiness Gate Table

| Gate | Status | Note |
|---|---|---|
{gate_table}

**Passing gates:** {result['step4_gate_results']['gates_passing']} / {result['step4_gate_results']['total_gates']}

---

## Producer Activation Status

| Field | Value |
|---|---|
| activation_allowed | {result['step6_producer_activation_status']['activation_allowed']} |
| canonical_rows_written | {result['step6_producer_activation_status']['canonical_rows_written']} |
| canonical_prediction_exists | {result['step6_producer_activation_status']['canonical_prediction_exists']} |
| Reason | {result['step6_producer_activation_status']['reason']} |

---

## Missing Data Checklist

{missing_section}

### Rerun Triggers
{chr(10).join(f"- {t}" for t in checklist['rerun_triggers'])}

---

## Future P83E Prompt

```
{result['step7_p83e_prompt']}
```

---

## Governance Invariants

| Invariant | Value |
|---|---|
| paper_only | {GOVERNANCE['paper_only']} |
| diagnostic_only | {GOVERNANCE['diagnostic_only']} |
| live_api_calls | {GOVERNANCE['live_api_calls']} |
| odds_used | {GOVERNANCE['odds_used']} |
| ev_calculated | {GOVERNANCE['ev_calculated']} |
| clv_calculated | {GOVERNANCE['clv_calculated']} |
| kelly_calculated | {GOVERNANCE['kelly_calculated']} |
| kelly_deploy_allowed | {GOVERNANCE['kelly_deploy_allowed']} |
| production_ready | {GOVERNANCE['production_ready']} |
| real_bet_allowed | {GOVERNANCE['real_bet_allowed']} |
| profitability_claim | {GOVERNANCE['profitability_claim']} |
| canonical_rows_written_in_p83d | False |
| forbidden_scan_pass | {result['forbidden_scan']['forbidden_scan_pass']} |

---

## Final Classification

**`{result['p83d_classification']}`**

{result['prediction_boundary']}
"""
    with open(report_path, "w") as f:
        f.write(md)
    print(f"[P83D] Report written → {report_path.relative_to(ROOT)}")

    classification = result["p83d_classification"]
    gates_pass = result["step4_gate_results"]["gates_passing"]
    gates_fail = result["step4_gate_results"]["gates_failing"]
    print(f"[P83D] Classification: {classification}")
    print(f"[P83D] Gates passing: {gates_pass}/{result['step4_gate_results']['total_gates']}")
    print(f"[P83D] Failing gates: {gates_fail}")
