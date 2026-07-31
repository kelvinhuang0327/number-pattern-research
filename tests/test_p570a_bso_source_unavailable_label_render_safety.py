"""P570A focused static tests for BSO source-unavailable label render safety.

No DB, no service startup, no route changes. These assertions cover the Best
Strategy Overview SOURCE_UNAVAILABLE empty state, which writes an HTML fallback
and must escape the selected lottery label before interpolation.
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


def _bso_load() -> str:
    script = _p95_script()
    return script.split("  async function bsoLoad() {", 1)[1].split(
        "\n  }\n\n  window.bsoExpandCard", 1
    )[0]


def test_bso_source_unavailable_lottery_label_escapes_before_inner_html() -> None:
    helper = _bso_load()

    assert "function bsoEscapeHtml(value)" in _p95_script()
    assert "const lotteryLabel = bsoEscapeHtml(LOTTERY_LABELS[lottery] || lottery);" in helper
    assert "📭 ${lotteryLabel} 基準資料尚未就緒" in helper
    assert "📭 ${LOTTERY_LABELS[lottery] || lottery} 基準資料尚未就緒" not in helper


def test_bso_source_unavailable_fix_does_not_add_runtime_or_data_behavior() -> None:
    helper = _bso_load()

    for forbidden in (
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
