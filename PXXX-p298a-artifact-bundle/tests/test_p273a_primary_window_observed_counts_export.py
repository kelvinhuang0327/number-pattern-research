"""
P273A — Primary-Window (50/300/750) Prize-Aware Observed-Counts Export tests.

All DB operations use synthetic temporary SQLite databases (pytest tmp_path).
The production database is NEVER opened, referenced, or written by any test.
No registry mutation and no process/service control occurs.

These tests also assert that the wrapper REUSES the committed exporter helpers
(same function objects) rather than forking the exporter, and that the prior
100/500/1500 reference-only windows never appear as primary records.
"""

from __future__ import annotations

import ast
import json
import re
import sqlite3
from pathlib import Path

import pytest

from analysis import p273a_primary_window_observed_counts_export as W
from analysis import p273a_prizeaware_replay_export as B

ROOT = Path(__file__).resolve().parent.parent
WRAPPER_PATH = ROOT / "analysis" / "p273a_primary_window_observed_counts_export.py"
P271C_SRC = ROOT / "lottery_api" / "prize_aware_scorer.py"
P271E_SRC = ROOT / "lottery_api" / "prize_aware_replay_adapter.py"
REAL_P267C = ROOT / "outputs" / "research" / "p267c_m3plus_strategy_revalidation_20260610.json"
REAL_P271A = ROOT / "outputs" / "research" / "p271a_prize_aware_endpoint_scoring_spec_20260611.json"

PRODUCTION_DB = "lottery_api/data/lottery_v2.db"

FORBIDDEN_SQL_TOKENS = (
    "INSERT", "UPDATE", "DELETE", "REPLACE", "CREATE", "ALTER", "DROP",
    "TRUNCATE", "VACUUM", "REINDEX", "ATTACH", "DETACH",
)


# ---------------------------------------------------------------------------
# Synthetic row + DB builders (no production data) — mirror committed exporter
# ---------------------------------------------------------------------------

def _d539(hit):
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
        psp = (actual_special % 8) + 1
    cutoff = cutoff if cutoff is not None else str(int(target_draw) - 1)
    return ("POWER_LOTTO", target_draw, strategy_id, bet_index, cutoff,
            json.dumps(predicted), psp, json.dumps(actual), actual_special,
            join_count)


def build_db(path, replay_rows, draw_keys=None):
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
                B.GOVERNED_ENDPOINT[lt]["endpoint_id"]: {
                    "condition_sql": B.GOVERNED_ENDPOINT[lt]["expected_condition_sql"],
                }
            }
            for lt in B.LOTTERY_TYPES
        }
    }


def _write_json(path, obj):
    path.write_text(json.dumps(obj), encoding="utf-8")
    return str(path)


# ===========================================================================
# Owner-approved window policy: exact 50/300/750; reject 100/500/1500
# ===========================================================================

def test_primary_windows_exactly_50_300_750():
    assert W.PRIMARY_WINDOWS == (50, 300, 750)
    assert W.PRIMARY_WINDOW_LABELS == {50: "SHORT", 300: "MID", 750: "LONG"}


def test_forbidden_reference_only_windows_not_primary():
    for w in (100, 500, 1500):
        assert w not in W.PRIMARY_WINDOWS
    assert W._FORBIDDEN_PRIMARY_WINDOWS == frozenset({100, 500, 1500})


def test_reference_only_metadata_includes_1500():
    pol = W.build_window_policy()
    assert pol["reference_only_windows"] == [1500]
    assert "all-history frequency or distribution" in pol["reference_only_descriptions"]
    for use in ("strategy_promotion", "strategy_elimination",
                "stability_pass_or_fail", "go_recommendation",
                "production_deployment_screening"):
        assert use in pol["reference_only_prohibited_uses"]


def test_future_correction_family_is_108():
    assert W.CORRECTION_FAMILY_PLANNED == 108
    assert W.build_window_policy()["correction_family_planned"] == 108
    assert B.EXPECTED_FROZEN_CELL_COUNT * len(W.PRIMARY_WINDOWS) == 108


# ===========================================================================
# Reuse of the committed exporter helpers (same objects, no fork)
# ===========================================================================

