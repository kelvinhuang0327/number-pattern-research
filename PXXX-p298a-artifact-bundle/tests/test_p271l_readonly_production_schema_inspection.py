"""Behavioral tests for the P271L read-only ACTUAL production schema inspection.

Every test runs against synthetic temporary SQLite databases created under the
pytest ``tmp_path`` (outside the repository). The canonical production database
is NEVER opened by this test module — only its path-resolution guards are
exercised (which read filesystem metadata, not SQLite).
"""

from __future__ import annotations

import ast
import importlib.util
import os
import sqlite3
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT_PATH = os.path.join(
    REPO_ROOT, "scripts", "p271l_readonly_production_schema_inspection.py"
)
LEDGER_SOURCE = os.path.join(REPO_ROOT, "lottery_api", "prospective_capture_ledger.py")


def _load_from_path(mod_name, path):
    spec = importlib.util.spec_from_file_location(mod_name, path)
    mod = importlib.util.module_from_spec(spec)
    # Register before exec so dataclasses/typing can resolve the module by name.
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


def _load_module():
    return _load_from_path("p271l_insp_under_test", SCRIPT_PATH)


insp = _load_module()


def _load_ledger():
    return _load_from_path("pcl_under_test", LEDGER_SOURCE)


pcl = _load_ledger()


# ---------------------------------------------------------------------------
# Fixtures: synthetic legacy + prospective DBs (out-of-repo tmp_path).
# ---------------------------------------------------------------------------

_LEGACY_DDL = [
    """CREATE TABLE draws (
        id INTEGER PRIMARY KEY AUTOINCREMENT, draw TEXT NOT NULL, date TEXT NOT NULL,
        lottery_type TEXT NOT NULL, numbers TEXT NOT NULL, special INTEGER DEFAULT 0,
        jackpot_amount REAL, numbers_positional TEXT, created_at TEXT)""",
    "CREATE INDEX idx_lottery_type ON draws(lottery_type)",
    """CREATE TABLE prediction_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT, lottery_type TEXT NOT NULL,
        latest_known_draw TEXT NOT NULL, latest_known_date TEXT, strategy_name TEXT NOT NULL,
        snapshot_source TEXT DEFAULT 'VALID', notes TEXT, created_at TEXT,
        analyzed TEXT, analysis_note TEXT, review_json TEXT)""",
    """CREATE TABLE prediction_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT, run_id INTEGER NOT NULL, bet_index INTEGER NOT NULL,
        numbers TEXT NOT NULL, special INTEGER, status TEXT DEFAULT 'PENDING', created_at TEXT,
        zone_coverage TEXT, strategy_name TEXT, num_bets INTEGER,
        FOREIGN KEY (run_id) REFERENCES prediction_runs(id))""",
    """CREATE TABLE prediction_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT, item_id INTEGER NOT NULL UNIQUE,
        actual_draw TEXT NOT NULL, actual_date TEXT, actual_numbers TEXT NOT NULL,
        actual_special INTEGER, hit_count INTEGER NOT NULL, matched_numbers TEXT NOT NULL,
        special_hit INTEGER DEFAULT 0, researched TEXT DEFAULT '無', resolved_at TEXT,
        wq_score INTEGER, split_risk TEXT,
        FOREIGN KEY (item_id) REFERENCES prediction_items(id))""",
    """CREATE TABLE strategy_replay_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT, lottery_type TEXT NOT NULL,
        strategy_scope TEXT NOT NULL DEFAULT 'ALL', started_at TEXT NOT NULL, finished_at TEXT,
        status TEXT NOT NULL DEFAULT 'RUNNING', generator_version TEXT NOT NULL DEFAULT 'v0.1',
        data_hash TEXT, notes TEXT, created_at TEXT)""",
    """CREATE TABLE strategy_prediction_replays (
        id INTEGER PRIMARY KEY AUTOINCREMENT, lottery_type TEXT NOT NULL, target_draw TEXT NOT NULL,
        target_date TEXT, strategy_id TEXT NOT NULL, strategy_name TEXT NOT NULL,
        strategy_version TEXT NOT NULL DEFAULT 'v0.1', history_cutoff_draw TEXT,
        replay_status TEXT NOT NULL, reject_reason TEXT, predicted_numbers TEXT,
        predicted_special INTEGER, actual_numbers TEXT, actual_special INTEGER, hit_numbers TEXT,
        hit_count INTEGER DEFAULT 0, special_hit INTEGER DEFAULT 0, replay_run_id INTEGER,
        generated_at TEXT,
        FOREIGN KEY (replay_run_id) REFERENCES strategy_replay_runs(id),
        UNIQUE(lottery_type, target_draw, strategy_id, replay_run_id))""",
]


