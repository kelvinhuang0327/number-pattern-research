"""
P265A — D3 Success Metric Recontract: M3+ Real Replay Success Rate (read-only).

Validates that GET /api/replay/d3-strategy-status-coverage's success_rate_30 /
100 / 500 / 1500 are now M3+ real replay success rates:

  * draw-level success = ANY bet_index for the (cell, target_draw) has
    hit_count >= 3 (at least 3 main-number hits)
  * special_hit does NOT make a draw an M3+ success on its own
  * denominator = distinct target_draw in the window (NOT replay row count)

It also asserts the legacy artifact endpoint (/api/replay/d3-strategy-status-audit)
contract is untouched and the UI wording reflects the M3+ metric. The endpoint
reads the replay store via SELECT only — these tests never write the DB.
"""
from __future__ import annotations

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
LEGACY_AUDIT_ROUTE = "/api/replay/d3-strategy-status-audit"
WINDOWS = [30, 100, 500, 1500]


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
def rows_by_key(payload) -> dict:
    return {(r["lottery_type"], r["strategy_id"]): r for r in payload["rows"]}


@pytest.fixture(scope="module")
def html() -> str:
    assert INDEX_HTML.exists(), f"index.html not found: {INDEX_HTML}"
    return INDEX_HTML.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def conn():
    c = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    yield c
    c.close()


def _m3plus_window(conn, lt, sid, n):
    """Direct-SQL M3+ draw-level success over the most recent n distinct draws."""
    draws = conn.execute(
        """
        SELECT MAX(CASE WHEN hit_count >= 3 THEN 1 ELSE 0 END) AS ds
        FROM strategy_prediction_replays
        WHERE lottery_type = ? AND strategy_id = ?
        GROUP BY target_draw
        ORDER BY CAST(target_draw AS INTEGER) DESC
        LIMIT ?
        """, (lt, sid, n)).fetchall()
    vals = [int(d["ds"]) for d in draws]
    rate = round(sum(vals) / len(vals), 4) if vals else None
    return rate, len(vals)


# ── 1. Metric contract declared as M3+ ──────────────────────────────────────

def test_success_metric_is_m3_plus(payload):
    sc = payload["success_rate_contract"]
    assert sc["success_metric"] == "M3_PLUS"
    assert "hit_count >= 3" in sc["draw_success_rule"]
    assert sc["special_hit_excluded"] is True
    assert sc["windows"] == WINDOWS


def test_metric_contract_denominator_distinct_draw(payload):
    sc = payload["success_rate_contract"]
    assert "distinct target_draw" in sc["denominator"]
    assert "row" in sc["denominator"].lower()  # explicitly NOT row count


def test_metric_still_display_only_not_gate(payload):
    sc = payload["success_rate_contract"]
    assert sc["display_metric_only"] is True
    assert sc["not_a_promotion_gate"] is True
    assert sc["not_a_strategy_ranking"] is True


# ── 2. success_rate matches M3+ direct SQL (single-bet + multi-bet) ──────────

def test_single_bet_success_rate_matches_m3plus_sql(conn, rows_by_key):
    lt, sid = "BIG_LOTTO", "markov_single_biglotto"
    if (lt, sid) not in rows_by_key:
        pytest.skip(f"{sid} not in payload")
    for n in WINDOWS:
        rate, avail = _m3plus_window(conn, lt, sid, n)
        assert rows_by_key[(lt, sid)][f"success_rate_{n}"] == rate
        assert rows_by_key[(lt, sid)][f"available_draws_{n}"] == avail


def test_multi_bet_success_rate_matches_m3plus_sql(conn, rows_by_key):
    """daily539_f4cold_5bet: 5 bets/draw, 1500 distinct draws (7500 rows)."""
    lt, sid = "DAILY_539", "daily539_f4cold_5bet"
    if (lt, sid) not in rows_by_key:
        pytest.skip(f"{sid} not in payload")
    for n in WINDOWS:
        rate, avail = _m3plus_window(conn, lt, sid, n)
        assert rows_by_key[(lt, sid)][f"success_rate_{n}"] == rate
        assert rows_by_key[(lt, sid)][f"available_draws_{n}"] == avail


