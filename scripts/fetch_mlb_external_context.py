#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wbc_backend.mlb_data.external_sources import fetch_and_materialize_external_context


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch external MLB context sources and materialize jsonl feeds.")
    parser.add_argument("--csv-path", default="data/mlb_2025/mlb_odds_2025_real.csv")
    parser.add_argument("--output-dir", default="data/mlb_context_sources")
    parser.add_argument("--start-date", default=None)
    parser.add_argument("--end-date", default=None)
    parser.add_argument("--max-games", type=int, default=50)
    args = parser.parse_args()
    summary = fetch_and_materialize_external_context(
        csv_path=args.csv_path,
        output_dir=args.output_dir,
        start_date=args.start_date,
        end_date=args.end_date,
        max_games=args.max_games,
    )
    print(json.dumps(summary.__dict__, ensure_ascii=False))


if __name__ == "__main__":
    main()
