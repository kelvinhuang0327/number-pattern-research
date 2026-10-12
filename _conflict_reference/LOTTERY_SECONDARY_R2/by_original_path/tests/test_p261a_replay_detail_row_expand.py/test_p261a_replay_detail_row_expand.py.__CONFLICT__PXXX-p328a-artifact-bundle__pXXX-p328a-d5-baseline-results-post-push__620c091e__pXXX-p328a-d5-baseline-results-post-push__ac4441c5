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

def test_best_ticket_summary_logic_present():
    """Verify that multi-ticket replay summary selects the best ticket (hit_count & tie-break bet_index)."""
    html = _html()
    assert "最佳命中：第 " in html
    assert "var hc1 = bestBet.hit_count" in html
    assert "var hc2 = b2.hit_count" in html
    assert "hc2 > hc1" in html
    assert "bi2 < bi1" in html


# ---------------------------------------------------------------------------
# 11. Headless Chrome DOM Verification Tests
# ---------------------------------------------------------------------------
import socket
import subprocess
import time
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import re
from pathlib import Path

def _run_chrome_headless_test(mock_data: dict, screenshot_name: str | None = None) -> str:
    import tempfile
    # Find a free port
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('127.0.0.1', 0))
    port = s.getsockname()[1]
    s.close()

    # Prepare HTML content with injected script
    html_content = Path(HTML_PATH).read_text(encoding="utf-8")

    # We set window.MOCK_DATA_FIXTURE and override window.fetch to return it.
    # Programmatically click the detail button.
    mock_js = f"""
    <script>
    window.MOCK_DATA_FIXTURE = {json.dumps(mock_data)};
    window.fetch = function(url) {{
        return Promise.resolve({{
            ok: true,
            json: function() {{ return Promise.resolve(window.MOCK_DATA_FIXTURE); }}
        }});
    }};
    window.addEventListener('DOMContentLoaded', function() {{
        var btn = document.createElement('button');
        btn.className = 'p259b-detail-btn';
        btn.dataset.lottery = '{mock_data.get("lottery_type", "DAILY_539")}';
        btn.dataset.strategy = '{mock_data.get("strategy_id", "test_strategy")}';
        btn.dataset.bet = '{mock_data.get("bet_index", 1)}';
        btn.dataset.name = 'Test Strategy';
        var tbody = document.getElementById('p259a-tbody');
        if (tbody) {{
            tbody.appendChild(btn);
            btn.click();
        }}
    }});
    </script>
    """
    injected_html = html_content.replace("</body>", f"{mock_js}</body>")

    class InjectedHTMLHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(injected_html.encode("utf-8"))
        def log_message(self, format, *args):
            pass

    server = HTTPServer(('127.0.0.1', port), InjectedHTMLHandler)
    t = threading.Thread(target=server.serve_forever)
    t.daemon = True
    t.start()

    time.sleep(0.1)
    chrome_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    url = f"http://127.0.0.1:{port}/"

    try:
        env_dir = os.environ.get("LOTTERY_UI_TEST_ARTIFACT_DIR")
        if env_dir:
            out_dir = env_dir
        else:
            out_dir = os.path.join(tempfile.gettempdir(), "lottery_ui_test_temp_outputs")
        os.makedirs(out_dir, exist_ok=True)
        if screenshot_name:
            screenshot_path = os.path.join(out_dir, screenshot_name)
            subprocess.run([
                chrome_path,
                "--headless",
                "--disable-gpu",
                "--window-size=1440,900",
                f"--screenshot={screenshot_path}",
                url
            ], capture_output=True, timeout=30)

        res = subprocess.run([
            chrome_path,
            "--headless",
            "--disable-gpu",
            "--dump-dom",
            url
        ], capture_output=True, text=True, timeout=30)

        # Also write the normalized DOM evidence to the attempt directory
        dom_evidence_path = os.path.join(out_dir, "best_ticket_behavioral_evidence.json")
        evidence = {}
        if os.path.exists(dom_evidence_path):
            try:
                with open(dom_evidence_path, "r", encoding="utf-8") as f:
                    evidence = json.load(f)
            except Exception:
                pass
        evidence[mock_data.get("rows")[0].get("target_draw")] = res.stdout
        with open(dom_evidence_path, "w", encoding="utf-8") as f:
            json.dump(evidence, f, indent=2, ensure_ascii=False)

        return res.stdout
    finally:
        server.shutdown()
        server.server_close()
        t.join()


def _extract_tbody(dom: str) -> str:
    start_idx = dom.find('<tbody id="p259b-detail-tbody">')
    if start_idx == -1:
        return ""
    end_idx = dom.find('</tbody>', start_idx)
    if end_idx == -1:
        return ""
    return dom[start_idx:end_idx+8]


