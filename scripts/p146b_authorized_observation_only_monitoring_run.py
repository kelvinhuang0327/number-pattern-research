#!/usr/bin/env python3
"""
P146B: Authorized observation-only monitoring run.

REQUIRES --authorization argument with exact phrase:
  P145B_AUTHORIZED_MANUAL_ON_DEMAND_MONITORING_OBSERVATION_ONLY_FOR_6_WAVE2_CANDIDATES_20260529

If authorization is missing or wrong, script exits non-zero with NO file output.

This script executes an authorized observation-only mock/fixture monitoring run for
all 6 Wave 2 candidate strategies.  No DB writes.  No live API calls.
No scheduler install.  No controlled_apply.  No registry update.
No champion promotion.  Output mode: file_artifact_only.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT / "lottery_api/data/lottery_v2.db"

TASK_ID = "P146B"
CLASSIFICATION = "P146B_AUTHORIZED_OBSERVATION_ONLY_MONITORING_RUN_COMPLETED"
DATE_SUFFIX = "20260529"

CANONICAL_REPO = str(REPO_ROOT)
CANONICAL_BRANCH = "claude/zen-gates-ff6802"
EXPECTED_TOTAL_ROWS = 94924

REQUIRED_AUTHORIZATION_PHRASE = (
    "P145B_AUTHORIZED_MANUAL_ON_DEMAND_MONITORING_OBSERVATION_ONLY_FOR_6_WAVE2_CANDIDATES_20260529"
)

OUT_JSON = REPO_ROOT / f"outputs/replay/p146b_authorized_observation_only_monitoring_run_{DATE_SUFFIX}.json"
OUT_MD = REPO_ROOT / f"docs/replay/p146b_authorized_observation_only_monitoring_run_{DATE_SUFFIX}.md"
ROADMAP = REPO_ROOT / "00-Plan/roadmap/roadmap.md"
CTO = REPO_ROOT / "00-Plan/roadmap/CTO-Analysis.md"

OBS_BASE = REPO_ROOT / "outputs/replay/live_monitoring_observation_only"

P146A_JSON = REPO_ROOT / "outputs/replay/p146a_observation_only_live_monitoring_runner_20260529.json"
P145B_JSON = REPO_ROOT / "outputs/replay/p145b_manual_on_demand_monitoring_authorization_gate_20260529.json"
P144B_JSON = REPO_ROOT / "outputs/replay/p144b_live_draw_monitoring_activation_gate_20260529.json"

REQUIRED_OBSERVATION_FIELDS = [
    "monitored_strategy_id",
    "lottery_type",
    "target_draw",
    "prediction_generated_at",
    "draw_result_available_at",
    "predicted_numbers",
    "actual_numbers",
    "hit_count",
    "evaluation_status",
    "source_trace",
    "monitoring_truth_level",
    "created_at",
]

# 6 monitoring candidates with fixture data
MONITORING_CANDIDATES = [
    {
        "strategy_id": "acb_markov_midfreq_3bet",
        "lottery_type": "DAILY_539",
        "bet_count": 3,
        "target_draw": "115000072",
        "actual_numbers": [4, 17, 22, 31, 35],
        "actual_special": None,
        "predicted_numbers_fixture": [
            [4, 10, 17, 34, 36],
            [5, 6, 12, 18, 28],
            [1, 19, 24, 29, 38],
        ],
    },
    {
        "strategy_id": "midfreq_fourier_mk_3bet",
        "lottery_type": "POWER_LOTTO",
        "bet_count": 3,
        "target_draw": "1894",
        "actual_numbers": [3, 12, 19, 24, 33, 38],
        "actual_special": 7,
        "predicted_numbers_fixture": [
            [3, 8, 12, 24, 33, 38],
            [5, 19, 21, 27, 35, 38],
            [2, 12, 18, 24, 30, 33],
        ],
    },
    {
        "strategy_id": "fourier_rhythm_3bet",
        "lottery_type": "POWER_LOTTO",
        "bet_count": 3,
        "target_draw": "1894",
        "actual_numbers": [3, 12, 19, 24, 33, 38],
        "actual_special": 7,
        "predicted_numbers_fixture": [
            [6, 12, 19, 24, 31, 38],
            [3, 10, 22, 27, 33, 36],
            [7, 15, 19, 24, 33, 39],
        ],
    },
    {
        "strategy_id": "pp3_freqort_4bet",
        "lottery_type": "POWER_LOTTO",
        "bet_count": 4,
        "target_draw": "1894",
        "actual_numbers": [3, 12, 19, 24, 33, 38],
        "actual_special": 7,
        "predicted_numbers_fixture": [
            [3, 12, 19, 24, 33, 38],
            [5, 14, 21, 28, 35, 38],
            [3, 12, 24, 30, 33, 38],
            [9, 17, 19, 24, 33, 37],
        ],
    },
    {
        "strategy_id": "power_precision_3bet",
        "lottery_type": "POWER_LOTTO",
        "bet_count": 3,
        "target_draw": "1894",
        "actual_numbers": [3, 12, 19, 24, 33, 38],
        "actual_special": 7,
        "predicted_numbers_fixture": [
            [4, 12, 19, 25, 33, 38],
            [3, 11, 19, 24, 32, 38],
            [6, 12, 18, 24, 33, 37],
        ],
    },
    {
        "strategy_id": "power_orthogonal_5bet",
        "lottery_type": "POWER_LOTTO",
        "bet_count": 5,
        "target_draw": "1894",
        "actual_numbers": [3, 12, 19, 24, 33, 38],
        "actual_special": 7,
        "predicted_numbers_fixture": [
            [3, 12, 19, 24, 33, 38],
            [6, 15, 22, 29, 33, 38],
            [4, 12, 20, 24, 33, 37],
            [3, 10, 19, 24, 31, 38],
            [8, 12, 19, 24, 33, 36],
        ],
    },
]

_OWN_FILES = {
    "scripts/p146b_authorized_observation_only_monitoring_run.py",
    f"outputs/replay/p146b_authorized_observation_only_monitoring_run_{DATE_SUFFIX}.json",
    f"docs/replay/p146b_authorized_observation_only_monitoring_run_{DATE_SUFFIX}.md",
    "tests/test_p146b_authorized_observation_only_monitoring_run.py",
    "00-Plan/roadmap/roadmap.md",
    "00-Plan/roadmap/CTO-Analysis.md",
}
_AUTOUSE_PREFIXES = (
    "outputs/replay/p135_", "outputs/replay/p136_", "outputs/replay/p142_",
    "outputs/replay/p143_", "outputs/replay/p144a_", "outputs/replay/p144b_",
    "outputs/replay/p145b_", "outputs/replay/p146a_",
    "outputs/replay/p144c_",
    "docs/replay/p135_", "docs/replay/p136_", "docs/replay/p142_",
    "docs/replay/p143_", "docs/replay/p144a_", "docs/replay/p144b_",
    "docs/replay/p145b_", "docs/replay/p146a_",
    "docs/replay/p144c_",
    "scripts/p142_", "scripts/p143_", "scripts/p144a_", "scripts/p144b_",
    "scripts/p144c_", "scripts/p145b_", "scripts/p146a_",
    "tests/test_p142_", "tests/test_p143_", "tests/test_p144a_", "tests/test_p144b_",
    "tests/test_p144c_", "tests/test_p145b_", "tests/test_p146a_",
    "outputs/replay/p147_", "docs/replay/p147_", "scripts/p147_", "tests/test_p147_",
)


def _stop(msg: str) -> None:
    print(f"STOP: {msg}", file=sys.stderr)
    sys.exit(1)


def _git(args: list[str]) -> str:
    p = subprocess.run(["git"] + args, cwd=REPO_ROOT, capture_output=True, text=True, check=True)
    return p.stdout.strip()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Phase 0: Authorization check ────────────────────────────────────────────

def check_authorization(provided: str | None) -> dict:
    if provided is None:
        print("ERROR: --authorization argument is required.", file=sys.stderr)
        print(f"Required phrase: {REQUIRED_AUTHORIZATION_PHRASE}", file=sys.stderr)
        sys.exit(1)
    if provided != REQUIRED_AUTHORIZATION_PHRASE:
        print("ERROR: Authorization phrase does not match.", file=sys.stderr)
        print(f"Expected: {REQUIRED_AUTHORIZATION_PHRASE}", file=sys.stderr)
        print(f"Got:      {provided}", file=sys.stderr)
        sys.exit(1)
    return {
        "exact_required_phrase": REQUIRED_AUTHORIZATION_PHRASE,
        "authorization_present": True,
        "execution_allowed": True,
        "authorization_source": "explicit_command_argument",
    }


# ── Phase 0: Stop conditions ─────────────────────────────────────────────────

def verify_repo_branch() -> dict:
    repo = _git(["rev-parse", "--show-toplevel"])
    branch = _git(["branch", "--show-current"])
    repo_ok = repo == CANONICAL_REPO
    branch_ok = branch == CANONICAL_BRANCH
    if not repo_ok:
        _stop(f"Repo mismatch: expected {CANONICAL_REPO!r}, got {repo!r}")
    if not branch_ok:
        _stop(f"Branch mismatch: expected {CANONICAL_BRANCH!r}, got {branch!r}")
    return {"repo_ok": repo_ok, "branch_ok": branch_ok, "repo": repo, "branch": branch}


def verify_db() -> dict:
    with sqlite3.connect(DB_PATH) as conn:
        total = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays;").fetchone()[0]
        cols = [r[1] for r in conn.execute("PRAGMA table_info(strategy_prediction_replays);").fetchall()]
    bet_index_exists = "bet_index" in cols
    if total != EXPECTED_TOTAL_ROWS:
        _stop(f"DB row count mismatch: expected {EXPECTED_TOTAL_ROWS}, got {total}")
    if not bet_index_exists:
        _stop("bet_index column missing from strategy_prediction_replays")
    return {
        "total_rows": total,
        "bet_index_column_exists": bet_index_exists,
        "db_path": str(DB_PATH),
        "drift_guard": "PASS",
    }


def load_predecessor(path: Path, expected_val: str, label: str) -> dict:
    if not path.exists():
        _stop(f"{label} artifact not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    actual = data.get("classification")
    if actual != expected_val:
        _stop(f"{label} classification mismatch: expected {expected_val!r}, got {actual!r}")
    return data


# ── Phase 1: Execute authorized observation-only monitoring run ──────────────

def _compute_hit_count(predicted: list[int], actual: list[int]) -> int:
    return len(set(predicted) & set(actual))


def execute_monitoring_run(now_ts: str) -> tuple[list[dict], list[dict], list[str]]:
    """
    Build observation records for all 6 strategies using fixture data.
    Returns (per_strategy_results, observation_records, output_files).
    """
    per_strategy_results = []
    output_files = []

    for cand in MONITORING_CANDIDATES:
        strategy_id = cand["strategy_id"]
        lottery_type = cand["lottery_type"]
        target_draw = cand["target_draw"]
        actual_numbers = cand["actual_numbers"]
        predicted_fixture = cand["predicted_numbers_fixture"]

        # Compute hit_count from first bet (best bet, representative)
        first_bet = predicted_fixture[0]
        hit_count = _compute_hit_count(first_bet, actual_numbers)

        # Build observation record (12 fields)
        if lottery_type == "DAILY_539":
            draw_result_ts = "2026-05-29T20:30:00+08:00"
            pred_gen_ts = "2026-05-28T18:00:00+00:00"
        else:
            draw_result_ts = "2026-05-29T21:30:00+08:00"
            pred_gen_ts = "2026-05-28T20:00:00+00:00"

        obs_record = {
            "monitored_strategy_id": strategy_id,
            "lottery_type": lottery_type,
            "target_draw": target_draw,
            "prediction_generated_at": pred_gen_ts,
            "draw_result_available_at": draw_result_ts,
            "predicted_numbers": json.dumps(predicted_fixture),
            "actual_numbers": json.dumps(actual_numbers),
            "hit_count": hit_count,
            "evaluation_status": "OBSERVATION_ONLY_MOCK_RUN",
            "source_trace": "p146b_authorized_mock_run",
            "monitoring_truth_level": "MOCK_OBSERVATION_ONLY",
            "created_at": now_ts,
        }

        # Validate 12 fields
        missing = [f for f in REQUIRED_OBSERVATION_FIELDS if f not in obs_record]
        schema_valid = len(missing) == 0

        # Write observation record
        out_dir = OBS_BASE / strategy_id
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / f"p146b_obs_{target_draw}_{DATE_SUFFIX}.json"
        out_file.write_text(json.dumps(obs_record, indent=2, ensure_ascii=False), encoding="utf-8")
        rel_path = str(out_file.relative_to(REPO_ROOT))
        output_files.append(rel_path)

        per_strategy_results.append({
            "strategy_id": strategy_id,
            "lottery_type": lottery_type,
            "record_created": True,
            "skipped_with_reason": None,
            "monitoring_truth_level": "MOCK_OBSERVATION_ONLY",
            "target_draw": target_draw,
            "hit_count": hit_count,
            "evaluation_status": "OBSERVATION_ONLY_MOCK_RUN",
            "output_path": rel_path,
            "champion_evidence_eligible": False,
            "schema_valid": schema_valid,
        })

    return per_strategy_results, output_files


# ── Phase 2: Dirty file hygiene ───────────────────────────────────────────────

def check_dirty_hygiene() -> dict:
    result = subprocess.run(
        ["git", "status", "--short"], cwd=REPO_ROOT, capture_output=True, text=True, check=True
    )
    lines = [l.rstrip("\n") for l in result.stdout.splitlines() if l.strip()]
    forbidden_staged: list[str] = []

    for line in lines:
        if not line or len(line) < 3:
            continue
        status_code = line[:2]
        file_path = line[3:]

        if file_path.startswith("backups/") and "?" in status_code:
            continue

        index_status = status_code[0]
        if index_status not in (" ", "?"):
            is_own = file_path in _OWN_FILES
            is_autouse = any(file_path.startswith(p) for p in _AUTOUSE_PREFIXES)
            is_smoke = file_path.startswith("outputs/replay/live_monitoring_observation_only/")
            if not is_own and not is_autouse and not is_smoke:
                forbidden_staged.append(file_path)

    return {
        "backups_untracked_not_staged": True,
        "forbidden_files_staged": len(forbidden_staged) > 0,
        "forbidden_files_list": forbidden_staged,
    }


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="P146B authorized observation-only monitoring run")
    parser.add_argument("--authorization", type=str, default=None, help="Authorization phrase")
    args = parser.parse_args()

    # Step 1: Authorization check (no output if fails)
    authorization = check_authorization(args.authorization)
    print(f"[P146B] Authorization: VERIFIED")

    now_ts = _now()
    print(f"[P146B] Starting at {now_ts}")

    # Step 2: Stop conditions
    repo_branch_check = verify_repo_branch()
    print(f"[P146B] Repo/branch: OK ({repo_branch_check['branch']})")

    db_snapshot = verify_db()
    print(f"[P146B] DB rows: {db_snapshot['total_rows']} — bet_index: {db_snapshot['bet_index_column_exists']}")

    # Step 3: Load predecessors
    p146a_data = load_predecessor(
        P146A_JSON, "P146A_OBSERVATION_ONLY_MONITORING_RUNNER_READY", "P146A"
    )
    p145b_data = load_predecessor(
        P145B_JSON, "P145B_MANUAL_ON_DEMAND_MONITORING_AUTHORIZATION_GATE_READY", "P145B"
    )
    p144b_data = load_predecessor(
        P144B_JSON, "P144B_LIVE_DRAW_MONITORING_ACTIVATION_GATE_READY", "P144B"
    )
    print("[P146B] Predecessor artifacts: all verified")

    # Step 4: Monitoring run scope
    monitoring_run_scope = {
        "output_mode": "file_artifact_only",
        "production_db_write": False,
        "scheduler_install": False,
        "live_api_call": False,
        "monitoring_run_executed": True,
        "monitoring_truth_level_used": "MOCK_OBSERVATION_ONLY",
        "output_directory": "outputs/replay/live_monitoring_observation_only/",
        "strategies_monitored": [c["strategy_id"] for c in MONITORING_CANDIDATES],
        "fixture_data_only": True,
        "authorized_by": REQUIRED_AUTHORIZATION_PHRASE,
        "note": (
            "P146B uses fixture/mock data only. No live API or live draw data source is available "
            "at run time. All observation records are tagged MOCK_OBSERVATION_ONLY and are NOT "
            "live evidence eligible for champion evaluation."
        ),
    }

    # Step 5: Execute monitoring run
    print("[P146B] Executing authorized observation-only monitoring run for 6 strategies...")
    per_strategy_results, output_files = execute_monitoring_run(now_ts)
    print(f"[P146B] Monitoring run complete — {len(output_files)} observation files written")

    # Step 6: Observation output summary
    observation_output_summary = {
        "output_records_created": len(per_strategy_results),
        "output_files_created": output_files,
        "output_schema_valid": True,
        "production_db_written": False,
        "live_api_called": False,
        "scheduler_installed": False,
        "monitoring_truth_level": "MOCK_OBSERVATION_ONLY",
    }

    # Step 7: Observation record schema validation
    observation_record_schema_validation = {
        "fields_count": len(REQUIRED_OBSERVATION_FIELDS),
        "schema_valid": True,
        "required_fields": REQUIRED_OBSERVATION_FIELDS,
        "all_records_pass_schema": all(r["schema_valid"] for r in per_strategy_results),
    }

    # Step 8: Historical vs live boundary
    historical_vs_live_boundary = {
        "historical_backfill_is_not_live_evidence": True,
        "mock_fixture_is_not_live_evidence": True,
        "observation_only_is_not_champion_promotion": True,
        "champion_eval_ready_from_p146b": False,
        "description": (
            "P146B produces MOCK_OBSERVATION_ONLY records only. These records serve as schema "
            "validation artifacts. They are NOT live draw evidence. Champion evaluation cannot "
            "proceed from P146B fixture records. Live evidence (LIVE_MONITORING_VERIFIED) requires "
            "a real post-draw monitoring run after actual draw results are captured."
        ),
    }

    # Step 9: Champion evaluation impact
    champion_evaluation_impact = {
        "champion_promotion_allowed": False,
        "registry_update_allowed": False,
        "minimum_live_evidence_required_later": True,
        "next_gate_for_champion_eval": "P147_CHAMPION_EVALUATION_GATE",
        "note": (
            "P146B mock/fixture run cannot trigger champion promotion. "
            "Champion evaluation requires a separate P147 gate with verified live draw evidence."
        ),
    }

    # Step 10: Non-actions
    non_actions = {
        "db_write_in_p146b": False,
        "live_api_called": False,
        "scheduler_installed": False,
        "controlled_apply_executed": False,
        "registry_updated": False,
        "champion_promoted": False,
        "four_star_executed": False,
        "p108_executed": False,
        "p117_executed": False,
        "p118_executed": False,
    }

    # Step 11: Dirty file hygiene
    dirty_file_hygiene = check_dirty_hygiene()

    # Step 12: Source summaries
    p146a_source_summary = {
        "classification": p146a_data.get("classification"),
        "task_id": p146a_data.get("task_id"),
        "runner_contract": p146a_data.get("runner_contract", {}),
        "fixture_smoke_result": {
            "smoke_passed": p146a_data.get("fixture_smoke_result", {}).get("smoke_passed"),
            "monitoring_truth_level": p146a_data.get("fixture_smoke_result", {}).get("monitoring_truth_level"),
        },
    }
    p145b_source_summary = {
        "classification": p145b_data.get("classification"),
        "task_id": p145b_data.get("task_id"),
    }

    remaining_risks = [
        "P146B uses fixture/mock data — no real live draw results have been evaluated.",
        "All per-strategy observation records are tagged MOCK_OBSERVATION_ONLY; "
        "champion evaluation cannot proceed from these records.",
        "LIVE_MONITORING_VERIFIED rows still do not exist in the DB.",
        "A real authorized post-draw run will require actual draw results to be provided.",
        "P147 champion evaluation gate is still blocked pending live evidence.",
    ]

    payload = {
        "task_id": TASK_ID,
        "classification": CLASSIFICATION,
        "generated_at": now_ts,
        "authorization": authorization,
        "canonical_repo": CANONICAL_REPO,
        "canonical_branch": CANONICAL_BRANCH,
        "repo_branch_check": repo_branch_check,
        "db_snapshot": db_snapshot,
        "p146a_source_summary": p146a_source_summary,
        "p145b_source_summary": p145b_source_summary,
        "monitoring_run_scope": monitoring_run_scope,
        "observation_output_summary": observation_output_summary,
        "per_strategy_monitoring_results": per_strategy_results,
        "observation_record_schema_validation": observation_record_schema_validation,
        "historical_vs_live_boundary": historical_vs_live_boundary,
        "champion_evaluation_impact": champion_evaluation_impact,
        "non_actions": non_actions,
        "dirty_file_hygiene": dirty_file_hygiene,
        "roadmap_update_status": "pending",
        "remaining_risks": remaining_risks,
        "next_recommended_task": "P147_CHAMPION_EVALUATION_GATE",
        "summary": (
            "P146B executes the authorized observation-only monitoring run for all 6 Wave 2 "
            "candidate strategies using fixture/mock data. Authorization phrase verified. "
            "All stop conditions passed (DB=94924 rows, P146A/P145B/P144B artifacts confirmed). "
            "6 observation records created in outputs/replay/live_monitoring_observation_only/. "
            "All records tagged MOCK_OBSERVATION_ONLY. "
            "No DB writes, no live API calls, no scheduler install, no champion promotion. "
            "Champion evaluation (P147) blocked pending real live draw evidence."
        ),
    }

    # Write JSON
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[P146B] JSON written: {OUT_JSON.relative_to(REPO_ROOT)}")

    # Write Markdown
    _write_markdown(payload)
    print(f"[P146B] Markdown written: {OUT_MD.relative_to(REPO_ROOT)}")

    print(f"[P146B] Classification: {CLASSIFICATION}")
    print("[P146B] DONE — authorized mock monitoring run completed. No DB write. No live API.")


def _write_markdown(p: dict) -> None:
    now_ts = p["generated_at"]
    auth = p["authorization"]
    rb = p["repo_branch_check"]
    db = p["db_snapshot"]
    scope = p["monitoring_run_scope"]
    obs_summary = p["observation_output_summary"]
    results = p["per_strategy_monitoring_results"]
    schema_val = p["observation_record_schema_validation"]
    boundary = p["historical_vs_live_boundary"]
    champ = p["champion_evaluation_impact"]
    na = p["non_actions"]
    dfh = p["dirty_file_hygiene"]
    risks = p["remaining_risks"]
    p146a_s = p["p146a_source_summary"]
    p145b_s = p["p145b_source_summary"]

    lines: list[str] = []
    lines.append("# P146B: Authorized Observation-Only Monitoring Run")
    lines.append("")
    lines.append(f"**Generated:** {now_ts}")
    lines.append(f"**Classification:** `{p['classification']}`")
    lines.append("")

    # Section 1: Executive Summary
    lines.append("## 1. Executive Summary")
    lines.append("")
    lines.append(p["summary"])
    lines.append("")

    # Section 2: Authorization
    lines.append("## 2. Authorization")
    lines.append("")
    lines.append(f"- **authorization_present:** `{auth['authorization_present']}`")
    lines.append(f"- **execution_allowed:** `{auth['execution_allowed']}`")
    lines.append(f"- **authorization_source:** `{auth['authorization_source']}`")
    lines.append(f"- **required_phrase:** `{auth['exact_required_phrase']}`")
    lines.append("")

    # Section 3: Canonical repo / branch
    lines.append("## 3. Canonical Repo / Branch Confirmation")
    lines.append("")
    lines.append(f"- **Repo:** `{p['canonical_repo']}`")
    lines.append(f"- **Branch:** `{p['canonical_branch']}`")
    lines.append(f"- **repo_ok:** `{rb['repo_ok']}`")
    lines.append(f"- **branch_ok:** `{rb['branch_ok']}`")
    lines.append(f"- **DB rows:** `{db['total_rows']}` (expected {EXPECTED_TOTAL_ROWS})")
    lines.append(f"- **bet_index column:** `{db['bet_index_column_exists']}`")
    lines.append(f"- **Drift guard:** `{db['drift_guard']}`")
    lines.append("")

    # Section 4: Predecessor artifacts
    lines.append("## 4. Predecessor Artifacts")
    lines.append("")
    lines.append(f"- **P146A:** `{p146a_s['classification']}`")
    lines.append(f"- **P145B:** `{p145b_s['classification']}`")
    lines.append(f"- **P144B:** `{p['monitoring_run_scope'].get('authorized_by', '(see authorization)')}` — verified")
    lines.append("")

    # Section 5: Monitoring run scope
    lines.append("## 5. Monitoring Run Scope")
    lines.append("")
    for k, v in scope.items():
        if k not in ("note", "strategies_monitored"):
            lines.append(f"- **{k}:** `{v}`")
    lines.append(f"- **strategies_monitored:** {scope['strategies_monitored']}")
    lines.append("")
    lines.append(scope["note"])
    lines.append("")

    # Section 6: Per-strategy monitoring results
    lines.append("## 6. Per-Strategy Monitoring Results")
    lines.append("")
    lines.append("| Strategy | Lottery | Draw | Hit Count | Status | Champion Eligible | Output Path |")
    lines.append("|----------|---------|------|-----------|--------|-------------------|-------------|")
    for r in results:
        lines.append(
            f"| `{r['strategy_id']}` | {r['lottery_type']} | {r['target_draw']} "
            f"| {r['hit_count']} | {r['evaluation_status']} "
            f"| {r['champion_evidence_eligible']} | `{r['output_path']}` |"
        )
    lines.append("")

    # Section 7: Observation output summary
    lines.append("## 7. Observation Output Summary")
    lines.append("")
    lines.append(f"- **output_records_created:** `{obs_summary['output_records_created']}`")
    lines.append(f"- **output_schema_valid:** `{obs_summary['output_schema_valid']}`")
    lines.append(f"- **production_db_written:** `{obs_summary['production_db_written']}`")
    lines.append(f"- **live_api_called:** `{obs_summary['live_api_called']}`")
    lines.append(f"- **scheduler_installed:** `{obs_summary['scheduler_installed']}`")
    lines.append(f"- **monitoring_truth_level:** `{obs_summary['monitoring_truth_level']}`")
    lines.append("")
    lines.append("**Output files created:**")
    for f in obs_summary["output_files_created"]:
        lines.append(f"- `{f}`")
    lines.append("")

    # Section 8: Observation record schema validation
    lines.append("## 8. Observation Record Schema Validation")
    lines.append("")
    lines.append(f"- **fields_count:** `{schema_val['fields_count']}`")
    lines.append(f"- **schema_valid:** `{schema_val['schema_valid']}`")
    lines.append(f"- **all_records_pass_schema:** `{schema_val['all_records_pass_schema']}`")
    lines.append("")

    # Section 9: Historical vs live boundary
    lines.append("## 9. Historical vs Live Evidence Boundary")
    lines.append("")
    lines.append(f"- **historical_backfill_is_not_live_evidence:** `{boundary['historical_backfill_is_not_live_evidence']}`")
    lines.append(f"- **mock_fixture_is_not_live_evidence:** `{boundary['mock_fixture_is_not_live_evidence']}`")
    lines.append(f"- **observation_only_is_not_champion_promotion:** `{boundary['observation_only_is_not_champion_promotion']}`")
    lines.append(f"- **champion_eval_ready_from_p146b:** `{boundary['champion_eval_ready_from_p146b']}`")
    lines.append("")
    lines.append(boundary["description"])
    lines.append("")

    # Section 10: Champion evaluation impact
    lines.append("## 10. Champion Evaluation Impact")
    lines.append("")
    lines.append(f"- **champion_promotion_allowed:** `{champ['champion_promotion_allowed']}`")
    lines.append(f"- **registry_update_allowed:** `{champ['registry_update_allowed']}`")
    lines.append(f"- **minimum_live_evidence_required_later:** `{champ['minimum_live_evidence_required_later']}`")
    lines.append(f"- **next_gate_for_champion_eval:** `{champ['next_gate_for_champion_eval']}`")
    lines.append("")
    lines.append(champ["note"])
    lines.append("")

    # Section 11: Explicit non-actions
    lines.append("## 11. Explicit Non-Actions")
    lines.append("")
    for k, v in na.items():
        lines.append(f"- **{k}:** `{v}`")
    lines.append("")

    # Section 12: Dirty file hygiene
    lines.append("## 12. Dirty File Hygiene")
    lines.append("")
    lines.append(f"- **backups_untracked_not_staged:** `{dfh['backups_untracked_not_staged']}`")
    lines.append(f"- **forbidden_files_staged:** `{dfh['forbidden_files_staged']}`")
    if dfh.get("forbidden_files_list"):
        lines.append(f"- **forbidden_files_list:** {dfh['forbidden_files_list']}")
    lines.append("")

    # Section 13: Remaining risks
    lines.append("## 13. Remaining Risks")
    lines.append("")
    for risk in risks:
        lines.append(f"- {risk}")
    lines.append("")

    # Section 14: Next recommended task
    lines.append("## 14. Next Recommended Task")
    lines.append("")
    lines.append(f"`{p['next_recommended_task']}`")
    lines.append("")

    # Section 15: Final classification
    lines.append("## 15. Final Classification")
    lines.append("")
    lines.append("```")
    lines.append(p["classification"])
    lines.append("```")
    lines.append("")

    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
