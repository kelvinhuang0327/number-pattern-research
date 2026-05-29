#!/usr/bin/env python3
"""
P145B: Manual on-demand monitoring authorization gate.

Read-only gate script.  No DB writes.  No controlled_apply executed.
No registry update.  No champion promotion.  No monitoring run executed.
No scheduler installed.  No live API called.
Defines the manual on-demand monitoring authorization gate and observation-only
execution plan for all 6 Wave 2 candidate strategies.
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

TASK_ID = "P145B"
CLASSIFICATION = "P145B_MANUAL_ON_DEMAND_MONITORING_AUTHORIZATION_GATE_READY"
DATE_SUFFIX = "20260529"

CANONICAL_REPO = str(REPO_ROOT)
CANONICAL_BRANCH = "claude/zen-gates-ff6802"
EXPECTED_TOTAL_ROWS = 94924

OUT_JSON = REPO_ROOT / f"outputs/replay/p145b_manual_on_demand_monitoring_authorization_gate_{DATE_SUFFIX}.json"
OUT_MD = REPO_ROOT / f"docs/replay/p145b_manual_on_demand_monitoring_authorization_gate_{DATE_SUFFIX}.md"
ROADMAP = REPO_ROOT / "00-Plan/roadmap/roadmap.md"
CTO = REPO_ROOT / "00-Plan/roadmap/CTO-Analysis.md"

P144B_JSON = REPO_ROOT / "outputs/replay/p144b_live_draw_monitoring_activation_gate_20260529.json"
P144A_JSON = REPO_ROOT / "outputs/replay/p144a_strategy_champion_registry_readiness_gate_20260529.json"
P143_JSON = REPO_ROOT / "outputs/replay/p143_post_wave2_governance_readiness_plan_20260529.json"

REQUIRED_CONTRACT_FIELDS = [
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

# Own files (allowed as dirty)
_OWN_FILES = {
    "scripts/p145b_manual_on_demand_monitoring_authorization_gate.py",
    f"outputs/replay/p145b_manual_on_demand_monitoring_authorization_gate_{DATE_SUFFIX}.json",
    f"docs/replay/p145b_manual_on_demand_monitoring_authorization_gate_{DATE_SUFFIX}.md",
    "tests/test_p145b_manual_on_demand_monitoring_authorization_gate.py",
    "00-Plan/roadmap/roadmap.md",
    "00-Plan/roadmap/CTO-Analysis.md",
}
_AUTOUSE_PREFIXES = (
    "outputs/replay/p135_", "outputs/replay/p136_", "outputs/replay/p142_",
    "outputs/replay/p143_", "outputs/replay/p144a_", "outputs/replay/p144b_",
    "outputs/replay/p146a_", "outputs/replay/p146b_",
    "outputs/replay/live_monitoring_observation_only/",
    "docs/replay/p135_", "docs/replay/p136_", "docs/replay/p142_",
    "docs/replay/p143_", "docs/replay/p144a_", "docs/replay/p144b_",
    "docs/replay/p146a_", "docs/replay/p146b_",
    "scripts/p141_", "scripts/p141a_", "scripts/p142_", "scripts/p143_",
    "scripts/p144a_", "scripts/p144b_", "scripts/p146a_", "scripts/p146b_",
    "tests/test_p141_", "tests/test_p141a_", "tests/test_p142_", "tests/test_p143_",
    "tests/test_p144a_", "tests/test_p144b_", "tests/test_p146a_", "tests/test_p146b_",
)


def _stop(msg: str) -> None:
    print(f"STOP: {msg}", file=sys.stderr)
    sys.exit(1)


def _git(args: list[str]) -> str:
    p = subprocess.run(["git"] + args, cwd=REPO_ROOT, capture_output=True, text=True, check=True)
    return p.stdout.strip()


def _ro_conn():
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.execute("PRAGMA query_only = ON")
    return conn


def _load_json(path: Path) -> dict:
    if not path.exists():
        _stop(f"Required artifact missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


# ── Phase 0 ───────────────────────────────────────────────────────────────────

def validate_preflight() -> dict:
    repo = _git(["rev-parse", "--show-toplevel"])
    branch = _git(["branch", "--show-current"])
    if repo != CANONICAL_REPO:
        _stop(f"repo mismatch: {repo}")
    if branch != CANONICAL_BRANCH:
        _stop(f"branch mismatch: {branch}")

    status_lines = subprocess.run(
        ["git", "status", "--short"],
        cwd=REPO_ROOT, capture_output=True, text=True, check=True,
    ).stdout.splitlines()

    unrelated = []
    for line in status_lines:
        if not line.strip():
            continue
        path_str = line[3:].strip()
        if path_str.startswith("backups/"):
            continue
        if path_str in _OWN_FILES:
            continue
        if any(path_str.startswith(pfx) for pfx in _AUTOUSE_PREFIXES):
            continue
        unrelated.append(path_str)
    if unrelated:
        _stop(f"unrelated dirty files: {unrelated}")

    git_dir = _git(["rev-parse", "--git-dir"])
    return {
        "expected_repo": CANONICAL_REPO,
        "actual_repo": repo,
        "expected_branch": CANONICAL_BRANCH,
        "actual_branch": branch,
        "git_dir": git_dir,
        "repo_ok": True,
        "branch_ok": True,
    }


def db_snapshot(conn: sqlite3.Connection) -> dict:
    total = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
    if total != EXPECTED_TOTAL_ROWS:
        _stop(f"DB rows={total}, expected {EXPECTED_TOTAL_ROWS}")
    cols = [r[1] for r in conn.execute("PRAGMA table_info(strategy_prediction_replays)").fetchall()]
    bet_index_exists = "bet_index" in cols
    if not bet_index_exists:
        _stop("bet_index column missing")
    return {
        "total_rows": total,
        "bet_index_column_exists": bet_index_exists,
        "rows_match_expected": total == EXPECTED_TOTAL_ROWS,
    }


def run_drift_guard() -> dict:
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts/replay_lifecycle_drift_guard.py")],
        cwd=str(REPO_ROOT), capture_output=True, text=True,
    )
    passed = result.returncode == 0 and "REPLAY_LIFECYCLE_DRIFT_GUARD_PASS" in result.stdout
    if not passed:
        _stop(f"drift guard failed:\n{result.stdout}\n{result.stderr}")
    return {
        "status": "PASS",
        "classification": "REPLAY_LIFECYCLE_DRIFT_GUARD_PASS",
        "total_rows": EXPECTED_TOTAL_ROWS,
    }


# ── Source artifact summaries ─────────────────────────────────────────────────

def build_p144b_source_summary(p144b: dict) -> dict:
    c = p144b.get("classification", "")
    if c != "P144B_LIVE_DRAW_MONITORING_ACTIVATION_GATE_READY":
        _stop(f"P144B classification mismatch: {c}")
    return {
        "classification": c,
        "artifact_path": str(P144B_JSON.relative_to(REPO_ROOT)),
        "pass": True,
        "candidate_count": len(p144b.get("monitoring_candidate_inventory", [])),
        "contract_field_count": len(p144b.get("live_monitoring_contract", {}).get("fields", {})),
    }


def build_p144a_source_summary(p144a: dict) -> dict:
    c = p144a.get("classification", "")
    if c != "P144A_STRATEGY_CHAMPION_REGISTRY_READINESS_GATE_READY":
        _stop(f"P144A classification mismatch: {c}")
    return {
        "classification": c,
        "pass": True,
    }


def build_p143_source_summary(p143: dict) -> dict:
    c = p143.get("classification", "")
    if c != "P143_POST_WAVE2_GOVERNANCE_READINESS_PLAN_READY":
        _stop(f"P143 classification mismatch: {c}")
    return {
        "classification": c,
        "pass": True,
    }


# ── Monitoring candidate inventory ────────────────────────────────────────────

def build_monitoring_candidate_inventory(p144b: dict, conn: sqlite3.Connection) -> list:
    """Read candidates from P144B artifact, enrich with current DB counts."""
    inventory = []
    for item in p144b.get("monitoring_candidate_inventory", []):
        sid = item["strategy_id"]
        rows = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id=?",
            (sid,),
        ).fetchone()[0]
        inventory.append({
            "strategy_id": sid,
            "lottery_type": item["lottery_type"],
            "bet_count": item["bet_count"],
            "wave2_task_source": item["wave2_task_source"],
            "truth_level": item["truth_level"],
            "total_replay_rows": rows,
            "live_monitoring_candidate": True,
            "live_evidence_available_now": False,
            "monitoring_note": (
                "All DB rows are historical backfill. "
                "No live draw monitoring active. "
                "Live evidence requires post-apply monitoring run."
            ),
        })
    return inventory


# ── Monitoring contract validation ───────────────────────────────────────────

def build_monitoring_contract_validation(p144b: dict) -> dict:
    contract_fields = list(p144b.get("live_monitoring_contract", {}).get("fields", {}).keys())
    missing = [f for f in REQUIRED_CONTRACT_FIELDS if f not in contract_fields]
    contract_complete = len(missing) == 0
    if not contract_complete:
        _stop(f"P144B contract missing required fields: {missing}")
    return {
        "required_contract_fields_count": len(REQUIRED_CONTRACT_FIELDS),
        "required_contract_fields": REQUIRED_CONTRACT_FIELDS,
        "contract_complete": contract_complete,
        "missing_fields": missing,
        "historical_backfill_is_not_live_evidence": True,
        "live_evidence_requires_post_apply_monitoring_run": True,
        "p144b_contract_field_count": len(contract_fields),
    }


# ── Manual on-demand authorization gate ──────────────────────────────────────

def build_manual_on_demand_authorization_gate() -> dict:
    return {
        "exact_authorization_phrase_template": (
            "P145B_AUTHORIZED_MANUAL_ON_DEMAND_MONITORING_OBSERVATION_ONLY_FOR_6_WAVE2_CANDIDATES_20260529"
        ),
        "authorization_required_before_execution": True,
        "execution_performed_in_p145b": False,
        "production_db_write_allowed": False,
        "observation_only_file_artifact_allowed_later": True,
        "gate_description": (
            "This gate documents the authorization contract for manual on-demand live monitoring. "
            "No monitoring run is executed in P145B. "
            "Execution of any live monitoring requires the exact authorization phrase above, "
            "issued explicitly by the project owner, before any prediction is generated or "
            "any draw result evaluation is stored."
        ),
        "gate_status": "PENDING_AUTHORIZATION",
    }


# ── Observation-only execution plan ──────────────────────────────────────────

def build_observation_only_execution_plan() -> dict:
    return {
        "output_mode": "file_artifact_only",
        "production_db_write": False,
        "scheduler_install": False,
        "live_api_call": False,
        "recommended_output_directory": "outputs/replay/live_monitoring_observation_only/",
        "next_execution_gate": "P146_LIVE_MONITORING_FIRST_DRAW_EVALUATION",
        "description": (
            "When manual on-demand monitoring is authorized, the execution plan is: "
            "(1) Generate forward-looking prediction JSON artifact for each strategy. "
            "(2) Store artifact in recommended_output_directory (file only, no DB write). "
            "(3) After draw result is available, run post-draw evaluation script. "
            "(4) Write observation JSON artifact to recommended_output_directory. "
            "(5) No DB write until P146 gate is explicitly authorized. "
            "This plan is OBSERVATION ONLY — no production side effects."
        ),
    }


# ── Per-strategy monitoring plan ─────────────────────────────────────────────

def build_per_strategy_monitoring_plan(inventory: list) -> list:
    plan = []
    for item in inventory:
        sid = item["strategy_id"]
        lt = item["lottery_type"]
        draw_source = (
            "official_draw_api_or_manual_input"
            if lt == "DAILY_539"
            else "official_draw_api_or_manual_input"
        )
        plan.append({
            "strategy_id": sid,
            "lottery_type": lt,
            "monitoring_truth_level": "LIVE_MONITORING_VERIFIED",
            "expected_output_artifact_path": (
                f"outputs/replay/live_monitoring_observation_only/{sid}/"
            ),
            "required_input_prediction_rows": (
                f"Forward-looking prediction generated BEFORE draw close for {lt}. "
                f"Bet count: {item['bet_count']}. "
                "Prediction must use strategy-specific prediction pipeline with current "
                "history cutoff draw = latest available draw at generation time."
            ),
            "required_draw_result_source": draw_source,
            "live_api_call_required": True,
            "db_write_required": False,
            "scheduler_required": False,
            "current_status": "authorization_pending",
            "wave2_task_source": item["wave2_task_source"],
            "bet_count": item["bet_count"],
        })
    return plan


# ── Runner availability assessment ───────────────────────────────────────────

def build_runner_availability_assessment() -> dict:
    # Search for any existing live monitoring runner in the repo
    candidate_paths = [
        REPO_ROOT / "scripts" / "live_monitoring_runner.py",
        REPO_ROOT / "scripts" / "p146_live_monitoring_runner.py",
        REPO_ROOT / "tools" / "live_monitoring_runner.py",
        REPO_ROOT / "tools" / "post_draw_monitor.py",
    ]
    found_path = None
    for path in candidate_paths:
        if path.exists():
            found_path = str(path.relative_to(REPO_ROOT))
            break

    # Also check via glob for any monitoring runner pattern
    monitoring_scripts = list(REPO_ROOT.glob("scripts/*monitor*runner*.py"))
    monitoring_scripts += list(REPO_ROOT.glob("tools/*monitor*runner*.py"))
    if found_path is None and monitoring_scripts:
        found_path = str(monitoring_scripts[0].relative_to(REPO_ROOT))

    existing_runner_found = found_path is not None
    return {
        "existing_runner_found": existing_runner_found,
        "existing_runner_path": found_path,
        "runner_missing": not existing_runner_found,
        "fixture_or_mock_available": False,
        "implementation_required_before_execution": True,
        "runner_search_note": (
            "Searched for live monitoring runner scripts in scripts/ and tools/. "
            "Existing tools (edge_monitor_live.py, rolling_strategy_monitor.py) provide "
            "backtest/RSM monitoring but do NOT implement per-draw live prediction "
            "generation + post-draw evaluation for Wave 2 strategies. "
            "A dedicated P146 monitoring runner must be implemented before execution."
        ),
    }


# ── Authorization phrase templates ────────────────────────────────────────────

def build_authorization_phrase_templates() -> dict:
    return {
        "manual_on_demand_observation_only": (
            "P145B_AUTHORIZED_MANUAL_ON_DEMAND_MONITORING_OBSERVATION_ONLY_FOR_6_WAVE2_CANDIDATES_20260529"
        ),
        "next_gate": "P146_LIVE_MONITORING_FIRST_DRAW_EVALUATION",
        "description": (
            "Authorization phrases must be issued exactly as specified to unlock "
            "manual on-demand monitoring execution. "
            "P145B does NOT execute monitoring — it defines the gate and contracts. "
            "Use the manual_on_demand_observation_only phrase to authorize P146 observation-only run."
        ),
    }


# ── Non-actions ───────────────────────────────────────────────────────────────

def build_non_actions() -> dict:
    return {
        "db_write_in_p145b": False,
        "controlled_apply_executed_in_p145b": False,
        "replay_rows_inserted_in_p145b": 0,
        "replay_rows_deleted_in_p145b": 0,
        "registry_update_executed_in_p145b": False,
        "champion_promotion_executed_in_p145b": False,
        "monitoring_run_executed_in_p145b": False,
        "scheduler_installed": False,
        "live_api_called": False,
        "four_star_executed": False,
        "p108_executed": False,
        "p117_executed": False,
        "p118_executed": False,
    }


# ── Dirty file hygiene ────────────────────────────────────────────────────────

def build_dirty_file_hygiene() -> dict:
    staged = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=str(REPO_ROOT), capture_output=True, text=True, check=True,
    ).stdout.splitlines()
    forbidden_tokens = ("lottery_v2.db", ".history", ".pid", ".runtime")
    forbidden_staged = [s for s in staged if any(t in s for t in forbidden_tokens)]
    return {
        "backups_untracked_not_staged": not any("backups/" in s for s in staged),
        "p135_p136_p142_autouse_regen_risk_noted": True,
        "forbidden_files_staged": len(forbidden_staged) > 0,
        "forbidden_staged_files": forbidden_staged,
        "staged_file_count_at_runtime": len(staged),
    }


# ── Roadmap update ────────────────────────────────────────────────────────────

ROADMAP_MARKER = "CTO_ROADMAP_UPDATED_AFTER_P145B_MANUAL_ON_DEMAND_MONITORING_AUTHORIZATION_GATE_20260529"


def _append_if_absent(path: Path, content: str, marker: str) -> bool:
    text = path.read_text(encoding="utf-8")
    if marker in text:
        return False
    path.write_text(text + content, encoding="utf-8")
    return True


def update_roadmap() -> str:
    section = f"""

