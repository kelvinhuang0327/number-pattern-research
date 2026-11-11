"""
tests/test_run_mlb_context_safety_audit.py

P12: Integration tests for scripts/run_mlb_context_safety_audit.py CLI.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_VENV_PYTHON = _REPO_ROOT / ".venv" / "bin" / "python"
_SCRIPT = _REPO_ROOT / "scripts" / "run_mlb_context_safety_audit.py"


def _python() -> str:
    if _VENV_PYTHON.exists():
        return str(_VENV_PYTHON)
    return sys.executable


def _write_safe_jsonl(path: Path) -> None:
    import json as _json
    with path.open("w") as f:
        f.write(_json.dumps({
            "game_id": "2025-04-01_A_B",
            "rest_days_home": 3,
            "bullpen_usage_last_3d_home": 9.5,
        }) + "\n")


def _write_risk_jsonl(path: Path) -> None:
    import json as _json
    with path.open("w") as f:
        f.write(_json.dumps({
            "game_id": "2025-04-01_A_B",
            "home_score": 5,
            "away_score": 3,
            "home_win": 1,
            "winner": "home",
        }) + "\n")


# ─────────────────────────────────────────────────────────────────────────────
# § 1  Paper zone guard
# ─────────────────────────────────────────────────────────────────────────────

def test_context_safety_cli_refuses_non_paper_output_dir():
    result = subprocess.run(
        [
            _python(), str(_SCRIPT),
            "--root", "data",
            "--output-dir", "/tmp/not_paper_zone",
        ],
        capture_output=True, text=True,
    )
    assert result.returncode != 0
    assert "REFUSED" in result.stderr


# ─────────────────────────────────────────────────────────────────────────────
# § 2  Summary file creation
# ─────────────────────────────────────────────────────────────────────────────

def test_context_safety_cli_writes_summary_md():
    paper_root = _REPO_ROOT / "outputs/predictions/PAPER"
    out_dir = paper_root / "test_p12_ctx_safety_tmp"
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        result = subprocess.run(
            [
                _python(), str(_SCRIPT),
                "--root", "data/mlb_context",
                "--output-dir", str(out_dir),
            ],
            capture_output=True, text=True, timeout=60,
            cwd=str(_REPO_ROOT),
        )
        assert result.returncode == 0, (
            f"CLI failed\nSTDOUT: {result.stdout[-2000:]}\nSTDERR: {result.stderr[-2000:]}"
        )

        summary_path = out_dir / "context_safety_summary.md"
        assert summary_path.exists(), "context_safety_summary.md not created"

        audit_path = out_dir / "context_safety_audit.json"
        assert audit_path.exists(), "context_safety_audit.json not created"

        # Audit should have at least 1 file
        audit = json.loads(audit_path.read_text())
        assert audit["total_files"] >= 1

    finally:
        import shutil
        shutil.rmtree(out_dir, ignore_errors=True)


# ─────────────────────────────────────────────────────────────────────────────
# § 3  Output content validation
# ─────────────────────────────────────────────────────────────────────────────

def test_context_safety_cli_audit_json_has_files_key():
    paper_root = _REPO_ROOT / "outputs/predictions/PAPER"
    out_dir = paper_root / "test_p12_ctx_files_tmp"
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        result = subprocess.run(
            [
                _python(), str(_SCRIPT),
                "--root", "data/mlb_context",
                "--output-dir", str(out_dir),
            ],
            capture_output=True, text=True, timeout=60,
            cwd=str(_REPO_ROOT),
        )
        assert result.returncode == 0

        audit_path = out_dir / "context_safety_audit.json"
        audit = json.loads(audit_path.read_text())

        assert "files" in audit
        assert "total_files" in audit
        assert "safety_counts" in audit

        for fa in audit["files"]:
            assert "safety_status" in fa
            assert fa["safety_status"] in {"PREGAME_SAFE", "POSTGAME_RISK", "UNKNOWN"}

    finally:
        import shutil
        shutil.rmtree(out_dir, ignore_errors=True)


# ─────────────────────────────────────────────────────────────────────────────
# § 4  Multi-root scanning
# ─────────────────────────────────────────────────────────────────────────────

def test_context_safety_cli_multi_root_scan():
    paper_root = _REPO_ROOT / "outputs/predictions/PAPER"
    out_dir = paper_root / "test_p12_ctx_multiroot_tmp"
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        result = subprocess.run(
            [
                _python(), str(_SCRIPT),
                "--root", "data/mlb_context",
                "--output-dir", str(out_dir),
            ],
            capture_output=True, text=True, timeout=60,
            cwd=str(_REPO_ROOT),
        )
        assert result.returncode == 0
        # Should print summary to stdout
        assert "PREGAME" in result.stdout or "POSTGAME" in result.stdout or "UNKNOWN" in result.stdout or "files" in result.stdout.lower()

    finally:
        import shutil
        shutil.rmtree(out_dir, ignore_errors=True)


# ─────────────────────────────────────────────────────────────────────────────
# § 5  Stdout contains required fields
# ─────────────────────────────────────────────────────────────────────────────

def test_context_safety_cli_stdout_has_counts():
    paper_root = _REPO_ROOT / "outputs/predictions/PAPER"
    out_dir = paper_root / "test_p12_ctx_stdout_tmp"
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        result = subprocess.run(
            [
                _python(), str(_SCRIPT),
                "--root", "data/mlb_context",
                "--output-dir", str(out_dir),
            ],
            capture_output=True, text=True, timeout=60,
            cwd=str(_REPO_ROOT),
        )
        assert result.returncode == 0
        stdout = result.stdout
        # Should print file counts
        assert "Total files" in stdout or "files audited" in stdout.lower() or "PREGAME" in stdout

    finally:
        import shutil
        shutil.rmtree(out_dir, ignore_errors=True)


# ─────────────────────────────────────────────────────────────────────────────
# § 6  Summary markdown content
# ─────────────────────────────────────────────────────────────────────────────

def test_context_safety_cli_summary_md_contains_key_sections():
    paper_root = _REPO_ROOT / "outputs/predictions/PAPER"
    out_dir = paper_root / "test_p12_ctx_md_tmp"
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        result = subprocess.run(
            [
                _python(), str(_SCRIPT),
                "--root", "data/mlb_context",
                "--output-dir", str(out_dir),
            ],
            capture_output=True, text=True, timeout=60,
            cwd=str(_REPO_ROOT),
        )
        assert result.returncode == 0

        md = (out_dir / "context_safety_summary.md").read_text()
        assert "Context Safety" in md
        assert "PREGAME" in md or "POSTGAME" in md or "UNKNOWN" in md
        assert "paper_only" in md

    finally:
        import shutil
        shutil.rmtree(out_dir, ignore_errors=True)
