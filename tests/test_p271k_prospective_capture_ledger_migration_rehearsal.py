"""P271K — temporary-DB migration rehearsal tests.

Every database used here is a pytest ``tmp_path`` file, an OS temp directory
*outside* the repository, or ``sqlite3 ":memory:"``. No test opens, copies, or
writes the canonical production database, requires the network, alters
environment configuration, or invokes any route / production service.

The rehearsal proves the merged P271J prospective schema installs additively on
a source-grounded representative legacy schema without disturbing it, is
idempotent, rolls back atomically on drift / injected failure, preserves caller
transaction ownership, fails closed when the DB is locked, and supports
temporary-only backup/restore. It does NOT authorise P271L–P271N.
"""

from __future__ import annotations

import hashlib
import importlib
import os
import re
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import lottery_api.prospective_capture_ledger as pcl  # noqa: E402
import p271k_prospective_capture_ledger_migration_rehearsal as rk  # noqa: E402

SCRIPT_PATH = SCRIPTS / "p271k_prospective_capture_ledger_migration_rehearsal.py"
SCRIPT_SRC = SCRIPT_PATH.read_text(encoding="utf-8")
DATABASE_PY = ROOT / "lottery_api" / "database.py"
DATABASE_SRC = DATABASE_PY.read_text(encoding="utf-8")
PROD_DB = ROOT / "lottery_api" / "data" / "lottery_v2.db"

EXPECTED_PROD_DB_SHA256 = (
    "3209a533b15e7b12bb8336a6f0cf92114d18dc0ae544de71f04954bdaa1d430e"
)
EXPECTED_P271J_MODULE_SHA256 = (
    "18e221ee632a81fbdb95cab171d3c3a4bae3bf2222f9f2c58c8a3398584c71db"
)
P271J_MERGE_COMMIT = "3dc06f76a70ff13927b63491fb4580528ed86a3d"

# Artifacts that must remain present and unchanged by this task (G/H/I/J).
PRESERVED_ARTIFACTS = (
    "lottery_api/prospective_capture_ledger.py",
    "tests/test_p271j_prospective_capture_ledger_implementation.py",
    "outputs/research/p271j_prospective_capture_ledger_implementation_20260613.json",
    "outputs/research/p271j_prospective_capture_ledger_implementation_20260613.md",
    "outputs/research/p271i_prospective_capture_ledger_implementation_design_20260613.json",
    "tests/test_p271i_prospective_capture_ledger_implementation_design.py",
    "outputs/research/p271h_prospective_capture_feasibility_audit_20260612.json",
    "outputs/research/p271g_prize_aware_null_prospective_preregistration_20260612.json",
)


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# Shared one-shot suite run (the locked scenario costs one busy_timeout wait;
# run it a single time and assert against the structured result everywhere).
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def suite_report(tmp_path_factory):
    workdir = tmp_path_factory.mktemp("p271k_suite")
    return rk.run_rehearsal_suite(str(workdir))


def _scenario(suite_report, name):
    return suite_report["scenarios"][name]


# ---------------------------------------------------------------------------
# Isolation / import safety
# ---------------------------------------------------------------------------


def test_no_import_time_db_access():
    # Every sqlite3.connect( occurrence must be inside a function (indented),
    # so importing the module performs no database access.
    for i, line in enumerate(SCRIPT_SRC.splitlines(), 1):
        if "sqlite3.connect(" in line:
            assert line[:1].isspace(), f"top-level sqlite3.connect at line {i}: {line!r}"


def test_reimport_does_not_touch_production_db():
    before = _sha256_file(PROD_DB)
    importlib.reload(rk)
    after = _sha256_file(PROD_DB)
    assert before == after == EXPECTED_PROD_DB_SHA256


def test_no_network_or_runtime_imports():
    forbidden = ("requests", "urllib.request", "httpx", "socket", "flask",
                 "fastapi", "uvicorn", "aiohttp")
    for token in forbidden:
        assert f"import {token}" not in SCRIPT_SRC, token
    # Does not import production runtime / route / server modules.
    assert "lottery_api.routes" not in SCRIPT_SRC
    assert "lottery_api.database" not in SCRIPT_SRC


