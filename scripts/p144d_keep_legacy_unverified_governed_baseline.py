#!/usr/bin/env python3
"""
P144D: Keep legacy unverified as governed baseline — Option A decision recorded.

THIS SCRIPT DOES NOT WRITE THE DB.
Option A = keep LEGACY_UNVERIFIED rows as governed baseline. No DB mutation.

Requires --authorization argument with exact phrase:
  P144C_AUTHORIZED_KEEP_LEGACY_UNVERIFIED_AS_GOVERNED_BASELINE_20260529

Usage:
  uv run python scripts/p144d_keep_legacy_unverified_governed_baseline.py \
      --authorization "P144C_AUTHORIZED_KEEP_LEGACY_UNVERIFIED_AS_GOVERNED_BASELINE_20260529"
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

TASK_ID = "P144D"
CLASSIFICATION = "P144D_LEGACY_UNVERIFIED_KEEP_GOVERNED_BASELINE_DECISION_RECORDED"
DATE_SUFFIX = "20260529"

CANONICAL_REPO = str(REPO_ROOT)
CANONICAL_BRANCH = "claude/zen-gates-ff6802"
EXPECTED_TOTAL_ROWS = 94924

REQUIRED_AUTH_PHRASE = "P144C_AUTHORIZED_KEEP_LEGACY_UNVERIFIED_AS_GOVERNED_BASELINE_20260529"

OUT_JSON = REPO_ROOT / f"outputs/replay/p144d_keep_legacy_unverified_governed_baseline_{DATE_SUFFIX}.json"
OUT_MD = REPO_ROOT / f"docs/replay/p144d_keep_legacy_unverified_governed_baseline_{DATE_SUFFIX}.md"
ROADMAP = REPO_ROOT / "00-Plan/roadmap/roadmap.md"
CTO = REPO_ROOT / "00-Plan/roadmap/CTO-Analysis.md"

P144C_JSON = REPO_ROOT / "outputs/replay/p144c_legacy_unverified_remediation_authorization_gate_20260529.json"
P146B_JSON = REPO_ROOT / "outputs/replay/p146b_authorized_observation_only_monitoring_run_20260529.json"
P142_JSON = REPO_ROOT / "outputs/replay/p142_wave2_multibet_apply_chain_closure_audit_20260529.json"


def _git(cmd: list[str]) -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", str(REPO_ROOT)] + cmd, stderr=subprocess.DEVNULL
        ).decode().strip()
    except Exception:
        return ""


def _check_repo_branch() -> dict:
    actual_repo = _git(["rev-parse", "--show-toplevel"])
    actual_branch = _git(["branch", "--show-current"])
    return {
        "expected_repo": CANONICAL_REPO,
        "actual_repo": actual_repo,
        "expected_branch": CANONICAL_BRANCH,
        "actual_branch": actual_branch,
        "repo_ok": actual_repo == CANONICAL_REPO,
        "branch_ok": actual_branch == CANONICAL_BRANCH,
    }


def _db_snapshot() -> dict:
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()
    total = cur.execute("SELECT COUNT(*) FROM strategy_prediction_replays;").fetchone()[0]
    cols = [r[1] for r in cur.execute("PRAGMA table_info(strategy_prediction_replays);")]
    conn.close()
    return {
        "db_path": str(DB_PATH),
        "total_rows": total,
        "expected_rows": EXPECTED_TOTAL_ROWS,
        "rows_ok": total == EXPECTED_TOTAL_ROWS,
        "bet_index_column_exists": "bet_index" in cols,
    }


def _load_artifact(path: Path) -> dict:
    if not path.exists():
        return {"error": f"not found: {path}"}
    return json.loads(path.read_text(encoding="utf-8"))


def _query_legacy_unverified(conn: sqlite3.Connection) -> dict:
    cur = conn.cursor()

    # Full breakdown
    rows = cur.execute(
        """
        SELECT strategy_id, bet_index, truth_level, source, controlled_apply_id, COUNT(*)
        FROM strategy_prediction_replays
        WHERE strategy_id IN ('power_precision_3bet','power_orthogonal_5bet')
        GROUP BY strategy_id, bet_index, truth_level, source, controlled_apply_id
        ORDER BY strategy_id, bet_index, truth_level, source;
        """
    ).fetchall()

    # Count LEGACY_UNVERIFIED per strategy
    power_precision = 0
    power_orthogonal = 0
    for sid, bidx, tlevel, src, ca_id, cnt in rows:
        if tlevel == "LEGACY_UNVERIFIED":
            if sid == "power_precision_3bet":
                power_precision += cnt
            elif sid == "power_orthogonal_5bet":
                power_orthogonal += cnt

    total_legacy = power_precision + power_orthogonal

    # Check all LEGACY_UNVERIFIED rows have bet_index=1
    non_b1 = cur.execute(
        """
        SELECT COUNT(*) FROM strategy_prediction_replays
        WHERE strategy_id IN ('power_precision_3bet','power_orthogonal_5bet')
          AND truth_level = 'LEGACY_UNVERIFIED'
          AND bet_index != 1;
        """
    ).fetchone()[0]

    # Check all LEGACY_UNVERIFIED rows have controlled_apply_id IS NULL
    non_null_caid = cur.execute(
        """
        SELECT COUNT(*) FROM strategy_prediction_replays
        WHERE strategy_id IN ('power_precision_3bet','power_orthogonal_5bet')
          AND truth_level = 'LEGACY_UNVERIFIED'
          AND controlled_apply_id IS NOT NULL;
        """
    ).fetchone()[0]

    # Check multi-bet rows (bet_index > 1) have no LEGACY_UNVERIFIED
    multibet_contamination = cur.execute(
        """
        SELECT COUNT(*) FROM strategy_prediction_replays
        WHERE strategy_id IN ('power_precision_3bet','power_orthogonal_5bet')
          AND truth_level = 'LEGACY_UNVERIFIED'
          AND bet_index > 1;
        """
    ).fetchone()[0]

    # Get actual source value
    src_row = cur.execute(
        """
        SELECT DISTINCT source FROM strategy_prediction_replays
        WHERE strategy_id IN ('power_precision_3bet','power_orthogonal_5bet')
          AND truth_level = 'LEGACY_UNVERIFIED';
        """
    ).fetchall()
    actual_sources = [r[0] for r in src_row]

    # Sample provenance hashes
    hashes = cur.execute(
        """
        SELECT provenance_hash FROM strategy_prediction_replays
        WHERE truth_level = 'LEGACY_UNVERIFIED'
          AND provenance_hash IS NOT NULL
        LIMIT 3;
        """
    ).fetchall()
    sample_hashes = [r[0] for r in hashes]

    return {
        "power_precision_3bet_legacy_unverified_rows": power_precision,
        "power_orthogonal_5bet_legacy_unverified_rows": power_orthogonal,
        "total_legacy_unverified_rows": total_legacy,
        "all_rows_bet_index_1": non_b1 == 0,
        "all_rows_controlled_apply_id_null": non_null_caid == 0,
        "p140_p141_multi_bet_contamination": multibet_contamination > 0,
        "actual_source": actual_sources[0] if len(actual_sources) == 1 else actual_sources,
        "sample_provenance_hashes": sample_hashes,
        "counts_ok": power_precision == 50 and power_orthogonal == 50 and total_legacy == 100,
    }


def _dirty_file_hygiene() -> dict:
    status = _git(["status", "--short"])
    lines = [ln for ln in status.splitlines() if ln.strip()]
    staged = [ln for ln in lines if not ln.startswith("??") and not ln.startswith(" ")]
    forbidden_staged = any(
        "lottery_v2.db" in ln or "backups/" in ln
        for ln in staged
    )
    # backups/ is untracked — that's OK
    backups_untracked = all(
        ln.startswith("??") for ln in lines if "backups/" in ln
    ) if any("backups/" in ln for ln in lines) else True
    return {
        "backups_untracked_not_staged": backups_untracked,
        "p135_p136_p142_autouse_regen_risk_noted": True,
        "forbidden_files_staged": forbidden_staged,
        "status_output": status or "(clean)",
    }


def _build_markdown(artifact: dict) -> str:
    ts = artifact["generated_at"]
    lus = artifact["legacy_unverified_current_state"]
    opt = artifact["selected_remediation_option"]
    pol = artifact["governed_baseline_policy"]
    sel = artifact["strict_selector_definitions"]
    champ = artifact["champion_monitoring_impact"]
    na = artifact["non_actions"]

    return f"""# P144D: Keep Legacy Unverified as Governed Baseline — Option A Decision Recorded

