#!/usr/bin/env python3
"""
P137: P10/P12 Legacy Row Governance Authorization Gate

Read-only governance analysis for power_precision_3bet (P10) and
power_orthogonal_5bet (P12) NULL-provenance legacy rows.

NO DB writes. NO controlled_apply. NO row insertions.
"""
import json
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

WORKTREE = Path("/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802")
DB_PATH = WORKTREE / "lottery_api/data/lottery_v2.db"
OUTPUTS_DIR = WORKTREE / "outputs/replay"
DOCS_DIR = WORKTREE / "docs/replay"
OUTPUT_JSON = OUTPUTS_DIR / "p137_p10_p12_legacy_row_governance_gate_20260529.json"
OUTPUT_MD = DOCS_DIR / "p137_p10_p12_legacy_row_governance_gate_20260529.md"

EXPECTED_REPO = "/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802"
EXPECTED_BRANCH = "claude/zen-gates-ff6802"
EXPECTED_DB_ROWS = 85924
P136_ARTIFACT = OUTPUTS_DIR / "p136_post_rsr6_p10_p12_baseline_reevaluation_20260529.json"
RSR6_ARTIFACT = OUTPUTS_DIR / "rsr6_cleanup_delete_orphan_bet_index2_rows_20260528.json"

P10_ID = "power_precision_3bet"
P12_ID = "power_orthogonal_5bet"
EXPECTED_BET1_ROWS = 1550
EXPECTED_BET2_PLUS_ROWS = 0
EXPECTED_PRODUCTION_ROWS = 1500
EXPECTED_NULL_PROV_ROWS = 50


def git_cmd(args):
    result = subprocess.run(
        ["git"] + args,
        cwd=WORKTREE,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def check_repo_branch():
    actual_repo = git_cmd(["rev-parse", "--show-toplevel"])
    actual_branch = git_cmd(["branch", "--show-current"])
    return {
        "expected_repo": EXPECTED_REPO,
        "actual_repo": actual_repo,
        "expected_branch": EXPECTED_BRANCH,
        "actual_branch": actual_branch,
        "repo_ok": actual_repo == EXPECTED_REPO,
        "branch_ok": actual_branch == EXPECTED_BRANCH,
    }


def check_db_rows(conn):
    row = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()
    return row[0]


def check_bet_index_schema(conn):
    cols = conn.execute("PRAGMA table_info(strategy_prediction_replays)").fetchall()
    col_names = [c[1] for c in cols]
    return "bet_index" in col_names


def check_artifact(path, expected_classification, expected_task_id=None):
    if not path.exists():
        return {"found": False, "classification": None, "task_id": None, "ok": False}
    with open(path) as f:
        data = json.load(f)
    classification = data.get("classification")
    task_id = data.get("task_id")
    ok = classification == expected_classification
    if expected_task_id:
        ok = ok and (task_id == expected_task_id)
    return {"found": True, "classification": classification, "task_id": task_id, "ok": ok}


def get_p10_p12_distribution(conn):
    result = {}
    for sid in [P10_ID, P12_ID]:
        rows = conn.execute(
            "SELECT bet_index, COUNT(*) FROM strategy_prediction_replays "
            "WHERE strategy_id=? GROUP BY bet_index ORDER BY bet_index",
            (sid,),
        ).fetchall()
        dist = {r[0]: r[1] for r in rows}
        result[sid] = {
            "bet1_rows": dist.get(1, 0),
            "bet2_plus_rows": sum(v for k, v in dist.items() if k > 1),
            "bet_index_distribution": dist,
        }
    return {
        "power_precision_3bet_bet1_rows": result[P10_ID]["bet1_rows"],
        "power_precision_3bet_bet2_plus_rows": result[P10_ID]["bet2_plus_rows"],
        "power_orthogonal_5bet_bet1_rows": result[P12_ID]["bet1_rows"],
        "power_orthogonal_5bet_bet2_plus_rows": result[P12_ID]["bet2_plus_rows"],
        "per_strategy": result,
    }


def audit_null_provenance(conn):
    result = {}
    for sid in [P10_ID, P12_ID]:
        null_rows = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE strategy_id=? AND provenance_hash IS NULL",
            (sid,),
        ).fetchone()[0]
        prod_rows = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE strategy_id=? AND provenance_hash IS NOT NULL",
            (sid,),
        ).fetchone()[0]
        # Get replay_run_id breakdown for NULL provenance
        run_id_breakdown = conn.execute(
            "SELECT replay_run_id, COUNT(*) FROM strategy_prediction_replays "
            "WHERE strategy_id=? AND provenance_hash IS NULL "
            "GROUP BY replay_run_id ORDER BY replay_run_id",
            (sid,),
        ).fetchall()
        # Get draw range for NULL provenance rows
        draw_range = conn.execute(
            "SELECT MIN(CAST(target_draw AS INTEGER)), MAX(CAST(target_draw AS INTEGER)) "
            "FROM strategy_prediction_replays "
            "WHERE strategy_id=? AND provenance_hash IS NULL",
            (sid,),
        ).fetchone()
        result[sid] = {
            "null_provenance_rows": null_rows,
            "production_baseline_rows": prod_rows,
            "replay_run_id_breakdown": {str(r[0]): r[1] for r in run_id_breakdown},
            "draw_range": {
                "min_draw": draw_range[0],
                "max_draw": draw_range[1],
            },
        }
    total = (
        result[P10_ID]["null_provenance_rows"]
        + result[P12_ID]["null_provenance_rows"]
    )
    return {
        "power_precision_3bet_null_provenance_rows": result[P10_ID]["null_provenance_rows"],
        "power_orthogonal_5bet_null_provenance_rows": result[P12_ID]["null_provenance_rows"],
        "production_baseline_rows_per_strategy": EXPECTED_PRODUCTION_ROWS,
        "total_legacy_rows_under_decision": total,
        "db_write_in_p137": False,
        "per_strategy_detail": result,
        "legacy_draw_range_note": (
            "NULL-provenance rows span draws 99000055–99000104 for both strategies. "
            "These are early replay_run_id=2 (20 rows) and replay_run_id=6 (30 rows) inserts "
            "predating P20 production backfill, with no controlled_apply_id, truth_level, "
            "source, or provenance_hash set at time of insertion."
        ),
    }


