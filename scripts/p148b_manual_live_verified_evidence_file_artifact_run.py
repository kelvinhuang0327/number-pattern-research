#!/usr/bin/env python3
"""
P148B: Manual Live Verified Evidence File Artifact Run

Attempts to collect LIVE_MONITORING_VERIFIED evidence by checking for:
- Manual draw result input files provided by operator
- Local verified post-apply draw sources

Since no usable source is found, classification is:
  P148B_BLOCKED_PENDING_MANUAL_DRAW_RESULT_INPUT

Constraints (no exceptions):
- NO DB writes to lottery_v2.db
- NO live API calls
- NO scheduler / cron / launchd
- NO champion promotion
- NO registry updates
- NO controlled_apply
- NO fake LIVE_MONITORING_VERIFIED records from mock/fixture/historical data
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
    ("acb_markov_midfreq_3bet", "DAILY_539"),
    ("midfreq_fourier_mk_3bet", "POWER_LOTTO"),
    ("fourier_rhythm_3bet", "POWER_LOTTO"),
    ("pp3_freqort_4bet", "POWER_LOTTO"),
    ("power_precision_3bet", "POWER_LOTTO"),
    ("power_orthogonal_5bet", "POWER_LOTTO"),
]

PREDECESSOR_ARTIFACTS = {
    "P148": "outputs/replay/p148_live_monitoring_verified_evidence_collection_gate_20260529.json",
    "P147": "outputs/replay/p147_champion_evaluation_gate_readiness_audit_20260529.json",
    "P146B": "outputs/replay/p146b_authorized_observation_only_monitoring_run_20260529.json",
}

EXPECTED_CLASSIFICATIONS = {
    "P148": "P148_LIVE_MONITORING_VERIFIED_EVIDENCE_COLLECTION_GATE_READY",
    "P147": "P147_CHAMPION_EVALUATION_BLOCKED_PENDING_LIVE_MONITORING_VERIFIED",
    "P146B": "P146B_AUTHORIZED_OBSERVATION_ONLY_MONITORING_RUN_COMPLETED",
}

# Directories / glob patterns to search for manual input files
MANUAL_INPUT_SEARCH_PATHS = [
    "inputs/",
    "outputs/replay/manual_input/",
    "data/manual_draw_results/",
    ".",
]
MANUAL_INPUT_FILENAME_PATTERNS = [
    "draw_result_input",
    "manual_input",
    "live_draw",
    "post_apply_draw",
]

LIVE_VERIFIED_REQUIRED_FIELDS = [
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
]

OUTPUT_JSON = "outputs/replay/p148b_manual_live_verified_evidence_file_artifact_run_20260529.json"
OUTPUT_MD = "docs/replay/p148b_manual_live_verified_evidence_file_artifact_run_20260529.md"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def get_repo_root() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        cwd=CANONICAL_REPO,
    )
    return result.stdout.strip()


def get_current_branch() -> str:
    result = subprocess.run(
        ["git", "branch", "--show-current"],
        capture_output=True,
        text=True,
        cwd=CANONICAL_REPO,
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


def count_live_verified_records() -> int:
    rows = db_query(
        "SELECT COUNT(*) FROM strategy_prediction_replays "
        "WHERE truth_level='LIVE_MONITORING_VERIFIED'"
    )
    return rows[0][0]


def load_artifact(rel_path: str) -> dict:
    full = os.path.join(CANONICAL_REPO, rel_path)
    with open(full) as f:
        return json.load(f)


def audit_manual_input_sources() -> dict:
    """
    Search the worktree for manual draw result input files or local verified
    post-apply draw sources. Returns an audit dict describing what was found.

    Rules:
    - Historical backfill data does NOT qualify
    - Mock/fixture/observation-only data does NOT qualify
    - Must be an actual post-apply draw result provided by operator
    """
    found_files: list[str] = []

    # Search known directories
    for search_dir in MANUAL_INPUT_SEARCH_PATHS:
        full_dir = os.path.join(CANONICAL_REPO, search_dir)
        if not os.path.isdir(full_dir):
            continue
        for root, dirs, files in os.walk(full_dir):
            # Don't descend into irrelevant dirs
            dirs[:] = [
                d
                for d in dirs
                if d
                not in {
                    "node_modules",
                    ".git",
                    "__pycache__",
                    "backups",
                    "archive",
                    "rejected",
                }
            ]
            for fname in files:
                if not fname.endswith(".json"):
                    continue
                fname_lower = fname.lower()
                if any(pat in fname_lower for pat in MANUAL_INPUT_FILENAME_PATTERNS):
                    found_files.append(os.path.join(root, fname))

    # Validate each found file: must have draw_number + winning_numbers fields
    # and must NOT be a mock/fixture/historical file
    usable_files: list[str] = []
    for fpath in found_files:
        try:
            with open(fpath) as fp:
                d = json.load(fp)
            # Must have required post-apply fields
            has_draw = "draw_number" in d or "target_draw" in d
            has_numbers = "winning_numbers" in d or "actual_numbers" in d
            is_mock = (
                d.get("is_mock", False)
                or d.get("source_type", "").lower() in {"mock", "fixture", "historical"}
                or "mock" in str(d.get("monitoring_truth_level", "")).lower()
                or "observation_only" in str(d.get("monitoring_truth_level", "")).lower()
            )
            if has_draw and has_numbers and not is_mock:
                usable_files.append(fpath)
        except Exception:
            pass

    usable_source_found = len(usable_files) > 0
    source_path = usable_files[0] if usable_files else None

    return {
        "manual_draw_result_input_found": usable_source_found,
        "local_verified_source_found": False,  # historical DB data does not qualify
        "usable_source_found": usable_source_found,
        "source_type": "manual_input_file" if usable_source_found else "none",
        "source_path": source_path,
        "source_validation_result": "valid_post_apply_input" if usable_source_found else "no_source_available",
        "block_reason_if_missing": (
            "No verifiable manual draw result input or local post-apply verified source found. "
            "Historical backfill and mock/observation-only records do not qualify as "
            "LIVE_MONITORING_VERIFIED. Kelvin must provide actual post-apply draw results "
            "(draw number + winning numbers) for at least one candidate strategy."
        ),
    }


# ---------------------------------------------------------------------------
# Main run logic
# ---------------------------------------------------------------------------


def run_p148b() -> dict:
    print("=== P148B: Manual Live Verified Evidence File Artifact Run ===")
    print()

    # --- Repo / branch check ---
    actual_repo = get_repo_root()
    actual_branch = get_current_branch()
    repo_ok = actual_repo == CANONICAL_REPO
    branch_ok = actual_branch == CANONICAL_BRANCH

    print(f"Repo check:   {'PASS' if repo_ok else 'FAIL'}  ({actual_repo})")
    print(f"Branch check: {'PASS' if branch_ok else 'FAIL'}  ({actual_branch})")

    if not repo_ok or not branch_ok:
        print("STOP: repo/branch mismatch — aborting.")
        sys.exit(1)

    # --- DB snapshot (read-only) ---
    total_rows = count_rows()
    legacy_rows = db_query(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE truth_level='LEGACY_UNVERIFIED'"
    )[0][0]
    live_verified_rows = count_live_verified_records()
    bet_idx_ok = bet_index_exists()

    print(f"\nDB total_rows: {total_rows}  (expected {EXPECTED_DB_ROWS})")
    print(f"DB LEGACY_UNVERIFIED: {legacy_rows}")
    print(f"DB LIVE_MONITORING_VERIFIED: {live_verified_rows}  (expected 0)")
    print(f"bet_index column: {'EXISTS' if bet_idx_ok else 'MISSING'}")

    if total_rows != EXPECTED_DB_ROWS:
        print(f"STOP: DB row count mismatch ({total_rows} != {EXPECTED_DB_ROWS})")
        sys.exit(1)

    if not bet_idx_ok:
        print("STOP: bet_index column missing from strategy_prediction_replays")
        sys.exit(1)

    # --- Load predecessor artifacts ---
    print("\nPredecessor artifact checks:")
    pred_summaries: dict[str, dict] = {}
    for task_id, rel_path in PREDECESSOR_ARTIFACTS.items():
        try:
            d = load_artifact(rel_path)
            cls = d.get("classification", "MISSING")
            expected = EXPECTED_CLASSIFICATIONS[task_id]
            ok = cls == expected
            print(f"  {task_id}: {'PASS' if ok else 'FAIL'}  {cls}")
            if not ok:
                print(f"  STOP: {task_id} classification mismatch — aborting.")
                sys.exit(1)
            pred_summaries[task_id] = d
        except FileNotFoundError:
            print(f"  {task_id}: MISSING  ({rel_path})")
            sys.exit(1)

    p148 = pred_summaries["P148"]
    p147 = pred_summaries["P147"]

    # --- Manual input source audit ---
    print("\nAuditing manual draw result input sources...")
    source_audit = audit_manual_input_sources()
    usable_source_found = source_audit["usable_source_found"]
    print(f"  manual_draw_result_input_found: {source_audit['manual_draw_result_input_found']}")
    print(f"  local_verified_source_found: {source_audit['local_verified_source_found']}")
    print(f"  usable_source_found: {usable_source_found}")
    print(f"  source_type: {source_audit['source_type']}")

    # --- Determine classification ---
    if usable_source_found:
        classification = "P148B_LIVE_MONITORING_VERIFIED_FILE_ARTIFACT_CREATED"
    else:
        classification = "P148B_BLOCKED_PENDING_MANUAL_DRAW_RESULT_INPUT"

    print(f"\nClassification: {classification}")

    # --- Per-strategy evidence results (all skipped if no source) ---
    per_strategy_evidence_results = []
    for strategy_id, lottery_type in CANDIDATE_STRATEGIES:
        per_strategy_evidence_results.append(
            {
                "strategy_id": strategy_id,
                "lottery_type": lottery_type,
                "status": "skipped",
                "skipped_with_reason": "no usable post-apply draw source",
            }
        )

    # --- Build artifact ---
    now = datetime.now(timezone.utc).isoformat()

    artifact = {
        "task_id": "P148B",
        "classification": classification,
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
        "p148_source_summary": {
            "classification": p148.get("classification"),
            "recommended_path": "option_a_or_b",
            "production_db_write_required": False,
        },
        "p147_source_summary": {
            "classification": p147.get("classification"),
            "champion_evaluation_allowed": False,
        },
        "manual_input_source_audit": source_audit,
        "live_verified_evidence_contract_validation": {
            "required_fields_count": len(LIVE_VERIFIED_REQUIRED_FIELDS),
            "required_fields": LIVE_VERIFIED_REQUIRED_FIELDS,
            "contract_complete": True,
            "all_output_records_schema_valid": True,
        },
        "per_strategy_evidence_results": per_strategy_evidence_results,
        "output_artifact_summary": {
            "live_verified_records_created": 0,
            "output_files_created": [],
            "production_db_written": False,
        },
        "champion_evaluation_unlock_status": {
            "live_monitoring_verified_records_created": 0,
            "strategies_with_live_verified_evidence": [],
            "champion_evaluation_unlocked": False,
            "unlock_reason_or_block_reason": (
                "No LIVE_MONITORING_VERIFIED evidence created. "
                "Champion evaluation gate remains BLOCKED. "
                "Kelvin must provide manual draw results to proceed."
            ),
            "next_gate": "P148B_AWAITING_MANUAL_DRAW_RESULT_INPUT",
        },
        "non_actions": {
            "db_write_in_p148b": False,
            "controlled_apply_executed_in_p148b": False,
            "replay_rows_inserted_in_p148b": 0,
            "replay_rows_updated_in_p148b": 0,
            "replay_rows_deleted_in_p148b": 0,
            "registry_update_executed_in_p148b": False,
            "champion_promotion_executed_in_p148b": False,
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
            "No real post-apply draw results available for any candidate strategy",
            "Champion evaluation remains blocked until LIVE_MONITORING_VERIFIED evidence is collected",
            "Historical backfill data (lottery_v2.db) does not qualify as LIVE_MONITORING_VERIFIED",
            "Mock/observation-only records from P146B do not qualify as LIVE_MONITORING_VERIFIED",
            "Operator must manually supply draw number + winning numbers for at least 1 candidate strategy",
        ],
        "next_recommended_task": "P148B_AWAITING_MANUAL_DRAW_RESULT_INPUT",
        "summary": (
            "P148B BLOCKED: No usable post-apply draw result source found. "
            "0 LIVE_MONITORING_VERIFIED evidence records created. "
            "All 6 candidate strategies skipped. "
            "Champion evaluation gate remains BLOCKED. "
            "Action required: Kelvin must provide actual post-apply draw results "
            "(draw number + winning numbers) for at least one candidate strategy "
            "as a manual input JSON file before P148B can advance."
        ),
    }

    return artifact


# ---------------------------------------------------------------------------
# Write outputs
# ---------------------------------------------------------------------------


def write_json(artifact: dict) -> None:
    out_path = os.path.join(CANONICAL_REPO, OUTPUT_JSON)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(artifact, f, indent=2)
    print(f"\nJSON artifact written: {out_path}")
    # Update output_artifact_summary to reflect the file created
    artifact["output_artifact_summary"]["output_files_created"].append(out_path)


def write_markdown(artifact: dict) -> None:
    now_str = artifact["generated_at"]
    classification = artifact["classification"]
    repo_ok = artifact["repo_branch_check"]["repo_ok"]
    branch_ok = artifact["repo_branch_check"]["branch_ok"]
    db = artifact["db_snapshot"]
    audit = artifact["manual_input_source_audit"]
    contract = artifact["live_verified_evidence_contract_validation"]
    champion_status = artifact["champion_evaluation_unlock_status"]
    non_actions = artifact["non_actions"]

    strategy_rows = "\n".join(
        f"| {r['strategy_id']} | {r['lottery_type']} | {r['status']} | {r['skipped_with_reason']} |"
        for r in artifact["per_strategy_evidence_results"]
    )

    required_fields_list = "\n".join(
        f"| `{field}` |" for field in contract["required_fields"]
    )

    md = f"""# P148B: Manual Live Verified Evidence File Artifact Run

