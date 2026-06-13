#!/usr/bin/env python3
"""P271L — Controlled Deployment Preflight (READ-ONLY, NON-EXECUTABLE APPLY).

This module produces a deterministic *preflight manifest* for a FUTURE
controlled production schema deployment of the P271J prospective capture
ledger. It is **NOT** a production migration command and performs **no**
deployment action of any kind.

HARD BOUNDARIES (enforced by construction and tests):
  * Read-only. No write to the production database, ever.
  * Never imports sqlite3 for the purpose of opening the production DB, and
    never opens a SQLite connection against the production DB.
  * Accepts an explicit repository root and production DB path.
  * Rejects any apply/deploy flag.
  * Contains no migration execution path.
  * Contains no process signal / kill / restart path.
  * Performs no network request.
  * Raw-hashes files only (SHA-256 over bytes) — it does not open the DB
    through SQLite.
  * Generates a deterministic preflight manifest.
  * Fails closed on missing evidence or conflicting state.

This script intentionally does NOT import sqlite3 at all. The presence of an
`import sqlite3` anywhere in this file would be a contract violation that the
accompanying test-suite asserts against.

Authorization context: P271L is a preflight + authorization-package task only.
Production apply remains UNAUTHORIZED. Official source verification remains
MANUAL_VERIFICATION_REQUIRED. Governance: HOLD / WAITING_FOR_USER_AUTHORIZATION.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess  # used ONLY for read-only `ps -p` / `kill -0` style checks
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Constants — fixed, deterministic. No dynamic time.
# ---------------------------------------------------------------------------

TASK_ID = "P271L_CONTROLLED_DEPLOYMENT_PREFLIGHT_AND_AUTHORIZATION_PACKAGE"
GENERATED_AT = "2026-06-13"  # fixed for deterministic output
MODE = "controlled_deployment_preflight"

CANONICAL_REPO_BASENAME = "LotteryNew"
EXPECTED_MAIN_COMMIT = "847262bd1a6efec3fcc3bff879867f71f7555ade"
P271K_MERGE_COMMIT = "847262bd1a6efec3fcc3bff879867f71f7555ade"
P271K_SOURCE_COMMIT = "b7b6d883bfac6881e4b60d5453ba68ae6d79675e"
P271K_CLASSIFICATION = "P271K_TEMPORARY_DB_MIGRATION_REHEARSAL_COMPLETE"
EXPECTED_PRODUCTION_DB_SHA256 = (
    "3209a533b15e7b12bb8336a6f0cf92114d18dc0ae544de71f04954bdaa1d430e"
)

PRODUCTION_DB_RELPATH = os.path.join("lottery_api", "data", "lottery_v2.db")

# Source-of-truth for the prospective schema. The migration must source schema
# objects from here (P271J), not redefine them.
LEDGER_SOURCE_RELPATH = os.path.join("lottery_api", "prospective_capture_ledger.py")
REHEARSAL_SCRIPT_RELPATH = os.path.join(
    "scripts", "p271k_prospective_capture_ledger_migration_rehearsal.py"
)
RUNTIME_DB_SOURCE_RELPATH = os.path.join("lottery_api", "database.py")

# Schema constants — these MUST match prospective_capture_ledger.py. The
# preflight verifies them against source at runtime and fails closed on drift.
EXPECTED_SCHEMA_VERSION = "p271j_prospective_capture_ledger.v1"
EXPECTED_PROSPECTIVE_TABLES = (
    "prospective_schema_meta",
    "prospective_activation_registry",
    "prospective_capture_batches",
    "prospective_prediction_ledger",
    "prospective_capture_events",
    "prospective_outcome_links",
)
EXPECTED_PROSPECTIVE_INDEXES = (
    "idx_ledger_identity",
    "idx_batch_cluster",
)
EXPECTED_APPEND_ONLY_TABLES = (
    "prospective_activation_registry",
    "prospective_capture_batches",
    "prospective_prediction_ledger",
    "prospective_capture_events",
    "prospective_outcome_links",
)
# Two triggers (no_update, no_delete) per append-only table.
EXPECTED_TRIGGER_COUNT = len(EXPECTED_APPEND_ONLY_TABLES) * 2
EXPECTED_LEDGER_SEMANTIC_UNIQUE = (
    "activation_id",
    "lottery_type",
    "target_draw",
    "strategy_id",
    "strategy_version",
    "bet_index",
)
EXPECTED_PRAGMAS = ("foreign_keys = ON", "busy_timeout = 5000")

# Legacy production tables known from source (lottery_api/database.py). Used for
# the source-defined collision audit; ACTUAL production schema is NOT read here.
LEGACY_TABLES_FROM_SOURCE = (
    "draws",
    "prediction_runs",
    "prediction_items",
    "prediction_results",
    "snapshot_schedule",
    "review_sessions",
    "review_findings",
    "review_hypotheses",
    "review_actions",
    "shadow_experiments",
    "prediction_review_status",
    "strategy_replay_runs",
    "strategy_prediction_replays",
)

# Known LotteryNew DB writer entry points (source-grounded, read-only inventory).
KNOWN_WRITER_SOURCES = (
    "lottery_api/database.py",          # DatabaseManager (insert_draws, vacuum, etc.)
    "lottery_api/routes/ingest.py",     # ingest / backfill HTTP writers
    "lottery_api/fetcher/backfill_engine.py",
    "lottery_api/utils/scheduler.py",   # background scheduler / learning integration
    "tools/post_draw_pipeline.py",      # post-draw automation (writes DB)
    "tools/upload_lottery_data.py",
    "tools/upload_daily539_txt.py",
    "tools/upload_big_lotto_csv.py",
    "scripts/p7_controlled_replay_row_apply.py",
    "scripts/apply_p0_schema_migration.py",
)


# ---------------------------------------------------------------------------
# Fail-closed exception
# ---------------------------------------------------------------------------

class PreflightError(RuntimeError):
    """Raised when evidence is missing or state conflicts. Fail closed."""


# ---------------------------------------------------------------------------
# Read-only primitives
# ---------------------------------------------------------------------------

def raw_sha256(path: str) -> str:
    """SHA-256 over the raw bytes of a file. Never opens via SQLite."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def file_metadata(path: str) -> Dict[str, object]:
    if not os.path.exists(path):
        return {"path": path, "exists": False}
    st = os.stat(path)
    return {
        "path": path,
        "exists": True,
        "size_bytes": st.st_size,
        "mtime_epoch": int(st.st_mtime),
        "inode": st.st_ino,
        "mode_octal": oct(st.st_mode & 0o777),
    }