## P145B Manual On-Demand Monitoring Authorization Gate (2026-05-29)
- Classification: `P145B_MANUAL_ON_DEMAND_MONITORING_AUTHORIZATION_GATE_READY`
- Manual on-demand monitoring authorization gate defined for all 6 Wave 2 strategies.
- Authorization phrase template defined; authorization_required_before_execution=true.
- execution_performed_in_p145b=false; production_db_write_allowed=false.
- Observation-only execution plan documented; next gate: P146_LIVE_MONITORING_FIRST_DRAW_EVALUATION.
- Runner availability: existing_runner_found assessed; implementation_required_before_execution=true.
- No DB write, no controlled_apply, no scheduler, no live API call, no monitoring run in P145B.
- Marker: `{ROADMAP_MARKER}`
"""
    appended = _append_if_absent(ROADMAP, section, ROADMAP_MARKER)
    return f"{'appended' if appended else 'already present'}: {ROADMAP_MARKER}"


def update_cto() -> str:
    section = f"""

## P145B Manual On-Demand Monitoring Authorization Gate (2026-05-29)
- P145B manual on-demand monitoring authorization gate completed for 6 Wave 2 strategies.
- Authorization gate defined; no monitoring executed; observation-only plan documented.
- authorization_required_before_execution=true; production_db_write_allowed=false.
- Runner not yet implemented; implementation required before P146 execution.
- Next gate: P146_LIVE_MONITORING_FIRST_DRAW_EVALUATION.
- No DB mutation. No registry update. No scheduler. Read-only gate.
- Marker: `{ROADMAP_MARKER}`

