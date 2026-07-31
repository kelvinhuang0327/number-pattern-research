#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wbc_backend.ux.report_center import build_report_center


def main() -> None:
    print(build_report_center())


if __name__ == "__main__":
    main()