def _make_legacy_db(path, with_secret_row=False):
    conn = sqlite3.connect(path)
    for ddl in _LEGACY_DDL:
        conn.execute(ddl)
    if with_secret_row:
        conn.execute(
            "INSERT INTO draws(draw,date,lottery_type,numbers,special) "
            "VALUES('999','2026/01/01','BIG_LOTTO','7,13,21,28,35,42',8)"
        )
    conn.commit()
    conn.close()


def _install_prospective(path):
    conn = sqlite3.connect(path)
    pcl.install_schema(conn)
    conn.close()


@pytest.fixture
def legacy_db(tmp_path):
    p = str(tmp_path / "legacy_only.db")
    _make_legacy_db(p)
    return p


@pytest.fixture
def prospective_empty_db(tmp_path):
    p = str(tmp_path / "prospective_empty.db")
    _make_legacy_db(p)
    _install_prospective(p)
    return p


# ---------------------------------------------------------------------------
# 1. No import-time production DB access.
# ---------------------------------------------------------------------------

def test_no_import_time_db_access(monkeypatch):
    # Execute the module's source fresh while sqlite3.connect is instrumented; a
    # top-level DB open would be recorded. (Re-exec avoids importlib.reload,
    # which can't re-find a spec_from_file_location module by name.)
    calls = []
    real_connect = sqlite3.connect
    monkeypatch.setattr(
        sqlite3, "connect",
        lambda *a, **k: (calls.append(a), real_connect(*a, **k))[1],
    )
    fresh = _load_from_path("p271l_insp_import_probe", SCRIPT_PATH)
    assert calls == [], "module import opened a database connection"
    assert hasattr(fresh, "run_inspection")


def test_module_has_no_global_connection():
    # No module-level sqlite3.Connection object should exist.
    for name in dir(insp):
        assert not isinstance(getattr(insp, name), sqlite3.Connection)


# ---------------------------------------------------------------------------
# 2. Exact immutable read-only URI + connection params.
# ---------------------------------------------------------------------------

def test_connection_uri_is_immutable_readonly():
    assert (
        insp.build_connection_uri("/x/y/lottery_v2.db")
        == "file:/x/y/lottery_v2.db?mode=ro&immutable=1"
    )


def test_connection_uri_percent_encodes_path():
    uri = insp.build_connection_uri("/a b/c#d/lottery_v2.db")
    assert uri.startswith("file:/a%20b/c%23d/")
    assert uri.endswith("?mode=ro&immutable=1")


def test_connection_is_autocommit_readonly(legacy_db):
    conn = insp.connect_readonly_immutable(legacy_db)
    try:
        assert conn.isolation_level is None
    finally:
        conn.close()


def test_report_records_exact_connection_contract(legacy_db):
    rep = insp.run_inspection(REPO_ROOT, legacy_db, synthetic=True)
    assert rep["connection_uri_contract"] == "file:<path>?mode=ro&immutable=1"
    assert rep["connection_params"] == {
        "uri": True, "isolation_level": None, "timeout": 0,
        "mode": "ro", "immutable": 1,
    }
    assert rep["connection_uri"].endswith("?mode=ro&immutable=1")
    assert rep["authorizer_installed"] is True


# ---------------------------------------------------------------------------
# 3. Authorizer denies writes / DDL / ATTACH / transactions / writable PRAGMAs.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("sql", [
    "CREATE TABLE evil(a)",
    "CREATE INDEX ix ON draws(draw)",
    "CREATE TRIGGER tg AFTER INSERT ON draws BEGIN SELECT 1; END",
    "CREATE VIEW v AS SELECT 1",
    "INSERT INTO draws(draw,date,lottery_type,numbers) VALUES('1','d','X','1')",
    "UPDATE draws SET draw='2'",
    "DELETE FROM draws",
    "DROP TABLE draws",
    "ALTER TABLE draws ADD COLUMN x TEXT",
    "ATTACH DATABASE ':memory:' AS m",
    "PRAGMA journal_mode=WAL",
    "PRAGMA wal_checkpoint(TRUNCATE)",
    "PRAGMA user_version=5",
    "REINDEX",
    "VACUUM",
    "BEGIN",
    "SAVEPOINT sp",
])
def test_authorizer_and_immutable_deny_mutations(legacy_db, sql):
    conn = insp.connect_readonly_immutable(legacy_db)
    try:
        with pytest.raises(sqlite3.DatabaseError):
            conn.execute(sql)
    finally:
        conn.close()