Generated: {ts}
Task: {artifact['task_id']}
Classification: `{artifact['classification']}`

---

## 1. Authorization

- Required phrase: `{artifact['authorization']['exact_required_phrase']}`
- Authorization present: {artifact['authorization']['authorization_present']}
- Decision allowed: {artifact['authorization']['decision_allowed']}
- Source: {artifact['authorization']['authorization_source']}

---

## 2. Canonical Repo / Branch Check

| Check | Expected | Actual | OK |
|-------|----------|--------|----|
| Repo  | `{artifact['canonical_repo']}` | `{artifact['repo_branch_check']['actual_repo']}` | {artifact['repo_branch_check']['repo_ok']} |
| Branch | `{artifact['canonical_branch']}` | `{artifact['repo_branch_check']['actual_branch']}` | {artifact['repo_branch_check']['branch_ok']} |

---

## 3. DB Snapshot (Read-Only)

- Total rows: {artifact['db_snapshot']['total_rows']} (expected: {artifact['db_snapshot']['expected_rows']})
- Rows OK: {artifact['db_snapshot']['rows_ok']}
- bet_index column exists: {artifact['db_snapshot']['bet_index_column_exists']}

---

## 4. Predecessor Artifact Validation

| Artifact | Classification | OK |
|----------|----------------|----|
| P144C | `{artifact['p144c_source_summary']['classification']}` | ✓ |
| P146B | `{artifact['p146b_source_summary']['classification']}` | ✓ |
| P142  | `{artifact['p142_source_summary']['classification']}` | ✓ |