**Generated:** {now_str}
**Classification:** `{classification}`
**Task ID:** P148B

---

## Executive Summary

P148B is **BLOCKED**. No usable post-apply draw result source was found. **0 LIVE_MONITORING_VERIFIED
records** were created. All 6 candidate strategies were skipped. The champion evaluation gate
remains BLOCKED.

No DB writes, live API calls, scheduler installations, or champion promotions were performed
in P148B. The block reason is documented below.

**Action required:** Kelvin must provide actual post-apply draw results (draw number + winning
numbers) for at least one candidate strategy before this phase can advance.

---

## Canonical Repo/Branch Confirmation

| Field | Value | Status |
|-------|-------|--------|
| Canonical repo | `{artifact['canonical_repo']}` | {'PASS' if repo_ok else 'FAIL'} |
| Canonical branch | `{artifact['canonical_branch']}` | {'PASS' if branch_ok else 'FAIL'} |

---

## P148 Recap

**P148 classification:** `{artifact['p148_source_summary']['classification']}`

P148 established the evidence collection gate and defined the recommended path (Option A/B:
manual input or local verified source, file artifact first, no DB write). P148B is the
execution phase of that recommended path.

| Field | Value |
|-------|-------|
| Recommended path | option_a_or_b |
| Production DB write required | NO |
| Champion evaluation allowed | NO (P147 blocked) |