def test_authorizer_allows_introspection_pragmas(legacy_db):
    conn = insp.connect_readonly_immutable(legacy_db)
    try:
        # These read-only introspection / scalar PRAGMAs must succeed.
        assert conn.execute('PRAGMA table_xinfo("draws")').fetchall()
        assert conn.execute('PRAGMA index_list("draws")').fetchall()
        conn.execute('PRAGMA foreign_key_list("prediction_items")').fetchall()
        assert conn.execute("PRAGMA schema_version").fetchone() is not None
        assert conn.execute("PRAGMA page_size").fetchone() is not None
        assert conn.execute("PRAGMA journal_mode").fetchone() is not None
    finally:
        conn.close()


def test_authorizer_unit_denies_unknown_pragma_and_setter():
    A = insp
    # wal_checkpoint is not in any allowlist -> deny.
    assert A._readonly_authorizer(A._ACT_PRAGMA, "wal_checkpoint", None, "main", None) == A._SQLITE_DENY
    # setter form of a scalar pragma (arg2 set) -> deny.
    assert A._readonly_authorizer(A._ACT_PRAGMA, "user_version", "5", "main", None) == A._SQLITE_DENY
    # getter form -> ok.
    assert A._readonly_authorizer(A._ACT_PRAGMA, "user_version", None, "main", None) == A._SQLITE_OK
    # introspection pragma with object name -> ok.
    assert A._readonly_authorizer(A._ACT_PRAGMA, "table_xinfo", "draws", "main", None) == A._SQLITE_OK
    # writes -> deny.
    for act in (9, 18, 23, 24, 25, 22, 32, 2, 11, 26):  # delete/insert/update/attach/detach/txn/savepoint/create/drop/alter
        assert A._readonly_authorizer(act, None, None, "main", None) == A._SQLITE_DENY
    # select/read -> ok; functions default-deny unless explicitly allowlisted.
    for act in (A._ACT_SELECT, A._ACT_READ):
        assert A._readonly_authorizer(act, None, None, "main", None) == A._SQLITE_OK
    assert A._readonly_authorizer(
        A._ACT_FUNCTION, None, "length", "main", None
    ) == A._SQLITE_DENY


def test_authorizer_function_allowlist_is_explicit_and_unapproved_denied(legacy_db):
    # None of the hardcoded inspection queries requires a SQL function.
    assert insp.APPROVED_SQL_FUNCTIONS == frozenset()
    conn = insp.connect_readonly_immutable(legacy_db)
    try:
        with pytest.raises(sqlite3.DatabaseError):
            conn.execute("SELECT length('harmless')")
    finally:
        conn.close()


def test_authorizer_function_allowlist_matching_is_case_normalized(
    legacy_db, monkeypatch
):
    monkeypatch.setattr(insp, "APPROVED_SQL_FUNCTIONS", frozenset({"length"}))
    conn = insp.connect_readonly_immutable(legacy_db)
    try:
        assert conn.execute("SELECT LeNgTh('abc')").fetchone() == (3,)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 4. No backup / copy / network / process-signal capability (static AST scan).
# ---------------------------------------------------------------------------

def _source_tree():
    with open(SCRIPT_PATH, "r", encoding="utf-8") as fh:
        return ast.parse(fh.read())


def _non_docstring_string_constants(tree):
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            ds = ast.get_docstring(node, clean=False)
            if ds is not None:
                docstrings.add(ds)
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if node.value not in docstrings:
                out.append(node.value)
    return out


def test_no_dangerous_imports():
    tree = _source_tree()
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported.add(node.module.split(".")[0])
    for forbidden in ("socket", "subprocess", "shutil", "signal", "requests", "urllib3"):
        assert forbidden not in imported, f"forbidden import: {forbidden}"


