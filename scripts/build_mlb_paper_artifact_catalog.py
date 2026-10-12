#!/usr/bin/env python3
"""Build the P243-A local paper artifact catalog."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wbc_backend.recommendation.paper_artifact_catalog import (  # noqa: E402
    DEFAULT_GENERATED_AT_UTC,
    DEFAULT_OUTPUT_DIR,
    PaperArtifactCatalogError,
    build_paper_artifact_catalog,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build a deterministic local catalog for P237-P242 paper artifacts."
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--generated-at-utc",
        default=DEFAULT_GENERATED_AT_UTC,
        help="fixed ISO timestamp for deterministic catalog outputs",
    )
    parser.add_argument("--quiet", action="store_true", help="suppress completion message")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = build_paper_artifact_catalog(
            output_dir=args.output_dir,
            generated_at_utc=args.generated_at_utc,
        )
    except PaperArtifactCatalogError as exc:
        parser.error(str(exc))
    if not args.quiet:
        print(
            f"Catalog {result.catalog['catalog_status']}: "
            f"{result.catalog['source_file_count']} files, "
            f"{result.catalog['source_total_bytes']} bytes"
        )
    return 0 if result.catalog["catalog_status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
