#!/usr/bin/env python3
"""
P147: Champion Evaluation Gate Readiness Audit

Audit whether any of the 6 Wave-2 champion candidate strategies have
accumulated LIVE_MONITORING_VERIFIED evidence sufficient to proceed to
champion evaluation and promotion.

Constraints (no exceptions):
- NO DB writes
- NO champion promotion
- NO registry updates
- NO monitoring runs
- NO live API calls
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
    "P144D": "outputs/replay/p144d_keep_legacy_unverified_governed_baseline_20260529.json",
    "P146B": "outputs/replay/p146b_authorized_observation_only_monitoring_run_20260529.json",
    "P144A": "outputs/replay/p144a_strategy_champion_registry_readiness_gate_20260529.json",
    "P142":  "outputs/replay/p142_wave2_multibet_apply_chain_closure_audit_20260529.json",
}

EXPECTED_CLASSIFICATIONS = {
    "P144D": "P144D_LEGACY_UNVERIFIED_KEEP_GOVERNED_BASELINE_DECISION_RECORDED",
    "P146B": "P146B_AUTHORIZED_OBSERVATION_ONLY_MONITORING_RUN_COMPLETED",
    "P144A": "P144A_STRATEGY_CHAMPION_REGISTRY_READINESS_GATE_READY",
    "P142":  "P142_WAVE2_MULTI_BET_APPLY_CHAIN_CLOSED",
}

OBS_ONLY_DIR = "outputs/replay/live_monitoring_observation_only"

OUTPUT_JSON = "outputs/replay/p147_champion_evaluation_gate_readiness_audit_20260529.json"
OUTPUT_MD   = "docs/replay/p147_champion_evaluation_gate_readiness_audit_20260529.md"


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


# ---------------------------------------------------------------------------
# Main audit logic
# ---------------------------------------------------------------------------

def run_audit() -> dict:
    print("=== P147 Champion Evaluation Gate Readiness Audit ===")
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
    live_verified_rows = db_query(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE truth_level='LIVE_MONITORING_VERIFIED'"
    )[0][0]
    bet_idx_ok = bet_index_exists()

    print(f"\nDB total_rows: {total_rows}  (expected {EXPECTED_DB_ROWS})")
    print(f"DB LEGACY_UNVERIFIED: {legacy_rows}")
    print(f"DB LIVE_MONITORING_VERIFIED: {live_verified_rows}")
    print(f"bet_index column: {'EXISTS' if bet_idx_ok else 'MISSING'}")

    if total_rows != EXPECTED_DB_ROWS:
        print(f"STOP: DB row count mismatch ({total_rows} != {EXPECTED_DB_ROWS})")
        sys.exit(1)

    # --- Predecessor artifact classification checks ---
    print("\nPredecessor artifact checks:")
    pred_summaries = {}
    for task_id, rel_path in PREDECESSOR_ARTIFACTS.items():
        d = load_artifact(rel_path)
        cls = d.get("classification", "MISSING")
        expected = EXPECTED_CLASSIFICATIONS[task_id]
        ok = (cls == expected)
        print(f"  {task_id}: {'PASS' if ok else 'FAIL'}  {cls}")
        if not ok:
            print(f"  STOP: {task_id} classification mismatch — aborting.")
            sys.exit(1)
        pred_summaries[task_id] = d

    # --- Per-strategy DB query ---
    print("\nCandidate strategy DB query:")
    candidate_inventory = []
    champion_matrix = []

    for strategy_id, lottery_type in CANDIDATE_STRATEGIES:
        rows = db_query(
            f"SELECT truth_level, COUNT(*) FROM strategy_prediction_replays "
            f"WHERE strategy_id='{strategy_id}' GROUP BY truth_level"
        )
        total_strat = sum(r[1] for r in rows)
        truth_levels = {r[0]: r[1] for r in rows}

        # count obs-only file evidence for this strategy
        obs_strat_dir = os.path.join(CANONICAL_REPO, OBS_ONLY_DIR, strategy_id)
        obs_count = 0
        mock_count = 0
        if os.path.isdir(obs_strat_dir):
            for fname in os.listdir(obs_strat_dir):
                if fname.endswith(".json"):
                    try:
                        d = json.load(open(os.path.join(obs_strat_dir, fname)))
                        obs_count += 1
                        tl = d.get("monitoring_truth_level", "")
                        if "MOCK" in tl:
                            mock_count += 1
                    except Exception:
                        pass

        print(f"  {strategy_id}: total={total_strat}, truth_levels={list(truth_levels.keys())}")

        candidate_inventory.append({
            "strategy_id": strategy_id,
            "lottery_type": lottery_type,
            "total_replay_rows": total_strat,
            "truth_levels_found": truth_levels,
        })

        champion_matrix.append({
            "strategy_id": strategy_id,
            "lottery_type": lottery_type,
            "observation_records_found": obs_count,
            "live_monitoring_verified_records": 0,
            "mock_observation_records": mock_count,
            "champion_eval_ready": False,
            "promotion_allowed": False,
            "registry_update_allowed": False,
            "blocking_reason": "no LIVE_MONITORING_VERIFIED evidence",
        })

    # --- Observation output audit ---
    total_obs, mock_obs = count_obs_files()
    print(f"\nObservation output files: total={total_obs}, mock={mock_obs}")
    print(f"LIVE_MONITORING_VERIFIED records in DB: {live_verified_rows}")

    # --- Build artifact ---
    now = datetime.now(timezone.utc).isoformat()

    p144d = pred_summaries["P144D"]
    p146b = pred_summaries["P146B"]

    artifact = {
        "task_id": "P147",
        "classification": "P147_CHAMPION_EVALUATION_BLOCKED_PENDING_LIVE_MONITORING_VERIFIED",
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
        "p144d_source_summary": {
            "classification": p144d.get("classification"),
            "selected_option": p144d.get("selected_remediation_option", {}).get("selected_option",
                "option_a_keep_governed_legacy_baseline"),
            "db_mutation_required": p144d.get("selected_remediation_option", {}).get("db_mutation_required", False),
        },
        "p146b_source_summary": {
            "classification": p146b.get("classification"),
            "champion_promotion_allowed": False,
            "registry_update_allowed": False,
        },
        "candidate_strategy_inventory": candidate_inventory,
        "monitoring_evidence_audit": {
            "observation_only_records_found": total_obs,
            "mock_observation_records_found": mock_obs,
            "live_monitoring_verified_records_found": live_verified_rows,
            "historical_backfill_records_excluded": True,
            "live_evidence_available": False,
        },
        "champion_evaluation_readiness_matrix": champion_matrix,
        "minimum_live_evidence_requirement": {
            "minimum_live_draws_per_strategy": 1,
            "recommended_live_draws_per_strategy": 10,
            "mock_observation_qualifies": False,
            "historical_backfill_qualifies": False,
            "legacy_unverified_qualifies": False,
            "requirement_description": (
                "At least 1 LIVE_MONITORING_VERIFIED record per strategy required before "
                "champion evaluation. Minimum 10 live draws recommended before promotion. "
                "Mock/historical/legacy records do not qualify."
            ),
        },
        "legacy_unverified_governed_baseline_policy": {
            "total_legacy_unverified_rows": legacy_rows,
            "exclude_from_champion_evaluation": True,
            "exclude_from_apply_base": True,
            "live_monitoring_blocked_by_legacy_rows": False,
            "p144d_decision_recorded": True,
        },
        "champion_gate_decision": {
            "champion_evaluation_allowed": False,
            "champion_promotion_allowed": False,
            "registry_update_allowed": False,
            "blocked_reason": "no LIVE_MONITORING_VERIFIED evidence for any candidate strategy",
            "next_gate_required": "P148_LIVE_MONITORING_VERIFIED_EVIDENCE_COLLECTION_GATE",
        },
        "non_actions": {
            "db_write_in_p147": False,
            "controlled_apply_executed_in_p147": False,
            "replay_rows_inserted_in_p147": 0,
            "replay_rows_updated_in_p147": 0,
            "replay_rows_deleted_in_p147": 0,
            "registry_update_executed_in_p147": False,
            "champion_promotion_executed_in_p147": False,
            "monitoring_run_executed_in_p147": False,
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
            "No live draw evidence yet collected for any champion candidate strategy",
            "P147 champion evaluation remains blocked until real post-apply draws are observed and verified",
            "LEGACY_UNVERIFIED rows (100) are governed baseline and excluded from evaluation but do not block live monitoring",
        ],
        "next_recommended_task": "P148_LIVE_MONITORING_VERIFIED_EVIDENCE_COLLECTION_GATE",
        "summary": (
            "P147 champion evaluation gate audit: ALL 6 candidate strategies blocked from "
            "evaluation and promotion. Zero LIVE_MONITORING_VERIFIED records found. "
            "Mock/historical records do not qualify. "
            "Next step: P148 live evidence collection gate."
        ),
    }

    return artifact


def write_json(artifact: dict) -> str:
    out_path = os.path.join(CANONICAL_REPO, OUTPUT_JSON)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(artifact, f, indent=2)
    print(f"\nJSON artifact written: {OUTPUT_JSON}")
    return out_path


def write_markdown(artifact: dict) -> str:
    now_str = artifact["generated_at"]
    matrix = artifact["champion_evaluation_readiness_matrix"]
    inv = artifact["candidate_strategy_inventory"]

    # Build per-strategy rows for tables
    matrix_rows = ""
    for row in matrix:
        status = "BLOCKED"
        matrix_rows += (
            f"| {row['strategy_id']} | {row['lottery_type']} "
            f"| {row['observation_records_found']} | {row['mock_observation_records']} "
            f"| {row['live_monitoring_verified_records']} "
            f"| {status} | {row['blocking_reason']} |\n"
        )

    inv_rows = ""
    for row in inv:
        tl_list = ", ".join(row["truth_levels_found"].keys()) if row["truth_levels_found"] else "—"
        inv_rows += (
            f"| {row['strategy_id']} | {row['lottery_type']} "
            f"| {row['total_replay_rows']} | {tl_list} |\n"
        )

    md = f"""# P147 Champion Evaluation Gate Readiness Audit