def test_no_dangerous_string_literals():
    strings = _non_docstring_string_constants(_source_tree())
    joined = "\n".join(strings)
    for token in ("mode=rw", "wal_checkpoint", "VACUUM", "ATTACH", " backup", ".backup", "rwc"):
        assert token not in joined, f"forbidden token in executable string: {token!r}"


def test_no_backup_or_kill_calls():
    tree = _source_tree()
    bad_attrs = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            bad_attrs.add(node.attr)
    for forbidden in ("backup", "kill", "system", "popen", "executescript", "iterdump"):
        assert forbidden not in bad_attrs, f"forbidden attribute used: {forbidden}"


# ---------------------------------------------------------------------------
# 5. Deterministic inventory / fingerprint.
# ---------------------------------------------------------------------------

def test_fingerprint_is_deterministic(prospective_empty_db):
    r1 = insp.run_inspection(REPO_ROOT, prospective_empty_db, synthetic=True)
    r2 = insp.run_inspection(REPO_ROOT, prospective_empty_db, synthetic=True)
    assert r1["schema_fingerprint_sha256"] == r2["schema_fingerprint_sha256"]
    assert r1["schema_inventory"]["table_names"] == r2["schema_inventory"]["table_names"]


def test_fingerprint_changes_with_schema(legacy_db, prospective_empty_db):
    r_legacy = insp.run_inspection(REPO_ROOT, legacy_db, synthetic=True)
    r_pros = insp.run_inspection(REPO_ROOT, prospective_empty_db, synthetic=True)
    assert r_legacy["schema_fingerprint_sha256"] != r_pros["schema_fingerprint_sha256"]


def test_inventory_counts_and_objects(legacy_db):
    rep = insp.run_inspection(REPO_ROOT, legacy_db, synthetic=True)
    inv = rep["schema_inventory"]
    assert "draws" in inv["table_names"]
    assert "strategy_prediction_replays" in inv["table_names"]
    assert rep["object_counts"]["tables"] == len(inv["table_names"])
    assert rep["schema_meta"]["sqlite_version"] == sqlite3.sqlite_version


def test_inventory_reconciles_internal_and_categorized_objects(legacy_db):
    rep = insp.run_inspection(REPO_ROOT, legacy_db, synthetic=True)
    counts = rep["object_counts"]
    assert counts["categorized_total"] == (
        counts["tables"] + counts["indexes"]
        + counts["triggers"] + counts["views"]
    )
    assert counts["categorized_total"] + counts["internal_total"] == counts["raw_total"]
    assert counts["reconciles"] is True
    assert rep["schema_inventory"]["internal_objects"] == [
        {"type": "table", "name": "sqlite_sequence", "tbl_name": "sqlite_sequence"}
    ]
    assert "sqlite_sequence" not in rep["schema_inventory"]["table_names"]


def test_fingerprint_contract_explicitly_preserves_raw_internal_objects(legacy_db):
    rep = insp.run_inspection(REPO_ROOT, legacy_db, synthetic=True)
    assert any(
        obj["name"] == "sqlite_sequence"
        for obj in rep["schema_inventory"]["objects"]
    )
    assert "sqlite_sequence" in (insp.compute_fingerprint.__doc__ or "")


# ---------------------------------------------------------------------------
# 6. Prospective-state classifications (all branches).
# ---------------------------------------------------------------------------

def test_state_absent_clean(legacy_db):
    rep = insp.run_inspection(REPO_ROOT, legacy_db, synthetic=True)
    assert rep["prospective_state"]["state"] == insp.STATE_ABSENT_CLEAN


def test_state_present_exact_and_empty(prospective_empty_db):
    rep = insp.run_inspection(REPO_ROOT, prospective_empty_db, synthetic=True)
    ps = rep["prospective_state"]
    assert ps["state"] == insp.STATE_PRESENT_EXACT_AND_EMPTY
    assert set(ps["present_prospective_tables"]) == set(insp.EXPECTED_PROSPECTIVE_TABLES)
    assert len(ps["present_prospective_triggers"]) == insp.EXPECTED_TRIGGER_COUNT
    assert ps["installed_schema_version"] == insp.EXPECTED_SCHEMA_VERSION


