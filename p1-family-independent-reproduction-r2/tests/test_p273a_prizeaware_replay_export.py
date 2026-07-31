"""
P273A — Prize-Aware Observed-Counts Export tests.

All DB operations use synthetic temporary SQLite databases (pytest tmp_path).
The production database is NEVER opened, referenced, or written by any test.
No registry mutation and no process/service control occurs.
"""

from __future__ import annotations

import ast
import importlib.util
import json
import re
import sqlite3
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = ROOT / "analysis" / "p273a_prizeaware_replay_export.py"
# Real committed sources used only for SHA-256 provenance (never opened as DB).
P271C_SRC = ROOT / "lottery_api" / "prize_aware_scorer.py"
P271E_SRC = ROOT / "lottery_api" / "prize_aware_replay_adapter.py"

PRODUCTION_DB = "lottery_api/data/lottery_v2.db"

FORBIDDEN_SQL_TOKENS = (
    "INSERT", "UPDATE", "DELETE", "REPLACE", "CREATE", "ALTER", "DROP",
    "TRUNCATE", "VACUUM", "REINDEX", "ATTACH", "DETACH",
)


def _load_module():
    spec = importlib.util.spec_from_file_location("p273a_mod", SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


m = _load_module()


# ---------------------------------------------------------------------------
# Synthetic row + DB builders (no production data)
# ---------------------------------------------------------------------------

def _d539(hit):
    """Return (predicted, actual) 5-number DAILY_539 lists with `hit` overlap."""
    actual = [1, 2, 3, 4, 5]
    filler = [35, 36, 37, 38, 39]
    predicted = actual[:hit] + filler[: 5 - hit]
    return predicted, actual


def raw_539(target_draw, bet_index, hit, strategy_id="d539_s00",
            join_count=1, cutoff=None):
    pred, act = _d539(hit)
    cutoff = cutoff if cutoff is not None else str(int(target_draw) - 1)
    return ("DAILY_539", target_draw, strategy_id, bet_index, cutoff,
            json.dumps(pred), None, json.dumps(act), None, join_count)


def raw_big(target_draw, bet_index, hit, special, strategy_id="big_s00",
            join_count=1, cutoff=None):
    """BIG_LOTTO row. special=1 -> actual_special (7) included in predicted."""
    actual = [1, 2, 3, 4, 5, 6]
    actual_special = 7
    base = actual[:hit]
    if special:
        base = base + [actual_special]
    filler = [n for n in (10, 11, 12, 13, 14, 15) if n not in base]
    predicted = (base + filler)[:6]
    cutoff = cutoff if cutoff is not None else str(int(target_draw) - 1)
    return ("BIG_LOTTO", target_draw, strategy_id, bet_index, cutoff,
            json.dumps(predicted), None, json.dumps(actual), actual_special,
            join_count)


def raw_power(target_draw, bet_index, hit, second_hit, predicted_special,
              strategy_id="pow_s00", join_count=1, cutoff=None):
    """POWER_LOTTO row. predicted_special=None -> missing second zone."""
    actual = [1, 2, 3, 4, 5, 6]
    actual_special = 4
    base = actual[:hit]
    filler = [n for n in (20, 21, 22, 23, 24, 25) if n not in base]
    predicted = (base + filler)[:6]
    if predicted_special is None:
        psp = None
    elif second_hit:
        psp = actual_special
    else:
        psp = (actual_special % 8) + 1  # any value != actual_special
    cutoff = cutoff if cutoff is not None else str(int(target_draw) - 1)
    return ("POWER_LOTTO", target_draw, strategy_id, bet_index, cutoff,
            json.dumps(predicted), psp, json.dumps(actual), actual_special,
            join_count)


def build_db(path, replay_rows, draw_keys=None):
    """Create a synthetic DB with the required schema and insert rows.

    replay_rows: list of CELL_QUERY-shaped tuples (join_count is ignored at the
                 DB layer; the draws table determines the real join count).
    draw_keys:   optional explicit list of (lottery_type, draw); if None it is
                 derived to give every replay row exactly one matching draw.
    """
    conn = sqlite3.connect(str(path))
    conn.execute(
        "CREATE TABLE strategy_prediction_replays ("
        "lottery_type TEXT, target_draw TEXT, strategy_id TEXT, "
        "bet_index INTEGER, history_cutoff_draw TEXT, predicted_numbers TEXT, "
        "predicted_special INTEGER, actual_numbers TEXT, actual_special INTEGER, "
        "replay_status TEXT, dry_run INTEGER)"
    )
    conn.execute("CREATE TABLE draws (lottery_type TEXT, draw TEXT)")
    for r in replay_rows:
        conn.execute(
            "INSERT INTO strategy_prediction_replays "
            "(lottery_type,target_draw,strategy_id,bet_index,history_cutoff_draw,"
            "predicted_numbers,predicted_special,actual_numbers,actual_special,"
            "replay_status,dry_run) VALUES (?,?,?,?,?,?,?,?,?,'PREDICTED',0)",
            r[:9],
        )
    if draw_keys is None:
        draw_keys = sorted({(r[0], r[1]) for r in replay_rows})
    for lt, draw in draw_keys:
        conn.execute("INSERT INTO draws (lottery_type, draw) VALUES (?,?)",
                     (lt, draw))
    conn.commit()
    conn.close()


# ===========================================================================
# 13. Exact 36-cell strategy freeze
# ===========================================================================

def _synthetic_p267c(n_539=15, n_big=11, n_power=10):
    results = []
    for i in range(n_539):
        results.append({"lottery_type": "DAILY_539", "strategy_id": f"d539_s{i:02d}"})
    for i in range(n_big):
        results.append({"lottery_type": "BIG_LOTTO", "strategy_id": f"big_s{i:02d}"})
    for i in range(n_power):
        results.append({"lottery_type": "POWER_LOTTO", "strategy_id": f"pow_s{i:02d}"})
    return {"results": results}


def _synthetic_p271a():
    return {
        "endpoint_definitions": {
            lt: {
                m.GOVERNED_ENDPOINT[lt]["endpoint_id"]: {
                    "condition_sql": m.GOVERNED_ENDPOINT[lt]["expected_condition_sql"],
                }
            }
            for lt in m.LOTTERY_TYPES
        }
    }


def _write_json(path, obj):
    path.write_text(json.dumps(obj), encoding="utf-8")
    return str(path)


def test_frozen_cells_exactly_36(tmp_path):
    p = _write_json(tmp_path / "p267c.json", _synthetic_p267c())
    cells = m.load_frozen_cells(p)
    assert len(cells) == 36
    assert sum(c["lottery_type"] == "DAILY_539" for c in cells) == 15
    assert sum(c["lottery_type"] == "BIG_LOTTO" for c in cells) == 11
    assert sum(c["lottery_type"] == "POWER_LOTTO" for c in cells) == 10


def test_frozen_cells_wrong_count_raises(tmp_path):
    p = _write_json(tmp_path / "p267c.json", _synthetic_p267c(n_539=14))
    with pytest.raises(m.FrozenCellError):
        m.load_frozen_cells(p)


def test_frozen_cells_duplicate_raises(tmp_path):
    obj = _synthetic_p267c()
    obj["results"].append({"lottery_type": "DAILY_539", "strategy_id": "d539_s00"})
    p = _write_json(tmp_path / "p267c.json", obj)
    with pytest.raises(m.FrozenCellError):
        m.load_frozen_cells(p)


def test_real_p267c_has_36_cells():
    """The committed P267C artifact must expose exactly 36 frozen cells."""
    real = ROOT / "outputs" / "research" / "p267c_m3plus_strategy_revalidation_20260610.json"
    cells = m.load_frozen_cells(str(real))
    assert len(cells) == 36


# ===========================================================================
# Endpoint verification against P271A (verify, not assume)
# ===========================================================================

def test_endpoint_verification_matches_real_p271a():
    real = ROOT / "outputs" / "research" / "p271a_prize_aware_endpoint_scoring_spec_20260611.json"
    actual = m.verify_endpoints_against_p271a(str(real))
    assert set(actual) == set(m.LOTTERY_TYPES)


def test_endpoint_drift_raises(tmp_path):
    bad = _synthetic_p271a()
    bad["endpoint_definitions"]["DAILY_539"]["D539_ANY_PRIZE_AWARE_WIN"][
        "condition_sql"] = "hit_count >= 1"
    p = _write_json(tmp_path / "p271a.json", bad)
    with pytest.raises(m.EndpointDriftError):
        m.verify_endpoints_against_p271a(p)


# ===========================================================================
# 1-3. mode=ro / query_only / single connection + transaction
# ===========================================================================

def test_mode_ro_uri_and_query_only(tmp_path):
    db = tmp_path / "syn.db"
    build_db(db, [raw_539("1000", 1, 2)])
    conn, evidence = m.open_readonly_connection(str(db))
    try:
        assert evidence["mode_ro"] is True
        assert "?mode=ro" in evidence["connection_uri"]
        assert evidence["query_only_enabled"] is True
        assert evidence["query_only_pragma_value"] == 1
        # Read-only: a write must be rejected.
        with pytest.raises(sqlite3.OperationalError):
            conn.execute("INSERT INTO draws (lottery_type, draw) VALUES ('X','1')")
    finally:
        conn.close()


def test_single_connection_and_single_transaction_in_source():
    src = SCRIPT_PATH.read_text(encoding="utf-8")
    assert src.count("sqlite3.connect(") == 1
    assert src.count('conn.execute("BEGIN")') == 1
    assert src.count('conn.execute("ROLLBACK")') == 1


def test_open_readonly_query_only_pragma_enforced(tmp_path):
    db = tmp_path / "syn.db"
    build_db(db, [raw_539("1000", 1, 2)])
    conn, _ = m.open_readonly_connection(str(db))
    try:
        val = conn.execute("PRAGMA query_only").fetchone()[0]
        assert val == 1
    finally:
        conn.close()


# ===========================================================================
# Schema verification
# ===========================================================================

def test_verify_schema_ok(tmp_path):
    db = tmp_path / "syn.db"
    build_db(db, [raw_539("1000", 1, 2)])
    conn, _ = m.open_readonly_connection(str(db))
    try:
        info = m.verify_schema(conn)
        assert "strategy_prediction_replays" in info["column_inventory"]
        assert "draws" in info["column_inventory"]
        assert len(info["schema_fingerprint_sha256"]) == 64
    finally:
        conn.close()


def test_verify_schema_missing_column_raises(tmp_path):
    db = tmp_path / "bad.db"
    conn = sqlite3.connect(str(db))
    # strategy_prediction_replays missing predicted_special column.
    conn.execute(
        "CREATE TABLE strategy_prediction_replays ("
        "lottery_type TEXT, target_draw TEXT, strategy_id TEXT, "
        "bet_index INTEGER, history_cutoff_draw TEXT, predicted_numbers TEXT, "
        "actual_numbers TEXT, actual_special INTEGER, "
        "replay_status TEXT, dry_run INTEGER)"
    )
    conn.execute("CREATE TABLE draws (lottery_type TEXT, draw TEXT)")
    conn.commit()
    conn.close()
    ro, _ = m.open_readonly_connection(str(db))
    try:
        with pytest.raises(m.SchemaDriftError):
            m.verify_schema(ro)
    finally:
        ro.close()


def test_verify_schema_missing_table_raises(tmp_path):
    db = tmp_path / "bad2.db"
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE draws (lottery_type TEXT, draw TEXT)")
    conn.commit()
    conn.close()
    ro, _ = m.open_readonly_connection(str(db))
    try:
        with pytest.raises(m.SchemaDriftError):
            m.verify_schema(ro)
    finally:
        ro.close()


# ===========================================================================
# 4-5. Windowing (most-recent N distinct) + CAST(target_draw) ordering
# ===========================================================================

def test_window_caps_and_span():
    # 1600 single-bet eligible draws; even target_draw == win.
    processed = [
        {"target_draw": str(d), "bet_index": 1, "eligible": True,
         "reason": None, "win": (d % 2 == 0)}
        for d in range(1600, 0, -1)
    ]
    distinct = [str(d) for d in range(1600, 0, -1)]
    rec100 = m.aggregate_window(processed, distinct, 100, "DAILY_539", "d539_s00")
    assert rec100["support_draws"] == 100
    assert rec100["latest_target_draw"] == "1600"
    assert rec100["earliest_target_draw"] == "1501"
    # even draws among 1501..1600 -> 50 successes
    assert rec100["observed_successes"] == 50
    rec500 = m.aggregate_window(processed, distinct, 500, "DAILY_539", "d539_s00")
    assert rec500["support_draws"] == 500
    rec1500 = m.aggregate_window(processed, distinct, 1500, "DAILY_539", "d539_s00")
    assert rec1500["support_draws"] == 1500
    # support below N when fewer draws exist
    assert rec1500["earliest_target_draw"] == "101"


def test_cast_integer_ordering_not_lexical(tmp_path):
    # Draws "9","10","200","1000": CAST DESC = 1000,200,10,9 (lexical would differ).
    rows = [raw_539(d, 1, 2) for d in ("9", "10", "200", "1000")]
    db = tmp_path / "ord.db"
    build_db(db, rows)
    conn, _ = m.open_readonly_connection(str(db))
    try:
        conn.execute("BEGIN")
        cell = m.compute_cell(conn, "DAILY_539", "d539_s00")
        conn.execute("ROLLBACK")
    finally:
        conn.close()
    w2 = next(w for w in cell["windows"] if w["window"] == 100)
    # most-recent 2 distinct by CAST = 1000 and 200
    assert w2["latest_target_draw"] == "1000"
    # earliest of all 4 by CAST int = 9 (not lexical "10")
    assert w2["earliest_target_draw"] == "9"


# ===========================================================================
# 6. Duplicate replay-row deduplication
# ===========================================================================

def test_duplicate_row_dedup():
    dup = raw_539("1000", 1, 2)
    processed, distinct = m._process_rows([dup, dup, dup])
    assert len(processed) == 1
    assert distinct == ["1000"]


# ===========================================================================
# 7-8. Draw-level any-bet aggregation + bet-count preservation/distribution
# ===========================================================================

def test_draw_level_any_bet_and_bet_count():
    # One draw, two bets: bet1 win (hit2), bet2 no-win (hit1).
    rows = [raw_539("1000", 1, 2), raw_539("1000", 2, 1)]
    processed, distinct = m._process_rows(rows)
    rec = m.aggregate_window(processed, distinct, 100, "DAILY_539", "d539_s00")
    assert rec["support_draws"] == 1
    assert rec["observed_successes"] == 1          # any-bet success
    assert rec["scoreable_rows"] == 2
    assert rec["bet_count_min"] == 2
    assert rec["bet_count_max"] == 2
    assert rec["bet_count_constant"] is True
    assert rec["bet_count_distribution"] == {"2": 1}


def test_variable_bet_count_distribution():
    rows = [
        raw_539("1000", 1, 1), raw_539("1000", 2, 1),   # draw 1000 -> 2 bets
        raw_539("999", 1, 1),                            # draw 999  -> 1 bet
    ]
    processed, distinct = m._process_rows(rows)
    rec = m.aggregate_window(processed, distinct, 100, "DAILY_539", "d539_s00")
    assert rec["support_draws"] == 2
    assert rec["bet_count_min"] == 1
    assert rec["bet_count_max"] == 2
    assert rec["bet_count_constant"] is False
    assert rec["bet_count_distribution"] == {"1": 1, "2": 1}


# ===========================================================================
# 9. Governed endpoint behaviour through P271C scorer
# ===========================================================================

def test_governed_endpoint_539():
    # hit>=2 -> win; hit=1 -> no win.
    p_win, _ = m._process_rows([raw_539("1000", 1, 2)])
    p_no, _ = m._process_rows([raw_539("1000", 1, 1)])
    assert p_win[0]["win"] is True
    assert p_no[0]["win"] is False


def test_governed_endpoint_big_m2_plus_special():
    # hit=2,special=1 -> win; hit=2,special=0 -> no; hit=3,special=0 -> win.
    assert m._process_rows([raw_big("1000", 1, 2, 1)])[0][0]["win"] is True
    assert m._process_rows([raw_big("1000", 1, 2, 0)])[0][0]["win"] is False
    assert m._process_rows([raw_big("1000", 1, 3, 0)])[0][0]["win"] is True


def test_governed_endpoint_power_m1_plus_second():
    # hit=1,second=1 -> win; hit=2,second=0 -> no; hit=3,second=0 -> win.
    assert m._process_rows([raw_power("1000", 1, 1, 1, 5)])[0][0]["win"] is True
    assert m._process_rows([raw_power("1000", 1, 2, 0, 5)])[0][0]["win"] is False
    assert m._process_rows([raw_power("1000", 1, 3, 0, 5)])[0][0]["win"] is True


# ===========================================================================
# 10-12. POWER NULL predicted_special exclusion + no manufactured second zone
# ===========================================================================

def test_power_missing_predicted_special_excluded():
    rows = [raw_power("1000", 1, 6, 1, None)]  # would be a huge win IF scored
    processed, distinct = m._process_rows(rows)
    assert processed[0]["eligible"] is False
    assert processed[0]["reason"] == m.EXCLUSION_MISSING_PREDICTED_SECOND_ZONE
    assert processed[0]["win"] is False  # never scored, never manufactured
    rec = m.aggregate_window(processed, distinct, 100, "POWER_LOTTO", "pow_s00")
    assert rec["support_draws"] == 0
    assert rec["observed_successes"] == 0
    assert rec["excluded_rows"] == 1
    assert rec["excluded_missing_special_rows"] == 1


def test_power_draw_support_requires_one_scoreable_bet():
    # Draw with one missing-special bet and one valid bet -> supported.
    rows = [raw_power("1000", 1, 1, 1, None), raw_power("1000", 2, 1, 1, 4)]
    processed, distinct = m._process_rows(rows)
    rec = m.aggregate_window(processed, distinct, 100, "POWER_LOTTO", "pow_s00")
    assert rec["support_draws"] == 1
    assert rec["observed_successes"] == 1
    assert rec["scoreable_rows"] == 1
    assert rec["excluded_missing_special_rows"] == 1
    assert rec["bet_count_distribution"] == {"1": 1}  # only scoreable bet counted


def test_exclusion_missing_draw_join_and_causality():
    # join_count=0 -> MISSING_DRAW_JOIN; cutoff>=target -> CAUSALITY_FAILURE.
    no_join = raw_539("1000", 1, 2, join_count=0)
    bad_caus = raw_539("999", 1, 2, cutoff="999")
    processed, _ = m._process_rows([no_join, bad_caus])
    reasons = {p["target_draw"]: p["reason"] for p in processed}
    assert reasons["1000"] == "MISSING_DRAW_JOIN"
    assert reasons["999"] == "CAUSALITY_FAILURE"


# ===========================================================================
# 14-18. End-to-end run_export: schema, provenance, digest, JSON/MD, flags
# ===========================================================================

def _e2e_run(tmp_path, name="e2e"):
    rows = []
    rows += [raw_539("1000", 1, 2, strategy_id="d539_s00"),
             raw_539("999", 1, 1, strategy_id="d539_s00")]
    rows += [raw_big("500", 1, 2, 1, strategy_id="big_s00")]
    rows += [raw_power("700", 1, 1, 1, 4, strategy_id="pow_s00"),
             raw_power("701", 1, 6, 1, None, strategy_id="pow_s00")]
    db = tmp_path / f"{name}.db"
    build_db(db, rows)
    p267c = _write_json(tmp_path / f"{name}_p267c.json", _synthetic_p267c())
    p271a = _write_json(tmp_path / f"{name}_p271a.json", _synthetic_p271a())
    result = m.run_export(
        db_path=str(db), p267c_path=p267c, p271a_path=p271a,
        scorer_path=str(P271C_SRC), adapter_path=str(P271E_SRC),
    )
    return result, str(db)


def test_e2e_schema_and_provenance(tmp_path):
    result, db = _e2e_run(tmp_path)
    assert result["meta"]["frozen_strategy_cell_count"] == 36
    assert result["meta"]["windows"] == [100, 500, 1500]
    prov = result["provenance"]
    assert prov["source_db_path"] == db
    assert prov["single_snapshot"] is True
    assert prov["single_connection"] is True
    assert prov["query_only_evidence"]["query_only_enabled"] is True
    assert set(prov["source_hashes"]) == {
        "p271a_json_sha256", "p267c_json_sha256",
        "p271c_source_sha256", "p271e_source_sha256",
    }
    for v in prov["source_hashes"].values():
        assert len(v) == 64
    assert prov["permitted_tables"] == ["draws", "strategy_prediction_replays"]
    assert len(result["cells"]) == 36


def test_e2e_safety_flags_all_correct(tmp_path):
    result, _ = _e2e_run(tmp_path)
    f = result["safety_flags"]
    assert f["db_read_only"] is True
    assert f["production_write"] is False
    assert f["services_controlled"] is False
    assert f["inference_performed"] is False
    assert f["edge_claim_made"] is False
    assert f["registry_mutation"] is False
    assert f["baseline_computed"] is False
    assert f["p_value_computed"] is False
    assert f["second_zone_manufactured"] is False


def _collect_keys(obj, skip=()):
    keys = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in skip:
                continue
            keys.append(k)
            keys.extend(_collect_keys(v, skip))
    elif isinstance(obj, list):
        for v in obj:
            keys.extend(_collect_keys(v, skip))
    return keys


def test_e2e_no_forbidden_inference_keys(tmp_path):
    # No inference field anywhere (the safety_flags subtree legitimately NAMES
    # these terms to negate them, so it is excluded from the key scan).
    result, _ = _e2e_run(tmp_path, name="infkeys")
    keys = _collect_keys(result, skip=("safety_flags",))
    forbidden = ("p_value", "p_empirical", "baseline", "bonferroni", "bh_fdr",
                 "confidence_interval", "edge_pp", "excess_pp", "significant",
                 "corrected")
    for k in keys:
        kl = k.lower()
        for term in forbidden:
            assert term not in kl, f"forbidden inference key present: {k}"


def test_e2e_deterministic_digest(tmp_path):
    # Two independent builds with identical content at different file paths
    # must yield the same digest (digest excludes wall-clock + paths).
    r1, db1 = _e2e_run(tmp_path, name="det_a")
    r2, db2 = _e2e_run(tmp_path, name="det_b")
    assert db1 != db2
    assert r1["canonical_payload_digest"] == r2["canonical_payload_digest"]


def test_e2e_digest_excludes_volatile_only(tmp_path):
    result, _ = _e2e_run(tmp_path)
    recomputed = m.compute_payload_digest(result)
    assert recomputed == result["canonical_payload_digest"]


def test_e2e_observed_counts_values(tmp_path):
    result, _ = _e2e_run(tmp_path)
    cells = {(c["lottery_type"], c["strategy_id"]): c for c in result["cells"]}
    d539 = cells[("DAILY_539", "d539_s00")]
    w100 = next(w for w in d539["windows"] if w["window"] == 100)
    assert w100["support_draws"] == 2          # draws 1000, 999
    assert w100["observed_successes"] == 1     # only draw 1000 (hit2) wins
    pw = cells[("POWER_LOTTO", "pow_s00")]
    pw100 = next(w for w in pw["windows"] if w["window"] == 100)
    # draw 701 fully excluded (missing special); draw 700 supported + win
    assert pw100["support_draws"] == 1
    assert pw100["observed_successes"] == 1
    assert pw100["excluded_missing_special_rows"] == 1


def test_e2e_json_markdown_consistency(tmp_path):
    result, _ = _e2e_run(tmp_path)
    md = m.render_markdown(result)
    assert result["canonical_payload_digest"] in md
    assert str(result["meta"]["frozen_strategy_cell_count"]) in md
    # A sampled per-cell support value appears in the Markdown table.
    cell = next(c for c in result["cells"] if c["strategy_id"] == "d539_s00")
    w = next(w for w in cell["windows"] if w["window"] == 100)
    assert f"| {w['support_draws']} |" in md


def test_write_artifacts_roundtrip(tmp_path):
    result, _ = _e2e_run(tmp_path)
    oj = tmp_path / "out.json"
    omd = tmp_path / "out.md"
    m.write_artifacts(result, str(oj), str(omd))
    loaded = json.loads(oj.read_text(encoding="utf-8"))
    assert loaded["canonical_payload_digest"] == result["canonical_payload_digest"]
    assert omd.read_text(encoding="utf-8").startswith("# P273A")


def test_per_cell_record_required_fields(tmp_path):
    result, _ = _e2e_run(tmp_path)
    required = {
        "lottery_type", "strategy_id", "window", "requested_window",
        "support_draws", "observed_successes", "observed_success_rate",
        "scoreable_rows", "excluded_rows", "excluded_missing_special_rows",
        "bet_count_min", "bet_count_max", "bet_count_distribution",
        "latest_target_draw", "earliest_target_draw", "endpoint_id",
        "endpoint_source_ref", "strategy_source_ref",
    }
    for cell in result["cells"]:
        for w in cell["windows"]:
            assert required.issubset(set(w))


# ===========================================================================
# 19. Static scan for forbidden write SQL (in string literals)
# ===========================================================================

def test_no_forbidden_write_sql_in_string_literals():
    tree = ast.parse(SCRIPT_PATH.read_text(encoding="utf-8"))
    literals = [
        node.value for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    ]
    pattern = re.compile(
        r"\b(" + "|".join(FORBIDDEN_SQL_TOKENS) + r")\b", re.IGNORECASE
    )
    for lit in literals:
        looks_sql = re.search(r"\b(SELECT|PRAGMA|BEGIN|ROLLBACK|FROM)\b", lit)
        if looks_sql:
            assert not pattern.search(lit), f"forbidden SQL verb in: {lit!r}"


def test_module_has_no_write_or_process_or_registry_interface():
    # Check for real call/import interfaces, not prose in the docstring.
    src = SCRIPT_PATH.read_text(encoding="utf-8")
    for banned in ("import subprocess", "subprocess.", "os.system(",
                   "launchctl", "Popen(", ".commit(", ".executemany(",
                   "hypothesis_registry", "os.remove(", "shutil."):
        assert banned not in src, f"unexpected interface: {banned}"


# ===========================================================================
# 20-22. No production DB reference; no registry mutation; no process control
# ===========================================================================

def test_focused_fixtures_never_open_production_db(tmp_path, monkeypatch):
    opened = []
    real_connect = sqlite3.connect

    def spy(*args, **kwargs):
        opened.append(args[0] if args else kwargs.get("database"))
        return real_connect(*args, **kwargs)

    monkeypatch.setattr(sqlite3, "connect", spy)
    result, db = _e2e_run(tmp_path)
    assert PRODUCTION_DB not in result["provenance"]["source_db_path"]
    for uri in opened:
        assert PRODUCTION_DB not in str(uri)
        assert str(tmp_path) in str(uri) or "p273a" not in str(uri)


def test_canonical_db_constant_is_documented_only():
    # The module documents the production path as the default, but tests never
    # open it. Confirm the constant exists and matches the governed path.
    assert m.CANONICAL_DB_PATH == PRODUCTION_DB
