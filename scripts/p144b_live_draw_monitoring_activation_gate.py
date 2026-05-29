#!/usr/bin/env python3
"""
P144B: Live draw monitoring activation gate.

Read-only gate script.  No DB writes.  No controlled_apply executed.
No registry update.  No champion promotion.  No monitoring activated.
No scheduler installed.  No live API called.
Defines the live monitoring contract, readiness matrix, and activation options
for all 6 Wave 2 candidate strategies.
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

TASK_ID = "P144B"
CLASSIFICATION = "P144B_LIVE_DRAW_MONITORING_ACTIVATION_GATE_READY"
DATE_SUFFIX = "20260529"

CANONICAL_REPO = str(REPO_ROOT)
CANONICAL_BRANCH = "claude/zen-gates-ff6802"
EXPECTED_TOTAL_ROWS = 94924

OUT_JSON = REPO_ROOT / f"outputs/replay/p144b_live_draw_monitoring_activation_gate_{DATE_SUFFIX}.json"
OUT_MD = REPO_ROOT / f"docs/replay/p144b_live_draw_monitoring_activation_gate_{DATE_SUFFIX}.md"
ROADMAP = REPO_ROOT / "00-Plan/roadmap/roadmap.md"
CTO = REPO_ROOT / "00-Plan/roadmap/CTO-Analysis.md"

P144A_JSON = REPO_ROOT / "outputs/replay/p144a_strategy_champion_registry_readiness_gate_20260529.json"
P143_JSON = REPO_ROOT / "outputs/replay/p143_post_wave2_governance_readiness_plan_20260529.json"
P142_JSON = REPO_ROOT / "outputs/replay/p142_wave2_multibet_apply_chain_closure_audit_20260529.json"

# Own files (allowed as dirty)
_OWN_FILES = {
    "scripts/p144b_live_draw_monitoring_activation_gate.py",
    f"outputs/replay/p144b_live_draw_monitoring_activation_gate_{DATE_SUFFIX}.json",
    f"docs/replay/p144b_live_draw_monitoring_activation_gate_{DATE_SUFFIX}.md",
    "tests/test_p144b_live_draw_monitoring_activation_gate.py",
    "00-Plan/roadmap/roadmap.md",
    "00-Plan/roadmap/CTO-Analysis.md",
}
_AUTOUSE_PREFIXES = (
    "outputs/replay/p135_", "outputs/replay/p136_", "outputs/replay/p142_",
    "outputs/replay/p143_", "outputs/replay/p144a_", "outputs/replay/p145b_",
    "docs/replay/p135_", "docs/replay/p136_", "docs/replay/p142_",
    "docs/replay/p143_", "docs/replay/p144a_", "docs/replay/p145b_",
    "scripts/p141_", "scripts/p141a_", "scripts/p142_", "scripts/p143_",
    "scripts/p144a_", "scripts/p145b_",
    "tests/test_p142_", "tests/test_p143_", "tests/test_p144a_", "tests/test_p145b_",
)

# 6 Wave 2 candidate strategies
_STRATEGY_META = [
    {
        "strategy_id": "acb_markov_midfreq_3bet",
        "lottery_type": "DAILY_539",
        "bet_count": 3,
        "wave2_task_source": "P131",
        "truth_level": "DAILY539_RETIRED_STRATEGY_BACKFILL_VERIFIED",
    },
    {
        "strategy_id": "midfreq_fourier_mk_3bet",
        "lottery_type": "POWER_LOTTO",
        "bet_count": 3,
        "wave2_task_source": "P132",
        "truth_level": "POWERLOTTO_WAVE4_STRATEGY_BACKFILL_VERIFIED",
    },
    {
        "strategy_id": "fourier_rhythm_3bet",
        "lottery_type": "POWER_LOTTO",
        "bet_count": 3,
        "wave2_task_source": "P134",
        "truth_level": "POWERLOTTO_SINGLE_STRATEGY_BACKFILL_VERIFIED",
    },
    {
        "strategy_id": "pp3_freqort_4bet",
        "lottery_type": "POWER_LOTTO",
        "bet_count": 4,
        "wave2_task_source": "P133",
        "truth_level": "POWERLOTTO_WAVE4_STRATEGY_BACKFILL_VERIFIED",
    },
    {
        "strategy_id": "power_precision_3bet",
        "lottery_type": "POWER_LOTTO",
        "bet_count": 3,
        "wave2_task_source": "P140",
        "truth_level": "POWERLOTTO_REMAINING_STRATEGIES_BACKFILL_VERIFIED",
    },
    {
        "strategy_id": "power_orthogonal_5bet",
        "lottery_type": "POWER_LOTTO",
        "bet_count": 5,
        "wave2_task_source": "P141",
        "truth_level": "POWERLOTTO_REMAINING_STRATEGIES_BACKFILL_VERIFIED",
    },
]


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

def build_p144a_source_summary() -> dict:
    p144a = _load_json(P144A_JSON)
    c = p144a.get("classification", "")
    if c != "P144A_STRATEGY_CHAMPION_REGISTRY_READINESS_GATE_READY":
        _stop(f"P144A classification mismatch: {c}")
    return {
        "classification": c,
        "pass": True,
        "candidate_count": len(p144a.get("candidate_strategy_inventory", {})),
        "registry_mutation_in_p144a": p144a.get("recommended_registry_path", {}).get("registry_mutation_in_p144a", False),
    }


def build_p143_source_summary() -> dict:
    p143 = _load_json(P143_JSON)
    c = p143.get("classification", "")
    if c != "P143_POST_WAVE2_GOVERNANCE_READINESS_PLAN_READY":
        _stop(f"P143 classification mismatch: {c}")
    return {
        "classification": c,
        "pass": True,
    }


def build_p142_source_summary() -> dict:
    p142 = _load_json(P142_JSON)
    c = p142.get("classification", "")
    if c != "P142_WAVE2_MULTI_BET_APPLY_CHAIN_CLOSED":
        _stop(f"P142 classification mismatch: {c}")
    return {
        "classification": c,
        "pass": True,
    }


# ── Monitoring candidate inventory ────────────────────────────────────────────

def build_monitoring_candidate_inventory(conn: sqlite3.Connection) -> list:
    inventory = []
    for meta in _STRATEGY_META:
        sid = meta["strategy_id"]
        rows = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id=?",
            (sid,),
        ).fetchone()[0]
        inventory.append({
            "strategy_id": sid,
            "lottery_type": meta["lottery_type"],
            "bet_count": meta["bet_count"],
            "wave2_task_source": meta["wave2_task_source"],
            "truth_level": meta["truth_level"],
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


# ── Live monitoring contract ──────────────────────────────────────────────────

def build_live_monitoring_contract() -> dict:
    return {
        "contract_version": "1.0",
        "description": (
            "Schema contract for a live monitoring record. "
            "Each record represents one strategy prediction evaluated against a real draw result "
            "captured after P144B monitoring is activated."
        ),
        "fields": {
            "monitored_strategy_id": "TEXT — strategy identifier (e.g. acb_markov_midfreq_3bet)",
            "lottery_type": "TEXT — DAILY_539 or POWER_LOTTO",
            "target_draw": "TEXT — draw number string (e.g. '115000072')",
            "prediction_generated_at": "TEXT — ISO timestamp when prediction was generated",
            "draw_result_available_at": "TEXT — ISO timestamp when draw result was confirmed",
            "predicted_numbers": "TEXT — JSON array of predicted numbers",
            "actual_numbers": "TEXT — JSON array of actual draw numbers",
            "hit_count": "INTEGER — number of matching numbers",
            "evaluation_status": "TEXT — PENDING | EVALUATED | SKIPPED",
            "source_trace": "TEXT — traceability key linking to prediction log entry",
            "monitoring_truth_level": "TEXT — truth level label for live monitoring rows",
            "created_at": "TEXT — ISO timestamp when monitoring record was created",
        },
        "monitoring_truth_level_for_live_rows": "LIVE_MONITORING_VERIFIED",
        "db_table": "strategy_prediction_replays",
        "note": (
            "Live monitoring rows use truth_level='LIVE_MONITORING_VERIFIED'. "
            "They are distinct from historical backfill rows and from LEGACY_UNVERIFIED rows. "
            "No live monitoring rows exist in the DB at P144B creation time."
        ),
    }


# ── Historical vs live data boundary ─────────────────────────────────────────

def build_historical_vs_live_data_boundary() -> dict:
    return {
        "historical_backfill_actual_numbers_count_may_exist": True,
        "historical_backfill_is_not_live_evidence": True,
        "live_evidence_requires_post_apply_monitoring_run": True,
        "champion_eval_ready_from_live_data": False,
        "explanation": (
            "Historical backfill rows have actual_numbers populated because the replay "
            "process runs against known historical draws. This is NOT live monitoring evidence. "
            "Live evidence is defined as: predictions generated BEFORE a draw, subsequently "
            "compared against the REAL draw result in a post-draw evaluation run. "
            "No such runs have occurred for any Wave 2 strategy. "
            "champion_eval_ready_from_live_data remains False until ≥50 live draws are evaluated "
            "per strategy with edge > baseline and perm p < 0.05."
        ),
    }


# ── Live monitoring readiness matrix ─────────────────────────────────────────

def build_live_monitoring_readiness_matrix(inventory: list) -> list:
    matrix = []
    for item in inventory:
        matrix.append({
            "strategy_id": item["strategy_id"],
            "lottery_type": item["lottery_type"],
            "monitoring_ready": False,
            "live_evidence_available_now": False,
            "monitoring_truth_level": "LIVE_MONITORING_VERIFIED",
            "required_next_step": (
                "Authorize live monitoring activation (P145B or equivalent). "
                "Generate forward-looking prediction, await draw result, run post-draw evaluation."
            ),
            "authorization_required_later": True,
            "blocking_reason": (
                "No live monitoring infrastructure active. "
                "Monitoring activation requires explicit authorization gate (not executed in P144B)."
            ),
        })
    return matrix


# ── Monitoring activation options ────────────────────────────────────────────

def build_monitoring_activation_options() -> dict:
    return {
        "option_a_manual_on_demand_monitoring": {
            "description": (
                "Manually generate predictions for the next draw, "
                "then run a post-draw evaluation script after results are available. "
                "No scheduler. No automated pipeline."
            ),
            "requires_scheduler": False,
            "requires_live_api": False,
            "db_write_in_p144b": False,
            "risk": "LOW",
            "pros": "Fully controlled; no infrastructure setup; immediate after authorization.",
            "cons": "Manual effort per draw; not scalable for continuous monitoring.",
            "recommended": True,
            "when_to_use": "When immediate, one-off live evaluation is desired after P145B authorization.",
        },
        "option_b_scheduled_monitoring_after_authorization": {
            "description": (
                "Install a scheduled monitoring pipeline that automatically generates predictions "
                "before each draw and runs evaluation after draw results are available. "
                "Requires explicit scheduler authorization and infra setup."
            ),
            "requires_scheduler": True,
            "requires_live_api": False,
            "db_write_in_p144b": False,
            "risk": "MEDIUM",
            "pros": "Automated; consistent; suitable for production-grade champion evaluation.",
            "cons": (
                "Requires scheduler setup, infra authorization, and per-strategy production routing. "
                "Not executable in P144B without additional authorization."
            ),
            "recommended": False,
            "when_to_use": "After P145B authorization + scheduler infrastructure review.",
        },
        "option_c_observation_only_file_artifact_before_db_write": {
            "description": (
                "Produce an observation-only JSON artifact capturing the monitoring contract, "
                "readiness matrix, and activation options without any DB write, API call, "
                "or scheduler install. Suitable as the immediate next step to document intent."
            ),
            "requires_scheduler": False,
            "requires_live_api": False,
            "db_write_in_p144b": False,
            "risk": "ZERO",
            "pros": (
                "Clean, safe, auditable. Documents the full monitoring design without side effects. "
                "Enables stakeholder review before activation."
            ),
            "cons": "No live evidence produced; champion evaluation still blocked.",
            "recommended": True,
            "when_to_use": "Immediately, as P144B output. This is what P144B does.",
        },
    }


# ── Authorization phrase templates ────────────────────────────────────────────

def build_authorization_phrase_templates() -> dict:
    return {
        "description": (
            "Templates for authorization phrases to be used in P145B (live monitoring activation). "
            "None of these are executed in P144B. They are reference templates only."
        ),
        "template_activate_manual_monitoring_single_strategy": (
            "AUTHORIZE: activate manual live draw monitoring for {strategy_id} on {lottery_type}. "
            "Generate prediction for draw {next_draw_id}. Evaluate after draw result confirmed."
        ),
        "template_activate_scheduled_monitoring_all_strategies": (
            "AUTHORIZE: install scheduled monitoring pipeline for all 6 Wave 2 strategies. "
            "Confirm infra setup and scheduler authorization before execution."
        ),
        "template_record_live_evaluation_result": (
            "AUTHORIZE: record live draw evaluation result for {strategy_id}, "
            "draw {target_draw}, hit_count={hit_count}, evaluation_status=EVALUATED."
        ),
        "execution_gate": "P145B_LIVE_MONITORING_AUTHORIZATION_AND_EXECUTION_GATE",
        "note": (
            "These templates are NOT executed in P144B. "
            "P145B (or an equivalent authorization gate) must be created and explicitly authorized "
            "before any live monitoring row is written to the DB."
        ),
    }


# ── Non-actions ───────────────────────────────────────────────────────────────

def build_non_actions() -> dict:
    return {
        "db_write_in_p144b": False,
        "controlled_apply_executed_in_p144b": False,
        "replay_rows_inserted_in_p144b": 0,
        "replay_rows_deleted_in_p144b": 0,
        "registry_update_executed_in_p144b": False,
        "champion_promotion_executed_in_p144b": False,
        "monitoring_activated_in_p144b": False,
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

ROADMAP_MARKER = "CTO_ROADMAP_UPDATED_AFTER_P144B_LIVE_DRAW_MONITORING_ACTIVATION_GATE_20260529"


def _append_if_absent(path: Path, content: str, marker: str) -> bool:
    text = path.read_text(encoding="utf-8")
    if marker in text:
        return False
    path.write_text(text + content, encoding="utf-8")
    return True


def update_roadmap() -> str:
    section = f"""