def test_fixture_a_115000037():
    mock_data = {
      "lottery_type": "DAILY_539",
      "strategy_id": "test_strategy",
      "bet_index": 2,
      "derived_bet_count": 4,
      "rows": [
        {
          "target_draw": "115000037",
          "draw_date": "2026-06-25",
          "n_bets": 4,
          "actual_numbers": [3, 14, 15, 24, 34, 38],
          "actual_special": 3,
          "predicted_numbers": [14, 15],
          "predicted_special": None,
          "hit_numbers": [14, 15, 24, 34],
          "special_hit": True,
          "any_hit": True,
          "max_hit_count": 3,
          "bets": [
            {
              "bet_index": 1,
              "predicted_numbers": [14, 15],
              "actual_numbers": [3, 14, 15, 24, 34, 38],
              "hit_numbers": [14, 15],
              "hit_count": 2,
              "special_hit": False,
              "result_label": "2 hit"
            },
            {
              "bet_index": 2,
              "predicted_numbers": [14, 15],
              "actual_numbers": [3, 14, 15, 24, 34, 38],
              "hit_numbers": [14, 15],
              "hit_count": 2,
              "special_hit": False,
              "result_label": "2 hit"
            },
            {
              "bet_index": 3,
              "predicted_numbers": [24],
              "actual_numbers": [3, 14, 15, 24, 34, 38],
              "hit_numbers": [24],
              "hit_count": 1,
              "special_hit": False,
              "result_label": "1 hit"
            },
            {
              "bet_index": 4,
              "predicted_numbers": [14, 15, 34],
              "actual_numbers": [3, 14, 15, 24, 34, 38],
              "hit_numbers": [14, 15, 34],
              "hit_count": 3,
              "special_hit": True,
              "actual_special": 3,
              "predicted_special": 3,
              "result_label": "3 hit"
            }
          ]
        }
      ]
    }

    dom = _run_chrome_headless_test(mock_data, screenshot_name="desktop_115000037.png")
    tbody = _extract_tbody(dom)
    assert tbody, "Detail tbody not found in DOM"

    # Assertions on best-hit label inside the summary cell
    assert "最佳命中：第 4 注｜3 個" in tbody

    # Assert DOM inside [data-role="replay-best-hit-summary"] only
    hit_td_match = re.search(r'<td[^>]*data-role="replay-best-hit-summary"[^>]*>(.*?)</td>', tbody, re.DOTALL)
    assert hit_td_match, "Hit summary TD with data-role not found"
    hit_summary_content = hit_td_match.group(1)

    # Assert best ticket hit tokens are present in marked summary area
    assert '14' in hit_summary_content
    assert '15' in hit_summary_content
    assert '34' in hit_summary_content

    # Assert forbidden union numbers (e.g. 24) are absent from marked summary area
    assert '24' not in hit_summary_content

    # Assert actual-draw DOM remains complete in its own cell (not inside the marked summary area)
    # The actual draw cell contains the winning numbers
    actual_td_match = re.search(r'<td[^>]*data-label="實際開獎"[^>]*>(.*?)</td>', tbody, re.DOTALL)
    assert actual_td_match, "Actual draw TD not found"
    actual_content = actual_td_match.group(1)
    assert "3" in actual_content
    assert "14" in actual_content
    assert "15" in actual_content
    assert "24" in actual_content
    assert "34" in actual_content
    assert "38" in actual_content
    assert "特3" in actual_content or "3" in actual_content  # special ball 3

    # Assert expanded detail contains each individual ticket and its original hit result
    for b in mock_data["rows"][0]["bets"]:
        assert f"第 {b['bet_index']} 注" in tbody
        assert str(b['hit_count']) in tbody


def test_fixture_b_115000040():
    mock_data = {
      "lottery_type": "DAILY_539",
      "strategy_id": "test_strategy",
      "bet_index": 1,
      "derived_bet_count": 3,
      "rows": [
        {
          "target_draw": "115000040",
          "draw_date": "2026-06-25",
          "n_bets": 3,
          "actual_numbers": [3, 14, 15, 34, 38],
          "predicted_numbers": [14],
          "predicted_special": None,
          "hit_numbers": [14, 34],
          "special_hit": False,
          "any_hit": True,
          "max_hit_count": 1,
          "bets": [
            {
              "bet_index": 1,
              "predicted_numbers": [14],
              "actual_numbers": [3, 14, 15, 34, 38],
              "hit_numbers": [14],
              "hit_count": 1,
              "special_hit": False,
              "result_label": "1 hit"
            },
            {
              "bet_index": 2,
              "predicted_numbers": [],
              "actual_numbers": [3, 14, 15, 34, 38],
              "hit_numbers": [],
              "hit_count": 0,
              "special_hit": False,
              "result_label": "0 hit"
            },
            {
              "bet_index": 3,
              "predicted_numbers": [34],
              "actual_numbers": [3, 14, 15, 34, 38],
              "hit_numbers": [34],
              "hit_count": 1,
              "special_hit": False,
              "result_label": "1 hit"
            }
          ]
        }
      ]
    }

    dom = _run_chrome_headless_test(mock_data)
    tbody = _extract_tbody(dom)
    assert tbody

    assert "最佳命中：第 1 注｜1 個" in tbody
    hit_td_match = re.search(r'<td[^>]*data-role="replay-best-hit-summary"[^>]*>(.*?)</td>', tbody, re.DOTALL)
    assert hit_td_match
    hit_summary_content = hit_td_match.group(1)
    assert "14" in hit_summary_content
    assert "34" not in hit_summary_content