def canonicalize(path: str) -> str:
    return os.path.realpath(path)


def read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def pid_is_live(pid: int) -> Optional[bool]:
    """Read-only liveness check using `kill -0` semantics.

    Returns True if alive, False if not, None if undeterminable. This NEVER
    sends a terminating signal — signal 0 performs no action on the target.
    """
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        # Process exists but owned by another user — treat as live (conservative).
        return True
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Inspections
# ---------------------------------------------------------------------------

def inspect_sidecars(db_path: str) -> Dict[str, object]:
    """Inventory WAL / SHM / journal sidecars by filename + stat only."""
    base = db_path
    sidecars = {
        "wal": base + "-wal",
        "shm": base + "-shm",
        "journal": base + "-journal",
    }
    out: Dict[str, object] = {}
    wal_present = False
    shm_present = False
    for label, p in sidecars.items():
        meta = file_metadata(p)
        out[label] = meta
        if label == "wal" and meta.get("exists"):
            wal_present = True
        if label == "shm" and meta.get("exists"):
            shm_present = True
    out["wal_present"] = wal_present
    out["shm_present"] = shm_present
    # A present SHM (and/or non-trivial WAL) indicates a writer opened the DB in
    # WAL journal mode at some point — unreconciled with database.py which sets
    # no journal_mode. Flag conservatively.
    out["wal_or_shm_unreconciled"] = bool(wal_present or shm_present)
    return out


def inspect_processes(repo_root: str) -> Dict[str, object]:
    """Read PID files and check liveness without signalling processes."""
    result: Dict[str, object] = {"pid_files": {}, "live_writer_candidate": False}
    missing_evidence = False
    for name in ("backend.pid", "frontend.pid"):
        path = os.path.join(repo_root, name)
        entry: Dict[str, object] = {"path": path, "exists": os.path.exists(path)}
        if entry["exists"]:
            try:
                pid = int(read_text(path).strip())
                entry["pid"] = pid
                live = pid_is_live(pid)
                entry["live"] = live
                entry["stale"] = (live is False)
            except Exception as exc:  # malformed pid file == missing evidence
                entry["error"] = str(exc)
                missing_evidence = True
        else:
            missing_evidence = True
        result["pid_files"][name] = entry
    result["missing_pid_evidence"] = missing_evidence
    return result


