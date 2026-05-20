"""
test_replay_lifecycle_drift_guard.py
=====================================
Deterministic tests for the read-only Post-V3 replay lifecycle drift guard.

These tests:
  - Do NOT require the backend to be running
  - Do NOT write to the DB
  - Run the drift guard script via subprocess and parse its JSON output

Pre-backfill baseline (updated 2026-05-20 after P0-P13 main merge, PR #142):
  legacy=460  v1=0  v2=0  p2b=0  p2f=0  p3bc=0  total=460
  No Phase-1 backfill applied yet — all 460 rows are legacy with truth_level=null.
  V3 tombstone strategies: 0 rows each (acb_markov_midfreq_3bet promoted out of tombstone list)
  truth_level: only REGENERATED_RETROSPECTIVE / ARTIFACT_RECONSTRUCTED_RETROSPECTIVE / OFFICIAL / OFFICIAL_DRAW_RESULT / NULL
  Final classification: REPLAY_LIFECYCLE_DRIFT_GUARD_PASS
"""

import json
import pathlib
import subprocess
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "replay_lifecycle_drift_guard.py"

# Known V3 tombstone strategy IDs
# acb_markov_midfreq_3bet removed: 3 replay rows inserted via P3BC_RESOLVE_20260516
V3_CODE_MISSING_STRATEGY_IDS = [
    "acb_1bet",
    "acb_markov_midfreq",
    "midfreq_acb_2bet",
    "midfreq_fourier_2bet",
    "h6_gate_mk20_ew85",
]

ALLOWED_TRUTH_LEVELS = {
    "REGENERATED_RETROSPECTIVE",
    "ARTIFACT_RECONSTRUCTED_RETROSPECTIVE",
    "OFFICIAL",
    "OFFICIAL_DRAW_RESULT",
    "null",
}


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _run_drift_guard(tmp_path: pathlib.Path) -> tuple:
    """Run the drift guard script with --strict --json-out and return (exit_code, result_dict)."""
    json_out = tmp_path / "drift_guard_result.json"
    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--strict",
            "--json-out",
            str(json_out),
        ],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    if json_out.exists():
        result = json.loads(json_out.read_text())
    else:
        result = {}
    return proc.returncode, result


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestDriftGuardScript:
    """Test suite for replay_lifecycle_drift_guard.py."""

    def test_script_compiles(self):
        """The drift guard script must compile without syntax errors."""
        proc = subprocess.run(
            [sys.executable, "-m", "py_compile", str(SCRIPT_PATH)],
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 0, (
            f"Script failed to compile:\n{proc.stderr}"
        )

    def test_strict_mode_passes(self, tmp_path):
        """In --strict mode, the script must exit 0 and report status=PASS."""
        exit_code, result = _run_drift_guard(tmp_path)
        assert exit_code == 0, (
            f"Drift guard exited {exit_code} (expected 0).\n"
            f"Violations: {result.get('violations', 'no JSON output')}"
        )
        assert result.get("status") == "PASS", (
            f"Expected status=PASS, got {result.get('status')}.\n"
            f"Violations: {result.get('violations', [])}"
        )

    def test_json_output_schema(self, tmp_path):
        """Output JSON must contain all required top-level keys."""
        _, result = _run_drift_guard(tmp_path)
        required_keys = [
            "status",
            "checked_at",
            "db_path",
            "row_counts",
            "lifecycle_counts",
            "truth_level_counts",
            "controlled_apply_id_counts",
            "violations",
            "final_classification",
        ]
        for key in required_keys:
            assert key in result, f"Missing required key '{key}' in JSON output"

        # row_counts sub-keys
        row_counts = result["row_counts"]
        for sub in ("v1", "v2", "legacy", "total"):
            assert sub in row_counts, f"Missing row_counts.{sub}"

        # lifecycle_counts sub-keys
        lc = result["lifecycle_counts"]
        assert "v3_code_missing_zero_row_strategies" in lc
        assert "v3_fake_row_violations" in lc
        assert isinstance(lc["v3_fake_row_violations"], list)

    def test_no_v3_fake_rows(self, tmp_path):
        """All known V3 CODE_MISSING strategy IDs must have 0 rows in the replay table."""
        _, result = _run_drift_guard(tmp_path)
        fake_violations = result.get("lifecycle_counts", {}).get("v3_fake_row_violations", [])
        assert fake_violations == [], (
            f"V3 tombstone strategies with unexpected rows: {fake_violations}"
        )
        assert result["lifecycle_counts"]["v3_code_missing_zero_row_strategies"] == len(
            V3_CODE_MISSING_STRATEGY_IDS
        ), (
            f"Expected {len(V3_CODE_MISSING_STRATEGY_IDS)} zero-row V3 strategies, "
            f"got {result['lifecycle_counts']['v3_code_missing_zero_row_strategies']}"
        )

    def test_truth_level_enum_clean(self, tmp_path):
        """No unexpected truth_level values must exist in the replay table."""
        _, result = _run_drift_guard(tmp_path)
        truth_level_counts = result.get("truth_level_counts", {})
        unexpected = set(truth_level_counts.keys()) - ALLOWED_TRUTH_LEVELS
        assert unexpected == set(), (
            f"Unexpected truth_level values found: {unexpected}"
        )
        # Pre-backfill state: all 460 legacy rows carry truth_level=null, which is a valid
        # accepted condition before Phase-1 backfill is applied.  Populated enum values
        # (REGENERATED_RETROSPECTIVE, ARTIFACT_RECONSTRUCTED_RETROSPECTIVE, OFFICIAL) are
        # expected only after the controlled backfill apply is executed.  This test validates
        # enum integrity (no unexpected values), not backfill completeness.

    def test_db_counts_match_baseline(self, tmp_path):
        """DB row counts must match the pre-backfill baseline: legacy=460, total=460.

        Updated 2026-05-20 (PR #142): No Phase-1 backfill has been applied yet.
        All 460 rows are legacy rows; v1/v2/p2b/p2f/p3bc buckets are all 0.
        The legacy=460 and total=460 invariants are production-critical and must
        not change without an authorized controlled-apply.
        """
        _, result = _run_drift_guard(tmp_path)
        rc = result.get("row_counts", {})
        # Production-critical invariants — must equal 460 at all times pre-backfill
        assert rc.get("legacy") == 460, f"legacy count mismatch: {rc.get('legacy')} != 460"
        assert rc.get("total") == 460, f"total count mismatch: {rc.get('total')} != 460"
        # Pre-backfill: all versioned buckets must be 0 (no controlled apply yet)
        assert rc.get("v1") == 0, f"V1 count mismatch: {rc.get('v1')} != 0 (no backfill applied)"
        assert rc.get("v2") == 0, f"V2 count mismatch: {rc.get('v2')} != 0 (no backfill applied)"
        assert rc.get("p2b") == 0, f"P2B count mismatch: {rc.get('p2b')} != 0 (no backfill applied)"
        assert rc.get("p2f") == 0, f"P2F count mismatch: {rc.get('p2f')} != 0 (no backfill applied)"
        assert rc.get("p3bc") == 0, f"P3BC count mismatch: {rc.get('p3bc')} != 0 (no backfill applied)"
        # Final classification must always be PASS
        assert result.get("final_classification") == "REPLAY_LIFECYCLE_DRIFT_GUARD_PASS", (
            f"Unexpected final_classification: {result.get('final_classification')}"
        )
