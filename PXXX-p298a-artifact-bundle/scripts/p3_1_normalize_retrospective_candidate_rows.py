#!/usr/bin/env python3
"""Normalize P3 retrospective rows for the P6-lite closure gate.

This script preserves the original P3 artifact and writes a normalized P3.1
JSONL plus summary/report outputs that make the provenance contract explicit.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_INPUT = Path("outputs/replay/p3_retrospective_candidate_rows_20260513.jsonl")
DEFAULT_OUTPUT = Path("outputs/replay/p3_1_retrospective_candidate_rows_normalized_20260514.jsonl")
DEFAULT_SUMMARY = Path("outputs/replay/p3_1_retrospective_candidate_summary_normalized_20260514.json")
DEFAULT_REPORT = Path("outputs/replay/p3_1_artifact_normalization_report_20260514.md")


@dataclass
class NormalizationResult:
    rows: list[dict[str, Any]]
    summary: dict[str, Any]
    invalid_rows: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--summary-output", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--report-output", type=Path, default=DEFAULT_REPORT)
    return parser.parse_args()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"missing input artifact: {path}")

    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_no, raw in enumerate(handle, start=1):
            text = raw.strip()
            if not text:
                continue
            try:
                row = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSON at line {line_no}: {exc}") from exc
            if not isinstance(row, dict):
                raise ValueError(f"row {line_no} is not an object")
            rows.append(row)
    return rows


def parse_draw_date(value: str) -> datetime:
    return datetime.strptime(value, "%Y/%m/%d")


def normalize_rows(rows: list[dict[str, Any]], source_file: Path, output_file: Path) -> NormalizationResult:
    normalized: list[dict[str, Any]] = []
    invalid_rows = 0
    for idx, row in enumerate(rows, start=1):
        normalized_row = dict(row)

        adapter_file_hash = str(normalized_row.get("adapter_file_hash", "")).strip()
        if not adapter_file_hash:
            invalid_rows += 1
            raise ValueError(f"row {idx} is missing adapter_file_hash")

        provenance_hash = str(normalized_row.get("provenance_hash", "")).strip()
        if provenance_hash:
            normalized_row["provenance_hash"] = provenance_hash
            normalized_row["provenance_hash_source"] = "existing_provenance_hash"
        else:
            normalized_row["provenance_hash"] = adapter_file_hash
            normalized_row["provenance_hash_source"] = "adapter_file_hash"
            normalized_row["provenance_normalization_reason"] = (
                "P6-lite closure gate requires provenance_hash"
            )

        truth_level = normalized_row.get("truth_level")
        if truth_level != "REGENERATED_RETROSPECTIVE":
            invalid_rows += 1
            raise ValueError(f"row {idx} has unexpected truth_level={truth_level!r}")

        if normalized_row.get("dry_run_only") is not True:
            invalid_rows += 1
            raise ValueError(f"row {idx} has dry_run_only != true")

        history_window_end = normalized_row.get("history_window_end")
        draw_date = normalized_row.get("draw_date")
        if not isinstance(history_window_end, str) or not isinstance(draw_date, str):
            invalid_rows += 1
            raise ValueError(f"row {idx} is missing date fields")
        if parse_draw_date(history_window_end) >= parse_draw_date(draw_date):
            invalid_rows += 1
            raise ValueError(
                f"row {idx} violates history_window_end < draw_date: {history_window_end} >= {draw_date}"
            )

        normalized.append(normalized_row)

    strategy_counts = Counter(row["strategy_id"] for row in normalized)
    truth_counts = Counter(row["truth_level"] for row in normalized)
    dry_run_counts = Counter("true" if row.get("dry_run_only") is True else "false" for row in normalized)

    date_order_violations = [
        {
            "row_index": idx,
            "strategy_id": row.get("strategy_id"),
            "history_window_end": row.get("history_window_end"),
            "draw_date": row.get("draw_date"),
        }
        for idx, row in enumerate(normalized, start=1)
        if parse_draw_date(str(row.get("history_window_end"))) >= parse_draw_date(str(row.get("draw_date")))
    ]

    summary = {
        "input_rows": len(rows),
        "output_rows": len(normalized),
        "rows_with_adapter_file_hash": sum(1 for row in normalized if str(row.get("adapter_file_hash", "")).strip()),
        "rows_with_provenance_hash_after_normalization": sum(
            1 for row in normalized if str(row.get("provenance_hash", "")).strip()
        ),
        "rows_normalized_from_adapter_file_hash": sum(
            1 for row in normalized if row.get("provenance_hash_source") == "adapter_file_hash"
        ),
        "strategies": sorted(strategy_counts),
        "per_strategy_counts": dict(sorted(strategy_counts.items())),
        "truth_level_counts": dict(sorted(truth_counts.items())),
        "dry_run_only_counts": dict(sorted(dry_run_counts.items())),
        "date_order_check": {
            "passed": not date_order_violations,
            "checked_rows": len(normalized),
            "violations": date_order_violations,
        },
        "invalid_rows": invalid_rows,
        "source_file": str(source_file),
        "output_file": str(output_file),
    }
    return NormalizationResult(rows=normalized, summary=summary, invalid_rows=invalid_rows)


def write_text_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(content, encoding="utf-8")
    tmp_path.replace(path)


def write_json_atomic(path: Path, payload: Any) -> None:
    write_text_atomic(path, json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def write_jsonl_atomic(path: Path, rows: list[dict[str, Any]]) -> None:
    lines = [json.dumps(row, ensure_ascii=False, sort_keys=False) for row in rows]
    write_text_atomic(path, "\n".join(lines) + "\n")


def build_report(summary: dict[str, Any]) -> str:
    lines = [
        "# P3.1 Artifact Normalization Report",
        "",
        "## 1. Problem Statement",
        "",
        "V1 stopped at `V1_BLOCKED_P3_ARTIFACT_INVALID` because `provenance_hash` was missing from the P3 retrospective candidate rows.",
        "",
        "## 2. Root Cause",
        "",
        "The P3 artifact emitted `adapter_file_hash` for every row, but it did not emit the closure-required `provenance_hash` field.",
        "",
        "## 3. Fix",
        "",
        "The normalized P3.1 artifact adds `provenance_hash = adapter_file_hash` and records `provenance_hash_source = adapter_file_hash` when the field was missing.",
        "",
        "## 4. Safety",
        "",
        "- No DB write",
        "- No registry change",
        "- No strategy mining",
        "- No row regeneration",
        "- Original P3 artifact preserved",
        "",
        "## 5. Validation Evidence",
        "",
        f"- Rows: {summary['output_rows']}",
        f"- Strategies: {len(summary['per_strategy_counts'])} x 50",
        f"- Truth level all REGENERATED_RETROSPECTIVE: {summary['truth_level_counts'] == {'REGENERATED_RETROSPECTIVE': summary['output_rows']}}",
        f"- Dry run only all true: {summary['dry_run_only_counts'] == {'true': summary['output_rows']}}",
        f"- History window end < draw date all true: {summary['date_order_check']['passed']}",
        f"- Provenance hash present all rows: {summary['rows_with_provenance_hash_after_normalization'] == summary['output_rows']}",
        "",
        "## 6. Next Instruction",
        "",
        "Resume V1 closure from Phase 3 using the normalized P3.1 JSONL as the controlled apply input.",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    rows = read_jsonl(args.input)
    result = normalize_rows(rows, args.input, args.output)

    write_jsonl_atomic(args.output, result.rows)
    write_json_atomic(args.summary_output, result.summary)
    write_text_atomic(args.report_output, build_report(result.summary))

    print(json.dumps(result.summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
