#!/usr/bin/env python3
"""Diff two existing P243-A local paper artifact catalogs."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wbc_backend.recommendation.paper_artifact_catalog_diff import (  # noqa: E402
    DEFAULT_BASELINE_CATALOG_CSV,
    DEFAULT_BASELINE_CATALOG_JSON,
    DEFAULT_CURRENT_CATALOG_CSV,
    DEFAULT_CURRENT_CATALOG_JSON,
    DEFAULT_GENERATED_AT_UTC,
    DEFAULT_OUTPUT_DIR,
    PaperArtifactCatalogDiffError,
    diff_paper_artifact_catalogs,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Diff deterministic P243 paper artifact catalog snapshots."
    )
    parser.add_argument("--baseline-catalog-json", type=Path, default=DEFAULT_BASELINE_CATALOG_JSON)
    parser.add_argument("--baseline-catalog-csv", type=Path, default=DEFAULT_BASELINE_CATALOG_CSV)
    parser.add_argument("--current-catalog-json", type=Path, default=DEFAULT_CURRENT_CATALOG_JSON)
    parser.add_argument("--current-catalog-csv", type=Path, default=DEFAULT_CURRENT_CATALOG_CSV)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--fail-on-changes", action="store_true")
    parser.add_argument("--include-unchanged", action="store_true")
    parser.add_argument(
        "--generated-at-utc",
        default=DEFAULT_GENERATED_AT_UTC,
        help="fixed ISO timestamp for deterministic diff outputs",
    )
    parser.add_argument("--quiet", action="store_true", help="suppress completion message")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = diff_paper_artifact_catalogs(
            baseline_catalog_json=args.baseline_catalog_json,
            baseline_catalog_csv=args.baseline_catalog_csv,
            current_catalog_json=args.current_catalog_json,
            current_catalog_csv=args.current_catalog_csv,
            output_dir=args.output_dir,
            fail_on_changes=args.fail_on_changes,
            include_unchanged=args.include_unchanged,
            generated_at_utc=args.generated_at_utc,
        )
    except PaperArtifactCatalogDiffError as exc:
        parser.exit(2, f"{parser.prog}: error: {exc}\n")
    if not args.quiet:
        print(
            f"Diff {result.summary['diff_status']}: "
            f"{result.summary['added_count']} added, "
            f"{result.summary['removed_count']} removed, "
            f"{result.summary['changed_count']} changed, "
            f"{result.summary['unchanged_count']} unchanged"
        )
    return 0 if result.summary["diff_status"] in {"PASS", "WARN"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
