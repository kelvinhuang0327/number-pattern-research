"""P562A focused static tests for batch upload file-info render safety.

No DB, no service startup, no runtime writes: these assertions verify
user-selected file names are rendered as text instead of interpolated HTML.
"""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
FILE_UPLOAD_HANDLER_JS = (
    REPO_ROOT / "src" / "core" / "handlers" / "FileUploadHandler.js"
)


def _script() -> str:
    return FILE_UPLOAD_HANDLER_JS.read_text(encoding="utf-8")


def _handle_multiple_file_upload_helper() -> str:
    script = _script()
    return script.split("async handleMultipleFileUpload(files) {", 1)[1].split(
        "\n    /**\n     * Render batch upload result details", 1
    )[0]


def _render_batch_file_info_helper() -> str:
    script = _script()
    return script.split("renderBatchFileInfo(fileInfo, fileResults, successCount) {", 1)[
        1
    ].split("\n    /**\n     * 載入範例數據", 1)[0]


def test_batch_upload_file_info_uses_text_nodes_for_file_names() -> None:
    helper = _render_batch_file_info_helper()

    assert "document.createTextNode(`• ${f.name}: ${displayCount} 筆`)" in helper
    assert "row.textContent = `• ${f.name}`;" in helper
    assert "added.textContent = ` (${f.count} 新增)`;" in helper
    assert "fileInfo.textContent = '';" in helper
    assert "fileInfo.appendChild(container);" in helper


def test_batch_upload_file_info_does_not_assign_html() -> None:
    helper = _render_batch_file_info_helper()
    upload_helper = _handle_multiple_file_upload_helper()

    assert "this.renderBatchFileInfo(fileInfo, fileResults, successCount);" in upload_helper
    assert "fileInfo.innerHTML" not in upload_helper
    assert "fileInfo.innerHTML" not in helper
    assert "html +=" not in helper
    assert "<br>" not in helper


def test_render_safety_fix_does_not_add_dependency_or_runtime_behavior() -> None:
    helper = _render_batch_file_info_helper()

    for forbidden in (
        "DOMPurify",
        "sanitize",
        "fetch(",
        "sqlite",
        "lottery_v2.db",
        "start_all",
        "scheduler",
        "localStorage",
    ):
        assert forbidden not in helper