def test_reuses_committed_exporter_helpers():
    assert W.aggregate_window is B.aggregate_window
    assert W._process_rows is B._process_rows
    assert W.compute_payload_digest is B.compute_payload_digest
    assert W.load_frozen_cells is B.load_frozen_cells
    assert W.verify_endpoints_against_p271a is B.verify_endpoints_against_p271a
    assert W.open_readonly_connection is B.open_readonly_connection
    assert W.verify_schema is B.verify_schema
    assert W.CELL_QUERY is B.CELL_QUERY


# ===========================================================================
# Frozen 36 cells (committed P267C)
# ===========================================================================

def test_frozen_cells_exactly_36_synthetic(tmp_path):
    p = _write_json(tmp_path / "p267c.json", _synthetic_p267c())
    cells = W.load_frozen_cells(p)
    assert len(cells) == 36
    assert sum(c["lottery_type"] == "DAILY_539" for c in cells) == 15
    assert sum(c["lottery_type"] == "BIG_LOTTO" for c in cells) == 11
    assert sum(c["lottery_type"] == "POWER_LOTTO" for c in cells) == 10


def test_real_committed_p267c_has_36_cells():
    cells = W.load_frozen_cells(str(REAL_P267C))
    assert len(cells) == 36


# ===========================================================================
# mode=ro / query_only / single connection + transaction
# ===========================================================================

def test_mode_ro_uri_and_query_only(tmp_path):
    db = tmp_path / "syn.db"
    build_db(db, [raw_539("1000", 1, 2)])
    conn, evidence = W.open_readonly_connection(str(db))
    try:
        assert evidence["mode_ro"] is True
        assert "?mode=ro" in evidence["connection_uri"]
        assert evidence["query_only_enabled"] is True
        assert evidence["query_only_pragma_value"] == 1
        with pytest.raises(sqlite3.OperationalError):
            conn.execute("INSERT INTO draws (lottery_type, draw) VALUES ('X','1')")
    finally:
        conn.close()


def test_single_connection_and_single_transaction_in_source():
    src = WRAPPER_PATH.read_text(encoding="utf-8")
    assert src.count("sqlite3.connect(") == 0  # wrapper opens via reused helper
    assert src.count('conn.execute("BEGIN")') == 1
    assert src.count('conn.execute("ROLLBACK")') == 1


# ===========================================================================
# Windowing: most-recent N distinct (50/300/750) + CAST integer ordering
# ===========================================================================

def test_primary_window_caps_and_span(tmp_path):
    # 800 single-bet eligible DAILY_539 draws (target_draw 1..800).
    rows = [raw_539(str(d), 1, 2 if d % 2 == 0 else 1, strategy_id="d539_s00")
            for d in range(1, 801)]
    db = tmp_path / "win.db"
    build_db(db, rows)
    conn, _ = W.open_readonly_connection(str(db))
    try:
        conn.execute("BEGIN")
        cell = W.compute_cell_primary(conn, "DAILY_539", "d539_s00")
        conn.execute("ROLLBACK")
    finally:
        conn.close()
    by_w = {w["window"]: w for w in cell["windows"]}
    assert sorted(by_w) == [50, 300, 750]
    assert by_w[50]["support_draws"] == 50
    assert by_w[50]["latest_target_draw"] == "800"
    assert by_w[50]["earliest_target_draw"] == "751"
    assert by_w[300]["support_draws"] == 300
    assert by_w[750]["support_draws"] == 750
    assert by_w[750]["earliest_target_draw"] == "51"
    # even target_draws win (hit2); within most-recent 50 (751..800) -> 25 wins
    assert by_w[50]["observed_successes"] == 25
    # window labels attached
    assert by_w[50]["window_label"] == "SHORT"
    assert by_w[300]["window_label"] == "MID"
    assert by_w[750]["window_label"] == "LONG"


def test_cast_integer_ordering_not_lexical(tmp_path):
    rows = [raw_539(d, 1, 2) for d in ("9", "10", "200", "1000")]
    db = tmp_path / "ord.db"
    build_db(db, rows)
    conn, _ = W.open_readonly_connection(str(db))
    try:
        conn.execute("BEGIN")
        cell = W.compute_cell_primary(conn, "DAILY_539", "d539_s00")
        conn.execute("ROLLBACK")
    finally:
        conn.close()
    w50 = next(w for w in cell["windows"] if w["window"] == 50)
    assert w50["latest_target_draw"] == "1000"     # CAST DESC, not lexical
    assert w50["earliest_target_draw"] == "9"       # int 9 < 10, not lexical


