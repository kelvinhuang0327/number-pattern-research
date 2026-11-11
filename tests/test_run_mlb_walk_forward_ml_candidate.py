from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_mlb_walk_forward_ml_candidate.py"
PYTHON = str((ROOT / ".venv" / "bin" / "python")) if (ROOT / ".venv" / "bin" / "python").exists() else sys.executable


def _write_input_csv(path: Path, n: int = 240) -> None:
    fields = [
        "Date", "Home", "Away", "home_win", "Home Score", "Away Score", "Status",
        "Home ML", "Away ML", "game_id", "raw_model_prob_before_p10", "raw_model_prob_home",
        "indep_recent_win_rate_delta", "indep_starter_era_delta", "indep_bullpen_proxy_delta",
        "leakage_safe",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for i in range(n):
            month = 3 + (i // 60)
            day = (i % 28) + 1
            y = 1 if (i % 4) in {0, 1} else 0
            w.writerow(
                {
                    "Date": f"2025-{month:02d}-{day:02d}",
                    "Home": "AAA",
                    "Away": "BBB",
                    "home_win": f"{float(y):.1f}",
                    "Home Score": "5" if y else "3",
                    "Away Score": "3" if y else "5",
                    "Status": "Final",
                    "Home ML": "-130",
                    "Away ML": "+110",
                    "game_id": f"g_{i}",
                    "raw_model_prob_before_p10": "0.52",
                    "raw_model_prob_home": "0.52",
                    "indep_recent_win_rate_delta": "0.2" if y else "-0.2",
                    "indep_starter_era_delta": "-0.3" if y else "0.3",
                    "indep_bullpen_proxy_delta": "0.0",
                    "leakage_safe": "True",
                }
            )


def test_cli_writes_outputs(tmp_path):
    in_csv = tmp_path / "input.csv"
    _write_input_csv(in_csv)
    out_dir = tmp_path / "outputs" / "predictions" / "PAPER" / "p13_ml"
    cp = subprocess.run(
        [
            PYTHON,
            str(SCRIPT),
            "--input-csv",
            str(in_csv),
            "--output-dir",
            str(out_dir),
            "--min-train-size",
            "60",
            "--initial-train-months",
            "2",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    assert cp.returncode == 0, cp.stderr
    assert (out_dir / "ml_feature_matrix.csv").exists()
    assert (out_dir / "ml_walk_forward_predictions.jsonl").exists()
    assert (out_dir / "ml_odds_with_walk_forward_predictions.csv").exists()
    assert (out_dir / "ml_model_metadata.json").exists()
    assert (out_dir / "ml_candidate_summary.md").exists()


def test_cli_refuses_non_paper_output_dir(tmp_path):
    in_csv = tmp_path / "input.csv"
    _write_input_csv(in_csv, n=80)
    out_dir = tmp_path / "bad" / "prod"
    cp = subprocess.run(
        [PYTHON, str(SCRIPT), "--input-csv", str(in_csv), "--output-dir", str(out_dir)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    assert cp.returncode != 0
    assert "REFUSED" in cp.stderr

