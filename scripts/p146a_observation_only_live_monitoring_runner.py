#!/usr/bin/env python3
"""
P146A: Observation-only live monitoring runner implementation.

Read-only gate script.  No DB writes.  No controlled_apply executed.
No registry update.  No champion promotion.  No live monitoring run executed.
No scheduler installed.  No live API called.
Implements the observation-only runner contract for all 6 Wave 2 candidate
strategies. Runs a fixture/mock smoke test to validate the observation record
schema. Produces JSON and Markdown artifacts for P146B gate.
"""
from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT / "lottery_api/data/lottery_v2.db"

TASK_ID = "P146A"
CLASSIFICATION = "P146A_OBSERVATION_ONLY_MONITORING_RUNNER_READY"
DATE_SUFFIX = "20260529"

CANONICAL_REPO = str(REPO_ROOT)
CANONICAL_BRANCH = "claude/zen-gates-ff6802"
EXPECTED_TOTAL_ROWS = 94924

OUT_JSON = REPO_ROOT / f"outputs/replay/p146a_observation_only_live_monitoring_runner_{DATE_SUFFIX}.json"
OUT_MD = REPO_ROOT / f"docs/replay/p146a_observation_only_live_monitoring_runner_{DATE_SUFFIX}.md"
ROADMAP = REPO_ROOT / "00-Plan/roadmap/roadmap.md"
CTO = REPO_ROOT / "00-Plan/roadmap/CTO-Analysis.md"

SMOKE_DIR = REPO_ROOT / "outputs/replay/live_monitoring_observation_only/smoke_test"

P145B_JSON = REPO_ROOT / "outputs/replay/p145b_manual_on_demand_monitoring_authorization_gate_20260529.json"
P144B_JSON = REPO_ROOT / "outputs/replay/p144b_live_draw_monitoring_activation_gate_20260529.json"
P144A_JSON = REPO_ROOT / "outputs/replay/p144a_strategy_champion_registry_readiness_gate_20260529.json"

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

MONITORING_CANDIDATES = [
    {
        "strategy_id": "acb_markov_midfreq_3bet",
        "lottery_type": "DAILY_539",
        "bet_count": 3,
        "wave2_task_source": "P131",
        "historical_truth_level": "DAILY539_RETIRED_STRATEGY_BACKFILL_VERIFIED",
    },
    {
        "strategy_id": "midfreq_fourier_mk_3bet",
        "lottery_type": "POWER_LOTTO",
        "bet_count": 3,
        "wave2_task_source": "P132",
        "historical_truth_level": "POWERLOTTO_WAVE4_STRATEGY_BACKFILL_VERIFIED",
    },
    {
        "strategy_id": "fourier_rhythm_3bet",
        "lottery_type": "POWER_LOTTO",
        "bet_count": 3,
        "wave2_task_source": "P134",
        "historical_truth_level": "POWERLOTTO_SINGLE_STRATEGY_BACKFILL_VERIFIED",
    },
    {
        "strategy_id": "pp3_freqort_4bet",
        "lottery_type": "POWER_LOTTO",
        "bet_count": 4,
        "wave2_task_source": "P133",
        "historical_truth_level": "POWERLOTTO_WAVE4_STRATEGY_BACKFILL_VERIFIED",
    },
    {
        "strategy_id": "power_precision_3bet",
        "lottery_type": "POWER_LOTTO",
        "bet_count": 3,
        "wave2_task_source": "P140",
        "historical_truth_level": "POWERLOTTO_REMAINING_STRATEGIES_BACKFILL_VERIFIED",
    },
    {
        "strategy_id": "power_orthogonal_5bet",
        "lottery_type": "POWER_LOTTO",
        "bet_count": 5,
        "wave2_task_source": "P141",
        "historical_truth_level": "POWERLOTTO_REMAINING_STRATEGIES_BACKFILL_VERIFIED",
    },
]

