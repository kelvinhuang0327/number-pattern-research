#!/usr/bin/env python3
"""Gate existing P245-A paper artifact diff outputs."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wbc_backend.recommendation.paper_artifact_diff_gate import (  # noqa: E402
    DEFAULT_DIFF_ENTRIES,
    DEFAULT_DIFF_SUMMARY,
    DEFAULT_GENERATED_AT_UTC,
    DEFAULT_OUTPUT_DIR,
    PaperArtifactDiffGateError,
    PaperArtifactDiffGatePolicy,
    gate_paper_artifact_diff,
)


def _non_negative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be >= 0")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Gate deterministic P245 paper artifact catalog diff outputs."
    )
    parser.add_argument("--diff-summary", type=Path, default=DEFAULT_DIFF_SUMMARY)
    parser.add_argument("--diff-entries", type=Path, default=DEFAULT_DIFF_ENTRIES)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--max-added", type=_non_negative_int, default=0)
    parser.add_argument("--max-removed", type=_non_negative_int, default=0)
    parser.add_argument("--max-changed", type=_non_negative_int, default=0)
    parser.add_argument("--max-warning", type=_non_negative_int, default=0)
    parser.add_argument("--allow-status-changes", action="store_true")
    parser.add_argument("--allow-role-changes", action="store_true")
    parser.add_argument("--allow-file-type-changes", action="store_true")
    parser.add_argument("--allow-notes-changes", action="store_true")
    parser.add_argument(
        "--generated-at-utc",
        default=DEFAULT_GENERATED_AT_UTC,
        help="fixed ISO timestamp for deterministic gate outputs",
    )
    parser.add_argument("--quiet", action="store_true", help="suppress completion message")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    policy = PaperArtifactDiffGatePolicy(
        max_added=args.max_added,
        max_removed=args.max_removed,
        max_changed=args.max_changed,
        max_warning=args.max_warning,
        allow_status_changes=args.allow_status_changes,
        allow_role_changes=args.allow_role_changes,
        allow_file_type_changes=args.allow_file_type_changes,
        allow_notes_changes=args.allow_notes_changes,
    )
    try:
        result = gate_paper_artifact_diff(
            diff_summary_path=args.diff_summary,
            diff_entries_path=args.diff_entries,
            output_dir=args.output_dir,
            policy=policy,
            generated_at_utc=args.generated_at_utc,
        )
    except PaperArtifactDiffGateError as exc:
        parser.exit(2, f"{parser.prog}: error: {exc}\n")
    if not args.quiet:
        counts = result.summary["observed_counts"]
        print(
            f"Gate {result.summary['gate_status']}: "
            f"{counts['added_count']} added, "
            f"{counts['removed_count']} removed, "
            f"{counts['changed_count']} changed, "
            f"{counts['warning_count']} input warnings"
        )
    return 0 if result.summary["gate_status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
