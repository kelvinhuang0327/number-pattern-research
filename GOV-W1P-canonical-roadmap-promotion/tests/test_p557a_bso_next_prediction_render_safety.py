"""P557A focused static tests for BSO next-prediction render safety.

No DB, no service startup, no runtime artifacts: these assertions verify the
historical strategy overview mini-panel escapes API-provided prediction text
before writing its small HTML wrapper.
"""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
INDEX_HTML = REPO_ROOT / "index.html"


def _p95_script() -> str:
    html = INDEX_HTML.read_text(encoding="utf-8")
    return html.split("// ===== P95 HISTORICAL STRATEGY OVERVIEW JS =====", 1)[
        1
    ].split("// ===== P257 BEST STRATEGY OVERVIEW", 1)[0]


def _bso_load_pred() -> str:
    script = _p95_script()
    return script.split("  window.bsoLoadPred = async function(strategyId, lottery) {", 1)[
        1
    ].split("\n  };\n\n  // Wire up filter changes", 1)[0]


def test_bso_prediction_panel_has_local_html_escape_helper() -> None:
    script = _p95_script()

    assert "function bsoEscapeHtml(value)" in script
    assert "String(value ?? '').replace(/[&<>\"']/g" in script
    for escaped in ("&amp;", "&lt;", "&gt;", "&quot;", "&#39;"):
        assert escaped in script


def test_bso_ready_prediction_values_are_escaped_before_inner_html() -> None:
    helper = _bso_load_pred()

    assert "b.map(bsoEscapeHtml).join(', ')" in helper
    assert "const specialValue = bsoEscapeHtml(data.predicted_special);" in helper
    assert "const disclaimer = bsoEscapeHtml(data.disclaimer || '');" in helper
    assert "${data.predicted_special}" not in helper
    assert "${data.disclaimer}" not in helper


def test_bso_non_ready_status_and_disclaimer_are_escaped() -> None:
    helper = _bso_load_pred()

    assert "const statusLabel = bsoEscapeHtml(msgs[status] || status);" in helper
    assert "${statusLabel}" in helper
    assert "${msgs[status] || status}" not in helper
    assert "${data.disclaimer || ''}" not in helper


def test_bso_render_safety_fix_does_not_add_runtime_or_data_behavior() -> None:
    helper = _bso_load_pred()

    for forbidden in (
        "DOMPurify",
        "sanitize",
        "sqlite",
        "lottery_v2.db",
        "start_all",
        "scheduler",
        "POST",
        "DELETE",
        "PUT",
        "PATCH",
        "method:",
    ):
        assert forbidden not in helper
