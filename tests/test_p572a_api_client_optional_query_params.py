"""P572A focused tests for ApiClient optional query parameter serialization.

No DB, no service startup, no runtime artifacts: these tests use Node with a
mocked fetch to verify the frontend client request contract.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
API_CLIENT = REPO_ROOT / "src" / "services" / "ApiClient.js"


def run_node(script: str) -> dict:
    result = subprocess.run(
        ["node", "--input-type=module", "-"],
        input=script,
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    return json.loads(result.stdout)


def test_get_omits_null_and_undefined_optional_query_params() -> None:
    script = """
        import { ApiClient } from './src/services/ApiClient.js';

        const client = new ApiClient();
        client.baseUrl = 'http://example.test';
        let capturedUrl = '';
        globalThis.fetch = async (url) => {
          capturedUrl = url;
          return {
            ok: true,
            status: 200,
            text: async () => '{}'
          };
        };

        await client.get('/api/data/draws', {
          lottery_type: undefined,
          page: null,
          sort: 'date'
        });

        console.log(JSON.stringify({ capturedUrl }));
    """

    payload = run_node(script)

    assert payload["capturedUrl"] == "http://example.test/api/data/draws?sort=date"
    assert "undefined" not in payload["capturedUrl"]
    assert "null" not in payload["capturedUrl"]


def test_get_preserves_meaningful_falsy_query_params() -> None:
    script = """
        import { ApiClient } from './src/services/ApiClient.js';

        const client = new ApiClient();
        client.baseUrl = 'http://example.test';
        let capturedUrl = '';
        globalThis.fetch = async (url) => {
          capturedUrl = url;
          return {
            ok: true,
            status: 200,
            text: async () => '{}'
          };
        };

        await client.get('/api/data/draws', {
          page: 0,
          include_empty: false,
          keyword: ''
        });

        console.log(JSON.stringify({ capturedUrl }));
    """

    payload = run_node(script)

    assert payload["capturedUrl"] == (
        "http://example.test/api/data/draws?"
        "page=0&include_empty=false&keyword="
    )


def test_optional_query_param_change_does_not_add_runtime_or_data_behavior() -> None:
    source = API_CLIENT.read_text(encoding="utf-8")
    helper = source.split("    _buildQueryString(params = {}) {", 1)[1].split(
        "\n    }\n\n    /**\n     * POST 請求", 1
    )[0]

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
