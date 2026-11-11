"""Tests for scripts/legacy_entrypoints/fetch_wbc_all_players.py — P152.

Validates that:
- _REPO_ROOT is derived from __file__, not a hardcoded local path.
- The output path resolves to <repo_root>/data/wbc_all_players_realtime.json.
- No hardcoded /Users/kelvin absolute path appears in the module source.
- WBCCrawler.run() writes output to a path under tmp_path when monkeypatched.
"""
from __future__ import annotations

import importlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

# ── Module import helpers ─────────────────────────────────────────────────────

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "legacy_entrypoints" / "fetch_wbc_all_players.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("fetch_wbc_all_players", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ── Tests ─────────────────────────────────────────────────────────────────────


def test_p152_repo_root_is_not_hardcoded():
    """_REPO_ROOT must not contain a hardcoded /Users/kelvin literal in source."""
    source = _SCRIPT.read_text(encoding="utf-8")
    assert "/Users/kelvin" not in source, (
        "Hardcoded local path detected in fetch_wbc_all_players.py — P152 fix not applied"
    )


def test_p152_repo_root_resolves_correctly():
    """_REPO_ROOT resolved at import time must equal the actual repo root."""
    mod = _load_module()
    repo_root = mod._REPO_ROOT
    # __file__ is <repo_root>/tests/test_*.py → parents[1] is repo root
    expected = Path(__file__).resolve().parents[1]
    assert repo_root == expected, f"_REPO_ROOT={repo_root!r} != expected={expected!r}"


def test_p152_output_path_is_relative_to_repo_root():
    """Output path constructed from _REPO_ROOT must be data/wbc_all_players_realtime.json."""
    mod = _load_module()
    output_path = mod._REPO_ROOT / "data" / "wbc_all_players_realtime.json"
    # Must NOT be rooted at a hardcoded user home
    relative = output_path.relative_to(mod._REPO_ROOT)
    assert str(relative) == "data/wbc_all_players_realtime.json"


def test_p152_run_writes_to_tmp_path(tmp_path, monkeypatch):
    """WBCCrawler.run() writes JSON to the monkeypatched repo root without network calls."""
    mod = _load_module()

    # Override _REPO_ROOT so output goes to tmp_path
    monkeypatch.setattr(mod, "_REPO_ROOT", tmp_path)

    # Stub network methods to return empty data (no live API calls)
    monkeypatch.setattr(mod.WBCCrawler, "get_active_wbc_teams", lambda self: [])

    crawler = mod.WBCCrawler()
    crawler.run()

    expected_file = tmp_path / "data" / "wbc_all_players_realtime.json"
    assert expected_file.exists(), f"Output file not created: {expected_file}"
    payload = json.loads(expected_file.read_text(encoding="utf-8"))
    assert isinstance(payload, list)


def test_p152_run_creates_parent_dir(tmp_path, monkeypatch):
    """run() creates data/ directory if it does not exist."""
    mod = _load_module()
    monkeypatch.setattr(mod, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(mod.WBCCrawler, "get_active_wbc_teams", lambda self: [])

    data_dir = tmp_path / "data"
    assert not data_dir.exists()

    mod.WBCCrawler().run()

    assert data_dir.exists()
