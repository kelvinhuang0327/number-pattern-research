#!/usr/bin/env python3
"""
P144C: Legacy unverified remediation authorization gate.

THIS SCRIPT DOES NOT WRITE THE DB.
No remediation is executed. This is an authorization gate only.

Reads current LEGACY_UNVERIFIED state from the DB, documents remediation options,
and produces a structured authorization gate artifact.
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

TASK_ID = "P144C"
CLASSIFICATION = "P144C_LEGACY_UNVERIFIED_REMEDIATION_AUTHORIZATION_GATE_READY"
DATE_SUFFIX = "20260529"

CANONICAL_REPO = str(REPO_ROOT)
CANONICAL_BRANCH = "claude/zen-gates-ff6802"
EXPECTED_TOTAL_ROWS = 94924

OUT_JSON = REPO_ROOT / f"outputs/replay/p144c_legacy_unverified_remediation_authorization_gate_{DATE_SUFFIX}.json"
OUT_MD = REPO_ROOT / f"docs/replay/p144c_legacy_unverified_remediation_authorization_gate_{DATE_SUFFIX}.md"
ROADMAP = REPO_ROOT / "00-Plan/roadmap/roadmap.md"
CTO = REPO_ROOT / "00-Plan/roadmap/CTO-Analysis.md"

P146B_JSON = REPO_ROOT / "outputs/replay/p146b_authorized_observation_only_monitoring_run_20260529.json"
P142_JSON = REPO_ROOT / "outputs/replay/p142_wave2_multibet_apply_chain_closure_audit_20260529.json"
P138B_JSON = REPO_ROOT / "outputs/replay/p138b_remark_p10_p12_legacy_rows_20260529.json"


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
    # check bet_index column
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

    # By strategy / bet_index / truth_level
    rows = cur.execute(
        """
        SELECT strategy_id, bet_index, truth_level, COUNT(*)
        FROM strategy_prediction_replays
        WHERE truth_level = 'LEGACY_UNVERIFIED'
        GROUP BY strategy_id, bet_index, truth_level
        ORDER BY strategy_id, bet_index, truth_level;
        """
    ).fetchall()

    power_precision = 0
    power_orthogonal = 0
    all_bet_index_1 = True
    for strategy_id, bet_index, truth_level, cnt in rows:
        if strategy_id == "power_precision_3bet":
            power_precision += cnt
        elif strategy_id == "power_orthogonal_5bet":
            power_orthogonal += cnt
        if bet_index != 1:
            all_bet_index_1 = False

    total_legacy = power_precision + power_orthogonal

    # Confirm controlled_apply_id is NULL for all LEGACY_UNVERIFIED rows
    null_ca = cur.execute(
        """
        SELECT COUNT(*) FROM strategy_prediction_replays
        WHERE truth_level = 'LEGACY_UNVERIFIED' AND controlled_apply_id IS NULL;
        """
    ).fetchone()[0]
    all_controlled_apply_id_null = (null_ca == total_legacy)

    # Confirm P140/P141 multi-bet rows have NO LEGACY_UNVERIFIED contamination
    contaminated = cur.execute(
        """
        SELECT COUNT(*) FROM strategy_prediction_replays
        WHERE strategy_id IN ('power_precision_3bet','power_orthogonal_5bet')
          AND bet_index > 1
          AND truth_level = 'LEGACY_UNVERIFIED';
        """
    ).fetchone()[0]

    # Get actual source value
    source_row = cur.execute(
        """
        SELECT DISTINCT source FROM strategy_prediction_replays
        WHERE truth_level = 'LEGACY_UNVERIFIED'
        LIMIT 1;
        """
    ).fetchone()
    actual_source = source_row[0] if source_row else None

    # Get sample provenance_hash
    sample_hashes = [
        r[0] for r in cur.execute(
            """
            SELECT DISTINCT provenance_hash FROM strategy_prediction_replays
            WHERE truth_level = 'LEGACY_UNVERIFIED' LIMIT 3;
            """
        ).fetchall()
    ]

    return {
        "power_precision_3bet_legacy_unverified_rows": power_precision,
        "power_orthogonal_5bet_legacy_unverified_rows": power_orthogonal,
        "total_legacy_unverified_rows": total_legacy,
        "all_rows_bet_index_1": all_bet_index_1,
        "all_rows_controlled_apply_id_null": all_controlled_apply_id_null,
        "p140_p141_multi_bet_contamination": contaminated > 0,
        "actual_source": actual_source,
        "sample_provenance_hashes": sample_hashes,
        "counts_ok": power_precision == 50 and power_orthogonal == 50 and total_legacy == 100,
    }


def _dirty_file_hygiene() -> dict:
    status = subprocess.check_output(
        ["git", "-C", str(REPO_ROOT), "status", "--short"],
        stderr=subprocess.DEVNULL,
    ).decode()
    lines = status.strip().splitlines()
    staged = [l for l in lines if len(l) >= 2 and l[0] not in (" ", "?")]
    forbidden = [
        l for l in staged
        if "lottery_v2.db" in l or "backups/" in l
    ]
    backups_untracked = any(
        l.startswith("??") and "backups/" in l for l in lines
    )
    return {
        "backups_untracked_not_staged": backups_untracked,
        "forbidden_files_staged": len(forbidden) > 0,
        "forbidden_list": forbidden,
    }


def main() -> None:
    now = datetime.now(timezone.utc).isoformat()
    print(f"[P144C] Starting at {now}")

    # --- Phase 0: Repo / branch ---
    rbc = _check_repo_branch()
    if not rbc["repo_ok"]:
        print(f"[STOP] Repo mismatch: {rbc['actual_repo']} != {CANONICAL_REPO}")
        sys.exit(1)
    if not rbc["branch_ok"]:
        print(f"[STOP] Branch mismatch: {rbc['actual_branch']} != {CANONICAL_BRANCH}")
        sys.exit(1)
    print(f"  Repo/branch OK: {rbc['actual_repo']} @ {rbc['actual_branch']}")

    # --- Phase 0: DB snapshot ---
    snap = _db_snapshot()
    if not snap["rows_ok"]:
        print(f"[STOP] DB rows {snap['total_rows']} != {EXPECTED_TOTAL_ROWS}")
        sys.exit(1)
    if not snap["bet_index_column_exists"]:
        print("[STOP] bet_index column missing")
        sys.exit(1)
    print(f"  DB rows OK: {snap['total_rows']}, bet_index column exists")

    # --- Phase 0: Artifact checks ---
    p146b = _load_artifact(P146B_JSON)
    if p146b.get("classification") != "P146B_AUTHORIZED_OBSERVATION_ONLY_MONITORING_RUN_COMPLETED":
        print(f"[STOP] P146B classification mismatch: {p146b.get('classification')}")
        sys.exit(1)

    p142 = _load_artifact(P142_JSON)
    if p142.get("classification") != "P142_WAVE2_MULTI_BET_APPLY_CHAIN_CLOSED":
        print(f"[STOP] P142 classification mismatch: {p142.get('classification')}")
        sys.exit(1)

    p138b = _load_artifact(P138B_JSON)
    if p138b.get("classification") != "P138B_P10_P12_LEGACY_ROWS_REMARKED":
        print(f"[STOP] P138B classification mismatch: {p138b.get('classification')}")
        sys.exit(1)
    print("  Predecessor artifacts OK: P146B, P142, P138B")

    # --- Phase 1: Query LEGACY_UNVERIFIED state ---
    conn = sqlite3.connect(str(DB_PATH))
    legacy_state = _query_legacy_unverified(conn)
    conn.close()

    if not legacy_state["counts_ok"]:
        print(f"[STOP] LEGACY_UNVERIFIED count unexpected: {legacy_state}")
        sys.exit(1)
    if legacy_state["p140_p141_multi_bet_contamination"]:
        print("[STOP] P140/P141 multi-bet rows contaminated with LEGACY_UNVERIFIED")
        sys.exit(1)
    print(f"  LEGACY_UNVERIFIED: power_precision_3bet={legacy_state['power_precision_3bet_legacy_unverified_rows']}, "
          f"power_orthogonal_5bet={legacy_state['power_orthogonal_5bet_legacy_unverified_rows']}, "
          f"total={legacy_state['total_legacy_unverified_rows']}")
    print(f"  All bet_index=1: {legacy_state['all_rows_bet_index_1']}, "
          f"controlled_apply_id all NULL: {legacy_state['all_rows_controlled_apply_id_null']}, "
          f"multi-bet contamination: {legacy_state['p140_p141_multi_bet_contamination']}")

    actual_source = legacy_state["actual_source"]

    # --- Build strict selector definitions ---
    strict_selector_definitions = {
        "strategy_id_in": ["power_precision_3bet", "power_orthogonal_5bet"],
        "truth_level": "LEGACY_UNVERIFIED",
        "bet_index": 1,
        "controlled_apply_id": "IS NULL",
        "source": actual_source,
        "note": "provenance_hash is a per-row SHA256[:16] derived from strategy_id|target_draw|bet_index|replay_run_id|predicted_numbers|P138B_LEGACY_REMARK_20260529",
        "sql_where_clause": (
            f"strategy_id IN ('power_precision_3bet','power_orthogonal_5bet') "
            f"AND truth_level = 'LEGACY_UNVERIFIED' "
            f"AND bet_index = 1 "
            f"AND controlled_apply_id IS NULL "
            f"AND source = '{actual_source}'"
        ),
    }

    # --- Remediation option matrix ---
    remediation_option_matrix = {
        "option_a_keep_governed_legacy_baseline": {
            "description": "Keep LEGACY_UNVERIFIED rows as a governed legacy baseline. No DB mutation required.",
            "db_mutation_required": False,
            "mutation_type": None,
            "row_count_impact": 0,
            "backup_required": False,
            "rollback_path": "no action needed",
            "risk_level": "NONE",
            "champion_impact": "legacy rows excluded from champion eval by truth_level filter",
            "selector_used": None,
            "authorization_phrase": "P144C_AUTHORIZED_KEEP_LEGACY_UNVERIFIED_AS_GOVERNED_BASELINE_20260529",
        },
        "option_b_enrich_provenance_metadata": {
            "description": (
                "Enrich provenance metadata (provenance_source, notes) for LEGACY_UNVERIFIED rows. "
                "UPDATE only — no INSERT/DELETE. Row count unchanged."
            ),
            "db_mutation_required": True,
            "mutation_type": "UPDATE_ONLY",
            "row_count_impact": 0,
            "backup_required": True,
            "rollback_path": "restore from backup",
            "risk_level": "LOW",
            "champion_impact": "improves traceability, no count change",
            "selector_used": strict_selector_definitions,
            "authorization_phrase": "P144C_AUTHORIZED_ENRICH_P10_P12_LEGACY_UNVERIFIED_PROVENANCE_20260529",
        },
        "option_c_quarantine_with_backup": {
            "description": (
                "Move LEGACY_UNVERIFIED rows to a separate quarantine table or artifact. "
                "Removes them from strategy_prediction_replays but preserves them in quarantine."
            ),
            "db_mutation_required": True,
            "mutation_type": "MOVE_TO_QUARANTINE",
            "row_count_impact": -100,
            "backup_required": True,
            "rollback_path": "restore from backup and reverse move",
            "risk_level": "MEDIUM",
            "champion_impact": "removes rows from strategy_prediction_replays",
            "selector_used": strict_selector_definitions,
            "authorization_phrase": "P144C_AUTHORIZED_QUARANTINE_P10_P12_LEGACY_UNVERIFIED_WITH_BACKUP_20260529",
        },
        "option_d_delete_with_strict_selector": {
            "description": (
                "Permanently delete LEGACY_UNVERIFIED rows using strict selector. "
                "Irreversible without backup restore."
            ),
            "db_mutation_required": True,
            "mutation_type": "DELETE",
            "row_count_impact": -100,
            "backup_required": True,
            "rollback_path": "restore from backup only",
            "risk_level": "HIGH/DESTRUCTIVE",
            "champion_impact": "permanent row removal",
            "selector_used": strict_selector_definitions,
            "authorization_phrase": "P144C_AUTHORIZED_DELETE_P10_P12_LEGACY_UNVERIFIED_WITH_STRICT_SELECTOR_20260529",
        },
    }

    # --- Recommended remediation path ---
    recommended_remediation_path = {
        "recommended_option": "option_a_keep_governed_legacy_baseline",
        "reason": (
            "LEGACY_UNVERIFIED rows are already excluded from champion eval and multi-bet apply "
            "by truth_level filter. No remediation required at this stage. "
            "Rows are isolated, non-contaminating, and well-documented via P138B remark."
        ),
        "db_write_required_later": False,
        "authorization_required_later": True,
        "next_gate": "P144D_LEGACY_UNVERIFIED_REMEDIATION_EXECUTION",
        "note": (
            "If richer traceability is desired before P147 live monitoring, option_b is safe. "
            "Options C and D require explicit authorization with backup verification."
        ),
    }

    # --- Authorization phrase templates ---
    authorization_phrase_templates = {
        "option_a": "P144C_AUTHORIZED_KEEP_LEGACY_UNVERIFIED_AS_GOVERNED_BASELINE_20260529",
        "option_b": "P144C_AUTHORIZED_ENRICH_P10_P12_LEGACY_UNVERIFIED_PROVENANCE_20260529",
        "option_c": "P144C_AUTHORIZED_QUARANTINE_P10_P12_LEGACY_UNVERIFIED_WITH_BACKUP_20260529",
        "option_d": "P144C_AUTHORIZED_DELETE_P10_P12_LEGACY_UNVERIFIED_WITH_STRICT_SELECTOR_20260529",
    }

    # --- Champion monitoring impact ---
    champion_monitoring_impact = {
        "champion_promotion_allowed_in_p144c": False,
        "live_monitoring_blocked_by_legacy_rows": False,
        "registry_update_blocked_by_legacy_rows": False,
        "note": (
            "LEGACY_UNVERIFIED rows are already isolated. "
            "They do not block champion eval or live monitoring."
        ),
        "recommended_before_p147": "option_a or option_b",
    }

    # --- Non-actions ---
    non_actions = {
        "db_write_in_p144c": False,
        "remediation_executed_in_p144c": False,
        "replay_rows_updated_in_p144c": 0,
        "replay_rows_deleted_in_p144c": 0,
        "controlled_apply_executed": False,
        "registry_update_executed": False,
        "champion_promotion_executed": False,
        "monitoring_run_executed": False,
        "scheduler_installed": False,
        "live_api_call_made": False,
        "four_star_executed": False,
        "p108_executed": False,
        "p117_executed": False,
        "p118_executed": False,
    }

    # --- Dirty file hygiene ---
    dirty = _dirty_file_hygiene()

    # --- Roadmap update status ---
    roadmap_txt = ROADMAP.read_text(encoding="utf-8") if ROADMAP.exists() else ""
    cto_txt = CTO.read_text(encoding="utf-8") if CTO.exists() else ""
    roadmap_update_status = {
        "roadmap_updated": "P144C" in roadmap_txt,
        "cto_analysis_updated": "P144C" in cto_txt,
        "note": "Will be updated after artifact generation",
    }

    # --- Remaining risks ---
    remaining_risks = [
        {
            "risk_id": "R1",
            "description": "LEGACY_UNVERIFIED rows could confuse future analyst if not documented",
            "mitigation": "P138B remark + P144C artifact provide full audit trail",
            "severity": "LOW",
        },
        {
            "risk_id": "R2",
            "description": "If option_d is authorized without backup, rows are permanently lost",
            "mitigation": "Backup required gate in all destructive options",
            "severity": "MEDIUM",
        },
        {
            "risk_id": "R3",
            "description": "Autouse-regenerated JSON artifacts may appear as dirty in git status",
            "mitigation": "Whitelist-only staging; restore autouse files before commit",
            "severity": "LOW",
        },
    ]

    # --- Compose full document ---
    doc = {
        "task_id": TASK_ID,
        "classification": CLASSIFICATION,
        "generated_at": now,
        "canonical_repo": CANONICAL_REPO,
        "canonical_branch": CANONICAL_BRANCH,
        "repo_branch_check": rbc,
        "db_snapshot": snap,
        "p146b_source_summary": {
            "artifact_path": str(P146B_JSON),
            "classification": p146b.get("classification"),
            "expected_classification": "P146B_AUTHORIZED_OBSERVATION_ONLY_MONITORING_RUN_COMPLETED",
            "classification_ok": p146b.get("classification") == "P146B_AUTHORIZED_OBSERVATION_ONLY_MONITORING_RUN_COMPLETED",
        },
        "p142_source_summary": {
            "artifact_path": str(P142_JSON),
            "classification": p142.get("classification"),
            "expected_classification": "P142_WAVE2_MULTI_BET_APPLY_CHAIN_CLOSED",
            "classification_ok": p142.get("classification") == "P142_WAVE2_MULTI_BET_APPLY_CHAIN_CLOSED",
        },
        "p138b_source_summary": {
            "artifact_path": str(P138B_JSON),
            "classification": p138b.get("classification"),
            "expected_classification": "P138B_P10_P12_LEGACY_ROWS_REMARKED",
            "classification_ok": p138b.get("classification") == "P138B_P10_P12_LEGACY_ROWS_REMARKED",
            "remark_scope": p138b.get("remark_scope", {}),
        },
        "legacy_unverified_current_state": legacy_state,
        "strict_selector_definitions": strict_selector_definitions,
        "remediation_option_matrix": remediation_option_matrix,
        "recommended_remediation_path": recommended_remediation_path,
        "authorization_phrase_templates": authorization_phrase_templates,
        "champion_monitoring_impact": champion_monitoring_impact,
        "non_actions": non_actions,
        "dirty_file_hygiene": dirty,
        "roadmap_update_status": roadmap_update_status,
        "remaining_risks": remaining_risks,
        "next_recommended_task": {
            "task_id": "P144D",
            "description": "Legacy unverified remediation execution (requires explicit authorization phrase)",
            "prerequisite_artifact": str(OUT_JSON),
            "prerequisite_classification": CLASSIFICATION,
        },
        "summary": (
            f"P144C authorization gate complete. "
            f"LEGACY_UNVERIFIED rows: power_precision_3bet={legacy_state['power_precision_3bet_legacy_unverified_rows']}, "
            f"power_orthogonal_5bet={legacy_state['power_orthogonal_5bet_legacy_unverified_rows']}, "
            f"total={legacy_state['total_legacy_unverified_rows']}. "
            f"All rows have bet_index=1, controlled_apply_id=NULL, source='{actual_source}'. "
            f"No multi-bet contamination. Recommended option: option_a (keep as governed baseline). "
            f"No DB writes in P144C. "
            f"Four remediation options documented with authorization phrases."
        ),
    }

    # --- Write JSON ---
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  JSON written: {OUT_JSON}")

    # --- Write Markdown ---
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    md = _build_markdown(doc, legacy_state, strict_selector_definitions,
                         remediation_option_matrix, recommended_remediation_path,
                         authorization_phrase_templates, champion_monitoring_impact,
                         non_actions, dirty, remaining_risks)
    OUT_MD.write_text(md, encoding="utf-8")
    print(f"  Markdown written: {OUT_MD}")

    # --- Update roadmap / CTO ---
    _update_roadmap()
    _update_cto()

    print(f"\n[P144C] COMPLETE — classification: {CLASSIFICATION}")
    print(f"  Summary: {doc['summary']}")


def _build_markdown(doc: dict, legacy_state: dict, ssd: dict, rom: dict,
                    rrp: dict, apt: dict, cmi: dict, na: dict, dirty: dict,
                    risks: list) -> str:
    lines = [
        f"# P144C: Legacy Unverified Remediation Authorization Gate",
        f"",
        f"**Generated:** {doc['generated_at']}  ",
        f"**Classification:** `{doc['classification']}`  ",
        f"**Canonical Repo:** `{doc['canonical_repo']}`  ",
        f"**Branch:** `{doc['canonical_branch']}`",
        f"",
        f"---",
        f"",
        f"## 1. Repo / Branch Check",
        f"",
        f"| Field | Expected | Actual | OK |",
        f"|-------|----------|--------|----|",
        f"| Repo | `{doc['repo_branch_check']['expected_repo']}` | `{doc['repo_branch_check']['actual_repo']}` | {doc['repo_branch_check']['repo_ok']} |",
        f"| Branch | `{doc['repo_branch_check']['expected_branch']}` | `{doc['repo_branch_check']['actual_branch']}` | {doc['repo_branch_check']['branch_ok']} |",
        f"",
        f"---",
        f"",
        f"## 2. DB Snapshot",
        f"",
        f"| Field | Value |",
        f"|-------|-------|",
        f"| DB Path | `{doc['db_snapshot']['db_path']}` |",
        f"| Total Rows | {doc['db_snapshot']['total_rows']} |",
        f"| Expected Rows | {doc['db_snapshot']['expected_rows']} |",
        f"| Rows OK | {doc['db_snapshot']['rows_ok']} |",
        f"| bet_index column exists | {doc['db_snapshot']['bet_index_column_exists']} |",
        f"",
        f"---",
        f"",
        f"## 3. Predecessor Artifact Validation",
        f"",
        f"| Artifact | Classification | OK |",
        f"|----------|---------------|----|",
        f"| P146B | `{doc['p146b_source_summary']['classification']}` | {doc['p146b_source_summary']['classification_ok']} |",
        f"| P142 | `{doc['p142_source_summary']['classification']}` | {doc['p142_source_summary']['classification_ok']} |",
        f"| P138B | `{doc['p138b_source_summary']['classification']}` | {doc['p138b_source_summary']['classification_ok']} |",
        f"",
        f"---",
        f"",
        f"## 4. LEGACY_UNVERIFIED Current State",
        f"",
        f"| Field | Value |",
        f"|-------|-------|",
        f"| power_precision_3bet rows | {legacy_state['power_precision_3bet_legacy_unverified_rows']} |",
        f"| power_orthogonal_5bet rows | {legacy_state['power_orthogonal_5bet_legacy_unverified_rows']} |",
        f"| Total LEGACY_UNVERIFIED rows | {legacy_state['total_legacy_unverified_rows']} |",
        f"| All rows bet_index=1 | {legacy_state['all_rows_bet_index_1']} |",
        f"| All rows controlled_apply_id NULL | {legacy_state['all_rows_controlled_apply_id_null']} |",
        f"| P140/P141 multi-bet contamination | {legacy_state['p140_p141_multi_bet_contamination']} |",
        f"| Source value | `{legacy_state['actual_source']}` |",
        f"",
        f"---",
        f"",
        f"## 5. Strict Selector Definitions",
        f"",
        f"```sql",
        f"WHERE {ssd['sql_where_clause']}",
        f"```",
        f"",
        f"| Criterion | Value |",
        f"|-----------|-------|",
        f"| strategy_id IN | {ssd['strategy_id_in']} |",
        f"| truth_level | `{ssd['truth_level']}` |",
        f"| bet_index | {ssd['bet_index']} |",
        f"| controlled_apply_id | {ssd['controlled_apply_id']} |",
        f"| source | `{ssd['source']}` |",
        f"",
        f"---",
        f"",
        f"## 6. Remediation Option Matrix",
        f"",
    ]

    for opt_key, opt in rom.items():
        lines += [
            f"### Option: {opt_key}",
            f"",
            f"**Description:** {opt['description']}  ",
            f"**DB Mutation Required:** {opt['db_mutation_required']}  ",
            f"**Row Count Impact:** {opt['row_count_impact']}  ",
            f"**Backup Required:** {opt['backup_required']}  ",
            f"**Rollback Path:** {opt['rollback_path']}  ",
            f"**Risk Level:** {opt['risk_level']}  ",
            f"**Champion Impact:** {opt['champion_impact']}  ",
            f"**Authorization Phrase:** `{opt['authorization_phrase']}`  ",
            f"",
        ]

    lines += [
        f"---",
        f"",
        f"## 7. Recommended Remediation Path",
        f"",
        f"**Recommended Option:** `{rrp['recommended_option']}`  ",
        f"**Reason:** {rrp['reason']}  ",
        f"**DB Write Required Later:** {rrp['db_write_required_later']}  ",
        f"**Next Gate:** `{rrp['next_gate']}`  ",
        f"**Note:** {rrp['note']}",
        f"",
        f"---",
        f"",
        f"## 8. Authorization Phrase Templates",
        f"",
        f"| Option | Authorization Phrase |",
        f"|--------|---------------------|",
    ]
    for k, v in apt.items():
        lines.append(f"| {k} | `{v}` |")

    lines += [
        f"",
        f"---",
        f"",
        f"## 9. Champion / Monitoring Impact",
        f"",
        f"| Field | Value |",
        f"|-------|-------|",
        f"| champion_promotion_allowed_in_p144c | {cmi['champion_promotion_allowed_in_p144c']} |",
        f"| live_monitoring_blocked_by_legacy_rows | {cmi['live_monitoring_blocked_by_legacy_rows']} |",
        f"| registry_update_blocked_by_legacy_rows | {cmi['registry_update_blocked_by_legacy_rows']} |",
        f"| recommended_before_p147 | {cmi['recommended_before_p147']} |",
        f"",
        f"---",
        f"",
        f"## 10. Non-Actions (All False/0)",
        f"",
        f"| Action | Value |",
        f"|--------|-------|",
    ]
    for k, v in na.items():
        lines.append(f"| {k} | {v} |")

    lines += [
        f"",
        f"---",
        f"",
        f"## 11. Dirty File Hygiene",
        f"",
        f"| Field | Value |",
        f"|-------|-------|",
        f"| backups_untracked_not_staged | {dirty['backups_untracked_not_staged']} |",
        f"| forbidden_files_staged | {dirty['forbidden_files_staged']} |",
        f"",
        f"---",
        f"",
        f"## 12. Remaining Risks",
        f"",
    ]
    for r in risks:
        lines += [
            f"**{r['risk_id']}** ({r['severity']}): {r['description']}  ",
            f"Mitigation: {r['mitigation']}  ",
            f"",
        ]

    lines += [
        f"---",
        f"",
        f"## 13. Roadmap / CTO Update",
        f"",
        f"Roadmap and CTO-Analysis updated as part of this script run.",
        f"",
        f"---",
        f"",
        f"## 14. Next Recommended Task",
        f"",
        f"**Task ID:** P144D  ",
        f"**Description:** Legacy unverified remediation execution (requires explicit authorization phrase)  ",
        f"**Prerequisite Artifact:** `{OUT_JSON}`  ",
        f"**Prerequisite Classification:** `{CLASSIFICATION}`",
        f"",
        f"---",
        f"",
        f"## 15. Summary",
        f"",
        doc["summary"],
        f"",
    ]
    return "\n".join(lines)


def _update_roadmap() -> None:
    if not ROADMAP.exists():
        return
    txt = ROADMAP.read_text(encoding="utf-8")
    if "P144C" in txt:
        return
    marker = "## P144"
    insert = (
        f"\n### P144C — Legacy Unverified Remediation Authorization Gate (2026-05-29) [DONE]\n"
        f"Authorization gate: documents 4 remediation options for 100 LEGACY_UNVERIFIED rows (P10/P12). "
        f"No DB writes. Recommended option: keep as governed baseline.\n"
    )
    if marker in txt:
        idx = txt.index(marker)
        txt = txt[:idx] + insert + txt[idx:]
    else:
        txt = txt.rstrip() + "\n" + insert
    ROADMAP.write_text(txt, encoding="utf-8")
    print(f"  Roadmap updated: {ROADMAP}")


def _update_cto() -> None:
    if not CTO.exists():
        return
    txt = CTO.read_text(encoding="utf-8")
    if "P144C" in txt:
        return
    marker = "## P144"
    insert = (
        f"\n### P144C — Legacy Unverified Remediation Authorization Gate (2026-05-29) [DONE]\n"
        f"- 100 LEGACY_UNVERIFIED rows (50 power_precision_3bet + 50 power_orthogonal_5bet) documented\n"
        f"- 4 remediation options with authorization phrases defined\n"
        f"- Recommended: option_a (keep as governed baseline, no DB mutation)\n"
        f"- No DB writes executed in P144C\n"
    )
    if marker in txt:
        idx = txt.index(marker)
        txt = txt[:idx] + insert + txt[idx:]
    else:
        txt = txt.rstrip() + "\n" + insert
    CTO.write_text(txt, encoding="utf-8")
    print(f"  CTO-Analysis updated: {CTO}")


if __name__ == "__main__":
    main()