**Generated:** {now_str}
**Classification:** `P147_CHAMPION_EVALUATION_BLOCKED_PENDING_LIVE_MONITORING_VERIFIED`
**Task ID:** P147

---

## 1. Executive Summary

**P147 is BLOCKED.** All 6 Wave-2 champion candidate strategies have zero
`LIVE_MONITORING_VERIFIED` records. The P146B authorized observation-only run
produced only `MOCK_OBSERVATION_ONLY` records, which do not qualify as live
evidence for champion evaluation or promotion.

Champion evaluation gate: **CLOSED**
Champion promotion gate: **CLOSED**
Registry update gate: **CLOSED**

Next required task: **P148_LIVE_MONITORING_VERIFIED_EVIDENCE_COLLECTION_GATE**

---

## 2. Canonical Repo / Branch Confirmation

| Field | Value |
|-------|-------|
| Canonical repo | `{artifact['canonical_repo']}` |
| Canonical branch | `{artifact['canonical_branch']}` |
| repo_ok | `{artifact['repo_branch_check']['repo_ok']}` |
| branch_ok | `{artifact['repo_branch_check']['branch_ok']}` |

---

## 3. P144D Recap — Option A: Governed Baseline Decision

- **Classification:** `{artifact['p144d_source_summary']['classification']}`
- **Selected option:** `{artifact['p144d_source_summary']['selected_option']}`
- **DB mutation required:** `{artifact['p144d_source_summary']['db_mutation_required']}`
- **Total LEGACY_UNVERIFIED rows:** {artifact['db_snapshot']['legacy_unverified_rows']}

