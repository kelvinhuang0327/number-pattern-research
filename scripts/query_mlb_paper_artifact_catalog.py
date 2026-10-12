#!/usr/bin/env python3
"""Query/export the existing P243-A local paper artifact catalog."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wbc_backend.recommendation.paper_artifact_catalog_query import (  # noqa: E402
    DEFAULT_CATALOG_CSV,
    DEFAULT_CATALOG_JSON,
    DEFAULT_GENERATED_AT_UTC,
    DEFAULT_OUTPUT_DIR,
    PaperArtifactCatalogQueryError,
    PaperArtifactCatalogQueryFilters,
    query_paper_artifact_catalog,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Query/export the deterministic P243 paper artifact catalog."
    )
    parser.add_argument("--catalog-json", type=Path, default=DEFAULT_CATALOG_JSON)
    parser.add_argument("--catalog-csv", type=Path, default=DEFAULT_CATALOG_CSV)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--artifact-group", action="append", default=[])
    parser.add_argument("--file-type", action="append", default=[])
    parser.add_argument("--detected-role", action="append", default=[])
    parser.add_argument("--status", action="append", default=[])
    parser.add_argument("--include-warnings", action="store_true")
    parser.add_argument("--only-warnings", action="store_true")
    parser.add_argument("--only-failures", action="store_true")
    parser.add_argument(
        "--generated-at-utc",
        default=DEFAULT_GENERATED_AT_UTC,
        help="fixed ISO timestamp for deterministic query outputs",
    )
    parser.add_argument("--quiet", action="store_true", help="suppress completion message")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    filters = PaperArtifactCatalogQueryFilters(
        artifact_groups=tuple(args.artifact_group),
        file_types=tuple(args.file_type),
        detected_roles=tuple(args.detected_role),
        statuses=tuple(args.status),
        include_warnings=args.include_warnings,
        only_warnings=args.only_warnings,
        only_failures=args.only_failures,
    )
    try:
        result = query_paper_artifact_catalog(
            catalog_json=args.catalog_json,
            catalog_csv=args.catalog_csv,
            output_dir=args.output_dir,
            filters=filters,
            generated_at_utc=args.generated_at_utc,
        )
    except PaperArtifactCatalogQueryError as exc:
        parser.exit(2, f"{parser.prog}: error: {exc}\n")
    if not args.quiet:
        print(
            f"Query {result.summary['query_status']}: "
            f"{result.summary['matched_entries']} of "
            f"{result.summary['total_catalog_entries']} catalog entries matched"
        )
    return 0 if result.summary["query_status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