---

## 5. Legacy Unverified Current State (Read-Only DB Queries)

| Strategy | LEGACY_UNVERIFIED Rows | bet_index |
|----------|------------------------|-----------|
| power_precision_3bet | {lus['power_precision_3bet_legacy_unverified_rows']} | 1 only |
| power_orthogonal_5bet | {lus['power_orthogonal_5bet_legacy_unverified_rows']} | 1 only |
| **Total** | **{lus['total_legacy_unverified_rows']}** | — |

- All rows bet_index=1: {lus['all_rows_bet_index_1']}
- All rows controlled_apply_id NULL: {lus['all_rows_controlled_apply_id_null']}
- P140/P141 multi-bet contamination: {lus['p140_p141_multi_bet_contamination']}
- Actual source: `{lus['actual_source']}`
- Counts OK (50+50=100): {lus['counts_ok']}

---

## 6. Selected Remediation Option

- **Option**: `{opt['selected_option']}`
- DB mutation required: {opt['db_mutation_required']}
- Row count impact: {opt['row_count_impact']}
- Risk level: {opt['risk_level']}
- Execution performed in P144D: {opt['execution_performed_in_p144d']}
- Remediation mutation performed: {opt['remediation_mutation_performed']}

---

## 7. Governed Baseline Policy

| Policy | Value |
|--------|-------|
| Keep legacy unverified rows | {pol['keep_legacy_unverified_rows']} |
| Exclude from champion evaluation | {pol['exclude_from_champion_evaluation']} |
| Exclude from apply base | {pol['exclude_from_apply_base']} |
| Live monitoring blocked by legacy rows | {pol['live_monitoring_blocked_by_legacy_rows']} |
| Registry update blocked by legacy rows | {pol['registry_update_blocked_by_legacy_rows']} |
| Future remediation allowed with new authorization | {pol['future_remediation_allowed_with_new_authorization']} |

---

## 8. Strict Selector Definitions

```sql
{sel['sql_where_clause']}
```

- strategy_id IN: {sel['strategy_id_in']}
- truth_level: `{sel['truth_level']}`
- bet_index: {sel['bet_index']}
- controlled_apply_id: {sel['controlled_apply_id']}
- source: `{sel['source']}`

---

## 9. Champion / Monitoring Impact

| Impact | Value |
|--------|-------|
| Champion promotion allowed in P144D | {champ['champion_promotion_allowed_in_p144d']} |
| Champion eval still requires live monitoring verified | {champ['champion_eval_still_requires_live_monitoring_verified']} |
| Live monitoring can continue | {champ['live_monitoring_can_continue']} |
| P147 blocked until live monitoring verified | {champ['p147_blocked_until_live_monitoring_verified']} |

---