def test_script_delegates_schema_to_p271j(tmp_path):
    # The script must not re-define the prospective schema; it delegates to the
    # merged module. Behavioural proof: installed version + objects match pcl.
    db = tmp_path / "delegate.db"
    conn = rk.connect_temporary(str(db))
    try:
        rk.build_legacy_fixture(conn)
        version = rk.install_prospective_schema(conn)
        assert version == pcl.SCHEMA_VERSION
        objs = pcl.schema_objects(conn)
        assert set(pcl.REQUIRED_TABLES) <= objs["tables"]
    finally:
        conn.close()
    # The script contains no literal CREATE TABLE for a real prospective_* table.
    for table in pcl.REQUIRED_TABLES:
        assert f"CREATE TABLE IF NOT EXISTS {table}" not in SCRIPT_SRC
        assert f"CREATE TABLE {table}" not in SCRIPT_SRC


# ---------------------------------------------------------------------------
# Path safety (J)
# ---------------------------------------------------------------------------


def test_explicit_path_required():
    with pytest.raises(rk.PathSafetyError):
        rk.validate_temporary_db_path(None)
    with pytest.raises(rk.PathSafetyError):
        rk.validate_temporary_db_path("")


def test_canonical_realpath_rejected():
    with pytest.raises(rk.PathSafetyError):
        rk.validate_temporary_db_path(str(PROD_DB))
    with pytest.raises(rk.PathSafetyError):
        rk.validate_temporary_db_path(rk.CANONICAL_PRODUCTION_DB)


def test_canonical_symlink_rejected(tmp_path):
    link = tmp_path / "sneaky_link.db"
    os.symlink(rk.CANONICAL_PRODUCTION_DB, link)
    try:
        with pytest.raises(rk.PathSafetyError):
            rk.validate_temporary_db_path(str(link))
    finally:
        os.unlink(link)


def test_repository_path_rejected():
    with pytest.raises(rk.PathSafetyError):
        rk.validate_temporary_db_path(str(ROOT / "scratch_p271k.db"))
    with pytest.raises(rk.PathSafetyError):
        rk.validate_temporary_db_path(str(ROOT / "lottery_api" / "data" / "x.db"))


def test_outside_repo_tmp_accepted(tmp_path):
    target = tmp_path / "ok.db"
    accepted = rk.validate_temporary_db_path(str(target))
    assert accepted == os.path.realpath(str(target))


def test_validate_does_not_create_file(tmp_path):
    target = tmp_path / "never_created.db"
    rk.validate_temporary_db_path(str(target))
    assert not target.exists()


def test_memory_allowed_for_install_but_not_file_ops():
    assert rk.validate_temporary_db_path(":memory:") == ":memory:"
    with pytest.raises(rk.PathSafetyError):
        rk.validate_temporary_db_path(":memory:", require_file=True)


def test_scenario_path_safety(suite_report):
    detail = _scenario(suite_report, "J_path_safety")
    assert detail["passed"], detail
    assert detail["detail"]["canonical_rejected"]
    assert detail["detail"]["repo_path_rejected"]
    assert detail["detail"]["symlink_to_canonical_rejected"]
    assert detail["detail"]["outside_tmp_accepted"]


# ---------------------------------------------------------------------------
# Legacy fixture grounding
# ---------------------------------------------------------------------------