## P144B Live Draw Monitoring Activation Gate (2026-05-29)
- Classification: `P144B_LIVE_DRAW_MONITORING_ACTIVATION_GATE_READY`
- Live monitoring contract defined for all 6 Wave 2 strategies.
- Historical vs live data boundary documented; champion_eval_ready_from_live_data=false.
- Readiness matrix: all 6 strategies monitoring_ready=false, authorization_required_later=true.
- Recommended path: option_c (observation-only artifact) now; option_a (manual on-demand) after P145B authorization.
- No DB write, no controlled_apply, no scheduler, no live API call in P144B.
- Next gate: P145B (live monitoring authorization and execution gate).
- Marker: `{ROADMAP_MARKER}`
"""
    appended = _append_if_absent(ROADMAP, section, ROADMAP_MARKER)
    return f"{'appended' if appended else 'already present'}: {ROADMAP_MARKER}"


def update_cto() -> str:
    section = f"""

## P144B Live Draw Monitoring Activation Gate (2026-05-29)
- P144B defined live monitoring contract for 6 Wave 2 strategies; no activation executed.
- Historical backfill rows are NOT live evidence; champion eval blocked until live monitoring active.
- All 6 strategies: monitoring_ready=false, live_evidence_available_now=false, authorization_required_later=true.
- Recommended options: C (observation artifact) now; A (manual on-demand) after P145B authorization.
- No DB mutation. No registry update. No scheduler. Read-only gate.
- Marker: `{ROADMAP_MARKER}`

