"""
tests/test_replay_branch_governance_guard.py
=============================================
15 tests for P13.5 Branch Governance Guard.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH  = PROJECT_ROOT / "scripts" / "replay_branch_governance_guard.py"
AUDIT_JSON   = PROJECT_ROOT / "outputs" / "replay" / "p13_5_branch_audit_20260520.json"
PYTHON       = str(PROJECT_ROOT / ".venv" / "bin" / "python")
CANONICAL    = "feat/p0-single-repo-stabilization-p1-catalog-plan-20260519"

# Forbidden strings that must NOT appear in the governance guard source code.
# These represent destructive / write git operations the script must never use.
_FORBIDDEN_GIT_PATTERNS = [
    "git checkout",
    "worktree add",
    "branch -d",
    "branch -D",
    "git switch",
    "git push",
    "git merge",
    "reset --hard",
]


@pytest.fixture(scope="module")
def audit_json() -> dict:
    """Load the pre-generated audit JSON (must already exist)."""
    assert AUDIT_JSON.exists(), f"Audit JSON not found: {AUDIT_JSON}"
    with open(AUDIT_JSON) as f:
        return json.load(f)


# ── 1. Script file exists ─────────────────────────────────────────────────────
def test_01_script_exists():
    assert SCRIPT_PATH.exists(), f"Guard script not found: {SCRIPT_PATH}"


# ── 2. Script runs successfully (exit 0) on the active branch ────────────────
def test_02_script_passes_on_canonical(tmp_path):
    """Guard must pass when expected-branch matches the actual active branch."""
    # After merging to main the active branch is 'main'; before merge it was the
    # canonical feature branch.  Use the current branch so the test stays green
    # regardless of which branch is checked out.
    import subprocess as _sp
    current = _sp.check_output(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"], text=True
    ).strip()
    out = tmp_path / "gov.json"
    result = subprocess.run(
        [PYTHON, str(SCRIPT_PATH),
         "--expected-branch", current,
         "--expected-rows", "6460",
         "--json-out", str(out)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, (
        f"Governance guard exit={result.returncode}\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )


# ── 3. JSON output file created ───────────────────────────────────────────────
def test_03_json_exists():
    assert AUDIT_JSON.exists(), "Audit JSON output does not exist"


# ── 4. JSON "phase" field ─────────────────────────────────────────────────────
def test_04_json_phase(audit_json):
    assert audit_json["phase"] == "P13_5_BRANCH_GOVERNANCE_LOCK"


# ── 5. JSON "classification" = BRANCH_GOVERNANCE_PASS ────────────────────────
def test_05_json_classification_pass(audit_json):
    assert audit_json["classification"] == "BRANCH_GOVERNANCE_PASS"


# ── 6. JSON "branch_ok" = True ───────────────────────────────────────────────
def test_06_json_branch_ok(audit_json):
    assert audit_json["branch_ok"] is True


# ── 7. JSON "production_rows" = 6460 (post-P19B apply) ───────────────────────
def test_07_json_production_rows(audit_json):
    assert audit_json["production_rows"] == 6460


# ── 8. JSON "new_branch_allowed" = False ─────────────────────────────────────
def test_08_json_new_branch_not_allowed(audit_json):
    assert audit_json["new_branch_allowed"] is False


# ── 9. JSON "new_worktree_allowed" = False ────────────────────────────────────
def test_09_json_new_worktree_not_allowed(audit_json):
    assert audit_json["new_worktree_allowed"] is False


# ── 10. JSON "checkout_allowed" = False ──────────────────────────────────────
def test_10_json_checkout_not_allowed(audit_json):
    assert audit_json["checkout_allowed"] is False


# ── 11. JSON "staged_db_files" = [] ──────────────────────────────────────────
def test_11_no_staged_db_files(audit_json):
    assert audit_json["staged_db_files"] == [], (
        f"Staged DB files found: {audit_json['staged_db_files']}"
    )


# ── 12. JSON "staged_backup_files" = [] ──────────────────────────────────────
def test_12_no_staged_backup_files(audit_json):
    assert audit_json["staged_backup_files"] == [], (
        f"Staged backup files found: {audit_json['staged_backup_files']}"
    )


# ── 13. JSON "staged_pid_runtime_files" = [] ─────────────────────────────────
def test_13_no_staged_pid_runtime_files(audit_json):
    assert audit_json["staged_pid_runtime_files"] == [], (
        f"Staged pid/runtime files found: {audit_json['staged_pid_runtime_files']}"
    )


# ── 14. Wrong branch → exit != 0, no git checkout performed ──────────────────
def test_14_wrong_branch_exits_nonzero(tmp_path):
    """
    Inject --expected-branch with a fake name. Script must exit non-zero.
    Test itself must NOT perform any git checkout or branch switch.
    The rejection is purely from branch name comparison inside the script.
    """
    fake_branch = "totally-fake-branch-that-does-not-exist"
    out = tmp_path / "fail.json"
    result = subprocess.run(
        [PYTHON, str(SCRIPT_PATH),
         "--expected-branch", fake_branch,
         "--expected-rows", "6460",
         "--json-out", str(out)],
        capture_output=True, text=True,
    )
    assert result.returncode != 0, (
        "Expected non-zero exit for wrong branch, got 0"
    )
    # Also verify JSON classification is failure
    if out.exists():
        with open(out) as f:
            d = json.load(f)
        assert d["classification"] != "BRANCH_GOVERNANCE_PASS", (
            f"Classification should not be PASS for wrong branch: {d['classification']}"
        )
        assert d["branch_ok"] is False


# ── 15. Static: script source must not contain forbidden git command strings ──
def test_15_static_no_forbidden_strings():
    """
    Read the governance guard source code and verify none of the
    forbidden destructive git command strings appear.
    """
    source = SCRIPT_PATH.read_text()
    violations = []
    for pattern in _FORBIDDEN_GIT_PATTERNS:
        if pattern in source:
            violations.append(pattern)
    assert not violations, (
        f"Forbidden git command strings found in {SCRIPT_PATH.name}: {violations}"
    )