def test_legacy_fixture_creates_grounded_tables():
    conn = sqlite3.connect(":memory:")
    try:
        rk.build_legacy_fixture(conn)
        tables = {
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        for expected in (
            "draws", "prediction_runs", "prediction_items", "prediction_results",
            "strategy_replay_runs", "strategy_prediction_replays",
        ):
            assert expected in tables
    finally:
        conn.close()


def test_legacy_fixture_columns_match_source():
    # Ground the fixture: key column signatures must appear verbatim in
    # lottery_api/database.py.
    conn = sqlite3.connect(":memory:")
    try:
        rk.build_legacy_fixture(conn, with_rows=False)
        checks = {
            "prediction_runs": ["latest_known_draw", "strategy_name", "snapshot_source"],
            "prediction_items": ["run_id", "bet_index", "numbers", "status"],
            "strategy_prediction_replays": [
                "target_draw", "strategy_id", "replay_status", "replay_run_id",
            ],
        }
        for table, cols in checks.items():
            info = conn.execute(f"PRAGMA table_info({table})").fetchall()
            names = {c[1] for c in info}
            for col in cols:
                assert col in names, f"{table}.{col}"
                assert col in DATABASE_SRC, f"{col} not grounded in database.py"
    finally:
        conn.close()


def test_grounding_metadata_cites_source():
    g = rk.LEGACY_FIXTURE_SOURCE_GROUNDING
    assert g["source_file"] == "lottery_api/database.py"
    assert g["source_commit"] == P271J_MERGE_COMMIT
    assert set(g["tables"]) >= {
        "draws", "prediction_runs", "prediction_items", "prediction_results",
        "strategy_replay_runs", "strategy_prediction_replays",
    }


def test_no_strategy_prediction_replays_reuse():
    # The merged P271J module must not reference the legacy replay table.
    module_src = Path(pcl.__file__).read_text(encoding="utf-8")
    assert "strategy_prediction_replays" not in module_src
    # The prospective ledger row table is its own table, not the legacy one.
    assert pcl._LEDGER_TABLE == "prospective_prediction_ledger"
    assert pcl._LEDGER_TABLE != "strategy_prediction_replays"


# ---------------------------------------------------------------------------
# Clean additive install + non-interference (A)
# ---------------------------------------------------------------------------


def test_scenario_clean_install(suite_report):
    s = _scenario(suite_report, "A_clean_additive_install")
    assert s["passed"], s
    assert s["detail"]["legacy_schema_unchanged"]
    assert s["detail"]["legacy_data_unchanged"]
    assert s["detail"]["integrity_check"] == "ok"
    assert s["detail"]["foreign_key_violations"] == []


def test_clean_install_explicit(tmp_path):
    db = tmp_path / "clean.db"
    conn = rk.connect_temporary(str(db))
    try:
        rk.build_legacy_fixture(conn)
        before = rk.legacy_snapshot(conn)
        rk.install_prospective_schema(conn)
        after = rk.legacy_snapshot(conn)
        assert before["schema_fingerprint"] == after["schema_fingerprint"]
        assert before["data_fingerprint"] == after["data_fingerprint"]
        # Unrelated table 'draws' untouched.
        assert before["data_fingerprint"]["draws"] == after["data_fingerprint"]["draws"]
        present = rk.prospective_objects_present(conn)
        assert present["tables_present"]
        assert present["triggers_present"]
        assert present["indexes_present"]
        assert rk.foreign_key_check(conn) == []
        assert rk.integrity_check(conn) == "ok"
    finally:
        conn.close()


def test_prospective_schema_has_no_actual_result_columns(tmp_path):
    db = tmp_path / "noresult.db"
    conn = rk.connect_temporary(str(db))
    try:
        rk.build_legacy_fixture(conn)
        rk.install_prospective_schema(conn)
        info = conn.execute(
            f"PRAGMA table_info({pcl._LEDGER_TABLE})"
        ).fetchall()
        cols = {c[1] for c in info}
        forbidden = {
            "actual_numbers", "actual_special", "hit_count", "hit_numbers",
            "matched_numbers", "special_hit",
        }
        assert forbidden.isdisjoint(cols), cols & forbidden
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Idempotence (B) and existing-row preservation (H)
# ---------------------------------------------------------------------------


def test_scenario_idempotence(suite_report):
    s = _scenario(suite_report, "B_same_version_idempotence")
    assert s["passed"], s
    assert s["detail"]["objects_identical"]
    assert s["detail"]["legacy_unchanged"]


def test_scenario_existing_prospective_rows(suite_report):
    s = _scenario(suite_report, "H_existing_prospective_rows_preserved")
    assert s["passed"], s
    assert s["detail"]["row_count_after_reinstall"] == 1
    assert s["detail"]["rows_unchanged"]


# ---------------------------------------------------------------------------
# Incompatible version (C) and injected failure (D) rollback atomicity
# ---------------------------------------------------------------------------


def test_scenario_incompatible_version(suite_report):
    s = _scenario(suite_report, "C_incompatible_version_rejected")
    assert s["passed"], s
    assert s["detail"]["raised"] == "SchemaVersionError"
    assert s["detail"]["new_objects_created"] == []
    assert s["detail"]["legacy_unchanged"]


def test_scenario_injected_failure_full_rollback(suite_report):
    s = _scenario(suite_report, "D_injected_failure_full_rollback")
    assert s["passed"], s
    assert s["detail"]["raised"] == "OperationalError"
    assert s["detail"]["prospective_objects_remaining"] is False
    assert s["detail"]["orphan_version_marker"] is None
    assert s["detail"]["legacy_unchanged"]
    assert s["detail"]["connection_left_in_transaction"] is False


def test_injected_failure_leaves_no_orphan(tmp_path):
    db = tmp_path / "inject.db"
    conn = sqlite3.connect(
        rk.validate_temporary_db_path(str(db)), factory=rk.InjectedFailureConnection
    )
    try:
        rk.build_legacy_fixture(conn)
        conn.arm()
        with pytest.raises(sqlite3.OperationalError):
            rk.install_prospective_schema(conn)
        assert rk.has_any_prospective_object(conn) is False
        assert pcl.get_schema_version(conn) is None
        assert conn.in_transaction is False
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Ambient transaction ownership (E)
# ---------------------------------------------------------------------------


def test_scenario_ambient_transaction(suite_report):
    s = _scenario(suite_report, "E_ambient_transaction_rejected")
    assert s["passed"], s
    assert s["detail"]["raised"] == "AmbientTransactionError"
    assert s["detail"]["caller_tx_open_after_rejection"] is True
    assert s["detail"]["observer_saw_uncommitted_row"] is False
    assert s["detail"]["observer_saw_prospective_object"] is False
    assert s["detail"]["caller_rollback_effective"] is True


def test_ambient_transaction_caller_commit_owned(tmp_path):
    # Caller's explicit COMMIT remains caller-owned after a rejected install.
    db = tmp_path / "ambient_commit.db"
    conn = rk.connect_temporary(str(db))
    try:
        rk.build_legacy_fixture(conn)
        conn.execute("BEGIN")
        conn.execute(
            "INSERT INTO draws (draw, date, lottery_type, numbers, special) "
            "VALUES ('777000001', '2026/06/13', 'DAILY_539', '1,2,3,4,5', 0)"
        )
        with pytest.raises(pcl.AmbientTransactionError):
            rk.install_prospective_schema(conn)
        assert conn.in_transaction is True
        conn.commit()  # caller decides to commit ITS work
        cnt = conn.execute(
            "SELECT COUNT(*) FROM draws WHERE draw='777000001'"
        ).fetchone()[0]
        assert cnt == 1
        # No prospective object was created by the rejected call.
        assert rk.has_any_prospective_object(conn) is False
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Locked / busy fail-closed (F)
# ---------------------------------------------------------------------------


def test_scenario_locked_database(suite_report):
    s = _scenario(suite_report, "F_locked_database_fail_closed")
    assert s["passed"], s
    assert s["detail"]["raised"] == "OperationalError"
    assert s["detail"]["lock_message_is_locked"]
    assert s["detail"]["prospective_objects_after_lock"] is False
    assert s["detail"]["installer_left_in_transaction"] is False


# ---------------------------------------------------------------------------
# Backup / restore (G) — temporary only
# ---------------------------------------------------------------------------


def test_scenario_backup_restore(suite_report):
    s = _scenario(suite_report, "G_temporary_backup_restore")
    assert s["passed"], s
    assert s["detail"]["restored_matches_pre_install"]
    assert s["detail"]["restored_has_prospective_objects"] is False


def test_backup_rejects_memory_and_repo_paths(tmp_path):
    src = tmp_path / "src.db"
    conn = rk.connect_temporary(str(src))
    try:
        rk.build_legacy_fixture(conn)
    finally:
        conn.close()
    with pytest.raises(rk.PathSafetyError):
        rk.backup_database(str(src), ":memory:")
    with pytest.raises(rk.PathSafetyError):
        rk.backup_database(str(src), str(ROOT / "leak_backup.db"))


# ---------------------------------------------------------------------------
# Constraints / append-only / uniqueness (I)
# ---------------------------------------------------------------------------


def test_scenario_constraints_enforced(suite_report):
    s = _scenario(suite_report, "I_constraints_and_append_only_enforced")
    assert s["passed"], s
    assert s["detail"]["foreign_keys_on"]
    assert s["detail"]["append_only_update_blocked"]
    assert s["detail"]["append_only_delete_blocked"]
    assert s["detail"]["semantic_unique_index"]


def test_semantic_unique_constraint_blocks_duplicate_identity(tmp_path):
    db = tmp_path / "unique.db"
    conn = rk.connect_temporary(str(db))
    try:
        rk.build_legacy_fixture(conn)
        rk.install_prospective_schema(conn)
        # Seed registry + batch so ledger FKs are satisfiable.
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            f"INSERT INTO {pcl._REGISTRY_TABLE} (activation_id, "
            "activation_artifact_commit, deployed_implementation_commit, "
            "migration_verification_ref, activation_merged_at_utc, "
            "prospective_start_at_utc, status, created_by, recorded_at_utc) VALUES "
            "('act_u', 'a', 'b', 'r', '2026-06-01T00:00:00+00:00', "
            "'2026-06-01T00:00:00+00:00', 'INACTIVE', 'p271k', "
            "'2026-06-01T00:00:00+00:00')"
        )
        conn.execute(
            f"INSERT INTO {pcl._BATCH_TABLE} (batch_id, activation_id, "
            "preregistration_version, prospective_protocol_version, lottery_type, "
            "target_draw, draw_close_at_utc, draw_close_source_id, "
            "draw_close_source_version, capture_mode, eligibility_status, "
            "created_by, recorded_at_utc) VALUES "
            "('batch_u', 'act_u', 'pv', 'pp', 'DAILY_539', '115000100', "
            "'2026-06-10T13:00:00+00:00', 'src', 'v1', 'LIVE_PRE_CLOSE', 'ELIGIBLE', "
            "'p271k', '2026-06-10T10:00:00+00:00')"
        )

        def _insert_ledger(ledger_id):
            conn.execute(
                f"INSERT INTO {pcl._LEDGER_TABLE} (ledger_id, batch_id, "
                "activation_id, preregistration_version, prospective_protocol_version, "
                "lottery_type, target_draw, strategy_id, strategy_version, bet_index, "
                "predicted_main_numbers, prediction_created_at_utc, draw_close_at_utc, "
                "eligibility_status, source_provenance, payload_hash, created_by, "
                "recorded_at_utc) VALUES "
                f"('{ledger_id}', 'batch_u', 'act_u', 'pv', 'pp', 'DAILY_539', "
                "'115000100', 'acb', 'v1', 1, '[1,2,3,4,5]', "
                "'2026-06-10T10:00:00+00:00', '2026-06-10T13:00:00+00:00', 'ELIGIBLE', "
                "'prov', 'hash', 'p271k', '2026-06-10T10:00:00+00:00')"
            )

        _insert_ledger("L1")  # same identity tuple, different ledger_id -> UNIQUE index
        with pytest.raises(sqlite3.IntegrityError):
            _insert_ledger("L2")
        conn.execute("ROLLBACK")
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Suite-level + integrity / non-action
# ---------------------------------------------------------------------------