def build_governance_decision_matrix():
    return {
        "decision_context": (
            "Both P10 (power_precision_3bet) and P12 (power_orthogonal_5bet) each contain "
            "50 rows with NULL provenance_hash, NULL controlled_apply_id, NULL truth_level, "
            "and NULL source. These rows predate the P20 production backfill. "
            "RSR6 removed orphan bet_index>1 rows but did not address NULL-provenance rows. "
            "P136 confirmed the state is stable and deferred the governance decision to P137."
        ),
        "option_a": {
            "name": "Keep legacy rows as governed legacy baseline",
            "description": (
                "Accept the 50+50 NULL-provenance rows as part of the historical record. "
                "No DB mutation. Document them as 'governed legacy baseline' via policy artifact only."
            ),
            "db_mutation_required": False,
            "mutation_type": "NONE",
            "risk_level": "LOW",
            "risk_notes": (
                "No DB change risk. However, the NULL provenance remains permanently unresolved. "
                "Future governance tooling or drift guards may flag these rows indefinitely. "
                "apply_gate checks that validate provenance completeness would need to explicitly "
                "allow NULL-provenance rows for P10/P12."
            ),
            "apply_readiness_impact": (
                "P10/P12 remain apply_ready=false unless the future dry-run gate is updated "
                "to accept NULL-provenance rows as a recognized legacy class."
            ),
            "rollback_requirement": "NOT REQUIRED — no mutation",
            "backup_requirement": "NOT REQUIRED — no mutation",
            "authorization_phrase_template": (
                "I authorize Option A for P10/P12 NULL-provenance legacy rows: "
                "accept 50 rows per strategy as governed legacy baseline with no DB mutation, "
                "and approve future dry-run gate to proceed acknowledging this legacy class."
            ),
            "can_unblock_future_dry_run_gate": True,
            "dry_run_gate_note": (
                "Dry-run gate must be updated to include a legacy_class acceptance clause. "
                "Requires explicit authorization before dry-run gate executes."
            ),
        },
        "option_b": {
            "name": "Re-mark legacy rows with explicit truth/provenance metadata",
            "description": (
                "UPDATE the 50+50 NULL-provenance rows to assign explicit metadata: "
                "truth_level='LEGACY_UNVERIFIED', controlled_apply_id='P137_LEGACY_REMARK', "
                "source='LEGACY_REPLAY_RUN', provenance_hash=deterministic_hash(strategy_id+draw). "
                "This converts NULL-provenance rows to a traceable governed state."
            ),
            "db_mutation_required": True,
            "mutation_type": "UPDATE 100 rows (50 per strategy)",
            "risk_level": "MEDIUM",
            "risk_notes": (
                "DB mutation required. Must be executed with a pre-mutation backup. "
                "The re-marked provenance_hash would be synthetically generated, not "
                "derived from the original prediction run — this must be documented. "
                "Risk of introducing incorrect metadata if hash logic is misspecified."
            ),
            "apply_readiness_impact": (
                "After successful re-marking, P10/P12 could potentially pass provenance "
                "completeness checks and proceed to future dry-run gate. "
                "apply_ready=false until re-mark is executed and verified."
            ),
            "rollback_requirement": "REQUIRED — pre-mutation DB backup, rollback script",
            "backup_requirement": "REQUIRED — full DB backup before UPDATE execution",
            "authorization_phrase_template": (
                "I authorize Option B for P10/P12 NULL-provenance legacy rows: "
                "execute a governed re-mark UPDATE of 100 rows assigning truth_level='LEGACY_UNVERIFIED', "
                "controlled_apply_id='P137_LEGACY_REMARK', source='LEGACY_REPLAY_RUN', "
                "and deterministic provenance_hash, with DB backup taken before execution. "
                "I understand this introduces synthetic provenance metadata."
            ),
            "can_unblock_future_dry_run_gate": True,
            "dry_run_gate_note": (
                "After re-marking, dry-run gate can treat P10/P12 as fully governed. "
                "Requires verification that all 100 rows have non-NULL provenance_hash post-mutation."
            ),
        },
        "option_c": {
            "name": "Quarantine/delete legacy rows with strict selector",
            "description": (
                "DELETE the 50+50 NULL-provenance rows using a strict selector: "
                "WHERE strategy_id IN ('power_precision_3bet','power_orthogonal_5bet') "
                "AND provenance_hash IS NULL AND CAST(target_draw AS INTEGER) BETWEEN 99000055 AND 99000104. "
                "P10/P12 would then have exactly 1500 clean production baseline rows each."
            ),
            "db_mutation_required": True,
            "mutation_type": "DELETE 100 rows (50 per strategy)",
            "risk_level": "MEDIUM-HIGH",
            "risk_notes": (
                "Data deletion is irreversible without backup restoration. "
                "The deleted rows represent draws 99000055–99000104 which are "
                "historical prediction records. Deletion reduces per-strategy row count "
                "from 1550 to 1500 and brings both strategies to a clean P20 baseline. "
                "Drift guard total would drop from 85924 to 85824 — a permanent 100-row reduction. "
                "Requires updated drift guard baseline after execution."
            ),
            "apply_readiness_impact": (
                "After deletion, P10/P12 would have 1500 clean production rows only. "
                "apply_ready could be re-evaluated after drift guard re-baseline. "
                "However, the 1500-row baseline itself may still require a separate "
                "multi-bet row controlled_apply before apply_ready=true."
            ),
            "rollback_requirement": "REQUIRED — pre-deletion DB backup, explicit restore procedure",
            "backup_requirement": "REQUIRED — full DB backup before DELETE execution",
            "authorization_phrase_template": (
                "I authorize Option C for P10/P12 NULL-provenance legacy rows: "
                "execute a governed DELETE of 100 rows "
                "(strategy_id IN ('power_precision_3bet','power_orthogonal_5bet') "
                "AND provenance_hash IS NULL AND CAST(target_draw AS INTEGER) BETWEEN 99000055 AND 99000104) "
                "with DB backup taken before execution. "
                "I acknowledge that total DB rows will decrease from 85924 to 85824 "
                "and drift guard baseline must be updated after deletion."
            ),
            "can_unblock_future_dry_run_gate": True,
            "dry_run_gate_note": (
                "After deletion, P10/P12 start with a clean 1500-row production baseline. "
                "Drift guard baseline must be updated to 85824 before future dry-run gate executes. "
                "Dry-run gate can then plan multi-bet row insertions from a clean state."
            ),
        },
    }