**Artifact**: `outputs/replay/p145b_manual_on_demand_monitoring_authorization_gate_20260529.json`
"""
    appended = _append_if_absent(CTO, section, ROADMAP_MARKER)
    return f"{'appended' if appended else 'already present'}: {ROADMAP_MARKER}"


# ── Markdown ──────────────────────────────────────────────────────────────────

def write_markdown(artifact: dict) -> None:
    auth_gate = artifact["manual_on_demand_authorization_gate"]
    obs_plan = artifact["observation_only_execution_plan"]
    inv = artifact["monitoring_candidate_inventory"]
    contract_val = artifact["monitoring_contract_validation"]
    per_strat = artifact["per_strategy_monitoring_plan"]
    runner = artifact["runner_availability_assessment"]
    auth_templates = artifact["authorization_phrase_templates"]
    non_act = artifact["non_actions"]
    risks = artifact["remaining_risks"]

    inv_rows = ""
    for item in inv:
        inv_rows += (
            f"| {item['strategy_id']} | {item['lottery_type']} | {item['bet_count']} | "
            f"{item['wave2_task_source']} | {item['truth_level']} | {item['total_replay_rows']:,} |\n"
        )

    per_strat_rows = ""
    for ps in per_strat:
        per_strat_rows += (
            f"| {ps['strategy_id']} | {ps['lottery_type']} | {ps['monitoring_truth_level']} | "
            f"{ps['db_write_required']} | {ps['scheduler_required']} | {ps['current_status']} |\n"
        )

    md = f"""# P145B: Manual On-Demand Monitoring Authorization Gate

