"""P550A focused static tests for SmartBetting wheel metadata render safety.

No DB, no service startup, no runtime artifacts: these assertions verify the
client renders wheel metadata text without interpolating API strings into HTML.
"""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
COMPONENT = REPO_ROOT / "src/ui/components/SmartBettingComponent.js"


def _component() -> str:
    return COMPONENT.read_text(encoding="utf-8")


def _render_results_block() -> str:
    script = _component()
    return script.split("    renderResults(combinations, originalCount, metadata = {}) {", 1)[
        1
    ].split("\n    async generateHedging()", 1)[0]


def test_wheel_metadata_disclaimer_uses_text_content_not_html_interpolation() -> None:
    block = _render_results_block()

    assert "const disclaimer = document.createElement('div');" in block
    assert "disclaimer.textContent = metadata.honest_disclaimer || '';" in block
    assert "${metadata.honest_disclaimer || ''}" not in block
    assert "metaInfo.innerHTML" not in block


def test_wheel_metadata_labels_are_built_with_dom_nodes() -> None:
    block = _render_results_block()

    for expected in (
        "const metaHeader = document.createElement('div');",
        "const sourceLabel = document.createElement('span');",
        "document.createTextNode('策略來源: ')",
        "const sourceValue = document.createElement('b');",
        "sourceValue.textContent = source;",
        "const verifiedLabel = document.createElement('span');",
        "verifiedLabel.textContent = isVerified;",
    ):
        assert expected in block


def test_render_safety_fix_does_not_add_dependency_or_runtime_behavior() -> None:
    block = _render_results_block()

    for forbidden in (
        "DOMPurify",
        "sanitize",
        "fetch(",
        "sqlite",
        "lottery_v2.db",
        "start_all",
        "scheduler",
    ):
        assert forbidden not in block