def get_recommended_decision():
    return {
        "recommended_option": "option_b",
        "rationale": (
            "Option B (re-mark) is recommended because it resolves the NULL-provenance state "
            "without data loss (unlike Option C) and without leaving permanent untracked metadata "
            "(unlike Option A). Re-marking with LEGACY_UNVERIFIED truth_level explicitly acknowledges "
            "that these rows predate the P20 provenance pipeline while preserving the historical record. "
            "The synthetic provenance_hash approach is well-established in the codebase (see P20 backfill). "
            "Option A creates permanent technical debt in governance tooling. "
            "Option C reduces the dataset unnecessarily for rows that are otherwise valid historical data."
        ),
        "caveat": (
            "This recommendation is advisory only. Option B requires explicit CTO authorization "
            "before execution. The authorization phrase in option_b.authorization_phrase_template "
            "must be provided verbatim before any DB mutation proceeds."
        ),
        "this_is_not_authorization": True,
        "authorization_status": "PENDING — not yet authorized",
    }


def get_authorization_phrase_templates():
    return {
        "option_a_phrase": (
            "I authorize Option A for P10/P12 NULL-provenance legacy rows: "
            "accept 50 rows per strategy as governed legacy baseline with no DB mutation, "
            "and approve future dry-run gate to proceed acknowledging this legacy class."
        ),
        "option_b_phrase": (
            "I authorize Option B for P10/P12 NULL-provenance legacy rows: "
            "execute a governed re-mark UPDATE of 100 rows assigning truth_level='LEGACY_UNVERIFIED', "
            "controlled_apply_id='P137_LEGACY_REMARK', source='LEGACY_REPLAY_RUN', "
            "and deterministic provenance_hash, with DB backup taken before execution. "
            "I understand this introduces synthetic provenance metadata."
        ),
        "option_c_phrase": (
            "I authorize Option C for P10/P12 NULL-provenance legacy rows: "
            "execute a governed DELETE of 100 rows "
            "(strategy_id IN ('power_precision_3bet','power_orthogonal_5bet') "
            "AND provenance_hash IS NULL AND CAST(target_draw AS INTEGER) BETWEEN 99000055 AND 99000104) "
            "with DB backup taken before execution. "
            "I acknowledge that total DB rows will decrease from 85924 to 85824 "
            "and drift guard baseline must be updated after deletion."
        ),
        "note": (
            "The exact phrase must be provided verbatim by the authorizing party. "
            "Paraphrasing or partial repetition does not constitute authorization."
        ),
    }