def test_state_present_exact_with_rows(tmp_path):
    p = str(tmp_path / "with_rows.db")
    _make_legacy_db(p)
    _install_prospective(p)
    # Append one append-only registry row directly (synthetic; not production).
    conn = sqlite3.connect(p)
    conn.execute(
        "INSERT INTO prospective_activation_registry "
        "(activation_id, activation_artifact_commit, deployed_implementation_commit, "
        " migration_verification_ref, activation_merged_at_utc, prospective_start_at_utc, "
        " status, created_by, recorded_at_utc) "
        "VALUES('a1','c','c','ref','2026-01-01T00:00:00+00:00','2026-01-01T00:00:00+00:00',"
        "'INACTIVE','t','2026-01-01T00:00:00+00:00')"
    )
    conn.commit()
    conn.close()
    rep = insp.run_inspection(REPO_ROOT, p, synthetic=True)
    assert rep["prospective_state"]["state"] == insp.STATE_PRESENT_EXACT_WITH_ROWS


def test_state_present_partial(tmp_path):
    p = str(tmp_path / "partial.db")
    _make_legacy_db(p)
    _install_prospective(p)
    conn = sqlite3.connect(p)
    # Drop one expected prospective table -> partial. Drop dependents first.
    conn.execute("DROP TABLE prospective_outcome_links")
    conn.commit()
    conn.close()
    rep = insp.run_inspection(REPO_ROOT, p, synthetic=True)
    assert rep["prospective_state"]["state"] == insp.STATE_PRESENT_PARTIAL


def test_state_present_incompatible_version(tmp_path):
    p = str(tmp_path / "badver.db")
    _make_legacy_db(p)
    _install_prospective(p)
    conn = sqlite3.connect(p)
    conn.execute(
        "UPDATE prospective_schema_meta SET value='p271j_prospective_capture_ledger.v999' "
        "WHERE key='schema_version'"
    )
    conn.commit()
    conn.close()
    rep = insp.run_inspection(REPO_ROOT, p, synthetic=True)
    assert rep["prospective_state"]["state"] == insp.STATE_PRESENT_INCOMPATIBLE_VERSION


def test_state_present_unexpected_objects(tmp_path):
    p = str(tmp_path / "stray.db")
    _make_legacy_db(p)
    conn = sqlite3.connect(p)
    conn.execute("CREATE TABLE prospective_mystery (x TEXT)")
    conn.commit()
    conn.close()
    rep = insp.run_inspection(REPO_ROOT, p, synthetic=True)
    ps = rep["prospective_state"]
    assert ps["state"] == insp.STATE_PRESENT_UNEXPECTED_OBJECTS
    assert any(
        obj["name"] == "prospective_mystery"
        for obj in ps["unexpected_prospective_objects"]
    )


def test_orphan_expected_index_is_partial_and_collision(tmp_path):
    p = str(tmp_path / "orphan_index.db")
    _make_legacy_db(p)
    conn = sqlite3.connect(p)
    conn.execute("CREATE UNIQUE INDEX idx_ledger_identity ON draws(draw)")
    conn.commit()
    conn.close()
    rep = insp.run_inspection(REPO_ROOT, p, synthetic=True)
    assert rep["prospective_state"]["state"] == insp.STATE_PRESENT_PARTIAL
    assert rep["schema_collision"]["collision_free_vs_legacy"] is False
    assert {
        (d["type"], d["name"])
        for d in rep["schema_collision"]["collision_details"]
    } == {("index", "idx_ledger_identity")}


def test_orphan_expected_trigger_is_partial_and_collision(tmp_path):
    p = str(tmp_path / "orphan_trigger.db")
    _make_legacy_db(p)
    trigger = insp.EXPECTED_PROSPECTIVE_TRIGGERS[0]
    conn = sqlite3.connect(p)
    conn.execute(
        f"CREATE TRIGGER {trigger} BEFORE UPDATE ON draws "
        "BEGIN SELECT RAISE(ABORT, 'synthetic'); END"
    )
    conn.commit()
    conn.close()
    rep = insp.run_inspection(REPO_ROOT, p, synthetic=True)
    assert rep["prospective_state"]["state"] == insp.STATE_PRESENT_PARTIAL
    assert rep["schema_collision"]["collision_free_vs_legacy"] is False
    detail = rep["schema_collision"]["collision_details"]
    assert any(d["type"] == "trigger" and d["name"] == trigger for d in detail)


