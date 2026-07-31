"""
tests/conftest.py — CI DB Fixture Guard
=======================================
Skips tests marked @pytest.mark.requires_db when the SQLite replay
database fixture is unavailable.

DB path resolution order:
  1. LOTTERY_TEST_DB_PATH environment variable (override for CI / simulation)
  2. lottery_api/data/lottery_v2.db  (default local path)

Rules:
  - Never creates, downloads, writes, or modifies the DB.
  - Skip message explicitly names the path that was checked.
  - Non-DB tests are never affected.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).parent.parent
_DEFAULT_DB_PATH = _REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"


def _get_db_path() -> Path:
    """Return the DB path, honouring LOTTERY_TEST_DB_PATH env override."""
    env_override = os.environ.get("LOTTERY_TEST_DB_PATH")
    if env_override:
        return Path(env_override)
    return _DEFAULT_DB_PATH


def pytest_runtest_setup(item: pytest.Item) -> None:
    """Skip any test marked requires_db when the DB fixture is unavailable."""
    if item.get_closest_marker("requires_db") is not None:
        db_path = _get_db_path()
        if not db_path.exists():
            pytest.skip(
                f"requires local SQLite replay database fixture "
                f"(checked: {db_path})"
            )