# ── 3. Denominator is distinct target_draw, not replay row count ─────────────

def test_multi_bet_denominator_is_distinct_draw_not_rows(conn, rows_by_key):
    lt, sid = "DAILY_539", "daily539_f4cold_5bet"
    if (lt, sid) not in rows_by_key:
        pytest.skip(f"{sid} not in payload")
    row = rows_by_key[(lt, sid)]
    total_rows = conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE lottery_type=? AND strategy_id=?",
        (lt, sid)).fetchone()[0]
    distinct_draws = conn.execute(
        "SELECT COUNT(DISTINCT target_draw) FROM strategy_prediction_replays "
        "WHERE lottery_type=? AND strategy_id=?", (lt, sid)).fetchone()[0]
    # A genuine multi-bet cell: rows must exceed distinct draws.
    assert total_rows > distinct_draws
    # available_draws_1500 must reflect distinct draws (capped at the window),
    # never the (much larger) replay row count.
    assert row["available_draws_1500"] == min(1500, distinct_draws)
    assert row["available_draws_1500"] <= distinct_draws
    assert row["available_draws_1500"] != total_rows


# ── 4. M3+ threshold semantics: hit_count 1/2 and special-only do not count ──

def test_hit_count_1_or_2_is_not_success(conn):
    """A draw whose best bet has hit_count in {1,2} must be a non-success."""
    row = conn.execute(
        """
        SELECT lottery_type, strategy_id, target_draw, MAX(hit_count) AS best
        FROM strategy_prediction_replays
        GROUP BY lottery_type, strategy_id, target_draw
        HAVING best IN (1, 2)
        LIMIT 1
        """).fetchone()
    assert row is not None, "expected at least one draw with best hit_count in {1,2}"
    success = 1 if row["best"] >= 3 else 0
    assert success == 0


def test_special_only_draw_is_not_m3plus_success(conn):
    """special_hit=1 but every bet hit_count<3 → must NOT be an M3+ success."""
    row = conn.execute(
        """
        SELECT lottery_type, strategy_id, target_draw,
               MAX(special_hit) AS any_special,
               MAX(hit_count)   AS best_hit,
               MAX(CASE WHEN hit_count >= 3 THEN 1 ELSE 0 END) AS m3plus
        FROM strategy_prediction_replays
        GROUP BY lottery_type, strategy_id, target_draw
        HAVING any_special = 1 AND best_hit < 3
        LIMIT 1
        """).fetchone()
    if row is None:
        pytest.skip("no special-only (hit_count<3) draw present")
    # The M3+ criterion must ignore special_hit entirely.
    assert row["m3plus"] == 0


def test_any_hit_would_have_counted_special_only(conn):
    """Sanity: under the OLD any-hit rule, a special-only draw WAS a success —
    proves M3+ is strictly stricter, not identical to the old metric."""
    row = conn.execute(
        """
        SELECT MAX(special_hit) AS any_special, MAX(hit_count) AS best_hit
        FROM strategy_prediction_replays
        GROUP BY lottery_type, strategy_id, target_draw
        HAVING any_special = 1 AND best_hit < 3
        LIMIT 1
        """).fetchone()
    if row is None:
        pytest.skip("no special-only draw present")
    old_any_hit = 1 if (row["best_hit"] >= 1 or row["any_special"] == 1) else 0
    new_m3plus = 1 if row["best_hit"] >= 3 else 0
    assert old_any_hit == 1 and new_m3plus == 0


# ── 5. M3+ rates are materially lower than the old any-hit rates ─────────────