def test_suite_all_passed(suite_report):
    assert suite_report["all_passed"], suite_report["scenarios"]


def test_no_repo_db_residue(tmp_path):
    # Running a rehearsal must not create any DB file inside the repository.
    db = tmp_path / "residue_check.db"
    conn = rk.connect_temporary(str(db))
    try:
        rk.build_legacy_fixture(conn)
        rk.install_prospective_schema(conn)
    finally:
        conn.close()
    # By construction the rehearsal refuses any repository-contained path, so no
    # rehearsal DB can land in the tree.
    with pytest.raises(rk.PathSafetyError):
        rk.validate_temporary_db_path(str(ROOT / "residue_check.db"))
    # Shallow spot-check of the directories this task actually writes to.
    suspects = {
        "residue_check.db", "scenario_a_clean.db", "scenario_d_injected.db",
        "scenario_f_locked.db", "scenario_g_backup.db", "scenario_g_source.db",
    }
    for d in (ROOT, ROOT / "scripts", ROOT / "tests", ROOT / "lottery_api",
              ROOT / "lottery_api" / "data", ROOT / "outputs",
              ROOT / "outputs" / "research"):
        if not d.exists():
            continue
        existing = set(os.listdir(d))
        assert suspects.isdisjoint(existing), f"residue in {d}: {suspects & existing}"
        for name in existing:
            assert not (name.startswith("scenario_")
                        and name.endswith((".db", "-wal", "-shm", "-journal"))), \
                f"stray rehearsal sidecar {name} in {d}"


def test_production_db_hash_unchanged_after_rehearsal(tmp_path):
    before = _sha256_file(PROD_DB)
    workdir = tmp_path / "work"
    workdir.mkdir()
    rk.run_rehearsal_suite(str(workdir), include_locked=False)
    after = _sha256_file(PROD_DB)
    assert before == after == EXPECTED_PROD_DB_SHA256


def test_p271j_module_unchanged():
    actual = _sha256_file(ROOT / "lottery_api" / "prospective_capture_ledger.py")
    assert actual == EXPECTED_P271J_MODULE_SHA256


def test_preserved_artifacts_present_and_nonempty():
    for rel in PRESERVED_ARTIFACTS:
        p = ROOT / rel
        assert p.exists(), rel
        assert p.stat().st_size > 0, rel


def test_p271l_m_n_not_started():
    for token in ("p271l", "p271m", "p271n"):
        hits = list((ROOT / "scripts").glob(f"{token}_*.py"))
        hits += list((ROOT / "tests").glob(f"test_{token}_*.py"))
        assert not hits, f"{token} artifacts unexpectedly present: {hits}"
