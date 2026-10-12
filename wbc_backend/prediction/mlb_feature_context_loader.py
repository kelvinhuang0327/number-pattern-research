"""
wbc_backend/prediction/mlb_feature_context_loader.py

P11: Context file discovery and loading for MLB independent features.

Discovers context files (bullpen, rest, weather, etc.) from specified root
directories and loads them into a unified in-memory bundle.

Supported formats:
  - JSONL  (.jsonl, .ndjson)
  - JSON   (.json)  — list of dicts, or {"rows": [...]} / {"items": [...]} / {"data": [...]}
  - CSV    (.csv)

Excluded paths:
  - .venv, .git, __pycache__, node_modules, build/

Safety: no production side effects, no API calls, no external writes.
paper_only = True always.
"""
from __future__ import annotations

import csv
import json
import pathlib
from typing import Any

__all__ = [
    "discover_context_files",
    "load_context_rows",
    "build_context_bundle",
]

# Directories to always skip during discovery
_SKIP_DIRS: set[str] = {
    ".venv",
    ".git",
    "__pycache__",
    "node_modules",
    "build",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
    "dist",
    "htmlcov",
}

# Context keywords that indicate a file is likely a context data source
_CONTEXT_KEYWORDS: list[str] = [
    "bullpen",
    "rest",
    "injury",
    "fatigue",
    "weather",
    "wind",
    "temp",
    "starter",
    "pitcher",
    "context",
    "park",
    "venue",
    "phase",
    "snapshot",
    "usage",
]

# Supported file extensions
_SUPPORTED_EXTS: set[str] = {".jsonl", ".ndjson", ".json", ".csv"}


# ---------------------------------------------------------------------------
# § 1  Discovery
# ---------------------------------------------------------------------------

def discover_context_files(
    root_paths: list[str] | None = None,
    base_dir: str | pathlib.Path | None = None,
) -> list[dict]:
    """
    Discover context data files under the given root paths.

    Parameters
    ----------
    root_paths : list[str] | None
        Root directory names to search. Defaults to ["data", "outputs", "reports"].
    base_dir : str | pathlib.Path | None
        Base directory for resolving root_paths. Defaults to current working dir.

    Returns
    -------
    list[dict]
        Sorted list of discovery records, each with:
        - ``path``: str — absolute file path
        - ``name``: str — filename
        - ``ext``: str — file extension
        - ``size_bytes``: int
        - ``likely_context``: bool — True if name contains a context keyword
        - ``context_keywords_found``: list[str]
        - ``format``: str — "jsonl" | "json" | "csv"
        - ``safe``: bool — always True (no unsafe discovery)
    """
    if root_paths is None:
        root_paths = ["data", "outputs", "reports"]
    if base_dir is None:
        base_dir = pathlib.Path.cwd()
    base = pathlib.Path(base_dir).resolve()

    results: list[dict] = []

    for root_name in root_paths:
        root = base / root_name
        if not root.exists():
            continue
        for fpath in _walk_safe(root):
            ext = fpath.suffix.lower()
            if ext not in _SUPPORTED_EXTS:
                continue
            name_lower = fpath.name.lower()
            kw_found = [k for k in _CONTEXT_KEYWORDS if k in name_lower]
            likely = len(kw_found) > 0
            fmt = _ext_to_format(ext)
            try:
                size = fpath.stat().st_size
            except OSError:
                size = 0
            results.append({
                "path": str(fpath),
                "name": fpath.name,
                "ext": ext,
                "size_bytes": size,
                "likely_context": likely,
                "context_keywords_found": kw_found,
                "format": fmt,
                "safe": True,
            })

    # Sort: likely context files first, then by path
    results.sort(key=lambda r: (not r["likely_context"], r["path"]))
    return results


def _walk_safe(root: pathlib.Path):
    """Yield all files under root, skipping excluded directories."""
    try:
        for item in root.rglob("*"):
            if not item.is_file():
                continue
            # Skip excluded directory components
            parts = item.parts
            if any(p in _SKIP_DIRS for p in parts):
                continue
            yield item
    except (PermissionError, OSError):
        return