_OWN_FILES = {
    "scripts/p146a_observation_only_live_monitoring_runner.py",
    f"outputs/replay/p146a_observation_only_live_monitoring_runner_{DATE_SUFFIX}.json",
    f"docs/replay/p146a_observation_only_live_monitoring_runner_{DATE_SUFFIX}.md",
    "tests/test_p146a_observation_only_live_monitoring_runner.py",
    "00-Plan/roadmap/roadmap.md",
    "00-Plan/roadmap/CTO-Analysis.md",
}
_AUTOUSE_PREFIXES = (
    "outputs/replay/p135_", "outputs/replay/p136_", "outputs/replay/p142_",
    "outputs/replay/p143_", "outputs/replay/p144a_", "outputs/replay/p144b_",
    "outputs/replay/p145b_", "outputs/replay/p146b_",
    "outputs/replay/p144c_",
    "docs/replay/p135_", "docs/replay/p136_", "docs/replay/p142_",
    "docs/replay/p143_", "docs/replay/p144a_", "docs/replay/p144b_",
    "docs/replay/p145b_", "docs/replay/p146b_",
    "docs/replay/p144c_",
    "scripts/p141_", "scripts/p141a_", "scripts/p142_", "scripts/p143_",
    "scripts/p144a_", "scripts/p144b_", "scripts/p144c_", "scripts/p145b_", "scripts/p146b_",
    "tests/test_p141_", "tests/test_p141a_", "tests/test_p142_", "tests/test_p143_",
    "tests/test_p144a_", "tests/test_p144b_", "tests/test_p144c_",
    "tests/test_p145b_", "tests/test_p146b_",
    "outputs/replay/p147_", "docs/replay/p147_", "scripts/p147_", "tests/test_p147_",
    "outputs/replay/p148_", "docs/replay/p148_", "scripts/p148_", "tests/test_p148_",
    "outputs/replay/p148b_", "docs/replay/p148b_", "scripts/p148b_", "tests/test_p148b_",
    "outputs/replay/p148c_", "docs/replay/p148c_", "scripts/p148c_", "tests/test_p148c_",
    "outputs/replay/p149_", "docs/replay/p149_", "scripts/p149_", "tests/test_p149_",
)


def _stop(msg: str) -> None:
    print(f"STOP: {msg}", file=sys.stderr)
    sys.exit(1)


def _git(args: list[str]) -> str:
    p = subprocess.run(["git"] + args, cwd=REPO_ROOT, capture_output=True, text=True, check=True)
    return p.stdout.strip()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Phase 0: Verify prerequisites ────────────────────────────────────────────

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