**Artifact**: `outputs/replay/p144b_live_draw_monitoring_activation_gate_20260529.json`
"""
    appended = _append_if_absent(CTO, section, ROADMAP_MARKER)
    return f"{'appended' if appended else 'already present'}: {ROADMAP_MARKER}"


# ── Markdown ──────────────────────────────────────────────────────────────────

def write_markdown(artifact: dict) -> None:
    inv = artifact["monitoring_candidate_inventory"]
    matrix = artifact["live_monitoring_readiness_matrix"]
    boundary = artifact["historical_vs_live_data_boundary"]
    opts = artifact["monitoring_activation_options"]
    contract = artifact["live_monitoring_contract"]
    non_act = artifact["non_actions"]
    risks = artifact["remaining_risks"]

    inv_rows = ""
    for item in inv:
        inv_rows += (
            f"| {item['strategy_id']} | {item['lottery_type']} | {item['bet_count']} | "
            f"{item['wave2_task_source']} | {item['truth_level']} | {item['total_replay_rows']:,} |\n"
        )

    matrix_rows = ""
    for row in matrix:
        matrix_rows += (
            f"| {row['strategy_id']} | {row['lottery_type']} | {row['monitoring_ready']} | "
            f"{row['live_evidence_available_now']} | {row['authorization_required_later']} |\n"
        )

    contract_rows = ""
    for field, desc in contract["fields"].items():
        contract_rows += f"| `{field}` | {desc} |\n"

    md = f"""# P144B: Live Draw Monitoring Activation Gate

