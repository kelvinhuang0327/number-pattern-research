"""
tests/test_run_mlb_feature_family_ablation.py

P12: Integration tests for scripts/run_mlb_feature_family_ablation.py CLI.
"""
from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_VENV_PYTHON = _REPO_ROOT / ".venv" / "bin" / "python"
_SCRIPT = _REPO_ROOT / "scripts" / "run_mlb_feature_family_ablation.py"
_P11_CSV = _REPO_ROOT / "outputs/predictions/PAPER/2026-05-11/mlb_odds_with_feature_candidate_probabilities.csv"


def _python() -> str:
    if _VENV_PYTHON.exists():
        return str(_VENV_PYTHON)
    return sys.executable


# ─────────────────────────────────────────────────────────────────────────────
# § Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _write_minimal_csv(path: Path, n: int = 50) -> None:
    """Write a minimal P11-like CSV for testing."""
    rows = []
    for i in range(n):
        rows.append({
            "Date": f"2025-04-{(i % 28) + 1:02d}",
            "Home": "TeamA",
            "Away": "TeamB",
            "Away Score": "3",
            "Home Score": "5" if i % 2 == 0 else "2",
            "Status": "Final",
            "Home ML": "-150",
            "Away ML": "+130",
            "Away Starter": "PitcherB",
            "Home Starter": "PitcherA",
            "game_id": f"2025-04-{(i % 28) + 1:02d}_A_B_{i}",
            "paper_only": "True",
            "leakage_safe": "True",
            "model_prob_home": str(0.5 + (i % 10) * 0.01),
            "model_prob_away": str(0.5 - (i % 10) * 0.01),
            "raw_model_prob_home": "0.5",
            "raw_model_prob_before_p10": "0.5",
            "probability_source": "feature_candidate",
            "feature_candidate_mode": "feature_augmented",
            "indep_recent_win_rate_delta": str(0.1 * (i % 5 - 2)),
            "indep_rest_days_delta": str(float(i % 7 - 3)),
            "indep_bullpen_proxy_delta": str(float(i % 3)),
            "indep_starter_era_delta": str(float(i % 4 - 1)),
            "indep_home_recent_win_rate": "0.55",
            "indep_away_recent_win_rate": "0.45",
            "indep_home_rest_days": str(i % 5),
            "indep_away_rest_days": str((i + 2) % 5),
            "indep_rest_days_delta": str((i % 5) - ((i + 2) % 5)),
            "indep_wind_kmh": "12.5",
            "indep_temp_c": "18.0",
            "indep_park_roof_type": "open",
            "O/U": "8.5",
            "Over": "-110",
            "Under": "-110",
        })
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


# ─────────────────────────────────────────────────────────────────────────────
# § 1  Paper zone guard
# ─────────────────────────────────────────────────────────────────────────────

def test_ablation_cli_refuses_non_paper_output_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = Path(tmpdir) / "input.csv"
        _write_minimal_csv(csv_path, 30)
        result = subprocess.run(
            [
                _python(), str(_SCRIPT),
                "--input-csv", str(csv_path),
                "--output-dir", "/tmp/not_paper_zone",
            ],
            capture_output=True, text=True,
        )
        assert result.returncode != 0
        assert "REFUSED" in result.stderr


# ─────────────────────────────────────────────────────────────────────────────
# § 2  Basic run — no OOF / no simulation (just variant CSV writing)
# ─────────────────────────────────────────────────────────────────────────────

def test_ablation_cli_writes_leaderboard_csv(tmp_path):
    # Output dir under PAPER zone
    paper_root = _REPO_ROOT / "outputs/predictions/PAPER"
    out_dir = paper_root / "test_p12_ablation_tmp"
    out_dir.mkdir(parents=True, exist_ok=True)

    input_csv = out_dir / "test_input.csv"
    _write_minimal_csv(input_csv, 40)

    try:
        result = subprocess.run(
            [
                _python(), str(_SCRIPT),
                "--input-csv", str(input_csv),
                "--output-dir", str(out_dir),
                "--date-start", "2025-04-01",
                "--date-end", "2025-04-30",
            ],
            capture_output=True, text=True, timeout=120,
            cwd=str(_REPO_ROOT),
        )
        assert result.returncode == 0, (
            f"CLI failed\nSTDOUT: {result.stdout[-2000:]}\nSTDERR: {result.stderr[-2000:]}"
        )

        # Leaderboard should exist
        lb_path = out_dir / "ablation_leaderboard.csv"
        assert lb_path.exists(), "ablation_leaderboard.csv not created"

        # Plan should exist
        plan_path = out_dir / "ablation_plan.json"
        assert plan_path.exists(), "ablation_plan.json not created"

        # Results should exist
        results_path = out_dir / "ablation_results.json"
        assert results_path.exists(), "ablation_results.json not created"

        # Summary should exist
        summary_path = out_dir / "ablation_summary.md"
        assert summary_path.exists(), "ablation_summary.md not created"

        # Leaderboard should have at least 16 rows
        with lb_path.open(newline="") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) >= 16, f"Expected ≥16 rows in leaderboard, got {len(rows)}"

    finally:
        import shutil
        shutil.rmtree(out_dir, ignore_errors=True)