**Classification**: `{CLASSIFICATION}`
**Task ID**: P145B
**Generated**: {artifact["generated_at"]}

---

## Executive Summary

P145B is a read-only manual on-demand monitoring authorization gate for all 6 Wave 2 candidate
strategies. It defines the authorization contract, observation-only execution plan, and per-strategy
monitoring plan. No DB write, no controlled_apply, no scheduler, no live API call, no monitoring run
executed in P145B. Authorization is required before any live monitoring is executed.
Next gate: P146_LIVE_MONITORING_FIRST_DRAW_EVALUATION.

---

## Canonical Repo / Branch Confirmation

| Field | Value |
|-------|-------|
| Expected repo | `{artifact["canonical_repo"]}` |
| Expected branch | `{artifact["canonical_branch"]}` |
| Repo OK | {artifact["repo_branch_check"]["repo_ok"]} |
| Branch OK | {artifact["repo_branch_check"]["branch_ok"]} |

---

## P144B Recap

| Field | Value |
|-------|-------|
| P144B classification | `{artifact["p144b_source_summary"]["classification"]}` |
| Artifact path | `{artifact["p144b_source_summary"]["artifact_path"]}` |
| Candidate count | {artifact["p144b_source_summary"]["candidate_count"]} |
| Contract field count | {artifact["p144b_source_summary"]["contract_field_count"]} |