**Classification**: `{CLASSIFICATION}`
**Task ID**: P144B
**Generated**: {artifact["generated_at"]}

---

## Executive Summary

P144B is a read-only live draw monitoring activation gate for all 6 Wave 2 candidate strategies.
It defines the live monitoring contract, readiness matrix, and activation options.
No DB write, no controlled_apply, no scheduler, no live API call, no champion promotion in P144B.
All 6 strategies are in a "replay rows applied, no live monitoring data" state.
Recommended path: option_c (observation-only artifact, this document) now;
option_a (manual on-demand monitoring) after explicit P145B authorization.

---

## Canonical Repo / Branch Confirmation

| Field | Value |
|-------|-------|
| Expected repo | `{artifact["canonical_repo"]}` |
| Expected branch | `{artifact["canonical_branch"]}` |
| Repo OK | {artifact["repo_branch_check"]["repo_ok"]} |
| Branch OK | {artifact["repo_branch_check"]["branch_ok"]} |

---

## Predecessor Artifact Summaries

| Task | Classification | Pass |
|------|----------------|------|
| P144A | `{artifact["p144a_source_summary"]["classification"]}` | {artifact["p144a_source_summary"]["pass"]} |
| P143 | `{artifact["p143_source_summary"]["classification"]}` | {artifact["p143_source_summary"]["pass"]} |
| P142 | `{artifact["p142_source_summary"]["classification"]}` | {artifact["p142_source_summary"]["pass"]} |

