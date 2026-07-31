#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from research.settlement_ingestion import ingest_settlements  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ingest research settlements into the isolated research layer.")
    parser.add_argument("--input", required=True, help="Path to a JSON or CSV settlement file.")
    parser.add_argument(
        "--research-dir",
        default=os.getenv("RESEARCH_DIR"),
        help="Optional research directory override. Defaults to RESEARCH_DIR or the repo research package directory.",
    )
    parser.add_argument(
        "--pending-hours",
        type=float,
        default=24.0,
        help="Hours after which unresolved predictions are flagged as pending.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    summary = ingest_settlements(
        args.input,
        base_dir=args.research_dir,
        pending_after_hours=args.pending_hours,
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
