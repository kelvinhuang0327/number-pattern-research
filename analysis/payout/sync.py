"""Helpers to refresh hedge-fund outputs after draw or jackpot updates."""

from __future__ import annotations

import logging
import os
import subprocess
import sys


logger = logging.getLogger(__name__)


def refresh_hedge_fund_outputs(project_root: str) -> bool:
    script = os.path.join(project_root, 'tools', 'run_hedge_fund_architecture.py')
    if not os.path.exists(script):
        logger.warning("Hedge fund refresh skipped: script not found at %s", script)
        return False

    try:
        proc = subprocess.run(
            [sys.executable, script],
            cwd=project_root,
            capture_output=True,
            text=True,
            check=True,
        )
        logger.info("Hedge fund outputs refreshed successfully")
        if proc.stdout.strip():
            logger.info(proc.stdout.strip())
        return True
    except Exception as exc:
        logger.warning("Hedge fund refresh failed: %s", exc)
        return False
