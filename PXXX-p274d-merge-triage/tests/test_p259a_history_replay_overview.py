"""P259A — Tests for GET /api/replay/history-overview.

Validates: default bet_index=1, bet count filters, lottery type isolation,
replay status categories, all-strategy inclusion, lifecycle as badge only,
detail page P259B deferral, and safety guarantees.
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


# ---------------------------------------------------------------------------
# 1. _derive_bet_count helper unit tests (no HTTP)
# ---------------------------------------------------------------------------

def _get_derive_bet_count():
    lottery_api_dir = str(REPO_ROOT / "lottery_api")
    if lottery_api_dir not in sys.path:
        sys.path.insert(0, lottery_api_dir)
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from routes.replay import _derive_bet_count
    return _derive_bet_count


def test_derive_bet_count_explicit_suffix():
    fn = _get_derive_bet_count()
    assert fn("power_precision_3bet") == 3
    assert fn("power_orthogonal_5bet") == 5
    assert fn("biglotto_deviation_2bet") == 2
    assert fn("biglotto_ts3_acb_4bet") == 4
    assert fn("biglotto_ts3_markov_freq_5bet") == 5
    assert fn("midfreq_acb_2bet") == 2
    assert fn("acb_markov_midfreq_3bet") == 3
    assert fn("acb_1bet") == 1
    assert fn("fourier_rhythm_3bet") == 3
    assert fn("ts3_regime_3bet") == 3


def test_derive_bet_count_triple_strike():
    fn = _get_derive_bet_count()
    assert fn("biglotto_triple_strike") == 3


def test_derive_bet_count_default_1():
    fn = _get_derive_bet_count()
    assert fn("daily539_f4cold") == 1
    assert fn("daily539_markov_cold") == 1
    assert fn("some_unknown_strategy") == 1


# ---------------------------------------------------------------------------
# 2. HTTP 200 and basic structure
# ---------------------------------------------------------------------------

def test_endpoint_returns_200(client):
    r = client.get("/api/replay/history-overview")
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text[:300]}"


def test_response_is_dict(client):
    r = client.get("/api/replay/history-overview")
    assert isinstance(r.json(), dict)


def test_required_top_level_fields(client):
    data = client.get("/api/replay/history-overview").json()
    required = [
        "default_bet_index", "bet_index_filter", "lottery_type_filter",
        "replay_status_category_filter", "total_rows", "rows",
        "all_strategies_included", "lifecycle_as_badge_only",
        "detail_page_note", "disclaimer",
        "no_db_write", "no_replay_backfill", "no_strategy_adapter_changes",
        "no_large_per_draw_detail",
    ]
    for field in required:
        assert field in data, f"Missing required field: {field}"


# ---------------------------------------------------------------------------
# 3. Default bet_index=1
# ---------------------------------------------------------------------------

def test_default_bet_index_is_1(client):
    data = client.get("/api/replay/history-overview").json()
    assert data["default_bet_index"] == 1
    assert data["bet_index_filter"] == 1


def test_default_view_filters_to_bet_count_1(client):
    data = client.get("/api/replay/history-overview").json()
    for row in data["rows"]:
        assert row["derived_bet_count"] == 1, (
            f"Default bet_index=1 but row has derived_bet_count={row['derived_bet_count']}: "
            f"{row['strategy_id']}"
        )


# ---------------------------------------------------------------------------
# 4. Bet count filter tabs (1/2/3/4/5/0=all)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("bet", [1, 2, 3, 4, 5])
def test_bet_filter_returns_matching_rows_only(client, bet):
    data = client.get(f"/api/replay/history-overview?bet_index={bet}").json()
    assert data["bet_index_filter"] == bet
    for row in data["rows"]:
        assert row["derived_bet_count"] == bet, (
            f"bet_index={bet} but row has derived_bet_count={row['derived_bet_count']}"
        )


def test_bet_filter_0_returns_all(client):
    all_data  = client.get("/api/replay/history-overview?bet_index=0").json()
    data_1    = client.get("/api/replay/history-overview?bet_index=1").json()
    data_3    = client.get("/api/replay/history-overview?bet_index=3").json()
    assert all_data["total_rows"] >= data_1["total_rows"]
    assert all_data["total_rows"] >= data_3["total_rows"]
    bet_counts = {r["derived_bet_count"] for r in all_data["rows"]}
    assert len(bet_counts) > 1, "bet_index=0 should include multiple bet counts"


# ---------------------------------------------------------------------------
# 5. Lottery type filter — no cross-contamination
# ---------------------------------------------------------------------------

def test_daily539_filter_excludes_big_lotto(client):
    data = client.get("/api/replay/history-overview?bet_index=0&lottery_type=DAILY_539").json()
    for row in data["rows"]:
        assert row["lottery_type"] == "DAILY_539", (
            f"DAILY_539 filter returned row with lottery_type={row['lottery_type']}"
        )
    lt_set = {r["lottery_type"] for r in data["rows"]}
    assert "BIG_LOTTO" not in lt_set


def test_big_lotto_filter_excludes_daily539(client):
    data = client.get("/api/replay/history-overview?bet_index=0&lottery_type=BIG_LOTTO").json()
    for row in data["rows"]:
        assert row["lottery_type"] == "BIG_LOTTO", (
            f"BIG_LOTTO filter returned row with lottery_type={row['lottery_type']}"
        )
    lt_set = {r["lottery_type"] for r in data["rows"]}
    assert "DAILY_539" not in lt_set


def test_no_lottery_filter_includes_all_types(client):
    data = client.get("/api/replay/history-overview?bet_index=0").json()
    lt_set = {r["lottery_type"] for r in data["rows"]}
    assert "DAILY_539" in lt_set
    assert "BIG_LOTTO" in lt_set
    assert "POWER_LOTTO" in lt_set


# ---------------------------------------------------------------------------
# 6. Replay status category filter
# ---------------------------------------------------------------------------

def test_replay_status_filter_has_rows(client):
    data = client.get(
        "/api/replay/history-overview?bet_index=0&replay_status_category=has_rows"
    ).json()
    for row in data["rows"]:
        assert row["replay_status_category"] == "has_rows"
        assert row["has_production_replay"] is True
        assert row["total_replay_rows"] > 0


def test_replay_status_filter_no_production_replay(client):
    data = client.get(
        "/api/replay/history-overview?bet_index=0&replay_status_category=no_production_replay"
    ).json()
    for row in data["rows"]:
        assert row["replay_status_category"] == "no_production_replay"
        assert row["has_production_replay"] is False


def test_replay_status_filter_artifact_only(client):
    data = client.get(
        "/api/replay/history-overview?bet_index=0&replay_status_category=artifact_only"
    ).json()
    for row in data["rows"]:
        assert row["replay_status_category"] == "artifact_only"
        assert row["has_production_replay"] is False


def test_replay_status_no_filter_includes_all_categories(client):
    data = client.get("/api/replay/history-overview?bet_index=0").json()
    cats = {r["replay_status_category"] for r in data["rows"]}
    assert len(cats) >= 2, f"Expected multiple replay categories, got: {cats}"


# ---------------------------------------------------------------------------
# 7. All strategy categories discoverable (lifecycle never excludes)
# ---------------------------------------------------------------------------

def test_all_lifecycle_statuses_discoverable(client):
    data = client.get("/api/replay/history-overview?bet_index=0").json()
    lc_set = {r["lifecycle_status"] for r in data["rows"]}
    expected = {"ONLINE", "REJECTED", "RETIRED"}
    missing = expected - lc_set
    assert not missing, (
        f"Missing lifecycle statuses in overview (all should be discoverable): {missing}"
    )


def test_rejected_strategies_present(client):
    data = client.get("/api/replay/history-overview?bet_index=0").json()
    rejected = [r for r in data["rows"] if r["lifecycle_status"] == "REJECTED"]
    assert len(rejected) > 0, "REJECTED strategies must be discoverable in overview"


def test_retired_strategies_present(client):
    data = client.get("/api/replay/history-overview?bet_index=0").json()
    retired = [r for r in data["rows"] if r["lifecycle_status"] == "RETIRED"]
    assert len(retired) > 0, "RETIRED strategies must be discoverable in overview"


def test_all_strategies_included_flag(client):
    data = client.get("/api/replay/history-overview?bet_index=0").json()
    assert data["all_strategies_included"] is True


def test_lifecycle_as_badge_only_flag(client):
    data = client.get("/api/replay/history-overview?bet_index=0").json()
    assert data["lifecycle_as_badge_only"] is True


# ---------------------------------------------------------------------------
# 8. Row schema — each row has required fields
# ---------------------------------------------------------------------------

def test_row_schema(client):
    data = client.get("/api/replay/history-overview?bet_index=0").json()
    required_row_fields = [
        "lottery_type", "strategy_id", "strategy_name", "derived_bet_count",
        "lifecycle_status", "is_executable",
        "total_replay_rows", "min_target_draw", "max_target_draw",
        "latest_target_draw", "replay_status_summary",
        "has_production_replay", "replay_status_category",
    ]
    for row in data["rows"]:
        for field in required_row_fields:
            assert field in row, f"Row missing field '{field}' for strategy {row.get('strategy_id')}"


def test_row_derived_bet_count_is_int(client):
    data = client.get("/api/replay/history-overview?bet_index=0").json()
    for row in data["rows"]:
        assert isinstance(row["derived_bet_count"], int)
        assert 1 <= row["derived_bet_count"] <= 5


# ---------------------------------------------------------------------------
# 9. Detail page explicitly deferred to P259B
# ---------------------------------------------------------------------------

def test_detail_page_note_mentions_p259b(client):
    data = client.get("/api/replay/history-overview").json()
    note = data.get("detail_page_note", "")
    assert "P259B" in note, f"detail_page_note must mention P259B. Got: {note!r}"


def test_detail_page_note_mentions_per_draw_query(client):
    data = client.get("/api/replay/history-overview").json()
    note = data.get("detail_page_note", "")
    assert "每一期" in note or "分頁" in note, (
        f"detail_page_note should mention per-draw paged query. Got: {note!r}"
    )


# ---------------------------------------------------------------------------
# 10. Safety guarantees
# ---------------------------------------------------------------------------

def test_no_db_write(client):
    data = client.get("/api/replay/history-overview").json()
    assert data["no_db_write"] is True


def test_no_replay_backfill(client):
    data = client.get("/api/replay/history-overview").json()
    assert data["no_replay_backfill"] is True


def test_no_strategy_adapter_changes(client):
    data = client.get("/api/replay/history-overview").json()
    assert data["no_strategy_adapter_changes"] is True


def test_no_large_per_draw_detail(client):
    data = client.get("/api/replay/history-overview").json()
    assert data["no_large_per_draw_detail"] is True
    # Rows must not contain per-draw detail fields
    for row in data["rows"]:
        assert "predicted_numbers" not in row, "Per-draw detail fields must not appear in overview rows"
        assert "hit_numbers" not in row


def test_disclaimer_present(client):
    data = client.get("/api/replay/history-overview").json()
    assert data.get("disclaimer"), "disclaimer must be present and non-empty"


# ---------------------------------------------------------------------------
# 11. HTML UI — bet tabs, section, P259B notice
# ---------------------------------------------------------------------------

def test_html_has_p259a_section():
    html = (REPO_ROOT / "index.html").read_text(encoding="utf-8")
    assert 'id="p259a-replay-overview-section"' in html


def test_html_has_p259a_nav_button():
    html = (REPO_ROOT / "index.html").read_text(encoding="utf-8")
    assert 'data-section="p259a-replay-overview"' in html


def test_html_has_bet_tabs_1_through_5():
    html = (REPO_ROOT / "index.html").read_text(encoding="utf-8")
    for bet in [1, 2, 3, 4, 5]:
        assert f'data-bet="{bet}"' in html, f"Missing bet tab data-bet={bet}"


def test_html_default_bet_tab_1_active():
    html = (REPO_ROOT / "index.html").read_text(encoding="utf-8")
    assert 'data-bet="1"' in html
    # The first bet tab must have the active class
    import re
    # Look for p259a-bet-tab-active on a data-bet="1" button
    pattern = r'data-bet="1"[^>]*p259a-bet-tab-active|p259a-bet-tab-active[^>]*data-bet="1"'
    assert re.search(pattern, html), "bet tab data-bet=1 must have p259a-bet-tab-active class"


def test_html_has_all_bet_tab():
    html = (REPO_ROOT / "index.html").read_text(encoding="utf-8")
    assert 'data-bet="0"' in html, "Missing 全部注數 tab (data-bet=0)"


def test_html_p259b_notice_present():
    html = (REPO_ROOT / "index.html").read_text(encoding="utf-8")
    assert "P259B" in html


def test_html_p259b_notice_content():
    html = (REPO_ROOT / "index.html").read_text(encoding="utf-8")
    assert "明細頁將於後續 P259B 實作" in html


def test_html_lottery_filter_options():
    html = (REPO_ROOT / "index.html").read_text(encoding="utf-8")
    # Check that both 今彩539 and 大樂透 options exist in p259a section
    assert "p259a-filter-lottery" in html
    assert "DAILY_539" in html
    assert "BIG_LOTTO" in html
    assert "POWER_LOTTO" in html


def test_html_replay_status_filter_options():
    html = (REPO_ROOT / "index.html").read_text(encoding="utf-8")
    assert "p259a-filter-replay-cat" in html
    assert "has_rows" in html
    assert "no_production_replay" in html
    assert "artifact_only" in html


def test_html_detail_button_disabled():
    html = (REPO_ROOT / "index.html").read_text(encoding="utf-8")
    # The 查看明細 button must be disabled
    assert "查看明細" in html
    # Find the button and verify disabled attribute
    import re
    m = re.search(r'<button[^>]*disabled[^>]*>[^<]*查看明細', html)
    assert m, "查看明細 button must have disabled attribute"


def test_html_no_production_db_write_in_p259a_js():
    html = (REPO_ROOT / "index.html").read_text(encoding="utf-8")
    # Extract P259A JS block only
    start = html.find("P259A: History Replay Overview JS")
    end   = html.find("</script>", start)
    if start == -1:
        pytest.skip("P259A JS block not found")
    p259a_js = html[start:end]
    forbidden = ["POST", "PUT", "DELETE", "fetch.*POST", "backfill", "INSERT", "UPDATE"]
    for term in forbidden:
        import re
        if re.search(term, p259a_js, re.IGNORECASE):
            pytest.fail(f"P259A JS contains forbidden term: {term!r}")