def inspect_writers() -> Dict[str, object]:
    """Source-grounded writer inventory (no execution, no DB open)."""
    return {
        "known_writer_sources": list(KNOWN_WRITER_SOURCES),
        "writer_count": len(KNOWN_WRITER_SOURCES),
        "multiple_writers_possible": len(KNOWN_WRITER_SOURCES) > 1,
        "note": (
            "Backend (lottery_api/app.py), ingest/backfill HTTP routes, the "
            "scheduler/learning integrator, post_draw_pipeline, and ad-hoc "
            "upload/controlled-apply scripts can all write the production DB. "
            "More than one writer can exist concurrently. database.py sets no "
            "busy_timeout (immediate SQLITE_BUSY) and no journal_mode."
        ),
    }


def inspect_runtime_db_config(repo_root: str) -> Dict[str, object]:
    """Read database.py (source) for connection/PRAGMA behavior. No DB open."""
    path = os.path.join(repo_root, RUNTIME_DB_SOURCE_RELPATH)
    if not os.path.exists(path):
        raise PreflightError(f"runtime DB source missing: {path}")
    src = read_text(path)
    return {
        "source": RUNTIME_DB_SOURCE_RELPATH,
        "sets_wal": "journal_mode" in src and "WAL" in src,
        "sets_busy_timeout": "busy_timeout" in src,
        "sets_foreign_keys_pragma": "foreign_keys" in src and "PRAGMA" in src,
        "uses_sqlite3_connect": ("sqlite3" + ".connect(") in src,
        "connection_style": (
            "short_lived_per_call"
            if "_get_connection" in src
            else "unknown"
        ),
        "note": (
            "lottery_api/database.py:_get_connection sets NO PRAGMA "
            "(no journal_mode/WAL, no busy_timeout, no foreign_keys). Default "
            "journal mode is rollback (delete). The prospective ledger by "
            "contrast sets foreign_keys=ON and busy_timeout=5000 per write."
        ),
    }


def inspect_source_schema(repo_root: str) -> Dict[str, object]:
    """Verify the prospective schema constants against source. Fail closed."""
    path = os.path.join(repo_root, LEDGER_SOURCE_RELPATH)
    if not os.path.exists(path):
        raise PreflightError(f"ledger source missing: {path}")
    src = read_text(path)

    if EXPECTED_SCHEMA_VERSION not in src:
        raise PreflightError(
            "schema_version drift: expected "
            f"{EXPECTED_SCHEMA_VERSION!r} not found in {LEDGER_SOURCE_RELPATH}"
        )

    # The real ledger defines table names via constants (e.g. _META_TABLE =
    # "prospective_schema_meta") and uses f-strings in CREATE TABLE, while the
    # synthetic test fixture uses literal CREATE TABLE statements. Accept either
    # form: the table name token must appear, AND the source must create tables.
    if "CREATE TABLE IF NOT EXISTS" not in src:
        raise PreflightError("no CREATE TABLE IF NOT EXISTS found in source")
    missing_tables = [t for t in EXPECTED_PROSPECTIVE_TABLES if t not in src]
    if missing_tables:
        raise PreflightError(f"missing prospective table name in source: {missing_tables}")

    missing_indexes = [i for i in EXPECTED_PROSPECTIVE_INDEXES if i not in src]
    if missing_indexes:
        raise PreflightError(f"missing index in source: {missing_indexes}")

    # Append-only trigger templates present.
    if "trg_" not in src or "no_update" not in src or "no_delete" not in src:
        raise PreflightError("append-only trigger templates not found in source")

    # Semantic uniqueness present.
    for col in EXPECTED_LEDGER_SEMANTIC_UNIQUE:
        if col not in src:
            raise PreflightError(f"semantic-unique column missing in source: {col}")

    foreign_keys_referenced = "FOREIGN KEY" in src

    return {
        "source": LEDGER_SOURCE_RELPATH,
        "schema_version": EXPECTED_SCHEMA_VERSION,
        "tables": list(EXPECTED_PROSPECTIVE_TABLES),
        "indexes": list(EXPECTED_PROSPECTIVE_INDEXES),
        "append_only_tables": list(EXPECTED_APPEND_ONLY_TABLES),
        "expected_trigger_count": EXPECTED_TRIGGER_COUNT,
        "semantic_unique_key": list(EXPECTED_LEDGER_SEMANTIC_UNIQUE),
        "foreign_keys_required": foreign_keys_referenced,
        "pragmas_required": list(EXPECTED_PRAGMAS),
        "verified_against_source": True,
    }