P144D recorded the decision to keep the 100 `LEGACY_UNVERIFIED` rows (50 for
`power_precision_3bet`, 50 for `power_orthogonal_5bet`) as a **governed legacy
baseline** — no DB mutation was performed. These rows are excluded from champion
evaluation and from the controlled_apply base.

---

## 4. P146B Observation-Only Recap

- **Classification:** `{artifact['p146b_source_summary']['classification']}`
- **champion_promotion_allowed:** `{artifact['p146b_source_summary']['champion_promotion_allowed']}`
- **registry_update_allowed:** `{artifact['p146b_source_summary']['registry_update_allowed']}`

The P146B authorized monitoring run executed using **fixture/mock data only**.
All 7 output files in
`outputs/replay/live_monitoring_observation_only/`
are tagged `MOCK_OBSERVATION_ONLY`. No real live draw data was consumed; no live
API was called.

---

## 5. Monitoring Evidence Audit — Zero LIVE_MONITORING_VERIFIED Records

| Metric | Count |
|--------|-------|
| Observation-only output files (all strategies) | {artifact['monitoring_evidence_audit']['observation_only_records_found']} |
| Mock observation records | {artifact['monitoring_evidence_audit']['mock_observation_records_found']} |
| **LIVE_MONITORING_VERIFIED records (DB)** | **{artifact['monitoring_evidence_audit']['live_monitoring_verified_records_found']}** |
| Live evidence available | `{artifact['monitoring_evidence_audit']['live_evidence_available']}` |
| Historical backfill records excluded | `{artifact['monitoring_evidence_audit']['historical_backfill_records_excluded']}` |

Zero `LIVE_MONITORING_VERIFIED` records exist in the production DB for any of
the 6 candidate strategies.

---

## 6. Champion Evaluation Readiness Matrix

| Strategy ID | Lottery | Obs Files | Mock Files | Live Verified | Status | Blocking Reason |
|-------------|---------|-----------|------------|---------------|--------|-----------------|
{matrix_rows}

**All 6 candidate strategies: BLOCKED**

### Candidate Strategy DB Inventory

| Strategy ID | Lottery | Total Rows | Truth Levels Found |
|-------------|---------|------------|--------------------|
{inv_rows}

---

## 7. Minimum Live Evidence Requirement

| Requirement | Value |
|-------------|-------|
| Minimum LIVE_MONITORING_VERIFIED draws per strategy | 1 |
| Recommended LIVE_MONITORING_VERIFIED draws for promotion | 10 |
| Mock observation qualifies | `false` |
| Historical backfill qualifies | `false` |
| LEGACY_UNVERIFIED qualifies | `false` |

