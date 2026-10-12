from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Sequence


ROOT = Path(__file__).resolve().parents[2]


MODE_COMMANDS: dict[str, tuple[str, ...]] = {
    "wbc": ("main.py",),
    "mlb-paper": ("scripts", "run_mlb_paper_tracking.py"),
    "mlb-benchmark": ("scripts", "run_mlb_decision_quality.py"),
    "mlb-alpha": ("scripts", "run_mlb_alpha_discovery.py"),
    "spring": ("scripts", "run_mlb_snapshot_collection.py"),
}


def build_mode_command(mode: str, extra_args: Sequence[str] | None = None) -> list[str]:
    key = mode.strip().lower()
    if key not in MODE_COMMANDS:
        raise ValueError(f"Unknown mode: {mode}")
    rel = MODE_COMMANDS[key]
    command = [sys.executable, str(ROOT.joinpath(*rel))]
    if extra_args:
        command.extend(list(extra_args))
    return command


def launch_mode(mode: str, extra_args: Sequence[str] | None = None) -> int:
    command = build_mode_command(mode, extra_args=extra_args)
    return subprocess.run(command, cwd=str(ROOT), check=False).returncode