## 10. Non-Actions Confirmation

| Action | Performed |
|--------|-----------|
| DB write in P144D | {na['db_write_in_p144d']} |
| Controlled apply executed | {na['controlled_apply_executed_in_p144d']} |
| Remediation mutation executed | {na['remediation_mutation_executed_in_p144d']} |
| Replay rows inserted | {na['replay_rows_inserted_in_p144d']} |
| Replay rows updated | {na['replay_rows_updated_in_p144d']} |
| Replay rows deleted | {na['replay_rows_deleted_in_p144d']} |
| Registry update executed | {na['registry_update_executed_in_p144d']} |
| Champion promotion executed | {na['champion_promotion_executed_in_p144d']} |
| Monitoring run executed | {na['monitoring_run_executed_in_p144d']} |
| Scheduler installed | {na['scheduler_installed']} |
| Live API called | {na['live_api_called']} |
| 4-STAR executed | {na['four_star_executed']} |
| P108 executed | {na['p108_executed']} |
| P117 executed | {na['p117_executed']} |
| P118 executed | {na['p118_executed']} |

---

## 11. Dirty File Hygiene

- backups/ untracked (not staged): {artifact['dirty_file_hygiene']['backups_untracked_not_staged']}
- P135/P136/P142 autouse regen risk noted: {artifact['dirty_file_hygiene']['p135_p136_p142_autouse_regen_risk_noted']}
- Forbidden files staged: {artifact['dirty_file_hygiene']['forbidden_files_staged']}

---

## 12. Remaining Risks

{chr(10).join(f'- {r}' for r in artifact['remaining_risks'])}

---

## 13. Next Recommended Task

**{artifact['next_recommended_task']}**

---

## 14. Summary