def get_future_dry_run_gate_impact():
    return {
        "current_blocker": (
            "P10/P12 are blocked from dry-run gate because both strategies contain "
            "NULL-provenance legacy rows. The apply gate cannot validate provenance "
            "completeness until the governance decision is made and executed."
        ),
        "after_option_a": {
            "dry_run_gate_feasible": True,
            "condition": "Dry-run gate must include explicit legacy_class acceptance clause for NULL-provenance rows.",
            "estimated_next_task": "P138A: dry-run gate with legacy_class acceptance for P10/P12",
        },
        "after_option_b": {
            "dry_run_gate_feasible": True,
            "condition": "All 100 rows have non-NULL provenance_hash. Drift guard re-check at 85924.",
            "estimated_next_task": "P138B: dry-run gate for P10/P12 post-re-mark",
        },
        "after_option_c": {
            "dry_run_gate_feasible": True,
            "condition": "Drift guard re-baseline at 85824. P10/P12 have clean 1500-row production state.",
            "estimated_next_task": "P138C: drift guard re-baseline + dry-run gate for P10/P12 post-deletion",
        },
        "p10_p12_multi_bet_note": (
            "Even after resolving the NULL-provenance issue, P10/P12 will still need "
            "a separate multi-bet controlled_apply to insert bet-2+ rows. "
            "P10 is power_precision_3bet (bet-2, bet-3 needed). "
            "P12 is power_orthogonal_5bet (bet-2 through bet-5 needed). "
            "The governance gate decision is a prerequisite, not a sufficient condition, for apply_ready."
        ),
    }


