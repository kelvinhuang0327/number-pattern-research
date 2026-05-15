#!/usr/bin/env python3
"""
Unified prediction API smoke-test entrypoint.

Run from project root:
  python3 tools/verify_prediction_api.py
"""
from __future__ import annotations

import asyncio
import os
import sys


def _bootstrap_path() -> None:
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    lottery_api_root = os.path.join(repo_root, "lottery_api")
    if lottery_api_root not in sys.path:
        sys.path.insert(0, lottery_api_root)


def main() -> int:
    _bootstrap_path()
    from tools.smoke_test_coordinator_api import main as smoke_main  # type: ignore
    from tools.contract_test_prediction_api import main as contract_main  # type: ignore

    asyncio.run(smoke_main())
    asyncio.run(contract_main())
    print("OK: unified prediction API smoke + contract tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
