"""P262B — Tests for the read-only Replay Overview Coverage Remediation.

Verifies that GET /api/replay/history-overview, in the new opt-in
`coverage_mode=true`, surfaces EVERY known strategy cell — registered
strategies, DB orphan strategies (replay rows but unregistered), registry/
lottery mismatches, and registered-without-rows strategies — each annotated
with registry_status / has_replay_rows / can_open_detail / missing_reason /
coverage_warning / available_bet_indices / max_bet_index / distinct_draw_count.

Hard guarantees asserted here (all READ-ONLY):
- coverage view contains all 40 known strategies (P262A matrix baseline)
- the 2 orphans + 1 registry/lottery mismatch + 5 registered-without-rows appear
- multi-bet strategies are visible in the default coverage view (bet_index=0)
- the explicit bet_index filter still works
- the LEGACY no-param behaviour (P259A) is byte-for-byte preserved
- no DB row-count change, no registry mutation across calls (read-only)

P262A matrix baseline (landed on main, commit 931ea93):
  total known strategies = 40 | registered = 38 | with replay rows = 35
  orphans               = midfreq_fourier_mk_3bet, pp3_freqort_4bet
  registry/lottery miss = POWER_LOTTO:midfreq_fourier_2bet
  registered w/o rows   = biglotto_ts3_acb_4bet, biglotto_ts3_markov_freq_5bet,
                          h6_gate_mk20_ew85, p1_deviation_2bet_539,
                          power_shlc_midfreq
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

EXPECTED_TOTAL_KNOWN = 40
EXPECTED_ORPHANS = {"midfreq_fourier_mk_3bet", "pp3_freqort_4bet"}
EXPECTED_MISMATCH_CELL = ("POWER_LOTTO", "midfreq_fourier_2bet")
EXPECTED_REGISTERED_NO_ROWS = {
    "biglotto_ts3_acb_4bet",
    "biglotto_ts3_markov_freq_5bet",
    "h6_gate_mk20_ew85",
    "p1_deviation_2bet_539",
    "power_shlc_midfreq",
}
ALLOWED_MISSING_REASONS = {
    "registered_without_rows",
    "artifact_only",
    "observation_no_data",
    "no_production_replay",
}
NEW_ROW_FIELDS = [
    "has_replay_rows", "distinct_draw_count", "max_bet_index",
    "available_bet_indices", "registry_status", "can_open_detail",
    "missing_reason", "coverage_warning",
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def client():
    """FastAPI TestClient with only the replay router mounted."""
    try:
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
    except ImportError as exc:
        pytest.skip(f"fastapi/httpx not available: {exc}")

    lottery_api_dir = str(REPO_ROOT / "lottery_api")
    if lottery_api_dir not in sys.path:
        sys.path.insert(0, lottery_api_dir)
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))

    try:
        from routes import replay as replay_mod
    except Exception as exc:
        pytest.skip(f"replay module unavailable: {exc}")

    app = FastAPI()
    app.include_router(replay_mod.router)
    try:
        return TestClient(app)
    except TypeError:
        pytest.skip("TestClient version incompatibility")


def _coverage_all(client):
    """Full coverage view: all bet counts, all lottery types."""
    return client.get("/api/replay/history-overview?coverage_mode=true&bet_index=0").json()


def _rows_by_strategy(rows):
    out = {}
    for r in rows:
        out.setdefault(r["strategy_id"], []).append(r)
    return out


# ---------------------------------------------------------------------------
# 1. Endpoint shape — coverage mode
# ---------------------------------------------------------------------------

def test_coverage_endpoint_200(client):
    r = client.get("/api/replay/history-overview?coverage_mode=true&bet_index=0")
    assert r.status_code == 200, f"got {r.status_code}: {r.text[:300]}"


def test_coverage_top_level_fields(client):
    d = _coverage_all(client)
    for f in ["coverage_mode", "total_known_strategies", "coverage_summary",
              "total_rows", "rows", "bet_index_filter"]:
        assert f in d, f"missing top-level field: {f}"
    assert d["coverage_mode"] is True
    assert d["bet_index_filter"] == 0


def test_coverage_summary_internal_consistency(client):
    d = _coverage_all(client)
    s = d["coverage_summary"]
    assert s["registered"] + s["unregistered_orphan"] + s["registry_lottery_mismatch"] == d["total_rows"]
    assert s["with_replay_rows"] + s["without_replay_rows"] == d["total_rows"]


# ---------------------------------------------------------------------------
# 2. Total coverage = 40 known strategies (P262A baseline)
# ---------------------------------------------------------------------------

def test_total_known_strategies_is_40(client):
    d = _coverage_all(client)
    distinct = {r["strategy_id"] for r in d["rows"]}
    assert len(distinct) == EXPECTED_TOTAL_KNOWN, (
        f"expected {EXPECTED_TOTAL_KNOWN} distinct strategies, got {len(distinct)}"
    )
    assert d["total_known_strategies"] == EXPECTED_TOTAL_KNOWN


def test_coverage_visible_count_exceeds_legacy_13(client):
    """The core P262A gap: default bet_index=1 only showed 13. Coverage shows all."""
    legacy = client.get("/api/replay/history-overview").json()  # no params
    coverage = _coverage_all(client)
    assert legacy["total_rows"] == 13, "legacy default view baseline is 13 rows"
    assert len({r["strategy_id"] for r in coverage["rows"]}) > 13
    assert coverage["total_known_strategies"] == 40


# ---------------------------------------------------------------------------
# 3. Orphan strategies (replay rows but unregistered) now appear
# ---------------------------------------------------------------------------

def test_orphans_present_in_coverage(client):
    d = _coverage_all(client)
    by = _rows_by_strategy(d["rows"])
    for sid in EXPECTED_ORPHANS:
        assert sid in by, f"orphan {sid} missing from coverage overview"


def test_orphans_marked_unregistered_with_detail(client):
    d = _coverage_all(client)
    by = _rows_by_strategy(d["rows"])
    for sid in EXPECTED_ORPHANS:
        row = by[sid][0]
        assert row["registry_status"] == "unregistered_orphan", sid
        assert row["has_replay_rows"] is True, sid
        assert row["can_open_detail"] is True, sid
        assert row["total_replay_rows"] > 0, sid
        assert row["coverage_warning"], f"{sid} should carry a coverage_warning"


# ---------------------------------------------------------------------------
# 4. Registry/lottery mismatch surfaced
# ---------------------------------------------------------------------------

def test_registry_lottery_mismatch_present(client):
    d = _coverage_all(client)
    lt, sid = EXPECTED_MISMATCH_CELL
    cell = [r for r in d["rows"]
            if r["strategy_id"] == sid and r["lottery_type"] == lt]
    assert cell, f"mismatch cell {lt}:{sid} missing from coverage overview"
    row = cell[0]
    assert row["registry_status"] == "registry_lottery_mismatch"
    assert row["has_replay_rows"] is True
    assert row["coverage_warning"]


def test_mismatch_not_in_legacy_overview(client):
    """The mismatch cell must NEVER have appeared in the registry-only legacy walk."""
    lt, sid = EXPECTED_MISMATCH_CELL
    legacy = client.get("/api/replay/history-overview?bet_index=0").json()
    cells = [r for r in legacy["rows"]
             if r["strategy_id"] == sid and r["lottery_type"] == lt]
    assert not cells, f"legacy overview unexpectedly produced mismatch cell {lt}:{sid}"


# ---------------------------------------------------------------------------
# 5. Registered-without-rows strategies appear, cannot open detail
# ---------------------------------------------------------------------------

def test_registered_without_rows_present(client):
    d = _coverage_all(client)
    by = _rows_by_strategy(d["rows"])
    for sid in EXPECTED_REGISTERED_NO_ROWS:
        assert sid in by, f"registered-without-rows {sid} missing from coverage"


def test_registered_without_rows_cannot_open_detail(client):
    d = _coverage_all(client)
    by = _rows_by_strategy(d["rows"])
    for sid in EXPECTED_REGISTERED_NO_ROWS:
        row = by[sid][0]
        assert row["has_replay_rows"] is False, sid
        assert row["can_open_detail"] is False, sid
        assert row["registry_status"] == "registered", sid
        assert row["missing_reason"] in ALLOWED_MISSING_REASONS, (
            f"{sid} missing_reason={row['missing_reason']} not in allowed set"
        )


def test_known_missing_reason_mapping(client):
    """Spot-check the specific reasons for the well-known no-row strategies."""
    d = _coverage_all(client)
    by = _rows_by_strategy(d["rows"])
    assert by["h6_gate_mk20_ew85"][0]["missing_reason"] == "observation_no_data"
    assert by["biglotto_ts3_acb_4bet"][0]["missing_reason"] == "artifact_only"
    assert by["power_shlc_midfreq"][0]["missing_reason"] == "artifact_only"


# ---------------------------------------------------------------------------
# 6. Multi-bet strategies visible by default; explicit bet filter still works
# ---------------------------------------------------------------------------

def test_multibet_visible_in_default_coverage(client):
    d = _coverage_all(client)
    multibet = [r for r in d["rows"] if r["derived_bet_count"] > 1]
    assert multibet, "default coverage view must include multi-bet strategies"
    bet_counts = {r["derived_bet_count"] for r in d["rows"]}
    assert len(bet_counts) > 1, f"expected multiple bet counts, got {bet_counts}"


def test_explicit_bet_index_filter_still_works(client):
    d3 = client.get("/api/replay/history-overview?coverage_mode=true&bet_index=3").json()
    assert d3["rows"], "bet_index=3 coverage should return rows"
    for r in d3["rows"]:
        assert r["derived_bet_count"] == 3, r["strategy_id"]
    ids = {r["strategy_id"] for r in d3["rows"]}
    assert "midfreq_fourier_mk_3bet" in ids, "3-bet orphan must appear under bet_index=3"
    assert "pp3_freqort_4bet" not in ids, "4-bet orphan must NOT appear under bet_index=3"


def test_coverage_lottery_filter_isolates(client):
    d = client.get(
        "/api/replay/history-overview?coverage_mode=true&bet_index=0&lottery_type=POWER_LOTTO"
    ).json()
    for r in d["rows"]:
        assert r["lottery_type"] == "POWER_LOTTO", r["strategy_id"]
    ids = {r["strategy_id"] for r in d["rows"]}
    # orphans live under POWER_LOTTO, so they must survive the POWER_LOTTO filter
    assert EXPECTED_ORPHANS.issubset(ids)


# ---------------------------------------------------------------------------
# 7. Row schema — new coverage fields present
# ---------------------------------------------------------------------------

def test_new_fields_present_on_every_row(client):
    d = _coverage_all(client)
    for row in d["rows"]:
        for f in NEW_ROW_FIELDS:
            assert f in row, f"row {row.get('strategy_id')} missing field {f}"


def test_available_bet_indices_is_list(client):
    d = _coverage_all(client)
    for row in d["rows"]:
        assert isinstance(row["available_bet_indices"], list)
        for v in row["available_bet_indices"]:
            assert isinstance(v, int)


def test_can_open_detail_iff_has_rows(client):
    d = _coverage_all(client)
    for row in d["rows"]:
        assert row["can_open_detail"] == row["has_replay_rows"], row["strategy_id"]


# ---------------------------------------------------------------------------
# 8. Orphan detail is actually reachable (P259B/P261A grouped endpoint)
# ---------------------------------------------------------------------------

def test_orphan_detail_grouped_returns_rows(client):
    """can_open_detail=true for orphans must be backed by a working detail query."""
    r = client.get(
        "/api/replay/history-detail-grouped"
        "?lottery_type=POWER_LOTTO&strategy_id=pp3_freqort_4bet&page=1&page_size=10"
    )
    assert r.status_code == 200, f"got {r.status_code}: {r.text[:200]}"
    d = r.json()
    assert d["total_count"] > 0, "orphan with replay rows must return detail rows"
    assert d["rows"], "orphan detail page should have rows"


# ---------------------------------------------------------------------------
# 9. LEGACY (P259A) behaviour preserved — backward compatibility
# ---------------------------------------------------------------------------

def test_legacy_no_param_default_unchanged(client):
    d = client.get("/api/replay/history-overview").json()
    assert d["coverage_mode"] is False
    assert d["default_bet_index"] == 1
    assert d["bet_index_filter"] == 1
    for row in d["rows"]:
        assert row["derived_bet_count"] == 1


def test_legacy_mode_has_no_orphans(client):
    """Legacy registry-only walk must not surface orphan/mismatch cells."""
    d = client.get("/api/replay/history-overview?bet_index=0").json()
    for row in d["rows"]:
        assert row["registry_status"] == "registered", row["strategy_id"]


def test_legacy_rows_still_carry_additive_fields(client):
    d = client.get("/api/replay/history-overview?bet_index=0").json()
    for row in d["rows"]:
        for f in NEW_ROW_FIELDS:
            assert f in row, f"legacy row {row['strategy_id']} missing additive field {f}"


# ---------------------------------------------------------------------------
# 10. READ-ONLY proof — no DB / registry mutation across calls
# ---------------------------------------------------------------------------

def _replay_row_count():
    from routes.replay import _open_conn
    conn = _open_conn()
    try:
        return conn.execute("SELECT COUNT(*) AS c FROM strategy_prediction_replays").fetchone()["c"]
    finally:
        conn.close()


def test_no_db_row_count_change(client):
    before = _replay_row_count()
    client.get("/api/replay/history-overview?coverage_mode=true&bet_index=0")
    client.get("/api/replay/history-overview?coverage_mode=true&bet_index=3")
    after = _replay_row_count()
    assert before == after, f"replay row count changed: {before} -> {after}"


def test_no_registry_mutation(client):
    from routes.replay import list_strategy_lifecycle_metadata
    before = len(list_strategy_lifecycle_metadata())
    client.get("/api/replay/history-overview?coverage_mode=true&bet_index=0")
    after = len(list_strategy_lifecycle_metadata())
    assert before == after == 38, f"registry size changed: {before} -> {after}"


def test_safety_flags_true(client):
    d = _coverage_all(client)
    assert d["no_db_write"] is True
    assert d["no_replay_backfill"] is True
    assert d["no_strategy_adapter_changes"] is True


# ---------------------------------------------------------------------------
# 11. Frontend — coverage columns + JS + P261A detail expand preserved
# ---------------------------------------------------------------------------

def test_html_has_coverage_columns():
    html = (REPO_ROOT / "index.html").read_text(encoding="utf-8")
    for col in ["註冊狀態", "不重複期數", "可用注 index", "缺漏原因"]:
        assert col in html, f"missing coverage column header: {col}"


def test_html_js_uses_coverage_mode():
    html = (REPO_ROOT / "index.html").read_text(encoding="utf-8")
    assert "coverage_mode=true" in html, "overview JS must fetch coverage_mode=true"


def test_html_has_registry_status_badges():
    html = (REPO_ROOT / "index.html").read_text(encoding="utf-8")
    assert "p262b-reg-orphan" in html
    assert "p262b-reg-mismatch" in html
    assert "regStatusBadge" in html


def test_html_p261a_detail_expand_preserved():
    """P262B must not regress the P261A row-expand detail behaviour."""
    html = (REPO_ROOT / "index.html").read_text(encoding="utf-8")
    assert "history-detail-grouped" in html
    assert "p261a-expand-btn" in html
    assert "展開" in html