def build_result(
    repo_branch_check,
    db_rows,
    bet_index_ok,
    p136_check,
    rsr6_check,
    p10_p12_dist,
    null_prov_audit,
    governance_matrix,
    recommended_decision,
    auth_phrases,
    dry_run_impact,
):
    now = datetime.now(timezone.utc).isoformat()
    head_sha = git_cmd(["rev-parse", "HEAD"])

    apply_gate_status = {
        "controlled_apply_executed": False,
        "replay_rows_inserted": 0,
        "db_rows_before": EXPECTED_DB_ROWS,
        "db_rows_after": db_rows,
        "power_precision_3bet_apply_ready": False,
        "power_orthogonal_5bet_apply_ready": False,
        "per_strategy_authorization_required_later": True,
    }

    blocked_or_excluded = [
        "no DB write in P137",
        "no controlled_apply in P137",
        "no replay rows inserted",
        "P10/P12 still blocked until governance decision authorization",
        "4_STAR excluded",
        "P108 not run",
        "P117 not run",
        "P118 not run",
        "rejected strategies no_action",
        "no scheduler install",
        "no lifecycle / champion / registry mutation",
    ]

    return {
        "task_id": "P137",
        "classification": "P137_P10_P12_LEGACY_ROW_GOVERNANCE_GATE_READY",
        "generated_at": now,
        "canonical_repo": EXPECTED_REPO,
        "canonical_branch": EXPECTED_BRANCH,
        "repo_branch_check": repo_branch_check,
        "db_snapshot": {
            "db_path": str(DB_PATH),
            "total_rows": db_rows,
            "expected_rows": EXPECTED_DB_ROWS,
            "rows_ok": db_rows == EXPECTED_DB_ROWS,
            "bet_index_schema_present": bet_index_ok,
            "head_sha": head_sha,
        },
        "p136_source_summary": {
            "artifact_path": str(P136_ARTIFACT),
            "artifact_found": p136_check["found"],
            "classification": p136_check["classification"],
            "expected_classification": "P136_POST_RSR6_P10_P12_REEVALUATION_READY",
            "classification_ok": p136_check["ok"],
        },
        "rsr6_cleanup_source_summary": {
            "artifact_path": str(RSR6_ARTIFACT),
            "artifact_found": rsr6_check["found"],
            "classification": rsr6_check["classification"],
            "expected_classification": "RSR6_ORPHAN_BET_INDEX2_CLEANUP_APPLIED",
            "classification_ok": rsr6_check["ok"],
        },
        "p10_p12_current_distribution": p10_p12_dist,
        "null_provenance_legacy_audit": null_prov_audit,
        "governance_decision_matrix": governance_matrix,
        "recommended_decision": recommended_decision,
        "authorization_phrase_templates": auth_phrases,
        "future_dry_run_gate_impact": dry_run_impact,
        "apply_gate_status": apply_gate_status,
        "blocked_or_excluded": blocked_or_excluded,
        "roadmap_update_status": "pending — will be updated in this run",
        "remaining_risks": [
            "NULL-provenance rows remain unresolved until governance option is authorized and executed.",
            "P10/P12 cannot enter dry-run gate until governance decision is made.",
            "Option B introduces synthetic provenance_hash that must be clearly labeled LEGACY_UNVERIFIED.",
            "Option C permanently reduces DB row count from 85924 to 85824 — drift guard baseline must be updated.",
            "Option A leaves NULL-provenance rows permanently unresolved — future governance tools may re-flag them.",
            "No multi-bet row gap covered in P137 — P10/P12 still need bet-2+ rows regardless of governance option chosen.",
        ],
        "next_recommended_task": (
            "After governance decision authorization: P138 — execute chosen governance option "
            "for P10/P12 legacy rows, then re-assess dry-run gate readiness."
        ),
        "summary": (
            "P137 is a read-only governance gate for power_precision_3bet (P10) and "
            "power_orthogonal_5bet (P12). Both strategies contain 50 NULL-provenance legacy rows "
            "each (total 100 rows, draws 99000055–99000104) in addition to 1500 clean production "
            "baseline rows. Three governance options are defined: "
            "Option A (keep as governed legacy baseline, no DB mutation), "
            "Option B (re-mark with LEGACY_UNVERIFIED metadata, UPDATE 100 rows), "
            "Option C (quarantine/delete 100 rows, DB drops to 85824). "
            "Recommended: Option B. No DB writes, no controlled_apply, no row insertions "
            "performed in P137. Authorization required before any option is executed."
        ),
    }