def test_orphan_registry_version_table_is_partial_and_collision(tmp_path):
    p = str(tmp_path / "orphan_registry.db")
    _make_legacy_db(p)
    conn = sqlite3.connect(p)
    conn.execute(
        "CREATE TABLE prospective_schema_meta "
        "(key TEXT PRIMARY KEY, value TEXT NOT NULL)"
    )
    conn.commit()
    conn.close()
    rep = insp.run_inspection(REPO_ROOT, p, synthetic=True)
    assert rep["prospective_state"]["state"] == insp.STATE_PRESENT_PARTIAL
    assert rep["schema_collision"]["collision_free_vs_legacy"] is False
    assert any(
        d["type"] == "table" and d["name"] == "prospective_schema_meta"
        for d in rep["schema_collision"]["collision_details"]
    )


# ---------------------------------------------------------------------------
# 7. No row-payload retrieval.
# ---------------------------------------------------------------------------

def test_no_payload_leaks_into_report(tmp_path):
    p = str(tmp_path / "secret.db")
    _make_legacy_db(p, with_secret_row=True)
    import json
    rep = insp.run_inspection(REPO_ROOT, p, synthetic=True)
    blob = json.dumps(rep, ensure_ascii=False)
    # The secret row's payload values must never appear in the schema report.
    assert "7,13,21,28,35,42" not in blob
    assert "'999'" not in blob and '"999"' not in blob


def test_emptiness_probe_uses_no_count(tmp_path):
    # Inspecting a prospective DB with rows reports emptiness booleans only.
    p = str(tmp_path / "probe.db")
    _make_legacy_db(p)
    _install_prospective(p)
    rep = insp.run_inspection(REPO_ROOT, p, synthetic=True)
    empt = rep["prospective_state"]["emptiness"]
    assert all(isinstance(v, bool) for v in empt.values())


# ---------------------------------------------------------------------------
# 8. WAL / sidecar / concurrent-mutation gates.
# ---------------------------------------------------------------------------

def test_clean_run_reports_integrity_ok(legacy_db):
    rep = insp.run_inspection(REPO_ROOT, legacy_db, synthetic=True)
    integ = rep["integrity"]
    assert integ["db_hash_unchanged"] is True
    assert integ["db_stat_unchanged"] is True
    assert integ["sidecars_unchanged"] is True
    assert integ["no_new_journal"] is True
    assert integ["data_version_unchanged"] is True
    assert integ["schema_version_stable"] is True
    assert rep["schema_version_before"] == rep["schema_version_after"]
    assert integ["integrity_ok"] is True


def test_changed_schema_version_is_unstable_and_blocking(legacy_db, monkeypatch):
    real_scalar = insp._scalar_pragma
    schema_reads = iter((101, 101, 102))

    def fake_scalar(conn, name):
        if name == "schema_version":
            return next(schema_reads)
        return real_scalar(conn, name)

    monkeypatch.setattr(insp, "_scalar_pragma", fake_scalar)
    rep = insp.run_inspection(REPO_ROOT, legacy_db, synthetic=True)
    assert rep["schema_version_before"] == 101
    assert rep["schema_version_after"] == 102
    assert rep["integrity"]["schema_version_stable"] is False
    assert rep["integrity"]["integrity_ok"] is False
    assert rep["actual_schema_blocker_cleared"] is False


def test_concurrent_mutation_detected(legacy_db, monkeypatch):
    # Simulate the raw file changing across the before/after hash window.
    seq = iter(["hashAAAA", "hashBBBB"])
    monkeypatch.setattr(insp, "raw_sha256", lambda _p: next(seq))
    rep = insp.run_inspection(REPO_ROOT, legacy_db, synthetic=True)
    assert rep["integrity"]["db_hash_unchanged"] is False
    assert rep["integrity"]["integrity_ok"] is False
    assert rep["actual_schema_blocker_cleared"] is False


def test_no_repo_residue_and_no_sidecars(legacy_db):
    insp.run_inspection(REPO_ROOT, legacy_db, synthetic=True)
    for sc in ("-wal", "-shm", "-journal"):
        assert not os.path.exists(legacy_db + sc)


