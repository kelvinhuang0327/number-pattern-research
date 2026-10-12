"""P559A focused static tests for ApiClient request timeout cleanup.

No DB, no service startup, no runtime artifacts: these assertions verify that
each client request attempt clears its abort timer even when fetch/JSON handling
throws before the successful response path.
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


def test_request_timeout_id_is_scoped_per_attempt() -> None:
    method = _request_method()

    assert "for (let attempt = 0; attempt <= maxRetries; attempt++) {" in method
    assert "let timeoutId = null;" in method
    assert "timeoutId = setTimeout(() => controller.abort(), this.requestTimeout);" in method


def test_request_timeout_is_cleared_in_finally_for_all_paths() -> None:
    method = _request_method()
    finally_block = method.split("} finally {", 1)[1]

    assert "if (timeoutId) {" in finally_block
    assert "clearTimeout(timeoutId);" in finally_block


def test_request_cleanup_change_does_not_add_runtime_or_data_behavior() -> None:
    method = _request_method()

    for forbidden in (
        "sqlite",
        "lottery_v2.db",
        "start_all",
        "scheduler",
        "localStorage",
        "indexedDB",
        "WebSocket",
    ):
        assert forbidden not in method