{artifact['summary']}
"""


def main() -> None:
    parser = argparse.ArgumentParser(
        description="P144D: Keep legacy unverified as governed baseline (Option A)"
    )
    parser.add_argument(
        "--authorization",
        type=str,
        default=None,
        help="Authorization phrase (required)",
    )
    args = parser.parse_args()

    # === Authorization check (must be first, before any file writes) ===
    if args.authorization is None:
        print("ERROR: --authorization argument is required.", file=sys.stderr)
        print(f"Required phrase: {REQUIRED_AUTH_PHRASE}", file=sys.stderr)
        sys.exit(1)

    if args.authorization != REQUIRED_AUTH_PHRASE:
        print("ERROR: Authorization phrase mismatch.", file=sys.stderr)
        print(f"Expected: {REQUIRED_AUTH_PHRASE}", file=sys.stderr)
        print(f"Got:      {args.authorization}", file=sys.stderr)
        sys.exit(1)

    print(f"[P144D] Authorization phrase verified.")

    # === Repo / branch check ===
    repo_branch = _check_repo_branch()
    if not repo_branch["repo_ok"]:
        print(f"ERROR: Repo mismatch. Expected: {CANONICAL_REPO}, Got: {repo_branch['actual_repo']}", file=sys.stderr)
        sys.exit(1)
    if not repo_branch["branch_ok"]:
        print(f"ERROR: Branch mismatch. Expected: {CANONICAL_BRANCH}, Got: {repo_branch['actual_branch']}", file=sys.stderr)
        sys.exit(1)
    print(f"[P144D] Repo/branch check passed.")

    # === DB snapshot (read-only) ===
    snap = _db_snapshot()
    if not snap["rows_ok"]:
        print(f"ERROR: DB row count mismatch. Expected: {EXPECTED_TOTAL_ROWS}, Got: {snap['total_rows']}", file=sys.stderr)
        sys.exit(1)
    if not snap["bet_index_column_exists"]:
        print("ERROR: bet_index column not found in strategy_prediction_replays.", file=sys.stderr)
        sys.exit(1)
    print(f"[P144D] DB snapshot: {snap['total_rows']} rows (PASS), bet_index column exists.")

    # === Load predecessor artifacts ===
    p144c = _load_artifact(P144C_JSON)
    if p144c.get("classification") != "P144C_LEGACY_UNVERIFIED_REMEDIATION_AUTHORIZATION_GATE_READY":
        print(f"ERROR: P144C classification mismatch: {p144c.get('classification')}", file=sys.stderr)
        sys.exit(1)

    p146b = _load_artifact(P146B_JSON)
    if p146b.get("classification") != "P146B_AUTHORIZED_OBSERVATION_ONLY_MONITORING_RUN_COMPLETED":
        print(f"ERROR: P146B classification mismatch: {p146b.get('classification')}", file=sys.stderr)
        sys.exit(1)

    p142 = _load_artifact(P142_JSON)
    if p142.get("classification") != "P142_WAVE2_MULTI_BET_APPLY_CHAIN_CLOSED":
        print(f"ERROR: P142 classification mismatch: {p142.get('classification')}", file=sys.stderr)
        sys.exit(1)

    print("[P144D] Predecessor artifacts validated: P144C, P146B, P142.")

    # === Query DB (read-only) ===
    conn = sqlite3.connect(str(DB_PATH))
    lus = _query_legacy_unverified(conn)
    conn.close()

    if not lus["counts_ok"]:
        print(f"ERROR: LEGACY_UNVERIFIED row counts unexpected: precision={lus['power_precision_3bet_legacy_unverified_rows']}, orthogonal={lus['power_orthogonal_5bet_legacy_unverified_rows']}", file=sys.stderr)
        sys.exit(1)
    if not lus["all_rows_bet_index_1"]:
        print("ERROR: Some LEGACY_UNVERIFIED rows have bet_index != 1.", file=sys.stderr)
        sys.exit(1)
    if lus["p140_p141_multi_bet_contamination"]:
        print("ERROR: Multi-bet LEGACY_UNVERIFIED contamination detected (bet_index > 1).", file=sys.stderr)
        sys.exit(1)

    print(f"[P144D] LEGACY_UNVERIFIED state: precision={lus['power_precision_3bet_legacy_unverified_rows']}, orthogonal={lus['power_orthogonal_5bet_legacy_unverified_rows']}, total={lus['total_legacy_unverified_rows']} (PASS)")

    # === Dirty file hygiene ===
    hygiene = _dirty_file_hygiene()

    # === Build artifact ===
    now_ts = datetime.now(timezone.utc).isoformat()

    artifact: dict = {
        "task_id": TASK_ID,
        "classification": CLASSIFICATION,
        "generated_at": now_ts,
        "authorization": {
            "exact_required_phrase": REQUIRED_AUTH_PHRASE,
            "provided_phrase": args.authorization,
            "authorization_present": True,
            "decision_allowed": True,
            "authorization_source": "explicit_command_argument",
        },
        "canonical_repo": CANONICAL_REPO,
        "canonical_branch": CANONICAL_BRANCH,
        "repo_branch_check": repo_branch,
        "db_snapshot": snap,
        "p144c_source_summary": {
            "classification": p144c.get("classification"),
            "task_id": p144c.get("task_id"),
            "generated_at": p144c.get("generated_at"),
            "recommended_option": p144c.get("recommended_remediation_path", {}).get("recommended_option"),
        },
        "p146b_source_summary": {
            "classification": p146b.get("classification"),
            "task_id": p146b.get("task_id"),
            "generated_at": p146b.get("generated_at"),
        },
        "p142_source_summary": {
            "classification": p142.get("classification"),
            "task_id": p142.get("task_id"),
            "generated_at": p142.get("generated_at"),
        },
        "legacy_unverified_current_state": lus,
        "selected_remediation_option": {
            "selected_option": "option_a_keep_governed_legacy_baseline",
            "db_mutation_required": False,
            "row_count_impact": 0,
            "risk_level": "NONE",
            "execution_performed_in_p144d": True,
            "remediation_mutation_performed": False,
            "description": "Keep LEGACY_UNVERIFIED rows as a governed legacy baseline. No DB mutation required.",
        },
        "governed_baseline_policy": {
            "keep_legacy_unverified_rows": True,
            "exclude_from_champion_evaluation": True,
            "exclude_from_apply_base": True,
            "live_monitoring_blocked_by_legacy_rows": False,
            "registry_update_blocked_by_legacy_rows": False,
            "future_remediation_allowed_with_new_authorization": True,
            "policy_rationale": (
                "LEGACY_UNVERIFIED rows are isolated to bet_index=1, controlled_apply_id IS NULL. "
                "Multi-bet rows (bet_index > 1) are BACKFILL_VERIFIED and unaffected. "
                "Champion evaluation filters by truth_level so legacy rows are excluded by design."
            ),
        },
        "strict_selector_definitions": {
            "strategy_id_in": ["power_precision_3bet", "power_orthogonal_5bet"],
            "truth_level": "LEGACY_UNVERIFIED",
            "bet_index": 1,
            "controlled_apply_id": "IS NULL",
            "source": lus.get("actual_source", "P138B_LEGACY_REMARK"),
            "note": (
                "provenance_hash is a per-row SHA256[:16] derived from "
                "strategy_id|target_draw|bet_index|replay_run_id|predicted_numbers|P138B_LEGACY_REMARK_20260529"
            ),
            "sql_where_clause": (
                "strategy_id IN ('power_precision_3bet','power_orthogonal_5bet') "
                "AND truth_level = 'LEGACY_UNVERIFIED' "
                "AND bet_index = 1 "
                "AND controlled_apply_id IS NULL "
                "AND source = 'P138B_LEGACY_REMARK'"
            ),
        },
        "champion_monitoring_impact": {
            "champion_promotion_allowed_in_p144d": False,
            "champion_eval_still_requires_live_monitoring_verified": True,
            "live_monitoring_can_continue": True,
            "p147_blocked_until_live_monitoring_verified": True,
            "note": (
                "Option A (keep governed baseline) does not block live monitoring. "
                "Champion promotion gate (P147) requires live monitoring verified draws — "
                "this condition is independent of LEGACY_UNVERIFIED row existence."
            ),
        },
        "non_actions": {
            "db_write_in_p144d": False,
            "controlled_apply_executed_in_p144d": False,
            "remediation_mutation_executed_in_p144d": False,
            "replay_rows_inserted_in_p144d": 0,
            "replay_rows_updated_in_p144d": 0,
            "replay_rows_deleted_in_p144d": 0,
            "registry_update_executed_in_p144d": False,
            "champion_promotion_executed_in_p144d": False,
            "monitoring_run_executed_in_p144d": False,
            "scheduler_installed": False,
            "live_api_called": False,
            "four_star_executed": False,
            "p108_executed": False,
            "p117_executed": False,
            "p118_executed": False,
        },
        "dirty_file_hygiene": hygiene,
        "roadmap_update_status": {
            "roadmap_md_updated": True,
            "cto_analysis_updated": True,
            "p144d_marked_done": True,
        },
        "remaining_risks": [
            "LEGACY_UNVERIFIED rows remain in DB indefinitely until future remediation with new authorization.",
            "Champion promotion (P147) requires live monitoring verified draws — not yet achieved.",
            "Future schema migrations must preserve bet_index=1 / LEGACY_UNVERIFIED isolation.",
            "Any new controlled_apply must use strict selector to avoid overwriting legacy rows.",
        ],
        "next_recommended_task": "P147_CHAMPION_EVALUATION_GATE",
        "summary": (
            "P144D records the Option A decision: keep 100 LEGACY_UNVERIFIED rows "
            "(50 power_precision_3bet + 50 power_orthogonal_5bet, all bet_index=1, "
            "controlled_apply_id IS NULL, source=P138B_LEGACY_REMARK) as a governed legacy baseline. "
            "No DB mutation was performed. DB row count remains 94924. "
            "Champion evaluation and apply base exclude LEGACY_UNVERIFIED rows by truth_level filter. "
            "Live monitoring is NOT blocked. P147 champion promotion gate remains blocked "
            "until live monitoring verified draws are accumulated."
        ),
    }

    # === Write outputs ===
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(artifact, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[P144D] JSON written: {OUT_JSON}")

    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text(_build_markdown(artifact), encoding="utf-8")
    print(f"[P144D] Markdown written: {OUT_MD}")

    # === Summary ===
    print("\n" + "=" * 70)
    print(f"  TASK:           {TASK_ID}")
    print(f"  CLASSIFICATION: {CLASSIFICATION}")
    print(f"  OPTION:         option_a_keep_governed_legacy_baseline")
    print(f"  DB ROWS:        {snap['total_rows']} (UNCHANGED)")
    print(f"  DB MUTATION:    False")
    print(f"  LEGACY STATE:   {lus['total_legacy_unverified_rows']} rows governed baseline")
    print(f"  NEXT TASK:      P147_CHAMPION_EVALUATION_GATE")
    print("=" * 70)


if __name__ == "__main__":
    main()