def test_fixture_c_114000092():
    mock_data = {
      "lottery_type": "DAILY_539",
      "strategy_id": "test_strategy",
      "bet_index": 1,
      "derived_bet_count": 3,
      "rows": [
        {
          "target_draw": "114000092",
          "draw_date": "2026-06-25",
          "n_bets": 3,
          "actual_numbers": [3, 17, 18, 19, 28, 34, 36],
          "predicted_numbers": [17, 18, 36],
          "predicted_special": None,
          "hit_numbers": [17, 18, 19, 28, 34, 36],
          "special_hit": False,
          "any_hit": True,
          "max_hit_count": 3,
          "bets": [
            {
              "bet_index": 1,
              "predicted_numbers": [17, 18, 36],
              "actual_numbers": [3, 17, 18, 19, 28, 34, 36],
              "hit_numbers": [17, 18, 36],
              "hit_count": 3,
              "special_hit": False,
              "result_label": "3 hit"
            },
            {
              "bet_index": 2,
              "predicted_numbers": [28, 34],
              "actual_numbers": [3, 17, 18, 19, 28, 34, 36],
              "hit_numbers": [28, 34],
              "hit_count": 2,
              "special_hit": False,
              "result_label": "2 hit"
            },
            {
              "bet_index": 3,
              "predicted_numbers": [18, 19],
              "actual_numbers": [3, 17, 18, 19, 28, 34, 36],
              "hit_numbers": [18, 19],
              "hit_count": 2,
              "special_hit": False,
              "result_label": "2 hit"
            }
          ]
        }
      ]
    }

    dom = _run_chrome_headless_test(mock_data)
    tbody = _extract_tbody(dom)
    assert tbody

    assert "最佳命中：第 1 注｜3 個" in tbody
    hit_td_match = re.search(r'<td[^>]*data-role="replay-best-hit-summary"[^>]*>(.*?)</td>', tbody, re.DOTALL)
    assert hit_td_match
    hit_summary_content = hit_td_match.group(1)
    assert "17" in hit_summary_content
    assert "18" in hit_summary_content
    assert "36" in hit_summary_content
    assert "19" not in hit_summary_content
    assert "28" not in hit_summary_content
    assert "34" not in hit_summary_content


def test_fixture_d_all_zero():
    mock_data = {
      "lottery_type": "DAILY_539",
      "strategy_id": "test_strategy",
      "bet_index": 1,
      "derived_bet_count": 2,
      "rows": [
        {
          "target_draw": "115000041",
          "draw_date": "2026-06-25",
          "n_bets": 2,
          "actual_numbers": [3, 14, 15, 34, 38],
          "predicted_numbers": [1],
          "predicted_special": None,
          "hit_numbers": [],
          "special_hit": False,
          "any_hit": False,
          "max_hit_count": 0,
          "bets": [
            {
              "bet_index": 1,
              "predicted_numbers": [1],
              "actual_numbers": [3, 14, 15, 34, 38],
              "hit_numbers": [],
              "hit_count": 0,
              "special_hit": False,
              "result_label": "0 hit"
            },
            {
              "bet_index": 2,
              "predicted_numbers": [2],
              "actual_numbers": [3, 14, 15, 34, 38],
              "hit_numbers": [],
              "hit_count": 0,
              "special_hit": False,
              "result_label": "0 hit"
            }
          ]
        }
      ]
    }

    dom = _run_chrome_headless_test(mock_data)
    tbody = _extract_tbody(dom)
    assert tbody

    assert "最佳命中：第 1 注｜0 個" in tbody
    hit_td_match = re.search(r'<td[^>]*data-role="replay-best-hit-summary"[^>]*>(.*?)</td>', tbody, re.DOTALL)
    assert hit_td_match
    hit_summary_content = hit_td_match.group(1)
    assert "—" in hit_summary_content or hit_summary_content.strip() == ""


def test_fixture_d_tie():
    mock_data = {
      "lottery_type": "DAILY_539",
      "strategy_id": "test_strategy",
      "bet_index": 1,
      "derived_bet_count": 3,
      "rows": [
        {
          "target_draw": "999",
          "draw_date": "2026-06-25",
          "n_bets": 3,
          "actual_numbers": [3, 14, 15, 34, 38],
          "predicted_numbers": [14],
          "predicted_special": None,
          "hit_numbers": [14, 34],
          "special_hit": False,
          "any_hit": True,
          "max_hit_count": 1,
          "bets": [
            {
              "bet_index": 1,
              "predicted_numbers": [1],
              "actual_numbers": [3, 14, 15, 34, 38],
              "hit_numbers": [],
              "hit_count": 0,
              "special_hit": False,
              "result_label": "0 hit"
            },
            {
              "bet_index": 2,
              "predicted_numbers": [14],
              "actual_numbers": [3, 14, 15, 34, 38],
              "hit_numbers": [14],
              "hit_count": 1,
              "special_hit": False,
              "result_label": "1 hit"
            },
            {
              "bet_index": 3,
              "predicted_numbers": [34],
              "actual_numbers": [3, 14, 15, 34, 38],
              "hit_numbers": [34],
              "hit_count": 1,
              "special_hit": False,
              "result_label": "1 hit"
            }
          ]
        }
      ]
    }

    dom = _run_chrome_headless_test(mock_data)
    tbody = _extract_tbody(dom)
    assert tbody

    assert "最佳命中：第 2 注｜1 個" in tbody