def schema_collision_audit() -> Dict[str, object]:
    """Source-defined collision audit between legacy and prospective objects."""
    legacy = set(LEGACY_TABLES_FROM_SOURCE)
    prospective = set(EXPECTED_PROSPECTIVE_TABLES)
    collisions = sorted(legacy & prospective)
    return {
        "legacy_tables_from_source": sorted(legacy),
        "prospective_tables": sorted(prospective),
        "name_collisions": collisions,
        "collision_free_per_source": len(collisions) == 0,
        "note": (
            "Source-level only. ACTUAL production schema is NOT read in P271L. "
            "All prospective objects use a 'prospective_' prefix; no legacy "
            "table from database.py source shares a name."
        ),
    }


# ---------------------------------------------------------------------------
# Contract builders (design-only, non-executable)
# ---------------------------------------------------------------------------

def build_maintenance_window_contract() -> Dict[str, object]:
    return {
        "required": True,
        "states": [
            "Announce maintenance window; freeze all scheduled ingest/learning jobs.",
            "Stop backend (lottery_api/app.py) and frontend via stop_all.sh; "
            "disable launchd KeepAlive (com.kelvin.lottery.dev.plist) so it does "
            "not auto-restart during the window.",
            "Confirm no process holds the production DB (lsof) and PID files are "
            "stale/removed.",
            "Reconcile WAL/SHM: ensure WAL is empty and checkpointed; remove or "
            "account for any -shm/-wal sidecars before backup.",
        ],
        "exit_criteria": "All writers stopped AND verified AND no DB holders.",
    }


def build_writer_quiescence_contract() -> Dict[str, object]:
    return {
        "required": True,
        "evidence_required": [
            "backend.pid / frontend.pid stale or removed",
            "no `python app.py` (cwd lottery_api) process alive",
            "no scheduler / post_draw_pipeline / ingest job running",
            "launchd KeepAlive disabled for the window",
            "lsof shows zero holders of lottery_v2.db",
            "WAL/SHM reconciled (no live writer-created sidecars)",
        ],
        "conservative_rule": (
            "If any active or potentially-active writer cannot be conclusively "
            "quiesced, the apply manifest MUST be NOT_READY_FOR_APPLY."
        ),
    }


def build_backup_strategy() -> Dict[str, object]:
    return {
        "raw_copy_only_while_wal_active": "REJECTED",
        "selected_method": "A_or_B_under_separate_authorization",
        "option_A_maintenance_window": [
            "Stop and verify all writers (writer-quiescence contract).",
            "Verify no active DB holders (lsof).",
            "Checkpoint WAL if authorized; confirm -wal is empty.",
            "Create verified backup (file copy of a quiesced DB).",
        ],
        "option_B_online_backup_api": [
            "Use SQLite online backup API under an explicitly authorized "
            "controlled process with validated source and destination.",
        ],
        "destination_requirements": {
            "outside_repo": True,
            "timestamped_immutable_filename": True,
            "record_source_db_identity_and_hash": True,
            "wal_handling": "checkpoint/reconcile before copy; copy sidecars only "
                            "if consistent snapshot guaranteed",
            "integrity_verification": "post-backup sqlite integrity_check + raw "
                                      "hash recorded (under separate authorization)",
            "restore_rehearsal_required": True,
            "checksum_recording": True,
            "retention_and_deletion_authorization": "explicit human gate",
            "failure_behavior": "abort apply; do not proceed without verified backup",
        },
        "executed_in_p271l": False,
    }