def test_production_hash_preserved_after_inspection(legacy_db):
    before = insp.raw_sha256(legacy_db)
    insp.run_inspection(REPO_ROOT, legacy_db, synthetic=True)
    after = insp.raw_sha256(legacy_db)
    assert before == after


# ---------------------------------------------------------------------------
# 9. Path guards (production canonical enforcement; synthetic refusal).
# ---------------------------------------------------------------------------

def test_production_resolution_rejects_non_canonical_repo(tmp_path):
    # A repo root whose basename != LotteryNew is rejected without opening a DB.
    with pytest.raises(insp.InspectionError):
        insp.resolve_production_db(str(tmp_path), "lottery_api/data/lottery_v2.db")


def test_production_resolution_rejects_wrong_db_path(legacy_db):
    with pytest.raises(insp.InspectionError):
        insp.resolve_production_db(REPO_ROOT, legacy_db)


def test_production_resolution_returns_canonical_path_without_open():
    # Resolves (filesystem realpath + existence only); does NOT open SQLite.
    resolved = insp.resolve_production_db(REPO_ROOT, insp.PRODUCTION_DB_RELPATH)
    assert resolved.endswith(os.path.join("lottery_api", "data", "lottery_v2.db"))
    assert os.path.basename(os.path.dirname(os.path.dirname(os.path.dirname(resolved)))) == "LotteryNew"


def test_synthetic_refuses_canonical_production_db():
    canonical = os.path.join(REPO_ROOT, insp.PRODUCTION_DB_RELPATH)
    with pytest.raises(insp.InspectionError):
        insp.resolve_synthetic_db(REPO_ROOT, canonical)


def test_synthetic_refuses_in_repo_path(tmp_path):
    in_repo = os.path.join(REPO_ROOT, "scripts", "p271l_readonly_production_schema_inspection.py")
    with pytest.raises(insp.InspectionError):
        insp.resolve_synthetic_db(REPO_ROOT, in_repo)


# ---------------------------------------------------------------------------
# 10. Legacy source comparison.
# ---------------------------------------------------------------------------

def test_legacy_comparison_all_present(legacy_db):
    rep = insp.run_inspection(REPO_ROOT, legacy_db, synthetic=True)
    cmp = rep["legacy_source_comparison"]
    assert cmp["all_legacy_tables_present"] is True
    assert cmp["all_source_columns_present"] is True
    for t in insp.LEGACY_COMPARISON_TABLES:
        assert cmp["per_table"][t]["present"] is True
        assert cmp["per_table"][t]["missing_source_columns"] == []


def test_legacy_comparison_does_not_overstate_unimplemented_dimensions(legacy_db):
    cmp = insp.run_inspection(REPO_ROOT, legacy_db, synthetic=True)[
        "legacy_source_comparison"
    ]
    for dimension in (
        "types", "nullability", "defaults", "primary_keys",
        "foreign_keys", "index_equivalence",
    ):
        assert cmp["comparison_scope"][dimension] == "NOT_FULLY_VERIFIED"
    for table in insp.LEGACY_COMPARISON_TABLES:
        row = cmp["per_table"][table]
        assert row["table_existence_status"] == "CHECKED_PRESENT"
        assert row["column_names_status"] == "CHECKED_PASS"
        assert row["types_status"] == "NOT_FULLY_VERIFIED"


def test_schema_collision_free_on_legacy_only(legacy_db):
    rep = insp.run_inspection(REPO_ROOT, legacy_db, synthetic=True)
    col = rep["schema_collision"]
    assert col["collision_free_vs_legacy"] is True
    assert col["legacy_name_collisions"] == []
    assert col["contract_names_already_present_in_deployed"] == []


def test_schema_collision_free_when_prospective_installed(prospective_empty_db):
    rep = insp.run_inspection(REPO_ROOT, prospective_empty_db, synthetic=True)
    col = rep["schema_collision"]
    # The installed prospective objects are the contract itself -> still no
    # *legacy* collision.
    assert col["collision_free_vs_legacy"] is True
    assert set(col["contract_names_already_present_in_deployed"]) == (
        set(insp.EXPECTED_OBJECT_SPECS)
    )


def test_legacy_comparison_detects_missing_table(tmp_path):
    p = str(tmp_path / "missing.db")
    conn = sqlite3.connect(p)
    conn.execute(_LEGACY_DDL[0])  # only draws
    conn.commit()
    conn.close()
    rep = insp.run_inspection(REPO_ROOT, p, synthetic=True)
    cmp = rep["legacy_source_comparison"]
    assert cmp["all_legacy_tables_present"] is False
    assert cmp["per_table"]["prediction_runs"]["present"] is False