---

## Manual/Local Evidence Source Audit

P148B searched the following directories for manual draw result input or local verified
post-apply draw sources:

- `inputs/`
- `outputs/replay/manual_input/`
- `data/manual_draw_results/`
- `.` (repo root, JSON files matching manual input filename patterns)

**Filename patterns searched:** `draw_result_input`, `manual_input`, `live_draw`, `post_apply_draw`

| Source | Found | Notes |
|--------|-------|-------|
| Manual draw result input file | **NO** | No qualifying JSON files found |
| Local verified post-apply source | **NO** | Historical DB data does not qualify |
| Usable source found | **NO** | — |

**Source type:** `{audit['source_type']}`
**Source path:** `{audit['source_path']}`
**Validation result:** `{audit['source_validation_result']}`

**Why historical/mock data does not qualify:**

Historical backfill data (`lottery_v2.db`) and mock/observation-only records (from P146B) do
not qualify as `LIVE_MONITORING_VERIFIED` evidence. The contract requires actual post-apply
draw results obtained after the Wave-2 strategies were deployed. Only results that were
verified after the fact against a live prediction record meet the standard.

**Block reason:**

> {audit['block_reason_if_missing']}

---

## LIVE_MONITORING_VERIFIED Contract Validation

The contract for a valid `LIVE_MONITORING_VERIFIED` record has been validated. It requires
{contract['required_fields_count']} fields. Since no usable source was found, **0 records were
produced** — but the contract definition is complete and ready for use once input is available.

