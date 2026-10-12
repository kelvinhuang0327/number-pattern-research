"""P573A focused static tests for upload-guidance render safety.

No DB, no service startup, no runtime writes: these assertions verify
stats-derived guidance counts are rendered as text instead of interpolated HTML.
"""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
FILE_UPLOAD_HANDLER_JS = (
    REPO_ROOT / "src" / "core" / "handlers" / "FileUploadHandler.js"
)


def _script() -> str:
    return FILE_UPLOAD_HANDLER_JS.read_text(encoding="utf-8")


def _show_upload_guidance_helper() -> str:
    script = _script()
    return script.split("    showUploadGuidance(stats) {", 1)[1].split(
        "\n    /**\n     * 處理多個文件上傳", 1
    )[0]


def test_upload_guidance_renders_stats_counts_as_text_nodes() -> None:
    helper = _show_upload_guidance_helper()

    assert "const typeCountText = document.createElement('strong');" in helper
    assert "typeCountText.textContent = String(typeCount);" in helper
    assert "const totalDrawsText = document.createElement('strong');" in helper
    assert "totalDrawsText.textContent = String(totalDraws);" in helper
    assert "description.appendChild(document.createElement('br'));" in helper
    assert "guidanceContent.textContent = '';" in helper
    assert "guidanceContent.appendChild(title);" in helper
    assert "guidanceContent.appendChild(description);" in helper


def test_upload_guidance_does_not_interpolate_stats_into_html() -> None:
    helper = _show_upload_guidance_helper()

    assert "guidanceContent.innerHTML" not in helper
    assert "${typeCount}" not in helper
    assert "${totalDraws}" not in helper


def test_upload_guidance_fix_does_not_add_dependency_or_runtime_behavior() -> None:
    helper = _show_upload_guidance_helper()

    for forbidden in (
        "DOMPurify",
        "sanitize",
        "fetch(",
        "sqlite",
        "lottery_v2.db",
        "start_all",
        "scheduler",
        "localStorage",
        "indexedDB",
    ):
        assert forbidden not in helper
