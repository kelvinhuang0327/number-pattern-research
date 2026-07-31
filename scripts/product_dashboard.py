#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wbc_backend.ux.product_dashboard import build_product_dashboard


def main() -> None:
    parser = argparse.ArgumentParser(description="Legacy dashboard alias; prefer python scripts/run_mode.py.")
    parser.add_argument(
        "--mode",
        default="all",
        choices=["all", "wbc", "mlb", "paper", "spring"],
        help="Focus the dashboard on one mode, or show everything.",
    )
    args = parser.parse_args()
    print(build_product_dashboard(mode=args.mode))


if __name__ == "__main__":
    main()