---

## Monitoring Candidate Inventory

| Strategy | Lottery | Bets | Source | Truth Level | DB Rows |
|----------|---------|------|--------|-------------|---------|
{inv_rows}
---

## Historical vs Live Data Boundary

| Flag | Value |
|------|-------|
| historical_backfill_actual_numbers_count_may_exist | {boundary["historical_backfill_actual_numbers_count_may_exist"]} |
| historical_backfill_is_not_live_evidence | {boundary["historical_backfill_is_not_live_evidence"]} |
| live_evidence_requires_post_apply_monitoring_run | {boundary["live_evidence_requires_post_apply_monitoring_run"]} |
| champion_eval_ready_from_live_data | {boundary["champion_eval_ready_from_live_data"]} |

**Note**: {boundary["explanation"]}

---

## Live Monitoring Contract

| Field | Description |
|-------|-------------|
{contract_rows}
- **Monitoring truth level for live rows**: `{contract["monitoring_truth_level_for_live_rows"]}`
- **DB table**: `{contract["db_table"]}`

---

## Live Monitoring Readiness Matrix

| Strategy | Lottery | Monitoring Ready | Live Evidence Now | Auth Required |
|----------|---------|-----------------|-------------------|---------------|
{matrix_rows}
**All 6 strategies**: monitoring_ready=False, live_evidence_available_now=False, authorization_required_later=True.

