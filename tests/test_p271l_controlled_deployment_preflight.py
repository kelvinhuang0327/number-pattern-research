"""P271L controlled-deployment-preflight tests.

Synthetic filesystem / process / config fixtures only. These tests NEVER touch
the real production DB, never open SQLite, never start/stop processes, and never
hit the network. They assert the preflight script's read-only, fail-closed,
non-executable contract and the completeness of the authorization package.

Required coverage: 48 items (see docstrings). Collected count is reported by
pytest; the file enumerates exactly 48 test functions.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import sys

import pytest

# ---------------------------------------------------------------------------
# Load the module under test by path (scripts/ is not a package).
# ---------------------------------------------------------------------------

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_THIS_DIR)
_MODULE_PATH = os.path.join(
    _REPO_ROOT, "scripts", "p271l_controlled_deployment_preflight.py"
)

_spec = importlib.util.spec_from_file_location("p271l_preflight", _MODULE_PATH)
pf = importlib.util.module_from_spec(_spec)
# Register before exec so dataclass introspection (py3.14) can resolve the module.
sys.modules["p271l_preflight"] = pf
_spec.loader.exec_module(pf)  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# Synthetic fixtures
# ---------------------------------------------------------------------------

EXPECTED_HASH = pf.EXPECTED_PRODUCTION_DB_SHA256


def _write(path: str, data: bytes) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(data)


def _bytes_for_hash(target_hex: str) -> bytes:
    """Brute-force tiny content whose sha256 equals target is infeasible; instead
    we monkeypatch raw_sha256 in tests that require the baseline match."""
    return b"synthetic"


@pytest.fixture
def synth_repo(tmp_path, monkeypatch):
    """Build a synthetic repo named 'LotteryNew' with the source files the
    preflight reads, plus a fake production DB and sidecars."""
    repo = tmp_path / "LotteryNew"
    (repo / "lottery_api" / "data").mkdir(parents=True)
    (repo / "scripts").mkdir(parents=True)

    # Synthetic database.py: short-lived connect, NO pragmas (matches reality).
    db_src = (
        "import sqlite3\n"
        "class DatabaseManager:\n"
        "    def _get_connection(self):\n"
        "        conn = sqlite3.connect(self.db_path)\n"
        "        conn.row_factory = sqlite3.Row\n"
        "        return conn\n"
    )
    _write(str(repo / "lottery_api" / "database.py"), db_src.encode())

    # Synthetic prospective_capture_ledger.py with all required schema markers.
    tables = pf.EXPECTED_PROSPECTIVE_TABLES
    creates = "\n".join(f"CREATE TABLE IF NOT EXISTS {t} (x TEXT)" for t in tables)
    idx = "\n".join(
        f"CREATE UNIQUE INDEX IF NOT EXISTS {i} ON foo (a)"
        for i in pf.EXPECTED_PROSPECTIVE_INDEXES
    )
    uniq = ", ".join(pf.EXPECTED_LEDGER_SEMANTIC_UNIQUE)
    ledger_src = (
        f'SCHEMA_VERSION = "{pf.EXPECTED_SCHEMA_VERSION}"\n'
        f"{creates}\n{idx}\n"
        "CREATE TRIGGER IF NOT EXISTS trg_x_no_update BEFORE UPDATE ON x BEGIN SELECT 1; END\n"
        "CREATE TRIGGER IF NOT EXISTS trg_x_no_delete BEFORE DELETE ON x BEGIN SELECT 1; END\n"
        f"FOREIGN KEY (activation_id) REFERENCES prospective_activation_registry\n"
        f"UNIQUE ({uniq})\n"
        "PRAGMA foreign_keys = ON\n"
        "PRAGMA busy_timeout = 5000\n"
    )
    _write(
        str(repo / "lottery_api" / "prospective_capture_ledger.py"),
        ledger_src.encode(),
    )

    db_file = repo / "lottery_api" / "data" / "lottery_v2.db"
    _write(str(db_file), b"SYNTHETIC-DB-BYTES")

    return repo


@pytest.fixture
def matching_hash(monkeypatch):
    """Force raw_sha256 to return the baseline hash so hash-match paths run."""
    monkeypatch.setattr(pf, "raw_sha256", lambda p: EXPECTED_HASH)


def _cfg(repo):
    return pf.PreflightConfig(
        repo_root=str(repo),
        production_db_path="lottery_api/data/lottery_v2.db",
    )


# ===========================================================================
# 1. no import-time production DB access
# ===========================================================================
def test_01_no_import_time_production_db_access():
    src = open(_MODULE_PATH, encoding="utf-8").read()
    # Module imports must not open any DB; assert no module-level connect call.
    assert "generate_manifest(" not in src.split("def ", 1)[0]
    assert "raw_sha256(" not in src.split("\nclass ", 1)[0].split("\ndef ", 1)[0]


# 2. no sqlite3 production connection path
def test_02_no_sqlite3_in_preflight_source():
    src = open(_MODULE_PATH, encoding="utf-8").read()
    # The preflight must never IMPORT sqlite3 nor call sqlite3.connect.
    # (A prose mention inside the module docstring is allowed; we assert on
    # actual statements only.)
    for line in src.splitlines():
        stripped = line.strip()
        assert not stripped.startswith("import sqlite3")
        assert not stripped.startswith("from sqlite3")
    assert "sqlite3.connect" not in src


# 3. no apply/deploy execution function
def test_03_no_apply_or_deploy_execution_function():
    names = [n for n in dir(pf) if callable(getattr(pf, n))]
    forbidden = re.compile(r"(execute_apply|run_apply|do_deploy|apply_migration|run_migration)")
    assert not any(forbidden.search(n) for n in names)


# 4. explicit repo/DB inputs required
def test_04_explicit_repo_and_db_inputs_required():
    parser = pf._build_arg_parser()
    with pytest.raises(SystemExit):
        parser.parse_args([])  # --repo-root required


# 5. wrong repo rejected
def test_05_wrong_repo_rejected(tmp_path):
    bad = tmp_path / "NotLotteryNew"
    (bad / "lottery_api" / "data").mkdir(parents=True)
    _write(str(bad / "lottery_api" / "data" / "lottery_v2.db"), b"x")
    with pytest.raises(pf.PreflightError):
        pf.generate_manifest(pf.PreflightConfig(str(bad), "lottery_api/data/lottery_v2.db"))


# 6. non-main baseline rejected (expected main commit constant present + asserted)
def test_06_expected_main_commit_constant():
    assert pf.EXPECTED_MAIN_COMMIT == "847262bd1a6efec3fcc3bff879867f71f7555ade"
    m = pf.build_controlled_apply_manifest("/r", "/r/db", "h", "X")
    assert m["required_main_commit"] == pf.EXPECTED_MAIN_COMMIT


# 7. expected merge commit required
def test_07_expected_merge_commit_required(synth_repo, matching_hash):
    man = pf.generate_manifest(_cfg(synth_repo))
    assert man["p271k_merge_commit"] == "847262bd1a6efec3fcc3bff879867f71f7555ade"


# 8. production DB path canonicalization
def test_08_db_path_canonicalization(synth_repo, matching_hash):
    man = pf.generate_manifest(_cfg(synth_repo))
    assert os.path.isabs(man["production_db_path"])
    assert man["production_db_path"] == os.path.realpath(man["production_db_path"])


# 9. production DB raw hashing only
def test_09_raw_hashing_only(tmp_path):
    f = tmp_path / "x.bin"
    f.write_bytes(b"abc")
    expect = hashlib.sha256(b"abc").hexdigest()
    assert pf.raw_sha256(str(f)) == expect


# 10. DB hash drift blocks readiness
def test_10_hash_drift_in_blockers(synth_repo, monkeypatch):
    monkeypatch.setattr(pf, "raw_sha256", lambda p: "deadbeef")
    man = pf.generate_manifest(_cfg(synth_repo))
    assert man["production_db_hash_matches_baseline"] is False
    assert any("HASH_DRIFT" in b for b in man["blockers"])


# 11. active backend marks apply not ready
def test_11_active_backend_blocks_apply(synth_repo, matching_hash):
    _write(str(synth_repo / "backend.pid"), str(os.getpid()).encode())
    man = pf.generate_manifest(_cfg(synth_repo))
    assert man["readiness_for_apply_authorization"] != "P271L_CONTROLLED_DEPLOYMENT_PREFLIGHT_COMPLETE"
    assert man["process_inventory"]["pid_files"]["backend.pid"]["live"] is True


# 12. missing PID evidence fails closed
def test_12_missing_pid_evidence(synth_repo, matching_hash):
    man = pf.generate_manifest(_cfg(synth_repo))  # no pid files written
    assert man["process_inventory"]["missing_pid_evidence"] is True
    assert any("PID_EVIDENCE" in b for b in man["blockers"])


# 13. stale PID distinguished from live PID
def test_13_stale_vs_live_pid(synth_repo, matching_hash):
    _write(str(synth_repo / "backend.pid"), b"999999")  # very unlikely live
    _write(str(synth_repo / "frontend.pid"), str(os.getpid()).encode())
    man = pf.generate_manifest(_cfg(synth_repo))
    be = man["process_inventory"]["pid_files"]["backend.pid"]
    fe = man["process_inventory"]["pid_files"]["frontend.pid"]
    assert be["stale"] is True
    assert fe["live"] is True


# 14. multiple potential writers fail closed
def test_14_multiple_writers(synth_repo, matching_hash):
    man = pf.generate_manifest(_cfg(synth_repo))
    assert man["writer_inventory"]["multiple_writers_possible"] is True
    assert any("MULTIPLE_POTENTIAL_WRITERS" in b for b in man["blockers"])


# 15. WAL sidecar inventory
def test_15_wal_sidecar_inventory(synth_repo, matching_hash):
    dbp = str(synth_repo / "lottery_api" / "data" / "lottery_v2.db")
    _write(dbp + "-wal", b"")
    man = pf.generate_manifest(_cfg(synth_repo))
    assert man["sidecar_inventory"]["wal"]["exists"] is True
    assert man["sidecar_inventory"]["wal_present"] is True


# 16. SHM sidecar inventory
def test_16_shm_sidecar_inventory(synth_repo, matching_hash):
    dbp = str(synth_repo / "lottery_api" / "data" / "lottery_v2.db")
    _write(dbp + "-shm", b"\0" * 32768)
    man = pf.generate_manifest(_cfg(synth_repo))
    assert man["sidecar_inventory"]["shm"]["exists"] is True
    assert man["sidecar_inventory"]["shm_present"] is True
    assert any("WAL_OR_SHM" in b for b in man["blockers"])


# 17. raw-copy-only active-WAL backup rejected
def test_17_raw_copy_backup_rejected():
    bs = pf.build_backup_strategy()
    assert bs["raw_copy_only_while_wal_active"] == "REJECTED"


# 18. backup path must be outside repo
def test_18_backup_outside_repo():
    bs = pf.build_backup_strategy()
    assert bs["destination_requirements"]["outside_repo"] is True


# 19. backup checksum required
def test_19_backup_checksum_required():
    bs = pf.build_backup_strategy()
    assert bs["destination_requirements"]["checksum_recording"] is True


# 20. backup integrity verification required
def test_20_backup_integrity_required():
    bs = pf.build_backup_strategy()
    assert "integrity" in bs["destination_requirements"]["integrity_verification"].lower()


# 21. actual production schema unread limitation recorded
def test_21_actual_schema_unread_recorded(synth_repo, matching_hash):
    man = pf.generate_manifest(_cfg(synth_repo))
    assert man["actual_production_schema_read"] is False
    assert man["actual_production_schema_limitation"] == (
        "ACTUAL_PRODUCTION_SCHEMA_NOT_READ_IN_P271L_PREFLIGHT"
    )


# 22. source-defined schema inventory deterministic
def test_22_source_schema_deterministic(synth_repo):
    a = pf.inspect_source_schema(str(synth_repo))
    b = pf.inspect_source_schema(str(synth_repo))
    assert a == b
    assert a["schema_version"] == pf.EXPECTED_SCHEMA_VERSION


# 23. legacy/prospective collision audit
def test_23_collision_audit():
    c = pf.schema_collision_audit()
    assert c["collision_free_per_source"] is True
    assert c["name_collisions"] == []


# 24. prospective schema version recorded
def test_24_schema_version_recorded(synth_repo, matching_hash):
    man = pf.generate_manifest(_cfg(synth_repo))
    assert man["prospective_schema_inventory"]["schema_version"] == pf.EXPECTED_SCHEMA_VERSION


# 25. required tables/indexes/triggers recorded
def test_25_tables_indexes_triggers_recorded(synth_repo):
    s = pf.inspect_source_schema(str(synth_repo))
    assert set(s["tables"]) == set(pf.EXPECTED_PROSPECTIVE_TABLES)
    assert set(s["indexes"]) == set(pf.EXPECTED_PROSPECTIVE_INDEXES)
    assert s["expected_trigger_count"] == pf.EXPECTED_TRIGGER_COUNT == 10


# 26. foreign-key requirements recorded
def test_26_foreign_key_requirements(synth_repo):
    s = pf.inspect_source_schema(str(synth_repo))
    assert s["foreign_keys_required"] is True


# 27. append-only requirements recorded
def test_27_append_only_requirements(synth_repo):
    s = pf.inspect_source_schema(str(synth_repo))
    assert set(s["append_only_tables"]) == set(pf.EXPECTED_APPEND_ONLY_TABLES)


# 28. semantic uniqueness requirements recorded
def test_28_semantic_uniqueness(synth_repo):
    s = pf.inspect_source_schema(str(synth_repo))
    assert tuple(s["semantic_unique_key"]) == pf.EXPECTED_LEDGER_SEMANTIC_UNIQUE


# 29. maintenance-window gate
def test_29_maintenance_window_gate():
    mw = pf.build_maintenance_window_contract()
    assert mw["required"] is True
    assert mw["exit_criteria"]


# 30. writer-quiescence gate
def test_30_writer_quiescence_gate():
    wq = pf.build_writer_quiescence_contract()
    assert wq["required"] is True
    assert "NOT_READY_FOR_APPLY" in wq["conservative_rule"]


# 31. active-lock gate
def test_31_active_lock_gate():
    gates = pf.build_pre_apply_stop_gates()
    assert any("lock holders" in g for g in gates)


# 32. disk-space gate
def test_32_disk_space_gate():
    gates = pf.build_pre_apply_stop_gates()
    assert any("disk space" in g for g in gates)


# 33. rollback-path gate
def test_33_rollback_path_gate():
    gates = pf.build_pre_apply_stop_gates()
    assert any("rollback destination" in g for g in gates)


# 34. P271M plan required
def test_34_p271m_plan_required(synth_repo, matching_hash):
    man = pf.generate_manifest(_cfg(synth_repo))
    assert man["p271m_verification_required"] is True
    assert pf.build_post_apply_verification_plan()["owner"].startswith("P271M")


# 35. P271N kept separate
def test_35_p271n_separate(synth_repo, matching_hash):
    man = pf.generate_manifest(_cfg(synth_repo))
    assert man["p271n_separate_authorization_required"] is True
    assert man["p271n_started"] is False


# 36. no activation in apply manifest
def test_36_no_activation_in_apply_manifest():
    m = pf.build_controlled_apply_manifest("/r", "/r/db", "h", "X")
    assert "MUST NOT insert any activation" in m["no_activation_declaration"]


# 37. authorization template contains all required fields
def test_37_authorization_template_fields():
    t = pf.build_authorization_template("/r", "/r/db")
    for field in (
        "execute_phrase", "repo", "main_commit", "production_db",
        "expected_pre_apply_sha256", "backup_path", "maintenance_window_confirmed",
        "all_writers_stopped_and_verified", "rollback_plan_confirmed",
    ):
        assert field in t["required_fields"]
    assert "YES execute P271L controlled production schema deployment" in t["copyable_template"]


# 38. manifest is non-executable
def test_38_manifest_non_executable():
    m = pf.build_controlled_apply_manifest("/r", "/r/db", "h", "X")
    assert m["non_executable"] is True


# 39. no production backup/checkpoint/restore performed
def test_39_no_backup_checkpoint_restore(synth_repo, matching_hash):
    man = pf.generate_manifest(_cfg(synth_repo))
    assert man["backup_executed"] is False
    assert man["checkpoint_executed"] is False
    assert man["restore_executed"] is False


# 40. no process signal/restart capability
def test_40_no_process_signal_restart_capability():
    src = open(_MODULE_PATH, encoding="utf-8").read()
    # Only kill(pid, 0) read-check is allowed; no terminating signals.
    assert "SIGKILL" not in src
    assert "SIGTERM" not in src
    assert "os.killpg" not in src
    assert ".terminate(" not in src
    # The only os.kill use is the signal-0 liveness check.
    kills = re.findall(r"os\.kill\([^)]*\)", src)
    assert all("0)" in k for k in kills)


# 41. no network access
def test_41_no_network_access():
    src = open(_MODULE_PATH, encoding="utf-8").read()
    for bad in ("import requests", "import urllib", "import http.client",
                "socket.socket", "urlopen", "httpx"):
        assert bad not in src


# 42. no production migration added
def test_42_no_production_migration_path():
    src = open(_MODULE_PATH, encoding="utf-8").read()
    assert "is_production_migration_command" in src
    m = pf.build_controlled_apply_manifest("/r", "/r/db", "h", "X")
    # apply manifest only becomes executable via future explicit authorization
    assert "future prompt contains the exact authorization phrase" in m["executable_only_when"]


# 43. no runtime integration
def test_43_no_runtime_integration(synth_repo, matching_hash):
    man = pf.generate_manifest(_cfg(synth_repo))
    assert man["runtime_integration_added"] is False


# 44. production DB hash unchanged (re-hash equals first hash; read-only)
def test_44_db_hash_unchanged(synth_repo):
    dbp = str(synth_repo / "lottery_api" / "data" / "lottery_v2.db")
    h1 = pf.raw_sha256(dbp)
    pf.generate_manifest(_cfg(synth_repo))
    h2 = pf.raw_sha256(dbp)
    assert h1 == h2  # preflight did not mutate the DB


# 45. P271I/J/K artifacts unchanged (preflight reads, never writes them)
def test_45_artifacts_not_written_by_preflight():
    src = open(_MODULE_PATH, encoding="utf-8").read()
    # No write/open('w') against any p271 artifact path.
    assert "p271i_" not in src
    assert not re.search(r"open\([^)]*p271[ijk]", src)


# 46. no repository DB/temp residue (preflight writes nothing into a repo by default)
def test_46_no_repo_residue(synth_repo, matching_hash):
    before = set(os.listdir(synth_repo / "lottery_api" / "data"))
    pf.generate_manifest(_cfg(synth_repo))
    after = set(os.listdir(synth_repo / "lottery_api" / "data"))
    assert before == after  # no new files created in the DB dir


# 47. deterministic JSON output
def test_47_deterministic_json(synth_repo, matching_hash):
    m1 = pf.generate_manifest(_cfg(synth_repo))
    m2 = pf.generate_manifest(_cfg(synth_repo))
    j1 = json.dumps(m1, indent=2, sort_keys=True, ensure_ascii=False)
    j2 = json.dumps(m2, indent=2, sort_keys=True, ensure_ascii=False)
    assert j1 == j2
    assert m1["generated_at"] == "2026-06-13"  # fixed, not dynamic


# 48. HOLD and MANUAL_VERIFICATION_REQUIRED declarations
def test_48_hold_and_manual_verification(synth_repo, matching_hash):
    man = pf.generate_manifest(_cfg(synth_repo))
    assert man["governance"] == "HOLD / WAITING_FOR_USER_AUTHORIZATION"
    assert man["source_verification_status"] == "MANUAL_VERIFICATION_REQUIRED"
    assert man["readiness_for_apply_authorization"] == (
        "P271L_PREFLIGHT_COMPLETE_NOT_READY_FOR_APPLY"
    )


# ---------------------------------------------------------------------------
# Extra guard: apply/deploy flags rejected at config level
# ---------------------------------------------------------------------------
def test_49_apply_flag_rejected(synth_repo):
    cfg = pf.PreflightConfig(str(synth_repo), "lottery_api/data/lottery_v2.db", apply=True)
    with pytest.raises(pf.PreflightError):
        pf.generate_manifest(cfg)


def test_50_deploy_flag_rejected(synth_repo):
    cfg = pf.PreflightConfig(str(synth_repo), "lottery_api/data/lottery_v2.db", deploy=True)
    with pytest.raises(pf.PreflightError):
        pf.generate_manifest(cfg)