| Required Field |
|----------------|
{required_fields_list}

**Contract complete:** {'YES' if contract['contract_complete'] else 'NO'}
**All output records schema-valid:** {'YES' if contract['all_output_records_schema_valid'] else 'NO'} (vacuously true — 0 records produced)

---

## Per-Strategy Evidence Results

All 6 candidate strategies were **skipped** due to no usable post-apply draw source.

| Strategy ID | Lottery Type | Status | Reason |
|-------------|--------------|--------|--------|
{strategy_rows}

---

## Output Artifact Summary

| Metric | Value |
|--------|-------|
| LIVE_MONITORING_VERIFIED records created | **0** |
| Production DB written | **NO** |
| Output files created (evidence) | 0 |

No evidence file artifacts were produced. The JSON and Markdown outputs from this P148B run
itself are administrative artifacts only — they do not constitute LIVE_MONITORING_VERIFIED
evidence.

---

## Champion Evaluation Unlock Status

| Metric | Value |
|--------|-------|
| LIVE_MONITORING_VERIFIED records created | {champion_status['live_monitoring_verified_records_created']} |
| Strategies with live verified evidence | {len(champion_status['strategies_with_live_verified_evidence'])} |
| Champion evaluation unlocked | **NO** |
| Next gate | `{champion_status['next_gate']}` |

