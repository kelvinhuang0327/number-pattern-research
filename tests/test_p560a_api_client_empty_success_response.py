"""P560A focused static tests for ApiClient empty success response handling.

No DB, no service startup, no runtime artifacts: these assertions cover the
frontend client contract for successful HTTP responses with no JSON body.
"""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
API_CLIENT = REPO_ROOT / "src" / "services" / "ApiClient.js"


def _script() -> str:
    return API_CLIENT.read_text(encoding="utf-8")


def _request_method() -> str:
    script = _script()
    return script.split("    async request(endpoint, options = {}) {", 1)[1].split(
        "\n    /**\n     * GET 請求", 1
    )[0]


def _parse_response_body_helper() -> str:
    script = _script()
    return script.split("    async _parseResponseBody(response) {", 1)[1].split(
        "\n    }\n\n    // ===== 數據管理 API =====", 1
    )[0]


def test_request_uses_shared_success_response_parser() -> None:
    method = _request_method()

    assert "return await this._parseResponseBody(response);" in method
    assert "return await response.json();" not in method


def test_success_response_parser_accepts_no_content_success() -> None:
    helper = _parse_response_body_helper()

    assert "response.status === 204 || response.status === 205" in helper
    assert "return null;" in helper
    assert "const body = await response.text();" in helper
    assert "if (!body.trim()) {" in helper
    assert "return JSON.parse(body);" in helper


def test_empty_success_response_change_does_not_add_runtime_or_data_behavior() -> None:
    helper = _parse_response_body_helper()

    for forbidden in (
        "sqlite",
        "lottery_v2.db",
        "start_all",
        "scheduler",
        "localStorage",
        "indexedDB",
        "fetch(",
    ):
        assert forbidden not in helper
