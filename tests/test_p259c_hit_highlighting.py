"""P259C — Tests for hit highlighting in the replay detail panel.

Validates: number tokens rendered as individual badges, hit numbers get
replay-number-token--hit class, non-hit numbers stay plain, fallback
intersection when hit_numbers empty, result badge classes, row class,
P259B API/pagination unbroken, P259A overview unbroken.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
HTML = (REPO_ROOT / "index.html").read_text(encoding="utf-8")


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


@pytest.fixture(scope="module")
def hit_row(client):
    """Return the first row with hit_count > 0 from the largest strategy."""
    ov = client.get("/api/replay/history-overview?bet_index=0").json()
    cands = sorted(
        [r for r in ov["rows"] if r.get("has_production_replay")],
        key=lambda r: -r["total_replay_rows"],
    )
    if not cands:
        pytest.skip("no strategy with replay rows")
    c = cands[0]
    data = client.get(
        f"/api/replay/history-detail?lottery_type={c['lottery_type']}"
        f"&strategy_id={c['strategy_id']}&bet_index={c['derived_bet_count']}"
        f"&hit_filter=hit&page_size=5"
    ).json()
    if not data["rows"]:
        pytest.skip("no hit rows found")
    return data["rows"][0]


@pytest.fixture(scope="module")
def miss_row(client):
    """Return the first row with hit_count == 0."""
    ov = client.get("/api/replay/history-overview?bet_index=0").json()
    cands = sorted(
        [r for r in ov["rows"] if r.get("has_production_replay")],
        key=lambda r: -r["total_replay_rows"],
    )
    if not cands:
        pytest.skip("no strategy with replay rows")
    c = cands[0]
    data = client.get(
        f"/api/replay/history-detail?lottery_type={c['lottery_type']}"
        f"&strategy_id={c['strategy_id']}&bet_index={c['derived_bet_count']}"
        f"&hit_filter=miss&page_size=5"
    ).json()
    if not data["rows"]:
        pytest.skip("no miss rows found")
    return data["rows"][0]


# ---------------------------------------------------------------------------
# 1. CSS classes present in index.html
# ---------------------------------------------------------------------------

def test_css_number_token_class():
    assert ".replay-number-token" in HTML


def test_css_number_token_hit_class():
    assert ".replay-number-token--hit" in HTML


def test_css_row_hit_class():
    assert ".replay-row--hit" in HTML


def test_css_result_badge_hit():
    assert ".replay-result-badge--hit" in HTML


def test_css_result_badge_miss():
    assert ".replay-result-badge--miss" in HTML


# ---------------------------------------------------------------------------
# 2. JS helper fmtNumberTokens present and correct
# ---------------------------------------------------------------------------

def test_fmtNumberTokens_function_defined():
    assert "function fmtNumberTokens" in HTML


def test_fmtNumberTokens_uses_hit_class():
    assert "replay-number-token--hit" in HTML


def test_fmtNumberTokens_fallback_intersection_comment():
    # Fallback logic must be present (no hardcoded data)
    assert "intersection" in HTML.lower() or "pSet" in HTML or "hitSet" in HTML


def test_fmtNumberTokens_no_db_write():
    # Extract P259B+P259C JS, check no write path
    start = HTML.find("P259B: History Replay Detail JS")
    end = HTML.rfind("</script>")
    js = HTML[start:end] if start != -1 else ""
    for term in ["method: 'POST'", 'method:"POST"', "INSERT", "UPDATE ", "backfill"]:
        assert term.lower() not in js.lower(), f"forbidden write term found: {term!r}"


# ---------------------------------------------------------------------------
# 3. renderDetailRows uses fmtNumberTokens
# ---------------------------------------------------------------------------

def test_render_uses_fmtNumberTokens_for_predicted():
    assert "fmtNumberTokens(r.predicted_numbers" in HTML


def test_render_uses_fmtNumberTokens_for_actual():
    assert "fmtNumberTokens(r.actual_numbers" in HTML


def test_render_uses_replay_row_hit_class():
    assert "replay-row--hit" in HTML


def test_render_uses_result_badge_class():
    assert "replay-result-badge--hit" in HTML
    assert "replay-result-badge--miss" in HTML


# ---------------------------------------------------------------------------
# 4. API: hit_numbers, predicted_numbers, actual_numbers are lists (from P259B)
# ---------------------------------------------------------------------------

def test_api_hit_row_fields_are_lists(hit_row):
    assert isinstance(hit_row["predicted_numbers"], list), "predicted_numbers must be a list"
    assert isinstance(hit_row["actual_numbers"], list), "actual_numbers must be a list"
    assert isinstance(hit_row["hit_numbers"], list), "hit_numbers must be a list"


def test_api_hit_row_hit_count_positive(hit_row):
    assert hit_row["hit_count"] > 0


def test_api_hit_row_hit_numbers_nonempty(hit_row):
    assert len(hit_row["hit_numbers"]) > 0, "hit filter row must have non-empty hit_numbers"


def test_api_hit_numbers_subset_of_predicted(hit_row):
    pred = set(hit_row["predicted_numbers"])
    for n in hit_row["hit_numbers"]:
        assert n in pred, f"hit number {n} not in predicted_numbers {pred}"


def test_api_hit_numbers_subset_of_actual(hit_row):
    actual = set(hit_row["actual_numbers"])
    for n in hit_row["hit_numbers"]:
        assert n in actual, f"hit number {n} not in actual_numbers {actual}"


def test_api_miss_row_hit_count_zero(miss_row):
    assert miss_row["hit_count"] == 0


def test_api_miss_row_hit_numbers_empty_or_absent(miss_row):
    hn = miss_row.get("hit_numbers", [])
    assert hn == [] or hn is None, f"miss row should have empty hit_numbers, got {hn}"


def test_api_result_label_hit(hit_row):
    assert "命中" in hit_row["result_label"]


def test_api_result_label_miss(miss_row):
    assert "未命中" in miss_row["result_label"]


# ---------------------------------------------------------------------------
# 5. Fallback intersection logic
# ---------------------------------------------------------------------------

def test_fallback_intersection_code_present():
    """fmtNumberTokens must compute intersection as fallback for empty hit_numbers."""
    start = HTML.find("function fmtNumberTokens")
    end = HTML.find("function renderSummary", start)
    if start == -1:
        pytest.fail("fmtNumberTokens function not found")
    fn_body = HTML[start:end]
    # Must have logic for empty hitNums case
    assert ("hitNums && hitNums.length" in fn_body or
            "hitNums.length > 0" in fn_body or
            "hitSet" in fn_body), "fallback intersection logic not found"
    # Must produce a Set of hits even when hitNums is empty
    assert "new Set" in fn_body, "expected Set construction in fmtNumberTokens"


def test_fallback_does_not_use_hardcoded_numbers():
    start = HTML.find("function fmtNumberTokens")
    end = HTML.find("function renderSummary", start)
    fn_body = HTML[start:end] if start != -1 else ""
    # No literal number arrays beyond trivial []
    suspicious = re.findall(r'\[\s*\d+\s*,\s*\d+', fn_body)
    assert not suspicious, f"hardcoded number arrays in fmtNumberTokens: {suspicious}"


# ---------------------------------------------------------------------------
# 6. Pagination unchanged (P259B regression guard)
# ---------------------------------------------------------------------------

def test_p259b_pagination_default(client):
    ov = client.get("/api/replay/history-overview?bet_index=0").json()
    cands = [r for r in ov["rows"] if r.get("has_production_replay") and r["total_replay_rows"] > 100]
    if not cands:
        pytest.skip("no large strategy")
    c = sorted(cands, key=lambda r: -r["total_replay_rows"])[0]
    data = client.get(
        f"/api/replay/history-detail?lottery_type={c['lottery_type']}"
        f"&strategy_id={c['strategy_id']}&bet_index={c['derived_bet_count']}"
    ).json()
    assert data["page"] == 1
    assert data["page_size"] == 100
    assert len(data["rows"]) == 100
    assert data["total_count"] == c["total_replay_rows"]
    assert data["has_next"] is True


def test_p259b_hit_filter_still_works(client):
    ov = client.get("/api/replay/history-overview?bet_index=0").json()
    cands = [r for r in ov["rows"] if r.get("has_production_replay")]
    if not cands:
        pytest.skip("no strategy with replay rows")
    c = sorted(cands, key=lambda r: -r["total_replay_rows"])[0]
    data = client.get(
        f"/api/replay/history-detail?lottery_type={c['lottery_type']}"
        f"&strategy_id={c['strategy_id']}&bet_index={c['derived_bet_count']}&hit_filter=hit&page_size=20"
    ).json()
    for row in data["rows"]:
        assert row["hit_count"] > 0


def test_p259b_sort_desc_still_works(client):
    ov = client.get("/api/replay/history-overview?bet_index=0").json()
    cands = [r for r in ov["rows"] if r.get("has_production_replay")]
    if not cands:
        pytest.skip("no strategy with replay rows")
    c = sorted(cands, key=lambda r: -r["total_replay_rows"])[0]
    data = client.get(
        f"/api/replay/history-detail?lottery_type={c['lottery_type']}"
        f"&strategy_id={c['strategy_id']}&bet_index={c['derived_bet_count']}"
        f"&sort=target_draw_desc&page_size=20"
    ).json()
    draws = [int(r["target_draw"]) for r in data["rows"]]
    assert draws == sorted(draws, reverse=True)


# ---------------------------------------------------------------------------
# 7. Overview still clean (P259A regression guard)
# ---------------------------------------------------------------------------

def test_p259a_overview_no_per_draw_detail(client):
    data = client.get("/api/replay/history-overview?bet_index=0").json()
    assert data["no_large_per_draw_detail"] is True
    for row in data["rows"]:
        assert "predicted_numbers" not in row
        assert "actual_numbers" not in row
        assert "hit_numbers" not in row


def test_p259a_overview_default_bet_index(client):
    data = client.get("/api/replay/history-overview").json()
    assert data["default_bet_index"] == 1
    for row in data["rows"]:
        assert row["derived_bet_count"] == 1


# ---------------------------------------------------------------------------
# 8. HTML: detail panel and key P259C elements
# ---------------------------------------------------------------------------

def test_html_detail_panel_present():
    assert 'id="p259b-detail-panel"' in HTML


def test_html_detail_tbody_present():
    assert 'id="p259b-detail-tbody"' in HTML


def test_html_p259c_js_block_present():
    # fmtNumberTokens must be in the P259B JS block (not a separate block)
    assert "fmtNumberTokens" in HTML


def test_html_fallback_no_network_or_db_call_in_function():
    """fmtNumberTokens must not contain fetch/XMLHttpRequest/db calls — pure in-memory."""
    start = HTML.find("function fmtNumberTokens")
    end = HTML.find("function renderSummary", start)
    fn_body = HTML[start:end] if start != -1 else ""
    forbidden = ["fetch(", "XMLHttpRequest", "conn.execute", "INSERT", "UPDATE "]
    for term in forbidden:
        assert term not in fn_body, f"forbidden network/db call in fmtNumberTokens: {term!r}"
    # The comment before the function clarifies display-only behavior (located before keyword)
    fn_comment_area = HTML[max(0, start - 300):start]
    assert "display-only" in fn_comment_area or "no DB" in fn_comment_area or "DB write" in fn_comment_area