def _ext_to_format(ext: str) -> str:
    if ext in (".jsonl", ".ndjson"):
        return "jsonl"
    if ext == ".json":
        return "json"
    if ext == ".csv":
        return "csv"
    return "unknown"


# ---------------------------------------------------------------------------
# § 2  Row loader
# ---------------------------------------------------------------------------

def load_context_rows(path: str | pathlib.Path) -> list[dict]:
    """
    Load rows from a context file.

    Supports JSONL, JSON (list or dict-with-list), and CSV.
    Returns an empty list on any parse error.

    Parameters
    ----------
    path : str | pathlib.Path
        Path to the context file.

    Returns
    -------
    list[dict]
        Loaded rows (empty if file is missing, empty, or unparseable).
    """
    p = pathlib.Path(path)
    if not p.exists():
        return []

    ext = p.suffix.lower()

    try:
        if ext in (".jsonl", ".ndjson"):
            return _load_jsonl(p)
        if ext == ".json":
            return _load_json(p)
        if ext == ".csv":
            return _load_csv(p)
    except Exception:
        return []

    return []


def _load_jsonl(path: pathlib.Path) -> list[dict]:
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            if isinstance(obj, dict):
                rows.append(obj)
        except json.JSONDecodeError:
            continue
    return rows


def _load_json(path: pathlib.Path) -> list[dict]:
    text = path.read_text(encoding="utf-8", errors="replace")
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        return []

    if isinstance(obj, list):
        return [r for r in obj if isinstance(r, dict)]
    if isinstance(obj, dict):
        for key in ("rows", "items", "data", "records", "games", "results"):
            if isinstance(obj.get(key), list):
                return [r for r in obj[key] if isinstance(r, dict)]
    return []


def _load_csv(path: pathlib.Path) -> list[dict]:
    rows: list[dict] = []
    try:
        with path.open(encoding="utf-8", errors="replace", newline="") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                rows.append(dict(row))
    except Exception:
        pass
    return rows


# ---------------------------------------------------------------------------
# § 3  Bundle builder
# ---------------------------------------------------------------------------

def build_context_bundle(
    paths: list[str | pathlib.Path],
) -> dict[str, Any]:
    """
    Load multiple context files and merge their rows into a single bundle dict.

    The bundle is structured as:
    {
        "bullpen": list[dict],   # rows from files whose name contains "bullpen"
        "rest": list[dict],      # rows from files whose name contains "rest" / "injury"
        "weather": list[dict],   # rows from files whose name contains "weather" / "wind"
        "starter": list[dict],   # rows from files whose name contains "starter" / "pitcher"
        "other": list[dict],     # everything else
        "_meta": {
            "files_loaded": int,
            "files_failed": int,
            "total_rows": int,
            "paths": list[str],
        }
    }

    Parameters
    ----------
    paths : list[str | pathlib.Path]
        Context file paths to load.

    Returns
    -------
    dict[str, Any]
        Bundle with categorised row lists.
    """
    bundle: dict[str, list[dict]] = {
        "bullpen": [],
        "rest": [],
        "weather": [],
        "starter": [],
        "other": [],
    }
    files_loaded = 0
    files_failed = 0
    total_rows = 0
    path_strs: list[str] = []

    for path in paths:
        p = pathlib.Path(path)
        name = p.name.lower()
        rows = load_context_rows(p)
        if not rows and not p.exists():
            files_failed += 1
            continue

        category = _classify_file(name)
        bundle[category].extend(rows)
        files_loaded += 1
        total_rows += len(rows)
        path_strs.append(str(p))

    bundle["_meta"] = {  # type: ignore[assignment]
        "files_loaded": files_loaded,
        "files_failed": files_failed,
        "total_rows": total_rows,
        "paths": path_strs,
    }
    return bundle  # type: ignore[return-value]


def _classify_file(name: str) -> str:
    """Return bundle category for a file based on its name."""
    if "bullpen" in name or "fatigue" in name:
        return "bullpen"
    if "rest" in name or "injury" in name:
        return "rest"
    if "weather" in name or "wind" in name or "temp" in name:
        return "weather"
    if "starter" in name or "pitcher" in name or "era" in name:
        return "starter"
    return "other"