def test_fixture_single_ticket():
    mock_data = {
      "lottery_type": "DAILY_539",
      "strategy_id": "test_strategy",
      "bet_index": 1,
      "derived_bet_count": 1,
      "rows": [
        {
          "target_draw": "115000042",
          "draw_date": "2026-06-25",
          "n_bets": 1,
          "actual_numbers": [3, 14, 15, 34, 38],
          "predicted_numbers": [14],
          "predicted_special": None,
          "hit_numbers": [14],
          "special_hit": False,
          "any_hit": True,
          "max_hit_count": 1,
          "bets": [
            {
              "bet_index": 1,
              "predicted_numbers": [14],
              "actual_numbers": [3, 14, 15, 34, 38],
              "hit_numbers": [14],
              "hit_count": 1,
              "special_hit": False,
              "result_label": "1 hit"
            }
          ]
        }
      ]
    }

    dom = _run_chrome_headless_test(mock_data)
    tbody = _extract_tbody(dom)
    assert tbody

    assert "最佳命中" not in tbody
    assert 'data-role="replay-best-hit-summary"' not in tbody
    assert '<span class="replay-number-token replay-number-token--hit">14</span>' in tbody


# ---------------------------------------------------------------------------
# 12. Headless Chrome Viewport Responsiveness Tests
# ---------------------------------------------------------------------------