def build_controlled_apply_manifest(
    repo_root: str, db_realpath: str, db_hash: str, readiness: str
) -> Dict[str, object]:
    return {
        "non_executable": True,
        "canonical_repo": repo_root,
        "canonical_repo_basename": CANONICAL_REPO_BASENAME,
        "required_main_commit": EXPECTED_MAIN_COMMIT,
        "production_db_canonical_realpath": db_realpath,
        "expected_pre_apply_sha256": db_hash,
        "hash_revalidation_rule": (
            "Re-hash the production DB immediately before apply; abort on any "
            "drift from the freshly-authorized expected hash."
        ),
        "required_maintenance_window_state": "CONFIRMED",
        "required_writer_quiescence_evidence": "ALL_WRITERS_STOPPED_AND_VERIFIED",
        "required_backup_evidence": "VERIFIED_BACKUP_OUTSIDE_REPO",
        "migration_schema_version": EXPECTED_SCHEMA_VERSION,
        "expected_prospective_tables": list(EXPECTED_PROSPECTIVE_TABLES),
        "expected_prospective_indexes": list(EXPECTED_PROSPECTIVE_INDEXES),
        "expected_trigger_count": EXPECTED_TRIGGER_COUNT,
        "lock_behavior": "BEGIN IMMEDIATE (acquire write lock up-front)",
        "busy_locked_failure_behavior": "abort + rollback; never retry blindly",
        "max_execution_boundary": "single transaction; CREATE-IF-NOT-EXISTS only; "
                                  "no data backfill; no DROP of legacy objects",
        "post_apply_checks": "delegated to P271M verification plan",
        "rollback_triggers": "see rollback_plan",
        "no_activation_declaration": (
            "This apply installs schema only. It MUST NOT insert any activation "
            "record, MUST NOT set status to ACTIVE, MUST NOT write any prediction "
            "rows. Prospective tables remain empty."
        ),
        "p271m_required_after_apply": True,
        "p271n_separately_authorized_after_p271m": True,
        "executable_only_when": (
            "a future prompt contains the exact authorization phrase from "
            "authorization_template AND all pre-apply STOP gates pass"
        ),
        "current_readiness": readiness,
    }


def build_authorization_template(repo_root: str, db_realpath: str) -> Dict[str, object]:
    fields = [
        "YES execute P271L controlled production schema deployment",
        f"repo={repo_root}",
        f"main_commit={EXPECTED_MAIN_COMMIT}",
        f"production_db={db_realpath}",
        "expected_pre_apply_sha256=<fresh hash>",
        "backup_path=<outside-repo path>",
        "maintenance_window_confirmed=YES",
        "all_writers_stopped_and_verified=YES",
        "rollback_plan_confirmed=YES",
    ]
    return {
        "required_fields": [
            "execute_phrase",
            "repo",
            "main_commit",
            "production_db",
            "expected_pre_apply_sha256",
            "backup_path",
            "maintenance_window_confirmed",
            "all_writers_stopped_and_verified",
            "rollback_plan_confirmed",
        ],
        "copyable_template": "\n".join(fields),
        "note": "This task and this template are NOT current authorization.",
    }


def build_pre_apply_stop_gates() -> List[str]:
    return [
        "wrong repo / branch / HEAD",
        "dirty or staged authorized files",
        "production DB hash drift vs freshly-authorized expected hash",
        "active or unverified writers",
        "active DB lock holders",
        "WAL/SHM state not reconciled",
        "backup missing or unverified",
        "actual production schema not inspected under separate authorization",
        "schema collision or incompatible version detected",
        "insufficient disk space for backup",
        "rollback destination missing",
        "production DB already contains unexpected prospective objects",
        "P271M verification plan missing",
        "P271N activation accidentally coupled to deployment",
    ]


def build_post_apply_verification_plan() -> Dict[str, object]:
    return {
        "owner": "P271M (separate task)",
        "checks": [
            "schema_version exact == p271j_prospective_capture_ledger.v1",
            "all expected prospective tables present, exact",
            "all expected indexes present, exact",
            f"trigger count == {EXPECTED_TRIGGER_COUNT} (append-only enforced)",
            "PRAGMA foreign_key_check passes",
            "PRAGMA integrity_check == ok",
            "legacy row-count / content invariants unchanged",
            "prospective tables EMPTY (no rows) unless separately authorized",
            "append-only triggers enforced (UPDATE/DELETE raise ABORT)",
            "semantic uniqueness enforced (composite unique key)",
            "no runtime integration unless separately approved",
            "DB and backup hashes recorded",
            "backend restart only AFTER verification passes",
            "no activation timestamp / no activation record / no prediction capture",
        ],
        "executed_in_p271l": False,
    }