# ===========================================================================
# Dedup, any-bet aggregation, bet-count distribution
# ===========================================================================

def test_duplicate_row_dedup():
    dup = raw_539("1000", 1, 2)
    processed, distinct = W._process_rows([dup, dup, dup])
    assert len(processed) == 1
    assert distinct == ["1000"]


def test_draw_level_any_bet_and_bet_count():
    rows = [raw_539("1000", 1, 2), raw_539("1000", 2, 1)]
    processed, distinct = W._process_rows(rows)
    rec = W.aggregate_window(processed, distinct, 50, "DAILY_539", "d539_s00")
    assert rec["support_draws"] == 1
    assert rec["observed_successes"] == 1
    assert rec["scoreable_rows"] == 2
    assert rec["bet_count_distribution"] == {"2": 1}


def test_variable_bet_count_distribution():
    rows = [raw_539("1000", 1, 1), raw_539("1000", 2, 1), raw_539("999", 1, 1)]
    processed, distinct = W._process_rows(rows)
    rec = W.aggregate_window(processed, distinct, 300, "DAILY_539", "d539_s00")
    assert rec["support_draws"] == 2
    assert rec["bet_count_min"] == 1
    assert rec["bet_count_max"] == 2
    assert rec["bet_count_constant"] is False
    assert rec["bet_count_distribution"] == {"1": 1, "2": 1}


# ===========================================================================
# POWER missing second-zone exclusion + no manufactured value
# ===========================================================================

def test_power_missing_predicted_special_excluded():
    rows = [raw_power("1000", 1, 6, 1, None)]
    processed, distinct = W._process_rows(rows)
    assert processed[0]["eligible"] is False
    assert processed[0]["reason"] == B.EXCLUSION_MISSING_PREDICTED_SECOND_ZONE
    assert processed[0]["win"] is False
    rec = W.aggregate_window(processed, distinct, 50, "POWER_LOTTO", "pow_s00")
    assert rec["support_draws"] == 0
    assert rec["excluded_missing_special_rows"] == 1


def test_power_draw_support_requires_one_scoreable_bet():
    rows = [raw_power("1000", 1, 1, 1, None), raw_power("1000", 2, 1, 1, 4)]
    processed, distinct = W._process_rows(rows)
    rec = W.aggregate_window(processed, distinct, 50, "POWER_LOTTO", "pow_s00")
    assert rec["support_draws"] == 1
    assert rec["observed_successes"] == 1
    assert rec["scoreable_rows"] == 1
    assert rec["excluded_missing_special_rows"] == 1


# ===========================================================================
# End-to-end run_export: schema, policy, digest, JSON/MD, flags
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
    result = W.run_export(
        db_path=str(db), p267c_path=p267c, p271a_path=p271a,
        scorer_path=str(P271C_SRC), adapter_path=str(P271E_SRC),
    )
    return result, str(db)


def test_e2e_meta_and_policy(tmp_path):
    result, db = _e2e_run(tmp_path)
    assert result["meta"]["task_id"] == "P273A_PRIMARY_WINDOW_OBSERVED_COUNTS_EXPORT"
    assert result["meta"]["primary_windows"] == [50, 300, 750]
    assert result["meta"]["frozen_strategy_cell_count"] == 36
    pol = result["window_policy"]
    assert pol["owner_approved"] is True
    assert pol["primary_windows"] == [50, 300, 750]
    assert pol["reference_only_windows"] == [1500]
    assert pol["correction_family_planned"] == 108
    assert len(result["cells"]) == 36


def test_e2e_only_primary_windows_present(tmp_path):
    result, _ = _e2e_run(tmp_path, name="winonly")
    seen = set()
    for cell in result["cells"]:
        for w in cell["windows"]:
            seen.add(w["window"])
    assert seen == {50, 300, 750}
    assert seen.isdisjoint({100, 500, 1500})