def write_markdown(result: dict) -> None:
    p10_dist = result["p10_p12_current_distribution"]
    null_audit = result["null_provenance_legacy_audit"]
    matrix = result["governance_decision_matrix"]
    auth = result["authorization_phrase_templates"]
    dry_run = result["future_dry_run_gate_impact"]
    rec = result["recommended_decision"]

    md = f"""# P137: P10/P12 Legacy Row Governance Authorization Gate

**Generated:** {result["generated_at"]}
**Classification:** `{result["classification"]}`
**Worktree:** `{result["canonical_repo"]}`
**Branch:** `{result["canonical_branch"]}`

---

## 1. Executive Summary

P137 is a **read-only governance gate** for `power_precision_3bet` (P10) and
`power_orthogonal_5bet` (P12). No DB writes, no controlled_apply, no row insertions.

Both strategies contain **50 NULL-provenance legacy rows each** (100 total) in addition
to 1500 clean production baseline rows from the P20 backfill. These legacy rows predate
the P20 provenance pipeline and have NULL `provenance_hash`, `controlled_apply_id`,
`truth_level`, and `source`.

P137 defines three governance options, provides authorization phrase templates for each,
and identifies the next executable task pending CTO authorization.

---

## 2. Canonical Repo / Branch Confirmation

| Field | Expected | Actual | OK |
|-------|----------|--------|----|
| Repo | `{result["repo_branch_check"]["expected_repo"]}` | `{result["repo_branch_check"]["actual_repo"]}` | {"✅" if result["repo_branch_check"]["repo_ok"] else "❌"} |
| Branch | `{result["repo_branch_check"]["expected_branch"]}` | `{result["repo_branch_check"]["actual_branch"]}` | {"✅" if result["repo_branch_check"]["branch_ok"] else "❌"} |
| DB rows | `{EXPECTED_DB_ROWS}` | `{result["db_snapshot"]["total_rows"]}` | {"✅" if result["db_snapshot"]["rows_ok"] else "❌"} |
| bet_index schema | required | {"present" if result["db_snapshot"]["bet_index_schema_present"] else "MISSING"} | {"✅" if result["db_snapshot"]["bet_index_schema_present"] else "❌"} |
| Drift guard | PASS | PASS | ✅ |

---

## 3. P136 Recap

**P136 classification:** `{result["p136_source_summary"]["classification"]}`
**RSR6 cleanup classification:** `{result["rsr6_cleanup_source_summary"]["classification"]}`

P136 confirmed that after RSR6 orphan bet_index cleanup:
- P10/P12 each have 1550 bet-1 rows and 0 bet-2+ rows
- 1500 rows per strategy have full P20 production provenance
- 50 rows per strategy retain NULL provenance from pre-P20 replay runs

P136 deferred the governance decision to P137 without DB mutation.

---

## 4. Why P10/P12 Need a Governance Decision

The apply gate for multi-bet controlled_apply requires **provenance completeness** —
all rows must have non-NULL `provenance_hash`, `controlled_apply_id`, `truth_level`,
and `source`. The 50 NULL-provenance rows per strategy fail this check.

These rows come from two early replay runs:
- `replay_run_id=2`: 20 rows per strategy (earliest batch)
- `replay_run_id=6`: 30 rows per strategy (second batch)

Both batches were inserted before the P20 provenance pipeline was established.
RSR6 cleaned orphan bet_index>1 rows but was explicitly scoped to not touch
NULL-provenance rows.

---

## 5. Current P10/P12 Row Distribution

| Strategy | bet-1 rows | bet-2+ rows |
|----------|-----------|-------------|
| `power_precision_3bet` | {p10_dist["power_precision_3bet_bet1_rows"]} | {p10_dist["power_precision_3bet_bet2_plus_rows"]} |
| `power_orthogonal_5bet` | {p10_dist["power_orthogonal_5bet_bet1_rows"]} | {p10_dist["power_orthogonal_5bet_bet2_plus_rows"]} |

Both strategies: `apply_ready = false`

---

## 6. NULL-Provenance Legacy Row Audit

| Strategy | NULL provenance rows | Production baseline rows | Draw range |
|----------|---------------------|--------------------------|------------|
| `power_precision_3bet` | {null_audit["power_precision_3bet_null_provenance_rows"]} | {null_audit["production_baseline_rows_per_strategy"]} | 99000055–99000104 |
| `power_orthogonal_5bet` | {null_audit["power_orthogonal_5bet_null_provenance_rows"]} | {null_audit["production_baseline_rows_per_strategy"]} | 99000055–99000104 |
| **Total under decision** | **{null_audit["total_legacy_rows_under_decision"]}** | — | — |

**replay_run_id breakdown (per strategy):**
- `replay_run_id=2`: 20 rows (NULL truth_level, NULL source, NULL provenance_hash)
- `replay_run_id=6`: 30 rows (NULL truth_level, NULL source, NULL provenance_hash)

**No DB write in P137:** confirmed (`db_write_in_p137 = false`)

---

## 7. Governance Decision Options

### Option A — Keep as Governed Legacy Baseline

**DB mutation:** None
**Risk level:** LOW

Accept the 50+50 NULL-provenance rows as part of the historical record.
Document them as a recognized legacy class via policy artifact only.
The dry-run gate must be updated to explicitly accept NULL-provenance rows as a
`legacy_class` designation.

**Risks:** NULL provenance remains permanently unresolved. Future governance tooling
may re-flag these rows. apply_gate must include a legacy_class exception.

**Rollback/Backup:** Not required.

**Authorization phrase:**
```
{auth["option_a_phrase"]}
```

---

### Option B — Re-mark with Explicit Metadata (RECOMMENDED)

**DB mutation:** UPDATE 100 rows (50 per strategy)
**Risk level:** MEDIUM

UPDATE the 100 NULL-provenance rows to assign:
- `truth_level = 'LEGACY_UNVERIFIED'`
- `controlled_apply_id = 'P137_LEGACY_REMARK'`
- `source = 'LEGACY_REPLAY_RUN'`
- `provenance_hash = deterministic_hash(strategy_id + target_draw)`

This converts NULL-provenance rows to a traceable governed state while preserving
the historical record. DB row count remains 85924.

**Risks:** Requires DB backup. Introduces synthetic provenance_hash — must be labeled
`LEGACY_UNVERIFIED` to distinguish from real prediction provenances.

**Rollback/Backup:** Full DB backup required before execution.

**Authorization phrase:**
```
{auth["option_b_phrase"]}
```

---

### Option C — Quarantine/Delete with Strict Selector

**DB mutation:** DELETE 100 rows (50 per strategy)
**Risk level:** MEDIUM-HIGH

DELETE rows matching:
```sql
WHERE strategy_id IN ('power_precision_3bet','power_orthogonal_5bet')
  AND provenance_hash IS NULL
  AND CAST(target_draw AS INTEGER) BETWEEN 99000055 AND 99000104
```

P10/P12 would have exactly 1500 clean production rows each.
DB total drops from 85924 to **85824**. Drift guard baseline must be updated.

**Risks:** Data deletion is irreversible without backup. 100 historical prediction
records permanently removed. Drift guard re-baseline required.

**Rollback/Backup:** Full DB backup required before execution. Restore procedure required.

**Authorization phrase:**
```
{auth["option_c_phrase"]}
```

---

## 8. Recommended Decision

**Recommended: Option B** (re-mark with LEGACY_UNVERIFIED metadata)

{rec["rationale"]}

> **{rec["caveat"]}**
>
> **Authorization status: {rec["authorization_status"]}**

---

## 9. Authorization Phrase Templates

All phrases must be provided **verbatim** by the authorizing party.
Paraphrasing or partial repetition does not constitute authorization.

**Option A:**
```
{auth["option_a_phrase"]}
```

**Option B (recommended):**
```
{auth["option_b_phrase"]}
```

**Option C:**
```
{auth["option_c_phrase"]}
```

---

## 10. Future Dry-Run Gate Impact

**Current blocker:** {dry_run["current_blocker"]}

| After option | Dry-run gate feasible? | Condition | Next task |
|-------------|----------------------|-----------|-----------|
| Option A | ✅ | {dry_run["after_option_a"]["condition"]} | `{dry_run["after_option_a"]["estimated_next_task"]}` |
| Option B | ✅ | {dry_run["after_option_b"]["condition"]} | `{dry_run["after_option_b"]["estimated_next_task"]}` |
| Option C | ✅ | {dry_run["after_option_c"]["condition"]} | `{dry_run["after_option_c"]["estimated_next_task"]}` |

**Note:** {dry_run["p10_p12_multi_bet_note"]}

---

## 11. Explicit Non-Actions in P137

- ❌ No DB writes executed
- ❌ No controlled_apply executed
- ❌ No replay rows inserted
- ❌ No `4_STAR` / `P108` / `P117` / `P118` execution
- ❌ No scheduler / cron / launchd install
- ❌ No strategy lifecycle / champion / registry mutation
- ❌ No P7/P8/P9/P11 Wave 2 rows touched
- ❌ No P126B–P126F / P131–P134 completed data touched
- ✅ DB rows: 85924 (unchanged)

---

## 12. Remaining Risks

{chr(10).join(f"- {r}" for r in result["remaining_risks"])}

---

## 13. Recommended Next Task

**{result["next_recommended_task"]}**

After CTO provides the authorization phrase for the chosen option, the next task is:
- **P138A** (after Option A): update dry-run gate to accept legacy_class for P10/P12
- **P138B** (after Option B): execute re-mark UPDATE with backup, verify 100 rows re-marked
- **P138C** (after Option C): execute DELETE with backup, re-baseline drift guard at 85824

---

## 14. Final Classification

```
P137_P10_P12_LEGACY_ROW_GOVERNANCE_GATE_READY
```
"""
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_MD.write_text(md.strip() + "\n")
    print(f"Markdown written: {OUTPUT_MD}")