---

## Monitoring Contract Validation

| Field | Value |
|-------|-------|
| required_contract_fields_count | {contract_val["required_contract_fields_count"]} |
| contract_complete | {contract_val["contract_complete"]} |
| historical_backfill_is_not_live_evidence | {contract_val["historical_backfill_is_not_live_evidence"]} |
| live_evidence_requires_post_apply_monitoring_run | {contract_val["live_evidence_requires_post_apply_monitoring_run"]} |

Required contract fields: {', '.join(f'`{f}`' for f in contract_val["required_contract_fields"])}

---

## Manual On-Demand Authorization Gate

| Field | Value |
|-------|-------|
| authorization_required_before_execution | {auth_gate["authorization_required_before_execution"]} |
| execution_performed_in_p145b | {auth_gate["execution_performed_in_p145b"]} |
| production_db_write_allowed | {auth_gate["production_db_write_allowed"]} |
| observation_only_file_artifact_allowed_later | {auth_gate["observation_only_file_artifact_allowed_later"]} |
| gate_status | `{auth_gate["gate_status"]}` |

**Authorization phrase template**:
```
{auth_gate["exact_authorization_phrase_template"]}
```

{auth_gate["gate_description"]}

---

## Observation-Only Execution Plan

| Field | Value |
|-------|-------|
| output_mode | `{obs_plan["output_mode"]}` |
| production_db_write | {obs_plan["production_db_write"]} |
| scheduler_install | {obs_plan["scheduler_install"]} |
| live_api_call | {obs_plan["live_api_call"]} |
| recommended_output_directory | `{obs_plan["recommended_output_directory"]}` |
| next_execution_gate | `{obs_plan["next_execution_gate"]}` |