def test_e2e_safety_flags_all_correct(tmp_path):
    result, _ = _e2e_run(tmp_path)
    f = result["safety_flags"]
    assert f["db_read_only"] is True
    assert f["production_write"] is False
    assert f["services_controlled"] is False
    assert f["inference_performed"] is False
    assert f["edge_claim_made"] is False
    assert f["go_recommendation_made"] is False
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
    # The data subtrees (cells, provenance, endpoints) must carry no inference
    # fields. safety_flags + window_policy legitimately NAME governance terms
    # (to negate/plan them), so they are excluded from the key scan.
    result, _ = _e2e_run(tmp_path, name="infkeys")
    keys = _collect_keys(result, skip=("safety_flags", "window_policy"))
    forbidden = ("p_value", "p_empirical", "baseline", "bonferroni", "bh_fdr",
                 "confidence_interval", "expected_success", "edge_pp",
                 "excess_pp", "significant", "corrected", "go_recommend")
    for k in keys:
        kl = k.lower()
        for term in forbidden:
            assert term not in kl, f"forbidden inference key present: {k}"


def test_e2e_deterministic_digest(tmp_path):
    r1, db1 = _e2e_run(tmp_path, name="det_a")
    r2, db2 = _e2e_run(tmp_path, name="det_b")
    assert db1 != db2
    assert r1["canonical_payload_digest"] == r2["canonical_payload_digest"]


def test_e2e_digest_excludes_volatile_only(tmp_path):
    result, _ = _e2e_run(tmp_path)
    assert W.compute_payload_digest(result) == result["canonical_payload_digest"]


def test_e2e_observed_counts_values(tmp_path):
    result, _ = _e2e_run(tmp_path)
    cells = {(c["lottery_type"], c["strategy_id"]): c for c in result["cells"]}
    d539 = cells[("DAILY_539", "d539_s00")]
    w50 = next(w for w in d539["windows"] if w["window"] == 50)
    assert w50["support_draws"] == 2
    assert w50["observed_successes"] == 1
    pw = cells[("POWER_LOTTO", "pow_s00")]
    pw50 = next(w for w in pw["windows"] if w["window"] == 50)
    assert pw50["support_draws"] == 1
    assert pw50["observed_successes"] == 1
    assert pw50["excluded_missing_special_rows"] == 1


def test_e2e_json_markdown_consistency(tmp_path):
    result, _ = _e2e_run(tmp_path)
    md = W.render_markdown(result)
    assert result["canonical_payload_digest"] in md
    assert str(result["meta"]["frozen_strategy_cell_count"]) in md
    assert "50 (SHORT)" in md and "300 (MID)" in md and "750 (LONG)" in md
    assert "108" in md
    cell = next(c for c in result["cells"] if c["strategy_id"] == "d539_s00")
    w = next(w for w in cell["windows"] if w["window"] == 50)
    assert f"| {w['support_draws']} |" in md


def test_write_artifacts_roundtrip(tmp_path):
    result, _ = _e2e_run(tmp_path)
    oj = tmp_path / "out.json"
    omd = tmp_path / "out.md"
    W.write_artifacts(result, str(oj), str(omd))
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
        "latest_target_draw", "earliest_target_draw",
    }
    for cell in result["cells"]:
        for w in cell["windows"]:
            assert required.issubset(set(w))


# ===========================================================================
# Static safety scans
# ===========================================================================

def test_no_forbidden_write_sql_in_string_literals():
    tree = ast.parse(WRAPPER_PATH.read_text(encoding="utf-8"))
    literals = [
        node.value for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    ]
    pattern = re.compile(
        r"\b(" + "|".join(FORBIDDEN_SQL_TOKENS) + r")\b", re.IGNORECASE
    )
    for lit in literals:
        if re.search(r"\b(SELECT|PRAGMA|BEGIN|ROLLBACK|FROM)\b", lit):
            assert not pattern.search(lit), f"forbidden SQL verb in: {lit!r}"


def test_module_has_no_write_or_process_or_registry_interface():
    src = WRAPPER_PATH.read_text(encoding="utf-8")
    for banned in ("import subprocess", "subprocess.", "os.system(",
                   "launchctl", "Popen(", ".commit(", ".executemany(",
                   "hypothesis_registry", "os.remove(", "shutil."):
        assert banned not in src, f"unexpected interface: {banned}"


def test_canonical_db_constant_is_documented_only():
    assert W.CANONICAL_DB_PATH == PRODUCTION_DB


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
