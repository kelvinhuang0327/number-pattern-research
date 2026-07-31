#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wbc_backend.ux.mode_launcher import build_mode_command, launch_mode
from wbc_backend.ux.product_dashboard import build_product_dashboard


def main() -> int:
    parser = argparse.ArgumentParser(description="Unified launcher for WBC / MLB / Spring modes.")
    parser.add_argument(
        "--mode",
        default="dashboard",
        choices=["dashboard", "reports", "wbc", "mlb-paper", "mlb-benchmark", "mlb-alpha", "spring"],
        help="Which mode to show or run.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the command that would run and exit.",
    )
    args, extra_args = parser.parse_known_args()

    if args.mode == "dashboard":
        print(build_product_dashboard())
        return 0
    if args.mode == "reports":
        from wbc_backend.ux.report_center import build_report_center
        print(build_report_center())
        return 0

    command = build_mode_command(args.mode, extra_args=extra_args)
    if args.dry_run:
        print(" ".join(command))
        return 0
    return launch_mode(args.mode, extra_args=extra_args)


if __name__ == "__main__":
    raise SystemExit(main())