def build_rollback_plan() -> Dict[str, object]:
    return {
        "triggers": [
            "integrity_check / foreign_key_check failure post-apply",
            "unexpected legacy row-count or content change",
            "apply aborted mid-transaction / partial schema",
            "collision or version mismatch discovered during apply",
            "any unexpected prospective rows present",
        ],
        "authorization_owner": "human operator (explicit), same gate as apply",
        "writer_stop_requirement": "all writers stopped before restore",
        "restore_procedure": "restore the verified pre-apply backup over the "
                             "production DB path (quiesced)",
        "post_restore_verification": "raw hash == expected_pre_apply_sha256 AND "
                                     "integrity_check == ok",
        "wal_shm_handling": "remove stale -wal/-shm after restore; verify clean state",
        "partial_drop_prohibition": (
            "Manual partial DROP of prospective objects is PROHIBITED unless "
            "separately designed and authorized."
        ),
        "incident_record_required": True,
    }


# ---------------------------------------------------------------------------
# Readiness decision
# ---------------------------------------------------------------------------

def decide_readiness(
    sidecars: Dict[str, object],
    processes: Dict[str, object],
    writers: Dict[str, object],
    collision: Dict[str, object],
    db_hash_matches: bool,
) -> Tuple[str, List[str]]:
    blockers: List[str] = []

    # Conservative: actual production schema not opened => never EXECUTABLE now.
    blockers.append(
        "actual_production_schema_not_read: separate authorization required for "
        "read-only actual production schema inspection before apply"
    )
    blockers.append(
        "fresh_production_db_hash_verification_required immediately before apply"
    )
    blockers.append(
        "verified_maintenance_window_and_writer_shutdown_required"
    )
    blockers.append(
        "verified_backup_destination_and_rollback_authorization_required"
    )

    if not db_hash_matches:
        blockers.append("PRODUCTION_DB_HASH_DRIFT vs baseline")

    if sidecars.get("wal_or_shm_unreconciled"):
        blockers.append(
            "WAL_OR_SHM_SIDECAR_PRESENT_UNRECONCILED (writer opened DB in WAL "
            "mode; database.py sets no journal_mode)"
        )

    if writers.get("multiple_writers_possible"):
        blockers.append("MULTIPLE_POTENTIAL_WRITERS_NOT_CONCLUSIVELY_QUIESCED")

    if processes.get("missing_pid_evidence"):
        blockers.append("MISSING_OR_MALFORMED_PID_EVIDENCE (fail closed)")

    if not collision.get("collision_free_per_source"):
        return "P271L_BLOCKED_SCHEMA_BREADTH_GAP", blockers

    # Default conservative classification.
    return "P271L_PREFLIGHT_COMPLETE_NOT_READY_FOR_APPLY", blockers


# ---------------------------------------------------------------------------
# Manifest generation
# ---------------------------------------------------------------------------

@dataclass
class PreflightConfig:
    repo_root: str
    production_db_path: str
    apply: bool = False  # MUST stay False; any True is rejected.
    deploy: bool = False  # MUST stay False; any True is rejected.