def main():
    print("=" * 70)
    print("P137: P10/P12 Legacy Row Governance Authorization Gate")
    print("=" * 70)

    # STOP guard: verify we are in the canonical worktree
    actual_repo = git_cmd(["rev-parse", "--show-toplevel"])
    actual_branch = git_cmd(["branch", "--show-current"])
    if actual_repo != EXPECTED_REPO:
        print(f"STOP: repo mismatch. Expected {EXPECTED_REPO}, got {actual_repo}")
        sys.exit(1)
    if actual_branch != EXPECTED_BRANCH:
        print(f"STOP: branch mismatch. Expected {EXPECTED_BRANCH}, got {actual_branch}")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)

    # Checks
    repo_branch_check = check_repo_branch()
    db_rows = check_db_rows(conn)
    if db_rows != EXPECTED_DB_ROWS:
        print(f"STOP: DB rows mismatch. Expected {EXPECTED_DB_ROWS}, got {db_rows}")
        conn.close()
        sys.exit(1)

    bet_index_ok = check_bet_index_schema(conn)
    if not bet_index_ok:
        print("STOP: bet_index column missing from strategy_prediction_replays")
        conn.close()
        sys.exit(1)

    p136_check = check_artifact(P136_ARTIFACT, "P136_POST_RSR6_P10_P12_REEVALUATION_READY", "P136")
    if not p136_check["ok"]:
        print(f"STOP: P136 artifact classification mismatch: {p136_check}")
        conn.close()
        sys.exit(1)

    rsr6_check = check_artifact(RSR6_ARTIFACT, "RSR6_ORPHAN_BET_INDEX2_CLEANUP_APPLIED", "RSR6_CLEANUP")
    if not rsr6_check["ok"]:
        print(f"STOP: RSR6 cleanup artifact classification mismatch: {rsr6_check}")
        conn.close()
        sys.exit(1)

    p10_p12_dist = get_p10_p12_distribution(conn)
    # Validate expected distribution
    for sid_key, expected in [
        ("power_precision_3bet_bet1_rows", EXPECTED_BET1_ROWS),
        ("power_precision_3bet_bet2_plus_rows", EXPECTED_BET2_PLUS_ROWS),
        ("power_orthogonal_5bet_bet1_rows", EXPECTED_BET1_ROWS),
        ("power_orthogonal_5bet_bet2_plus_rows", EXPECTED_BET2_PLUS_ROWS),
    ]:
        actual = p10_p12_dist[sid_key]
        if actual != expected:
            print(f"STOP: {sid_key} mismatch. Expected {expected}, got {actual}")
            conn.close()
            sys.exit(1)

    null_prov_audit = audit_null_provenance(conn)
    if null_prov_audit["total_legacy_rows_under_decision"] != 100:
        print(f"STOP: expected 100 total NULL-provenance rows, got {null_prov_audit['total_legacy_rows_under_decision']}")
        conn.close()
        sys.exit(1)

    conn.close()

    governance_matrix = build_governance_decision_matrix()
    recommended_decision = get_recommended_decision()
    auth_phrases = get_authorization_phrase_templates()
    dry_run_impact = get_future_dry_run_gate_impact()

    result = build_result(
        repo_branch_check,
        db_rows,
        bet_index_ok,
        p136_check,
        rsr6_check,
        p10_p12_dist,
        null_prov_audit,
        governance_matrix,
        recommended_decision,
        auth_phrases,
        dry_run_impact,
    )

    # Write outputs
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(f"JSON written: {OUTPUT_JSON}")

    write_markdown(result)

    # Summary
    print()
    print(f"task_id          : {result['task_id']}")
    print(f"classification   : {result['classification']}")
    print(f"repo_ok          : {result['repo_branch_check']['repo_ok']}")
    print(f"branch_ok        : {result['repo_branch_check']['branch_ok']}")
    print(f"db_rows          : {result['db_snapshot']['total_rows']}")
    print(f"bet_index_ok     : {result['db_snapshot']['bet_index_schema_present']}")
    print(f"P136 ok          : {result['p136_source_summary']['classification_ok']}")
    print(f"RSR6 ok          : {result['rsr6_cleanup_source_summary']['classification_ok']}")
    print(f"P10 bet1         : {result['p10_p12_current_distribution']['power_precision_3bet_bet1_rows']}")
    print(f"P12 bet1         : {result['p10_p12_current_distribution']['power_orthogonal_5bet_bet1_rows']}")
    print(f"total_legacy_100 : {result['null_provenance_legacy_audit']['total_legacy_rows_under_decision']}")
    print(f"db_write         : {result['null_provenance_legacy_audit']['db_write_in_p137']}")
    print(f"controlled_apply : {result['apply_gate_status']['controlled_apply_executed']}")
    print()
    print("P137 complete.")


if __name__ == "__main__":
    main()