# ─────────────────────────────────────────────────────────────────────────────
# § 3  Leaderboard content validation
# ─────────────────────────────────────────────────────────────────────────────

def test_ablation_cli_leaderboard_has_all_variants():
    paper_root = _REPO_ROOT / "outputs/predictions/PAPER"
    out_dir = paper_root / "test_p12_lb_validate_tmp"
    out_dir.mkdir(parents=True, exist_ok=True)

    input_csv = out_dir / "test_input.csv"
    _write_minimal_csv(input_csv, 40)

    required_variants = {
        "all_features", "recent_only", "rest_only", "bullpen_only",
        "starter_only", "weather_only", "no_recent", "no_rest",
        "no_bullpen", "no_starter", "no_weather", "no_context_features",
        "recent_plus_rest", "starter_plus_bullpen", "recent_rest_starter",
        "market_or_base_only_baseline",
    }

    try:
        result = subprocess.run(
            [
                _python(), str(_SCRIPT),
                "--input-csv", str(input_csv),
                "--output-dir", str(out_dir),
                "--date-start", "2025-04-01",
                "--date-end", "2025-04-30",
            ],
            capture_output=True, text=True, timeout=120,
            cwd=str(_REPO_ROOT),
        )
        assert result.returncode == 0

        lb_path = out_dir / "ablation_leaderboard.csv"
        with lb_path.open(newline="") as f:
            rows = list(csv.DictReader(f))
        found_variants = {r["variant_name"] for r in rows}
        for req in required_variants:
            assert req in found_variants, f"Missing variant in leaderboard: {req}"

    finally:
        import shutil
        shutil.rmtree(out_dir, ignore_errors=True)


# ─────────────────────────────────────────────────────────────────────────────
# § 4  Missing input CSV
# ─────────────────────────────────────────────────────────────────────────────

def test_ablation_cli_refuses_missing_input():
    paper_root = _REPO_ROOT / "outputs/predictions/PAPER"
    out_dir = paper_root / "test_p12_missing_tmp"
    result = subprocess.run(
        [
            _python(), str(_SCRIPT),
            "--input-csv", "/tmp/does_not_exist_p12.csv",
            "--output-dir", str(out_dir),
        ],
        capture_output=True, text=True,
    )
    assert result.returncode != 0


# ─────────────────────────────────────────────────────────────────────────────
# § 5  OOF run with real P11 CSV (if available)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.skipif(
    not _P11_CSV.exists(),
    reason="P11 feature candidate CSV not present"
)
def test_ablation_cli_oof_run_with_real_data():
    """Smoke test: run ablation with --run-oof on real P11 CSV."""
    paper_root = _REPO_ROOT / "outputs/predictions/PAPER"
    out_dir = paper_root / "test_p12_oof_smoke_tmp"
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        result = subprocess.run(
            [
                _python(), str(_SCRIPT),
                "--input-csv", str(_P11_CSV),
                "--output-dir", str(out_dir),
                "--date-start", "2025-03-01",
                "--date-end", "2025-12-31",
                "--run-oof",
            ],
            capture_output=True, text=True, timeout=300,
            cwd=str(_REPO_ROOT),
        )
        assert result.returncode == 0, (
            f"STDOUT: {result.stdout[-3000:]}\nSTDERR: {result.stderr[-2000:]}"
        )

        results_path = out_dir / "ablation_results.json"
        assert results_path.exists()
        results = json.loads(results_path.read_text())
        assert len(results) >= 16

        # At least some variants should have oof_bss
        bss_values = [r.get("oof_bss") for r in results if r.get("oof_bss") is not None]
        assert len(bss_values) > 0, "No OOF BSS values computed"

    finally:
        import shutil
        shutil.rmtree(out_dir, ignore_errors=True)
