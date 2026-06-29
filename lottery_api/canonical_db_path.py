"""Policy-A canonical SQLite database path resolver.

This helper is intentionally pure stdlib path validation: no project imports,
no sqlite imports, no directory creation, and no process-CWD fallback.
"""

from pathlib import Path
from typing import Optional, Union


PathLike = Union[str, Path]


def repo_root() -> Path:
    """Return the repository root derived from this source file location."""
    return Path(__file__).resolve().parent.parent


def canonical_db_path() -> Path:
    """Return the source-location anchored canonical lottery DB path."""
    return repo_root() / "lottery_api" / "data" / "lottery_v2.db"


def _existing_regular_file(path: Path) -> str:
    """Return an absolute DB path only when it is an existing regular file."""
    if not path.exists():
        raise FileNotFoundError(f"Lottery DB path does not exist: {path}")
    if not path.is_file():
        raise FileNotFoundError(f"Lottery DB path is not a regular file: {path}")
    return str(path)


def resolve_db_path(db_path: Optional[PathLike] = None) -> str:
    """Validate and return a DB path without any fallback selection.

    ``None`` selects the source-anchored worktree-local canonical DB. That
    default must already exist as a regular file. Explicit custom paths must be
    absolute existing regular files; relative custom paths are rejected before
    any SQLite connection attempt can occur.
    """
    if db_path is None:
        return _existing_regular_file(canonical_db_path())

    candidate = Path(db_path)
    if not candidate.is_absolute():
        raise ValueError(
            "db_path must be an absolute path; use None for the canonical "
            "lottery_api/data/lottery_v2.db"
        )
    return _existing_regular_file(candidate)