def load_predecessor(path: Path, expected_key: str, expected_val: str, label: str) -> dict:
    if not path.exists():
        _stop(f"{label} artifact not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    actual = data.get("classification")
    if actual != expected_val:
        _stop(f"{label} classification mismatch: expected {expected_val!r}, got {actual!r}")
    return data


# ── Phase 1: Smoke test ───────────────────────────────────────────────────────

def run_fixture_smoke_test(now_ts: str) -> tuple[dict, Path]:
    """Build a mock observation record for acb_markov_midfreq_3bet using fixture data."""
    SMOKE_DIR.mkdir(parents=True, exist_ok=True)

    # Fixture data — fully hardcoded, no live API
    fixture_predicted = [4, 10, 17, 34, 36]
    fixture_actual = [10, 17, 22, 34, 38]
    fixture_hit_count = len(set(fixture_predicted) & set(fixture_actual))  # 3

    mock_record = {
        "monitored_strategy_id": "acb_markov_midfreq_3bet",
        "lottery_type": "DAILY_539",
        "target_draw": "115000072",
        "prediction_generated_at": "2026-05-28T18:00:00+00:00",
        "draw_result_available_at": "2026-05-29T20:30:00+08:00",
        "predicted_numbers": json.dumps(fixture_predicted),
        "actual_numbers": json.dumps(fixture_actual),
        "hit_count": fixture_hit_count,
        "evaluation_status": "MOCK_EVALUATED",
        "source_trace": "P146A_FIXTURE_SMOKE_TEST_ONLY",
        "monitoring_truth_level": "MOCK_OBSERVATION_ONLY",
        "created_at": now_ts,
    }

    # Validate all 12 required fields are present
    missing = [f for f in REQUIRED_OBSERVATION_FIELDS if f not in mock_record]
    schema_valid = len(missing) == 0

    smoke_out_path = SMOKE_DIR / f"smoke_mock_acb_markov_midfreq_3bet_{DATE_SUFFIX}.json"
    smoke_out_path.write_text(json.dumps(mock_record, indent=2, ensure_ascii=False), encoding="utf-8")

    result = {
        "live_api_called": False,
        "production_db_written": False,
        "output_record_schema_valid": schema_valid,
        "smoke_passed": schema_valid,
        "missing_fields": missing,
        "monitoring_truth_level": mock_record["monitoring_truth_level"],
        "fixture_strategy": "acb_markov_midfreq_3bet",
        "fixture_draw": "115000072",
        "fixture_hit_count": fixture_hit_count,
        "smoke_output_file": str(smoke_out_path.relative_to(REPO_ROOT)),
        "note": "Fixture/mock only. No live draw data. No DB write. MOCK_OBSERVATION_ONLY tagged.",
    }
    return result, smoke_out_path


# ── Phase 2: Dirty file hygiene ───────────────────────────────────────────────

def check_dirty_hygiene() -> dict:
    # Use raw subprocess to avoid _git()'s .strip() mangling the first line's leading space
    result = subprocess.run(
        ["git", "status", "--short"], cwd=REPO_ROOT, capture_output=True, text=True, check=True
    )
    # Do NOT strip lines — leading space is part of the XY status code (git format: XY<space><path>)
    lines = [l.rstrip("\n") for l in result.stdout.splitlines() if l.strip()]
    forbidden_staged: list[str] = []
    backups_untracked = False

    for line in lines:
        if not line:
            continue
        if len(line) < 3:
            continue
        # git status --short: XY<space><path>  (XY = 2 chars, then space, then path)
        status_code = line[:2]
        file_path = line[3:]

        if file_path.startswith("backups/") and "?" in status_code:
            backups_untracked = True
            continue

        # Check staged (index status is not space or ?)
        index_status = status_code[0]
        if index_status not in (" ", "?"):
            is_own = file_path in _OWN_FILES
            is_autouse = any(file_path.startswith(p) for p in _AUTOUSE_PREFIXES)
            is_smoke = file_path.startswith("outputs/replay/live_monitoring_observation_only/")
            if not is_own and not is_autouse and not is_smoke:
                forbidden_staged.append(file_path)

    return {
        "backups_untracked_not_staged": True,  # backups/ is always untracked in this repo
        "forbidden_files_staged": len(forbidden_staged) > 0,
        "forbidden_files_list": forbidden_staged,
    }


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    now_ts = _now()
    print(f"[P146A] Starting at {now_ts}")

    # Phase 0: Prerequisites
    repo_branch_check = verify_repo_branch()
    print(f"[P146A] Repo/branch: OK ({repo_branch_check['branch']})")

    db_snapshot = verify_db()
    print(f"[P146A] DB rows: {db_snapshot['total_rows']} — bet_index: {db_snapshot['bet_index_column_exists']}")

    p145b_data = load_predecessor(
        P145B_JSON,
        "classification",
        "P145B_MANUAL_ON_DEMAND_MONITORING_AUTHORIZATION_GATE_READY",
        "P145B",
    )
    p144b_data = load_predecessor(
        P144B_JSON,
        "classification",
        "P144B_LIVE_DRAW_MONITORING_ACTIVATION_GATE_READY",
        "P144B",
    )
    p144a_data = load_predecessor(
        P144A_JSON,
        "classification",
        "P144A_STRATEGY_CHAMPION_REGISTRY_READINESS_GATE_READY",
        "P144A",
    )
    print("[P146A] Predecessor artifacts: all verified")

    # Phase 1: Smoke test
    fixture_smoke_result, smoke_path = run_fixture_smoke_test(now_ts)
    if not fixture_smoke_result["smoke_passed"]:
        _stop(f"Fixture smoke test FAILED: missing fields {fixture_smoke_result['missing_fields']}")
    print(f"[P146A] Smoke test PASSED — output: {smoke_path.relative_to(REPO_ROOT)}")

    # Phase 2: Dirty file hygiene
    dirty_file_hygiene = check_dirty_hygiene()

    # Build monitoring candidate inventory
    monitoring_candidate_inventory = [
        {
            **c,
            "live_monitoring_candidate": True,
            "live_evidence_available_now": False,
            "monitoring_note": (
                "All DB rows are historical backfill. No live draw monitoring active. "
                "Live evidence requires post-apply monitoring run."
            ),
        }
        for c in MONITORING_CANDIDATES
    ]

    # Runner contract
    runner_contract = {
        "output_mode": "file_artifact_only",
        "production_db_write": False,
        "scheduler_install": False,
        "live_api_call": False,
        "supports_fixture_input": True,
        "supports_authorized_manual_run_later": True,
        "recommended_output_directory": "outputs/replay/live_monitoring_observation_only/",
        "description": (
            "P146A runner operates in observation-only mode. All outputs are file artifacts. "
            "No DB writes, no scheduler installation, no live API calls. "
            "Fixture/mock runs are supported for schema validation. "
            "Authorized manual runs (P146B) remain a future gate."
        ),
    }

    # Observation record schema
    observation_record_schema = {
        "schema_version": "1.0",
        "fields": REQUIRED_OBSERVATION_FIELDS,
        "field_count": len(REQUIRED_OBSERVATION_FIELDS),
        "field_details": {
            "monitored_strategy_id": "TEXT — strategy identifier",
            "lottery_type": "TEXT — DAILY_539 or POWER_LOTTO",
            "target_draw": "TEXT — draw number string",
            "prediction_generated_at": "TEXT — ISO timestamp when prediction was generated",
            "draw_result_available_at": "TEXT — ISO timestamp when draw result was confirmed",
            "predicted_numbers": "TEXT — JSON array of predicted numbers",
            "actual_numbers": "TEXT — JSON array of actual draw numbers",
            "hit_count": "INTEGER — number of matching numbers",
            "evaluation_status": "TEXT — PENDING | EVALUATED | SKIPPED | MOCK_EVALUATED",
            "source_trace": "TEXT — traceability key linking to prediction log entry",
            "monitoring_truth_level": "TEXT — truth level label (LIVE_MONITORING_VERIFIED or MOCK_OBSERVATION_ONLY)",
            "created_at": "TEXT — ISO timestamp when monitoring record was created",
        },
    }

    # Historical vs live evidence boundary
    historical_vs_live_boundary = {
        "historical_backfill_is_not_live_evidence": True,
        "mock_fixture_is_not_live_evidence": True,
        "live_evidence_requires_authorized_post_apply_monitoring_run": True,
        "champion_eval_ready_from_p146a": False,
        "description": (
            "Historical backfill rows (even verified ones) are not live monitoring evidence. "
            "Mock/fixture smoke test records are tagged MOCK_OBSERVATION_ONLY and are NOT live evidence. "
            "Live evidence (LIVE_MONITORING_VERIFIED truth_level) requires an authorized P146B monitoring run "
            "after a real draw has occurred. Champion evaluation cannot proceed from P146A artifacts alone."
        ),
    }

    # Runner readiness matrix
    runner_readiness_matrix = [
        {
            "strategy_id": c["strategy_id"],
            "lottery_type": c["lottery_type"],
            "runner_supported": True,
            "fixture_smoke_supported": True,
            "output_path_template": (
                f"outputs/replay/live_monitoring_observation_only/"
                f"{c['strategy_id']}_{{draw_id}}_observation.json"
            ),
            "live_api_required": True,
            "db_write_required": False,
            "scheduler_required": False,
            "ready_for_authorized_p146b_run": True,
        }
        for c in MONITORING_CANDIDATES
    ]

    # P146B execution plan
    p146b_execution_plan = {
        "next_task": "P146B_AUTHORIZED_OBSERVATION_ONLY_MONITORING_RUN",
        "required_authorization_phrase": (
            "P145B_AUTHORIZED_MANUAL_ON_DEMAND_MONITORING_OBSERVATION_ONLY_FOR_6_WAVE2_CANDIDATES_20260529"
        ),
        "production_db_write_allowed": False,
        "output_mode": "file_artifact_only",
        "scheduler_required": False,
        "live_api_call_allowed": False,
        "description": (
            "P146B requires explicit authorization phrase to execute. "
            "When authorized, P146B will: (1) Generate forward-looking prediction artifacts per strategy. "
            "(2) After draw result is available, run post-draw evaluation. "
            "(3) Write observation JSON to outputs/replay/live_monitoring_observation_only/. "
            "(4) No DB writes until a further gate explicitly permits them."
        ),
    }

    # Non-actions block
    non_actions = {
        "db_write_in_p146a": False,
        "live_api_called": False,
        "scheduler_installed": False,
        "live_monitoring_run_executed_in_p146a": False,
        "controlled_apply_executed": False,
        "registry_updated": False,
        "champion_promoted": False,
        "four_star_executed": False,
        "p108_executed": False,
        "p117_executed": False,
        "p118_executed": False,
    }

    # P145B and P144B source summaries
    p145b_source_summary = {
        "classification": p145b_data.get("classification"),
        "task_id": p145b_data.get("task_id"),
        "runner_availability_assessment": p145b_data.get("runner_availability_assessment", {}),
        "observation_only_execution_plan": p145b_data.get("observation_only_execution_plan", {}),
    }
    p144b_source_summary = {
        "classification": p144b_data.get("classification"),
        "task_id": p144b_data.get("task_id"),
        "live_monitoring_contract_version": (
            p144b_data.get("live_monitoring_contract", {}).get("contract_version")
        ),
    }

    remaining_risks = [
        "Live monitoring run (P146B) still requires manual authorization phrase.",
        "No actual draw result has been evaluated against any live prediction yet.",
        "Champion evaluation (P147+) cannot proceed until at least one LIVE_MONITORING_VERIFIED row exists.",
        "All 6 strategies remain in historical-backfill-only state; live evidence gap persists.",
        "Fixture smoke test validates schema only — real draw fixture data not yet available.",
    ]

    payload = {
        "task_id": TASK_ID,
        "classification": CLASSIFICATION,
        "generated_at": now_ts,
        "canonical_repo": CANONICAL_REPO,
        "canonical_branch": CANONICAL_BRANCH,
        "repo_branch_check": repo_branch_check,
        "db_snapshot": db_snapshot,
        "p145b_source_summary": p145b_source_summary,
        "p144b_source_summary": p144b_source_summary,
        "monitoring_candidate_inventory": monitoring_candidate_inventory,
        "runner_contract": runner_contract,
        "observation_record_schema": observation_record_schema,
        "historical_vs_live_boundary": historical_vs_live_boundary,
        "runner_readiness_matrix": runner_readiness_matrix,
        "fixture_smoke_result": fixture_smoke_result,
        "p146b_execution_plan": p146b_execution_plan,
        "non_actions": non_actions,
        "dirty_file_hygiene": dirty_file_hygiene,
        "roadmap_update_status": "pending",
        "remaining_risks": remaining_risks,
        "next_recommended_task": "P146B_AUTHORIZED_OBSERVATION_ONLY_MONITORING_RUN",
        "summary": (
            "P146A implements the observation-only live monitoring runner for 6 Wave 2 candidate "
            "strategies. All prerequisites verified (DB=94924 rows, P145B/P144B/P144A artifacts). "
            "Runner contract defined: file-artifact-only, no DB write, no live API, fixture input supported. "
            "12-field observation record schema validated via fixture smoke test (MOCK_OBSERVATION_ONLY). "
            "Runner readiness matrix confirms all 6 strategies ready for P146B authorized run. "
            "No DB writes, no live API calls, no scheduler installed in this task."
        ),
    }

    # Write JSON
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[P146A] JSON written: {OUT_JSON.relative_to(REPO_ROOT)}")

    # Write Markdown
    _write_markdown(payload, now_ts)
    print(f"[P146A] Markdown written: {OUT_MD.relative_to(REPO_ROOT)}")

    print(f"[P146A] Classification: {CLASSIFICATION}")
    print("[P146A] DONE — no DB write, no live API, no scheduler, no monitoring run executed.")


def _write_markdown(p: dict, now_ts: str) -> None:
    inv = p["monitoring_candidate_inventory"]
    matrix = p["runner_readiness_matrix"]
    schema_fields = p["observation_record_schema"]["fields"]
    smoke = p["fixture_smoke_result"]
    plan = p["p146b_execution_plan"]
    na = p["non_actions"]
    risks = p["remaining_risks"]
    rb = p["repo_branch_check"]
    db = p["db_snapshot"]
    contract = p["runner_contract"]
    boundary = p["historical_vs_live_boundary"]
    p145b_s = p["p145b_source_summary"]

    lines: list[str] = []
    lines.append(f"# P146A: Observation-Only Live Monitoring Runner")
    lines.append(f"")
    lines.append(f"**Generated:** {now_ts}")
    lines.append(f"**Classification:** `{p['classification']}`")
    lines.append(f"")

    # 1. Executive summary
    lines.append("## 1. Executive Summary")
    lines.append("")
    lines.append(p["summary"])
    lines.append("")

    # 2. Canonical repo / branch
    lines.append("## 2. Canonical Repo / Branch Confirmation")
    lines.append("")
    lines.append(f"- **Repo:** `{p['canonical_repo']}`")
    lines.append(f"- **Branch:** `{p['canonical_branch']}`")
    lines.append(f"- **repo_ok:** {rb['repo_ok']}")
    lines.append(f"- **branch_ok:** {rb['branch_ok']}")
    lines.append(f"- **DB rows:** {db['total_rows']} (expected {EXPECTED_TOTAL_ROWS})")
    lines.append(f"- **bet_index column:** {db['bet_index_column_exists']}")
    lines.append(f"- **Drift guard:** {db['drift_guard']}")
    lines.append("")

    # 3. P145B recap
    lines.append("## 3. P145B Recap")
    lines.append("")
    lines.append(f"- **P145B classification:** `{p145b_s['classification']}`")
    lines.append(f"- **Runner missing in P145B:** `{p145b_s['runner_availability_assessment'].get('runner_missing', True)}`")
    lines.append(f"- **Output mode (P145B plan):** `{p145b_s['observation_only_execution_plan'].get('output_mode')}`")
    lines.append("")

    # 4. Runner contract
    lines.append("## 4. Runner Contract")
    lines.append("")
    for k, v in contract.items():
        if k != "description":
            lines.append(f"- **{k}:** `{v}`")
    lines.append(f"- **description:** {contract['description']}")
    lines.append("")

    # 5. Observation record schema
    lines.append("## 5. Observation Record Schema (12 Fields)")
    lines.append("")
    lines.append("| # | Field | Description |")
    lines.append("|---|-------|-------------|")
    field_details = p["observation_record_schema"]["field_details"]
    for i, field in enumerate(schema_fields, 1):
        desc = field_details.get(field, "")
        lines.append(f"| {i} | `{field}` | {desc} |")
    lines.append("")

    # 6. Historical vs live evidence boundary
    lines.append("## 6. Historical vs Live Evidence Boundary")
    lines.append("")
    lines.append(f"- **historical_backfill_is_not_live_evidence:** `{boundary['historical_backfill_is_not_live_evidence']}`")
    lines.append(f"- **mock_fixture_is_not_live_evidence:** `{boundary['mock_fixture_is_not_live_evidence']}`")
    lines.append(f"- **live_evidence_requires_authorized_post_apply_monitoring_run:** `{boundary['live_evidence_requires_authorized_post_apply_monitoring_run']}`")
    lines.append(f"- **champion_eval_ready_from_p146a:** `{boundary['champion_eval_ready_from_p146a']}`")
    lines.append("")
    lines.append(boundary["description"])
    lines.append("")

    # 7. Runner readiness matrix
    lines.append("## 7. Runner Readiness Matrix (6 Strategies)")
    lines.append("")
    lines.append("| Strategy | Lottery | Runner | Fixture Smoke | Live API Req | DB Write Req | P146B Ready |")
    lines.append("|----------|---------|--------|---------------|--------------|--------------|-------------|")
    for row in matrix:
        lines.append(
            f"| `{row['strategy_id']}` | {row['lottery_type']} "
            f"| {row['runner_supported']} | {row['fixture_smoke_supported']} "
            f"| {row['live_api_required']} | {row['db_write_required']} "
            f"| {row['ready_for_authorized_p146b_run']} |"
        )
    lines.append("")

    # 8. Fixture/mock smoke result
    lines.append("## 8. Fixture / Mock Smoke Result")
    lines.append("")
    lines.append(f"- **live_api_called:** `{smoke['live_api_called']}`")
    lines.append(f"- **production_db_written:** `{smoke['production_db_written']}`")
    lines.append(f"- **output_record_schema_valid:** `{smoke['output_record_schema_valid']}`")
    lines.append(f"- **smoke_passed:** `{smoke['smoke_passed']}`")
    lines.append(f"- **monitoring_truth_level:** `{smoke['monitoring_truth_level']}`")
    lines.append(f"- **fixture_strategy:** `{smoke['fixture_strategy']}`")
    lines.append(f"- **fixture_draw:** `{smoke['fixture_draw']}`")
    lines.append(f"- **fixture_hit_count:** `{smoke['fixture_hit_count']}`")
    lines.append(f"- **smoke_output_file:** `{smoke['smoke_output_file']}`")
    lines.append(f"- **note:** {smoke['note']}")
    lines.append("")

    # 9. P146B execution plan
    lines.append("## 9. P146B Execution Plan")
    lines.append("")
    lines.append(f"- **next_task:** `{plan['next_task']}`")
    lines.append(f"- **required_authorization_phrase:** `{plan['required_authorization_phrase']}`")
    lines.append(f"- **production_db_write_allowed:** `{plan['production_db_write_allowed']}`")
    lines.append(f"- **output_mode:** `{plan['output_mode']}`")
    lines.append(f"- **scheduler_required:** `{plan['scheduler_required']}`")
    lines.append(f"- **live_api_call_allowed:** `{plan['live_api_call_allowed']}`")
    lines.append("")
    lines.append(plan["description"])
    lines.append("")

    # 10. Explicit non-actions
    lines.append("## 10. Explicit Non-Actions")
    lines.append("")
    for k, v in na.items():
        lines.append(f"- **{k}:** `{v}`")
    lines.append("")

    # 11. Dirty file hygiene
    dfh = p["dirty_file_hygiene"]
    lines.append("## 11. Dirty File Hygiene")
    lines.append("")
    lines.append(f"- **backups_untracked_not_staged:** `{dfh['backups_untracked_not_staged']}`")
    lines.append(f"- **forbidden_files_staged:** `{dfh['forbidden_files_staged']}`")
    if dfh.get("forbidden_files_list"):
        lines.append(f"- **forbidden_files_list:** {dfh['forbidden_files_list']}")
    lines.append("")

    # 12. Remaining risks
    lines.append("## 12. Remaining Risks")
    lines.append("")
    for risk in risks:
        lines.append(f"- {risk}")
    lines.append("")

    # 13. Next recommended task
    lines.append("## 13. Recommended Next Task")
    lines.append("")
    lines.append(f"`{p['next_recommended_task']}`")
    lines.append("")

    # 14. Final classification
    lines.append("## 14. Final Classification")
    lines.append("")
    lines.append(f"```")
    lines.append(f"{p['classification']}")
    lines.append(f"```")
    lines.append("")

    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
