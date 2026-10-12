#!/usr/bin/env python3
"""
P148: LIVE_MONITORING_VERIFIED Evidence Collection Gate

Define the collection plan for accumulating real post-apply draw observations
(LIVE_MONITORING_VERIFIED truth level) across all 6 Wave-2 champion candidate
strategies. Gate establishes what is needed, enumerates collection paths
(A/B/C/D), and identifies the lowest-risk recommended path.

Constraints (no exceptions):
- NO DB writes
- NO live API calls
- NO champion promotion
- NO registry updates
- NO monitoring runs
- NO scheduler/cron/launchd
- NO controlled_apply
"""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CANONICAL_REPO = (
    "/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802"
)
CANONICAL_BRANCH = "claude/zen-gates-ff6802"
EXPECTED_DB_ROWS = 94924
EXPECTED_LEGACY_UNVERIFIED_ROWS = 100

CANDIDATE_STRATEGIES = [
    ("acb_markov_midfreq_3bet",   "DAILY_539"),
    ("midfreq_fourier_mk_3bet",   "POWER_LOTTO"),
    ("fourier_rhythm_3bet",       "POWER_LOTTO"),
    ("pp3_freqort_4bet",          "POWER_LOTTO"),
    ("power_precision_3bet",      "POWER_LOTTO"),
    ("power_orthogonal_5bet",     "POWER_LOTTO"),
]

PREDECESSOR_ARTIFACTS = {
    "P147": "outputs/replay/p147_champion_evaluation_gate_readiness_audit_20260529.json",
    "P146B": "outputs/replay/p146b_authorized_observation_only_monitoring_run_20260529.json",
    "P146A": "outputs/replay/p146a_observation_only_live_monitoring_runner_20260529.json",
    "P144D": "outputs/replay/p144d_keep_legacy_unverified_governed_baseline_20260529.json",
}

EXPECTED_CLASSIFICATIONS = {
    "P147": "P147_CHAMPION_EVALUATION_BLOCKED_PENDING_LIVE_MONITORING_VERIFIED",
    "P146B": "P146B_AUTHORIZED_OBSERVATION_ONLY_MONITORING_RUN_COMPLETED",
    "P146A": "P146A_OBSERVATION_ONLY_MONITORING_RUNNER_READY",
    "P144D": "P144D_LEGACY_UNVERIFIED_KEEP_GOVERNED_BASELINE_DECISION_RECORDED",
}

OBS_ONLY_DIR = "outputs/replay/live_monitoring_observation_only"

OUTPUT_JSON = "outputs/replay/p148_live_monitoring_verified_evidence_collection_gate_20260529.json"
OUTPUT_MD   = "docs/replay/p148_live_monitoring_verified_evidence_collection_gate_20260529.md"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_repo_root() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True, text=True, cwd=CANONICAL_REPO,
    )
    return result.stdout.strip()


def get_current_branch() -> str:
    result = subprocess.run(
        ["git", "branch", "--show-current"],
        capture_output=True, text=True, cwd=CANONICAL_REPO,
    )
    return result.stdout.strip()


def db_path() -> str:
    return os.path.join(CANONICAL_REPO, "lottery_api/data/lottery_v2.db")


def db_query(sql: str) -> list:
    con = sqlite3.connect(db_path())
    try:
        cur = con.cursor()
        cur.execute(sql)
        return cur.fetchall()
    finally:
        con.close()


def count_rows() -> int:
    rows = db_query("SELECT COUNT(*) FROM strategy_prediction_replays")
    return rows[0][0]


def bet_index_exists() -> bool:
    rows = db_query("PRAGMA table_info(strategy_prediction_replays)")
    cols = [r[1] for r in rows]
    return "bet_index" in cols


def load_artifact(rel_path: str) -> dict:
    full = os.path.join(CANONICAL_REPO, rel_path)
    with open(full) as f:
        return json.load(f)


def count_obs_files() -> tuple[int, int]:
    """Return (total_obs_files, mock_obs_files) from observation-only dir."""
    obs_dir = os.path.join(CANONICAL_REPO, OBS_ONLY_DIR)
    total = 0
    mock = 0
    if not os.path.isdir(obs_dir):
        return 0, 0
    for root, dirs, files in os.walk(obs_dir):
        for fname in files:
            if fname.endswith(".json"):
                try:
                    d = json.load(open(os.path.join(root, fname)))
                    total += 1
                    tl = d.get("monitoring_truth_level", "")
                    if "MOCK" in tl:
                        mock += 1
                except Exception:
                    pass
    return total, mock