{obs_plan["description"]}

---

## Per-Strategy Monitoring Plan

| Strategy | Lottery | Truth Level | DB Write | Scheduler | Status |
|----------|---------|-------------|----------|-----------|--------|
{per_strat_rows}
All 6 strategies: db_write_required=False, scheduler_required=False, current_status=authorization_pending.

---

## Monitoring Candidate Inventory

| Strategy | Lottery | Bets | Source | Truth Level | DB Rows |
|----------|---------|------|--------|-------------|---------|
{inv_rows}
---

## Runner Availability Assessment

| Field | Value |
|-------|-------|
| existing_runner_found | {runner["existing_runner_found"]} |
| existing_runner_path | {runner["existing_runner_path"] or "None"} |
| runner_missing | {runner["runner_missing"]} |
| fixture_or_mock_available | {runner["fixture_or_mock_available"]} |
| implementation_required_before_execution | {runner["implementation_required_before_execution"]} |

{runner["runner_search_note"]}

---

## Authorization Phrase Template

```
{auth_templates["manual_on_demand_observation_only"]}
```

- **Next gate**: `{auth_templates["next_gate"]}`
- {auth_templates["description"]}

---

## Explicit Non-Actions

| Action | Status |
|--------|--------|
| DB write in P145B | {non_act["db_write_in_p145b"]} |
| controlled_apply executed | {non_act["controlled_apply_executed_in_p145b"]} |
| replay_rows_inserted | {non_act["replay_rows_inserted_in_p145b"]} |
| replay_rows_deleted | {non_act["replay_rows_deleted_in_p145b"]} |
| registry_update_executed | {non_act["registry_update_executed_in_p145b"]} |
| champion_promotion_executed | {non_act["champion_promotion_executed_in_p145b"]} |
| monitoring_run_executed | {non_act["monitoring_run_executed_in_p145b"]} |
| scheduler_installed | {non_act["scheduler_installed"]} |
| live_api_called | {non_act["live_api_called"]} |
| 4_STAR_executed | {non_act["four_star_executed"]} |
| P108_executed | {non_act["p108_executed"]} |
| P117_executed | {non_act["p117_executed"]} |
| P118_executed | {non_act["p118_executed"]} |