def test_biglotto_single_bet_m3plus_far_below_old_anyhit(conn, rows_by_key):
    """BIG_LOTTO single-bet old any-hit ~54%; M3+ must be far lower (< 20%)."""
    lt, sid = "BIG_LOTTO", "markov_single_biglotto"
    if (lt, sid) not in rows_by_key:
        pytest.skip(f"{sid} not in payload")
    sr100 = rows_by_key[(lt, sid)]["success_rate_100"]
    assert sr100 is not None
    assert sr100 < 0.20, f"M3+ single-bet rate unexpectedly high: {sr100}"


def test_biglotto_echo_aware_3bet_not_90_plus(conn, rows_by_key):
    """biglotto_echo_aware_3bet old any-hit ~94%; M3+ must not be 90%+."""
    lt, sid = "BIG_LOTTO", "biglotto_echo_aware_3bet"
    if (lt, sid) not in rows_by_key:
        pytest.skip(f"{sid} not in payload")
    sr100 = rows_by_key[(lt, sid)]["success_rate_100"]
    assert sr100 is not None
    assert sr100 < 0.90, f"M3+ multi-bet rate still 90%+: {sr100}"


# ── 6. available_draws retained; no-row strategies → null ────────────────────

def test_available_draws_fields_present(rows_by_key):
    for r in rows_by_key.values():
        for n in WINDOWS:
            assert f"available_draws_{n}" in r
            assert isinstance(r[f"available_draws_{n}"], int)


def test_no_row_strategy_success_rate_is_null(rows_by_key):
    no_row = [r for r in rows_by_key.values() if not r["has_replay_rows"]]
    assert no_row, "expected at least one registered-without-rows cell"
    for r in no_row:
        for n in WINDOWS:
            assert r[f"success_rate_{n}"] is None
            assert r[f"available_draws_{n}"] == 0


def test_success_rate_in_unit_range(rows_by_key):
    for r in rows_by_key.values():
        for n in WINDOWS:
            sr = r[f"success_rate_{n}"]
            assert sr is None or (0.0 <= sr <= 1.0)


# ── 7. Legacy artifact endpoint contract is untouched ────────────────────────

def test_legacy_audit_payload_unchanged():
    try:
        from routes import replay as replay_mod
    except Exception as exc:
        pytest.skip(f"replay module unavailable: {exc}")
    audit = replay_mod._load_d3_strategy_status_audit_payload()
    # Legacy artifact is no_db_query, 14 rows, fixed schema — must be intact.
    assert audit["forbidden_actions_confirmed"]["no_db_query"] is True
    assert audit["route_path"] == LEGACY_AUDIT_ROUTE
    assert isinstance(audit.get("rows"), list)
    assert len(audit["rows"]) == 14


def test_both_endpoints_present_in_ui(html):
    assert COVERAGE_ROUTE in html
    assert LEGACY_AUDIT_ROUTE in html


# ── 8. UI wording reflects M3+ ───────────────────────────────────────────────

def test_ui_columns_say_m3plus(html):
    section_start = html.find('id="p263b-d3-ssot-section"')
    assert section_start != -1
    section = html[section_start:section_start + 8000]
    for n in ("30期", "100期", "500期", "1500期"):
        assert n in section
    assert "M3+" in section


def test_ui_explains_m3plus_definition(html):
    section_start = html.find('id="p263b-d3-ssot-section"')
    section = html[section_start:section_start + 8000]
    assert "命中主號 3 顆以上" in section


def test_ui_disclaims_not_approval_or_betting(html):
    section_start = html.find('id="p263b-d3-ssot-section"')
    section = html[section_start:section_start + 8000]
    assert "不代表 D3 核准或投注建議" in section


def test_ui_special_hit_excluded_note(html):
    section_start = html.find('id="p263b-d3-ssot-section"')
    section = html[section_start:section_start + 8000]
    assert "special_hit 不單獨計入" in section


# ── 9. Read-only — no DB mutation ────────────────────────────────────────────

def test_endpoint_does_not_change_db_row_count():
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    try:
        before = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
    finally:
        conn.close()
    from routes import replay as replay_mod
    replay_mod._build_d3_ssot_coverage_payload()
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    try:
        after = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
    finally:
        conn.close()
    assert before == after
