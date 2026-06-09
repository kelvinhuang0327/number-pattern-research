"""P261A — Tests for Replay Detail Row Expand (multi-bet inline detail).

Validates:
- NEW read-only endpoint GET /api/replay/history-detail-grouped:
  * groups by distinct target_draw — one row per draw, nested bets[]
  * server-side pagination over DRAWS (page_size max 1500, never loads all)
  * multi-bet strategy returns all bets per draw (第 1 注 … 第 N 注)
  * single-bet strategy returns exactly one bet per draw
  * draw-level hit_filter (all / hit / miss) with hit+miss==all
  * sort asc/desc, exact target_draw search, lottery+strategy isolation
  * read-only safety flags; no DB write
- EXISTING GET /api/replay/history-detail contract unchanged (regression)
- index.html main detail table: 命中數 column REMOVED, 明細 (expand) column ADDED,
  still 7 columns; expand control + per-bet panel + toggle present
- 命中數 lives in the expand panel (per-bet table)
- P260C token style preserved (white / green / purple); quick range 100/300/500/1500,
  1000 absent
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
HTML_PATH = REPO_ROOT / "index.html"


def _html() -> str:
    return HTML_PATH.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def client():
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


def _overview_rows(client):
    return client.get("/api/replay/history-overview?bet_index=0").json().get("rows", [])


@pytest.fixture(scope="module")
def multibet_sample(client):
    """Discover a strategy with >1 declared bet and production replay rows."""
    cands = [
        r for r in _overview_rows(client)
        if r.get("has_production_replay")
        and r.get("derived_bet_count", 1) >= 2
        and r.get("total_replay_rows", 0) > 10
    ]
    if not cands:
        pytest.skip("No multi-bet strategy with replay rows found in DB")
    cands.sort(key=lambda r: r["total_replay_rows"], reverse=True)
    c = cands[0]
    return {
        "lottery_type": c["lottery_type"],
        "strategy_id": c["strategy_id"],
        "bet_index": c["derived_bet_count"],
        "derived_bet_count": c["derived_bet_count"],
    }


@pytest.fixture(scope="module")
def singlebet_sample(client):
    """Discover a single-bet strategy with production replay rows."""
    cands = [
        r for r in _overview_rows(client)
        if r.get("has_production_replay")
        and r.get("derived_bet_count", 1) == 1
        and r.get("total_replay_rows", 0) > 10
    ]
    if not cands:
        pytest.skip("No single-bet strategy with replay rows found in DB")
    cands.sort(key=lambda r: r["total_replay_rows"], reverse=True)
    c = cands[0]
    return {"lottery_type": c["lottery_type"], "strategy_id": c["strategy_id"]}


def _grouped_url(s, **kw):
    base = (
        f"/api/replay/history-detail-grouped?lottery_type={s['lottery_type']}"
        f"&strategy_id={s['strategy_id']}"
    )
    for k, v in kw.items():
        base += f"&{k}={v}"
    return base


# ---------------------------------------------------------------------------
# 1. Grouped endpoint: basic structure
# ---------------------------------------------------------------------------

def test_grouped_200(client, multibet_sample):
    r = client.get(_grouped_url(multibet_sample))
    assert r.status_code == 200, f"got {r.status_code}: {r.text[:300]}"


def test_grouped_top_fields(client, multibet_sample):
    d = client.get(_grouped_url(multibet_sample)).json()
    for f in ["lottery_type", "strategy_id", "bet_index", "derived_bet_count",
              "bet_index_matches_strategy", "grouped", "page", "page_size",
              "total_count", "has_next", "sort", "hit_filter", "rows", "summary",
              "paginated", "server_side_pagination", "no_full_load",
              "no_db_write", "no_replay_backfill", "no_strategy_adapter_changes"]:
        assert f in d, f"missing top-level field: {f}"
    assert d["grouped"] is True


def test_grouped_default_page_size(client, multibet_sample):
    d = client.get(_grouped_url(multibet_sample)).json()
    assert d["page"] == 1
    assert d["page_size"] == 100


def test_grouped_row_schema(client, multibet_sample):
    d = client.get(_grouped_url(multibet_sample, page_size=5)).json()
    assert d["rows"], "fixture should return rows"
    for row in d["rows"]:
        for f in ["target_draw", "draw_date", "n_bets", "actual_numbers",
                  "predicted_numbers", "hit_numbers", "bets", "any_hit",
                  "max_hit_count"]:
            assert f in row, f"draw row missing field: {f}"
        assert isinstance(row["bets"], list)
        assert isinstance(row["predicted_numbers"], list)
        assert isinstance(row["hit_numbers"], list)


def test_grouped_bet_schema(client, multibet_sample):
    d = client.get(_grouped_url(multibet_sample, page_size=5)).json()
    for row in d["rows"]:
        for b in row["bets"]:
            for f in ["bet_index", "predicted_numbers", "actual_numbers",
                      "hit_numbers", "hit_count", "special_hit", "result_label"]:
                assert f in b, f"bet missing field: {f}"
            assert isinstance(b["predicted_numbers"], list)
            assert isinstance(b["actual_numbers"], list)
            assert isinstance(b["hit_numbers"], list)


# ---------------------------------------------------------------------------
# 2. Multi-bet grouping correctness
# ---------------------------------------------------------------------------

def test_multibet_row_has_all_bets(client, multibet_sample):
    n = multibet_sample["derived_bet_count"]
    d = client.get(_grouped_url(multibet_sample, page_size=20)).json()
    # At least one draw must expose the full declared bet set.
    full = [row for row in d["rows"] if row["n_bets"] >= n]
    assert full, f"expected a draw with >= {n} bets"
    row = full[0]
    assert len(row["bets"]) == row["n_bets"]
    bet_idxs = sorted(b["bet_index"] for b in row["bets"])
    assert bet_idxs == list(range(1, row["n_bets"] + 1)), \
        f"bet_index sequence must be 1..{row['n_bets']}, got {bet_idxs}"


def test_multibet_bets_distinct_index(client, multibet_sample):
    d = client.get(_grouped_url(multibet_sample, page_size=20)).json()
    for row in d["rows"]:
        idxs = [b["bet_index"] for b in row["bets"]]
        assert len(idxs) == len(set(idxs)), "bet_index values must be distinct within a draw"


def test_singlebet_one_bet_per_draw(client, singlebet_sample):
    d = client.get(_grouped_url(singlebet_sample, page_size=10)).json()
    assert d["rows"], "single-bet fixture should return rows"
    for row in d["rows"]:
        assert row["n_bets"] == 1, "single-bet strategy must have exactly 1 bet per draw"
        assert len(row["bets"]) == 1
        assert row["bets"][0]["bet_index"] == 1


# ---------------------------------------------------------------------------
# 3. Pagination is over DRAWS, server-side
# ---------------------------------------------------------------------------

def test_grouped_pagination_caps_draws(client, multibet_sample):
    d = client.get(_grouped_url(multibet_sample, page_size=10)).json()
    assert d["total_count"] > 10, "fixture should have >10 draws"
    assert len(d["rows"]) == 10, "page must be capped at page_size draws"


def test_grouped_total_count_equals_distinct_draws(client, multibet_sample):
    d = client.get(_grouped_url(multibet_sample)).json()
    assert d["total_count"] == d["summary"]["total_draws"], \
        "total_count must equal distinct draws when hit_filter=all"


def test_grouped_total_count_less_than_rowcount_for_multibet(client, multibet_sample):
    """Distinct draws must be strictly fewer than total bet-rows for a multi-bet
    strategy — proving grouping actually collapses bets into one row per draw."""
    d = client.get(_grouped_url(multibet_sample)).json()
    s = d["summary"]
    assert s["total_draws"] < s["total_replay_rows"], \
        "multi-bet grouping must collapse multiple bet-rows into fewer draws"


def test_grouped_page_size_1500_ok(client, multibet_sample):
    r = client.get(_grouped_url(multibet_sample, page_size=1500))
    assert r.status_code == 200
    assert r.json()["page_size"] == 1500


def test_grouped_page_size_1501_rejected(client, multibet_sample):
    r = client.get(_grouped_url(multibet_sample, page_size=1501))
    assert r.status_code == 422


def test_grouped_page_zero_rejected(client, multibet_sample):
    assert client.get(_grouped_url(multibet_sample, page=0)).status_code == 422


def test_grouped_has_next_consistency(client, multibet_sample):
    d = client.get(_grouped_url(multibet_sample, page=1, page_size=10)).json()
    assert d["has_next"] == (10 < d["total_count"])


def test_grouped_last_page_has_next_false(client, multibet_sample):
    total = client.get(_grouped_url(multibet_sample, page_size=10)).json()["total_count"]
    last = math.ceil(total / 10)
    d = client.get(_grouped_url(multibet_sample, page=last, page_size=10)).json()
    assert d["has_next"] is False


# ---------------------------------------------------------------------------
# 4. Draw-level hit_filter
# ---------------------------------------------------------------------------

def test_grouped_hit_filter_partition(client, multibet_sample):
    allc = client.get(_grouped_url(multibet_sample, hit_filter="all")).json()["total_count"]
    hitc = client.get(_grouped_url(multibet_sample, hit_filter="hit")).json()["total_count"]
    missc = client.get(_grouped_url(multibet_sample, hit_filter="miss")).json()["total_count"]
    assert allc == hitc + missc, "hit + miss draws must partition all draws"


def test_grouped_hit_filter_hit_has_a_hit(client, multibet_sample):
    d = client.get(_grouped_url(multibet_sample, hit_filter="hit", page_size=50)).json()
    for row in d["rows"]:
        assert row["max_hit_count"] > 0 or any(b["hit_count"] > 0 for b in row["bets"]), \
            "hit-filtered draw must have at least one bet with a hit"


def test_grouped_hit_filter_miss_no_hits(client, multibet_sample):
    d = client.get(_grouped_url(multibet_sample, hit_filter="miss", page_size=50)).json()
    for row in d["rows"]:
        assert row["max_hit_count"] == 0
        assert all(b["hit_count"] == 0 for b in row["bets"])


def test_grouped_invalid_hit_filter_400(client, multibet_sample):
    assert client.get(_grouped_url(multibet_sample, hit_filter="bogus")).status_code == 400


def test_grouped_invalid_sort_400(client, multibet_sample):
    assert client.get(_grouped_url(multibet_sample, sort="bogus")).status_code == 400


# ---------------------------------------------------------------------------
# 5. Sort, search, isolation
# ---------------------------------------------------------------------------

def test_grouped_sort_desc(client, multibet_sample):
    d = client.get(_grouped_url(multibet_sample, sort="target_draw_desc", page_size=30)).json()
    draws = [int(r["target_draw"]) for r in d["rows"]]
    assert draws == sorted(draws, reverse=True)


def test_grouped_sort_asc(client, multibet_sample):
    d = client.get(_grouped_url(multibet_sample, sort="target_draw_asc", page_size=30)).json()
    draws = [int(r["target_draw"]) for r in d["rows"]]
    assert draws == sorted(draws)


def test_grouped_target_draw_exact(client, multibet_sample):
    first = client.get(_grouped_url(multibet_sample, page_size=3)).json()
    if not first["rows"]:
        pytest.skip("no rows to search")
    td = first["rows"][0]["target_draw"]
    d = client.get(_grouped_url(multibet_sample, target_draw=td)).json()
    assert d["total_count"] == 1
    assert d["rows"][0]["target_draw"] == td


def test_grouped_target_draw_nonexistent_empty(client, multibet_sample):
    d = client.get(_grouped_url(multibet_sample, target_draw="000000000")).json()
    assert d["total_count"] == 0
    assert d["rows"] == []


def test_grouped_isolation(client, multibet_sample):
    d = client.get(_grouped_url(multibet_sample, page_size=30)).json()
    for row in d["rows"]:
        assert row["lottery_type"] == multibet_sample["lottery_type"]
        assert row["strategy_id"] == multibet_sample["strategy_id"]


def test_grouped_nonexistent_strategy_empty(client, multibet_sample):
    url = (
        f"/api/replay/history-detail-grouped?lottery_type={multibet_sample['lottery_type']}"
        f"&strategy_id=__nope__"
    )
    d = client.get(url).json()
    assert d["total_count"] == 0
    assert d["rows"] == []


# ---------------------------------------------------------------------------
# 6. Safety flags + bet_index confirmatory semantics
# ---------------------------------------------------------------------------

def test_grouped_safety_flags(client, multibet_sample):
    d = client.get(_grouped_url(multibet_sample)).json()
    assert d["paginated"] is True
    assert d["server_side_pagination"] is True
    assert d["no_full_load"] is True
    assert d["no_db_write"] is True
    assert d["no_replay_backfill"] is True
    assert d["no_strategy_adapter_changes"] is True


def test_grouped_bet_index_param_is_confirmatory(client, multibet_sample):
    """bet_index param must NOT filter — same draw count regardless of value."""
    n = multibet_sample["derived_bet_count"]
    c1 = client.get(_grouped_url(multibet_sample, bet_index=1)).json()
    c2 = client.get(_grouped_url(multibet_sample, bet_index=n)).json()
    assert c1["total_count"] == c2["total_count"], \
        "grouped view must return all draws regardless of bet_index param"
    # and rows still carry the full bet set
    if c1["rows"]:
        assert c1["rows"][0]["bets"] == c2["rows"][0]["bets"]


# ---------------------------------------------------------------------------
# 7. Existing history-detail contract unchanged (regression)
# ---------------------------------------------------------------------------

def test_history_detail_still_row_per_bet(client, multibet_sample):
    """The legacy /history-detail must still return total_count == all bet-rows."""
    base = (
        f"/api/replay/history-detail?lottery_type={multibet_sample['lottery_type']}"
        f"&strategy_id={multibet_sample['strategy_id']}"
        f"&bet_index={multibet_sample['bet_index']}"
    )
    legacy = client.get(base + "&page_size=10").json()
    grouped = client.get(_grouped_url(multibet_sample, page_size=10)).json()
    # legacy counts bet-rows; grouped counts draws — legacy must be larger for multi-bet
    assert legacy["total_count"] > grouped["total_count"], \
        "legacy history-detail must still count bet-rows (more than grouped draws)"
    assert "grouped" not in legacy, "legacy endpoint must not carry grouped marker"


def test_history_detail_page_size_1500_still_ok(client, multibet_sample):
    base = (
        f"/api/replay/history-detail?lottery_type={multibet_sample['lottery_type']}"
        f"&strategy_id={multibet_sample['strategy_id']}"
        f"&bet_index={multibet_sample['bet_index']}&page_size=1500"
    )
    assert client.get(base).status_code == 200


# ---------------------------------------------------------------------------
# 8. HTML — main table column change (命中數 removed, 明細 added)
# ---------------------------------------------------------------------------

def _thead() -> str:
    html = _html()
    start = html.find('id="p259b-detail-table"')
    assert start != -1, "p259b-detail-table not found"
    ts = html.find("<thead>", start)
    te = html.find("</thead>", ts)
    return html[ts:te]


def test_main_table_still_seven_columns():
    assert _thead().count("<th>") == 7


def test_main_table_no_hit_count_column():
    """P261A: 命中數 must NOT be a main-table column header."""
    assert "命中數" not in _thead()


def test_main_table_has_detail_column():
    assert "明細" in _thead()


def test_main_table_core_columns_present():
    th = _thead()
    for col in ["期號", "日期", "策略", "預測號碼", "實際開獎", "命中號碼"]:
        assert col in th, f"missing main-table column: {col}"


# ---------------------------------------------------------------------------
# 9. HTML/JS — expand control + per-bet panel
# ---------------------------------------------------------------------------

def test_expand_button_class_present():
    assert "p261a-expand-btn" in _html()


def test_expand_button_label_present():
    html = _html()
    assert "展開" in html and "收起" in html


def test_render_bet_detail_panel_function():
    assert "function renderBetDetailPanel(" in _html()


def test_toggle_bet_detail_function():
    assert "function toggleBetDetail(" in _html()


def test_bet_detail_row_class_present():
    assert "p261a-bet-detail-row" in _html()


def test_panel_renders_per_bet_label():
    """Expand panel labels each bet 第 N 注."""
    html = _html()
    assert "第 ' + b.bet_index + ' 注" in html or "第 " in html and "b.bet_index" in html


def test_panel_uses_bet_fields():
    html = _html()
    for ref in ["b.predicted_numbers", "b.actual_numbers", "b.hit_numbers",
                "b.hit_count", "b.bet_index"]:
        assert ref in html, f"expand panel must use {ref}"


def test_hit_count_in_expand_panel():
    """命中數 (hit_count) must be rendered in the per-bet expand panel."""
    html = _html()
    assert "p261a-bet-hitcount" in html
    assert "b.hit_count" in html


def test_loaddetail_uses_grouped_endpoint():
    assert "/api/replay/history-detail-grouped" in _html()


def test_expand_handler_wired():
    html = _html()
    assert "p261a-expand-btn" in html
    assert "toggleBetDetail(" in html


# ---------------------------------------------------------------------------
# 10. P260C token style regression + quick range
# ---------------------------------------------------------------------------

def test_token_classes_preserved():
    html = _html()
    for cls in [".replay-number-token", ".replay-number-token--hit",
                ".replay-number-token--special", ".replay-number-token--special-hit",
                ".replay-row--hit"]:
        assert cls in html, f"token CSS missing: {cls}"


def test_token_white_green_purple_preserved():
    html = _html()
    assert "background:#ffffff" in html          # white base token
    assert "#28a745" in html                      # green hit
    assert "#6e40c9" in html                      # purple special
    assert "border-radius:50%" in html            # circular
    assert "border-radius:1000px" in html         # pill special


def test_panel_uses_token_helpers():
    html = _html()
    assert "fmtNumberTokens(" in html
    assert "fmtSpecialToken(" in html
    assert "fmtHitTokens(" in html


def test_quick_range_preserved():
    html = _html()
    for ps in ["p260a-range-100", "p260a-range-300", "p260a-range-500", "p260a-range-1500"]:
        assert f'data-testid="{ps}"' in html
    assert 'data-testid="p260a-range-1000"' not in html


def test_no_csv_export_added():
    """P261A scope guard: no CSV export wiring introduced in the detail panel JS."""
    html = _html()
    # crude guard: the P261A work must not add CSV/blob download verbs near the panel
    assert "text/csv" not in html.lower()