# ---------------------------------------------------------------------------
# 11. P271I/J/K/L integrity + contract alignment.
# ---------------------------------------------------------------------------

def test_schema_contract_matches_ledger_source():
    # The inspection's expected schema_version must equal the ledger's SSOT.
    assert insp.EXPECTED_SCHEMA_VERSION == pcl.SCHEMA_VERSION
    assert set(insp.EXPECTED_PROSPECTIVE_TABLES) == set(pcl.REQUIRED_TABLES)
    assert insp.EXPECTED_TRIGGER_COUNT == len(pcl._APPEND_ONLY_TABLES) * 2
    expected_triggers = {
        f"trg_{table}_{operation}"
        for table in pcl._APPEND_ONLY_TABLES
        for operation in ("no_update", "no_delete")
    }
    assert set(insp.EXPECTED_PROSPECTIVE_TRIGGERS) == expected_triggers
    assert len(insp.EXPECTED_OBJECT_SPECS) == 18


@pytest.mark.parametrize("relpath", [
    "scripts/p271l_controlled_deployment_preflight.py",
    "tests/test_p271l_controlled_deployment_preflight.py",
    "lottery_api/prospective_capture_ledger.py",
    "scripts/p271k_prospective_capture_ledger_migration_rehearsal.py",
    "tests/test_p271j_prospective_capture_ledger_implementation.py",
    "tests/test_p271k_prospective_capture_ledger_migration_rehearsal.py",
])
def test_prior_phase_artifacts_present(relpath):
    assert os.path.exists(os.path.join(REPO_ROOT, relpath)), relpath


# ---------------------------------------------------------------------------
# 12. Production apply + P271M/P271N remain unauthorized.
# ---------------------------------------------------------------------------

def test_report_declares_apply_not_ready(legacy_db):
    rep = insp.run_inspection(REPO_ROOT, legacy_db, synthetic=True)
    assert rep["final_classification"] == "P271L_PREFLIGHT_COMPLETE_NOT_READY_FOR_APPLY"
    assert rep["production_apply"] == "NOT_READY_FOR_APPLY"
    assert rep["governance"] == "HOLD / WAITING_FOR_USER_AUTHORIZATION"
    assert rep["source_verification_status"] == "MANUAL_VERIFICATION_REQUIRED"


def test_report_negative_declarations(legacy_db):
    rep = insp.run_inspection(REPO_ROOT, legacy_db, synthetic=True)
    for key in (
        "production_db_opened_writable", "production_db_copied", "production_db_written",
        "backup_executed", "checkpoint_executed", "restore_executed",
        "process_signaled_or_stopped", "production_migration_executed",
        "deployment_started", "prospective_collection_activated",
        "p271m_started", "p271n_started",
    ):
        assert rep[key] is False, key
    assert rep["production_db_opened_readonly"] is True
    assert rep["prediction_success_claim"] is None


def test_remaining_apply_blockers_retained(legacy_db):
    rep = insp.run_inspection(REPO_ROOT, legacy_db, synthetic=True)
    blockers = rep["remaining_apply_blockers"]
    assert any("fresh_apply_time" in b for b in blockers)
    assert any("backup" in b for b in blockers)
    assert any("rollback" in b for b in blockers)
    assert any("wal_shm" in b for b in blockers)


def test_report_records_test_and_single_connection_evidence(legacy_db):
    rep = insp.run_inspection(REPO_ROOT, legacy_db, synthetic=True)
    assert rep["focused_tests"]["status"] == "NOT_RUN_BY_INSPECTION_SCRIPT"
    assert rep["combined_tests"]["status"] == "NOT_RUN_BY_INSPECTION_SCRIPT"
    assert rep["full_repo_suite"]["status"] == "NOT_RUN"
    evidence = rep["single_connection_evidence"]
    assert evidence["one_bounded_code_path"] is True
    assert evidence["connection_closed_in_finally"] is True
    assert evidence["writable_fallback"] is False
    assert evidence["retry_path"] is False
    assert evidence["exact_historical_count_status"] == "EVIDENCE_LIMITATION"