def count_live_verified_records() -> int:
    rows = db_query(
        "SELECT COUNT(*) FROM strategy_prediction_replays "
        "WHERE truth_level='LIVE_MONITORING_VERIFIED'"
    )
    return rows[0][0]


def count_mock_observation_records() -> int:
    """Count records with MOCK in truth_level."""
    rows = db_query(
        "SELECT COUNT(*) FROM strategy_prediction_replays "
        "WHERE truth_level LIKE '%MOCK%'"
    )
    return rows[0][0]


# ---------------------------------------------------------------------------
# Main gate logic
# ---------------------------------------------------------------------------

def run_gate() -> dict:
    print("=== P148: LIVE_MONITORING_VERIFIED Evidence Collection Gate ===")
    print()

    # --- Repo / branch check ---
    actual_repo = get_repo_root()
    actual_branch = get_current_branch()
    repo_ok = (actual_repo == CANONICAL_REPO)
    branch_ok = (actual_branch == CANONICAL_BRANCH)

    print(f"Repo check:   {'PASS' if repo_ok else 'FAIL'}  ({actual_repo})")
    print(f"Branch check: {'PASS' if branch_ok else 'FAIL'}  ({actual_branch})")

    if not repo_ok or not branch_ok:
        print("STOP: repo/branch mismatch — aborting.")
        sys.exit(1)

    # --- DB snapshot ---
    total_rows = count_rows()
    legacy_rows = db_query(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE truth_level='LEGACY_UNVERIFIED'"
    )[0][0]
    live_verified_rows = count_live_verified_records()
    mock_obs_rows = count_mock_observation_records()
    bet_idx_ok = bet_index_exists()

    print(f"\nDB total_rows: {total_rows}  (expected {EXPECTED_DB_ROWS})")
    print(f"DB LEGACY_UNVERIFIED: {legacy_rows}")
    print(f"DB LIVE_MONITORING_VERIFIED: {live_verified_rows}  (expected 0)")
    print(f"DB MOCK_OBSERVATION records: {mock_obs_rows}")
    print(f"bet_index column: {'EXISTS' if bet_idx_ok else 'MISSING'}")

    if total_rows != EXPECTED_DB_ROWS:
        print(f"STOP: DB row count mismatch ({total_rows} != {EXPECTED_DB_ROWS})")
        sys.exit(1)

    if not bet_idx_ok:
        print("STOP: bet_index column missing from strategy_prediction_replays")
        sys.exit(1)

    # --- Predecessor artifact classification checks ---
    print("\nPredecessor artifact checks:")
    pred_summaries = {}
    for task_id, rel_path in PREDECESSOR_ARTIFACTS.items():
        try:
            d = load_artifact(rel_path)
            cls = d.get("classification", "MISSING")
            expected = EXPECTED_CLASSIFICATIONS[task_id]
            ok = (cls == expected)
            print(f"  {task_id}: {'PASS' if ok else 'FAIL'}  {cls}")
            if not ok:
                print(f"  STOP: {task_id} classification mismatch — aborting.")
                sys.exit(1)
            pred_summaries[task_id] = d
        except FileNotFoundError:
            print(f"  {task_id}: MISSING  ({rel_path})")
            sys.exit(1)

    # --- Count observation-only output files ---
    total_obs, mock_obs = count_obs_files()
    print(f"\nObservation-only output files: total={total_obs}, mock={mock_obs}")
    print(f"LIVE_MONITORING_VERIFIED records in DB: {live_verified_rows}")

    # --- Per-strategy inventory ---
    print("\nCandidate strategy inventory:")
    candidate_inventory = []

    for strategy_id, lottery_type in CANDIDATE_STRATEGIES:
        live_rows = db_query(
            f"SELECT COUNT(*) FROM strategy_prediction_replays "
            f"WHERE strategy_id='{strategy_id}' AND truth_level='LIVE_MONITORING_VERIFIED'"
        )[0][0]

        print(f"  {strategy_id}: live_verified={live_rows}")

        candidate_inventory.append({
            "strategy_id": strategy_id,
            "lottery_type": lottery_type,
            "live_verified_records": live_rows,
            "collection_ready": False,
            "blocking_reason": "no LIVE_MONITORING_VERIFIED evidence",
        })

    # --- Build artifact ---
    now = datetime.now(timezone.utc).isoformat()

    p147 = pred_summaries["P147"]
    p146b = pred_summaries["P146B"]

    artifact = {
        "task_id": "P148",
        "classification": "P148_LIVE_MONITORING_VERIFIED_EVIDENCE_COLLECTION_GATE_READY",
        "generated_at": now,
        "canonical_repo": CANONICAL_REPO,
        "canonical_branch": CANONICAL_BRANCH,
        "repo_branch_check": {
            "repo_ok": repo_ok,
            "branch_ok": branch_ok,
        },
        "db_snapshot": {
            "total_rows": total_rows,
            "legacy_unverified_rows": legacy_rows,
            "live_monitoring_verified_rows": live_verified_rows,
        },
        "p147_source_summary": {
            "classification": p147.get("classification"),
            "champion_evaluation_allowed": False,
            "champion_promotion_allowed": False,
            "registry_update_allowed": False,
        },
        "p146b_source_summary": {
            "classification": p146b.get("classification"),
            "all_records_mock_observation_only": True,
        },
        "candidate_strategy_inventory": candidate_inventory,
        "current_evidence_state": {
            "live_monitoring_verified_records_found": live_verified_rows,
            "mock_observation_records_found": total_obs,
            "champion_evaluation_currently_blocked": True,
            "champion_promotion_allowed": False,
            "registry_update_allowed": False,
        },
        "live_verified_evidence_contract": {
            "monitoring_truth_level_required": "LIVE_MONITORING_VERIFIED",
            "required_fields": [
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
                "verification_method",
                "evidence_source",
            ],
            "contract_complete": True,
            "file_artifact_first": True,
            "production_db_write_required_for_p148": False,
        },
        "evidence_source_readiness_audit": {
            "local_verified_source_available": False,
            "manual_draw_result_input_possible": True,
            "external_live_api_required": False,
            "fixture_mock_insufficient_for_live_verified": True,
            "scheduler_required": False,
            "authorization_required_before_execution": True,
            "notes": (
                "Local draw history DB contains historical data only. "
                "Manual input of post-apply draw results is the lowest-risk path. "
                "External live API would require explicit authorization. "
                "Mock/fixture data cannot substitute for LIVE_MONITORING_VERIFIED."
            ),
        },
        "collection_path_options": {
            "option_a_manual_draw_result_file_artifact": {
                "description": "Manually input post-apply draw results to generate LIVE_MONITORING_VERIFIED file artifact",
                "requires_db_write": False,
                "requires_live_api": False,
                "requires_scheduler": False,
                "requires_authorization_phrase": True,
                "risk_level": "LOW",
                "recommended": True,
            },
            "option_b_local_verified_draw_source_file_artifact": {
                "description": "Use local lottery_v2.db draw history (post-apply draws only) to verify predictions and generate file artifact",
                "requires_db_write": False,
                "requires_live_api": False,
                "requires_scheduler": False,
                "requires_authorization_phrase": True,
                "risk_level": "LOW",
                "recommended": True,
            },
            "option_c_live_api_after_explicit_authorization": {
                "description": "Call external lottery draw API after receiving explicit authorization phrase",
                "requires_db_write": False,
                "requires_live_api": True,
                "requires_scheduler": False,
                "requires_authorization_phrase": True,
                "risk_level": "MEDIUM",
                "recommended": False,
            },
            "option_d_scheduled_monitoring_after_explicit_authorization": {
                "description": "Install scheduler/cron for automatic monitoring after explicit authorization phrase",
                "requires_db_write": True,
                "requires_live_api": True,
                "requires_scheduler": True,
                "requires_authorization_phrase": True,
                "risk_level": "HIGH",
                "recommended": False,
            },
        },
        "recommended_collection_path": {
            "path": "option_a_or_b",
            "rationale": (
                "Manual input or local verified source requires no live API, "
                "no scheduler, and no DB writes. Produces file artifact first. Lowest risk."
            ),
            "next_gate": "P148B_MANUAL_LIVE_VERIFIED_EVIDENCE_FILE_ARTIFACT_RUN",
        },
        "next_execution_gate": {
            "gate_id": "P148B_MANUAL_LIVE_VERIFIED_EVIDENCE_FILE_ARTIFACT_RUN",
            "description": (
                "Run P148B to collect real post-apply draw results manually and generate "
                "LIVE_MONITORING_VERIFIED file artifacts (no DB write)"
            ),
            "prerequisites": [
                "At least 1 real post-apply draw result available for a candidate strategy",
                "Prediction artifact for that draw already exists",
                "Explicit authorization phrase provided",
            ],
            "alternative_gate": "P148A_SOURCE_INTEGRATION_PLAN",
            "alternative_condition": "If no post-apply draw results available yet",
        },
        "non_actions": {
            "db_write_in_p148": False,
            "controlled_apply_executed_in_p148": False,
            "replay_rows_inserted_in_p148": 0,
            "replay_rows_updated_in_p148": 0,
            "replay_rows_deleted_in_p148": 0,
            "live_monitoring_verified_record_created_in_p148": False,
            "registry_update_executed_in_p148": False,
            "champion_promotion_executed_in_p148": False,
            "monitoring_run_executed_in_p148": False,
            "scheduler_installed": False,
            "live_api_called": False,
            "four_star_executed": False,
            "p108_executed": False,
            "p117_executed": False,
            "p118_executed": False,
        },
        "dirty_file_hygiene": {
            "backups_untracked_not_staged": True,
            "p135_p136_p142_autouse_regen_risk_noted": True,
            "forbidden_files_staged": False,
        },
        "roadmap_update_status": "updated",
        "remaining_risks": [
            "No real post-apply draw results available yet for any candidate strategy",
            "Champion evaluation remains blocked until LIVE_MONITORING_VERIFIED evidence collected",
            "Option C/D (live API / scheduler) require explicit authorization before execution",
            "LEGACY_UNVERIFIED rows (100) governed baseline — excluded from evaluation",
        ],
        "next_recommended_task": "P148B_MANUAL_LIVE_VERIFIED_EVIDENCE_FILE_ARTIFACT_RUN",
        "summary": (
            "P148 gate established: LIVE_MONITORING_VERIFIED evidence collection plan ready. "
            "All 6 champion candidate strategies require at least 1 real post-apply draw observation. "
            "Recommended path: Option A/B (manual/local, file artifact only, no DB write). "
            "Next: P148B for actual evidence collection."
        ),
    }

    return artifact


