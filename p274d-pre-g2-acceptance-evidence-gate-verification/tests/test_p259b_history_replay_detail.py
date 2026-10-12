"""P259B — Tests for GET /api/replay/history-detail (paginated per-draw replay).

Validates: server-side pagination (default page=1/page_size=100, max 200, never
returns all rows), total_count/has_next correctness, sort target_draw asc/desc,
hit_filter all/hit/miss, exact target_draw search, lottery_type+strategy_id
isolation, bet_index (P259A-consistent strategy-level), result_label derivation,
overview API still has NO per-draw detail, and read-only safety guarantees.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


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


@pytest.fixture(scope="module")
def sample(client):
    """Discover a real strategy that has production replay rows.

    Returns dict with lottery_type, strategy_id, bet_index (derived count),
    and total_replay_rows — robust against DB content changes.
    """
    ov = client.get("/api/replay/history-overview?bet_index=0").json()
    candidates = [
        r for r in ov.get("rows", [])
        if r.get("has_production_replay") and r.get("total_replay_rows", 0) > 100
    ]
    if not candidates:
        pytest.skip("No strategy with >100 replay rows found in DB")
    # Prefer the one with the most rows for stable pagination tests
    candidates.sort(key=lambda r: r["total_replay_rows"], reverse=True)
    c = candidates[0]
    return {
        "lottery_type": c["lottery_type"],
        "strategy_id": c["strategy_id"],
        "bet_index": c["derived_bet_count"],
        "total_replay_rows": c["total_replay_rows"],
    }


def _detail_url(s, **kw):
    base = (
        f"/api/replay/history-detail?lottery_type={s['lottery_type']}"
        f"&strategy_id={s['strategy_id']}&bet_index={s['bet_index']}"
    )
    for k, v in kw.items():
        base += f"&{k}={v}"
    return base


# ---------------------------------------------------------------------------
# 1. Helper unit tests (no HTTP)
# ---------------------------------------------------------------------------

def _import_helpers():
    lottery_api_dir = str(REPO_ROOT / "lottery_api")
    if lottery_api_dir not in sys.path:
        sys.path.insert(0, lottery_api_dir)
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from routes.replay import _parse_numbers_field, _detail_result_label
    return _parse_numbers_field, _detail_result_label


def test_parse_numbers_field():
    parse, _ = _import_helpers()
    assert parse("[1, 7, 15]") == [1, 7, 15]
    assert parse(None) == []
    assert parse("") == []
    assert parse([2, 3]) == [2, 3]
    assert parse("not-json") == ["not-json"]


def test_result_label_derivation_unit():
    _, label = _import_helpers()
    assert label(0, 0) == "未命中"
    assert label(0, 1) == "未命中＋特別號"
    assert label(3, 0) == "命中 3 碼"
    assert label(2, 1) == "命中 2 碼＋特別號"
    assert label(None, 0) == "未命中"


# ---------------------------------------------------------------------------
# 2. Basic 200 + structure
# ---------------------------------------------------------------------------

def test_detail_endpoint_200(client, sample):
    r = client.get(_detail_url(sample))
    assert r.status_code == 200, f"got {r.status_code}: {r.text[:300]}"


def test_detail_required_top_fields(client, sample):
    data = client.get(_detail_url(sample)).json()
    for f in ["lottery_type", "strategy_id", "bet_index", "derived_bet_count",
              "bet_index_matches_strategy", "page", "page_size", "total_count",
              "has_next", "sort", "hit_filter", "rows", "summary",
              "paginated", "server_side_pagination", "no_full_load",
              "no_db_write", "no_replay_backfill", "no_strategy_adapter_changes"]:
        assert f in data, f"missing top-level field: {f}"


# ---------------------------------------------------------------------------
# 3. Pagination defaults + limits
# ---------------------------------------------------------------------------

def test_default_page_and_page_size(client, sample):
    data = client.get(_detail_url(sample)).json()
    assert data["page"] == 1
    assert data["page_size"] == 100


def test_page_size_max_200_ok(client, sample):
    r = client.get(_detail_url(sample, page_size=200))
    assert r.status_code == 200
    assert r.json()["page_size"] == 200


def test_page_size_over_1500_rejected(client, sample):
    # P260A raised the limit from 200 to 1500; 1501 must still be rejected.
    r = client.get(_detail_url(sample, page_size=1501))
    assert r.status_code == 422


def test_page_zero_rejected(client, sample):
    r = client.get(_detail_url(sample, page=0))
    assert r.status_code == 422


def test_page_size_zero_rejected(client, sample):
    r = client.get(_detail_url(sample, page_size=0))
    assert r.status_code == 422


def test_pagination_does_not_return_all_rows(client, sample):
    # With a small page_size, returned rows must be capped at page_size,
    # NOT the full result set.
    data = client.get(_detail_url(sample, page_size=10)).json()
    assert data["total_count"] > 10, "fixture should have >10 rows"
    assert len(data["rows"]) == 10, "page must be capped at page_size"
    assert data["total_count"] == sample["total_replay_rows"]


def test_total_count_and_has_next_consistency(client, sample):
    data = client.get(_detail_url(sample, page=1, page_size=10)).json()
    total = data["total_count"]
    expected_has_next = (1 * 10) < total
    assert data["has_next"] == expected_has_next


def test_last_page_has_next_false(client, sample):
    total = client.get(_detail_url(sample, page_size=10)).json()["total_count"]
    import math
    last_page = math.ceil(total / 10)
    data = client.get(_detail_url(sample, page=last_page, page_size=10)).json()
    assert data["has_next"] is False


# ---------------------------------------------------------------------------
# 4. Sort
# ---------------------------------------------------------------------------

def test_sort_desc(client, sample):
    data = client.get(_detail_url(sample, sort="target_draw_desc", page_size=50)).json()
    draws = [int(r["target_draw"]) for r in data["rows"]]
    assert draws == sorted(draws, reverse=True), "target_draw_desc must be descending"


def test_sort_asc(client, sample):
    data = client.get(_detail_url(sample, sort="target_draw_asc", page_size=50)).json()
    draws = [int(r["target_draw"]) for r in data["rows"]]
    assert draws == sorted(draws), "target_draw_asc must be ascending"


def test_invalid_sort_400(client, sample):
    r = client.get(_detail_url(sample, sort="bogus"))
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# 5. hit_filter
# ---------------------------------------------------------------------------

def test_hit_filter_hit(client, sample):
    data = client.get(_detail_url(sample, hit_filter="hit", page_size=100)).json()
    for r in data["rows"]:
        assert r["hit_count"] > 0, "hit filter must only return hit_count>0"


def test_hit_filter_miss(client, sample):
    data = client.get(_detail_url(sample, hit_filter="miss", page_size=100)).json()
    for r in data["rows"]:
        assert r["hit_count"] == 0, "miss filter must only return hit_count=0"


def test_hit_filter_all_is_superset(client, sample):
    all_total = client.get(_detail_url(sample, hit_filter="all")).json()["total_count"]
    hit_total = client.get(_detail_url(sample, hit_filter="hit")).json()["total_count"]
    miss_total = client.get(_detail_url(sample, hit_filter="miss")).json()["total_count"]
    assert all_total == hit_total + miss_total


def test_invalid_hit_filter_400(client, sample):
    r = client.get(_detail_url(sample, hit_filter="bogus"))
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# 6. target_draw exact search
# ---------------------------------------------------------------------------

def test_target_draw_exact_search(client, sample):
    # Grab a real target_draw from page 1, then search for it exactly.
    first = client.get(_detail_url(sample, page_size=5)).json()
    if not first["rows"]:
        pytest.skip("no rows to search")
    td = first["rows"][0]["target_draw"]
    data = client.get(_detail_url(sample, target_draw=td)).json()
    assert data["total_count"] >= 1
    for r in data["rows"]:
        assert r["target_draw"] == td


def test_target_draw_nonexistent_returns_empty(client, sample):
    data = client.get(_detail_url(sample, target_draw="000000000")).json()
    assert data["total_count"] == 0
    assert data["rows"] == []


# ---------------------------------------------------------------------------
# 7. Isolation: lottery_type + strategy_id
# ---------------------------------------------------------------------------

def test_isolation_lottery_and_strategy(client, sample):
    data = client.get(_detail_url(sample, page_size=100)).json()
    for r in data["rows"]:
        assert r["lottery_type"] == sample["lottery_type"]
        assert r["strategy_id"] == sample["strategy_id"]


def test_bet_index_matches_strategy(client, sample):
    data = client.get(_detail_url(sample)).json()
    assert data["derived_bet_count"] == sample["bet_index"]
    assert data["bet_index_matches_strategy"] is True


def test_wrong_strategy_returns_no_other_strategy_rows(client, sample):
    # A nonexistent strategy id must return zero rows (clean isolation).
    url = (
        f"/api/replay/history-detail?lottery_type={sample['lottery_type']}"
        f"&strategy_id=__nonexistent_strategy__&bet_index=1"
    )
    data = client.get(url).json()
    assert data["total_count"] == 0
    assert data["rows"] == []


# ---------------------------------------------------------------------------
# 8. Row schema + result_label
# ---------------------------------------------------------------------------

def test_detail_row_schema(client, sample):
    data = client.get(_detail_url(sample, page_size=20)).json()
    required = ["lottery_type", "strategy_id", "strategy_name", "bet_index",
               "target_draw", "draw_date", "predicted_numbers", "actual_numbers",
               "hit_count", "hit_numbers", "special_hit", "result_label",
               "replay_created_at"]
    for r in data["rows"]:
        for f in required:
            assert f in r, f"detail row missing field: {f}"
        assert isinstance(r["predicted_numbers"], list)
        assert isinstance(r["actual_numbers"], list)
        assert r["bet_index"] == sample["bet_index"]


def test_result_label_consistent_with_hit_count(client, sample):
    data = client.get(_detail_url(sample, page_size=100)).json()
    for r in data["rows"]:
        if r["hit_count"] == 0:
            assert "未命中" in r["result_label"]
        else:
            assert f"命中 {r['hit_count']} 碼" in r["result_label"]


# ---------------------------------------------------------------------------
# 9. Summary
# ---------------------------------------------------------------------------

def test_summary_fields(client, sample):
    s = client.get(_detail_url(sample)).json()["summary"]
    for f in ["total_replay_rows", "total_hit_rows", "hit_rate",
              "first_target_draw", "last_target_draw", "latest_target_draw",
              "current_filters"]:
        assert f in s
    assert s["total_replay_rows"] == sample["total_replay_rows"]
    assert 0.0 <= s["hit_rate"] <= 1.0


# ---------------------------------------------------------------------------
# 10. Safety guarantees
# ---------------------------------------------------------------------------

def test_safety_flags(client, sample):
    data = client.get(_detail_url(sample)).json()
    assert data["paginated"] is True
    assert data["server_side_pagination"] is True
    assert data["no_full_load"] is True
    assert data["no_db_write"] is True
    assert data["no_replay_backfill"] is True
    assert data["no_strategy_adapter_changes"] is True


# ---------------------------------------------------------------------------
# 11. Overview API must NOT carry per-draw detail (regression guard)
# ---------------------------------------------------------------------------

def test_overview_has_no_per_draw_detail(client):
    data = client.get("/api/replay/history-overview?bet_index=0").json()
    assert data["no_large_per_draw_detail"] is True
    for row in data["rows"]:
        assert "predicted_numbers" not in row
        assert "actual_numbers" not in row
        assert "hit_numbers" not in row


# ---------------------------------------------------------------------------
# 12. HTML UI
# ---------------------------------------------------------------------------

def _html():
    return (REPO_ROOT / "index.html").read_text(encoding="utf-8")


def test_html_detail_panel_present():
    assert 'id="p259b-detail-panel"' in _html()


def test_html_detail_table_present():
    assert 'id="p259b-detail-table"' in _html()
    assert 'id="p259b-detail-tbody"' in _html()


def test_html_detail_controls_present():
    h = _html()
    assert 'id="p259b-hit-filter"' in h
    assert 'id="p259b-sort"' in h
    assert 'id="p259b-target-draw"' in h
    assert 'id="p259b-search-btn"' in h


def test_html_pagination_controls_present():
    h = _html()
    assert 'id="p259b-prev-btn"' in h
    assert 'id="p259b-next-btn"' in h
    assert 'id="p259b-page-info"' in h


def test_html_summary_card_present():
    assert 'id="p259b-summary-card"' in _html()


def test_html_detail_button_enabled_class():
    # The 查看明細 button is now wired with a clickable class
    assert "p259b-detail-btn" in _html()


def test_html_detail_default_page_size_100_mentioned():
    # The UI copy states server-side pagination + default 100 per page
    h = _html()
    assert "每頁 100" in h or "page_size: 100" in h or "page_size=100" in h


def test_html_p259b_notice_updated():
    # The stale "尚未開放" wording must be replaced
    h = _html()
    assert "尚未開放" not in h
    assert "明細頁已實作" in h


def test_html_detail_fetch_no_write_method():
    # P259B JS block must not contain DB-write / POST / backfill verbs
    import re
    h = _html()
    start = h.find("P259B: History Replay Detail JS")
    end = h.find("</script>", start)
    if start == -1:
        pytest.skip("P259B JS block not found")
    js = h[start:end]
    for term in ["method: 'POST'", "method:\"POST\"", "INSERT", "UPDATE ", "DELETE", "backfill"]:
        assert term.lower() not in js.lower(), f"forbidden term in P259B JS: {term}"
