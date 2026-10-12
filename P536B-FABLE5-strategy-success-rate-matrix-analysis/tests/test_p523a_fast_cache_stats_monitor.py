"""Focused static tests for the P523A_FAST read-only cache monitor."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
INDEX_HTML = REPO_ROOT / "index.html"


def _html() -> str:
    return INDEX_HTML.read_text(encoding="utf-8")


def test_cache_stats_panel_is_part_of_visible_replay_monitoring() -> None:
    html = _html()
    replay = html.split('id="replay-section"', 1)[1].split('id="tracking-section"', 1)[0]

    assert '<!-- Read-only model cache monitor -->' in replay
    assert 'id="cache-stats-panel"' in replay
    assert 'id="cache-stats-total"' in replay
    assert 'id="cache-stats-detail"' in replay
    assert 'id="refresh-cache-stats-btn"' in replay
    assert 'aria-live="polite"' in replay


def test_cache_stats_uses_existing_read_only_endpoint() -> None:
    html = _html()
    script = html.split("// P523A_FAST: read-only cache monitoring", 1)[1]

    assert "fetch(base + '/api/cache/stats')" in script
    assert "response.ok" in script
    assert "response.json()" in script
    assert "/api/cache/clear" not in script
    assert "method:" not in script


def test_cache_stats_renders_count_ttl_and_model_names() -> None:
    html = _html()
    script = html.split("// P523A_FAST: read-only cache monitoring", 1)[1]

    assert "payload.total_cached" in script
    assert "payload.cached_models" in script
    assert "payload.cache_ttl_hours" in script
    assert "models.join('、')" in script
    assert "目前沒有快取模型" in script


def test_cache_stats_has_loading_error_and_manual_refresh_states() -> None:
    html = _html()
    script = html.split("// P523A_FAST: read-only cache monitoring", 1)[1]

    assert "讀取中…" in script
    assert "無法讀取" in script
    assert "不影響其他功能" in script
    assert "refresh.disabled = true" in script
    assert "refresh.disabled = false" in script
    assert "refresh.addEventListener('click', loadCacheStats)" in script


def test_cache_stats_monitor_does_not_add_prediction_or_db_behavior() -> None:
    html = _html()
    script = html.split("// P523A_FAST: read-only cache monitoring", 1)[1]

    for forbidden in ("sqlite", "lottery_v2.db", "/api/predict", "提高中獎率"):
        assert forbidden not in script