def generate_manifest(cfg: PreflightConfig) -> Dict[str, object]:
    # Reject any apply/deploy intent. Fail closed.
    if cfg.apply or cfg.deploy:
        raise PreflightError(
            "apply/deploy flags are forbidden in the preflight script; "
            "this is NOT a production migration command"
        )

    repo_root = canonicalize(cfg.repo_root)

    # Repo identity guard.
    if os.path.basename(repo_root) != CANONICAL_REPO_BASENAME:
        raise PreflightError(
            f"non-canonical repo root: {repo_root} "
            f"(expected basename {CANONICAL_REPO_BASENAME})"
        )

    db_path = cfg.production_db_path
    if not os.path.isabs(db_path):
        db_path = os.path.join(repo_root, db_path)
    db_realpath = canonicalize(db_path)

    if not os.path.exists(db_realpath):
        raise PreflightError(f"production DB not found (fail closed): {db_realpath}")

    db_hash = raw_sha256(db_realpath)  # raw bytes only; never via SQLite
    db_hash_matches = (db_hash == EXPECTED_PRODUCTION_DB_SHA256)

    fs_meta = file_metadata(db_realpath)
    sidecars = inspect_sidecars(db_realpath)
    processes = inspect_processes(repo_root)
    writers = inspect_writers()
    runtime_cfg = inspect_runtime_db_config(repo_root)
    source_schema = inspect_source_schema(repo_root)
    collision = schema_collision_audit()

    readiness, blockers = decide_readiness(
        sidecars, processes, writers, collision, db_hash_matches
    )

    manifest: Dict[str, object] = {
        "task_id": TASK_ID,
        "generated_at": GENERATED_AT,
        "mode": MODE,
        "preflight_only": True,
        "p271k_merge_commit": P271K_MERGE_COMMIT,
        "p271k_source_commit": P271K_SOURCE_COMMIT,
        "p271k_classification": P271K_CLASSIFICATION,
        # Negative declarations — all must remain false.
        "production_db_opened": False,
        "production_db_copied": False,
        "production_db_written": False,
        "backup_executed": False,
        "checkpoint_executed": False,
        "restore_executed": False,
        "production_migration_executed": False,
        "production_schema_modified": False,
        "runtime_integration_added": False,
        "process_stopped_or_restarted": False,
        "deployment_started": False,
        "prospective_collection_activated": False,
        "activation_timestamp_inserted": False,
        "actual_production_schema_read": False,
        "actual_production_schema_limitation":
            "ACTUAL_PRODUCTION_SCHEMA_NOT_READ_IN_P271L_PREFLIGHT",
        # Evidence.
        "source_verification_status": "MANUAL_VERIFICATION_REQUIRED",
        "production_db_path": db_realpath,
        "production_db_sha256": db_hash,
        "production_db_sha256_expected": EXPECTED_PRODUCTION_DB_SHA256,
        "production_db_hash_matches_baseline": db_hash_matches,
        "filesystem_metadata": fs_meta,
        "sidecar_inventory": sidecars,
        "process_inventory": processes,
        "writer_inventory": writers,
        "runtime_db_config": runtime_cfg,
        "source_schema_inventory": source_schema,
        "prospective_schema_inventory": source_schema,
        "schema_collision_result": collision,
        # Contracts.
        "maintenance_window_contract": build_maintenance_window_contract(),
        "writer_quiescence_contract": build_writer_quiescence_contract(),
        "backup_strategy": build_backup_strategy(),
        "controlled_apply_manifest": build_controlled_apply_manifest(
            repo_root, db_realpath, db_hash, readiness
        ),
        "authorization_template": build_authorization_template(repo_root, db_realpath),
        "pre_apply_stop_gates": build_pre_apply_stop_gates(),
        "post_apply_verification_plan": build_post_apply_verification_plan(),
        "rollback_plan": build_rollback_plan(),
        "p271m_verification_required": True,
        "p271n_separate_authorization_required": True,
        "p271m_started": False,
        "p271n_started": False,
        # Decision.
        "readiness_for_apply_authorization": readiness,
        "blockers": blockers,
        "governance": "HOLD / WAITING_FOR_USER_AUTHORIZATION",
        "is_production_migration_command": False,
    }
    return manifest


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "P271L controlled deployment PREFLIGHT (read-only). "
            "This is NOT a production migration command."
        )
    )
    p.add_argument("--repo-root", required=True, help="canonical repository root")
    p.add_argument(
        "--production-db",
        default=PRODUCTION_DB_RELPATH,
        help="production DB path (relative to repo root or absolute)",
    )
    p.add_argument("--out", default=None, help="optional output JSON path")
    # No --apply / --deploy flags are accepted. Their absence is intentional.
    return p


def main(argv: Optional[List[str]] = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    # Defensive: reject any stray apply/deploy-looking token.
    raw = " ".join(argv or [])
    if re.search(r"--?(apply|deploy|migrate|execute)\b", raw):
        raise PreflightError("apply/deploy/migrate/execute flags are forbidden")

    cfg = PreflightConfig(
        repo_root=args.repo_root,
        production_db_path=args.production_db,
    )
    manifest = generate_manifest(cfg)
    text = json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
    print(text)
    print(
        "\n[NOTICE] P271L preflight only. Production apply is NOT authorized. "
        "Official source: MANUAL_VERIFICATION_REQUIRED. "
        "Governance: HOLD / WAITING_FOR_USER_AUTHORIZATION.",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
