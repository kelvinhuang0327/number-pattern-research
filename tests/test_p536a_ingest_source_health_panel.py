"""Focused static tests for the P536A_FAST ingest source health panel."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
INDEX_HTML = REPO_ROOT / "index.html"
AUTO_FETCH_JS = REPO_ROOT / "src" / "ui" / "AutoFetchManager.js"
INGEST_ROUTE = REPO_ROOT / "lottery_api" / "routes" / "ingest.py"


def _html() -> str:
    return INDEX_HTML.read_text(encoding="utf-8")


def _js() -> str:
    return AUTO_FETCH_JS.read_text(encoding="utf-8")


def _source_health_script() -> str:
    return _js().split("// P536A_FAST: read-only source health panel", 1)[1].split(
        "// ─── Fetch Latest", 1
    )[0]


def test_existing_ingest_status_endpoint_is_read_only_source_health() -> None:
    route = INGEST_ROUTE.read_text(encoding="utf-8")
    status_route = route.split('@router.get("/api/ingest/status")', 1)[1].split(
        '@router.post("/api/ingest/fetch-latest")', 1
    )[0]

    assert '@router.get("/api/ingest/status")' in route
    assert "fetcher.check_source(lt)" in status_route
    assert '"overall_ok"' in status_route
    assert '"sources"' in status_route


def test_source_health_panel_is_visible_in_auto_fetch_section() -> None:
    html = _html()
    auto_fetch = html.split('class="af-section"', 1)[1].split(
        '<!-- P535A/G03: fetch-latest write-capable insert confirmation modal -->', 1
    )[0]

    assert "<!-- P536A_FAST: read-only official source health panel -->" in auto_fetch
    assert 'id="af-source-health-btn"' in auto_fetch
    assert 'id="af-source-health-status"' in auto_fetch
    assert 'id="af-source-health-results"' in auto_fetch
    assert "官網來源狀態" in auto_fetch
    assert "不查詢 DB、不寫入" in auto_fetch


def test_source_health_ui_uses_existing_get_endpoint_only() -> None:
    script = _source_health_script()

    assert "sourceHealthBtn?.addEventListener('click', () => this._onSourceHealth())" in _js()
    assert "fetch(getApiUrl('/api/ingest/status'))" in script
    assert "json.sources || {}" in script
    assert "Boolean(json.overall_ok)" in script

    for forbidden in (
        "/api/ingest/fetch-latest",
        "/api/ingest/backfill",
        "/api/ingest/log/clear",
        "POST",
        "DELETE",
        "PUT",
        "PATCH",
        "method:",
    ):
        assert forbidden not in script


def test_source_health_renders_per_lottery_state_safely() -> None:
    script = _source_health_script()

    for expected in (
        "_buildSourceHealthHtml",
        "Object.entries(sources)",
        "source?.latest_draw || {}",
        "source?.ok ?",
        "latest.draw ||",
        "latest.date ||",
        "source?.parsed_count",
        "source?.error ||",
        "_esc(label)",
        "_esc(latestDraw)",
        "_esc(latestDate)",
        "_esc(parsedCount)",
        "_esc(error)",
        "無來源狀態",
    ):
        assert expected in script


def test_source_health_change_stays_no_db_non_mutating_and_non_predictive() -> None:
    script = _source_health_script()

    for forbidden in (
        "sqlite",
        "lottery_v2.db",
        "/api/predict",
        "/api/cache/clear",
        "winning",
        "edge",
        "betting",
    ):
        assert forbidden not in script


def test_loading_button_state_restores_icon_markup_after_request() -> None:
    script = _js()
    helper = script.split("_setBtnLoading(btn, loading) {", 1)[1].split(
        "\n    }\n}", 1
    )[0]

    assert "btn.dataset.originalHtml = btn.innerHTML" in helper
    assert "btn.textContent = '處理中...'" in helper
    assert "btn.innerHTML = btn.dataset.originalHtml" in helper
    assert "delete btn.dataset.originalHtml" in helper
    assert "dataset._origText" not in helper