---

## Monitoring Activation Options

### Option A: Manual On-Demand Monitoring (Recommended after P145B)
- {opts["option_a_manual_on_demand_monitoring"]["description"]}
- **Risk**: {opts["option_a_manual_on_demand_monitoring"]["risk"]}
- **Requires scheduler**: {opts["option_a_manual_on_demand_monitoring"]["requires_scheduler"]}
- **Pros**: {opts["option_a_manual_on_demand_monitoring"]["pros"]}
- **Cons**: {opts["option_a_manual_on_demand_monitoring"]["cons"]}

### Option B: Scheduled Monitoring After Authorization
- {opts["option_b_scheduled_monitoring_after_authorization"]["description"]}
- **Risk**: {opts["option_b_scheduled_monitoring_after_authorization"]["risk"]}
- **Requires scheduler**: {opts["option_b_scheduled_monitoring_after_authorization"]["requires_scheduler"]}
- **Pros**: {opts["option_b_scheduled_monitoring_after_authorization"]["pros"]}
- **Cons**: {opts["option_b_scheduled_monitoring_after_authorization"]["cons"]}

### Option C: Observation-Only File Artifact (Recommended now) ✅
- {opts["option_c_observation_only_file_artifact_before_db_write"]["description"]}
- **Risk**: {opts["option_c_observation_only_file_artifact_before_db_write"]["risk"]}
- **Requires scheduler**: {opts["option_c_observation_only_file_artifact_before_db_write"]["requires_scheduler"]}
- **Pros**: {opts["option_c_observation_only_file_artifact_before_db_write"]["pros"]}
- **Cons**: {opts["option_c_observation_only_file_artifact_before_db_write"]["cons"]}

**Recommended monitoring path**: `{artifact["recommended_monitoring_path"]}`

---

## Authorization Phrase Templates (P145B Reference Only)

These templates define the authorization phrases for P145B. None are executed in P144B.

- **Execution gate**: `{artifact["authorization_phrase_templates"]["execution_gate"]}`
- **Manual monitoring**: `{artifact["authorization_phrase_templates"]["template_activate_manual_monitoring_single_strategy"]}`
- **Scheduled monitoring**: `{artifact["authorization_phrase_templates"]["template_activate_scheduled_monitoring_all_strategies"]}`
- **Record result**: `{artifact["authorization_phrase_templates"]["template_record_live_evaluation_result"]}`

---

## Explicit Non-Actions

| Action | Status |
|--------|--------|
| DB write in P144B | {non_act["db_write_in_p144b"]} |
| controlled_apply executed | {non_act["controlled_apply_executed_in_p144b"]} |
| replay_rows_inserted | {non_act["replay_rows_inserted_in_p144b"]} |
| replay_rows_deleted | {non_act["replay_rows_deleted_in_p144b"]} |
| registry_update_executed | {non_act["registry_update_executed_in_p144b"]} |
| champion_promotion_executed | {non_act["champion_promotion_executed_in_p144b"]} |
| monitoring_activated | {non_act["monitoring_activated_in_p144b"]} |
| scheduler_installed | {non_act["scheduler_installed"]} |
| live_api_called | {non_act["live_api_called"]} |
| 4_STAR_executed | {non_act["four_star_executed"]} |
| P108_executed | {non_act["p108_executed"]} |
| P117_executed | {non_act["p117_executed"]} |
| P118_executed | {non_act["p118_executed"]} |

---

## Dirty File Hygiene Note