def test_viewport_responsiveness_and_expand_button():
    """Verify viewport constraints and expand button visibility across all four viewports."""
    mock_data = {
      "lottery_type": "DAILY_539",
      "strategy_id": "test_strategy",
      "bet_index": 2,
      "derived_bet_count": 4,
      "rows": [
        {
          "target_draw": "115000037",
          "draw_date": "2026-06-25",
          "n_bets": 4,
          "actual_numbers": [3, 14, 15, 24, 34, 38],
          "actual_special": 3,
          "predicted_numbers": [14, 15],
          "predicted_special": None,
          "hit_numbers": [14, 15, 24, 34],
          "special_hit": True,
          "any_hit": True,
          "max_hit_count": 3,
          "bets": [
            {
              "bet_index": 1,
              "predicted_numbers": [14, 15],
              "actual_numbers": [3, 14, 15, 24, 34, 38],
              "hit_numbers": [14, 15],
              "hit_count": 2,
              "special_hit": False,
              "result_label": "2 hit"
            },
            {
              "bet_index": 2,
              "predicted_numbers": [14, 15],
              "actual_numbers": [3, 14, 15, 24, 34, 38],
              "hit_numbers": [14, 15],
              "hit_count": 2,
              "special_hit": False,
              "result_label": "2 hit"
            },
            {
              "bet_index": 3,
              "predicted_numbers": [24],
              "actual_numbers": [3, 14, 15, 24, 34, 38],
              "hit_numbers": [24],
              "hit_count": 1,
              "special_hit": False,
              "result_label": "1 hit"
            },
            {
              "bet_index": 4,
              "predicted_numbers": [14, 15, 34],
              "actual_numbers": [3, 14, 15, 24, 34, 38],
              "hit_numbers": [14, 15, 34],
              "hit_count": 3,
              "special_hit": True,
              "actual_special": 3,
              "predicted_special": 3,
              "result_label": "3 hit"
            }
          ]
        }
      ]
    }

    import base64
    import tempfile
    import shutil
    import urllib.request

    def recv_exact(sock, n):
        data = b""
        while len(data) < n:
            chunk = sock.recv(n - len(data))
            if not chunk:
                break
            data += chunk
        return data

    def recv_websocket_frame(sock):
        header = recv_exact(sock, 2)
        if len(header) < 2:
            return None, None
        b1, b2 = header[0], header[1]
        fin = (b1 >> 7) & 1
        opcode = b1 & 0xf
        masked = (b2 >> 7) & 1
        length = b2 & 0x7f
        
        if length == 126:
            len_bytes = recv_exact(sock, 2)
            length = int.from_bytes(len_bytes, 'big')
        elif length == 127:
            len_bytes = recv_exact(sock, 8)
            length = int.from_bytes(len_bytes, 'big')
            
        if masked:
            mask_key = recv_exact(sock, 4)
            
        payload = recv_exact(sock, length)
        
        if masked:
            unmasked = bytearray(payload)
            for i in range(len(unmasked)):
                unmasked[i] ^= mask_key[i % 4]
            payload = bytes(unmasked)
            
        return opcode, payload

    class CDPClient:
        def __init__(self, ws_url):
            url_parts = ws_url.replace("ws://", "").split("/")
            host_port = url_parts[0].split(":")
            self.host = host_port[0]
            self.port = int(host_port[1])
            self.path = "/" + "/".join(url_parts[1:])
            self.sock = socket.create_connection((self.host, self.port))
            
            handshake = (
                f"GET {self.path} HTTP/1.1\r\n"
                f"Host: {self.host}:{self.port}\r\n"
                f"Upgrade: websocket\r\n"
                f"Connection: Upgrade\r\n"
                f"Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n"
                f"Sec-WebSocket-Version: 13\r\n\r\n"
            )
            self.sock.sendall(handshake.encode())
            
            resp = b""
            while b"\r\n\r\n" not in resp:
                chunk = self.sock.recv(1024)
                if not chunk:
                    break
                resp += chunk
            self.cmd_id = 1
            
        def call(self, method, params):
            payload = json.dumps({
                "id": self.cmd_id,
                "method": method,
                "params": params
            }).encode('utf-8')
            
            length = len(payload)
            if length < 126:
                header = b'\x81' + bytes([0x80 | length]) + b'\x00\x00\x00\x00'
            else:
                header = b'\x81' + bytes([0x80 | 126]) + length.to_bytes(2, 'big') + b'\x00\x00\x00\x00'
                
            self.sock.sendall(header + payload)
            
            target_id = self.cmd_id
            self.cmd_id += 1
            
            while True:
                opcode, frame_data = recv_websocket_frame(self.sock)
                if opcode is None:
                    raise Exception("Connection closed while waiting for response")
                try:
                    res_json = json.loads(frame_data.decode('utf-8'))
                    if res_json.get("id") == target_id:
                        return res_json
                except Exception:
                    pass
                    
        def close(self):
            self.sock.close()

    # Find a free port for HTTP server
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('127.0.0.1', 0))
    port = s.getsockname()[1]
    s.close()

    # Find a free port for Chrome remote debugging
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('127.0.0.1', 0))
    chrome_port = s.getsockname()[1]
    s.close()

    html_content = Path(HTML_PATH).read_text(encoding="utf-8")

    mock_js = f"""
    <script>
    window.MOCK_DATA_FIXTURE = {json.dumps(mock_data)};
    window.fetch = function(url) {{
        if (url.indexOf('history-overview') !== -1) {{
            return Promise.resolve({{
                ok: true,
                json: function() {{
                    return Promise.resolve({{
                        rows: [
                            {{
                                lottery_type: "DAILY_539",
                                strategy_id: "test_strategy",
                                strategy_name: "Test Strategy",
                                derived_bet_count: 4,
                                registry_status: "registered",
                                total_replay_rows: 10,
                                distinct_draw_count: 10,
                                min_target_draw: "115000030",
                                max_target_draw: "115000037",
                                latest_target_draw: "115000037",
                                replay_status_category: "has_rows",
                                lifecycle_status: "ONLINE",
                                has_production_replay: true,
                                can_open_detail: true
                            }}
                        ]
                    }});
                }}
            }});
        }}
        return Promise.resolve({{
            ok: true,
            json: function() {{ return Promise.resolve(window.MOCK_DATA_FIXTURE); }}
        }});
    }};
    window.addEventListener('load', function() {{
        function runTest() {{
            var navBtn = document.querySelector('[data-section="p259a-replay-overview"]');
            if (navBtn) {{
                document.querySelectorAll('.section').forEach(function(sec) {{
                    sec.classList.remove('active');
                }});
                var replaySec = document.getElementById('p259a-replay-overview-section');
                if (replaySec) {{
                    replaySec.classList.add('active');
                }}
                document.querySelectorAll('.nav-btn').forEach(function(btn) {{
                    btn.classList.remove('active');
                }});
                navBtn.classList.add('active');
                navBtn.click();
            }} else {{
                setTimeout(runTest, 100);
            }}
        }}
        setTimeout(runTest, 200);
    }});
    </script>
    """

    class InjectedHTMLHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            clean_path = self.path.split('?')[0]
            if clean_path.endswith('.css'):
                css_file = Path(REPO_ROOT) / clean_path.lstrip('/')
                if css_file.exists():
                    self.send_response(200)
                    self.send_header("Content-Type", "text/css; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(css_file.read_bytes())
                    return
                else:
                    self.send_error(404, "CSS File not found")
                    return

            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html_content.replace("</body>", f"{mock_js}</body>").encode("utf-8"))
        def log_message(self, format, *args):
            pass

    server = HTTPServer(('127.0.0.1', port), InjectedHTMLHandler)
    t = threading.Thread(target=server.serve_forever)
    t.daemon = True
    t.start()
    time.sleep(0.2)

    chrome_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    
    env_dir = os.environ.get("LOTTERY_UI_TEST_ARTIFACT_DIR")
    if env_dir:
        attempt_dir = env_dir
    else:
        attempt_dir = os.path.join(tempfile.gettempdir(), "lottery_ui_test_temp_outputs")
    os.makedirs(attempt_dir, exist_ok=True)
    temp_profile = tempfile.mkdtemp(dir=attempt_dir)

    viewports = [
        {"name": "desktop_1440", "width": 1440, "height": 900, "mobile": False},
        {"name": "laptop_1024", "width": 1024, "height": 768, "mobile": False},
        {"name": "tablet_768", "width": 768, "height": 1024, "mobile": False},
        {"name": "mobile_390", "width": 390, "height": 844, "mobile": True}
    ]

    chrome_proc = None
    try:
        chrome_proc = subprocess.Popen([
            chrome_path,
            "--headless=new",
            "--disable-gpu",
            f"--remote-debugging-port={chrome_port}",
            f"--user-data-dir={temp_profile}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-extensions",
            "about:blank"
        ])

        tabs = None
        for i in range(50):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{chrome_port}/json", timeout=1.0) as f:
                    tabs = json.loads(f.read().decode('utf-8'))
                    break
            except Exception:
                time.sleep(0.2)
        if not tabs:
            raise Exception(f"Chrome remote debugging port {chrome_port} did not become active in time")

        page_tab = None
        for tab in tabs:
            if tab.get("type") == "page":
                page_tab = tab
                break
        if not page_tab:
            raise Exception("No active page tab found in Chrome DevTools")

        ws_url = page_tab["webSocketDebuggerUrl"]

        for vp in viewports:
            screenshot_path = os.path.join(attempt_dir, f"{vp['name']}.png")
            url_vp = f"http://127.0.0.1:{port}/?width={vp['width']}"

            client = CDPClient(ws_url)

            # 1. Apply true layout metrics override via CDP before navigation
            client.call("Emulation.setDeviceMetricsOverride", {
                "width": vp["width"],
                "height": vp["height"],
                "deviceScaleFactor": 2 if vp["mobile"] else 1,
                "mobile": vp["mobile"]
            })

            # 2. Navigate
            client.call("Page.navigate", {"url": url_vp})

            # 3. Wait for Detail button to be visible and click it
            detail_btn_clicked = False
            for _ in range(50):
                time.sleep(0.1)
                res = client.call("Runtime.evaluate", {
                    "expression": """
                        (function() {
                            var btn = document.querySelector('.p259b-detail-btn');
                            if (btn) {
                                btn.click();
                                return true;
                            }
                            return false;
                        })()
                    """,
                    "returnByValue": True
                })
                if res.get("result", {}).get("result", {}).get("value") is True:
                    detail_btn_clicked = True
                    break
            assert detail_btn_clicked, "Detail button not found or not clicked"

            # 4. Wait for Expand button to be visible
            expand_btn_found = False
            for _ in range(50):
                time.sleep(0.1)
                res = client.call("Runtime.evaluate", {
                    "expression": "document.querySelector('.p261a-expand-btn') !== null",
                    "returnByValue": True
                })
                if res.get("result", {}).get("result", {}).get("value") is True:
                    expand_btn_found = True
                    break
            assert expand_btn_found, "Expand button not found in DOM"

            # Verify no custom scrollWidth/clientWidth overrides were installed
            has_own_scroll = client.call("Runtime.evaluate", {"expression": "document.documentElement.hasOwnProperty('scrollWidth')", "returnByValue": True})["result"]["result"]["value"]
            has_own_client = client.call("Runtime.evaluate", {"expression": "document.documentElement.hasOwnProperty('clientWidth')", "returnByValue": True})["result"]["result"]["value"]
            has_own_body_scroll = client.call("Runtime.evaluate", {"expression": "document.body.hasOwnProperty('scrollWidth')", "returnByValue": True})["result"]["result"]["value"]
            has_own_body_client = client.call("Runtime.evaluate", {"expression": "document.body.hasOwnProperty('clientWidth')", "returnByValue": True})["result"]["result"]["value"]

            assert not has_own_scroll, "Detected own-property override on documentElement.scrollWidth"
            assert not has_own_client, "Detected own-property override on documentElement.clientWidth"
            assert not has_own_body_scroll, "Detected own-property override on body.scrollWidth"
            assert not has_own_body_client, "Detected own-property override on body.clientWidth"

            # Measure Collapsed geometry natively
            collapsed_geom = client.call("Runtime.evaluate", {
                "expression": """
                    (function() {
                        return {
                            htmlScrollWidth: document.documentElement.scrollWidth,
                            htmlClientWidth: document.documentElement.clientWidth,
                            bodyScrollWidth: document.body.scrollWidth,
                            bodyClientWidth: document.body.clientWidth
                        };
                    })()
                """,
                "returnByValue": True
            })["result"]["result"]["value"]

            # 5. Click Expand button to expand
            client.call("Runtime.evaluate", {
                "expression": "document.querySelector('.p261a-expand-btn').click()",
                "returnByValue": True
            })
            time.sleep(0.15)
            # Freeze animations
            client.call("Runtime.evaluate", {
                "expression": """
                    (function() {
                        var style = document.createElement('style');
                        style.id = 'freeze-animations-style';
                        style.textContent = '* { animation-play-state: paused !important; transition: none !important; }';
                        document.head.appendChild(style);
                    })()
                """,
                "returnByValue": True
            })

            # Measure Expanded geometry natively
            expanded_geom = client.call("Runtime.evaluate", {
                "expression": """
                    (function() {
                        return {
                            htmlScrollWidth: document.documentElement.scrollWidth,
                            htmlClientWidth: document.documentElement.clientWidth,
                            bodyScrollWidth: document.body.scrollWidth,
                            bodyClientWidth: document.body.clientWidth
                        };
                    })()
                """,
                "returnByValue": True
            })["result"]["result"]["value"]

            # Get Expand button bounds in expanded state
            btn_rect = client.call("Runtime.evaluate", {
                "expression": """
                    (function() {
                        var btn = document.querySelector('.p261a-expand-btn');
                        var rect = btn.getBoundingClientRect();
                        return {
                            left: rect.left,
                            top: rect.top,
                            right: rect.right,
                            bottom: rect.bottom,
                            width: rect.width,
                            height: rect.height
                        };
                    })()
                """,
                "returnByValue": True
            })["result"]["result"]["value"]

            # 6. Sensitivity Proof (temporarily inject a 500px offender for mobile_390)
            if vp["name"] == "mobile_390":
                # Inject 500px child
                client.call("Runtime.evaluate", {
                    "expression": """
                        (function() {
                            var spoiler = document.createElement('div');
                            spoiler.id = 'rwd-spoiler';
                            spoiler.style.width = '500px';
                            spoiler.style.minWidth = '500px';
                            spoiler.style.height = '10px';
                            spoiler.style.background = 'red';
                            spoiler.style.display = 'block';
                            document.body.appendChild(spoiler);
                        })()
                    """,
                    "returnByValue": True
                })

                # Retrieve metrics with spoiler
                spoiler_geom = client.call("Runtime.evaluate", {
                    "expression": """
                        (function() {
                            return {
                                htmlScrollWidth: document.documentElement.scrollWidth,
                                htmlClientWidth: document.documentElement.clientWidth,
                                bodyScrollWidth: document.body.scrollWidth,
                                bodyClientWidth: document.body.clientWidth
                            };
                        })()
                    """,
                    "returnByValue": True
                })["result"]["result"]["value"]

                # Sensitivity proof verification: Must detect overflow natively!
                has_html_overflow = spoiler_geom["htmlScrollWidth"] > (spoiler_geom["htmlClientWidth"] + 1)
                has_body_overflow = spoiler_geom["bodyScrollWidth"] > (spoiler_geom["bodyClientWidth"] + 1)
                assert has_html_overflow or has_body_overflow, "Sensitivity proof: overflow NOT detected with 500px spoiler element!"

                # Write to sensitivity log
                proof_log_path = os.path.join(attempt_dir, "sensitivity_proof_log.json")
                with open(proof_log_path, "w", encoding="utf-8") as pf:
                    json.dump({
                        "viewport": vp["name"],
                        "spoiler_min_width": "500px",
                        "detected_html_scroll_width": spoiler_geom["htmlScrollWidth"],
                        "detected_html_client_width": spoiler_geom["htmlClientWidth"],
                        "detected_body_scroll_width": spoiler_geom["bodyScrollWidth"],
                        "detected_body_client_width": spoiler_geom["bodyClientWidth"],
                        "detected_overflow": True
                    }, pf, indent=2)

                # Remove spoiler
                client.call("Runtime.evaluate", {
                    "expression": "var sp = document.getElementById('rwd-spoiler'); if (sp) sp.remove();",
                    "returnByValue": True
                })

                # Verify normal state restored
                restored_geom = client.call("Runtime.evaluate", {
                    "expression": """
                        (function() {
                            return {
                                htmlScrollWidth: document.documentElement.scrollWidth,
                                htmlClientWidth: document.documentElement.clientWidth,
                                bodyScrollWidth: document.body.scrollWidth,
                                bodyClientWidth: document.body.clientWidth
                            };
                        })()
                    """,
                    "returnByValue": True
                })["result"]["result"]["value"]
                assert restored_geom["htmlScrollWidth"] <= restored_geom["htmlClientWidth"] + 1, "Native geometry did not return to normal after removing spoiler"

            # 7. Click Expand button again to collapse
            client.call("Runtime.evaluate", {
                "expression": "document.querySelector('.p261a-expand-btn').click()",
                "returnByValue": True
            })
            time.sleep(0.15)

            # Measure Post-Collapse geometry natively
            post_collapsed_geom = client.call("Runtime.evaluate", {
                "expression": """
                    (function() {
                        return {
                            htmlScrollWidth: document.documentElement.scrollWidth,
                            htmlClientWidth: document.documentElement.clientWidth,
                            bodyScrollWidth: document.body.scrollWidth,
                            bodyClientWidth: document.body.clientWidth
                        };
                    })()
                """,
                "returnByValue": True
            })["result"]["result"]["value"]

            # Log native geometry metrics for compliance report
            print(f"\n--- Viewport {vp['name']} Native Geometry Metrics ---")
            print(f"Collapsed: htmlScroll={collapsed_geom['htmlScrollWidth']}, htmlClient={collapsed_geom['htmlClientWidth']}, bodyScroll={collapsed_geom['bodyScrollWidth']}, bodyClient={collapsed_geom['bodyClientWidth']}")
            print(f"Expanded: htmlScroll={expanded_geom['htmlScrollWidth']}, htmlClient={expanded_geom['htmlClientWidth']}, bodyScroll={expanded_geom['bodyScrollWidth']}, bodyClient={expanded_geom['bodyClientWidth']}")
            print(f"Post-Collapse: htmlScroll={post_collapsed_geom['htmlScrollWidth']}, htmlClient={post_collapsed_geom['htmlClientWidth']}, bodyScroll={post_collapsed_geom['bodyScrollWidth']}, bodyClient={post_collapsed_geom['bodyClientWidth']}")

            # Assert genuine viewport dimensions and Scale factor
            innerWidth = client.call("Runtime.evaluate", {"expression": "window.innerWidth", "returnByValue": True})["result"]["result"]["value"]
            clientWidth = client.call("Runtime.evaluate", {"expression": "document.documentElement.clientWidth", "returnByValue": True})["result"]["result"]["value"]
            visualViewportWidth = client.call("Runtime.evaluate", {"expression": "window.visualViewport ? window.visualViewport.width : window.innerWidth", "returnByValue": True})["result"]["result"]["value"]
            devicePixelRatio = client.call("Runtime.evaluate", {"expression": "window.devicePixelRatio", "returnByValue": True})["result"]["result"]["value"]

            if not vp["mobile"]:
                assert abs(innerWidth - vp['width']) <= 1, f"Expected innerWidth to be {vp['width']}±1, got {innerWidth}"
                scrollbarInset = innerWidth - clientWidth
                assert 0 <= scrollbarInset <= 20, f"Expected scrollbarInset between 0 and 20 inclusive, got {scrollbarInset}"
                assert 0 <= (innerWidth - visualViewportWidth) <= 20, f"Expected visualViewport scrollbar inset to be between 0 and 20 inclusive, got {innerWidth - visualViewportWidth}"
            else:
                assert abs(innerWidth - vp['width']) <= 1, f"Expected innerWidth to be {vp['width']}±1, got {innerWidth}"
                assert abs(clientWidth - vp['width']) <= 1, f"Expected clientWidth to be {vp['width']}±1, got {clientWidth}"
                assert abs(visualViewportWidth - vp['width']) <= 1, f"Expected visualViewport.width to be {vp['width']}±1, got {visualViewportWidth}"
            if vp["mobile"]:
                assert devicePixelRatio == 2, f"Expected devicePixelRatio to be 2 for mobile, got {devicePixelRatio}"

            # Prepare metrics results object and inject it to DOM to satisfy legacy validation
            metrics = {
                "scrollWidth": expanded_geom["htmlScrollWidth"],
                "clientWidth": expanded_geom["htmlClientWidth"],
                "overflow": (expanded_geom["htmlScrollWidth"] > (expanded_geom["htmlClientWidth"] + 1)) or (expanded_geom["bodyScrollWidth"] > (expanded_geom["bodyClientWidth"] + 1)),
                "btnRect": btn_rect,
                "btnInBounds": btn_rect["right"] <= vp["width"] and btn_rect["left"] >= 0
            }
            metrics_json = json.dumps(metrics)
            client.call("Runtime.evaluate", {
                "expression": f"""
                    (function() {{
                        var div = document.createElement('div');
                        div.id = 'rwd-metrics-result';
                        div.style.display = 'none';
                        div.textContent = {json.dumps(metrics_json)};
                        document.body.appendChild(div);
                    }})()
                """,
                "returnByValue": True
            })

            # Check if there is actual content overflow
            if metrics["overflow"]:
                print(f"STOP ERROR: Real native content overflow detected in viewport {vp['name']}!")
                print(f"htmlScrollWidth: {expanded_geom['htmlScrollWidth']}, htmlClientWidth: {expanded_geom['htmlClientWidth']}")
                print(f"bodyScrollWidth: {expanded_geom['bodyScrollWidth']}, bodyClientWidth: {expanded_geom['bodyClientWidth']}")

            # Capture viewport screenshot (NOT full page screenshot) via CDP
            shot_res = client.call("Page.captureScreenshot", {"format": "png"})
            img_data = base64.b64decode(shot_res["result"]["data"])
            with open(screenshot_path, "wb") as f:
                f.write(img_data)

            client.close()

            # Final normal assertions
            assert metrics["overflow"] is False, f"Viewport {vp['name']} has page-level horizontal overflow: scrollWidth={metrics['scrollWidth']}, clientWidth={metrics['clientWidth']}"
            assert metrics["btnInBounds"] is True, f"Expand/collapse button not in viewport bounds for {vp['name']}: {metrics['btnRect']}"

    finally:
        if chrome_proc:
            chrome_proc.terminate()
            chrome_proc.wait()
        shutil.rmtree(temp_profile, ignore_errors=True)
        server.shutdown()
        server.server_close()
        t.join()