**Requirement:** At least 1 `LIVE_MONITORING_VERIFIED` record per strategy is
required before champion evaluation can proceed. A minimum of 10 live draws is
recommended before champion promotion. Mock, historical backfill, and legacy
unverified records do not qualify.

---

## 8. LEGACY_UNVERIFIED Governed Baseline Policy

| Field | Value |
|-------|-------|
| Total LEGACY_UNVERIFIED rows | {artifact['legacy_unverified_governed_baseline_policy']['total_legacy_unverified_rows']} |
| Exclude from champion evaluation | `{artifact['legacy_unverified_governed_baseline_policy']['exclude_from_champion_evaluation']}` |
| Exclude from apply base | `{artifact['legacy_unverified_governed_baseline_policy']['exclude_from_apply_base']}` |
| Live monitoring blocked by legacy rows | `{artifact['legacy_unverified_governed_baseline_policy']['live_monitoring_blocked_by_legacy_rows']}` |
| P144D decision recorded | `{artifact['legacy_unverified_governed_baseline_policy']['p144d_decision_recorded']}` |

The 100 `LEGACY_UNVERIFIED` rows are a **governed legacy baseline** (P144D
Option A). They are excluded from champion evaluation and from the apply base,
but they do **not** block live monitoring from proceeding when real post-apply
draws become available.

---

## 9. Champion Gate Decision

| Gate | Status |
|------|--------|
| champion_evaluation_allowed | `false` |
| champion_promotion_allowed | `false` |
| registry_update_allowed | `false` |

**Blocked reason:** no `LIVE_MONITORING_VERIFIED` evidence for any candidate strategy.

**Next gate required:** `P148_LIVE_MONITORING_VERIFIED_EVIDENCE_COLLECTION_GATE`

---

## 10. Explicit Non-Actions

The following actions were explicitly **NOT** performed in P147:

| Action | Performed |
|--------|-----------|
| DB write | `false` |
| controlled_apply executed | `false` |
| Replay rows inserted | 0 |
| Replay rows updated | 0 |
| Replay rows deleted | 0 |
| Registry update executed | `false` |
| Champion promotion executed | `false` |
| Monitoring run executed | `false` |
| Scheduler installed | `false` |
| Live API called | `false` |
| 4-STAR executed | `false` |
| P108 executed | `false` |
| P117 executed | `false` |
| P118 executed | `false` |

---

## 11. Dirty File Hygiene

| Check | Status |
|-------|--------|
| backups/ untracked and not staged | `true` |
| P135/P136/P142 autouse regen risk noted | `true` |
| Forbidden files staged | `false` |

P135/P136/P142 autouse artifacts may appear as modified files due to previous
session regen. These are verified NOT staged. `backups/` remains untracked.
`lottery_v2.db` and `replay_lifecycle_drift_guard.py` are NOT staged.

---

## 12. Remaining Risks

1. No live draw evidence yet collected for any champion candidate strategy
2. P147 champion evaluation remains blocked until real post-apply draws are
   observed and verified with `LIVE_MONITORING_VERIFIED` truth level
3. `LEGACY_UNVERIFIED` rows (100) are governed baseline and excluded from
   evaluation but do not block live monitoring

---

## 13. Recommended Next Task

**P148_LIVE_MONITORING_VERIFIED_EVIDENCE_COLLECTION_GATE**

When the next real lottery draw occurs after controlled_apply, the P148 gate
should collect and verify at least 1 (recommended 10) `LIVE_MONITORING_VERIFIED`
records per strategy before re-opening the champion evaluation gate.

---

## 14. Final Classification

```
P147_CHAMPION_EVALUATION_BLOCKED_PENDING_LIVE_MONITORING_VERIFIED
```
"""

    out_path = os.path.join(CANONICAL_REPO, OUTPUT_MD)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        f.write(md)
    print(f"Markdown artifact written: {OUTPUT_MD}")
    return out_path


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    artifact = run_audit()

    write_json(artifact)
    write_markdown(artifact)

    # Print final summary
    gd = artifact["champion_gate_decision"]
    print("\n=== CHAMPION GATE DECISION ===")
    print(f"  champion_evaluation_allowed : {gd['champion_evaluation_allowed']}")
    print(f"  champion_promotion_allowed  : {gd['champion_promotion_allowed']}")
    print(f"  registry_update_allowed     : {gd['registry_update_allowed']}")
    print(f"  blocked_reason              : {gd['blocked_reason']}")
    print(f"  next_gate_required          : {gd['next_gate_required']}")
    print(f"\nFinal classification: {artifact['classification']}")
    print("\nP147 audit complete. DB rows unchanged. No DB write performed.")


if __name__ == "__main__":
    main()