- `backups/` remains untracked; not staged; not deleted.
- `docs/replay/p135_*`, `docs/replay/p136_*`, `docs/replay/p142_*`, `docs/replay/p143_*`, `docs/replay/p144a_*`:
  autouse fixture may regenerate; not staged.
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

All 6 Wave 2 candidate strategies have live monitoring contract defined.
Readiness gate READY. No monitoring activated. No DB write.
Next: P145B live monitoring authorization and execution gate.
"""
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text(md, encoding="utf-8")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print("P144B: starting live draw monitoring activation gate...")

    repo_branch = validate_preflight()
    print("  Phase 0: repo/branch/dirty-files OK")

    conn = _ro_conn()
    snap = db_snapshot(conn)
    print(f"  DB rows: {snap['total_rows']}, bet_index_column_exists: {snap['bet_index_column_exists']}")

    drift = run_drift_guard()
    print(f"  Drift guard: {drift['status']}")

    p144a_summary = build_p144a_source_summary()
    p143_summary = build_p143_source_summary()
    p142_summary = build_p142_source_summary()
    print("  Predecessor artifact classifications: all PASS")

    inventory = build_monitoring_candidate_inventory(conn)
    contract = build_live_monitoring_contract()
    boundary = build_historical_vs_live_data_boundary()
    matrix = build_live_monitoring_readiness_matrix(inventory)
    opts = build_monitoring_activation_options()
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
        "p144a_source_summary": p144a_summary,
        "p143_source_summary": p143_summary,
        "p142_source_summary": p142_summary,
        "monitoring_candidate_inventory": inventory,
        "live_monitoring_contract": contract,
        "historical_vs_live_data_boundary": boundary,
        "live_monitoring_readiness_matrix": matrix,
        "monitoring_activation_options": opts,
        "recommended_monitoring_path": "option_c",
        "authorization_phrase_templates": auth_templates,
        "non_actions": non_act,
        "dirty_file_hygiene": dirty,
        "roadmap_update_status": roadmap_status,
        "remaining_risks": [
            "P135/P136/P142/P143/P144A autouse fixtures may regenerate artifacts on regression runs; "
            "regenerated files appear as unstaged changes but are not P144B products.",
            "All 6 candidate strategies have 0 live draw monitoring data; "
            "champion evaluation remains blocked until live monitoring is activated (P145B).",
            "LEGACY_UNVERIFIED rows (100 total: 50 per P10/P12 strategy) remain pending P144C remediation.",
            "backups/ directory remains untracked; rollback commands reference pre-P141 backup.",
            "Live monitoring infrastructure (prediction pipeline, post-draw evaluator) not yet implemented.",
            "champion_eval_ready_from_live_data=False for all strategies; "
            "promotion gate requires ≥50 live draws with edge > baseline and perm p < 0.05.",
        ],
        "next_recommended_task": (
            "P145B: live monitoring authorization and execution gate — "
            "authorize and execute manual on-demand live monitoring for Wave 2 strategies. "
            "P144C: LEGACY_UNVERIFIED remediation authorization gate (independent). "
            "P145: observation watchlist + champion eval gate after live monitoring threshold met."
        ),
        "summary": (
            "P144B defines the live draw monitoring contract and readiness matrix for all 6 "
            "Wave 2 candidate strategies (DB=94,924 rows). "
            "Historical backfill rows are NOT live evidence. "
            "All 6 strategies: monitoring_ready=False, live_evidence_available_now=False, "
            "authorization_required_later=True. "
            "Recommended path: option_c (observation-only artifact) now; "
            "option_a (manual on-demand) after P145B authorization. "
            "No DB write, no scheduler, no live API call, no champion promotion in P144B."
        ),
    }

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(artifact, indent=2, ensure_ascii=False), encoding="utf-8")
    write_markdown(artifact)

    print(f"P144B complete: {CLASSIFICATION}")
    print(f"  JSON: {OUT_JSON}")
    print(f"  MD:   {OUT_MD}")


if __name__ == "__main__":
    main()