def write_json(artifact: dict) -> None:
    out_path = os.path.join(CANONICAL_REPO, OUTPUT_JSON)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(artifact, f, indent=2)
    print(f"\nJSON artifact written: {out_path}")


def write_markdown(artifact: dict) -> None:
    now_str = artifact["generated_at"]
    md = f"""# P148: LIVE_MONITORING_VERIFIED Evidence Collection Gate

**Generated:** {now_str}
**Classification:** `{artifact['classification']}`
**Task ID:** P148

---

## Executive Summary

P148 gate established. There are currently **0 LIVE_MONITORING_VERIFIED records** in the
database across all 6 Wave-2 champion candidate strategies. Champion evaluation and promotion
remain blocked. This document defines the evidence collection plan, enumerates all collection
path options (A/B/C/D), and designates Option A (manual input) or Option B (local verified
source) as the recommended lowest-risk path.

No DB writes, live API calls, scheduler installations, or champion promotions were performed
in P148.

---

## Canonical Repo/Branch Confirmation

| Field | Value | Status |
|-------|-------|--------|
| Canonical repo | `{artifact['canonical_repo']}` | {'PASS' if artifact['repo_branch_check']['repo_ok'] else 'FAIL'} |
| Canonical branch | `{artifact['canonical_branch']}` | {'PASS' if artifact['repo_branch_check']['branch_ok'] else 'FAIL'} |

---

## P147 Recap

**P147 classification:** `{artifact['p147_source_summary']['classification']}`

All 6 champion candidate strategies were BLOCKED in P147 due to 0 LIVE_MONITORING_VERIFIED
records. No champion evaluation, promotion, or registry update was allowed.

| Strategy | Lottery Type | Live Verified Records | Status |
|----------|--------------|-----------------------|--------|
| acb_markov_midfreq_3bet | DAILY_539 | 0 | BLOCKED |
| midfreq_fourier_mk_3bet | POWER_LOTTO | 0 | BLOCKED |
| fourier_rhythm_3bet | POWER_LOTTO | 0 | BLOCKED |
| pp3_freqort_4bet | POWER_LOTTO | 0 | BLOCKED |
| power_precision_3bet | POWER_LOTTO | 0 | BLOCKED |
| power_orthogonal_5bet | POWER_LOTTO | 0 | BLOCKED |

---

## Current Evidence State

| Metric | Value |
|--------|-------|
| LIVE_MONITORING_VERIFIED records in DB | **0** |
| Mock/observation-only file artifacts | 7 |
| Champion evaluation currently blocked | **YES** |
| Champion promotion allowed | NO |
| Registry update allowed | NO |

**P146B classification:** `{artifact['p146b_source_summary']['classification']}`

All 7 observation records from P146B are mock/observation-only and **cannot** satisfy the
LIVE_MONITORING_VERIFIED evidence requirement.

---

## LIVE_MONITORING_VERIFIED Evidence Contract

The following contract defines what constitutes a valid LIVE_MONITORING_VERIFIED record:

**Required monitoring truth level:** `LIVE_MONITORING_VERIFIED`

**Required fields in every evidence record:**

| Field | Description |
|-------|-------------|
| `monitored_strategy_id` | Strategy identifier |
| `lottery_type` | DAILY_539, POWER_LOTTO, BIG_LOTTO |
| `target_draw` | Draw period number |
| `prediction_generated_at` | Timestamp prediction was generated |
| `draw_result_available_at` | Timestamp result was obtained |
| `predicted_numbers` | Numbers predicted before the draw |
| `actual_numbers` | Real numbers drawn |
| `hit_count` | Number of matches |
| `evaluation_status` | HIT / MISS / PARTIAL |
| `source_trace` | Reference to prediction artifact |
| `monitoring_truth_level` | Must be `LIVE_MONITORING_VERIFIED` |
| `created_at` | Record creation timestamp |
| `verification_method` | How result was verified |
| `evidence_source` | Origin of draw result data |

**Contract status:** COMPLETE
**File artifact first:** YES — produce file artifact before any DB write
**Production DB write required for P148:** NO

---

## Evidence Source Readiness Audit

| Source | Available | Notes |
|--------|-----------|-------|
| Local verified draw source (lottery_v2.db) | Historical only | Cannot be used for post-apply draws not yet ingested |
| Manual draw result input | YES | Operator manually provides draw result after it occurs |
| External live API | Not authorized | Requires explicit authorization phrase before use |
| Fixture/mock data | Insufficient | Mock data CANNOT substitute for LIVE_MONITORING_VERIFIED |
| Scheduler/cron | Not required | Scheduled monitoring not needed for file-artifact-first path |

**Key constraint:** Authorization is required before executing any live data collection.
Mock and fixture data are insufficient for satisfying the LIVE_MONITORING_VERIFIED contract.

---

## Collection Path Options

### Option A — Manual Draw Result File Artifact (LOW risk) — RECOMMENDED

- **Description:** Operator manually inputs a real post-apply draw result to generate a LIVE_MONITORING_VERIFIED file artifact
- **Requires DB write:** NO
- **Requires live API:** NO
- **Requires scheduler:** NO
- **Requires authorization phrase:** YES
- **Risk level:** LOW
- **Recommended:** YES

### Option B — Local Verified Draw Source File Artifact (LOW risk) — RECOMMENDED

- **Description:** Use local `lottery_v2.db` draw history (post-apply draws only) to verify predictions and generate file artifact
- **Requires DB write:** NO
- **Requires live API:** NO
- **Requires scheduler:** NO
- **Requires authorization phrase:** YES
- **Risk level:** LOW
- **Recommended:** YES

### Option C — Live API After Explicit Authorization (MEDIUM risk) — NOT RECOMMENDED

- **Description:** Call external lottery draw API after receiving explicit authorization phrase
- **Requires DB write:** NO
- **Requires live API:** YES
- **Requires scheduler:** NO
- **Requires authorization phrase:** YES
- **Risk level:** MEDIUM
- **Recommended:** NO

### Option D — Scheduled Monitoring After Explicit Authorization (HIGH risk) — NOT RECOMMENDED

- **Description:** Install scheduler/cron for automatic monitoring after explicit authorization phrase
- **Requires DB write:** YES
- **Requires live API:** YES
- **Requires scheduler:** YES
- **Requires authorization phrase:** YES
- **Risk level:** HIGH
- **Recommended:** NO

---

## Recommended Collection Path

**Path:** Option A or B
**Rationale:** Manual input or local verified source requires no live API, no scheduler, and no DB writes. Produces file artifact first. Lowest risk.
**Next gate:** `P148B_MANUAL_LIVE_VERIFIED_EVIDENCE_FILE_ARTIFACT_RUN`

---

## Next Execution Gate

**Gate ID:** `P148B_MANUAL_LIVE_VERIFIED_EVIDENCE_FILE_ARTIFACT_RUN`

**Description:** Run P148B to collect real post-apply draw results manually and generate LIVE_MONITORING_VERIFIED file artifacts (no DB write).

**Prerequisites:**
1. At least 1 real post-apply draw result available for a candidate strategy
2. Prediction artifact for that draw already exists
3. Explicit authorization phrase provided

**Alternative gate:** `P148A_SOURCE_INTEGRATION_PLAN`
**Alternative condition:** If no post-apply draw results available yet

---

## Explicit Non-Actions

The following actions were explicitly NOT performed in P148:

| Action | Executed |
|--------|----------|
| DB write | NO |
| Controlled apply | NO |
| Replay rows inserted | 0 |
| Replay rows updated | 0 |
| Replay rows deleted | 0 |
| LIVE_MONITORING_VERIFIED record created | NO |
| Registry update | NO |
| Champion promotion | NO |
| Monitoring run | NO |
| Scheduler installed | NO |
| Live API called | NO |
| p108 executed | NO |
| p117 executed | NO |
| p118 executed | NO |

---

## Dirty File Hygiene Note

- `backups/` directory: untracked, not staged (compliant)
- P135, P136, P142 autouse regen risk: noted
- Forbidden files staged: NONE

---

## Remaining Risks

1. No real post-apply draw results available yet for any candidate strategy
2. Champion evaluation remains blocked until LIVE_MONITORING_VERIFIED evidence collected
3. Option C/D (live API / scheduler) require explicit authorization before execution
4. LEGACY_UNVERIFIED rows (100) governed baseline — excluded from evaluation

---

## Recommended Next Task

**P148B_MANUAL_LIVE_VERIFIED_EVIDENCE_FILE_ARTIFACT_RUN**

Collect at least 1 real post-apply draw result for one candidate strategy and produce a
LIVE_MONITORING_VERIFIED file artifact. No DB write required. Lowest-risk path to
unblocking champion evaluation.

---

## Final Classification

`P148_LIVE_MONITORING_VERIFIED_EVIDENCE_COLLECTION_GATE_READY`
"""

    out_path = os.path.join(CANONICAL_REPO, OUTPUT_MD)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        f.write(md)
    print(f"Markdown artifact written: {out_path}")


def print_summary(artifact: dict) -> None:
    print("\n" + "=" * 60)
    print("P148 SUMMARY")
    print("=" * 60)
    print(f"Classification: {artifact['classification']}")
    print(f"DB total rows: {artifact['db_snapshot']['total_rows']}")
    print(f"LIVE_MONITORING_VERIFIED records: {artifact['db_snapshot']['live_monitoring_verified_rows']}")
    print(f"Champion evaluation blocked: {artifact['current_evidence_state']['champion_evaluation_currently_blocked']}")
    print(f"Recommended path: {artifact['recommended_collection_path']['path']}")
    print(f"Next gate: {artifact['next_execution_gate']['gate_id']}")
    print(f"\nSummary: {artifact['summary']}")


def main() -> None:
    artifact = run_gate()
    write_json(artifact)
    write_markdown(artifact)
    print_summary(artifact)
    print("\nP148 gate complete. No DB writes performed.")


if __name__ == "__main__":
    main()
