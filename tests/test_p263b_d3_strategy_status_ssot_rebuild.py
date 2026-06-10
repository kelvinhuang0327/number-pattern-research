"""
P263B — D3 Strategy Status / Contract Audit SSOT Rebuild (read-only tests).

Validates the new read-only endpoint GET /api/replay/d3-strategy-status-coverage
and the new index.html SSOT section. The endpoint reads the replay store via
SELECT only; these tests assert coverage, fields, the success-rate contract, the
P263A bug fixes (lifecycle/registry agreement; no per-lottery replay-count swap),
and that no DB rows change. They never write the DB, registry, or any artifact.

The existing artifact-backed /api/replay/d3-strategy-status-audit (P258N) is NOT
modified by P263B and its contract tests remain green.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
LOTTERY_API_DIR = str(REPO_ROOT / "lottery_api")
if LOTTERY_API_DIR not in sys.path:
    sys.path.insert(0, LOTTERY_API_DIR)
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

INDEX_HTML = REPO_ROOT / "index.html"
DB_PATH = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
COVERAGE_ROUTE = "/api/replay/d3-strategy-status-coverage"

FORBIDDEN_D3_STATUSES = {
    "APPROVED", "PROMOTED", "PRODUCTION_READY", "RECOMMENDED",
    "PREDICTIVE_EDGE_CONFIRMED",
}

NEW_REQUIRED_ROW_FIELDS = [
    "registry_status", "distinct_draw_count", "can_open_detail", "missing_reason",
    "status_reason", "status_updated_at", "status_source",
    "reject_reason", "reject_updated_at", "reject_source_artifact",
    "success_rate_30", "success_rate_100", "success_rate_500", "success_rate_1500",
    "available_draws_30", "available_draws_100", "available_draws_500",
    "available_draws_1500",
]

ORPHANS = {("POWER_LOTTO", "midfreq_fourier_mk_3bet"), ("POWER_LOTTO", "pp3_freqort_4bet")}
REGISTERED_WITHOUT_ROWS = {
    ("BIG_LOTTO", "biglotto_ts3_acb_4bet"),
    ("BIG_LOTTO", "biglotto_ts3_markov_freq_5bet"),
    ("DAILY_539", "p1_deviation_2bet_539"),
    ("POWER_LOTTO", "h6_gate_mk20_ew85"),
    ("POWER_LOTTO", "power_shlc_midfreq"),
}
MISMATCH = ("POWER_LOTTO", "midfreq_fourier_2bet")


# ── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def payload() -> dict:
    if not DB_PATH.exists():
        pytest.skip(f"replay DB not present at {DB_PATH}")
    try:
        from routes import replay as replay_mod
    except Exception as exc:
        pytest.skip(f"replay module unavailable: {exc}")
    return replay_mod._build_d3_ssot_coverage_payload()


@pytest.fixture(scope="module")
def api_payload() -> dict:
    if not DB_PATH.exists():
        pytest.skip(f"replay DB not present at {DB_PATH}")
    try:
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        from routes import replay as replay_mod
    except Exception as exc:
        pytest.skip(f"fastapi/replay unavailable: {exc}")
    app = FastAPI()
    app.include_router(replay_mod.router)
    try:
        client = TestClient(app)
    except TypeError:
        pytest.skip("TestClient version incompatibility")
    r = client.get(COVERAGE_ROUTE)
    assert r.status_code == 200, f"{r.status_code}: {r.text}"
    return r.json()


@pytest.fixture(scope="module")
def rows_by_key(payload) -> dict:
    return {(r["lottery_type"], r["strategy_id"]): r for r in payload["rows"]}


@pytest.fixture(scope="module")
def html() -> str:
    return INDEX_HTML.read_text(encoding="utf-8")


# ── Coverage = full P262B universe ──────────────────────────────────────────

def test_api_route_and_200(api_payload):
    assert api_payload["route_path"] == COVERAGE_ROUTE
    assert isinstance(api_payload["rows"], list)


def test_coverage_is_41_cells_40_strategies(payload):
    assert payload["summary"]["total_cells"] == 41
    assert payload["summary"]["total_strategies"] == 40
    assert len(payload["rows"]) == 41


def test_coverage_summary_matches_p262b(payload):
    c = payload["coverage_summary"]
    assert c["registered"] == 38
    assert c["unregistered_orphan"] == 2
    assert c["registry_lottery_mismatch"] == 1
    assert c["with_replay_rows"] == 36
    assert c["without_replay_rows"] == 5
    assert c["can_open_detail"] == 36


def test_no_phantom_rows(payload, rows_by_key):
    """Every D3 row maps to a registry-supported or replay-store cell (no RSM phantoms)."""
    from routes import replay as replay_mod
    meta = replay_mod.list_strategy_lifecycle_metadata()
    supported = {(lt, m["strategy_id"]) for m in meta for lt in m["supported_lottery_types"]}
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    try:
        db_cells = {(r[0], r[1]) for r in conn.execute(
            "SELECT DISTINCT lottery_type, strategy_id FROM strategy_prediction_replays")}
    finally:
        conn.close()
    universe = supported | db_cells
    for key in rows_by_key:
        assert key in universe, f"phantom row not in SSOT universe: {key}"
    # the 6 P263A phantom ids must NOT appear
    phantom_ids = {"f4cold_5bet", "regime_2bet", "p1_deviation_4bet",
                   "p1_dev_sum5bet", "p1_neighbor_cold_2bet", "orthogonal_5bet"}
    present = {sid for (_lt, sid) in rows_by_key}
    assert phantom_ids.isdisjoint(present)


# ── Orphans / registered-without-rows / mismatch ────────────────────────────

def test_orphans_present_can_open_detail_true(rows_by_key):
    for key in ORPHANS:
        r = rows_by_key[key]
        assert r["registry_status"] == "unregistered_orphan"
        assert r["can_open_detail"] is True


def test_registered_without_rows_present_can_open_detail_false(rows_by_key):
    for key in REGISTERED_WITHOUT_ROWS:
        r = rows_by_key[key]
        assert r["has_replay_rows"] is False
        assert r["can_open_detail"] is False
        for n in (30, 100, 500, 1500):
            assert r[f"success_rate_{n}"] is None
            assert r[f"available_draws_{n}"] == 0


def test_mismatch_present(rows_by_key):
    assert rows_by_key[MISMATCH]["registry_status"] == "registry_lottery_mismatch"


# ── All P263A-missing fields now present ────────────────────────────────────

def test_every_row_has_all_new_fields(payload):
    for r in payload["rows"]:
        for f in NEW_REQUIRED_ROW_FIELDS:
            assert f in r, f"{r['strategy_id']} missing {f}"


def test_success_rate_fields_exist_and_in_range(payload):
    for r in payload["rows"]:
        for n in (30, 100, 500, 1500):
            sr = r[f"success_rate_{n}"]
            assert sr is None or (0.0 <= sr <= 1.0)
            assert isinstance(r[f"available_draws_{n}"], int)


# ── Bug fix #1: lifecycle agrees with registry (no contradiction) ───────────

def test_lifecycle_matches_registry_for_registered(payload):
    from routes import replay as replay_mod
    meta = {m["strategy_id"]: m for m in replay_mod.list_strategy_lifecycle_metadata()}
    for r in payload["rows"]:
        if r["registry_status"] == "registered":
            assert r["lifecycle"] == meta[r["strategy_id"]]["lifecycle_status"], (
                f"{r['strategy_id']} lifecycle {r['lifecycle']} != registry"
            )


def test_orphans_lifecycle_unregistered(rows_by_key):
    for key in ORPHANS:
        assert rows_by_key[key]["lifecycle"] == "UNREGISTERED"


# ── Bug fix #2: replay_row_count is per-cell, no DAILY_539/POWER_LOTTO swap ──

def test_replay_row_count_matches_db_per_cell(payload):
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    try:
        db = {(r[0], r[1]): r[2] for r in conn.execute(
            "SELECT lottery_type, strategy_id, COUNT(*) "
            "FROM strategy_prediction_replays GROUP BY lottery_type, strategy_id")}
    finally:
        conn.close()
    for r in payload["rows"]:
        key = (r["lottery_type"], r["strategy_id"])
        assert r["replay_row_count"] == db.get(key, 0), f"{key} replay count mismatch"


def test_no_lottery_total_transposition(payload):
    by_lottery = {}
    for r in payload["rows"]:
        by_lottery[r["lottery_type"]] = by_lottery.get(r["lottery_type"], 0) + r["replay_row_count"]
    # DB truth (un-swapped): 539=34,680 / POWER=36,104 / BIG=24,140
    assert by_lottery["DAILY_539"] == 34680
    assert by_lottery["POWER_LOTTO"] == 36104
    assert by_lottery["BIG_LOTTO"] == 24140


# ── Reject provenance from rejected/*.json ──────────────────────────────────

def test_reject_reason_shown_when_artifact_exists(rows_by_key):
    r = rows_by_key[("BIG_LOTTO", "markov_2bet_biglotto")]
    assert r["reject_reason"] and r["reject_reason"] != "unknown"
    assert r["reject_source_artifact"] == "rejected/markov_2bet_biglotto.json"
    assert r["reject_updated_at"]


def test_malformed_reject_artifact_is_unknown_not_fabricated(rows_by_key):
    r = rows_by_key[("DAILY_539", "p1_deviation_2bet_539")]
    assert r["reject_reason"] == "unknown"
    assert r["reject_source_artifact"] == "rejected/p1_deviation_2bet_539.json"


def test_online_strategy_has_no_reject_reason(rows_by_key):
    r = rows_by_key[("BIG_LOTTO", "ts3_regime_3bet")]
    assert r["reject_reason"] is None


# ── Success-rate contract correctness (spot-check vs direct SQL) ────────────

def test_success_rate_30_matches_direct_sql(rows_by_key):
    # P265A: success metric recontracted to M3+ (hit_count >= 3); special_hit
    # no longer contributes on its own.
    lt, sid = "BIG_LOTTO", "ts3_regime_3bet"
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    try:
        draws = conn.execute(
            """
            SELECT MAX(CASE WHEN hit_count >= 3 THEN 1 ELSE 0 END) AS ds
            FROM strategy_prediction_replays
            WHERE lottery_type = ? AND strategy_id = ?
            GROUP BY target_draw
            ORDER BY CAST(target_draw AS INTEGER) DESC
            LIMIT 30
            """, (lt, sid)).fetchall()
    finally:
        conn.close()
    vals = [int(d[0]) for d in draws]
    expected = round(sum(vals) / len(vals), 4)
    assert rows_by_key[(lt, sid)]["success_rate_30"] == expected
    assert rows_by_key[(lt, sid)]["available_draws_30"] == len(vals)


# ── Safety semantics preserved ──────────────────────────────────────────────

def test_all_d3_contract_status_not_evaluated(payload):
    for r in payload["rows"]:
        assert r["d3_contract_status"] == "NOT_EVALUATED_BY_D3"


def test_no_forbidden_d3_statuses(payload):
    statuses = {r["d3_contract_status"] for r in payload["rows"]}
    assert statuses.isdisjoint(FORBIDDEN_D3_STATUSES)


def test_safety_disclaimers_present(payload):
    d = payload["safety_disclaimers"]
    assert len(d) >= 5
    assert any("prediction model" in x.lower() for x in d)
    assert any("not approval" in x.lower() for x in d)
    assert any("betting advice" in x.lower() for x in d)


def test_forbidden_actions_confirmed(payload):
    fac = payload["forbidden_actions_confirmed"]
    assert fac["no_db_write"] is True
    assert fac["no_replay_backfill"] is True
    assert fac["no_registry_mutation"] is True
    assert fac["no_adapter_change"] is True
    assert fac["no_migration"] is True
    assert fac["read_only_query"] is True


def test_success_rate_contract_declared(payload):
    sc = payload["success_rate_contract"]
    assert sc["windows"] == [30, 100, 500, 1500]
    assert sc["display_metric_only"] is True
    assert sc["not_a_promotion_gate"] is True
    # P265A: recontracted from any-hit to M3+ (hit_count >= 3).
    assert "hit_count >= 3" in sc["draw_success_rule"]
    assert sc["success_metric"] == "M3_PLUS"
    assert sc["special_hit_excluded"] is True


# ── No DB write (read-only) ─────────────────────────────────────────────────

def test_endpoint_does_not_change_db_row_count():
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    try:
        before = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
    finally:
        conn.close()
    from routes import replay as replay_mod
    replay_mod._build_d3_ssot_coverage_payload()
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    try:
        after = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
    finally:
        conn.close()
    assert before == after == 94924


# ── UI section ──────────────────────────────────────────────────────────────

def test_ui_section_and_nav_exist(html):
    assert 'id="p263b-d3-ssot-section"' in html
    assert 'data-section="p263b-d3-ssot"' in html


def test_ui_fetches_coverage_route(html):
    assert COVERAGE_ROUTE in html


def test_ui_has_success_rate_columns(html):
    section_start = html.find('id="p263b-d3-ssot-section"')
    section = html[section_start:section_start + 6000]
    for label in ("30期", "100期", "500期", "1500期"):
        assert label in section


def test_ui_has_safety_disclaimers(html):
    section_start = html.find('id="p263b-d3-ssot-section"')
    section = html[section_start:section_start + 6000]
    assert "預測模型" in section
    assert "下注建議" in section
    assert "NOT_YET_REJECTED" in section


def test_ui_no_forbidden_statuses_in_section(html):
    start = html.find('id="p263b-d3-ssot-section"')
    end = html.find("END P263B")
    section = html[start:end]
    for status in FORBIDDEN_D3_STATUSES:
        assert status not in section


def test_ui_does_not_modify_p258_section_fetch(html):
    """P258O section must still fetch the original artifact route (untouched)."""
    assert "/api/replay/d3-strategy-status-audit" in html