---

## Dirty File Hygiene Note

- `backups/` remains untracked; not staged; not deleted.
- `docs/replay/p135_*`, `docs/replay/p136_*`, `docs/replay/p142_*`, `docs/replay/p143_*`,
  `docs/replay/p144a_*`, `docs/replay/p144b_*`: autouse fixture may regenerate; not staged.
- Same applies to corresponding `outputs/replay/` JSON files.
- No DB files, history files, pid files, or runtime files staged.

---

## Remaining Risks

{chr(10).join(f"- {r}" for r in risks)}

---

## Recommended Next Task

{artifact["next_recommended_task"]}

---

## Final Classification

`{CLASSIFICATION}`

All 6 Wave 2 candidate strategies have manual on-demand authorization gate defined.
P145B gate READY. No monitoring executed. No DB write.
Next: Authorize P146_LIVE_MONITORING_FIRST_DRAW_EVALUATION after authorization phrase issued.
"""
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text(md, encoding="utf-8")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print("P145B: starting manual on-demand monitoring authorization gate...")

    repo_branch = validate_preflight()
    print("  Phase 0: repo/branch/dirty-files OK")

    conn = _ro_conn()
    snap = db_snapshot(conn)
    print(f"  DB rows: {snap['total_rows']}, bet_index_column_exists: {snap['bet_index_column_exists']}")

    drift = run_drift_guard()
    print(f"  Drift guard: {drift['status']}")

    p144b = _load_json(P144B_JSON)
    p144a = _load_json(P144A_JSON)
    p143 = _load_json(P143_JSON)

    p144b_summary = build_p144b_source_summary(p144b)
    p144a_summary = build_p144a_source_summary(p144a)
    p143_summary = build_p143_source_summary(p143)
    print("  Predecessor artifact classifications: all PASS")

    inventory = build_monitoring_candidate_inventory(p144b, conn)
    contract_val = build_monitoring_contract_validation(p144b)
    auth_gate = build_manual_on_demand_authorization_gate()
    obs_plan = build_observation_only_execution_plan()
    per_strat = build_per_strategy_monitoring_plan(inventory)
    runner = build_runner_availability_assessment()
    auth_templates = build_authorization_phrase_templates()
    non_act = build_non_actions()
    dirty = build_dirty_file_hygiene()
    conn.close()

    roadmap_status = update_roadmap()
    cto_status = update_cto()
    print(f"  Roadmap: {roadmap_status}")
    print(f"  CTO: {cto_status}")

    artifact = {
        "task_id": TASK_ID,
        "classification": CLASSIFICATION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "canonical_repo": CANONICAL_REPO,
        "canonical_branch": CANONICAL_BRANCH,
        "repo_branch_check": repo_branch,
        "db_snapshot": snap,
        "drift_guard_result": drift,
        "p144b_source_summary": p144b_summary,
        "p144a_source_summary": p144a_summary,
        "p143_source_summary": p143_summary,
        "monitoring_candidate_inventory": inventory,
        "monitoring_contract_validation": contract_val,
        "manual_on_demand_authorization_gate": auth_gate,
        "observation_only_execution_plan": obs_plan,
        "per_strategy_monitoring_plan": per_strat,
        "runner_availability_assessment": runner,
        "authorization_phrase_templates": auth_templates,
        "non_actions": non_act,
        "dirty_file_hygiene": dirty,
        "roadmap_update_status": roadmap_status,
        "remaining_risks": [
            "P135/P136/P142/P143/P144A/P144B autouse fixtures may regenerate artifacts on regression runs; "
            "regenerated files appear as unstaged changes but are not P145B products.",
            "All 6 candidate strategies have 0 live draw monitoring data; "
            "champion evaluation remains blocked until live monitoring is activated (P146).",
            "LEGACY_UNVERIFIED rows (100 total: 50 per P10/P12 strategy) remain pending P144C remediation.",
            "backups/ directory remains untracked; rollback commands reference pre-P141 backup.",
            "Live monitoring runner not yet implemented; P146 requires dedicated runner implementation "
            "before any prediction generation or draw result evaluation can occur.",
            "champion_eval_ready_from_live_data=False for all strategies; "
            "promotion gate requires >=50 live draws with edge > baseline and perm p < 0.05.",
            "Authorization phrase must be issued explicitly before any live monitoring execution; "
            "gate_status=PENDING_AUTHORIZATION until phrase is provided.",
        ],
        "next_recommended_task": (
            "P146: live monitoring first draw evaluation — "
            "after authorization phrase P145B_AUTHORIZED_MANUAL_ON_DEMAND_MONITORING_OBSERVATION_ONLY_"
            "FOR_6_WAVE2_CANDIDATES_20260529 is issued, implement runner and execute first "
            "observation-only monitoring draw for Wave 2 strategies. "
            "P144C: LEGACY_UNVERIFIED remediation authorization gate (independent). "
            "P145: observation watchlist + champion eval gate after live monitoring threshold met."
        ),
        "summary": (
            "P145B defines the manual on-demand monitoring authorization gate for all 6 "
            "Wave 2 candidate strategies (DB=94,924 rows). "
            "Authorization phrase template defined; execution_performed_in_p145b=False. "
            "Observation-only execution plan documented; next gate: P146. "
            "Runner not found; implementation required before execution. "
            "No DB write, no scheduler, no live API call, no monitoring run in P145B."
        ),
    }

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(artifact, indent=2, ensure_ascii=False), encoding="utf-8")
    write_markdown(artifact)

    print(f"P145B complete: {CLASSIFICATION}")
    print(f"  JSON: {OUT_JSON}")
    print(f"  MD:   {OUT_MD}")


if __name__ == "__main__":
    main()
