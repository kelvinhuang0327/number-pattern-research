"""Focused static tests for the P528A_FAST Replay public strategy filter."""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
INDEX_HTML = REPO_ROOT / "index.html"


def _html() -> str:
    return INDEX_HTML.read_text(encoding="utf-8")


def _replay_script() -> str:
    return _html().split("// ===== REPLAY PAGE JS", 1)[1].split("// ===== P95", 1)[0]


def _public_only_snippet() -> str:
    script = _replay_script()
    return "\n".join(
        line
        for line in script.splitlines()
        if "publicOnly" in line
        or "public_only" in line
        or "rp-public-only-strategies" in line
        or "publicOnlyStrategies" in line
    )


def test_public_only_control_is_in_replay_filter_bar() -> None:
    html = _html()
    filters = html.split('id="rp-lifecycle-select"', 1)[1].split(
        'id="rp-query-btn"', 1
    )[0]

    assert 'id="rp-public-only-strategies"' in filters
    assert 'type="checkbox"' in filters
    assert '策略清單只顯示公開狀態' in filters
    assert 'id="rp-strategy-select"' in filters


def test_strategy_loader_uses_existing_read_only_public_only_parameter() -> None:
    script = _replay_script()

    assert "const publicOnly = document.getElementById('rp-public-only-strategies')" in script
    assert "url += '&public_only=true';" in script
    assert "fetch(url)" in script
    assert "`${BASE}/strategies?lottery_type=${lt}`" in script
    assert "method:" not in script


def test_public_only_filter_preserves_default_lifecycle_behavior() -> None:
    script = _replay_script()

    assert "if (publicOnly) {" in script
    assert "} else if (lc) {" in script
    assert "url += `&lifecycle_status=${encodeURIComponent(lc)}`;" in script
    assert "public_only=true" in script


def test_public_only_filter_reload_and_url_state_are_wired() -> None:
    script = _replay_script()

    assert "rp_public_only" in script
    assert "params.set('rp_public_only', 'true')" in script
    assert "publicOnlyToggle.checked" in script
    assert "publicOnlyStrategies.addEventListener('change'" in script
    assert "rpLoadStrategies();" in script
    assert "rpUpdateURL();" in script


def test_public_only_filter_does_not_add_db_prediction_or_mutation_behavior() -> None:
    snippet = _public_only_snippet()

    for forbidden in (
        "sqlite",
        "lottery_v2.db",
        "/api/predict",
        "/api/cache/clear",
        "fetch-latest",
        "POST",
        "DELETE",
        "PUT",
        "PATCH",
        "method:",
    ):
        assert forbidden not in snippet