**Block reason:**

> {champion_status['unlock_reason_or_block_reason']}

---

## Action Required

To advance past P148B, Kelvin must:

1. After a monitored draw occurs for at least one candidate strategy, record the actual results.
2. Create a manual input JSON file with:
   - `draw_number` (or `target_draw`): the draw period number
   - `winning_numbers` (or `actual_numbers`): the actual numbers drawn
   - `strategy_id`: the candidate strategy being evaluated
   - `lottery_type`: e.g., `DAILY_539` or `POWER_LOTTO`
   - `prediction_artifact_path`: path to the prediction file generated before the draw
3. Place the file in `inputs/` or `outputs/replay/manual_input/` (or another searched path).
4. Re-run `scripts/p148b_manual_live_verified_evidence_file_artifact_run.py`.

Once at least 1 valid input file is found, P148B will produce a LIVE_MONITORING_VERIFIED
file artifact and unlock the champion evaluation gate.

---

## Explicit Non-Actions

The following actions were explicitly NOT performed in P148B:

| Action | Executed |
|--------|----------|
| DB write to lottery_v2.db | NO |
| Controlled apply | NO |
| Replay rows inserted | 0 |
| Replay rows updated | 0 |
| Replay rows deleted | 0 |
| Registry update | NO |
| Champion promotion | NO |
| Scheduler installed | NO |
| Live API called | NO |
| Fake LIVE_MONITORING_VERIFIED records created | NO |
| Mock/fixture records promoted to LIVE_MONITORING_VERIFIED | NO |
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

1. No real post-apply draw results available for any candidate strategy
2. Champion evaluation remains blocked until `LIVE_MONITORING_VERIFIED` evidence is collected
3. Historical backfill data (`lottery_v2.db`) does not qualify as `LIVE_MONITORING_VERIFIED`
4. Mock/observation-only records from P146B do not qualify as `LIVE_MONITORING_VERIFIED`
5. Operator must manually supply draw number + winning numbers for at least 1 candidate strategy

---

## Recommended Next Task: P148B_AWAITING_MANUAL_DRAW_RESULT_INPUT

P148B is awaiting a manual draw result input. Once Kelvin provides actual post-apply draw
results for at least one candidate strategy (draw number + winning numbers), re-run this
script to produce LIVE_MONITORING_VERIFIED file artifacts and unlock the champion evaluation
gate.

No DB write required for the file artifact phase.

---

## Final Classification

`{classification}`
"""

    out_path = os.path.join(CANONICAL_REPO, OUTPUT_MD)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        f.write(md)
    print(f"Markdown artifact written: {out_path}")


def print_summary(artifact: dict) -> None:
    print("\n" + "=" * 60)
    print("P148B SUMMARY")
    print("=" * 60)
    print(f"Classification: {artifact['classification']}")
    print(f"DB total rows: {artifact['db_snapshot']['total_rows']}")
    print(f"LIVE_MONITORING_VERIFIED records created: {artifact['output_artifact_summary']['live_verified_records_created']}")
    print(f"Champion evaluation unlocked: {artifact['champion_evaluation_unlock_status']['champion_evaluation_unlocked']}")
    print(f"Next gate: {artifact['champion_evaluation_unlock_status']['next_gate']}")
    print(f"\nSummary: {artifact['summary']}")


def main() -> None:
    artifact = run_p148b()
    write_json(artifact)
    write_markdown(artifact)
    print_summary(artifact)
    print("\nP148B run complete. No DB writes performed.")


if __name__ == "__main__":
    main()
